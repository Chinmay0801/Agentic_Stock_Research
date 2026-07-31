# 📊 Agentic Stock Research & Analysis Platform

An autonomous financial analyst powered by AI agents. The platform automates stock research by gathering market data, performing analysis, and providing clear investment insights.

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | Django + DRF | REST API & database management |
| Async Queue | Celery + Redis | Background agent tasks |
| Database | PostgreSQL | User data & research reports |
| AI Core | LangChain + OpenAI/Gemini | Multi-agent reasoning |
| Data Providers | Yahoo Finance, Alpha Vantage | Real-time market data |
| Frontend | React + Vite | User dashboard |

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/WPL_Project.git
cd WPL_Project

# 2. Create your .env file
cp .env.example .env
# Edit .env with your API keys

# 3. Start everything with Docker
docker-compose up --build

# 4. In another terminal, run migrations and seed demo data
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python backend/seed_demo_data.py
```

### Access
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/

### Without Docker (Manual)

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Project Structure

```
├── backend/
│   ├── config/          # Django settings, Celery, URLs
│   ├── apps/
│   │   ├── users/       # Auth & user management
│   │   ├── research/    # Research reports
│   │   ├── agents/      # AI agent orchestration
│   │   └── market_data/ # Market data & news
│   └── requirements/
├── frontend/
│   └── src/
│       ├── components/  # Reusable UI components
│       ├── pages/       # Dashboard, Report, Login
│       └── services/    # API client
├── docker-compose.yml
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users/register/` | Register new user |
| GET | `/api/users/profile/` | Get current user profile |
| GET/POST | `/api/research/reports/` | List/create research reports |
| GET | `/api/research/tickers/` | List stock tickers |
| GET | `/api/agents/runs/` | List AI agent runs |
| GET | `/api/market-data/snapshots/` | Market data snapshots |
| GET | `/api/market-data/news/` | News articles |

## Team

| Member | Focus |
|--------|-------|
| Chinmay (230905264) | Full Stack Development & AI Integration |
| Teammate 2 | AI Agents & Data Providers |
| Teammate 3 | Frontend Dashboard |

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow guidelines.
