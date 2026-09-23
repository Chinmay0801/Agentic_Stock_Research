"""
Seed script — populates the database with demo data for presentation.
Run: python seed_demo_data.py
"""
import os
import sys
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from apps.users.models import CustomUser
from apps.research.models import StockTicker, ResearchReport
from apps.agents.models import AgentRun
from apps.market_data.models import MarketDataSnapshot, NewsArticle

print("🚀 Seeding demo data...")

# Get admin user
admin_user = CustomUser.objects.filter(is_superuser=True).first()
if not admin_user:
    print("❌ No superuser found. Create one first with: python manage.py createsuperuser")
    sys.exit(1)

# ─── Stock Tickers ──────────────────────────────────────────
tickers_data = [
    ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics'),
    ('MSFT', 'Microsoft Corp.', 'Technology', 'Software'),
    ('GOOGL', 'Alphabet Inc.', 'Technology', 'Internet Services'),
    ('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', 'E-Commerce'),
    ('TSLA', 'Tesla Inc.', 'Automotive', 'Electric Vehicles'),
    ('NVDA', 'NVIDIA Corp.', 'Technology', 'Semiconductors'),
    ('TCS.NS', 'Tata Consultancy Services', 'Technology', 'IT Services'),
    ('INFY.NS', 'Infosys Ltd.', 'Technology', 'IT Services'),
    ('RELIANCE.NS', 'Reliance Industries', 'Conglomerate', 'Diversified'),
    ('META', 'Meta Platforms Inc.', 'Technology', 'Social Media'),
]

tickers = {}
for symbol, name, sector, industry in tickers_data:
    ticker, created = StockTicker.objects.get_or_create(
        symbol=symbol,
        defaults={'company_name': name, 'sector': sector, 'industry': industry},
    )
    tickers[symbol] = ticker
    status = "✅ Created" if created else "⏭️  Exists"
    print(f"  {status}: {ticker}")

# ─── Market Data Snapshots (live from Yahoo Finance) ────────
# Seeding real quotes keeps the admin panel consistent with what the app
# serves. Pass --offline to skip the network and seed tickers only.
if '--offline' in sys.argv:
    print("  ⏭️  --offline: skipping live snapshot fetch")
else:
    from apps.market_data.utils import MarketDataManager, SymbolNotFound

    for symbol in ['AAPL', 'MSFT', 'NVDA', 'TCS.NS', 'INFY.NS', 'RELIANCE.NS']:
        try:
            manager = MarketDataManager(symbol)
            data = manager.fetch_data()
            snap = manager.save_to_db(data)
            print("  ✅ Snapshot: {0} @ {1} {2}".format(
                manager.symbol, snap.price, snap.currency))
        except SymbolNotFound as exc:
            print("  ⚠️  {0}: {1}".format(symbol, exc))
        except Exception as exc:
            print("  ⚠️  {0}: could not reach Yahoo Finance ({1})".format(symbol, exc))

# ─── News Articles ──────────────────────────────────────────
news_data = [
    ('AAPL', 'Apple Beats Q4 Earnings Estimates with Record Services Revenue', 'Reuters', 'https://reuters.com/apple-q4', 0.82),
    ('AAPL', 'iPhone 16 Pro Sales Surge in India, Apple Says', 'Bloomberg', 'https://bloomberg.com/iphone-india', 0.65),
    ('MSFT', 'Microsoft Azure Revenue Grows 29% in Latest Quarter', 'CNBC', 'https://cnbc.com/msft-azure', 0.78),
    ('GOOGL', 'Alphabet Faces Antitrust Scrutiny Over Search Dominance', 'WSJ', 'https://wsj.com/google-antitrust', -0.45),
    ('TSLA', 'Tesla Cybertruck Deliveries Accelerate Amid Mixed Reviews', 'TechCrunch', 'https://techcrunch.com/cybertruck', 0.10),
    ('NVDA', 'NVIDIA H200 GPU Sets New AI Training Records', 'The Verge', 'https://theverge.com/nvidia-h200', 0.91),
    ('TCS.NS', 'TCS Wins $2B Multi-Year Deal with European Bank', 'Economic Times', 'https://economictimes.com/tcs', 0.72),
    ('INFY.NS', 'Infosys Lowers FY25 Guidance Amid Macro Uncertainty', 'Moneycontrol', 'https://moneycontrol.com/infy', -0.30),
]

for symbol, title, source, url, sentiment in news_data:
    article, created = NewsArticle.objects.get_or_create(
        title=title,
        defaults={
            'ticker': tickers.get(symbol),
            'source': source,
            'url': url,
            'published_at': timezone.now() - timedelta(hours=len(news_data)),
            'summary': f'Article about {tickers[symbol].company_name}.',
            'sentiment_score': sentiment,
        },
    )
    if created:
        print(f"  ✅ News: {title[:50]}...")

# ─── Research Reports ───────────────────────────────────────
reports_data = [
    ('AAPL', 'Comprehensive analysis of Apple stock performance and growth potential', 'completed'),
    ('TSLA', 'Risk assessment for Tesla amid EV market competition', 'completed'),
    ('NVDA', 'AI boom impact on NVIDIA valuation and future outlook', 'in_progress'),
    ('TCS.NS', 'TCS fundamental analysis: IT services sector outlook', 'pending'),
]

for symbol, query, report_status in reports_data:
    report, created = ResearchReport.objects.get_or_create(
        ticker=tickers[symbol],
        user=admin_user,
        query=query,
        defaults={
            'status': report_status,
            'summary': f'Detailed analysis of {tickers[symbol].company_name}.' if report_status == 'completed' else '',
            'fundamental_analysis': {'verdict': 'Buy', 'pe_ratio': 32.1} if report_status == 'completed' else {},
            'sentiment_analysis': {'mood': 'Bullish', 'score': 0.75} if report_status == 'completed' else {},
            'risk_assessment': {'level': 'Medium', 'volatility': 22.5} if report_status == 'completed' else {},
        },
    )
    if created:
        print(f"  ✅ Report: {query[:50]}...")

        # Create agent runs for completed reports
        if report_status == 'completed':
            for agent_type in ['fundamental', 'sentiment', 'risk', 'valuation']:
                AgentRun.objects.create(
                    report=report,
                    agent_type=agent_type,
                    status='completed',
                    input_data={'ticker': symbol, 'query': query},
                    output_data={'result': f'{agent_type} analysis completed'},
                    started_at=timezone.now() - timedelta(minutes=10),
                    completed_at=timezone.now() - timedelta(minutes=5),
                )
            print(f"    ✅ Created 4 agent runs for report")

print("\n🎉 Demo data seeding complete!")
print(f"   Tickers: {StockTicker.objects.count()}")
print(f"   Reports: {ResearchReport.objects.count()}")
print(f"   Agent Runs: {AgentRun.objects.count()}")
print(f"   Snapshots: {MarketDataSnapshot.objects.count()}")
print(f"   News: {NewsArticle.objects.count()}")
print(f"\n📌 Login to admin: http://127.0.0.1:8000/admin/")
print(f"   Username: admin | Password: admin123")
