from django.contrib import admin
from .models import MarketDataSnapshot, NewsArticle


@admin.register(MarketDataSnapshot)
class MarketDataSnapshotAdmin(admin.ModelAdmin):
    """Admin configuration for MarketDataSnapshot model."""
    list_display = ('id', 'get_ticker', 'price', 'volume', 'market_cap', 'pe_ratio', 'data_source', 'fetched_at')
    list_filter = ('data_source', 'fetched_at')
    search_fields = ('ticker__symbol',)
    ordering = ('-fetched_at',)

    def get_ticker(self, obj):
        return obj.ticker.symbol
    get_ticker.short_description = 'Ticker'


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    """Admin configuration for NewsArticle model."""
    list_display = ('id', 'title_short', 'get_ticker', 'source', 'sentiment_score', 'published_at')
    list_filter = ('source', 'published_at')
    search_fields = ('title', 'source', 'ticker__symbol')
    ordering = ('-published_at',)

    def title_short(self, obj):
        return obj.title[:60] + '...' if len(obj.title) > 60 else obj.title
    title_short.short_description = 'Title'

    def get_ticker(self, obj):
        return obj.ticker.symbol if obj.ticker else '—'
    get_ticker.short_description = 'Ticker'
