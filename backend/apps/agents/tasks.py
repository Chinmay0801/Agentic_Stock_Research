"""
Celery tasks for AI agent pipeline.

These tasks are triggered when a new research report is created.
Each task runs asynchronously via Celery + Redis.
"""
from celery import shared_task
from django.utils import timezone
from apps.market_data.utils import MarketDataManager, SymbolNotFound
from apps.agents.agents_logic import (
    FundamentalAgent,
    SentimentAgent,
    RiskAgent,
    ValuationAgent
)

@shared_task(bind=True, max_retries=3)
def run_research_pipeline(self, report_id):
    """
    Main orchestrator task — kicks off the multi-agent research pipeline.
    
    Flow:
    1. Fetch and persist market data
    2. Run Fundamental Analysis
    3. Run Sentiment Analysis
    4. Run Risk Assessment
    5. Run Valuation
    6. Update ResearchReport with final summary
    """
    from apps.research.models import ResearchReport
    from apps.agents.models import AgentRun

    try:
        report = ResearchReport.objects.get(id=report_id)
        if not report.ticker:
             report.status = 'failed'
             report.save()
             return "No ticker symbol provided."

        report.status = 'in_progress'
        report.save()

        # 1. Fetch Market Data
        manager = MarketDataManager(report.ticker.symbol)
        try:
            mkt_data = manager.fetch_data()
        except SymbolNotFound as exc:
            report.status = 'failed'
            report.summary = str(exc)
            report.save()
            return str(exc)

        # fetch_data may resolve 'TCS' to 'TCS.NS'; keep the report pointed at
        # the listing the snapshot was actually taken from.
        if manager.ticker and manager.ticker.pk != report.ticker.pk:
            report.ticker = manager.ticker
            report.save(update_fields=['ticker'])

        manager.save_to_db(mkt_data)

        # 2. Define Agents
        agents = {
            'fundamental': FundamentalAgent(),
            'sentiment': SentimentAgent(),
            'risk': RiskAgent(),
            'valuation': ValuationAgent()
        }

        # 3. Execute Pipeline
        for agent_key, agent_instance in agents.items():
            agent_run = AgentRun.objects.create(
                report=report,
                agent_type=agent_key,
                status='running',
                started_at=timezone.now()
            )
            
            try:
                # Actual AI execution
                result = agent_instance.run(report.ticker.symbol, mkt_data)
                
                # Save output to report JSON fields
                if agent_key == 'fundamental':
                    report.fundamental_analysis = result
                elif agent_key == 'sentiment':
                    report.sentiment_analysis = result
                elif agent_key == 'risk':
                    report.risk_assessment = result
                elif agent_key == 'valuation':
                    report.valuation = result

                agent_run.output_data = result
                agent_run.status = 'completed'
            except Exception as e:
                agent_run.status = 'failed'
                agent_run.error_message = str(e)
                # We could fail the whole report or just log the error. 
                # For now, let's keep going but mark the run as failed.
            
            agent_run.completed_at = timezone.now()
            agent_run.save()

        # 4. Final Finalize
        report.status = 'completed'
        report.summary = (
            f"Comprehensive analysis for {report.ticker.symbol} completed. "
            f"Fundamental and sentiment data evaluated through specialized agents."
        )
        report.save()

    except Exception as exc:
        if 'report' in locals():
            report.status = 'failed'
            report.save()
        raise self.retry(exc=exc, countdown=60)
