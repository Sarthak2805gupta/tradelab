"""
yfinance wrapper with a DB-backed quote cache and a shared history cache.

All functions degrade gracefully — they return None or empty structures
if the network/yfinance call fails so the views never 500 on a bad ticker.

Performance design (see the "Speed" section of the README):

  * One network round-trip per ticker. A quote is derived from a single
    `history(period="1y")` call plus the chart metadata that comes with it
    (live price, previous close, day range, 52-week range). The old code
    made 2–3 calls per ticker (5-day history + fast_info, which itself
    fetched a year of prices) and the dashboard needed ~60 calls cold.
  * That same call fills the history cache for the ticker, so the Analysis
    page, Risk Analyser (6mo) and Live desk (3mo) read daily bars from the
    cache instead of fetching them again — shorter daily windows are sliced
    from the cached year.
  * Bulk helpers (fetch_quotes) do one DB query for a list of tickers and
    fetch the misses in parallel with a hard deadline, so a page is never
    blocked for longer than a few seconds by Yahoo; whatever is still in
    flight finishes in the background and is cached for the next request.
  * Stale-while-revalidate: cached quotes older than CACHE_TTL_SECONDS are
    served immediately and refreshed by a background thread.
  * A background warm loop (ensure_warm_loop) keeps the dashboard universe
    fresh while the process is alive.
"""
from __future__ import annotations

import logging
import math
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache as djcache
from django.utils import timezone as djtz

# Pure-Python sockets (urllib, smtplib) must not hang a request thread.
# yfinance's own HTTP client has its own timeouts; see _run_with_deadline.
socket.setdefaulttimeout(5)

log = logging.getLogger(__name__)

try:
    # yfinance's own logger spams stderr with "possibly delisted" messages for
    # symbols that have temporary feed issues — silence it; we already handle
    # the failure by returning None.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

CACHE_TTL_SECONDS = 600      # "fresh" window — 10 min, serve without revalidation
HISTORY_TTL_SECONDS = 1800   # daily bars — 30 min
INTRADAY_TTL_SECONDS = 120   # 5-minute bars for the live chart — 2 min
INFO_TTL_SECONDS = 6 * 3600  # Ticker.info (fundamentals / profile) — 6 h
NEGATIVE_CACHE_TTL = 300     # remember a failed symbol for 5 min
FETCH_DEADLINE_SECONDS = 4.0 # max time a page waits for cold quotes
MAX_WORKERS = 8

INDEX_TICKERS = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
}

# A small static universe used as the fallback "gainers/losers" pool when
# no NSE bhavcopy is available. Keep it lean — yfinance is rate-limited.
NSE_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "WIPRO.NS",
    "ASIANPAINT.NS", "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
]

# Daily-bar periods that can be served by slicing the cached 1-year history.
_SLICEABLE_MONTHS = {"1mo": 1, "3mo": 3, "6mo": 6, "1y": 12}


def _now() -> datetime:
    return djtz.now()


# ---------- quote cache (DB) ----------

def _cache_get(ticker: str) -> tuple:
    """Returns (data_or_None, state) where state is 'fresh', 'stale', or 'miss'."""
    from apps.stocks.models import PriceCache
    try:
        row = PriceCache.objects.get(ticker=ticker)
    except PriceCache.DoesNotExist:
        return None, "miss"
    except Exception:  # DB hiccup — behave like a miss rather than 500
        return None, "miss"
    age = (_now() - row.last_updated).total_seconds()
    return row.data_json, ("fresh" if age <= CACHE_TTL_SECONDS else "stale")


def _cache_get_many(tickers: list[str]) -> dict[str, tuple]:
    """One query for a list of tickers → {ticker: (data, state)}."""
    from apps.stocks.models import PriceCache
    out = {t: (None, "miss") for t in tickers}
    try:
        rows = PriceCache.objects.filter(ticker__in=tickers)
    except Exception:
        return out
    now = _now()
    for row in rows:
        age = (now - row.last_updated).total_seconds()
        out[row.ticker] = (row.data_json, "fresh" if age <= CACHE_TTL_SECONDS else "stale")
    return out


def _cache_set(ticker: str, data: dict) -> None:
    """Persist a quote. A failed write (e.g. SQLite 'database is locked' under
    concurrent dashboard fetches) must not discard the data we just fetched."""
    from apps.stocks.models import PriceCache
    try:
        PriceCache.objects.update_or_create(ticker=ticker, defaults={"data_json": data})
    except Exception as exc:
        log.debug("PriceCache write skipped for %s: %s", ticker, exc)


# ---------- helpers ----------

def _is_rate_limit_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "RateLimit" in name:
        return True
    msg = str(exc).lower()
    return "rate limit" in msg or "too many requests" in msg or "429" in msg


def _history_with_retry(ticker_obj, period: str, interval: str, attempts: int = 2):
    """yf.history with a small linear backoff on rate-limit errors."""
    last_exc = None
    for i in range(attempts):
        try:
            return ticker_obj.history(period=period, interval=interval)
        except Exception as e:
            last_exc = e
            if _is_rate_limit_error(e) and i < attempts - 1:
                time.sleep(0.5)
                continue
            raise
    if last_exc:
        raise last_exc


def _num(v) -> float | None:
    """Coerce to float, returning None for None/NaN/garbage."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _bars_from_frame(df) -> list[dict]:
    out = []
    for ts, row in df.iterrows():
        out.append({
            "time": int(ts.timestamp()),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]) if not math.isnan(float(row["Volume"])) else 0,
        })
    return out


def _run_with_deadline(jobs: dict[str, Callable[[], Any]], deadline: float) -> dict[str, Any]:
    """
    Run callables in parallel; return {key: result} for the ones that finished
    within `deadline` seconds. The rest keep running in the background (their
    side effect — filling the caches — still happens) and are simply absent
    from the result, so a slow Yahoo never holds a page hostage.
    """
    if not jobs:
        return {}
    pool = ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(jobs)))
    futs = {pool.submit(fn): key for key, fn in jobs.items()}
    done, _ = wait(futs, timeout=deadline)
    out = {}
    for fut in done:
        try:
            out[futs[fut]] = fut.result()
        except Exception:
            out[futs[fut]] = None
    pool.shutdown(wait=False)
    return out


# ---------- single-flight ----------
# When several threads ask for the same ticker at once (dashboard panels,
# the background warmer, the analysis page's parallel sub-fetches), only one
# of them goes to Yahoo; the others wait for it and reuse the result.
_sf_lock = threading.Lock()
_sf_inflight: dict[str, threading.Event] = {}
_sf_results: dict[str, Any] = {}


def _single_flight(key: str, fn: Callable[[], Any], wait_timeout: float = 30.0) -> Any:
    with _sf_lock:
        ev = _sf_inflight.get(key)
        leader = ev is None
        if leader:
            ev = threading.Event()
            _sf_inflight[key] = ev
    if not leader:
        ev.wait(wait_timeout)
        return _sf_results.get(key)
    try:
        result = fn()
        _sf_results[key] = result
        return result
    finally:
        with _sf_lock:
            _sf_inflight.pop(key, None)
        ev.set()


# Last fetched year of daily bars per ticker, kept in memory as a fallback
# for when the shared cache write was skipped (e.g. SQLite busy).
_year_bars: dict[str, list[dict]] = {}
_YEAR_BARS_MAX = 400


def _remember_year(ticker: str, bars: list[dict]) -> None:
    if len(_year_bars) >= _YEAR_BARS_MAX and ticker not in _year_bars:
        _year_bars.pop(next(iter(_year_bars)))
    _year_bars[ticker] = bars


def _cached_year(ticker: str) -> list[dict] | None:
    return djcache.get(_hist_key(ticker, "1y", "1d")) or _year_bars.get(ticker)


# ---------- Ticker resolution ----------
# Maps user-typed symbols to resolved yfinance tickers.
# If user types "RELIANCE", we try RELIANCE.NS then RELIANCE.BO.
_resolved_tickers: dict[str, str] = {}  # "RELIANCE" -> "RELIANCE.NS"


def resolve_ticker(raw: str) -> str:
    """
    If the ticker already has a suffix (.NS, .BO, =F, etc), return as-is.
    Otherwise try .NS then .BO and return whichever has data.
    Results are cached in-process and in the shared cache so repeated lookups are free,
    and the probe itself warms the quote cache for the winning symbol.
    """
    raw = raw.strip().upper()
    if not raw:
        return raw

    # Already has a known suffix
    if any(raw.endswith(s) for s in (".NS", ".BO", "=F", "=X")):
        return raw

    if raw in _resolved_tickers:
        return _resolved_tickers[raw]
    cached = djcache.get(f"resolve:{raw}")
    if cached:
        _resolved_tickers[raw] = cached
        return cached

    # Try .NS first (NSE is more liquid), then .BO (BSE)
    for suffix in (".NS", ".BO"):
        candidate = raw + suffix
        data, state = _cache_get(candidate)
        if data is None:
            data = _fetch_quote_from_yf(candidate)
        if data and data.get("price", 0) > 0:
            _resolved_tickers[raw] = candidate
            djcache.set(f"resolve:{raw}", candidate, 7 * 24 * 3600)
            return candidate

    # Neither worked — return with .NS as default (will fail gracefully downstream)
    _resolved_tickers[raw] = raw + ".NS"
    return raw + ".NS"


# ---------- quotes ----------

_bg_refresh_in_flight: set[str] = set()  # prevent duplicate background refreshes
_negative_cache: dict[str, float] = {}   # ticker -> timestamp of last failure


def _negative(ticker: str) -> bool:
    t = _negative_cache.get(ticker)
    return bool(t and (time.time() - t) < NEGATIVE_CACHE_TTL)


def _bg_refresh_quote(ticker: str) -> None:
    """Background-refresh a stale quote without blocking the page load."""
    if ticker in _bg_refresh_in_flight:
        return
    _bg_refresh_in_flight.add(ticker)

    def _do():
        try:
            _fetch_quote_from_yf(ticker)
        except Exception:
            pass
        finally:
            _bg_refresh_in_flight.discard(ticker)

    threading.Thread(target=_do, daemon=True).start()


def fetch_quote(ticker: str) -> dict | None:
    """
    Return quote dict. Uses stale-while-revalidate caching:
    - Fresh cache: serve immediately
    - Stale cache: serve immediately + refresh in background
    - No cache: block on yfinance (first-ever fetch for this ticker)
    """
    if not ticker:
        return None
    data, state = _cache_get(ticker)
    if state == "fresh":
        return data
    if state == "stale" and data is not None:
        _bg_refresh_quote(ticker)
        return data  # serve stale immediately, bg thread updates for next load
    if _negative(ticker):
        return None  # recently failed, don't retry
    return _fetch_quote_from_yf(ticker)


def fetch_quotes(tickers: list[str], deadline: float = FETCH_DEADLINE_SECONDS) -> dict[str, dict | None]:
    """
    Bulk version of fetch_quote: one DB query, parallel fetch of the misses
    with a hard deadline, background refresh of stale entries. Returns a dict
    in the input order; tickers that could not be fetched in time map to None.
    """
    tickers = [t for t in tickers if t]
    result: dict[str, dict | None] = {t: None for t in tickers}
    if not tickers:
        return result
    states = _cache_get_many(tickers)
    jobs: dict[str, Callable[[], Any]] = {}
    for t in tickers:
        data, state = states.get(t, (None, "miss"))
        if data is not None:
            result[t] = data
            if state == "stale":
                _bg_refresh_quote(t)
        elif not _negative(t):
            jobs[t] = (lambda sym=t: _fetch_quote_from_yf(sym))
    fetched = _run_with_deadline(jobs, deadline)
    for t, data in fetched.items():
        result[t] = data
    return result


def _fetch_quote_from_yf(ticker: str) -> dict | None:
    """
    The actual yfinance fetch: ONE chart request (1y of daily bars + metadata).
    Separated so it can run in foreground or background. Also fills the
    history cache for the ticker as a side effect. Concurrent callers for the
    same ticker share one request (single-flight).
    """
    if yf is None or not ticker:
        return None
    return _single_flight(f"quote:{ticker}", lambda: _fetch_quote_uncoalesced(ticker))


def _fetch_quote_uncoalesced(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        hist = _history_with_retry(t, period="1y", interval="1d")
        if hist is None or hist.empty:
            _negative_cache[ticker] = time.time()
            return None
        # yfinance includes a partial bar for the live session with NaN OHLC.
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            _negative_cache[ticker] = time.time()
            return None

        try:
            meta = t.get_history_metadata() or {}
        except Exception:
            meta = {}

        closes = hist["Close"]
        last_bar_close = float(closes.iloc[-1])

        # Live price: prefer the exchange's regular-market price from the chart
        # metadata (real-time), fall back to the last bar's close.
        last_price = _num(meta.get("regularMarketPrice")) or last_bar_close

        # Previous close: the prior session's close even mid-session, which is
        # exactly what we need for the day's % change.
        prev_close = _num(meta.get("previousClose")) or _num(meta.get("chartPreviousClose"))
        if prev_close is None or prev_close <= 0:
            prev_close = float(closes.iloc[-2]) if len(closes) > 1 else last_price
        # Guard: if the metadata's "previous close" is actually today's close
        # (happens after the session rolls over), fall back to the bar before it.
        if len(closes) > 1 and abs(prev_close - last_bar_close) < 1e-9 and abs(last_price - last_bar_close) < 1e-9:
            prev_close = float(closes.iloc[-2])

        change = last_price - prev_close
        change_pct = (change / prev_close * 100.0) if prev_close else 0.0

        day_high = _num(meta.get("regularMarketDayHigh")) or float(hist["High"].iloc[-1])
        day_low = _num(meta.get("regularMarketDayLow")) or float(hist["Low"].iloc[-1])
        last_volume = _num(meta.get("regularMarketVolume"))
        if last_volume is None:
            last_volume = _num(hist["Volume"].iloc[-1]) or 0
        # 52-week range: metadata first, else the full year of bars we just
        # fetched (the old fallback used only 5 days of history).
        year_high = _num(meta.get("fiftyTwoWeekHigh")) or float(hist["High"].max())
        year_low = _num(meta.get("fiftyTwoWeekLow")) or float(hist["Low"].min())
        currency = meta.get("currency") or None

        data = {
            "ticker": ticker,
            "price": round(last_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "volume": int(last_volume),
            "fifty_two_week_high": round(year_high, 2),
            "fifty_two_week_low": round(year_low, 2),
            # Not in the chart payload; reuse Ticker.info if it is already cached
            # (fast_info.market_cap cost an extra slow "shares" request per quote).
            "market_cap": _num((djcache.get(f"info:{ticker}") or {}).get("marketCap")),
            "currency": currency or "INR",
            "fetched_at": _now().isoformat(),
        }
        _cache_set(ticker, data)
        _negative_cache.pop(ticker, None)
        bars = _bars_from_frame(hist)
        _remember_year(ticker, bars)
        try:
            _store_history(ticker, "1y", "1d", bars)
        except Exception:
            pass
        return data
    except Exception as exc:
        log.debug("quote fetch failed for %s: %s", ticker, exc)
        _negative_cache[ticker] = time.time()
        return None


# ---------- history ----------

def _hist_key(ticker: str, period: str, interval: str) -> str:
    return f"hist_{ticker}_{period}_{interval}"


def _store_history(ticker: str, period: str, interval: str, bars: list[dict]) -> None:
    ttl = INTRADAY_TTL_SECONDS if interval.endswith("m") else HISTORY_TTL_SECONDS
    try:
        djcache.set(_hist_key(ticker, period, interval), bars, ttl)
    except Exception as exc:  # a busy cache must not lose the data we fetched
        log.debug("history cache write skipped for %s: %s", ticker, exc)


def _slice_months(bars: list[dict], months: int) -> list[dict]:
    """Bars from the last `months` calendar months (Yahoo's period semantics)."""
    if not bars:
        return bars
    from dateutil.relativedelta import relativedelta
    end = datetime.fromtimestamp(bars[-1]["time"])
    cutoff = (end - relativedelta(months=months)).timestamp()
    return [b for b in bars if b["time"] > cutoff]


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> list[dict]:
    """
    Return OHLC list ready for TradingView Lightweight Charts.
    Daily windows of 1mo/3mo/6mo are served from the cached 1-year history
    (which the quote fetch already fills) so they rarely need the network.
    """
    if not ticker:
        return []
    cached = djcache.get(_hist_key(ticker, period, interval))
    if cached is not None:
        return cached

    if interval == "1d" and period in _SLICEABLE_MONTHS and period != "1y":
        year = _cached_year(ticker)
        if year is None and not _negative(ticker):
            _fetch_quote_from_yf(ticker)  # fetches the year + warms the quote
            year = _cached_year(ticker)
        if year:
            out = _slice_months(year, _SLICEABLE_MONTHS[period])
            _store_history(ticker, period, interval, out)
            return out
        return []

    if period == "1y" and interval == "1d":
        year = _year_bars.get(ticker)
        if year:
            return year
        if _negative(ticker):
            return []
        _fetch_quote_from_yf(ticker)
        return _cached_year(ticker) or []

    if yf is None:
        return []
    try:
        df = _history_with_retry(yf.Ticker(ticker), period=period, interval=interval)
        if df is None or df.empty:
            return []
        df = df.dropna(subset=["Close"])
        if df.empty:
            return []
        out = _bars_from_frame(df)
        _store_history(ticker, period, interval, out)
        return out
    except Exception:
        return []


# ---------- fundamentals (Ticker.info) ----------

def get_info(ticker: str) -> dict:
    """
    Ticker.info, cached for 6 hours. This is yfinance's slowest call and the
    Analysis page used to make it three times per load (fundamentals,
    financials, company profile) — now it's one call shared by all of them.
    """
    if yf is None or not ticker:
        return {}
    key = f"info:{ticker}"
    cached = djcache.get(key)
    if cached is not None:
        return cached
    def _load():
        try:
            info = yf.Ticker(ticker).info or {}
        except Exception:
            info = {}
        if info:
            try:
                djcache.set(key, info, INFO_TTL_SECONDS)
            except Exception:
                pass
        return info

    return _single_flight(key, _load) or {}


def fetch_fundamentals(ticker: str) -> dict:
    """PE / market cap / etc from Ticker.info (shared cache, see get_info)."""
    info = get_info(ticker)
    if not info:
        return {}
    return {
        "pe_ratio": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "long_name": info.get("longName") or info.get("shortName"),
    }


# ---------- dashboard helpers ----------

def top_movers(n: int = 5) -> dict:
    quotes = [q for q in fetch_quotes(NSE_UNIVERSE).values() if q]
    quotes.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    return {"gainers": quotes[:n], "losers": list(reversed(quotes[-n:]))}


def fetch_indices() -> list[dict]:
    """Index quotes in a stable order (NIFTY 50, SENSEX, BANK NIFTY)."""
    quotes = fetch_quotes(list(INDEX_TICKERS.values()))
    out: list[dict] = []
    for name, sym in INDEX_TICKERS.items():
        q = quotes.get(sym)
        if q:
            q = dict(q)
            q["name"] = name
            out.append(q)
    return out


# ---------- background warm loop ----------

WARM_INTERVAL_SECONDS = 540  # just under the 10-minute quote TTL
_warm_lock = threading.Lock()
_warm_started = False


def warm_universe(extra: list[str] | None = None) -> None:
    """Refresh quotes (and therefore 1y history) for everything the dashboard shows."""
    symbols = list(dict.fromkeys(NSE_UNIVERSE + list(INDEX_TICKERS.values()) + (extra or [])))
    states = _cache_get_many(symbols)
    todo = [s for s in symbols if states.get(s, (None, "miss"))[1] != "fresh"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_fetch_quote_from_yf, todo))


def ensure_warm_loop(extra: list[str] | None = None) -> None:
    """
    Start (once per process) a daemon thread that re-warms the dashboard
    universe every WARM_INTERVAL_SECONDS, so users never pay for a cold
    Yahoo fetch while the server is up. Disabled with PREWARM_IN_PROCESS=false.
    """
    global _warm_started
    if not getattr(settings, "PREWARM_IN_PROCESS", True) or yf is None:
        return
    with _warm_lock:
        if _warm_started:
            return
        _warm_started = True

    def _loop():
        # First pass right away (the page that triggered us is already being
        # served from whatever is cached), then periodically.
        while True:
            try:
                warm_universe(extra)
            except Exception as exc:  # pragma: no cover
                log.debug("warm loop error: %s", exc)
            time.sleep(WARM_INTERVAL_SECONDS)

    threading.Thread(target=_loop, name="tradelab-warm", daemon=True).start()
