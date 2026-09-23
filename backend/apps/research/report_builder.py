"""
Builds a research report payload from live Yahoo Finance data.

Every number here comes from yfinance. The narrative strings are templated
from those numbers rather than invented, so the text and the metrics can
never disagree. Headline sentiment is a transparent keyword score, not a
model call, so this endpoint keeps working without an LLM API key.
"""
import datetime
import logging

from apps.market_data.utils import (
    MarketDataManager,
    SymbolNotFound,
    quote_price,
    annualized_volatility,
    pct_change_over,
    resolve_symbol,
)

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {
    'USD': '$', 'INR': '₹', 'EUR': '€', 'GBP': '£',
    'JPY': '¥', 'CNY': '¥', 'HKD': 'HK$', 'AUD': 'A$', 'CAD': 'C$',
}

# Yahoo's analyst consensus, collapsed onto the three badges the UI styles.
RECOMMENDATION_MAP = {
    'strong_buy': 'BUY', 'buy': 'BUY', 'outperform': 'BUY',
    'hold': 'HOLD', 'neutral': 'HOLD',
    'sell': 'SELL', 'underperform': 'SELL', 'strong_sell': 'SELL',
}

POSITIVE_WORDS = (
    'beat', 'beats', 'surge', 'surges', 'rally', 'rallies', 'gain', 'gains',
    'jump', 'jumps', 'record', 'upgrade', 'upgrades', 'growth', 'profit',
    'outperform', 'strong', 'boost', 'wins', 'high', 'raises', 'bullish',
)
NEGATIVE_WORDS = (
    'miss', 'misses', 'fall', 'falls', 'drop', 'drops', 'plunge', 'plunges',
    'slump', 'decline', 'declines', 'loss', 'losses', 'downgrade', 'cut',
    'cuts', 'weak', 'probe', 'lawsuit', 'fine', 'slide', 'bearish', 'warns',
)


def currency_symbol(code):
    return CURRENCY_SYMBOLS.get(code, (code or '') + ' ')


def format_market_cap(value, symbol):
    """1.69e13 -> '₹16.89T'. Returns 'N/A' when Yahoo omits the field."""
    if not value:
        return 'N/A'
    for divisor, suffix in ((1e12, 'T'), (1e9, 'B'), (1e6, 'M')):
        if value >= divisor:
            return '{0}{1}{2}'.format(symbol, round(value / divisor, 2), suffix)
    return '{0}{1}'.format(symbol, round(value, 2))


def format_pct(value):
    """A signed percentage string, or 'N/A' when the input is missing."""
    if value is None:
        return 'N/A'
    return '{0}{1}%'.format('+' if value >= 0 else '', round(value, 2))


def score_headline(title):
    """Keyword sentiment in [-1, 1] for a single headline."""
    words = set(title.lower().replace(',', ' ').replace('.', ' ').split())
    positive = len(words & set(POSITIVE_WORDS))
    negative = len(words & set(NEGATIVE_WORDS))
    if positive == negative:
        return 0.0
    return round((positive - negative) / float(positive + negative), 2)


def _label(score):
    if score > 0:
        return 'Positive', 'positive'
    if score < 0:
        return 'Negative', 'negative'
    return 'Neutral', 'neutral'


def _pct(value):
    """Yahoo returns growth/margin ratios as fractions; render them as percent."""
    return None if value is None else round(value * 100, 1)


def build_strengths(info, price, symbol):
    out = []
    revenue_growth = _pct(info.get('revenueGrowth'))
    if revenue_growth is not None and revenue_growth > 0:
        out.append('Revenue growing {0}% year over year'.format(revenue_growth))

    margins = _pct(info.get('profitMargins'))
    if margins is not None and margins > 10:
        out.append('Healthy net profit margin of {0}%'.format(margins))

    roe = _pct(info.get('returnOnEquity'))
    if roe is not None and roe > 15:
        out.append('Strong return on equity at {0}%'.format(roe))

    debt = info.get('debtToEquity')
    if debt is not None and debt < 50:
        out.append('Conservative balance sheet (debt/equity {0})'.format(round(debt, 1)))

    dividend = info.get('dividendYield')
    if dividend and dividend > 1:
        out.append('Pays a {0}% dividend yield'.format(round(dividend, 2)))

    target = info.get('targetMeanPrice')
    if target and price and target > price:
        upside = round((target - price) / price * 100, 1)
        out.append('Analyst mean target implies {0}% upside ({1}{2})'.format(
            upside, symbol, round(target, 2)))

    return out or ['No standout strengths in the reported fundamentals.']


def build_weaknesses(info, price):
    out = []
    pe = info.get('trailingPE')
    if pe and pe > 40:
        out.append('Elevated trailing P/E of {0}'.format(round(pe, 1)))

    debt = info.get('debtToEquity')
    if debt is not None and debt > 100:
        out.append('Leveraged balance sheet (debt/equity {0})'.format(round(debt, 1)))

    earnings_growth = _pct(info.get('earningsGrowth'))
    if earnings_growth is not None and earnings_growth < 0:
        out.append('Earnings contracted {0}% year over year'.format(abs(earnings_growth)))

    margins = _pct(info.get('profitMargins'))
    if margins is not None and margins < 10:
        out.append('Thin net margin of {0}%'.format(margins))

    high52 = info.get('fiftyTwoWeekHigh')
    if high52 and price and price >= high52 * 0.95:
        out.append('Trading within 5% of its 52-week high, limiting near-term upside')

    analysts = info.get('numberOfAnalystOpinions')
    if analysts is not None and analysts < 5:
        out.append('Thin analyst coverage ({0} opinions)'.format(analysts))

    return out or ['No material weaknesses flagged by the reported metrics.']


def build_warnings(info, price, volatility):
    out = []
    if volatility is not None and volatility > 35:
        out.append('High realised volatility of {0}% annualised'.format(volatility))

    beta = info.get('beta')
    if beta is not None and beta > 1.2:
        out.append('Beta of {0} means it amplifies broad market moves'.format(round(beta, 2)))

    low52, high52 = info.get('fiftyTwoWeekLow'), info.get('fiftyTwoWeekHigh')
    if low52 and high52 and price:
        band = high52 - low52
        if band > 0:
            position = (price - low52) / band * 100
            if position > 80:
                out.append('Priced in the top 20% of its 52-week range')
            elif position < 20:
                out.append('Priced in the bottom 20% of its 52-week range — check for a value trap')

    debt = info.get('debtToEquity')
    if debt is not None and debt > 100:
        out.append('Debt/equity of {0} raises refinancing risk if rates stay high'.format(round(debt, 1)))

    if not info.get('trailingPE'):
        out.append('No trailing P/E reported — the company may be loss-making')

    return out or ['No elevated risk signals in the reported metrics.']


def build_report(ticker_symbol, query=None):
    """
    Fetch live data for `ticker_symbol` and assemble the report payload the
    React frontend consumes. Propagates SymbolNotFound for unknown tickers.
    """
    manager = MarketDataManager(ticker_symbol)
    data = manager.fetch_data()

    # Persist what we just fetched so the admin panel and the market-data API
    # reflect real searches. A storage failure must not sink the response.
    try:
        manager.save_to_db(data)
    except Exception:
        logger.exception('Could not persist market data for %s', manager.symbol)

    info = data['info']
    resolved = data['symbol']
    history = data['history']
    code = data['currency']
    symbol = currency_symbol(code)

    price = float(data['latest_price'])
    name = info.get('longName') or info.get('shortName') or resolved
    sector = info.get('sector') or 'its sector'
    pe = info.get('trailingPE')
    pe_display = round(pe, 2) if pe else 'N/A'
    query = query or 'Comprehensive analysis of {0}'.format(resolved)

    diff1d = pct_change_over(history, 1)
    diff1w = pct_change_over(history, 5)
    volatility = annualized_volatility(history)

    recommendation = RECOMMENDATION_MAP.get(info.get('recommendationKey'), 'HOLD')

    # --- Sentiment over the real headlines -------------------------------
    headlines = []
    for article in data['news']:
        score = score_headline(article['title'])
        label, css = _label(score)
        headlines.append({
            'text': article['title'],
            'label': label,
            'sentiment': css,
            'source': article['source'],
            'url': article['url'],
            'published_at': article['published_at'].isoformat(),
        })

    if headlines:
        scores = [score_headline(h['text']) for h in headlines]
        sentiment_score = round(sum(scores) / len(scores), 2)
    else:
        sentiment_score = 0.0

    if sentiment_score > 0.2:
        mood = 'Bullish'
    elif sentiment_score < -0.2:
        mood = 'Bearish'
    else:
        mood = 'Neutral'

    # --- Risk -------------------------------------------------------------
    if volatility is None:
        risk_level = 'Medium'
    elif volatility > 40:
        risk_level = 'High'
    elif volatility < 20:
        risk_level = 'Low'
    else:
        risk_level = 'Medium'

    # --- Valuation against the analyst consensus target -------------------
    target_mean = info.get('targetMeanPrice')
    if target_mean:
        if price > target_mean * 1.1:
            valuation_status = 'Overvalued'
        elif price < target_mean * 0.9:
            valuation_status = 'Undervalued'
        else:
            valuation_status = 'Fairly Valued'
        reasoning = (
            'At {0}{1} the stock trades {2} versus the {3}-analyst mean target of '
            '{0}{4}.'.format(
                symbol, round(price, 2),
                format_pct((price - target_mean) / target_mean * 100),
                info.get('numberOfAnalystOpinions') or 'n/a',
                round(target_mean, 2),
            )
        )
    elif pe:
        valuation_status = 'Overvalued' if pe > 40 else ('Undervalued' if pe < 15 else 'Fairly Valued')
        reasoning = 'No analyst target available; assessed on a trailing P/E of {0}.'.format(round(pe, 2))
    else:
        valuation_status = 'Unrated'
        reasoning = 'Yahoo Finance reports neither an analyst target nor a trailing P/E for this listing.'

    low_target, high_target = info.get('targetLowPrice'), info.get('targetHighPrice')
    if low_target and high_target:
        fair_price = '{0}{1} - {0}{2}'.format(symbol, round(low_target, 2), round(high_target, 2))
    else:
        fair_price = 'Not published by analysts'

    # --- 30-session price history for the chart ---------------------------
    chart_data = []
    if history is not None and len(history):
        window = history.tail(30)
        for stamp, row in window.iterrows():
            chart_data.append({
                'name': stamp.strftime('%d %b'),
                'price': round(float(row['Close']), 2),
            })

    revenue_growth = _pct(info.get('revenueGrowth'))
    earnings_growth = _pct(info.get('earningsGrowth'))
    margins = _pct(info.get('profitMargins'))

    return {
        'id': int(datetime.datetime.now().timestamp() * 1000),
        'ticker_symbol': resolved,
        'requested_symbol': ticker_symbol.upper(),
        'company_name': name,
        'exchange': info.get('exchange'),
        'sector': sector,
        'query': query,
        'status': 'completed',
        'data_source': 'yahoo_finance',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'snapshot': {
            'price': round(price, 2),
            'currency': symbol,
            'currency_code': code,
            'mcap': format_market_cap(info.get('marketCap'), symbol),
            'pe': pe_display,
            'diff1d': format_pct(diff1d),
            'diff1w': format_pct(diff1w),
            'recommendation': recommendation,
        },
        'summary': {
            'text': (
                '{0} ({1}) trades at {2}{3} on {4}, giving a market cap of {5} and a '
                'trailing P/E of {6}. Analyst consensus is {7}.'.format(
                    name, resolved, symbol, round(price, 2),
                    info.get('exchange') or 'its listed exchange',
                    format_market_cap(info.get('marketCap'), symbol),
                    pe_display, recommendation,
                )
            ),
            'bullets': [
                'Revenue Trend: {0}'.format(
                    '{0} {1}% YoY'.format('📈' if (revenue_growth or 0) >= 0 else '📉', revenue_growth)
                    if revenue_growth is not None else 'not reported by Yahoo Finance'),
                'Earnings Trend: {0}'.format(
                    '{0} {1}% YoY'.format('📈' if (earnings_growth or 0) >= 0 else '📉', earnings_growth)
                    if earnings_growth is not None else 'not reported by Yahoo Finance'),
                'Net Margin: {0}'.format(
                    '{0}%'.format(margins) if margins is not None else 'not reported'),
                'Risk: {0} — {1} annualised volatility over the past year'.format(
                    risk_level,
                    '{0}%'.format(volatility) if volatility is not None else 'unknown'),
                '52-Week Range: {0}{1} - {0}{2}'.format(
                    symbol,
                    round(info.get('fiftyTwoWeekLow'), 2) if info.get('fiftyTwoWeekLow') else 'N/A',
                    round(info.get('fiftyTwoWeekHigh'), 2) if info.get('fiftyTwoWeekHigh') else 'N/A'),
            ],
        },
        'fundamental_analysis': {
            'summary': (
                '{0} operates in {1}. Trailing P/E is {2}, net margin {3}, and '
                'debt/equity {4}.'.format(
                    name, sector, pe_display,
                    '{0}%'.format(margins) if margins is not None else 'not reported',
                    round(info['debtToEquity'], 1) if info.get('debtToEquity') is not None else 'not reported',
                )
            ),
            'strengths': build_strengths(info, price, symbol),
            'weaknesses': build_weaknesses(info, price),
            'metrics': {
                'pe_ratio': round(pe, 2) if pe else None,
                'forward_pe': round(info['forwardPE'], 2) if info.get('forwardPE') else None,
                'current_price': round(price, 2),
                '52w_high': info.get('fiftyTwoWeekHigh'),
                '52w_low': info.get('fiftyTwoWeekLow'),
                'price_to_book': round(info['priceToBook'], 2) if info.get('priceToBook') else None,
                'return_on_equity': _pct(info.get('returnOnEquity')),
                'revenue_growth': revenue_growth,
                'profit_margin': margins,
                'debt_to_equity': round(info['debtToEquity'], 1) if info.get('debtToEquity') is not None else None,
                'dividend_yield': info.get('dividendYield'),
                'beta': info.get('beta'),
            },
            'verdict': recommendation.capitalize(),
        },
        'sentiment_analysis': {
            'sentiment_score': sentiment_score,
            'mood': mood,
            'headlines': headlines,
            'buzz_level': 'High' if len(headlines) >= 5 else ('Medium' if headlines else 'Low'),
            'summary': (
                'Keyword sentiment across {0} recent Yahoo Finance headlines scores '
                '{1} ({2}).'.format(len(headlines), sentiment_score, mood)
                if headlines else 'Yahoo Finance returned no recent headlines for this ticker.'
            ),
        },
        'risk_assessment': {
            'risk_level': risk_level,
            'warnings': build_warnings(info, price, volatility),
            'risk_summary': (
                '{0} shows {1}% annualised volatility and a beta of {2}, placing it in the '
                '{3} risk band.'.format(
                    resolved,
                    volatility if volatility is not None else 'an unknown',
                    round(info['beta'], 2) if info.get('beta') is not None else 'n/a',
                    risk_level.lower(),
                )
            ),
            'volatility_index': volatility,
        },
        'valuation': {
            'valuation_status': valuation_status,
            'fair_price_estimate': fair_price,
            'reasoning': reasoning,
            'analyst_target_mean': round(target_mean, 2) if target_mean else None,
        },
        'chart_data': chart_data,
    }


# ---------------------------------------------------------------------------
# Stock comparison
# ---------------------------------------------------------------------------

class MarketMismatch(Exception):
    """Raised when two tickers trade in different markets."""


# A P/E or margin only means something against a peer in the same market:
# different currencies bring different rate regimes, tax rules and index
# multiples, so the app refuses to put them in the same table.
MARKET_NAMES = {
    'INR': 'India', 'USD': 'United States', 'GBP': 'United Kingdom',
    'EUR': 'Eurozone', 'JPY': 'Japan', 'HKD': 'Hong Kong',
    'AUD': 'Australia', 'CAD': 'Canada', 'CNY': 'China',
}


def market_name(code):
    return MARKET_NAMES.get(code, code or 'Unknown')


def build_stock_facts(ticker_symbol, prefer_currency=None):
    """The comparable subset of a stock's live data."""
    manager = MarketDataManager(ticker_symbol, prefer_currency=prefer_currency)
    data = manager.fetch_data()

    try:
        manager.save_to_db(data)
    except Exception:
        logger.exception('Could not persist market data for %s', manager.symbol)

    info = data['info']
    code = data['currency']
    symbol = currency_symbol(code)
    price = float(data['latest_price'])
    volatility = annualized_volatility(data['history'])

    scores = [score_headline(a['title']) for a in data['news']]
    sentiment_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    if volatility is None:
        risk = 'Medium'
    elif volatility > 40:
        risk = 'High'
    elif volatility < 20:
        risk = 'Low'
    else:
        risk = 'Medium'

    return {
        'symbol': data['symbol'],
        'requested_symbol': ticker_symbol.upper(),
        'company_name': info.get('longName') or info.get('shortName') or data['symbol'],
        'exchange': info.get('exchange'),
        'sector': info.get('sector'),
        'currency': symbol,
        'currency_code': code,
        'market': market_name(code),
        'price': round(price, 2),
        'market_cap': info.get('marketCap'),
        'market_cap_display': format_market_cap(info.get('marketCap'), symbol),
        'pe_ratio': round(info['trailingPE'], 2) if info.get('trailingPE') else None,
        'revenue_growth': _pct(info.get('revenueGrowth')),
        'earnings_growth': _pct(info.get('earningsGrowth')),
        'profit_margin': _pct(info.get('profitMargins')),
        'return_on_equity': _pct(info.get('returnOnEquity')),
        'debt_to_equity': round(info['debtToEquity'], 1) if info.get('debtToEquity') is not None else None,
        'dividend_yield': info.get('dividendYield'),
        'beta': round(info['beta'], 2) if info.get('beta') is not None else None,
        'volatility': volatility,
        'risk': risk,
        'sentiment_score': sentiment_score,
        'recommendation': RECOMMENDATION_MAP.get(info.get('recommendationKey'), 'HOLD'),
    }


# (key, label, 'high' | 'low' — which direction wins, None = not scored)
COMPARISON_ROWS = (
    ('price', 'Current Price', None),
    ('market_cap_display', 'Market Cap', None),
    ('pe_ratio', 'P/E Ratio', 'low'),
    ('revenue_growth', 'Revenue Growth (YoY %)', 'high'),
    ('earnings_growth', 'Earnings Growth (YoY %)', 'high'),
    ('profit_margin', 'Net Profit Margin (%)', 'high'),
    ('return_on_equity', 'Return on Equity (%)', 'high'),
    ('debt_to_equity', 'Debt / Equity', 'low'),
    ('dividend_yield', 'Dividend Yield (%)', 'high'),
    ('volatility', 'Volatility (annualised %)', 'low'),
    ('beta', 'Beta', 'low'),
    ('sentiment_score', 'News Sentiment', 'high'),
)


def _winner(left, right, direction):
    """'left', 'right' or 'tie' — or None when a value is missing."""
    if direction is None or left is None or right is None:
        return None
    # A negative P/E means the company is loss-making, not cheap.
    if direction == 'low' and (left <= 0 or right <= 0):
        return None
    if left == right:
        return 'tie'
    if direction == 'high':
        return 'left' if left > right else 'right'
    return 'left' if left < right else 'right'


def build_comparison(symbol_1, symbol_2):
    """
    Compare two tickers from the same market.

    Raises SymbolNotFound for an unknown ticker and MarketMismatch when the
    two trade in different currencies.
    """
    left = build_stock_facts(symbol_1)
    # Resolve the second ticker in the first one's market, so 'TCS' vs
    # 'INFY' compares two NSE listings instead of pulling the NYSE ADR.
    right = build_stock_facts(symbol_2, prefer_currency=left['currency_code'])

    if left['currency_code'] != right['currency_code']:
        raise MarketMismatch(
            "Cannot compare {0} ({1}, {2}) with {3} ({4}, {5}). Ratios like P/E and "
            "margins are only meaningful between stocks in the same market — compare "
            "Indian stocks with Indian stocks, US with US.".format(
                left['symbol'], left['market'], left['currency_code'],
                right['symbol'], right['market'], right['currency_code'],
            )
        )

    if left['symbol'] == right['symbol']:
        raise MarketMismatch(
            'Pick two different stocks — both inputs resolved to {0}.'.format(left['symbol'])
        )

    rows, left_wins, right_wins = [], 0, 0
    for key, label, direction in COMPARISON_ROWS:
        won = _winner(left.get(key), right.get(key), direction)
        if won == 'left':
            left_wins += 1
        elif won == 'right':
            right_wins += 1
        rows.append({
            'key': key,
            'label': label,
            'left': left.get(key),
            'right': right.get(key),
            'better': won,
        })

    if left_wins > right_wins:
        verdict = '{0} leads on {1} of {2} scored metrics.'.format(
            left['symbol'], left_wins, left_wins + right_wins)
    elif right_wins > left_wins:
        verdict = '{0} leads on {1} of {2} scored metrics.'.format(
            right['symbol'], right_wins, left_wins + right_wins)
    else:
        verdict = 'Evenly matched — each leads on {0} scored metrics.'.format(left_wins)

    return {
        'market': left['market'],
        'currency': left['currency'],
        'currency_code': left['currency_code'],
        'left': left,
        'right': right,
        'rows': rows,
        'left_wins': left_wins,
        'right_wins': right_wins,
        'verdict': verdict,
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Lightweight quotes (watchlist)
# ---------------------------------------------------------------------------

MAX_QUOTE_SYMBOLS = 12


def build_quotes(symbols):
    """
    Small live quotes for a watchlist strip.

    Skips history and news entirely — one `info` call per symbol — so a row of
    tickers refreshes quickly. Unknown symbols come back with an `error` field
    rather than failing the whole batch.
    """
    seen, quotes = set(), []

    for raw in symbols[:MAX_QUOTE_SYMBOLS]:
        requested = raw.strip().upper()
        if not requested or requested in seen:
            continue
        seen.add(requested)

        try:
            resolved, _ticker, info = resolve_symbol(requested)
        except SymbolNotFound as exc:
            quotes.append({'requested_symbol': requested, 'error': str(exc)})
            continue
        except Exception:
            logger.exception('Quote lookup failed for %s', requested)
            quotes.append({
                'requested_symbol': requested,
                'error': 'Could not reach Yahoo Finance.',
            })
            continue

        code = info.get('currency') or 'USD'
        price = quote_price(info)
        change = info.get('regularMarketChangePercent')

        quotes.append({
            'requested_symbol': requested,
            'symbol': resolved,
            'company_name': info.get('longName') or info.get('shortName') or resolved,
            'currency': currency_symbol(code),
            'currency_code': code,
            'market': market_name(code),
            'price': round(price, 2) if price is not None else None,
            'change_pct': round(change, 2) if change is not None else None,
            'change_display': format_pct(change),
            'error': None,
        })

    return quotes
