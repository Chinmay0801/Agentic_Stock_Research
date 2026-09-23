"""
Tests for symbol resolution, news normalisation and snapshot persistence.

Yahoo Finance is mocked throughout — the suite runs offline and
deterministically.
"""
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
from django.test import TestCase

from apps.market_data.models import MarketDataSnapshot, NewsArticle
from apps.market_data.utils import (
    MarketDataManager,
    SymbolNotFound,
    annualized_volatility,
    normalize_news,
    pct_change_over,
    resolve_symbol,
)


def make_history(closes):
    """A minimal OHLCV frame shaped like yfinance's."""
    index = pd.date_range('2026-01-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': closes, 'Open': closes, 'High': closes,
                         'Low': closes, 'Volume': [1000] * len(closes)}, index=index)


class FakeTicker:
    """Stands in for yf.Ticker. Unknown symbols return an empty info dict."""

    REGISTRY = {}

    def __init__(self, symbol):
        self.symbol = symbol
        self._data = self.REGISTRY.get(symbol)

    @property
    def info(self):
        return (self._data or {}).get('info', {})

    @property
    def news(self):
        return (self._data or {}).get('news', [])

    def history(self, period='1y'):
        return (self._data or {}).get('history', make_history([]))


def register(symbol, price, currency='USD', **extra):
    info = {'currentPrice': price, 'currency': currency,
            'longName': extra.pop('long_name', symbol), **extra}
    FakeTicker.REGISTRY[symbol] = {
        'info': info,
        'news': [],
        'history': make_history([price] * 30),
    }


class ResolveSymbolTests(TestCase):
    def setUp(self):
        FakeTicker.REGISTRY.clear()
        patcher = patch('apps.market_data.utils.yf.Ticker', FakeTicker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_bare_us_symbol_resolves_as_typed(self):
        register('AAPL', 200.0)
        symbol, _ticker, info = resolve_symbol('AAPL')
        self.assertEqual(symbol, 'AAPL')
        self.assertEqual(info['currency'], 'USD')

    def test_bare_indian_symbol_falls_back_to_nse(self):
        register('RELIANCE.NS', 1250.0, currency='INR')
        symbol, _ticker, info = resolve_symbol('RELIANCE')
        self.assertEqual(symbol, 'RELIANCE.NS')
        self.assertEqual(info['currency'], 'INR')

    def test_falls_back_to_bse_when_nse_is_missing(self):
        register('SOMECO.BO', 42.0, currency='INR')
        symbol, _ticker, _info = resolve_symbol('SOMECO')
        self.assertEqual(symbol, 'SOMECO.BO')

    def test_explicit_suffix_is_used_verbatim(self):
        register('INFY.BO', 1000.0, currency='INR')
        register('INFY', 20.0)  # the NYSE ADR, which must not win here
        symbol, _ticker, _info = resolve_symbol('INFY.BO')
        self.assertEqual(symbol, 'INFY.BO')

    def test_prefer_currency_picks_nse_over_us_adr(self):
        """INFY is a real NYSE ticker; an INR preference must reach INFY.NS."""
        register('INFY', 20.0, currency='USD')
        register('INFY.NS', 1500.0, currency='INR')

        self.assertEqual(resolve_symbol('INFY')[0], 'INFY')
        self.assertEqual(resolve_symbol('INFY', prefer_currency='INR')[0], 'INFY.NS')

    def test_unknown_symbol_raises_rather_than_returning_zero(self):
        with self.assertRaises(SymbolNotFound) as ctx:
            resolve_symbol('NOSUCHTICKER')
        self.assertIn('.NS', str(ctx.exception))

    def test_blank_symbol_raises(self):
        with self.assertRaises(SymbolNotFound):
            resolve_symbol('   ')

    def test_whitespace_and_case_are_normalised(self):
        register('TCS.NS', 2089.6, currency='INR')
        self.assertEqual(resolve_symbol('  tcs  ')[0], 'TCS.NS')


class NormalizeNewsTests(TestCase):
    def test_reads_the_nested_schema_used_by_yfinance_1x(self):
        articles = [{
            'id': 'abc',
            'content': {
                'title': 'Reliance gains on tax relief',
                'summary': 'A summary.',
                'pubDate': '2026-09-18T10:12:51Z',
                'provider': {'displayName': 'Simply Wall St.'},
                'canonicalUrl': {'url': 'https://example.com/a'},
            },
        }]
        (article,) = normalize_news(articles)
        self.assertEqual(article['title'], 'Reliance gains on tax relief')
        self.assertEqual(article['source'], 'Simply Wall St.')
        self.assertEqual(article['url'], 'https://example.com/a')
        self.assertEqual(article['published_at'].year, 2026)

    def test_still_reads_the_old_flat_schema(self):
        articles = [{
            'title': 'Legacy headline',
            'link': 'https://example.com/legacy',
            'publisher': 'Reuters',
            'providerPublishTime': 1758000000,
        }]
        (article,) = normalize_news(articles)
        self.assertEqual(article['title'], 'Legacy headline')
        self.assertEqual(article['source'], 'Reuters')
        self.assertEqual(article['url'], 'https://example.com/legacy')

    def test_articles_without_a_title_are_skipped(self):
        self.assertEqual(normalize_news([{'content': {'summary': 'no title'}}]), [])

    def test_respects_the_limit(self):
        articles = [{'content': {'title': 'H{0}'.format(i)}} for i in range(10)]
        self.assertEqual(len(normalize_news(articles, limit=3)), 3)

    def test_handles_missing_news(self):
        self.assertEqual(normalize_news(None), [])


class HistoryMathTests(TestCase):
    def test_pct_change_over_one_session(self):
        history = make_history([100.0, 110.0])
        self.assertAlmostEqual(pct_change_over(history, 1), 10.0)

    def test_pct_change_returns_none_without_enough_rows(self):
        self.assertIsNone(pct_change_over(make_history([100.0]), 5))
        self.assertIsNone(pct_change_over(None, 1))

    def test_volatility_is_zero_for_a_flat_series(self):
        self.assertEqual(annualized_volatility(make_history([100.0] * 30)), 0.0)

    def test_volatility_needs_a_minimum_history(self):
        self.assertIsNone(annualized_volatility(make_history([100.0, 101.0])))
        self.assertIsNone(annualized_volatility(None))


class MarketDataManagerTests(TestCase):
    def setUp(self):
        FakeTicker.REGISTRY.clear()
        patcher = patch('apps.market_data.utils.yf.Ticker', FakeTicker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saves_snapshot_with_the_reported_currency(self):
        register('TCS.NS', 2089.6, currency='INR', long_name='Tata Consultancy Services',
                 trailingPE=15.34, marketCap=7560355643392, dayHigh=2104.2,
                 dayLow=2077.6, volume=2226378)

        manager = MarketDataManager('TCS')
        snapshot = manager.save_to_db(manager.fetch_data())

        self.assertEqual(manager.symbol, 'TCS.NS')
        self.assertEqual(snapshot.currency, 'INR')
        self.assertEqual(snapshot.price, Decimal('2089.6'))
        self.assertEqual(snapshot.ticker.symbol, 'TCS.NS')
        self.assertEqual(snapshot.ticker.company_name, 'Tata Consultancy Services')

    def test_unknown_symbol_never_persists_a_zero_price(self):
        manager = MarketDataManager('NOSUCHTICKER')
        with self.assertRaises(SymbolNotFound):
            manager.fetch_data()
        self.assertEqual(MarketDataSnapshot.objects.count(), 0)

    def test_news_is_persisted_and_deduplicated(self):
        register('AAPL', 200.0)
        FakeTicker.REGISTRY['AAPL']['news'] = [{
            'content': {
                'title': 'Apple beats estimates',
                'pubDate': '2026-09-23T10:00:00Z',
                'provider': {'displayName': 'Reuters'},
                'canonicalUrl': {'url': 'https://example.com/apple'},
            },
        }]

        manager = MarketDataManager('AAPL')
        data = manager.fetch_data()
        manager.save_to_db(data)
        manager.save_to_db(data)  # a repeat search must not duplicate rows

        self.assertEqual(NewsArticle.objects.count(), 1)
        article = NewsArticle.objects.get()
        self.assertEqual(article.title, 'Apple beats estimates')
        self.assertEqual(article.source, 'Reuters')
        self.assertNotEqual(article.published_at.year, 1970)

    def test_bse_history_falls_back_to_the_nse_twin(self):
        register('INFY.BO', 1019.2, currency='INR')
        register('INFY.NS', 1020.5, currency='INR')
        # Yahoo serves only the current session for BSE listings.
        FakeTicker.REGISTRY['INFY.BO']['history'] = make_history([1019.2])
        FakeTicker.REGISTRY['INFY.NS']['history'] = make_history(
            [1000.0 + i for i in range(30)])

        data = MarketDataManager('INFY.BO').fetch_data()

        self.assertEqual(data['symbol'], 'INFY.BO')
        self.assertEqual(len(data['history']), 30)
