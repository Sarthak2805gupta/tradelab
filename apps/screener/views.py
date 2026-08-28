"""
Backtest + trade-analyzer views ported from the old Flask screener
(Stock-Screener/app.py). The standalone Screener scan page has been
removed; these two endpoints remain because they're used by the
Analysis page's backtester and the Watchlist's trade-analyzer stream.
"""
from __future__ import annotations

import json
import math
import traceback

from django.http import HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST

# Trigger sys.path injection for the ported flat-import modules
from . import services  # noqa: F401
from .json_utils import safe_json


# In-process cache the Trade Analyzer checks before hitting yfinance.
# Currently always empty since nothing populates it (the screener scan
# that used to warm it was removed) — kept so trade_analyzer_stream's
# cache-hit accounting still works.
SCREENER_DF_CACHE: dict = {}


def _json_response(payload, status=200) -> HttpResponse:
    return HttpResponse(safe_json(payload), status=status, content_type="application/json")


# ── Backtester ─────────────────────────────────────────────────────────

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


# ── Trade Analyzer (used by the Watchlist page) ─────────────────────────

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
