"""
"What if I'd bought X on date Y for amount Z?" — hindsight calculator.
Extracted from the view; pure computation apart from the yfinance download.
"""
from __future__ import annotations

import math
from datetime import datetime


def compute(ticker: str, date_raw: str, amount_raw: str) -> tuple[dict | None, str | None]:
    """Return (result, error). Exactly one of the two is non-None."""
    try:
        import yfinance as yf
        import pandas as pd

        amount = float(amount_raw)
        start_dt = datetime.strptime(date_raw, "%Y-%m-%d")

        hist = yf.download(ticker, start=start_dt.strftime("%Y-%m-%d"),
                           auto_adjust=True, progress=False)
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        hist = hist.dropna()
        if len(hist) < 2:
            return None, "Not enough price history for that date."

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
            bench = yf.download("^NSEI", start=start_dt.strftime("%Y-%m-%d"),
                                auto_adjust=True, progress=False)
            if isinstance(bench.columns, pd.MultiIndex):
                bench.columns = bench.columns.get_level_values(0)
            bench_ret = float((bench["Close"].iloc[-1] / bench["Close"].iloc[0] - 1) * 100)
        except Exception:
            bench_ret = None

        # Chart series
        series = [
            {"t": d.strftime("%Y-%m-%d"), "v": round(float(c * shares), 2)}
            for d, c in closes.items()
        ]

        return {
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
        }, None
    except Exception as exc:
        return None, str(exc)
