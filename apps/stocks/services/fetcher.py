"""
yfinance wrapper with a 60-second DB-backed cache.

All functions degrade gracefully — they return None or empty structures
if the network/yfinance call fails so the views never 500 on a bad ticker.
"""
from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

from django.utils import timezone as djtz

# Keep network hangs short. 2s timeout + stale-while-revalidate means pages
# are never blocked waiting for a slow yfinance response.
socket.setdefaulttimeout(2)

try:
    import logging
    # yfinance's own logger spams stderr with "possibly delisted" messages for
    # symbols that have temporary feed issues — silence it; we already handle
    # the failure by returning None.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

CACHE_TTL_SECONDS = 600    # "fresh" window — 10 min, serve without revalidation
CACHE_STALE_SECONDS = 3600 # "stale-while-revalidate" window — 1 hr, serve stale, refresh in background

INDEX_TICKERS = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
}


def _now() -> datetime:
    return djtz.now()


def _cache_get(ticker: str) -> tuple:
    """
    Returns (data_or_None, state) where state is 'fresh', 'stale', or 'miss'.
    Fresh = within CACHE_TTL_SECONDS, serve immediately, no revalidation.
    Stale = older than TTL but within STALE window, serve immediately + revalidate in bg.
    Miss = nothing in DB at all, must block on yfinance.
    """
    from apps.stocks.models import PriceCache
    try:
        row = PriceCache.objects.get(ticker=ticker)
    except PriceCache.DoesNotExist:
        return None, "miss"
    age = (_now() - row.last_updated).total_seconds()
    if age <= CACHE_TTL_SECONDS:
        return row.data_json, "fresh"
    if age <= CACHE_STALE_SECONDS:
        return row.data_json, "stale"
    return row.data_json, "stale"  # even super-old is better than blocking


def _cache_set(ticker: str, data: dict) -> None:
    from apps.stocks.models import PriceCache
    PriceCache.objects.update_or_create(
        ticker=ticker, defaults={"data_json": data}
    )


def _is_rate_limit_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "RateLimit" in name:
        return True
    msg = str(exc).lower()
    return "rate limit" in msg or "too many requests" in msg or "429" in msg


def _history_with_retry(ticker_obj, period: str, interval: str, attempts: int = 2):
    """yf.history with a small linear backoff on rate-limit errors."""
    import time as _time
    last_exc = None
    for i in range(attempts):
        try:
            return ticker_obj.history(period=period, interval=interval)
        except Exception as e:
            last_exc = e
            if _is_rate_limit_error(e) and i < attempts - 1:
                _time.sleep(0.5)
                continue
            raise
    if last_exc:
        raise last_exc


# ---------- Ticker resolution ----------
# Maps user-typed symbols to resolved yfinance tickers.
# If user types "RELIANCE", we try RELIANCE.NS then RELIANCE.BO.
_resolved_tickers = {}  # "RELIANCE" -> "RELIANCE.NS"


def resolve_ticker(raw: str) -> str:
    """
    If the ticker already has a suffix (.NS, .BO, =F, etc), return as-is.
    Otherwise try .NS then .BO and return whichever has data.
    Caches results in-process so repeated lookups are free.
    """
    raw = raw.strip().upper()
    if not raw:
        return raw

    # Already has a known suffix
    if any(raw.endswith(s) for s in (".NS", ".BO", "=F", "=X")):
        return raw

    # Check cache
    if raw in _resolved_tickers:
        return _resolved_tickers[raw]

    # Try .NS first (NSE is more liquid), then .BO (BSE)
    for suffix in (".NS", ".BO"):
        candidate = raw + suffix
        try:
            t = yf.Ticker(candidate)
            fi = t.fast_info
            price = getattr(fi, "last_price", None)
            if price and price > 0:
                _resolved_tickers[raw] = candidate
                return candidate
        except Exception:
            continue

    # Neither worked — return with .NS as default (will fail gracefully downstream)
    _resolved_tickers[raw] = raw + ".NS"
    return raw + ".NS"


_bg_refresh_in_flight = set()  # prevent duplicate background refreshes
_negative_cache = {}  # ticker -> timestamp of last failure (skip for 5 min)
NEGATIVE_CACHE_TTL = 300  # 5 min


def _bg_refresh_quote(ticker: str) -> None:
    """Background-refresh a stale quote without blocking the page load."""
    import threading
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
    - Fresh cache (<3min): serve immediately
    - Stale cache (3-30min): serve immediately + refresh in background
    - No cache: block on yfinance (first-ever fetch for this ticker)
    """
    data, state = _cache_get(ticker)
    if state == "fresh":
        return data
    if state == "stale" and data is not None:
        _bg_refresh_quote(ticker)
        return data  # serve stale immediately, bg thread updates for next load
    # Cache miss — check negative cache first to avoid blocking on known-bad tickers
    import time as _t
    neg_time = _negative_cache.get(ticker)
    if neg_time and (_t.time() - neg_time) < NEGATIVE_CACHE_TTL:
        return None  # recently failed, don't retry
    result = _fetch_quote_from_yf(ticker)
    if result is None:
        _negative_cache[ticker] = _t.time()
    return result


def _fetch_quote_from_yf(ticker: str) -> dict | None:
    """The actual yfinance fetch. Separated so it can run in foreground or background."""
    if yf is None:
        return None

    try:
        t = yf.Ticker(ticker)
        info = None
        try:
            info = t.fast_info
        except Exception:
            info = None

        hist = _history_with_retry(t, period="5d", interval="1d")
        if hist is None or hist.empty:
            return None
        # yfinance includes a partial bar for the live session with NaN OHLC.
        hist = hist.dropna(subset=["Close"])
        if hist.empty and info is None:
            return None

        def _fi(attr):
            """Pull a numeric value from fast_info, returning None on any failure or NaN."""
            if info is None:
                return None
            try:
                v = getattr(info, attr, None)
            except Exception:
                return None
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            if fv != fv:  # NaN check
                return None
            return fv

        # Live price: prefer fast_info (real-time), fall back to last close.
        last_price = _fi("last_price")
        if last_price is None and not hist.empty:
            last_price = float(hist["Close"].iloc[-1])
        if last_price is None:
            return None

        # Previous close: fast_info gives the *prior session's* close even mid-session,
        # which is exactly what we need for the day's % change.
        prev_close = _fi("previous_close")
        if prev_close is None:
            if len(hist) > 1:
                prev_close = float(hist["Close"].iloc[-2])
            elif not hist.empty:
                prev_close = float(hist["Close"].iloc[-1])
            else:
                prev_close = last_price

        change = last_price - prev_close
        change_pct = (change / prev_close * 100.0) if prev_close else 0.0

        day_high = _fi("day_high")
        if day_high is None and not hist.empty:
            day_high = float(hist["High"].iloc[-1])
        day_low = _fi("day_low")
        if day_low is None and not hist.empty:
            day_low = float(hist["Low"].iloc[-1])

        last_volume = _fi("last_volume")
        if last_volume is None and not hist.empty:
            last_volume = float(hist["Volume"].iloc[-1])
        volume = int(last_volume) if last_volume is not None else 0

        year_high = _fi("year_high")
        if year_high is None and not hist.empty:
            year_high = float(hist["High"].max())
        year_low = _fi("year_low")
        if year_low is None and not hist.empty:
            year_low = float(hist["Low"].min())

        market_cap = _fi("market_cap")
        try:
            currency = getattr(info, "currency", None) if info is not None else None
        except Exception:
            currency = None

        data = {
            "ticker": ticker,
            "price": round(last_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "day_high": round(day_high, 2) if day_high is not None else None,
            "day_low": round(day_low, 2) if day_low is not None else None,
            "volume": volume,
            "fifty_two_week_high": round(year_high, 2) if year_high is not None else None,
            "fifty_two_week_low": round(year_low, 2) if year_low is not None else None,
            "market_cap": market_cap,
            "currency": currency or "INR",
            "fetched_at": _now().isoformat(),
        }
        _cache_set(ticker, data)
        return data
    except Exception:
        return None


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> list[dict]:
    """Return OHLC list ready for TradingView Lightweight Charts. Cached 5 min."""
    from django.core.cache import cache as _mcache
    cache_key = f"hist_{ticker}_{period}_{interval}"
    cached = _mcache.get(cache_key)
    if cached is not None:
        return cached

    if yf is None:
        return []
    try:
        df = _history_with_retry(yf.Ticker(ticker), period=period, interval=interval)
        if df is None or df.empty:
            return []
        df = df.dropna(subset=["Close"])
        if df.empty:
            return []
        out = []
        for ts, row in df.iterrows():
            out.append({
                "time": int(ts.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })
        _mcache.set(cache_key, out, 1800)  # 30 min
        return out
    except Exception:
        return []


def fetch_fundamentals(ticker: str) -> dict:
    """PE / market cap / etc — slower call, not cached at this layer."""
    if yf is None:
        return {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    return {
        "pe_ratio": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "long_name": info.get("longName") or info.get("shortName"),
    }


# A small static universe used as the fallback "gainers/losers" pool when
# no NSE bhavcopy is available. Keep it lean — yfinance is rate-limited.
NSE_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "WIPRO.NS",
    "ASIANPAINT.NS", "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
]


def top_movers(n: int = 5) -> dict:
    quotes: list[dict] = []
    # Parallel fetch so a cold cache doesn't stall the dashboard for 20+ sequential calls.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_quote, sym): sym for sym in NSE_UNIVERSE}
        for fut in as_completed(futs, timeout=None):
            try:
                q = fut.result(timeout=5)
            except Exception:
                q = None
            if q:
                quotes.append(q)
    quotes.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    return {"gainers": quotes[:n], "losers": list(reversed(quotes[-n:]))}


def fetch_indices() -> list[dict]:
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(INDEX_TICKERS)) as pool:
        futs = {pool.submit(fetch_quote, sym): name for name, sym in INDEX_TICKERS.items()}
        for fut in as_completed(futs, timeout=3):
            name = futs[fut]
            try:
                q = fut.result(timeout=0.1)
            except Exception:
                q = None
            if q:
                q = dict(q)
                q["name"] = name
                out.append(q)
    return out
