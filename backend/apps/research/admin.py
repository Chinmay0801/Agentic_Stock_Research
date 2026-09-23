from django.contrib import admin
from .models import StockTicker, ResearchReport


@admin.register(StockTicker)
class StockTickerAdmin(admin.ModelAdmin):
    """Admin configuration for StockTicker model."""
    list_display = ('symbol', 'company_name', 'sector', 'industry', 'created_at')
    list_filter = ('sector', 'industry')
    search_fields = ('symbol', 'company_name', 'sector')
    ordering = ('symbol',)


@admin.register(ResearchReport)
class ResearchReportAdmin(admin.ModelAdmin):
    """Admin configuration for ResearchReport model."""
    list_display = ('id', 'get_ticker', 'user', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('query', 'ticker__symbol', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    def get_ticker(self, obj):
        return obj.ticker.symbol if obj.ticker else '—'
    get_ticker.short_description = 'Ticker'
