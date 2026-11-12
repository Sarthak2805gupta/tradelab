# StockApp — Indian Markets Learning & Analysis

A full-stack Django app for Indian retail investors. Live NSE/BSE quotes,
technical analysis, portfolio tracking, watchlists with price alerts, and a
10-module learning center with quizzes.

**Stack**: Django + DRF · MySQL/Postgres/SQLite · Tailwind (prebuilt CSS) · Vanilla JS · native canvas charts · yfinance · pandas/numpy.

## Quick start

```bash
# 1. clone & enter
cd stockapp-project

# 2. virtualenv + deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. configure your DB
cp .env.example .env
#   then edit .env with your MySQL credentials
#   (or set DB_ENGINE=django.db.backends.sqlite3 for a zero-setup trial)

# 4. create the MySQL database (skip if using SQLite)
mysql -u root -p -e "CREATE DATABASE stockapp_db CHARACTER SET utf8mb4;"

# 5. migrate, load learning content, and run
python manage.py makemigrations
python manage.py migrate          # also creates the cache table
python manage.py loaddata learning_modules.json
python manage.py createsuperuser   # optional, for admin + per-user data
python manage.py runserver
```

Open http://localhost:8000.

## Features

| Route | What it does |
|---|---|
| `/` | Live Nifty 50 / Sensex / Bank Nifty, top 5 gainers & losers, market open/close indicator, "what to watch", portfolio summary |
| `/analysis/?ticker=INFY.NS` | Quick-pick tiles, PE/52w/RSI/MACD/SMA/Bollinger/support-resistance, Trend/Momentum/Risk/Action verdict with plain-English reasons + confidence score, multi-period candlestick chart |
| `/portfolio/` | Add/edit/delete holdings, live P&L, allocation doughnut, CSV export |
| `/watchlist/` | Up to 20 tickers, JS auto-refresh every 60s, in-app price alerts |
| `/learn/` | 10 modules, key terms, "did you know", 3-question quiz, progress bar |

## Project layout

```
stockapp-project/
├── manage.py
├── requirements.txt
├── .env.example
├── stockapp/                 ← Django project
│   ├── settings.py           ← MySQL via .env
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── stocks/               ← Analysis engine, watchlist, fetcher
│   │   ├── models.py         ← Watchlist, PriceCache
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services/
│   │       ├── fetcher.py    ← yfinance + 60s DB cache
│   │       ├── indicators.py ← SMA, RSI, MACD, Bollinger, S/R
│   │       └── analysis.py   ← Verdict engine
│   ├── portfolio/            ← UserPortfolio model + CSV export
│   └── learning/             ← Module/QuizQuestion/LearningProgress + fixture
│       └── fixtures/learning_modules.json
├── templates/
│   ├── base.html             ← Sidebar, dark navy theme
│   ├── dashboard.html
│   ├── analysis.html
│   ├── portfolio.html
│   ├── watchlist.html
│   ├── _report_card.html
│   └── learning/{index,module}.html
└── static/
    ├── css/styles.css
    └── js/app.js
```

## Notes & gotchas

- **Indian tickers need a `.NS` (or `.BO` for BSE) suffix** — `RELIANCE.NS`, `TCS.NS`, `INFY.NS`. The analysis page throws a friendly 404 message on bad symbols.
- **yfinance is rate-limited.** The `fetcher.py` layer caches every quote in the database (`PriceCache` table, fresh for 10 minutes, served stale and refreshed in the background after that), so the dashboard, watchlist polling, and analysis engine all share one set of API calls.
- **Auth is optional.** Anonymous users get a session-backed watchlist and a single shared portfolio bucket. Sign in via `/admin/` for per-user data.
- **MySQL vs SQLite.** The default is MySQL (per the spec). Set `DB_ENGINE=django.db.backends.sqlite3` in `.env` to switch to SQLite for a zero-setup trial — no other changes needed.
- **No Celery required for the basics.** The 60s cache and `setInterval(refresh, 60000)` in the watchlist template handle the live-update story without a worker. To plug Celery/Django-Q in later, add a periodic task that calls `apps.stocks.services.fetcher.fetch_quote` for hot tickers.
- **Charts.** Price charts use the bundled `static/js/tradelab-chart.js`; Chart.js (portfolio, encyclopedia) loads from CDN.
- **CSS.** Tailwind is precompiled into `static/css/tailwind.css`. After adding new Tailwind classes to a template, rebuild it:
  `npx tailwindcss@3.4.17 -c frontend/tailwind.config.js -i frontend/tailwind.input.css -o static/css/tailwind.css --minify`

## Speed

- One Yahoo request per ticker (1 year of daily bars + live quote metadata); shorter daily windows are sliced from it.
- Shared cache (`CACHE_BACKEND=db`, the default) for history, fundamentals and 5-minute analysis reports, so all
  gunicorn workers and restarts reuse the same data. `migrate` creates its table.
- Pages never wait more than ~4 s on Yahoo; slow symbols finish in the background and are cached for the next view.
- A background thread keeps the dashboard tickers warm while the server is up (`PREWARM_IN_PROCESS=false` to turn off).
- On Render's free plan the instance sleeps after 15 idle minutes and takes ~30-60 s to wake. The keep-alive workflow
  pings every 10 minutes, but GitHub can delay scheduled runs; a paid instance (or an external uptime pinger) removes cold starts entirely.

## Disclaimer

Educational tool only. Not investment advice. SEBI's 2023 study found 9 out
of 10 retail F&O traders lose money — please learn risk management before
trading with real capital.
