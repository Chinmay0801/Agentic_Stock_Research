from rest_framework import viewsets
from .models import AgentRun
from .serializers import AgentRunSerializer


class AgentRunViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve AI agent runs (read-only)."""
    queryset = AgentRun.objects.all()
    serializer_class = AgentRunSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by user if authenticated, otherwise return all for demo
        if self.request.user.is_authenticated:
            qs = qs.filter(report__user=self.request.user)
        return qs
