"""
Views for the stocks app (dashboard, analysis, live desk, calculators, API).

Language/stack note: this is a Django (Python) application and the refactor
keeps it that way on purpose. All of the number-crunching (pandas/numpy),
the market-data client (yfinance) and the template layer are Python, so a
rewrite in another language would have meant re-implementing those pieces
and risking behaviour drift for no user-visible gain. Instead the views were
slimmed down: static universes, the news feed, the what-if and SIP
calculators now live in `apps/stocks/services/*` and the views only parse
input, call a service and render. Output and page design are unchanged.
"""
from datetime import time
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import Watchlist
from .services import fetcher, analysis, commodities, risk_analyser, day_trading, news, what_if, sip
from .services.fetcher import resolve_ticker
from .services.universe import (
    QUICK_PICKS, SEARCH_UNIVERSE, NIFTY50_TICKERS, SENSEX_TICKERS, BANK_TICKERS, equity_universe,
)

__all__ = ["QUICK_PICKS", "SEARCH_UNIVERSE"]  # re-exported for backwards compatibility


# ---------- shared helpers ----------

def _market_status() -> dict:
    import random
    now = timezone.localtime()
    is_weekday = now.weekday() < 5
    open_t = time(9, 15)
    close_t = time(15, 30)
    is_open = is_weekday and (open_t <= now.time() <= close_t)

    if is_open:
        vibes = [
            "🔔 Bulls & Bears are at it!",
            "🚀 Markets are LIVE — let's go!",
            "📈 Trading floor is buzzing",
            "⚡ Live ticks incoming",
            "🎯 Game on, traders",
        ]
    elif not is_weekday:
        vibes = [
            "🛌 Markets are on a weekend nap",
            "🍵 Weekend mode — chai & charts",
            "🌴 Markets out of office",
            "🎮 Off-day. Touch grass.",
        ]
    elif now.time() < open_t:
        vibes = [
            "☕ Markets warming up — bell at 09:15",
            "🌅 Pre-market — sip chai, plan trades",
            "🐂 Bulls still asleep",
        ]
    else:
        vibes = [
            "🌙 Markets clocked out for the day",
            "🍿 Closing bell rang — recap time",
            "💤 Dalal Street dreaming till 09:15",
            "🛏️ Charts sleeping. You should too.",
        ]

    return {
        "is_open": is_open,
        "now": now.strftime("%H:%M IST"),
        "vibe": random.choice(vibes),
    }


def _parse_amount_risk(request) -> tuple[str, str, float, float]:
    """
    Read the position-sizer form fields. Returns the raw strings (echoed back
    into the form) and the parsed floats; both floats are 0 when either value
    is missing or not a number.
    """
    amount_raw = request.GET.get("amount", "").strip()
    risk_raw = request.GET.get("risk", "").strip()
    try:
        amount = float(amount_raw) if amount_raw else 0
        risk_pct = float(risk_raw) if risk_raw else 0
    except ValueError:
        amount = risk_pct = 0
    return amount_raw, risk_raw, amount, risk_pct


def _parse_timeframe(request) -> str:
    timeframe = request.GET.get("timeframe", risk_analyser.DEFAULT_TIMEFRAME).strip()
    if timeframe not in risk_analyser.TIMEFRAMES:
        timeframe = risk_analyser.DEFAULT_TIMEFRAME
    return timeframe


def _session_watchlist(request) -> list[str]:
    if request.user.is_authenticated:
        return list(Watchlist.objects.filter(user=request.user).values_list("ticker", flat=True))
    return request.session.get("watchlist", [])


# ---------- Dashboard ----------

DASHBOARD_COMMODITY_ETFS = [
    {"key": "gold", "name": "Gold ETF", "emoji": "🥇", "ticker": "GOLDBEES.NS"},
    {"key": "silver", "name": "Silver ETF", "emoji": "🥈", "ticker": "SILVERBEES.NS"},
]


def _dashboard_commodities():
    # Parallel quotes — each fetch_quote is a network call; run concurrently.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(DASHBOARD_COMMODITY_ETFS)) as pool:
        quotes = list(pool.map(lambda c: fetcher.fetch_quote(c["ticker"]), DASHBOARD_COMMODITY_ETFS))
    return [{**c, "quote": q} for c, q in zip(DASHBOARD_COMMODITY_ETFS, quotes)]


def _portfolio_summary(user) -> dict | None:
    """Invested / current / P&L totals for the signed-in user's holdings."""
    from apps.portfolio.models import UserPortfolio
    rows = UserPortfolio.objects.filter(user=user)
    invested = current = Decimal("0")
    for r in rows:
        invested += r.buy_price * r.quantity
        q = fetcher.fetch_quote(r.ticker)
        price = Decimal(str(q["price"])) if q else r.buy_price
        current += price * r.quantity
    return {
        "invested": invested,
        "current": current,
        "pnl": current - invested,
    }


def dashboard(request):
    # Parallelise the three slow-ish network fetches that make up the top of
    # the dashboard (indices, movers, commodity ETFs).
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_idx = pool.submit(fetcher.fetch_indices)
        f_mov = pool.submit(fetcher.top_movers, 5)
        f_com = pool.submit(_dashboard_commodities)
        indices = f_idx.result()
        movers = f_mov.result()
        commodity_etfs = f_com.result()

    # Optional: portfolio summary if signed in
    portfolio_summary = _portfolio_summary(request.user) if request.user.is_authenticated else None

    # "What to watch" — top absolute movers
    watch_today = sorted(
        movers["gainers"] + movers["losers"],
        key=lambda x: abs(x.get("change_pct", 0)),
        reverse=True,
    )[:5]

    return render(request, "dashboard.html", {
        "indices": indices,
        "gainers": movers["gainers"],
        "losers": movers["losers"],
        "market": _market_status(),
        "portfolio_summary": portfolio_summary,
        "watch_today": watch_today,
        "commodity_etfs": commodity_etfs,
    })


# ---------- Analysis ----------

def _deep_indicator_readings(ticker: str) -> list[dict]:
    """Supertrend, ADX, Ichimoku, CMF, Aroon, candlestick patterns — [] on any failure."""
    try:
        from .services import deep_indicators
        bars = fetcher.fetch_history(ticker, period="1y", interval="1d") or []
        if not bars:
            return []
        import pandas as pd
        df = pd.DataFrame(bars).rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        return deep_indicators.compute(df)
    except Exception:
        return []


def analysis_view(request):
    ticker = resolve_ticker(request.GET.get("ticker", "").strip())
    report = None
    sizer = None
    amount_raw, risk_raw, amount, risk_pct = _parse_amount_risk(request)
    timeframe = _parse_timeframe(request)
    deep = []
    headlines = []
    if ticker:
        report = analysis.analyze(ticker)
        if report and report.get("ok"):
            headlines = news.fetch_news(ticker)
            if amount > 0 and risk_pct > 0:
                sizer = risk_analyser.size_single_stock(ticker, amount, risk_pct, timeframe=timeframe)
            deep = _deep_indicator_readings(ticker)
    return render(request, "analysis.html", {
        "ticker": ticker,
        "report": report,
        "news": headlines,
        "quick_picks": QUICK_PICKS,
        "sizer": sizer,
        "deep_indicators": deep,
        "form_amount": amount_raw,
        "form_risk": risk_raw,
        "form_timeframe": timeframe,
        "timeframes": risk_analyser.TIMEFRAMES,
    })


# ---------- About ----------

def about_view(request):
    return render(request, "about.html", {})


# ---------- What-if calculator ----------

def what_if_view(request):
    """What if I'd bought X on date Y for amount Z? — Monte Carlo of hindsight."""
    ticker_raw = (request.GET.get("ticker") or "").strip()
    date_raw = (request.GET.get("date") or "").strip()
    amount_raw = (request.GET.get("amount") or "").strip()

    ticker = resolve_ticker(ticker_raw) if ticker_raw else ""
    result = None
    error = None

    if ticker and date_raw and amount_raw:
        result, error = what_if.compute(ticker, date_raw, amount_raw)

    return render(request, "what_if.html", {
        "ticker": ticker_raw,
        "date": date_raw,
        "amount": amount_raw,
        "result": result,
        "error": error,
    })


# ---------- SIP calculator ----------

def sip_view(request):
    """Monte Carlo SIP outcome simulator."""
    monthly_raw = (request.GET.get("monthly") or "").strip()
    years_raw = (request.GET.get("years") or "").strip()
    goal_raw = (request.GET.get("goal") or "").strip()

    result = None
    error = None

    if monthly_raw and years_raw:
        result, error = sip.simulate(monthly_raw, years_raw, goal_raw)

    return render(request, "sip.html", {
        "monthly": monthly_raw, "years": years_raw or "15", "goal": goal_raw,
        "result": result, "error": error,
    })


# ---------- Glossary / Encyclopedia ----------

def glossary_view(request):
    """Glossary terms now live inside the Trading Encyclopedia."""
    return redirect("/encyclopedia/#cat=glossary")


def encyclopedia_view(request):
    """Trading Encyclopedia — indicators, strategies, patterns, glossary."""
    return render(request, "encyclopedia.html")


# ---------- Day Trade Basket (multi-position session cart) ----------

BASKET_SESSION_KEY = "daytrade_basket"
BASKET_MAX_ITEMS = 8


def _get_basket(request) -> list[dict]:
    return request.session.get(BASKET_SESSION_KEY, [])


def _save_basket(request, items: list[dict]) -> None:
    request.session[BASKET_SESSION_KEY] = items
    request.session.modified = True


@require_http_methods(["POST"])
def basket_add(request):
    items = _get_basket(request)
    if len(items) >= BASKET_MAX_ITEMS:
        return redirect("live")
    ticker = resolve_ticker(request.POST.get("ticker", "").strip())
    try:
        amount = float(request.POST.get("amount") or 0)
        risk = float(request.POST.get("risk") or 0)
    except ValueError:
        return redirect("live")
    if not ticker or amount <= 0 or risk <= 0:
        return redirect("live")
    # Dedup: if same ticker already in basket, replace it
    items = [it for it in items if it.get("ticker") != ticker]
    items.append({"ticker": ticker, "amount": amount, "risk": risk})
    _save_basket(request, items)
    return redirect("live")


@require_http_methods(["POST"])
def basket_remove(request, idx: int):
    items = _get_basket(request)
    if 0 <= idx < len(items):
        items.pop(idx)
        _save_basket(request, items)
    return redirect("live")


@require_http_methods(["POST"])
def basket_clear(request):
    _save_basket(request, [])
    return redirect("live")


def _size_basket(items: list[dict]) -> dict:
    """Run size_day_trade on every item and aggregate totals."""
    sized_items = []
    total_capital = 0.0
    total_position_value = 0.0
    total_max_loss = 0.0
    total_target_profit = 0.0
    sizable_count = 0

    for i, it in enumerate(items):
        plan = day_trading.size_day_trade(it["ticker"], it["amount"], it["risk"])
        entry = {"index": i, "input": it, "plan": plan}
        sized_items.append(entry)
        if plan and plan.get("ok"):
            sizable_count += 1
            total_capital += it["amount"]
            total_position_value += plan["position_value"]
            total_max_loss += plan["max_loss_rs"]
            total_target_profit += plan["target_profit_rs"]

    combined_risk_pct = (total_max_loss / total_capital * 100) if total_capital else 0
    combined_reward_risk = (total_target_profit / total_max_loss) if total_max_loss else 0

    return {
        "items": sized_items,
        "count": len(items),
        "sizable_count": sizable_count,
        "total_capital": total_capital,
        "total_position_value": total_position_value,
        "total_max_loss": total_max_loss,
        "total_target_profit": total_target_profit,
        "combined_risk_pct": round(combined_risk_pct, 2),
        "combined_reward_risk": round(combined_reward_risk, 2),
    }


# ---------- Live Trading (merged with Day Trading desk) ----------

DAY_TRADE_CACHE_KEY = "day_trade_ranking_v2"
DAY_TRADE_CACHE_TTL = 120


def _day_trade_rankings() -> tuple[list[dict], bool]:
    """
    Serve the cached day-trade ranking, or ([] , loading=True) while a
    background thread computes it for the next page load. Never blocks.
    """
    from django.core.cache import cache
    ranked = cache.get(DAY_TRADE_CACHE_KEY)
    if ranked is not None:
        return ranked, False

    import threading

    def _bg_rank():
        r = day_trading.rank_day_trade_candidates(equity_universe())
        cache.set(DAY_TRADE_CACHE_KEY, r, DAY_TRADE_CACHE_TTL)

    threading.Thread(target=_bg_rank, daemon=True).start()
    return [], True


def _tag_categories(ranked: list[dict]) -> None:
    """Tag each stock with index membership for the filter chips (in place)."""
    for r in ranked:
        cats = []
        tk = r.get("ticker", "")
        if tk in NIFTY50_TICKERS:
            cats.append("nifty50")
        if tk in SENSEX_TICKERS:
            cats.append("sensex")
        if tk in BANK_TICKERS:
            cats.append("bank")
        if r.get("score", 0) >= 8:
            cats.append("score8")
        r["categories"] = " ".join(cats)


def _intraday_levels(quote: dict) -> dict:
    day_mid = (quote["day_high"] + quote["day_low"]) / 2 if quote.get("day_high") and quote.get("day_low") else None
    day_range_pct = None
    if quote.get("day_high") and quote.get("day_low") and quote["day_low"]:
        day_range_pct = (quote["day_high"] - quote["day_low"]) / quote["day_low"] * 100
    return {
        "day_mid": day_mid,
        "day_range_pct": day_range_pct,
        "above_mid": quote["price"] > day_mid if day_mid else None,
    }


def live_view(request):
    """
    Unified live trading + day-trading desk.
    Optimised for speed: all network calls parallelised, rankings lazy-loaded.
    """
    from django.core.cache import cache

    ticker = resolve_ticker(request.GET.get("ticker", "").strip())

    # All fetch_quote calls hit the DB cache first (~1ms), only going to
    # yfinance on cache miss. So sequential calls are fine when caches are warm.
    quote = fetcher.fetch_quote(ticker)
    # Indices: serve whatever is cached, don't block on yfinance failures
    try:
        indices = fetcher.fetch_indices()
    except Exception:
        indices = []

    # Watchlist
    watchlist_quotes = []
    for t in _session_watchlist(request)[:8]:
        q = fetcher.fetch_quote(t)
        if q:
            watchlist_quotes.append(q)

    # Intraday verdict — uses quote only (instant). History-based signals
    # (SMA5/SMA20) are added only if bars happen to be cached already.
    cached_bars = cache.get(f"hist_{ticker}_3mo_1d") or []
    intraday_call = day_trading.intraday_verdict(ticker, quote=quote, bars=cached_bars) if quote else None

    # Rankings: serve from cache or skip (don't block page load)
    ranked, rankings_loading = _day_trade_rankings()
    _tag_categories(ranked)
    top_candidates = ranked[:8]

    # Position sizer (only when user submits the form)
    sizer = None
    amount_raw, risk_raw, amount, risk_pct = _parse_amount_risk(request)
    if amount > 0 and risk_pct > 0:
        sizer = day_trading.size_day_trade(ticker, amount, risk_pct)

    # Intraday levels for the range bar
    levels = _intraday_levels(quote) if quote else None

    basket_summary = _size_basket(_get_basket(request))

    return render(request, "live.html", {
        "ticker": ticker,
        "quote": quote,
        "indices": indices,
        "watchlist_quotes": watchlist_quotes,
        "top_candidates": top_candidates,
        "ranked_full": ranked,
        "rankings_loading": rankings_loading,
        "sizer": sizer,
        "intraday_call": intraday_call,
        "form_amount": amount_raw,
        "form_risk": risk_raw,
        "levels": levels,
        "market": _market_status(),
        "basket": basket_summary,
    })


# ---------- Commodities (long-term ETF vs Futures) ----------

def commodities_view(request):
    key = request.GET.get("c", "").strip().lower()
    detail = commodities.build_commodity_view(key) if key else None
    listing = commodities.list_commodities()

    sizer = None
    amount_raw, risk_raw, amount, risk_pct = _parse_amount_risk(request)
    if detail and amount > 0 and risk_pct > 0:
        sizer = commodities.build_position_sizer(
            detail["spec"], detail["etf_quote"], detail["fut_quote"], amount, risk_pct,
        )

    return render(request, "commodities.html", {
        "listing": listing,
        "detail": detail,
        "selected_key": key,
        "sizer": sizer,
        "form_amount": amount_raw,
        "form_risk": risk_raw,
    })


# ---------- Risk Analyser ----------

def risk_analyser_view(request):
    amount_raw, risk_raw, amount, risk_pct = _parse_amount_risk(request)
    timeframe = _parse_timeframe(request)

    result = None
    if amount > 0 and risk_pct > 0:
        result = risk_analyser.analyse(amount, risk_pct, equity_universe(), timeframe=timeframe)

    return render(request, "risk_analyser.html", {
        "result": result,
        "form_amount": amount_raw,
        "form_risk": risk_raw,
        "form_timeframe": timeframe,
        "timeframes": risk_analyser.TIMEFRAMES,
    })


# ---------- API endpoints ----------

def api_quote(request, ticker: str):
    q = fetcher.fetch_quote(resolve_ticker(ticker))
    if not q:
        return JsonResponse({"error": "not_found"}, status=404)
    return JsonResponse(q)


def api_history(request, ticker: str):
    period = request.GET.get("period", "1y")
    interval = request.GET.get("interval", "1d")
    bars = fetcher.fetch_history(resolve_ticker(ticker), period=period, interval=interval)
    return JsonResponse({"ticker": ticker, "bars": bars, "interval": interval})


def api_analyze(request, ticker: str):
    return JsonResponse(analysis.analyze(resolve_ticker(ticker)))


# ---------- Watchlist ----------

def watchlist_view(request):
    if request.user.is_authenticated:
        items = list(Watchlist.objects.filter(user=request.user))
    else:
        # demo mode: show session-stored tickers
        items = [{"ticker": t, "alert_price": None} for t in request.session.get("watchlist", [])]
    return render(request, "watchlist.html", {"items": items})


@require_http_methods(["POST"])
def watchlist_add(request):
    ticker = resolve_ticker(request.POST.get("ticker", "").strip())
    if not ticker:
        return redirect("watchlist")
    if request.user.is_authenticated:
        Watchlist.objects.get_or_create(user=request.user, ticker=ticker)
    else:
        wl = request.session.get("watchlist", [])
        if ticker not in wl and len(wl) < 20:
            wl.append(ticker)
            request.session["watchlist"] = wl
    return redirect("watchlist")


@require_http_methods(["POST"])
def watchlist_remove(request, ticker: str):
    ticker = ticker.upper()
    if request.user.is_authenticated:
        Watchlist.objects.filter(user=request.user, ticker=ticker).delete()
    else:
        wl = request.session.get("watchlist", [])
        request.session["watchlist"] = [t for t in wl if t != ticker]
    return redirect("watchlist")


def api_watchlist_quotes(request):
    """Returns live quotes for the user's watchlist — polled every 60s."""
    out = []
    for t in _session_watchlist(request):
        q = fetcher.fetch_quote(t)
        if q:
            out.append(q)
    return JsonResponse({"quotes": out})
