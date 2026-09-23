"""
URL configuration for Agentic Stock Research Platform.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """
    API root — lists all available endpoints.
    This is the browsable entry point for the Django REST Framework API.
    """
    return Response({
        'message': 'Welcome to the Agentic Stock Research API',
        'version': '1.0.0',
        'endpoints': {
            'admin': request.build_absolute_uri('/admin/'),
            'users_register': request.build_absolute_uri('/api/users/register/'),
            'users_profile': request.build_absolute_uri('/api/users/profile/'),
            'research_tickers': request.build_absolute_uri('/api/research/tickers/'),
            'research_reports': request.build_absolute_uri('/api/research/reports/'),
            'research_quick_demo': request.build_absolute_uri('/api/research/quick-demo/'),
            'research_compare': request.build_absolute_uri('/api/research/compare/'),
            'agent_runs': request.build_absolute_uri('/api/agents/runs/'),
            'market_snapshots': request.build_absolute_uri('/api/market-data/snapshots/'),
            'market_news': request.build_absolute_uri('/api/market-data/news/'),
        }
    })


urlpatterns = [
    path('', api_root, name='root'),
    path('admin/', admin.site.urls),
    path('api/', api_root, name='api-root'),
    path('api/users/', include('apps.users.urls')),
    path('api/research/', include('apps.research.urls')),
    path('api/agents/', include('apps.agents.urls')),
    path('api/market-data/', include('apps.market_data.urls')),

    # DRF built-in login/logout for the browsable API
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
