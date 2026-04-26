from datetime import datetime, time
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .models import Watchlist
from .services import fetcher, analysis, commodities, risk_analyser, day_trading
from .services.fetcher import resolve_ticker


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


# Index membership for day-trade filter chips
NIFTY50_TICKERS = {
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "WIPRO.NS",
    "ASIANPAINT.NS", "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "BAJAJFINSV.NS", "NESTLEIND.NS", "TECHM.NS", "INDUSINDBK.NS", "M&M.NS",
}
SENSEX_TICKERS = {
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "WIPRO.NS",
    "ASIANPAINT.NS", "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "NESTLEIND.NS", "TECHM.NS", "INDUSINDBK.NS", "M&M.NS", "BAJAJFINSV.NS",
    "BAJAJ-AUTO.NS",
}
BANK_TICKERS = {
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "INDUSINDBK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
}

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


def dashboard(request):
    # Parallelise the three slow-ish network fetches that make up the top of
    # the dashboard (indices, movers, commodity ETFs). Cuts first-paint wait
    # from ~2s to under 800ms cold.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_idx  = pool.submit(fetcher.fetch_indices)
        f_mov  = pool.submit(fetcher.top_movers, 5)
        f_com  = pool.submit(_dashboard_commodities)
        indices = f_idx.result()
        movers = f_mov.result()
        commodity_etfs = f_com.result()

    # Optional: portfolio summary if signed in
    portfolio_summary = None
    if request.user.is_authenticated:
        from apps.portfolio.models import UserPortfolio
        rows = UserPortfolio.objects.filter(user=request.user)
        invested = current = Decimal("0")
        for r in rows:
            invested += r.buy_price * r.quantity
            q = fetcher.fetch_quote(r.ticker)
            price = Decimal(str(q["price"])) if q else r.buy_price
            current += price * r.quantity
        portfolio_summary = {
            "invested": invested,
            "current": current,
            "pnl": current - invested,
        }

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


QUICK_PICKS = [
    {"label": "Index heavyweights", "stocks": [
        {"name": "Reliance", "ticker": "RELIANCE.NS"},
        {"name": "TCS", "ticker": "TCS.NS"},
        {"name": "HDFC Bank", "ticker": "HDFCBANK.NS"},
        {"name": "Infosys", "ticker": "INFY.NS"},
        {"name": "ICICI Bank", "ticker": "ICICIBANK.NS"},
        {"name": "HUL", "ticker": "HINDUNILVR.NS"},
        {"name": "ITC", "ticker": "ITC.NS"},
        {"name": "L&T", "ticker": "LT.NS"},
        {"name": "SBI", "ticker": "SBIN.NS"},
        {"name": "Bharti Airtel", "ticker": "BHARTIARTL.NS"},
    ]},
    {"label": "Banking & finance", "stocks": [
        {"name": "Kotak Bank", "ticker": "KOTAKBANK.NS"},
        {"name": "Axis Bank", "ticker": "AXISBANK.NS"},
        {"name": "Bajaj Finance", "ticker": "BAJFINANCE.NS"},
        {"name": "IndusInd Bank", "ticker": "INDUSINDBK.NS"},
    ]},
    {"label": "IT & tech", "stocks": [
        {"name": "Wipro", "ticker": "WIPRO.NS"},
        {"name": "HCL Tech", "ticker": "HCLTECH.NS"},
        {"name": "Tech Mahindra", "ticker": "TECHM.NS"},
    ]},
    {"label": "Auto & industrials", "stocks": [
        {"name": "Maruti Suzuki", "ticker": "MARUTI.NS"},
        {"name": "M&M", "ticker": "M&M.NS"},
        {"name": "UltraTech Cement", "ticker": "ULTRACEMCO.NS"},
        {"name": "Bajaj Auto", "ticker": "BAJAJ-AUTO.NS"},
    ]},
    {"label": "Consumer & pharma", "stocks": [
        {"name": "Asian Paints", "ticker": "ASIANPAINT.NS"},
        {"name": "Titan", "ticker": "TITAN.NS"},
        {"name": "Sun Pharma", "ticker": "SUNPHARMA.NS"},
        {"name": "Nestle India", "ticker": "NESTLEIND.NS"},
    ]},
]


def _build_commodity_quick_picks():
    """Derive a 'Commodities' quick-picks group from the canonical commodities spec."""
    stocks = []
    for spec in commodities.COMMODITIES:
        if spec.get("etf"):
            stocks.append({
                "name": f"{spec['emoji']} {spec['name']} ETF",
                "ticker": spec["etf"]["ticker"],
            })
        if spec.get("futures"):
            stocks.append({
                "name": f"{spec['emoji']} {spec['name']} Futures",
                "ticker": spec["futures"]["ticker"],
            })
    return {"label": "Commodities — ETFs & Futures", "stocks": stocks}


QUICK_PICKS.append(_build_commodity_quick_picks())


def _build_search_universe():
    import json
    from pathlib import Path
    seen = set()
    out = []
    # Quick picks first so they rank above the bulk list when names collide
    for group in QUICK_PICKS:
        for s in group["stocks"]:
            if s["ticker"] in seen:
                continue
            seen.add(s["ticker"])
            out.append({"name": s["name"], "ticker": s["ticker"]})
    # Bundled NSE universe (~200 names)
    data_path = Path(__file__).resolve().parent / "data" / "nse_stocks.json"
    try:
        with data_path.open() as f:
            for s in json.load(f):
                if s["ticker"] in seen:
                    continue
                seen.add(s["ticker"])
                out.append({"name": s["name"], "ticker": s["ticker"]})
    except (FileNotFoundError, ValueError):
        pass
    return out


SEARCH_UNIVERSE = _build_search_universe()


def analysis_view(request):
    ticker = resolve_ticker(request.GET.get("ticker", "").strip())
    report = None
    sizer = None
    amount_raw = request.GET.get("amount", "").strip()
    risk_raw = request.GET.get("risk", "").strip()
    timeframe = request.GET.get("timeframe", risk_analyser.DEFAULT_TIMEFRAME).strip()
    if timeframe not in risk_analyser.TIMEFRAMES:
        timeframe = risk_analyser.DEFAULT_TIMEFRAME
    try:
        amount = float(amount_raw) if amount_raw else 0
        risk_pct = float(risk_raw) if risk_raw else 0
    except ValueError:
        amount = risk_pct = 0
    deep = []
    news = []
    if ticker:
        report = analysis.analyze(ticker)
        if report and report.get("ok"):
            # News feed — free via yfinance
            try:
                import yfinance as _yf
                from django.core.cache import cache as _cache
                _k = f"news:{ticker}"
                news = _cache.get(_k)
                if news is None:
                    raw = _yf.Ticker(ticker).news or []
                    news = []
                    for n in raw[:6]:
                        # yfinance shape varies by version — be defensive
                        item = n.get("content") or n
                        title = item.get("title") or n.get("title") or ""
                        publisher = (item.get("provider") or {}).get("displayName") if isinstance(item.get("provider"), dict) else (item.get("publisher") or n.get("publisher") or "")
                        link = (item.get("canonicalUrl") or {}).get("url") if isinstance(item.get("canonicalUrl"), dict) else (item.get("link") or n.get("link") or "")
                        pub_time = item.get("pubDate") or n.get("providerPublishTime")
                        thumb = None
                        tb = item.get("thumbnail")
                        if isinstance(tb, dict):
                            res = tb.get("resolutions") or []
                            if res: thumb = res[0].get("url")
                        synopsis = (item.get("summary") or item.get("description") or n.get("summary") or "").strip()
                        if title and link:
                            news.append({"title": title, "publisher": publisher, "link": link, "time": pub_time, "thumb": thumb, "synopsis": synopsis})
                    _cache.set(_k, news, 30 * 60)
            except Exception:
                news = []
            if amount > 0 and risk_pct > 0:
                sizer = risk_analyser.size_single_stock(ticker, amount, risk_pct, timeframe=timeframe)
            # Rich indicator readings — Supertrend, ADX, Ichimoku, CMF, Aroon, patterns
            try:
                from .services import deep_indicators
                from .services.fetcher import fetch_history
                bars = fetch_history(ticker, period="1y", interval="1d") or []
                if bars:
                    import pandas as _pd
                    dfd = _pd.DataFrame(bars).rename(columns={
                        "open": "Open", "high": "High", "low": "Low",
                        "close": "Close", "volume": "Volume",
                    })
                    deep = deep_indicators.compute(dfd)
            except Exception:
                deep = []
    return render(request, "analysis.html", {
        "ticker": ticker,
        "report": report,
        "news": news,
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
        try:
            from datetime import datetime as _dt
            import yfinance as _yf
            import pandas as _pd
            import math as _math

            amount = float(amount_raw)
            start_dt = _dt.strptime(date_raw, "%Y-%m-%d")

            hist = _yf.download(ticker, start=start_dt.strftime("%Y-%m-%d"),
                                auto_adjust=True, progress=False)
            if isinstance(hist.columns, _pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            hist = hist.dropna()
            if len(hist) < 2:
                error = "Not enough price history for that date."
            else:
                entry_price = float(hist["Close"].iloc[0])
                current_price = float(hist["Close"].iloc[-1])
                shares = amount / entry_price
                current_value = shares * current_price
                pnl = current_value - amount
                pnl_pct = (pnl / amount) * 100.0
                days = max(1, (hist.index[-1] - hist.index[0]).days)
                years = days / 365.25
                cagr = (pow(current_value / amount, 1 / years) - 1) * 100 if years > 0 else pnl_pct

                # Max drawdown — what was the worst point along the way
                closes = hist["Close"].astype(float)
                running_peak = closes.cummax()
                drawdown = (closes - running_peak) / running_peak
                mdd_pct = float(drawdown.min()) * 100
                mdd_idx = drawdown.idxmin()
                mdd_price = float(closes.loc[mdd_idx])

                # Best exit, worst exit
                best_idx = closes.idxmax()
                worst_idx = closes.idxmin()

                # Benchmark to Nifty over same window
                try:
                    bench = _yf.download("^NSEI", start=start_dt.strftime("%Y-%m-%d"),
                                         auto_adjust=True, progress=False)
                    if isinstance(bench.columns, _pd.MultiIndex):
                        bench.columns = bench.columns.get_level_values(0)
                    bench_ret = float((bench["Close"].iloc[-1] / bench["Close"].iloc[0] - 1) * 100)
                except Exception:
                    bench_ret = None

                # Chart series
                series = [
                    {"t": d.strftime("%Y-%m-%d"), "v": round(float(c * shares), 2)}
                    for d, c in closes.items()
                ]

                result = {
                    "ticker": ticker,
                    "amount": amount,
                    "shares": round(shares, 4),
                    "entry_price": round(entry_price, 2),
                    "current_price": round(current_price, 2),
                    "current_value": round(current_value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "cagr": round(cagr, 2),
                    "years": round(years, 2),
                    "mdd_pct": round(mdd_pct, 2),
                    "mdd_date": mdd_idx.strftime("%d %b %Y"),
                    "mdd_price": round(mdd_price, 2),
                    "best_date": best_idx.strftime("%d %b %Y"),
                    "best_price": round(float(closes.loc[best_idx]), 2),
                    "worst_date": worst_idx.strftime("%d %b %Y"),
                    "worst_price": round(float(closes.loc[worst_idx]), 2),
                    "bench_ret": round(bench_ret, 2) if bench_ret is not None else None,
                    "series": series,
                    "start_date": hist.index[0].strftime("%d %b %Y"),
                }
        except Exception as exc:
            error = str(exc)

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
        try:
            import numpy as _np

            monthly = float(monthly_raw)
            years = int(float(years_raw))
            goal = float(goal_raw) if goal_raw else None
            n_months = years * 12

            # Historical Nifty: assume ~12% CAGR, ~18% annualized volatility (realistic long-term).
            # Converted to monthly: mean ≈ 0.949%, std ≈ 5.2%.
            mu = 0.12 / 12
            sigma = 0.18 / _np.sqrt(12)

            sims = 2000
            rng = _np.random.default_rng(42)
            # monthly returns, sims × n_months
            rets = rng.normal(mu, sigma, size=(sims, n_months))

            # Apply SIP compounding
            finals = _np.zeros(sims)
            for i in range(sims):
                v = 0.0
                for r in rets[i]:
                    v = (v + monthly) * (1 + r)
                finals[i] = v

            p5, p50, p95 = _np.percentile(finals, [5, 50, 95])
            total_invested = monthly * n_months
            prob_goal = None
            if goal:
                prob_goal = float((finals >= goal).mean() * 100)

            result = {
                "monthly": monthly, "years": years, "n_months": n_months,
                "invested": round(total_invested),
                "p5": round(float(p5)), "p50": round(float(p50)), "p95": round(float(p95)),
                "p50_mult": round(float(p50) / total_invested, 2) if total_invested else 0,
                "goal": goal,
                "prob_goal": round(prob_goal, 1) if prob_goal is not None else None,
                "sims": sims,
            }
        except Exception as exc:
            error = str(exc)

    return render(request, "sip.html", {
        "monthly": monthly_raw, "years": years_raw or "15", "goal": goal_raw,
        "result": result, "error": error,
    })


# ---------- Glossary ----------

def glossary_view(request):
    """Glossary terms now live inside the Trading Encyclopedia."""
    from django.shortcuts import redirect
    return redirect("/encyclopedia/#cat=glossary")


def encyclopedia_view(request):
    """Trading Encyclopedia — indicators, strategies, patterns, glossary."""
    from django.shortcuts import render
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

def live_view(request):
    """
    Unified live trading + day-trading desk.
    Optimised for speed: all network calls parallelised, rankings lazy-loaded.
    """
    from django.core.cache import cache

    ticker = resolve_ticker(request.GET.get("ticker", "").strip())

    # All fetch_quote calls hit the 3-min DB cache first (~1ms), only going to
    # yfinance on cache miss. So sequential calls are fine when caches are warm.
    quote = fetcher.fetch_quote(ticker)
    # Indices: serve whatever is cached, don't block on yfinance failures
    try:
        indices = fetcher.fetch_indices()
    except Exception:
        indices = []

    # Watchlist
    if request.user.is_authenticated:
        from apps.stocks.models import Watchlist
        watchlist_tickers = list(Watchlist.objects.filter(user=request.user).values_list("ticker", flat=True))
    else:
        watchlist_tickers = request.session.get("watchlist", [])
    watchlist_quotes = []
    for t in watchlist_tickers[:8]:
        q = fetcher.fetch_quote(t)
        if q:
            watchlist_quotes.append(q)

    # Intraday verdict — uses quote only (instant). History-based signals
    # (SMA5/SMA20) are added only if bars happen to be cached already.
    from django.core.cache import cache as _mcache
    bars_key = f"hist_{ticker}_3mo_1d"
    cached_bars = _mcache.get(bars_key) or []
    intraday_call = day_trading.intraday_verdict(ticker, quote=quote, bars=cached_bars) if quote else None

    # ---- Rankings: serve from cache or skip (don't block page load) ----
    DAY_TRADE_CACHE_KEY = "day_trade_ranking_v2"
    DAY_TRADE_CACHE_TTL = 120

    ranked = cache.get(DAY_TRADE_CACHE_KEY)
    rankings_loading = False
    if ranked is None:
        # Don't block the page — show "loading" state and trigger ranking
        # via a one-off background computation for next page load.
        rankings_loading = True
        ranked = []
        # Fire-and-forget: populate cache for next request
        import threading
        def _bg_rank():
            equity_universe = []
            seen = set()
            for group in QUICK_PICKS:
                if "commodities" in group["label"].lower():
                    continue
                for s in group["stocks"]:
                    if s["ticker"] in seen:
                        continue
                    seen.add(s["ticker"])
                    equity_universe.append(s)
            r = day_trading.rank_day_trade_candidates(equity_universe)
            cache.set(DAY_TRADE_CACHE_KEY, r, DAY_TRADE_CACHE_TTL)
        threading.Thread(target=_bg_rank, daemon=True).start()

    # Tag each stock with index membership for filter chips
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

    top_candidates = ranked[:8]

    # ---- Position sizer (only when user submits the form) ----
    sizer = None
    amount_raw = request.GET.get("amount", "").strip()
    risk_raw = request.GET.get("risk", "").strip()
    try:
        amount = float(amount_raw) if amount_raw else 0
        risk_pct = float(risk_raw) if risk_raw else 0
    except ValueError:
        amount = risk_pct = 0
    if amount > 0 and risk_pct > 0:
        sizer = day_trading.size_day_trade(ticker, amount, risk_pct)

    # Intraday levels for the range bar
    levels = None
    if quote:
        day_mid = (quote["day_high"] + quote["day_low"]) / 2 if quote.get("day_high") and quote.get("day_low") else None
        day_range_pct = None
        if quote.get("day_high") and quote.get("day_low") and quote["day_low"]:
            day_range_pct = (quote["day_high"] - quote["day_low"]) / quote["day_low"] * 100
        levels = {
            "day_mid": day_mid,
            "day_range_pct": day_range_pct,
            "above_mid": quote["price"] > day_mid if day_mid else None,
        }

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
    amount_raw = request.GET.get("amount", "").strip()
    risk_raw = request.GET.get("risk", "").strip()
    try:
        amount = float(amount_raw) if amount_raw else 0
        risk_pct = float(risk_raw) if risk_raw else 0
    except ValueError:
        amount = risk_pct = 0
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
    amount_raw = request.GET.get("amount", "").strip()
    risk_raw = request.GET.get("risk", "").strip()
    timeframe = request.GET.get("timeframe", risk_analyser.DEFAULT_TIMEFRAME).strip()
    if timeframe not in risk_analyser.TIMEFRAMES:
        timeframe = risk_analyser.DEFAULT_TIMEFRAME
    try:
        amount = float(amount_raw) if amount_raw else 0
        risk_pct = float(risk_raw) if risk_raw else 0
    except ValueError:
        amount = risk_pct = 0

    result = None
    if amount > 0 and risk_pct > 0:
        # Use the equity quick-picks (skip the commodities group since those are
        # ETFs/futures with different risk characteristics)
        equity_universe = []
        seen = set()
        for group in QUICK_PICKS:
            if "commodities" in group["label"].lower():
                continue
            for s in group["stocks"]:
                if s["ticker"] in seen:
                    continue
                seen.add(s["ticker"])
                equity_universe.append(s)
        result = risk_analyser.analyse(amount, risk_pct, equity_universe, timeframe=timeframe)

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
    items = []
    if request.user.is_authenticated:
        items = list(Watchlist.objects.filter(user=request.user))
    else:
        # demo mode: show session-stored tickers
        tickers = request.session.get("watchlist", [])
        items = [{"ticker": t, "alert_price": None} for t in tickers]
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
    if request.user.is_authenticated:
        tickers = list(Watchlist.objects.filter(user=request.user).values_list("ticker", flat=True))
    else:
        tickers = request.session.get("watchlist", [])
    out = []
    for t in tickers:
        q = fetcher.fetch_quote(t)
        if q:
            out.append(q)
    return JsonResponse({"quotes": out})
