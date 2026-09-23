import math
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

import yfinance as yf
from django.utils import timezone

from .models import MarketDataSnapshot, NewsArticle
from apps.research.models import StockTicker


class SymbolNotFound(Exception):
    """Raised when a ticker cannot be resolved on any supported exchange."""


# Yahoo needs an exchange suffix for Indian listings: .NS = NSE, .BO = BSE.
# A bare symbol is tried first so US tickers keep working unchanged.
EXCHANGE_SUFFIXES = ('', '.NS', '.BO')

# Several Indian companies also trade as US ADRs under their bare symbol
# (INFY and WIT are on the NYSE in USD). When the caller already knows which
# market it wants, try that market's suffixes before the bare symbol.
SUFFIXES_BY_CURRENCY = {
    'INR': ('.NS', '.BO'),
}


def quote_price(info):
    """The quote price, or None if Yahoo returned an empty/unknown symbol."""
    if not info:
        return None
    for key in ('currentPrice', 'regularMarketPrice', 'previousClose'):
        value = info.get(key)
        if value is not None:
            return value
    return None


def resolve_symbol(symbol, prefer_currency=None):
    """
    Resolve a user-typed symbol to a live Yahoo ticker.

    'RELIANCE' -> ('RELIANCE.NS', <Ticker>, info), 'AAPL' -> ('AAPL', ...).
    A symbol that already carries a suffix ('TCS.NS') is used verbatim.
    `prefer_currency` biases the search toward one market, so comparing
    'INFY' against an INR stock finds INFY.NS rather than the NYSE ADR.
    Raises SymbolNotFound when nothing resolves, so callers never silently
    persist a zero price.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise SymbolNotFound('No ticker symbol supplied.')

    if '.' in symbol:
        candidates = [symbol]
    else:
        preferred = SUFFIXES_BY_CURRENCY.get(prefer_currency, ())
        order = list(preferred) + [s for s in EXCHANGE_SUFFIXES if s not in preferred]
        candidates = [symbol + s for s in order]

    for candidate in candidates:
        try:
            ticker = yf.Ticker(candidate)
            info = ticker.info
        except Exception:
            continue
        if quote_price(info) is not None:
            return candidate, ticker, info

    raise SymbolNotFound(
        "'{0}' did not resolve on Yahoo Finance. Indian listings need an exchange "
        "suffix, e.g. {0}.NS (NSE) or {0}.BO (BSE).".format(symbol)
    )


def _news_content(article):
    """
    yfinance >= 0.2.55 nests article fields under 'content'; older releases
    return them flat. Accept both.
    """
    content = article.get('content')
    return content if isinstance(content, dict) else article


def _news_url(content, article):
    for key in ('canonicalUrl', 'clickThroughUrl'):
        block = content.get(key)
        if isinstance(block, dict) and block.get('url'):
            return block['url']
    return content.get('link') or article.get('link') or ''


def _news_published_at(content, article):
    raw = content.get('pubDate') or content.get('displayTime')
    if raw:
        try:
            # Yahoo sends RFC 3339 with a trailing 'Z'.
            return datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        except ValueError:
            pass

    epoch = content.get('providerPublishTime') or article.get('providerPublishTime')
    if epoch:
        return datetime.fromtimestamp(epoch, tz=dt_timezone.utc)

    return timezone.now()


def _news_source(content, article):
    provider = content.get('provider')
    if isinstance(provider, dict) and provider.get('displayName'):
        return provider['displayName']
    return content.get('publisher') or article.get('publisher') or 'Unknown'


def normalize_news(articles, limit=5):
    """Flatten raw yfinance news into dicts the rest of the app can rely on."""
    normalized = []
    for article in articles or []:
        content = _news_content(article)
        title = content.get('title')
        if not title:
            continue
        normalized.append({
            'title': title[:500],
            'url': _news_url(content, article),
            'source': _news_source(content, article)[:100],
            'published_at': _news_published_at(content, article),
            'summary': content.get('summary') or content.get('description') or '',
        })
        if len(normalized) >= limit:
            break
    return normalized


def annualized_volatility(history):
    """Annualized stdev of daily returns, as a percentage. None if too few rows."""
    if history is None or len(history) < 5:
        return None
    returns = history['Close'].pct_change().dropna()
    if returns.empty:
        return None
    daily = float(returns.std())
    if math.isnan(daily):
        return None
    return round(daily * math.sqrt(252) * 100, 1)


def pct_change_over(history, sessions):
    """Percent move across the last `sessions` trading days, or None."""
    if history is None or len(history) < sessions + 1:
        return None
    closes = history['Close']
    past, latest = float(closes.iloc[-(sessions + 1)]), float(closes.iloc[-1])
    if not past:
        return None
    return round((latest - past) / past * 100, 2)


class MarketDataManager:
    """
    Utility class to fetch and persist market data using yfinance.
    """

    def __init__(self, ticker_symbol, prefer_currency=None):
        self.prefer_currency = prefer_currency
        self.input_symbol = ticker_symbol.strip().upper()
        self.symbol = self.input_symbol
        self.ticker = None
        self.yf_ticker = None
        self.info = None

    def _set_ticker_instance(self, company_name=None):
        """Ensures the StockTicker instance exists in the DB."""
        self.ticker, created = StockTicker.objects.get_or_create(
            symbol=self.symbol,
            defaults={'company_name': company_name or self.symbol},
        )
        # Backfill the placeholder name written by earlier runs.
        if not created and company_name and self.ticker.company_name in ('', self.symbol):
            self.ticker.company_name = company_name
            self.ticker.save(update_fields=['company_name'])

    @staticmethod
    def _fetch_history(symbol, yf_ticker, period='1y'):
        try:
            return yf_ticker.history(period=period)
        except Exception:
            return None

    def fetch_data(self):
        """
        Resolves the symbol, then fetches core info, history, and news.
        Raises SymbolNotFound if the ticker does not exist on any exchange.
        """
        self.symbol, self.yf_ticker, self.info = resolve_symbol(
            self.input_symbol, prefer_currency=self.prefer_currency)
        info = self.info

        self._set_ticker_instance(info.get('longName') or info.get('shortName'))

        history = self._fetch_history(self.symbol, self.yf_ticker)

        # Yahoo serves only the current session for BSE (.BO) listings, which
        # leaves no data for the chart or the volatility figure. The NSE twin
        # of the same company carries the full series, so borrow it.
        if (history is None or len(history) < 5) and self.symbol.endswith('.BO'):
            nse_symbol = self.symbol[:-3] + '.NS'
            fallback = self._fetch_history(nse_symbol, yf.Ticker(nse_symbol))
            if fallback is not None and len(fallback) >= 5:
                history = fallback

        try:
            news = self.yf_ticker.news
        except Exception:
            news = []

        return {
            'symbol': self.symbol,
            'info': info,
            'currency': info.get('currency') or 'USD',
            'latest_price': self._to_decimal(quote_price(info)),
            'history': history,
            'news': normalize_news(news),
        }

    def save_to_db(self, data):
        """
        Saves a snapshot and news articles to the database.
        """
        info = data['info']

        snapshot = MarketDataSnapshot.objects.create(
            ticker=self.ticker,
            price=data['latest_price'],
            currency=data['currency'],
            open_price=self._to_decimal(info.get('open') or info.get('regularMarketOpen')),
            high=self._to_decimal(info.get('dayHigh') or info.get('regularMarketDayHigh')),
            low=self._to_decimal(info.get('dayLow') or info.get('regularMarketDayLow')),
            volume=info.get('volume') or info.get('regularMarketVolume'),
            market_cap=info.get('marketCap'),
            pe_ratio=self._to_decimal(info.get('trailingPE')),
            dividend_yield=self._to_decimal(info.get('dividendYield')),
            data_source='yahoo_finance',
        )

        for article in data['news']:
            if not article['url']:
                continue
            NewsArticle.objects.get_or_create(
                ticker=self.ticker,
                url=article['url'],
                defaults={
                    'title': article['title'],
                    'source': article['source'],
                    'published_at': article['published_at'],
                    'summary': article['summary'],
                },
            )

        return snapshot

    def _to_decimal(self, value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return None
