from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import logging
from .models import StockTicker, ResearchReport
from apps.market_data.utils import SymbolNotFound
from .report_builder import (
    MarketMismatch,
    build_comparison,
    build_quotes,
    build_report,
)
from .serializers import (
    StockTickerSerializer,
    ResearchReportSerializer,
    ResearchReportCreateSerializer,
)

logger = logging.getLogger(__name__)


class StockTickerViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve stock tickers."""
    queryset = StockTicker.objects.all()
    serializer_class = StockTickerSerializer


class ResearchReportViewSet(viewsets.ModelViewSet):
    """CRUD for research reports. Creating a report triggers the agent pipeline."""
    serializer_class = ResearchReportSerializer

    def get_queryset(self):
        # Show all reports for demo; filter by user if authenticated
        if self.request.user.is_authenticated:
            return ResearchReport.objects.filter(user=self.request.user)
        return ResearchReport.objects.all()

    def create(self, request, *args, **kwargs):
        create_serializer = ResearchReportCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)

        # Create a ticker if a symbol was provided
        ticker = None
        symbol = create_serializer.validated_data.get('ticker_symbol')
        if symbol:
            ticker, _ = StockTicker.objects.get_or_create(
                symbol=symbol.upper(),
                defaults={'company_name': symbol.upper()},
            )

        report = ResearchReport.objects.create(
            user=request.user,
            ticker=ticker,
            query=create_serializer.validated_data['query'],
            status='pending',
        )

        # Kick off Celery task
        from apps.agents.tasks import run_research_pipeline
        run_research_pipeline.delay(report.id)

        serializer = ResearchReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def quick_demo_report(request):
    """
    Standalone endpoint used by the React dashboard.

    Receives { "ticker": "...", "query": "..." } and returns a full research
    report built from live Yahoo Finance data. Bare Indian symbols are
    resolved to their NSE/BSE listing automatically (RELIANCE -> RELIANCE.NS),
    and an unknown ticker returns 404 rather than a fabricated price.

    Needs no authentication, no Celery worker and no Redis — just the
    migrated database. The fetched snapshot and news are persisted on the
    way through, so the admin panel reflects real searches.
    """
    data = request.data
    ticker = (data.get('ticker') or '').strip().upper()
    query = (data.get('query') or '').strip()

    if not ticker:
        return Response(
            {'detail': 'A ticker symbol is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = build_report(ticker, query or None)
    except SymbolNotFound as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except Exception:
        logger.exception('Failed to build report for %s', ticker)
        return Response(
            {'detail': 'Could not reach Yahoo Finance for {0}. Try again shortly.'.format(ticker)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(payload)


@api_view(['POST'])
@permission_classes([AllowAny])
def compare_stocks(request):
    """
    Side-by-side comparison of two tickers from the same market.

    Receives { "ticker1": "...", "ticker2": "..." }. Bare Indian symbols are
    resolved to their NSE listing, so 'TCS' vs 'INFY' works. Comparing across
    markets (an INR stock against a USD one) returns 400, because P/E and
    margin comparisons are not meaningful across currencies.
    """
    data = request.data
    first = (data.get('ticker1') or '').strip().upper()
    second = (data.get('ticker2') or '').strip().upper()

    if not first or not second:
        return Response(
            {'detail': 'Two ticker symbols are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = build_comparison(first, second)
    except SymbolNotFound as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except MarketMismatch as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception('Failed to compare %s and %s', first, second)
        return Response(
            {'detail': 'Could not reach Yahoo Finance. Try again shortly.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(payload)


@api_view(['GET'])
@permission_classes([AllowAny])
def stock_quotes(request):
    """
    Live quotes for a comma-separated list of symbols, for the watchlist strip.

    GET /api/research/quotes/?symbols=TCS,AAPL

    One `info` lookup per symbol, capped at MAX_QUOTE_SYMBOLS. An unknown
    symbol returns an `error` on its own row instead of failing the batch.
    """
    raw = (request.query_params.get('symbols') or '').strip()
    if not raw:
        return Response(
            {'detail': 'Pass ?symbols=AAPL,TCS'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    symbols = [s for s in (part.strip() for part in raw.split(',')) if s]
    if not symbols:
        return Response(
            {'detail': 'No usable symbols in the request.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quotes = build_quotes(symbols)
    except Exception:
        logger.exception('Quote batch failed for %s', raw)
        return Response(
            {'detail': 'Could not reach Yahoo Finance. Try again shortly.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({'quotes': quotes, 'count': len(quotes)})


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    """Liveness probe for deployments and container health checks."""
    return Response({'status': 'ok', 'service': 'agentic-stock-research'})
