from django.contrib import admin
from .models import AgentRun


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    """Admin configuration for AgentRun model."""
    list_display = ('id', 'agent_type', 'status', 'get_report_id', 'started_at', 'completed_at', 'created_at')
    list_filter = ('agent_type', 'status')
    search_fields = ('agent_type', 'error_message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_report_id(self, obj):
        return f"Report #{obj.report_id}"
    get_report_id.short_description = 'Report'
