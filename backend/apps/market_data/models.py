from django.db import models


class MarketDataSnapshot(models.Model):
    """Cached market data for a stock ticker."""
    ticker = models.ForeignKey(
        'research.StockTicker',
        on_delete=models.CASCADE,
        related_name='market_snapshots',
    )
    price = models.DecimalField(max_digits=12, decimal_places=4)
    currency = models.CharField(
        max_length=8, default='USD',
        help_text='ISO code reported by the exchange, e.g. USD or INR.',
    )
    open_price = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    high = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    low = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    volume = models.BigIntegerField(null=True)
    market_cap = models.BigIntegerField(null=True)
    pe_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    dividend_yield = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    data_source = models.CharField(max_length=50, default='yahoo_finance')
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fetched_at']
        get_latest_by = 'fetched_at'

    def __str__(self):
        return f"{self.ticker.symbol} @ {self.price} ({self.fetched_at:%Y-%m-%d %H:%M})"


class NewsArticle(models.Model):
    """News article related to a stock or market."""
    ticker = models.ForeignKey(
        'research.StockTicker',
        on_delete=models.CASCADE,
        related_name='news_articles',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=500)
    source = models.CharField(max_length=100)
    url = models.URLField()
    published_at = models.DateTimeField()
    summary = models.TextField(blank=True)
    sentiment_score = models.FloatField(
        null=True, blank=True,
        help_text='Sentiment score from -1.0 (bearish) to 1.0 (bullish)',
    )
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title[:80]
