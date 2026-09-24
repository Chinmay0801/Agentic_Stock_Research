# 📊 Agentic Stock Research & Analysis Platform

A full-stack stock research tool that pulls **live market data** from Yahoo Finance,
builds a structured research report, and compares two stocks side by side — with a
LangChain multi-agent pipeline running asynchronously on Celery.

Covers the **Indian market (NSE/BSE)** and **US markets**, resolving exchange
suffixes automatically: type `TCS`, get `TCS.NS` priced in ₹.

---

## Highlights

| | |
|---|---|
| 🌍 **Multi-market** | NSE (`.NS`), BSE (`.BO`) and US listings, each in its own currency |
| 🔎 **Smart symbol resolution** | `RELIANCE` → `RELIANCE.NS`; unknown tickers return a clear 404, never a fabricated price |
| ⚖️ **Same-market comparison** | 12 scored metrics, direction-aware (lower P/E wins, higher margin wins) |
| ⭐ **Live watchlist** | Batched quote endpoint with per-symbol error isolation |
| 🤖 **AI agent pipeline** | Fundamental / Sentiment / Risk / Valuation agents via LangChain + Celery |
| ✅ **48 tests** | Yahoo Finance fully mocked — the suite runs offline and deterministically |

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Backend | Django 5 + DRF | REST API, ORM, admin |
| Async Queue | Celery + Redis | Background agent pipeline |
| Database | PostgreSQL (SQLite for local dev) | Reports, snapshots, news |
| AI Core | LangChain + Gemini/OpenAI | Multi-agent reasoning |
| Market Data | yfinance (Yahoo Finance) | Quotes, fundamentals, history, news |
| Frontend | React 19 + Vite 8 + Recharts | Dashboard, report view, comparison |

---

## Quick Start

> For the full walkthrough — optional Celery worker, running tests, troubleshooting — see **[HOW_TO_RUN.md](HOW_TO_RUN.md)**.

### Option A — Docker (one command)

```bash
git clone https://github.com/Chinmay0801/Agentic_Stock_Research.git
cd Agentic_Stock_Research
cp .env.example .env
docker compose up --build
```

That's it. The backend container waits for PostgreSQL, applies migrations,
creates `admin` / `admin123`, and seeds live market data before serving.

> If your `DJANGO_SECRET_KEY` contains a `$`, escape it as `$$` in `.env` —
> Compose reads `$` as a variable reference and would truncate the key inside
> the containers.

### Option B — Local (no Docker, no PostgreSQL, no Redis)

The research dashboard runs on Django + SQLite alone — no AI API key required.

```bash
# Terminal 1 — backend
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Optionally seed the admin panel with live data:

```bash
python manage.py createsuperuser
python seed_demo_data.py          # --offline to skip network calls
```

### Access

| | |
|---|---|
| Frontend | http://localhost:5173 |
| API root | http://localhost:8000/api/ |
| Admin | http://localhost:8000/admin/ |
| Health | http://localhost:8000/api/research/health/ |

**Logging in:** demo accounts live in browser `localStorage` — click Register and
pick any username. The Django superuser is only for the admin panel.

---

## Using it

### Searching

Type any ticker. Indian listings need an exchange suffix on Yahoo, and the
backend adds it for you:

| You type | Resolves to | Shows |
|---|---|---|
| `AAPL` | `AAPL` | Apple Inc., USD |
| `TCS` | `TCS.NS` | Tata Consultancy Services, INR |
| `RELIANCE` | `RELIANCE.NS` | Reliance Industries, INR |
| `INFY.BO` | `INFY.BO` | Infosys, BSE, INR |

### Comparing

Both stocks must trade in the same market — P/E ratios and margins aren't
comparable across currencies, so `TCS` vs `AAPL` is rejected with an explanation
rather than rendered as a misleading table.

The second ticker resolves in the first one's market, which matters because some
Indian companies also trade as US ADRs under their bare symbol. `TCS` vs `INFY`
gives `TCS.NS` vs `INFY.NS` — not the NYSE ADR. To compare ADRs, type the US
symbols directly (`INFY` vs `WIT`).

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/research/quick-demo/` | Full research report for one ticker |
| `POST` | `/api/research/compare/` | Same-market comparison of two tickers |
| `GET` | `/api/research/quotes/?symbols=TCS,AAPL` | Batched live quotes |
| `GET` | `/api/research/health/` | Liveness probe |
| `GET/POST` | `/api/research/reports/` | Report CRUD (triggers the Celery pipeline) |
| `GET` | `/api/market-data/snapshots/` | Persisted price snapshots |
| `GET` | `/api/market-data/news/` | Persisted news articles |

```bash
curl -X POST http://localhost:8000/api/research/quick-demo/ \
  -H "Content-Type: application/json" \
  -d '{"ticker":"RELIANCE","query":"Is it a good buy?"}'
```

**Error handling:** `404` unknown ticker (with a suffix hint), `400` bad input or
cross-market comparison, `502` Yahoo Finance unreachable.

---

## Architecture

```
React (Vite)
    │  POST /api/research/quick-demo/
    ▼
Django REST Framework
    │
    ├─ report_builder.py ──► MarketDataManager ──► yfinance ──► Yahoo Finance
    │        │                      │
    │        │                      └─► persists MarketDataSnapshot + NewsArticle
    │        │
    │        └─► templated narrative from the fetched numbers
    │
    └─ Celery task (async) ──► LangChain agents ──► Gemini/OpenAI
                                  Fundamental · Sentiment · Risk · Valuation
```

Every figure in a report comes from yfinance; the prose is templated from those
same numbers, so the text and the metrics can't disagree. Headline sentiment is a
transparent keyword score rather than a model call, which keeps the dashboard
working without an LLM API key.

---

## Tests

```bash
cd backend
python manage.py test apps
```

48 tests in well under a second, with **no network access** — `yfinance.Ticker`
is replaced by a fixture registry, so the suite is deterministic and can exercise
malformed upstream responses that a live API would never return on demand.

Coverage includes symbol resolution and ADR precedence, both yfinance news
schemas, volatility maths, comparison scoring direction, and every API error path.

```bash
python manage.py test apps.market_data                  # resolution + parsing
python manage.py test apps.research.tests.CompareTests  # one class
```

---

## Configuration

All settings have working defaults; see [.env.example](.env.example).

| Variable | Default | Notes |
|---|---|---|
| `USE_SQLITE` | `1` | `0` switches to PostgreSQL (docker-compose sets this) |
| `DJANGO_ENV` | `development` | `production` loads hardened settings |
| `SEED_DEMO_DATA` | `1` | Seeds live data on container start |
| `GEMINI_API_KEY` | — | Optional; only the Celery agent pipeline uses it |
| `VITE_API_URL` | empty | Set to an absolute origin if the API is on another host |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Vite dev-proxy target; Docker sets `http://web:8000` |
| `POSTGRES_HOST` | `localhost` | `db` inside Docker |

Settings are layered: `base.py` (PostgreSQL from env) → `development.py`
(SQLite unless `USE_SQLITE=0`) → `production.py`.

---

## Project Layout

```
backend/
  apps/
    research/       reports, comparison, quotes, report_builder.py
    market_data/    yfinance integration, symbol resolution, snapshots
    agents/         LangChain agents + Celery tasks
    users/          custom user model
  config/settings/  base / development / production
  entrypoint.sh     waits for Postgres, migrates, seeds
frontend/
  src/pages/        Dashboard, ResearchReport, Compare
  src/services/     axios client, API base resolution
```

Tests live beside the code they cover: `apps/market_data/tests.py` (resolution,
news parsing, persistence) and `apps/research/tests.py` (API contracts,
comparison scoring).

---

## Notes & Limitations

- Yahoo Finance serves no historical bars for `.BO` (BSE) listings; the app
  borrows the `.NS` series for charts and volatility.
- Demo auth is `localStorage`-based, not Django auth — it's a UI demo, not a
  security boundary.
- Headline sentiment is keyword-based unless the Celery agent pipeline runs.
- The synchronous report path blocks a request thread for roughly a second per
  Yahoo call and has no caching yet — fine for a demo, not for real traffic.
- Not investment advice.
