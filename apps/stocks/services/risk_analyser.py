"""
Risk-aware stock screener.

User says: "I have ₹X to invest and I'm only willing to lose at most Y%."
We score the QUICK_PICKS universe (or a passed-in symbol list) on:

  1. Estimated 1-month downside (using realised daily volatility × √21 × 1.65)
  2. Trend score from the existing indicator stack (we want momentum on our side)
  3. Affordability — at least 1 share fits in their capital

Then we filter to "stocks whose estimated 1-month worst-case loss ≤ user's risk
budget" and rank the survivors by trend score. The output is structured so the
template can show a table of fits, plus a section of "near misses" (stocks that
were excluded because they were too volatile, with the reason).

Volatility estimation note: using a 1.65σ "5% worst-case" 1-month proxy is more
conservative than 1σ but less paranoid than 3σ. It maps to "if the past 60 days
of volatility persists, there's roughly a 5% chance of losing more than this
much in a month." This is a back-of-envelope number, not a guarantee.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from . import indicators
from .fetcher import fetch_quote, fetch_history


# Z-score for the lower 5th percentile of a normal distribution
ONE_TAIL_5PCT_Z = 1.645
TRADING_DAYS_PER_MONTH = 21

# Time-frame presets → (label, trading days)
TIMEFRAMES = {
    "1w": {"label": "1 Week", "days": 5},
    "1mo": {"label": "1 Month", "days": 21},
    "3mo": {"label": "3 Months", "days": 63},
    "6mo": {"label": "6 Months", "days": 126},
    "1y": {"label": "1 Year", "days": 252},
}
DEFAULT_TIMEFRAME = "1mo"


def _estimate_downside_pct(closes: pd.Series, horizon_days: int = TRADING_DAYS_PER_MONTH) -> float | None:
    """Return an estimated 5%-worst-case loss over `horizon_days` trading days, in %."""
    if closes is None or len(closes) < 30:
        return None
    rets = closes.pct_change().dropna().tail(60)  # last ~3 months of dailies
    if rets.empty:
        return None
    daily_sigma = float(rets.std())
    if daily_sigma == 0:
        return 0.0
    horizon_sigma = daily_sigma * math.sqrt(horizon_days)
    return horizon_sigma * ONE_TAIL_5PCT_Z * 100  # express as %


# Back-compat alias
_estimate_monthly_downside_pct = _estimate_downside_pct


def _analyse_one(symbol: dict, horizon_days: int = TRADING_DAYS_PER_MONTH) -> dict | None:
    ticker = symbol["ticker"]
    name = symbol["name"]
    quote = fetch_quote(ticker)
    bars = fetch_history(ticker, period="6mo", interval="1d")
    if not quote or not bars:
        return None
    df = pd.DataFrame(bars).rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })
    ind = indicators.compute_all(df)
    if not ind:
        return None
    closes = df["Close"].astype(float)
    downside_pct = _estimate_downside_pct(closes, horizon_days)
    if downside_pct is None:
        return None

    # Recent trailing return matching the selected horizon (for context)
    if len(closes) > horizon_days:
        trailing_return = (closes.iloc[-1] / closes.iloc[-horizon_days - 1] - 1) * 100
    else:
        trailing_return = None

    return {
        "ticker": ticker,
        "name": name,
        "price": quote["price"],
        "change_pct": quote["change_pct"],
        "downside_pct": round(downside_pct, 2),
        "trend_score": ind.get("score", 0),
        "verdict": ind.get("verdict", "NEUTRAL"),
        "rsi": round(ind.get("rsi") or 50, 1),
        "one_month_return": round(trailing_return, 2) if trailing_return is not None else None,
    }


def size_single_stock(ticker: str, amount: float, risk_pct: float,
                      timeframe: str = DEFAULT_TIMEFRAME) -> dict | None:
    """
    Per-stock position sizer for the analysis page.

    Translates "I want to put ₹X into THIS stock and won't tolerate more than Y% loss"
    into a concrete plan: how many shares fit, what the estimated 1-month worst-case
    loss is, whether the stock fits the user's tolerance, and (if not) what the
    largest position size that *would* fit looks like.
    """
    if amount <= 0 or risk_pct <= 0:
        return None

    tf_spec = TIMEFRAMES.get(timeframe, TIMEFRAMES[DEFAULT_TIMEFRAME])
    horizon_days = tf_spec["days"]
    tf_label = tf_spec["label"]

    quote = fetch_quote(ticker)
    bars = fetch_history(ticker, period="6mo", interval="1d")
    if not quote or not bars:
        return None

    df = pd.DataFrame(bars).rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })
    closes = df["Close"].astype(float)
    downside_pct = _estimate_downside_pct(closes, horizon_days)
    if downside_pct is None:
        return None

    price = quote["price"]
    if price > amount:
        return {
            "ok": False,
            "reason": "unaffordable",
            "price": price,
            "downside_pct": round(downside_pct, 2),
            "explanation": (
                f"One share of {ticker} costs ₹{price:,.2f}, which exceeds your ₹{amount:,.0f} "
                f"budget. You'd need at least ₹{price:,.0f} to buy a single share."
            ),
        }

    units = int(amount // price)
    deployed = units * price
    leftover = amount - deployed
    expected_loss_rs = deployed * (downside_pct / 100)
    expected_loss_pct_of_capital = (expected_loss_rs / amount) * 100
    fits_risk = expected_loss_pct_of_capital <= risk_pct

    # If it doesn't fit, compute the largest sub-position that would fit the risk budget
    safe_units = None
    safe_capital = None
    if not fits_risk and downside_pct > 0:
        max_safe_capital = (amount * risk_pct / 100) / (downside_pct / 100)
        safe_units = int(max_safe_capital // price)
        safe_capital = safe_units * price

    if fits_risk:
        verdict = "FITS"
        verdict_text = (
            f"₹{amount:,.0f} buys {units} shares at ₹{price:,.2f} each, deploying ₹{deployed:,.0f}. "
            f"Based on the last 60 days of volatility, a rough {tf_label.lower()} worst-case loss is "
            f"~₹{expected_loss_rs:,.0f} ({expected_loss_pct_of_capital:.1f}% of your capital) — "
            f"comfortably within your {risk_pct}% tolerance. Go ahead."
        )
    elif safe_units and safe_units > 0:
        verdict = "TOO BIG"
        verdict_text = (
            f"At {units} shares (₹{deployed:,.0f}), the estimated {tf_label.lower()} worst-case loss "
            f"(~{expected_loss_pct_of_capital:.1f}% of capital) blows past your {risk_pct}% budget. "
            f"To stay inside your risk budget, cap the position at {safe_units} shares "
            f"(~₹{safe_capital:,.0f}) and keep the rest in cash or safer assets."
        )
    else:
        verdict = "SKIP"
        verdict_text = (
            f"This stock's volatility ({downside_pct:.1f}% estimated {tf_label.lower()} downside) is too high "
            f"for your {risk_pct}% tolerance — even one share would breach the risk budget. "
            f"Look for less-volatile alternatives in the Risk Analyser."
        )

    return {
        "ok": True,
        "ticker": ticker,
        "amount": amount,
        "risk_pct": risk_pct,
        "timeframe": timeframe,
        "timeframe_label": tf_label,
        "price": price,
        "units": units,
        "deployed": deployed,
        "leftover": leftover,
        "downside_pct": round(downside_pct, 2),
        "expected_loss_rs": round(expected_loss_rs, 0),
        "expected_loss_pct": round(expected_loss_pct_of_capital, 2),
        "fits_risk": fits_risk,
        "safe_units": safe_units,
        "safe_capital": safe_capital,
        "verdict": verdict,
        "verdict_text": verdict_text,
    }


def analyse(amount: float, risk_pct: float, universe: list[dict],
            timeframe: str = DEFAULT_TIMEFRAME) -> dict:
    """
    Run the risk screen across the universe and return:
      - "fits": stocks that pass risk + affordability filters, ranked by trend score
      - "rejected_volatility": stocks excluded purely because they're too volatile
      - "rejected_unaffordable": stocks where one share alone exceeds the user's capital
    """
    if amount <= 0 or risk_pct <= 0:
        return {"error": "Need positive amount and risk %"}

    tf_spec = TIMEFRAMES.get(timeframe, TIMEFRAMES[DEFAULT_TIMEFRAME])
    horizon_days = tf_spec["days"]
    tf_label = tf_spec["label"]

    risk_budget_pct = risk_pct  # the user's stated tolerance, in %

    # Fetch + analyse in parallel — fetcher already caches each ticker for 60s
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(lambda s: _analyse_one(s, horizon_days), universe):
            if r is not None:
                results.append(r)

    fits = []
    rejected_vol = []
    rejected_aff = []

    for r in results:
        if r["price"] > amount:
            r["reject_reason"] = (
                f"One share costs ₹{r['price']:,.2f}, which exceeds your ₹{amount:,.0f} capital."
            )
            rejected_aff.append(r)
            continue

        units_affordable = int(amount // r["price"])
        capital_deployed = units_affordable * r["price"]

        # The risk check: does the estimated horizon downside fit the user's budget?
        if r["downside_pct"] > risk_budget_pct:
            r["reject_reason"] = (
                f"Estimated {tf_label.lower()} worst-case loss ({r['downside_pct']:.1f}%) exceeds your "
                f"{risk_budget_pct:.1f}% tolerance."
            )
            rejected_vol.append(r)
            continue

        # Score the fit: prefer high trend score, low downside (slack vs budget), positive momentum
        slack = risk_budget_pct - r["downside_pct"]  # how much headroom under the budget
        fit_score = (r["trend_score"] * 10) + (slack * 0.5) - max(0, r["downside_pct"] - 5)

        r.update({
            "units_affordable": units_affordable,
            "capital_deployed": capital_deployed,
            "leftover": amount - capital_deployed,
            "fit_score": round(fit_score, 1),
            "risk_headroom_pct": round(slack, 2),
        })
        fits.append(r)

    fits.sort(key=lambda x: x["fit_score"], reverse=True)
    rejected_vol.sort(key=lambda x: x["downside_pct"])

    return {
        "amount": amount,
        "risk_pct": risk_pct,
        "timeframe": timeframe,
        "timeframe_label": tf_label,
        "fits": fits,
        "rejected_volatility": rejected_vol,
        "rejected_unaffordable": rejected_aff,
        "universe_size": len(universe),
        "analysed_count": len(results),
        "fit_count": len(fits),
    }
