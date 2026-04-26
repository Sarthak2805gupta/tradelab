"""
Screener views — ports the Flask app's routes (Stock-Screener/app.py) into
Django. SSE endpoints use StreamingHttpResponse; POST tools are CSRF-exempt
because they're JSON APIs called from the screener page's own JS.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests as _requests

from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

# Trigger sys.path injection for the ported flat-import modules
from . import services  # noqa: F401
from .json_utils import safe_json


IST = timezone(timedelta(hours=5, minutes=30))

# In-process cache populated by the screener SSE stream and consumed by
# the Trade Analyzer to skip duplicate yfinance downloads.
SCREENER_DF_CACHE: dict = {}


def _json_response(payload, status=200) -> HttpResponse:
    return HttpResponse(safe_json(payload), status=status, content_type="application/json")


def _ns(sym: str) -> str:
    """Add .NS suffix for NSE stocks unless already suffixed or an index."""
    s = (sym or "").strip().upper()
    if not s:
        return ""
    return s if ("." in s or s.startswith("^")) else s + ".NS"


# ── Page views ──────────────────────────────────────────────────────────

def index(request):
    return render(request, "screener/index.html")


# ── Screener config + SSE ──────────────────────────────────────────────

@require_GET
def screener_config(request):
    try:
        from screener_v3 import CONDITIONS_META, WEIGHTS  # type: ignore
        conditions = [{**c, "default_weight": WEIGHTS[c["key"]]} for c in CONDITIONS_META]
        return _json_response({"success": True, "conditions": conditions})
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc)}, status=500)


@require_GET
def screener_stream(request):
    """SSE endpoint — runs screener_v3 and streams progress + per-ticker results."""
    index_name = request.GET.get("index", "nifty50").lower()
    liq_preset = request.GET.get("liquidity", "medium").lower()
    use_fundamentals = request.GET.get("fundamentals", "1") == "1"
    use_mtf = request.GET.get("mtf", "1") == "1"

    try:
        custom_weights = json.loads(request.GET.get("weights", "{}")) or None
    except Exception:
        custom_weights = None

    def generate():
        try:
            from screener_v3 import (  # type: ignore
                download_and_calculate, score_stock, check_liquidity,
                check_fundamentals, detect_market_regime, download_nifty_returns,
                check_weekly_gate, INDEX_MAP, NIFTY_50, MAX_WEIGHTED_SCORE, WEIGHTS,
            )

            if custom_weights:
                effective_max = sum(custom_weights.get(k, v) for k, v in WEIGHTS.items())
            else:
                effective_max = MAX_WEIGHTED_SCORE

            tickers = INDEX_MAP.get(index_name, NIFTY_50)
            results, failed, illiquid, fund_fail, mtf_block = [], [], [], [], []
            start_time = time.time()

            SCREENER_DF_CACHE.clear()

            yield f"data: {safe_json({'type': 'status', 'msg': 'Detecting market regime…'})}\n\n"
            regime = detect_market_regime()
            nifty_close = download_nifty_returns()

            yield f"data: {safe_json({'type': 'regime', 'regime': regime})}\n\n"
            yield f"data: {safe_json({'type': 'start', 'total': len(tickers), 'index': index_name.upper(), 'regime': regime['regime'], 'qualify': regime['qualify_score']})}\n\n"

            # ── Parallel prefetch: download all yfinance data up front ──
            # Collapses three serial network calls per ticker (3mo quote,
            # .info, 1y history) into concurrent fetches, cutting total
            # wall time roughly 10× on a 50-ticker scan.
            import yfinance as yf
            import pandas as pd
            yield f"data: {safe_json({'type': 'status', 'msg': f'Prefetching {len(tickers)} tickers in parallel…'})}\n\n"

            prefetch_3mo: dict = {}
            prefetch_full: dict = {}
            prefetch_fund: dict = {}

            def _fetch_3mo(t):
                try:
                    df = yf.download(t, period="3mo", auto_adjust=True, progress=False)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    df.dropna(inplace=True)
                    return ("3mo", t, df)
                except Exception:
                    return ("3mo", t, None)

            def _fetch_full(t):
                try:
                    return ("full", t, download_and_calculate(t, period="1y"))
                except Exception:
                    return ("full", t, (None, None))

            def _fetch_fund(t):
                try:
                    return ("fund", t, check_fundamentals(t))
                except Exception:
                    return ("fund", t, None)

            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = []
                for t in tickers:
                    futures.append(pool.submit(_fetch_3mo, t))
                    futures.append(pool.submit(_fetch_full, t))
                    if use_fundamentals:
                        futures.append(pool.submit(_fetch_fund, t))
                for fut in as_completed(futures):
                    kind, t, payload = fut.result()
                    if kind == "3mo":   prefetch_3mo[t] = payload
                    elif kind == "full": prefetch_full[t] = payload
                    elif kind == "fund": prefetch_fund[t] = payload

            for idx, ticker in enumerate(tickers):
                event = {
                    "type": "progress",
                    "idx": idx + 1,
                    "total": len(tickers),
                    "ticker": ticker.replace(".NS", ""),
                    "pct": round((idx + 1) / len(tickers) * 100),
                    "elapsed": round(time.time() - start_time, 1),
                }

                df_q = prefetch_3mo.get(ticker)
                if df_q is None or len(df_q) < 20:
                    failed.append(ticker)
                    yield f"data: {safe_json(event)}\n\n"
                    continue

                liq = check_liquidity(df_q, preset=liq_preset)
                if not liq["passes"]:
                    illiquid.append(ticker)
                    event["filtered"] = "liquidity"
                    event["liq_grade"] = liq["grade"]
                    yield f"data: {safe_json(event)}\n\n"
                    continue

                if use_fundamentals:
                    fund = prefetch_fund.get(ticker) or check_fundamentals(ticker)
                    if not fund or not fund.get("passes"):
                        fund_fail.append(ticker)
                        event["filtered"] = "fundamentals"
                        yield f"data: {safe_json(event)}\n\n"
                        continue

                df, dfw = prefetch_full.get(ticker, (None, None))
                if df is None:
                    failed.append(ticker)
                    yield f"data: {safe_json(event)}\n\n"
                    continue

                try:
                    SCREENER_DF_CACHE[ticker] = df[["Open", "High", "Low", "Close", "Volume"]].copy()
                except Exception:
                    pass

                if use_mtf:
                    mtf = check_weekly_gate(dfw)
                    if mtf["gate_level"] == "BLOCKED":
                        mtf_block.append(ticker)
                        event["filtered"] = "mtf"
                        yield f"data: {safe_json(event)}\n\n"
                        continue
                else:
                    mtf = {"gate_level": "OFF", "cap_score": None, "bonus_pts": 0}

                result = score_stock(
                    df, ticker, nifty_close=nifty_close, liq_result=liq,
                    custom_weights=custom_weights,
                )
                if result is None:
                    failed.append(ticker)
                    yield f"data: {safe_json(event)}\n\n"
                    continue

                if mtf["cap_score"] is not None:
                    result["W_Score"] = min(result["W_Score"], mtf["cap_score"])
                result["MTF_Gate"] = mtf["gate_level"]
                result["MTF_Bonus"] = mtf["bonus_pts"]
                result["Score"] = result["W_Score"] + result.get("RS_Bonus", 0) + mtf["bonus_pts"]

                clean = {k: (float(v) if hasattr(v, "item") else v) for k, v in result.items()}
                results.append(clean)
                event["result"] = clean
                yield f"data: {safe_json(event)}\n\n"
                time.sleep(0.05)

            results_sorted = sorted(
                results,
                key=lambda x: (-x["Score"], -x.get("RS_Score", 0), -x["ADX"], -x["Vol_Ratio"]),
            )
            total = len(results)
            qualify = regime.get("qualify_score", 18) if regime else 18
            summary = {
                "total": total,
                "exceptional": sum(1 for r in results if r["Score"] >= qualify + 8),
                "strong": sum(1 for r in results if qualify <= r["Score"] < qualify + 8),
                "moderate": sum(1 for r in results if qualify - 5 <= r["Score"] < qualify),
                "weak": sum(1 for r in results if r["Score"] < qualify - 5),
                "qualified": sum(1 for r in results if r["Score"] >= qualify),
                "illiquid": len(illiquid),
                "fund_failed": len(fund_fail),
                "mtf_blocked": len(mtf_block),
                "avg_rsi": round(sum(r["RSI"] for r in results) / total, 1) if total else 0,
                "avg_adx": round(sum(r["ADX"] for r in results) / total, 1) if total else 0,
                "pct_bull_st": round(sum(1 for r in results if r["ST_Dir"] == 1) / total * 100, 1) if total else 0,
                "pct_adv": round(sum(1 for r in results if r["1M_Chg%"] > 0) / total * 100, 1) if total else 0,
                "failed": len(failed),
                "elapsed": round(time.time() - start_time, 1),
                "max_score": effective_max,
                "regime": regime,
            }
            yield f"data: {safe_json({'type': 'complete', 'results': results_sorted, 'summary': summary})}\n\n"

        except Exception as exc:
            yield f"data: {safe_json({'type': 'error', 'message': str(exc), 'trace': traceback.format_exc()})}\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ── Backtester ─────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def backtest_run(request):
    try:
        data = json.loads(request.body or b"{}")
    except Exception:
        data = {}

    ticker_raw = data.get("ticker", "RELIANCE").strip().upper()
    ticker = ticker_raw if ticker_raw.endswith(".NS") else ticker_raw + ".NS"
    period = data.get("period", "3y")
    capital = int(data.get("capital", 100000))
    sl_pct = float(data.get("stop_loss", 5)) / 100
    tp_pct = float(data.get("take_profit", 10)) / 100
    max_hold = int(data.get("max_hold_days", 20))

    try:
        from backtester_v2 import (  # type: ignore
            get_data_with_indicators, run_backtest, calculate_metrics,
            strategy_triple_confirmation, strategy_mean_reversion,
            strategy_macd_momentum, strategy_golden_cross,
            strategy_supertrend, strategy_donchian_breakout,
            strategy_ichimoku, strategy_parabolic_sar, strategy_hma_momentum,
        )

        df = get_data_with_indicators(ticker, period)
        strategies = [
            (strategy_triple_confirmation, "Triple Confirmation"),
            (strategy_mean_reversion, "Mean Reversion"),
            (strategy_macd_momentum, "MACD Momentum"),
            (strategy_golden_cross, "Golden Cross"),
            (strategy_supertrend, "Supertrend"),
            (strategy_donchian_breakout, "Donchian Breakout"),
            (strategy_ichimoku, "Ichimoku"),
            (strategy_parabolic_sar, "Parabolic SAR"),
            (strategy_hma_momentum, "HMA Momentum"),
        ]

        all_metrics, all_equity_curves, all_trades = [], {}, {}
        chart_dates = None

        for func, name in strategies:
            trades, equity = run_backtest(
                df, func, name,
                capital=capital, stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct, max_hold_days=max_hold,
            )
            metrics = calculate_metrics(trades, equity, capital, name)

            step = max(1, len(equity) // 300)
            all_equity_curves[name] = [float(v) for v in equity[::step]]
            if chart_dates is None:
                chart_dates = [d.strftime("%b %y") for d in df.index[::step]]

            clean_trades = []
            for t in trades:
                clean_trades.append({
                    "Entry Date": t["Entry Date"],
                    "Exit Date": t["Exit Date"],
                    "Entry Price": float(t["Entry Price"]),
                    "Exit Price": float(t["Exit Price"]),
                    "PnL %": float(t["PnL %"]),
                    "PnL Rs": float(t["PnL ₹"]),
                    "Days Held": int(t["Days Held"]),
                    "Exit Reason": t["Exit Reason"],
                    "Win": bool(t["Win"]),
                })
            all_trades[name] = clean_trades

            clean_m = {}
            for k, v in metrics.items():
                if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                    clean_m[k] = None
                elif hasattr(v, "item"):
                    clean_m[k] = v.item()
                else:
                    clean_m[k] = v
            all_metrics.append(clean_m)

        best_ret = max(all_metrics, key=lambda m: m["Return %"] or 0)["Strategy"]
        best_sharpe = max(all_metrics, key=lambda m: m["Sharpe Ratio"] or 0)["Strategy"]

        return _json_response({
            "success": True,
            "ticker": ticker,
            "display_ticker": ticker.replace(".NS", ""),
            "period": period,
            "capital": capital,
            "date_range": f"{df.index[0].strftime('%d %b %Y')} – {df.index[-1].strftime('%d %b %Y')}",
            "total_days": len(df),
            "metrics": all_metrics,
            "equity_curves": all_equity_curves,
            "chart_dates": chart_dates or [],
            "trades": all_trades,
            "best_return": best_ret,
            "best_sharpe": best_sharpe,
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


# ── Stock data / live / news ───────────────────────────────────────────

def _series(col):
    out = []
    for v in col:
        try:
            f = float(v)
            out.append(None if (math.isnan(f) or math.isinf(f)) else round(f, 4))
        except Exception:
            out.append(None)
    return out


@require_GET
def stock_data(request):
    ticker_raw = request.GET.get("ticker", "RELIANCE").strip().upper()
    period = request.GET.get("period", "1y")
    ticker = ticker_raw if ticker_raw.endswith(".NS") else ticker_raw + ".NS"

    try:
        df = None
        summary = None

        try:
            from screener_v3 import (  # type: ignore
                download_and_calculate as _dac_v3,
                score_stock as _ss_v3,
                download_nifty_returns,
            )
            for try_period in ([period] if period != "1y" else ["1y", "2y"]):
                df, _ = _dac_v3(ticker, period=try_period)
                if df is not None:
                    break
            if df is not None:
                nifty_close = download_nifty_returns()
                summary = _ss_v3(df, ticker, nifty_close=nifty_close)
                if summary:
                    summary["Score"] = summary.get("W_Score", 0) + summary.get("RS_Bonus", 0)
        except Exception:
            df = None

        if df is None:
            from screener_v2 import (  # type: ignore
                download_and_calculate as _dac_v2,
                score_stock as _ss_v2,
            )
            for try_period in ([period, "2y", "3y"] if period == "1y" else [period, "1y", "2y"]):
                df = _dac_v2(ticker, period=try_period)
                if df is not None:
                    break
            if df is None:
                return _json_response(
                    {"success": False, "error": f"Could not download data for {ticker_raw}. Try again in a moment."},
                    status=400,
                )
            summary = _ss_v2(df, ticker)
            if summary:
                summary["Score"] = summary.get("Score", 0)

        dates = [d.strftime("%d-%m-%Y") for d in df.index]
        n = len(df)

        def _col(name):
            return _series(df[name]) if name in df.columns else [None] * n

        pat_hammer, pat_doji, pat_engulf = [None] * n, [None] * n, [None] * n
        try:
            from complete_indicators import is_hammer, is_bullish_engulfing, is_doji  # type: ignore
            lows = df["Low"].values
            for i in range(max(1, n - 90), n):
                row = df.iloc[i]
                prev = df.iloc[i - 1]
                lo = float(lows[i])
                if is_hammer(row):
                    pat_hammer[i] = round(lo * 0.992, 2)
                if is_doji(row):
                    pat_doji[i] = round(lo * 0.992, 2)
                if is_bullish_engulfing(prev, row):
                    pat_engulf[i] = round(lo * 0.992, 2)
        except Exception:
            pass

        return _json_response({
            "success": True,
            "ticker": ticker_raw,
            "period": period,
            "dates": dates,
            "ohlcv": {
                "open": _series(df["Open"]),
                "high": _series(df["High"]),
                "low": _series(df["Low"]),
                "close": _series(df["Close"]),
                "volume": _series(df["Volume"]),
            },
            "ind": {
                "sma20": _col("SMA_20"), "sma50": _col("SMA_50"), "sma200": _col("SMA_200"),
                "bb_up": _col("BB_Up"), "bb_lo": _col("BB_Lo"), "hma21": _col("HMA_21"),
                "rsi": _col("RSI"),
                "macd": _col("MACD"), "macd_sig": _col("MACD_Signal"), "macd_hist": _col("MACD_Hist"),
                "adx": _col("ADX"), "di_plus": _col("DI_Plus"), "di_minus": _col("DI_Minus"),
                "st_dir": _col("ST_Dir"),
                "ich_ca": _col("Ich_Cloud_A"), "ich_cb": _col("Ich_Cloud_B"),
                "ich_tk": _col("Ich_Tenkan"), "ich_kj": _col("Ich_Kijun"),
                "psar": _col("PSAR"), "psar_dir": _col("PSAR_Trend"),
                "williams_r": _col("Williams_R"), "cmf": _col("CMF"),
                "aroon_up": _col("Aroon_Up"), "aroon_dn": _col("Aroon_Dn"),
                "mfi": _col("MFI"),
            },
            "patterns": {"hammer": pat_hammer, "doji": pat_doji, "engulf": pat_engulf},
            "summary": summary,
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@require_GET
def stock_live(request):
    """5-min intraday OHLCV; falls back to last available trading session."""
    import yfinance as yf
    import pandas as pd
    ticker_raw = request.GET.get("ticker", "RELIANCE").strip().upper()
    ticker = ticker_raw if ticker_raw.endswith(".NS") else ticker_raw + ".NS"
    try:
        is_live = False
        df = None
        raw = yf.download(ticker, period="1d", interval="5m", auto_adjust=True, progress=False)
        if raw is not None and len(raw) > 0:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.dropna(inplace=True)
            if len(raw) > 0:
                df = raw
                is_live = True

        if df is None:
            raw5 = yf.download(ticker, period="5d", interval="5m", auto_adjust=True, progress=False)
            if raw5 is not None and len(raw5) > 0:
                if isinstance(raw5.columns, pd.MultiIndex):
                    raw5.columns = raw5.columns.get_level_values(0)
                raw5.dropna(inplace=True)
                if len(raw5) > 0:
                    last_date = raw5.index.normalize()[-1]
                    df = raw5[raw5.index.normalize() == last_date]

        if df is None or len(df) == 0:
            return _json_response({"success": False, "error": "No intraday data available"}, status=400)

        times = [d.strftime("%H:%M") for d in df.index]
        closes = [round(float(v), 2) for v in df["Close"]]
        highs = [round(float(v), 2) for v in df["High"]]
        lows = [round(float(v), 2) for v in df["Low"]]
        vols = [int(v) for v in df["Volume"]]

        df2 = yf.download(ticker, period="5d", interval="1d", auto_adjust=True, progress=False)
        if isinstance(df2.columns, pd.MultiIndex):
            df2.columns = df2.columns.get_level_values(0)
        prev_close = float(df2["Close"].iloc[-2]) if len(df2) >= 2 else closes[0]
        last_close = closes[-1] if closes else 0
        chg_pct = round((last_close - prev_close) / prev_close * 100, 2) if prev_close else 0
        session_date = df.index[0].strftime("%d %b %Y")
        session_label = "Today" if is_live else f"Last Session — {session_date}"

        return _json_response({
            "success": True, "ticker": ticker_raw, "is_live": is_live,
            "session_label": session_label,
            "times": times, "close": closes, "high": highs, "low": lows, "volume": vols,
            "last": last_close, "prev_close": round(prev_close, 2), "chg_pct": chg_pct,
            "day_open": round(float(df["Open"].iloc[0]), 2),
            "day_high": round(max(highs), 2), "day_low": round(min(lows), 2),
            "date": session_date,
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@require_GET
def stock_news(request):
    """Aggregates news from Yahoo Finance + Google News RSS (Indian financial sites)."""
    import yfinance as yf
    import xml.etree.ElementTree as ET
    import re
    from email.utils import parsedate_to_datetime

    ticker_raw = request.GET.get("ticker", "RELIANCE").strip().upper()
    ticker = ticker_raw if ticker_raw.endswith(".NS") else ticker_raw + ".NS"

    cutoff = (datetime.now(IST) - timedelta(days=60)).timestamp()
    articles, seen = [], set()

    def _add(title, synopsis, link, publisher, ts):
        key = title.lower()[:60]
        if key in seen or not title:
            return
        seen.add(key)
        articles.append({
            "title": title,
            "synopsis": synopsis or title,
            "link": link,
            "publisher": publisher,
            "date": datetime.fromtimestamp(ts, tz=IST).strftime("%d %b %Y") if ts else "—",
            "time": datetime.fromtimestamp(ts, tz=IST).strftime("%d %b %Y, %H:%M") if ts else "—",
            "timestamp": ts,
        })

    try:
        t = yf.Ticker(ticker)
        for item in (t.news or []):
            ts = item.get("providerPublishTime", 0)
            if ts and ts < cutoff:
                continue
            content = item.get("content", {}) or {}
            title = (content.get("title") or item.get("title") or "").strip()
            link = (content.get("canonicalUrl", {}).get("url") or item.get("link") or "").strip()
            pub = (content.get("provider", {}).get("displayName") or item.get("publisher") or "").strip()
            synopsis = (content.get("summary") or "").strip()
            _add(title, synopsis, link, pub, ts or 0)
    except Exception:
        pass

    try:
        company_name = ticker_raw
        try:
            info = yf.Ticker(ticker).info
            company_name = info.get("shortName") or info.get("longName") or ticker_raw
            company_name = company_name.replace(" Limited", "").replace(" Ltd", "").strip()
        except Exception:
            pass

        indian_sites = (
            "site:moneycontrol.com OR site:economictimes.indiatimes.com OR "
            "site:livemint.com OR site:business-standard.com OR "
            "site:financialexpress.com OR site:ndtvprofit.com OR "
            "site:thehindubusinessline.com OR site:zeebiz.com"
        )
        query = f'"{company_name}" NSE stock ({indian_sites})'
        rss_url = (
            "https://news.google.com/rss/search"
            f"?q={_requests.utils.quote(query)}"
            "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        resp = _requests.get(rss_url, headers=headers, timeout=8)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("source") or "Google News").strip()
                desc = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()
                pub_date_str = item.findtext("pubDate") or ""
                ts = 0
                if pub_date_str:
                    try:
                        ts = int(parsedate_to_datetime(pub_date_str).timestamp())
                    except Exception:
                        pass
                if ts and ts < cutoff:
                    continue
                _add(title, desc, link, pub, ts)
    except Exception:
        pass

    articles.sort(key=lambda x: x["timestamp"], reverse=True)
    return _json_response({"success": True, "articles": articles, "ticker": ticker_raw})


@require_GET
def search_ticker(request):
    """Yahoo Finance ticker search filtered to NSE/BSE."""
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return _json_response({"results": []})
    try:
        resp = _requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={
                "q": q, "quotesCount": 12, "newsCount": 0,
                "enableFuzzyQuery": "true", "region": "IN", "lang": "en-IN",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        data = resp.json()
        results = []
        for item in data.get("quotes", []):
            exchange = item.get("exchange", "")
            if exchange not in ("NSI", "BSE", "NSE"):
                continue
            sym = item.get("symbol", "")
            if not sym:
                continue
            display = sym.replace(".NS", "").replace(".BO", "")
            name = (item.get("shortname") or item.get("longname") or "").strip()
            results.append({
                "symbol": display,
                "name": name,
                "exchange": "NSE" if exchange == "NSI" else exchange,
            })
        return _json_response({"results": results})
    except Exception as exc:
        return _json_response({"results": [], "error": str(exc)}, status=500)


# ── Tools API (analysis suite + advanced strategies) ───────────────────

def _rsi_series(close, period=14):
    d = close.diff()
    ag = d.where(d > 0, 0).ewm(com=period - 1, min_periods=period).mean()
    al = (-d.where(d < 0, 0)).ewm(com=period - 1, min_periods=period).mean()
    return 100 - 100 / (1 + ag / al)


def _macd_series(close, fast=12, slow=26, sig=9):
    ml = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sl = ml.ewm(span=sig, adjust=False).mean()
    return ml, sl


def _atr_series(df, period=14):
    import pandas as pd
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift(1)).abs()
    lc = (df["Low"] - df["Close"].shift(1)).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(period).mean()


def _dl(sym, period="1y", interval="1d"):
    import yfinance as yf
    import pandas as pd
    df = yf.download(sym, period=period, interval=interval, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(how="all", inplace=True)
    return df if len(df) > 5 else None


def _read_json_body(request) -> dict:
    try:
        return json.loads(request.body or b"{}") or {}
    except Exception:
        return {}


@csrf_exempt
@require_POST
def tools_confluence(request):
    data = _read_json_body(request)
    sym = _ns(data.get("symbol", ""))
    if not sym:
        return _json_response({"success": False, "error": "Symbol required"}, status=400)
    try:
        import pandas as pd
        results = []
        for label, period, interval in [("Daily", "6mo", "1d"), ("Weekly", "2y", "1wk"), ("Monthly", "5y", "1mo")]:
            df = _dl(sym, period=period, interval=interval)
            if df is None or len(df) < 20:
                continue
            close = df["Close"].dropna()
            rsi_s = _rsi_series(close)
            ml, sl = _macd_series(close)
            rsi_v = float(rsi_s.iloc[-1])
            macd_bull = bool(float(ml.iloc[-1]) > float(sl.iloc[-1]))
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50v = close.rolling(50).mean().iloc[-1]
            sma50 = float(sma50v) if not pd.isna(sma50v) else None
            price = float(close.iloc[-1])
            a20 = price > sma20
            a50 = (price > sma50) if sma50 is not None else None
            bull = sum([rsi_v > 50, rsi_v < 70, macd_bull, a20, a50 or False])
            rsi_sig = ("Overbought" if rsi_v > 70 else
                       "Bullish" if rsi_v > 55 else
                       "Neutral" if rsi_v > 45 else
                       "Bearish" if rsi_v > 30 else "Oversold")
            results.append({
                "label": label, "price": round(price, 2),
                "rsi": round(rsi_v, 1), "rsi_signal": rsi_sig,
                "macd_bull": macd_bull,
                "above_sma20": a20, "above_sma50": a50,
                "sma20": round(sma20, 2),
                "sma50": round(sma50, 2) if sma50 is not None else None,
                "bull_score": bull, "max_score": 5,
                "trend": ("BULLISH" if bull >= 4 else "NEUTRAL" if bull >= 2 else "BEARISH"),
            })
        if not results:
            return _json_response({"success": False, "error": f"No data for {sym}"}, status=400)
        overall = sum(r["bull_score"] for r in results)
        return _json_response({
            "success": True, "symbol": sym.replace(".NS", ""),
            "timeframes": results, "overall_score": overall, "overall_max": 15,
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
@require_POST
def tools_sr(request):
    data = _read_json_body(request)
    sym = _ns(data.get("symbol", ""))
    if not sym:
        return _json_response({"success": False, "error": "Symbol required"}, status=400)
    try:
        df = _dl(sym, period="3mo", interval="1d")
        if df is None or len(df) < 10:
            return _json_response({"success": False, "error": f"No data for {sym}"}, status=400)
        H = float(df["High"].iloc[-1]); L = float(df["Low"].iloc[-1]); C = float(df["Close"].iloc[-1])
        pivot = (H + L + C) / 3
        levels = [
            {"label": "R3", "price": round(H + 2 * (pivot - L), 2), "type": "resistance"},
            {"label": "R2", "price": round(pivot + (H - L), 2), "type": "resistance"},
            {"label": "R1", "price": round(2 * pivot - L, 2), "type": "resistance"},
            {"label": "Pivot", "price": round(pivot, 2), "type": "pivot"},
            {"label": "S1", "price": round(2 * pivot - H, 2), "type": "support"},
            {"label": "S2", "price": round(pivot - (H - L), 2), "type": "support"},
            {"label": "S3", "price": round(L - 2 * (H - pivot), 2), "type": "support"},
        ]
        highs = df["High"].values; lows = df["Low"].values
        sh, sl_list = [], []
        for i in range(2, len(df) - 2):
            if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
                sh.append(round(float(highs[i]), 2))
            if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
                sl_list.append(round(float(lows[i]), 2))
        near_res = min((l for l in levels if l["type"] == "resistance" and l["price"] > C),
                       key=lambda x: x["price"], default=None)
        near_sup = max((l for l in levels if l["type"] == "support" and l["price"] < C),
                       key=lambda x: x["price"], default=None)
        return _json_response({
            "success": True, "symbol": sym.replace(".NS", ""), "price": round(C, 2),
            "levels": levels,
            "swing_highs": sorted(sh, reverse=True)[:5],
            "swing_lows": sorted(sl_list)[:5],
            "nearest_resistance": near_res, "nearest_support": near_sup,
            "dates": [d.strftime("%d-%m-%Y") for d in df.index],
            "closes": [round(float(v), 2) for v in df["Close"]],
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
@require_POST
def tools_rs_ranker(request):
    data = _read_json_body(request)
    syms_raw = [s.strip() for s in (data.get("symbols", "") or "").split(",") if s.strip()]
    benchmark = (data.get("benchmark", "^NSEI") or "^NSEI").strip().upper() or "^NSEI"
    period = data.get("period", "3mo")
    if not syms_raw:
        return _json_response({"success": False, "error": "Symbols required"}, status=400)
    try:
        b_df = _dl(benchmark, period=period, interval="1d")
        if b_df is None:
            return _json_response({"success": False, "error": f"Cannot download {benchmark}"}, status=400)
        b_ret = float((b_df["Close"].iloc[-1] - b_df["Close"].iloc[0]) / b_df["Close"].iloc[0] * 100)
        results = []
        for sr in syms_raw:
            sym = _ns(sr)
            df = _dl(sym, period=period, interval="1d")
            if df is None:
                continue
            s_ret = float((df["Close"].iloc[-1] - df["Close"].iloc[0]) / df["Close"].iloc[0] * 100)
            rs = round(s_ret / b_ret, 3) if b_ret else 0
            rsi_v = round(float(_rsi_series(df["Close"].dropna()).iloc[-1]), 1)
            results.append({
                "symbol": sr.replace(".NS", "").upper(),
                "return_pct": round(s_ret, 2), "rs": rs,
                "rsi": rsi_v, "outperform": s_ret > b_ret,
            })
        results.sort(key=lambda x: -x["rs"])
        for i, r in enumerate(results):
            r["rank"] = i + 1
        return _json_response({
            "success": True, "benchmark": benchmark, "period": period,
            "bench_return": round(b_ret, 2), "results": results,
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
@require_POST
def tools_monte_carlo(request):
    data = _read_json_body(request)
    sym = _ns(data.get("symbol", ""))
    days = min(int(data.get("days", 252)), 504)
    n_sim = 1000
    if not sym:
        return _json_response({"success": False, "error": "Symbol required"}, status=400)
    try:
        import numpy as np
        df = _dl(sym, period="2y", interval="1d")
        if df is None or len(df) < 50:
            return _json_response({"success": False, "error": f"Not enough data for {sym}"}, status=400)
        close = df["Close"].dropna()
        dr = close.pct_change().dropna()
        mu = float(dr.mean()); sigma = float(dr.std())
        price0 = float(close.iloc[-1])
        rng = np.random.default_rng(42)
        rand = rng.normal(mu, sigma, (days, n_sim))
        paths = price0 * np.cumprod(1 + rand, axis=0)
        final = paths[-1]
        p = lambda q: round(float(np.percentile(final, q)), 2)
        step = max(1, days // 120)
        days_ax = list(range(0, days, step))
        def _band(q):
            return [round(float(np.percentile(paths[d], q)), 2) for d in days_ax]
        return _json_response({
            "success": True, "symbol": sym.replace(".NS", ""),
            "current_price": round(price0, 2), "days": days,
            "mu_annual": round(mu * 252 * 100, 2),
            "sigma_annual": round(sigma * (252 ** 0.5) * 100, 2),
            "p5": p(5), "p25": p(25), "p50": p(50), "p75": p(75), "p95": p(95),
            "prob_profit": round(float((final > price0).mean() * 100), 1),
            "chart": {"days": days_ax, "p5": _band(5), "p50": _band(50), "p95": _band(95)},
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
@require_POST
def tools_portfolio_risk(request):
    data = _read_json_body(request)
    holdings = data.get("holdings", {}) or {}
    if len(holdings) < 2:
        return _json_response({"success": False, "error": "At least 2 holdings required"}, status=400)
    try:
        import pandas as pd
        import numpy as np
        total = sum(holdings.values())
        cl_data, stats = {}, []
        for sym_raw, amt in holdings.items():
            sym = _ns(sym_raw)
            df = _dl(sym, period="1y", interval="1d")
            if df is None:
                continue
            close = df["Close"].dropna()
            cl_data[sym_raw] = close
            dr = close.pct_change().dropna()
            stats.append({
                "symbol": sym_raw.replace(".NS", "").upper(),
                "invested": round(float(amt), 0),
                "weight": round(float(amt) / total * 100, 1),
                "annual_return": round(float(dr.mean()) * 252 * 100, 2),
                "annual_vol": round(float(dr.std()) * (252 ** 0.5) * 100, 2),
                "price": round(float(close.iloc[-1]), 2),
            })
        if len(cl_data) < 2:
            return _json_response({"success": False,
                                   "error": "Not enough valid data — use .NS suffix for NSE stocks."},
                                  status=400)
        combined = pd.DataFrame(cl_data).dropna()
        port_ret = combined.pct_change().dropna()
        w_arr = [holdings.get(s, 0) / total for s in combined.columns]
        port_daily = port_ret.dot(w_arr)
        p_ann_ret = float(port_daily.mean()) * 252 * 100
        p_ann_vol = float(port_daily.std()) * (252 ** 0.5) * 100
        var_95 = float(np.percentile(port_daily, 5))
        sharpe = p_ann_ret / p_ann_vol if p_ann_vol else 0
        cum = ((1 + port_daily).cumprod() - 1) * 100
        step = max(1, len(cum) // 200)
        return _json_response({
            "success": True, "total_value": round(total, 0), "stocks": stats,
            "portfolio_return": round(p_ann_ret, 2),
            "portfolio_vol": round(p_ann_vol, 2),
            "var_95_pct": round(var_95 * 100, 3),
            "var_95_amount": round(abs(var_95) * total, 0),
            "sharpe": round(sharpe, 3),
            "dates": [d.strftime("%d-%m-%Y") for d in combined.index[::step]],
            "cumulative_return": [round(float(v), 3) for v in cum.iloc[::step]],
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
@require_POST
def tools_pairs(request):
    data = _read_json_body(request)
    s1_raw = (data.get("sym1", "") or "").strip().upper()
    s2_raw = (data.get("sym2", "") or "").strip().upper()
    sym1, sym2 = _ns(s1_raw), _ns(s2_raw)
    if not sym1 or not sym2:
        return _json_response({"success": False, "error": "Two symbols required"}, status=400)
    try:
        import pandas as pd
        import numpy as np
        df1 = _dl(sym1, period="2y", interval="1d")
        df2 = _dl(sym2, period="2y", interval="1d")
        if df1 is None or df2 is None or len(df1) < 60 or len(df2) < 60:
            return _json_response({"success": False, "error": "Not enough data for one or both symbols"}, status=400)
        c1 = df1["Close"].rename(s1_raw); c2 = df2["Close"].rename(s2_raw)
        combined = pd.concat([c1, c2], axis=1).dropna()
        if len(combined) < 60:
            return _json_response({"success": False, "error": "Not enough overlapping data"}, status=400)
        corr = float(combined[s1_raw].corr(combined[s2_raw]))
        x = combined[s2_raw].values; y = combined[s1_raw].values
        hedge_ratio = float(np.polyfit(x, y, 1)[0])
        spread = combined[s1_raw] - hedge_ratio * combined[s2_raw]
        sp_mean = float(spread.mean()); sp_std = float(spread.std())
        z = (spread - sp_mean) / sp_std
        cur_z = float(z.iloc[-1])
        coint_pval = None; cointegrated = None
        try:
            from statsmodels.tsa.stattools import coint as _coint
            _, cp, _ = _coint(combined[s1_raw], combined[s2_raw])
            coint_pval = round(float(cp), 4); cointegrated = coint_pval < 0.05
        except Exception:
            pass
        signal = ("SELL SPREAD" if cur_z > 2 else "BUY SPREAD" if cur_z < -2 else "NEUTRAL")
        step = max(1, len(combined) // 200)
        return _json_response({
            "success": True, "sym1": s1_raw.replace(".NS", ""), "sym2": s2_raw.replace(".NS", ""),
            "correlation": round(corr, 4), "hedge_ratio": round(hedge_ratio, 4),
            "cointegrated": cointegrated, "coint_pval": coint_pval,
            "current_z": round(cur_z, 3), "signal": signal,
            "spread_mean": round(sp_mean, 4), "spread_std": round(sp_std, 4),
            "dates": [d.strftime("%d-%m-%Y") for d in combined.index[::step]],
            "z_scores": [round(float(v), 3) for v in z.iloc[::step]],
            "spread": [round(float(v), 2) for v in spread.iloc[::step]],
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@csrf_exempt
@require_POST
def tools_supertrend(request):
    data = _read_json_body(request)
    sym = _ns(data.get("symbol", ""))
    atr_period = int(data.get("atr_period", 10))
    multiplier = float(data.get("multiplier", 3.0))
    if not sym:
        return _json_response({"success": False, "error": "Symbol required"}, status=400)
    try:
        import pandas as pd
        df = _dl(sym, period="2y", interval="1d")
        if df is None or len(df) < 50:
            return _json_response({"success": False, "error": f"Not enough data for {sym}"}, status=400)
        atr = _atr_series(df, atr_period)
        hl2 = (df["High"] + df["Low"]) / 2
        bu = hl2 + multiplier * atr
        bl = hl2 - multiplier * atr
        fu = bu.copy(); fl = bl.copy()
        close = df["Close"]
        for i in range(1, len(df)):
            fu.iloc[i] = bu.iloc[i] if (bu.iloc[i] < fu.iloc[i - 1] or close.iloc[i - 1] > fu.iloc[i - 1]) else fu.iloc[i - 1]
            fl.iloc[i] = bl.iloc[i] if (bl.iloc[i] > fl.iloc[i - 1] or close.iloc[i - 1] < fl.iloc[i - 1]) else fl.iloc[i - 1]
        direction = pd.Series(1, index=df.index, dtype=int)
        st_line = pd.Series(float("nan"), index=df.index)
        for i in range(1, len(df)):
            prev = int(direction.iloc[i - 1])
            if prev == 1:
                direction.iloc[i] = -1 if float(close.iloc[i]) < float(fl.iloc[i]) else 1
            else:
                direction.iloc[i] = 1 if float(close.iloc[i]) > float(fu.iloc[i]) else -1
            st_line.iloc[i] = float(fl.iloc[i]) if direction.iloc[i] == 1 else float(fu.iloc[i])
        trades = []; in_trade = False; ep = 0.0; ed = ""
        for i in range(1, len(df)):
            pd_ = int(direction.iloc[i - 1]); cd = int(direction.iloc[i])
            if not in_trade and pd_ == -1 and cd == 1:
                in_trade = True; ep = float(close.iloc[i]); ed = df.index[i].strftime("%d-%m-%Y")
            elif in_trade and pd_ == 1 and cd == -1:
                xp = float(close.iloc[i])
                pnl = (xp - ep) / ep * 100
                trades.append({"entry": ed, "exit": df.index[i].strftime("%d-%m-%Y"),
                               "entry_price": round(ep, 2), "exit_price": round(xp, 2),
                               "pnl_pct": round(pnl, 2), "win": pnl > 0})
                in_trade = False
        wins = sum(1 for t in trades if t["win"])
        win_rate = round(wins / len(trades) * 100, 1) if trades else 0
        total_r = round(sum(t["pnl_pct"] for t in trades), 2)
        cur_dir = int(direction.iloc[-1])
        step = max(1, len(df) // 200)
        return _json_response({
            "success": True, "symbol": sym.replace(".NS", ""),
            "current_trend": "BULLISH" if cur_dir == 1 else "BEARISH",
            "current_signal": "BUY" if cur_dir == 1 else "SELL",
            "supertrend_line": round(float(st_line.iloc[-1]), 2),
            "atr": round(float(atr.iloc[-1]), 2),
            "atr_period": atr_period, "multiplier": multiplier,
            "total_trades": len(trades), "win_rate": win_rate, "total_return": total_r,
            "trades": trades[-15:],
            "dates": [d.strftime("%d-%m-%Y") for d in df.index[::step]],
            "closes": [round(float(v), 2) for v in close.iloc[::step]],
            "st_line": [round(float(v), 2) if not math.isnan(v) else None for v in st_line.iloc[::step]],
            "direction": [int(v) for v in direction.iloc[::step]],
        })
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@require_GET
def dashboard_top_picks(request):
    """
    Cached top-5 ranked Nifty 50 picks from screener_v3 for the Dashboard.
    First call takes ~30-60s (downloads + scores Nifty 50). Subsequent calls
    served from cache for 1 hour.
    """
    from django.core.cache import cache
    key = "dash_top_picks_v1"
    cached = cache.get(key)
    if cached is not None:
        return _json_response({"success": True, "cached": True, **cached})
    try:
        import yfinance as yf
        import pandas as pd
        from screener_v3 import (  # type: ignore
            download_and_calculate, score_stock, check_liquidity,
            detect_market_regime, download_nifty_returns, NIFTY_50,
        )
        regime = detect_market_regime()
        nifty_close = download_nifty_returns()
        results = []
        for ticker in NIFTY_50:
            try:
                df_q = yf.download(ticker, period="3mo", auto_adjust=True, progress=False)
                if isinstance(df_q.columns, pd.MultiIndex):
                    df_q.columns = df_q.columns.get_level_values(0)
                df_q.dropna(inplace=True)
                if len(df_q) < 20:
                    continue
                liq = check_liquidity(df_q, preset="medium")
                if not liq["passes"]:
                    continue
                df, _ = download_and_calculate(ticker, period="1y")
                if df is None:
                    continue
                r = score_stock(df, ticker, nifty_close=nifty_close, liq_result=liq)
                if r is None:
                    continue
                r["Score"] = r["W_Score"] + r.get("RS_Bonus", 0)
                results.append({k: (float(v) if hasattr(v, "item") else v) for k, v in r.items()})
            except Exception:
                continue
        results.sort(key=lambda x: (-x["Score"], -x.get("RS_Score", 0), -x.get("ADX", 0)))
        top = results[:5]
        payload = {
            "top": top,
            "regime": regime,
            "total_scored": len(results),
        }
        cache.set(key, payload, 3600)
        return _json_response({"success": True, "cached": False, **payload})
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc), "trace": traceback.format_exc()}, status=500)


@require_GET
def trade_analyzer_stream(request):
    """SSE — analyzes trade setups for a list of tickers, reuses screener cache when warm."""
    tickers_param = request.GET.get("tickers", "")
    config_param = request.GET.get("config", "{}")
    tickers_raw = [t.strip() for t in tickers_param.split(",") if t.strip()]
    try:
        user_cfg = json.loads(config_param)
    except Exception:
        user_cfg = {}

    def generate():
        try:
            from trade_analyzer import analyze_ticker, CONFIG as TA_CONFIG  # type: ignore

            config = {**TA_CONFIG, **{k: v for k, v in user_cfg.items() if v is not None}}

            tickers = []
            for t in tickers_raw:
                u = t.upper()
                if u.startswith("^") or u.endswith(".NS") or u.endswith(".BO"):
                    tickers.append(u)
                else:
                    tickers.append(u + ".NS")

            if not tickers:
                yield f"data: {safe_json({'type': 'error', 'message': 'No tickers provided'})}\n\n"
                return

            cache_hits = sum(1 for t in tickers if t in SCREENER_DF_CACHE)
            yield f"data: {safe_json({'type': 'start', 'total': len(tickers), 'cache_hits': cache_hits})}\n\n"

            trades, skipped = [], []
            for idx, ticker in enumerate(tickers):
                clean_name = ticker.replace(".NS", "").replace(".BO", "")
                pct = round((idx + 1) / len(tickers) * 100)
                cached_df = SCREENER_DF_CACHE.get(ticker)
                yield f"data: {safe_json({'type': 'progress', 'idx': idx + 1, 'total': len(tickers), 'ticker': clean_name, 'pct': pct, 'cached': cached_df is not None})}\n\n"

                result = analyze_ticker(ticker, config, prefetched_df=cached_df)
                clean = json.loads(safe_json(result))
                verdict = result.get("verdict", "ERROR")
                if verdict == "TRADE":
                    trades.append(clean)
                    yield f"data: {safe_json({'type': 'trade', 'result': clean})}\n\n"
                else:
                    skipped.append(clean)
                    yield f"data: {safe_json({'type': 'skip', 'result': clean})}\n\n"

            grade_order = {"A": 0, "B": 1, "C": 2}
            trades.sort(key=lambda r: (
                grade_order.get(r.get("setup", {}).get("grade", "C"), 3),
                -(r.get("setup", {}).get("rr_ratio") or 0),
            ))
            summary = {"analyzed": len(tickers), "trades": len(trades),
                       "skipped": len(skipped), "cache_hits": cache_hits}
            yield f"data: {safe_json({'type': 'complete', 'trades': trades, 'skipped': skipped, 'summary': summary})}\n\n"

        except Exception as exc:
            yield f"data: {safe_json({'type': 'error', 'message': str(exc), 'trace': traceback.format_exc()})}\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
