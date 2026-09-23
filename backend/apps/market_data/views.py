from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes as perm
from rest_framework.response import Response
from .models import MarketDataSnapshot, NewsArticle
from .serializers import MarketDataSnapshotSerializer, NewsArticleSerializer


class MarketDataViewSet(viewsets.ReadOnlyModelViewSet):
    """Retrieve cached market data snapshots."""
    queryset = MarketDataSnapshot.objects.all()
    serializer_class = MarketDataSnapshotSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ticker = self.request.query_params.get('ticker')
        if ticker:
            qs = qs.filter(ticker__symbol=ticker.upper())
        return qs


class NewsArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """Retrieve news articles, optionally filtered by ticker."""
    queryset = NewsArticle.objects.all()
    serializer_class = NewsArticleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ticker = self.request.query_params.get('ticker')
        if ticker:
            qs = qs.filter(ticker__symbol=ticker.upper())
        return qs
