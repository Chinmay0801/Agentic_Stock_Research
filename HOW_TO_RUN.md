# How to Run the Agentic Stock Research Platform

Two ways to run this: **Docker** (full stack, one command) or **manually**
(fastest — no Docker, no PostgreSQL, no Redis).

The research dashboard needs **no AI API key**. Market data comes from Yahoo
Finance, which is free and keyless. An API key is only needed for the LangChain
agent pipeline that runs through Celery.

---

## 1. Docker — one command

**Prerequisites:** Docker Desktop running, plus Git.

```bash
git clone https://github.com/Chinmay0801/Agentic_Stock_Research.git
cd Agentic_Stock_Research
cp .env.example .env
docker compose up --build
```

That's the whole setup. On start, the backend container:

1. Waits for PostgreSQL to accept connections
2. Applies migrations
3. Creates the superuser `admin` / `admin123`
4. Seeds live market data

No manual `docker compose exec` steps needed.

To skip seeding (faster start), set `SEED_DEMO_DATA=0` in `.env`.

### What runs

| Service | Port | Purpose |
|---|---|---|
| `frontend` | 5173 | Vite dev server |
| `web` | 8000 | Django API |
| `db` | 5432 | PostgreSQL |
| `redis` | 6379 | Celery broker |
| `celery` | — | Agent pipeline worker |

> ⚠️ **If your `DJANGO_SECRET_KEY` contains a `$`**, escape it as `$$` in `.env`.
> Docker Compose interprets `$` as a variable reference and will silently
> truncate the key inside containers. You'll see
> `warning: The "..." variable is not set` on startup if this applies to you.

---

## 2. Manual — no Docker

Runs on Django + SQLite alone.

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

Optionally seed the admin panel with live data:

```bash
python manage.py createsuperuser
python seed_demo_data.py          # --offline to skip network calls
```

### Frontend

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

### Optional: the AI agent pipeline

Only needed for `POST /api/research/reports/`. Requires Redis running plus a
`GEMINI_API_KEY` or `OPENAI_API_KEY` in `.env`:

```bash
cd backend
celery -A config worker -l info   # Windows: add --pool=solo
```

---

## Access

| | |
|---|---|
| Frontend | http://localhost:5173 |
| API root | http://localhost:8000/api/ |
| Admin | http://localhost:8000/admin/ |
| Health | http://localhost:8000/api/research/health/ |

**Logging in:** accounts live in browser `localStorage` — this is a demo auth
layer, not Django auth. Click Register and pick any username/password. The
superuser is only for the Django admin panel.

---

## Database: SQLite vs PostgreSQL

Settings are layered, and a single env var picks the engine:

| Layer | Database |
|---|---|
| `config/settings/base.py` | PostgreSQL, from `POSTGRES_*` env vars |
| `config/settings/development.py` | SQLite **unless** `USE_SQLITE=0` |
| `config/settings/production.py` | Inherits PostgreSQL; adds security headers |

`docker-compose.yml` sets `USE_SQLITE=0`, so containers use the real PostgreSQL
service while local development stays zero-config on SQLite.

To use PostgreSQL locally, set `USE_SQLITE=0` and `POSTGRES_HOST=localhost` in
`.env`, then re-run `python manage.py migrate`.

---

## Running the tests

```bash
cd backend
python manage.py test apps
```

48 tests, roughly 0.07 seconds, **no network access** — `yfinance.Ticker` is
replaced by a fixture registry. Run a subset with:

```bash
python manage.py test apps.market_data
python manage.py test apps.research.tests.CompareTests
```

---

## Searching for stocks

Type any ticker. Data comes live from Yahoo Finance.

**Indian stocks need an exchange suffix on Yahoo** — `.NS` for NSE, `.BO` for
BSE. The backend adds it for you, and the report header shows the symbol it
actually used.

| You type | Resolves to | Shows |
|---|---|---|
| `AAPL` | `AAPL` | Apple Inc., USD |
| `TCS` | `TCS.NS` | Tata Consultancy Services, INR |
| `RELIANCE` | `RELIANCE.NS` | Reliance Industries, INR |
| `INFY.BO` | `INFY.BO` | Infosys, BSE, INR |

An unrecognised ticker returns a clear error instead of a made-up price.

### Comparing two stocks

The Compare page takes any two tickers and pulls both live. **Both must trade in
the same market** — P/E ratios and margins aren't comparable across currencies,
so `TCS` vs `AAPL` is rejected with an explanation rather than shown as a table.

The second ticker resolves in the first one's market, which matters because some
Indian companies also trade as US ADRs under their bare symbol. `TCS` vs `INFY`
gives `TCS.NS` vs `INFY.NS` (both NSE, INR) — not the NYSE ADR. To compare the
ADRs instead, type the US symbols directly (`INFY` vs `WIT`).

---

## API quick reference

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/research/quick-demo/` | Full research report for one ticker |
| `POST` | `/api/research/compare/` | Same-market comparison of two tickers |
| `GET` | `/api/research/quotes/?symbols=TCS,AAPL` | Batched live quotes |
| `GET` | `/api/research/health/` | Liveness probe |
| `GET/POST` | `/api/research/reports/` | Report CRUD (triggers Celery pipeline) |
| `GET` | `/api/market-data/snapshots/` | Persisted price snapshots |
| `GET` | `/api/market-data/news/` | Persisted news articles |

```bash
# A full report
curl -X POST http://localhost:8000/api/research/quick-demo/ \
  -H "Content-Type: application/json" \
  -d '{"ticker":"RELIANCE","query":"Is it a good buy?"}'

# A comparison
curl -X POST http://localhost:8000/api/research/compare/ \
  -H "Content-Type: application/json" \
  -d '{"ticker1":"TCS","ticker2":"INFY"}'

# Batched quotes
curl "http://localhost:8000/api/research/quotes/?symbols=TCS,AAPL,RELIANCE"
```

| Status | Meaning |
|---|---|
| `400` | Bad input, or a cross-market comparison |
| `404` | Ticker doesn't exist on Yahoo Finance |
| `502` | Yahoo Finance unreachable or rate-limiting |

---

## Troubleshooting

**"Failed to connect to Django server. Is it running?"**
The backend isn't up, or it's on another port. The frontend calls the API
same-origin through the Vite proxy — confirm `runserver` is listening on 8000.

**A ticker returns "did not resolve on Yahoo Finance"**
The symbol doesn't exist on Yahoo. Check the spelling, or add `.NS` / `.BO`
explicitly. Some companies are listed under a renamed entity — Zomato, for
instance, is now `ETERNAL.NS`.

**"Could not reach Yahoo Finance … Try again shortly." (HTTP 502)**
Network failure or Yahoo rate-limiting. Wait a few seconds and retry.

**`no such column: market_data_marketdatasnapshot.currency`**
Your database predates the currency migration. Run `python manage.py migrate`.

**Docker: `warning: The "..." variable is not set`**
Your `.env` has a `$` inside a value. Escape it as `$$`. See the Docker section.

**Docker: `exec ./entrypoint.sh: no such file or directory`**
A CRLF line-ending issue. The Dockerfile strips them, so rebuild without cache:
`docker compose build --no-cache web`.

**Celery on Windows: tasks accepted but never run**
Use the solo pool: `celery -A config worker -l info --pool=solo`.

**Changes to Python files aren't taking effect**
If you started the server with `--noreload`, restart it manually.
