"""
Tests for the research API: report building, comparison guards and quotes.

Yahoo Finance is mocked via the FakeTicker registry in market_data.tests, so
the suite runs offline.
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.market_data.tests import FakeTicker, register
from apps.research.report_builder import (
    MarketMismatch,
    _winner,
    build_comparison,
    format_market_cap,
    format_pct,
    score_headline,
)


class MockedYahooTestCase(TestCase):
    """Patches yfinance and gives every test a clean ticker registry."""

    def setUp(self):
        FakeTicker.REGISTRY.clear()
        patcher = patch('apps.market_data.utils.yf.Ticker', FakeTicker)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = APIClient()


class FormattingTests(TestCase):
    def test_market_cap_uses_the_right_magnitude(self):
        self.assertEqual(format_market_cap(1.689e13, '₹'), '₹16.89T')
        self.assertEqual(format_market_cap(7.92e11, '$'), '$792.0B')
        self.assertEqual(format_market_cap(5.5e6, '$'), '$5.5M')

    def test_market_cap_handles_missing_values(self):
        self.assertEqual(format_market_cap(None, '$'), 'N/A')
        self.assertEqual(format_market_cap(0, '$'), 'N/A')

    def test_percentages_carry_an_explicit_sign(self):
        self.assertEqual(format_pct(2.854), '+2.85%')
        self.assertEqual(format_pct(-1.5), '-1.5%')
        self.assertEqual(format_pct(None), 'N/A')

    def test_headline_sentiment_scores_by_keyword(self):
        self.assertGreater(score_headline('Apple beats estimates, shares rally'), 0)
        self.assertLess(score_headline('Profit misses, shares plunge on weak guidance'), 0)
        self.assertEqual(score_headline('Company announces annual meeting date'), 0.0)


class WinnerTests(TestCase):
    def test_higher_wins_for_growth_metrics(self):
        self.assertEqual(_winner(16.4, 2.9, 'high'), 'left')
        self.assertEqual(_winner(2.9, 16.4, 'high'), 'right')

    def test_lower_wins_for_pe_and_debt(self):
        self.assertEqual(_winner(15.2, 38.6, 'low'), 'left')
        self.assertEqual(_winner(90.0, 36.7, 'low'), 'right')

    def test_equal_values_tie(self):
        self.assertEqual(_winner(10.0, 10.0, 'high'), 'tie')

    def test_missing_values_are_not_scored(self):
        self.assertIsNone(_winner(None, 10.0, 'high'))
        self.assertIsNone(_winner(10.0, None, 'low'))

    def test_unscored_rows_return_none(self):
        self.assertIsNone(_winner(100, 200, None))

    def test_negative_pe_is_not_treated_as_cheap(self):
        """A loss-making company has a negative P/E; that must not 'win'."""
        self.assertIsNone(_winner(-5.0, 30.0, 'low'))


class QuickDemoReportTests(MockedYahooTestCase):
    URL = '/api/research/quick-demo/'

    def test_returns_live_data_for_a_us_ticker(self):
        register('AAPL', 337.5, long_name='Apple Inc.', exchange='NMS',
                 sector='Technology', trailingPE=38.6, marketCap=4.9e12,
                 fiftyTwoWeekHigh=345.34, fiftyTwoWeekLow=243.42,
                 recommendationKey='buy', targetMeanPrice=328.2,
                 numberOfAnalystOpinions=39)

        response = self.client.post(self.URL, {'ticker': 'AAPL'}, format='json')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['ticker_symbol'], 'AAPL')
        self.assertEqual(body['company_name'], 'Apple Inc.')
        self.assertEqual(body['snapshot']['currency'], '$')
        self.assertEqual(body['snapshot']['price'], 337.5)
        self.assertEqual(body['snapshot']['recommendation'], 'BUY')

    def test_resolves_a_bare_indian_symbol_and_reports_rupees(self):
        register('TCS.NS', 2089.6, currency='INR',
                 long_name='Tata Consultancy Services Limited', exchange='NSI')

        response = self.client.post(self.URL, {'ticker': 'TCS'}, format='json')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['ticker_symbol'], 'TCS.NS')
        self.assertEqual(body['requested_symbol'], 'TCS')
        self.assertEqual(body['snapshot']['currency'], '₹')
        self.assertEqual(body['snapshot']['currency_code'], 'INR')

    def test_unknown_ticker_returns_404_not_a_made_up_price(self):
        response = self.client.post(self.URL, {'ticker': 'ZZQQ99'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertIn('did not resolve', response.json()['detail'])

    def test_missing_ticker_returns_400(self):
        self.assertEqual(self.client.post(self.URL, {}, format='json').status_code, 400)

    def test_report_carries_the_full_frontend_contract(self):
        register('AAPL', 337.5, trailingPE=38.6)
        body = self.client.post(self.URL, {'ticker': 'AAPL'}, format='json').json()

        for key in ('snapshot', 'summary', 'fundamental_analysis',
                    'sentiment_analysis', 'risk_assessment', 'valuation',
                    'chart_data'):
            self.assertIn(key, body)
        for key in ('price', 'currency', 'mcap', 'pe', 'diff1d', 'diff1w',
                    'recommendation'):
            self.assertIn(key, body['snapshot'])


class CompareTests(MockedYahooTestCase):
    URL = '/api/research/compare/'

    def register_indian_pair(self):
        register('TCS.NS', 2089.6, currency='INR', trailingPE=15.2,
                 revenueGrowth=0.139, profitMargins=0.181)
        register('INFY.NS', 1020.5, currency='INR', trailingPE=13.1,
                 revenueGrowth=0.029, profitMargins=0.164)

    def test_compares_two_indian_stocks_from_bare_symbols(self):
        self.register_indian_pair()
        register('INFY', 20.0, currency='USD')  # the NYSE ADR must not be picked

        response = self.client.post(
            self.URL, {'ticker1': 'TCS', 'ticker2': 'INFY'}, format='json')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['left']['symbol'], 'TCS.NS')
        self.assertEqual(body['right']['symbol'], 'INFY.NS')
        self.assertEqual(body['market'], 'India')
        self.assertEqual(body['currency_code'], 'INR')

    def test_scores_metrics_in_the_right_direction(self):
        self.register_indian_pair()
        body = self.client.post(
            self.URL, {'ticker1': 'TCS', 'ticker2': 'INFY'}, format='json').json()
        rows = {row['key']: row for row in body['rows']}

        # Lower P/E is better, so INFY.NS (13.1) beats TCS.NS (15.2).
        self.assertEqual(rows['pe_ratio']['better'], 'right')
        # Higher revenue growth is better, so TCS.NS wins.
        self.assertEqual(rows['revenue_growth']['better'], 'left')
        # Price is shown but never scored.
        self.assertIsNone(rows['price']['better'])

    def test_rejects_a_cross_market_comparison(self):
        register('TCS.NS', 2089.6, currency='INR')
        register('AAPL', 337.5, currency='USD')

        response = self.client.post(
            self.URL, {'ticker1': 'TCS', 'ticker2': 'AAPL'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('same market', response.json()['detail'])

    def test_rejects_comparing_a_stock_with_itself(self):
        register('RELIANCE.NS', 1248.0, currency='INR')
        response = self.client.post(
            self.URL, {'ticker1': 'RELIANCE', 'ticker2': 'RELIANCE.NS'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('two different stocks', response.json()['detail'])

    def test_unknown_ticker_returns_404(self):
        register('TCS.NS', 2089.6, currency='INR')
        response = self.client.post(
            self.URL, {'ticker1': 'TCS', 'ticker2': 'ZZQQ99'}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_requires_both_tickers(self):
        response = self.client.post(self.URL, {'ticker1': 'TCS'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_mismatch_is_raised_by_the_builder_too(self):
        register('TCS.NS', 2089.6, currency='INR')
        register('AAPL', 337.5, currency='USD')
        with self.assertRaises(MarketMismatch):
            build_comparison('TCS', 'AAPL')


class QuotesTests(MockedYahooTestCase):
    URL = '/api/research/quotes/'

    def test_returns_a_quote_per_symbol(self):
        register('TCS.NS', 2089.6, currency='INR', regularMarketChangePercent=-0.73)
        register('AAPL', 337.5, regularMarketChangePercent=1.2)

        response = self.client.get(self.URL, {'symbols': 'TCS,AAPL'})

        self.assertEqual(response.status_code, 200)
        quotes = {q['requested_symbol']: q for q in response.json()['quotes']}
        self.assertEqual(quotes['TCS']['symbol'], 'TCS.NS')
        self.assertEqual(quotes['TCS']['currency'], '₹')
        self.assertEqual(quotes['TCS']['change_display'], '-0.73%')
        self.assertEqual(quotes['AAPL']['change_display'], '+1.2%')

    def test_one_bad_symbol_does_not_sink_the_batch(self):
        register('AAPL', 337.5)
        body = self.client.get(self.URL, {'symbols': 'AAPL,ZZQQ99'}).json()

        quotes = {q['requested_symbol']: q for q in body['quotes']}
        self.assertIsNone(quotes['AAPL']['error'])
        self.assertIn('did not resolve', quotes['ZZQQ99']['error'])

    def test_duplicates_are_collapsed(self):
        register('AAPL', 337.5)
        body = self.client.get(self.URL, {'symbols': 'AAPL,AAPL,aapl'}).json()
        self.assertEqual(body['count'], 1)

    def test_requires_the_symbols_parameter(self):
        self.assertEqual(self.client.get(self.URL).status_code, 400)


class HealthTests(TestCase):
    def test_health_endpoint_reports_ok(self):
        response = APIClient().get('/api/research/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
