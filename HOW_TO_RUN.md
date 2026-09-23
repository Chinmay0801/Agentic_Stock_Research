# How to Run the Agentic Stock Research Platform

Two ways to run this: **manually** (fastest — no Docker, no PostgreSQL, no Redis) or
with **Docker** (full stack including Celery + Redis).

---

## 1. Manual Setup (Recommended for a quick demo)

The dashboard's research flow runs entirely through Django + SQLite. You do **not**
need PostgreSQL, Redis, a Celery worker, or any AI API key to see live stock data.

### Backend (Django)

1. Open a terminal in the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment (Windows):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   On macOS/Linux use `source venv/bin/activate`.
3. Install dependencies:
   ```bash
   pip install -r requirements/dev.txt
   ```
4. Apply migrations (creates `db.sqlite3`):
   ```bash
   python manage.py migrate
   ```
5. *(Optional)* Create an admin account and seed demo data so the admin panel
   isn't empty. The seed fetches **live quotes** from Yahoo Finance:
   ```bash
   python manage.py createsuperuser
   python seed_demo_data.py
   ```
   Add `--offline` to skip the network calls: `python seed_demo_data.py --offline`
6. Start the server:
   ```bash
   python manage.py runserver
   ```

### Frontend (React + Vite)

1. Open a **second terminal**:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the dev server:
   ```bash
   npm run dev
   ```

### Open it

- **Frontend Dashboard**: http://localhost:5173
- **Backend API root**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/

**Logging in:** accounts are stored in browser `localStorage` — this is a demo auth
layer, not Django auth. Just click Register and pick any username/password. The
superuser from step 5 is only for the Django admin panel.

---

## 2. Using Docker (full stack)

Brings up the frontend, backend, PostgreSQL, Redis, and a Celery worker.

**Prerequisites:** Docker Desktop running, plus Git.

1. Clone and enter the project:
   ```bash
   git clone https://github.com/Chinmay0801/Agentic_Stock_Research.git
   cd Agentic_Stock_Research
   ```
2. Create your env file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to add a Gemini/LangChain key if you want the AI agent pipeline.
   The dashboard's research flow works without one.
3. Build and start:
   ```bash
   docker-compose up --build
   ```
4. In a separate terminal, initialize the database (first run only). The
   container's working directory is `/app`, so run the seed script by name:
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   docker-compose exec web python seed_demo_data.py
   ```

Same URLs as above.

> **Note:** `config/settings/base.py` currently hardcodes SQLite, so the `web`
> container writes to SQLite even though `docker-compose` starts PostgreSQL.
> To actually use PostgreSQL, restore the `DATABASES` block that reads the
> `POSTGRES_*` variables from `.env`.

---

## Searching for stocks

Type any ticker into the dashboard. Data comes live from Yahoo Finance.

**Indian stocks need an exchange suffix on Yahoo** — `.NS` for NSE, `.BO` for BSE.
The backend adds it for you: typing `TCS` resolves to `TCS.NS`, and the report
header shows the symbol it actually used. You can also type the suffix yourself.

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

The second ticker is resolved in the first one's market, which matters because
some Indian companies also trade as US ADRs under their bare symbol. `TCS` vs
`INFY` gives you `TCS.NS` vs `INFY.NS` (both NSE, INR) — not the NYSE ADR.
To compare the ADRs instead, type the US symbols directly (`INFY` vs `WIT`).

---

## Troubleshooting

**"Failed to connect to Django server. Is it running?"**
The backend isn't up, or it's on a different port. The frontend calls
`http://localhost:8000` — confirm `python manage.py runserver` is listening there.

**A ticker returns "did not resolve on Yahoo Finance"**
The symbol doesn't exist on Yahoo. Check the spelling, or try the `.NS` / `.BO`
suffix explicitly. Note some companies are listed under a renamed entity —
Zomato, for instance, is now `ETERNAL.NS`.

**"Could not reach Yahoo Finance … Try again shortly." (HTTP 502)**
A network failure or Yahoo rate-limiting. Wait a few seconds and retry.

**`no such column: market_data_marketdatasnapshot.currency`**
You're on an older database. Run `python manage.py migrate`.

**Changes to Python files aren't taking effect**
If you started the server with `--noreload`, restart it manually.
