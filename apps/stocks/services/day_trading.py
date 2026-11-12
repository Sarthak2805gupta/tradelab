"""
Day-trading risk analyser and ranking engine.

Completely different risk model from the swing/long-term Risk Analyser:
  - Holding horizon: hours, not weeks
  - "Risk" = stop-loss distance, not monthly volatility
  - Volatility is a *feature*, not a bug — a stock that doesn't move
    intraday is useless for day trading
  - Liquidity (volume) matters a lot more than it does for long holds

Two public APIs:
  - rank_day_trade_candidates(universe) -> ranked list of stocks
  - size_day_trade(ticker, capital, max_risk_pct) -> per-stock position sizer
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .fetcher import fetch_quote, fetch_history


# ---------- helpers ----------

def _atr_pct(bars: list[dict], period: int = 14) -> float | None:
    """
    Average True Range as a % of current price (Wilder's smoothed ATR).
    This is our proxy for 'how much does this stock typically move in a day'.

    Accuracy: the previous version averaged only the last 14 true ranges with
    equal weight, so a single wild day dropped out of the number abruptly two
    weeks later and the stop-loss distance jumped with it. Wilder's smoothing
    (the standard ATR definition) weights recent days more and decays old
    shocks gradually, which is what every charting platform shows as "ATR".
    """
    if not bars or len(bars) < period + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h = bars[i]["high"]
        l = bars[i]["low"]
        pc = bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period          # seed with a simple average
    for tr in trs[period:]:                   # then Wilder-smooth the rest
        atr = (atr * (period - 1) + tr) / period
    last_close = bars[-1]["close"]
    if not last_close:
        return None
    return (atr / last_close) * 100.0


def _session_fraction_elapsed(now=None) -> float:
    """
    How much of today's NSE session (09:15–15:30 IST) has elapsed, 0..1.
    Returns 1.0 outside market hours / on weekends so a completed day's
    volume is compared against a full-day average.
    """
    from datetime import time as dtime
    from django.utils import timezone
    now = now or timezone.localtime()
    if now.weekday() >= 5:
        return 1.0
    open_t, close_t = dtime(9, 15), dtime(15, 30)
    t = now.time()
    if t <= open_t:
        return 1.0
    if t >= close_t:
        return 1.0
    elapsed = (t.hour * 60 + t.minute) - (open_t.hour * 60 + open_t.minute)
    total = (close_t.hour * 60 + close_t.minute) - (open_t.hour * 60 + open_t.minute)
    # Floor at 10%: the opening minutes carry a disproportionate share of volume.
    return max(0.10, min(1.0, elapsed / total))


def _avg_volume(bars: list[dict], days: int = 20) -> float | None:
    if not bars or len(bars) < days:
        return None
    vols = [b.get("volume", 0) for b in bars[-days:]]
    return sum(vols) / len(vols)


def _intraday_range_pct(quote: dict) -> float | None:
    h = quote.get("day_high")
    l = quote.get("day_low")
    if not h or not l or l == 0:
        return None
    return (h - l) / l * 100.0


def _position_in_range(quote: dict) -> float | None:
    """Where is the current price within today's low-high range? 0.0 = at low, 1.0 = at high."""
    h = quote.get("day_high")
    l = quote.get("day_low")
    p = quote.get("price")
    if not h or not l or not p or h == l:
        return None
    return max(0.0, min(1.0, (p - l) / (h - l)))


# ---------- ranking ----------

def _score_one_candidate(symbol: dict) -> dict | None:
    ticker = symbol["ticker"]
    name = symbol["name"]
    quote = fetch_quote(ticker)
    bars = fetch_history(ticker, period="3mo", interval="1d")
    if not quote or not bars or len(bars) < 15:
        return None

    atr_pct = _atr_pct(bars)
    avg_vol = _avg_volume(bars)
    day_range = _intraday_range_pct(quote)
    range_pos = _position_in_range(quote)

    if atr_pct is None or avg_vol is None:
        return None

    # --- Scoring ---
    score = 5.0
    factors = []

    # ATR sweet spot: 1.5% - 4% is ideal for day trading
    if 1.5 <= atr_pct <= 4.0:
        score += 2.0
        factors.append({"label": f"ATR {atr_pct:.1f}% — ideal intraday volatility", "delta": "+2.0", "positive": True,
            "why": f"This stock typically moves {atr_pct:.1f}% per day — enough to make a profit on a 1:1.5 risk-reward trade, but not so wild that random noise triggers your stop."})
    elif 4.0 < atr_pct <= 6.0:
        score += 1.0
        factors.append({"label": f"ATR {atr_pct:.1f}% — high volatility, sharp moves", "delta": "+1.0", "positive": True,
            "why": f"This stock swings {atr_pct:.1f}% daily — bigger profit targets are possible but you need a wider stop, which means more rupees at risk per share."})
    elif atr_pct > 6.0:
        score -= 0.5
        factors.append({"label": f"ATR {atr_pct:.1f}% — very volatile", "delta": "−0.5", "positive": False,
            "why": f"At {atr_pct:.1f}% daily swings, even a well-placed stop gets triggered by random noise. Day trading this requires very fast reflexes or very wide stops."})
    elif 0.8 <= atr_pct < 1.5:
        score += 0.3
        factors.append({"label": f"ATR {atr_pct:.1f}% — moderate", "delta": "+0.3", "positive": None,
            "why": f"The stock only moves {atr_pct:.1f}% per day — you'll need to nail your entry precisely and accept smaller targets. Works for patient scalpers."})
    else:
        score -= 1.5
        factors.append({"label": f"ATR {atr_pct:.1f}% — too quiet", "delta": "−1.5", "positive": False,
            "why": f"This stock barely moves intraday. After brokerage and slippage, there's almost no profit margin left. Your time is better spent elsewhere."})

    # Liquidity: average 20-day volume
    if avg_vol > 5_000_000:
        score += 2.0
        factors.append({"label": "Very high liquidity", "delta": "+2.0", "positive": True,
            "why": f"Avg daily volume of {avg_vol/1e6:.1f}M shares means the bid-ask spread is razor-thin and you can enter/exit large positions without moving the price."})
    elif avg_vol > 1_000_000:
        score += 1.0
        factors.append({"label": "Good liquidity", "delta": "+1.0", "positive": True,
            "why": f"Avg daily volume of {avg_vol/1e6:.1f}M — enough liquidity for retail-sized positions without significant slippage."})
    elif avg_vol > 200_000:
        factors.append({"label": "Moderate liquidity", "delta": "0", "positive": None,
            "why": "Volume is adequate but not great. You might face wider spreads and slower fills, especially if you're trading larger quantities."})
    else:
        score -= 2.0
        factors.append({"label": "Low liquidity — wide spreads", "delta": "−2.0", "positive": False,
            "why": "Thin volume means wide bid-ask spreads eat into your profit on every trade, and exiting in a hurry can move the price against you."})

    # Today's range vs typical ATR
    if day_range is not None and atr_pct:
        ratio = day_range / atr_pct
        if ratio < 0.5:
            score += 0.8
            factors.append({"label": f"Today's range only {day_range:.1f}% — room for a move", "delta": "+0.8", "positive": True,
                "why": f"The stock has only used {ratio*100:.0f}% of its typical daily range so far. Statistically, there's room for the move to extend — you're not showing up late."})
        elif ratio > 1.3:
            score -= 0.5
            factors.append({"label": f"Today's range {day_range:.1f}% — already exhausted", "delta": "−0.5", "positive": False,
                "why": f"The stock already moved {ratio*100:.0f}% of its typical daily range today. Most of the day's move is likely done — entering now is chasing."})

    # Position in day range
    if range_pos is not None:
        if 0.35 <= range_pos <= 0.65:
            score += 0.5
            factors.append({"label": "Price mid-range — flexible entry", "delta": "+0.5", "positive": True,
                "why": "Price is in the middle of today's range — you can go long or short without being at an extreme. This gives you the most flexibility."})
        elif range_pos < 0.15:
            factors.append({"label": "Price near day low — bounce or breakdown", "delta": "0", "positive": None,
                "why": "Price is near the day's low. Could bounce (buy the dip) or break down further. Wait for a clear signal before committing."})
        elif range_pos > 0.85:
            factors.append({"label": "Price near day high — breakout or rejection", "delta": "0", "positive": None,
                "why": "Price is near the day's high. Could break out to new highs (momentum trade) or get rejected and fall. Watch for confirmation before entry."})

    # Clamp
    score = max(0.0, min(10.0, score))

    # Tier
    if score >= 7.5:
        tier = "PRIME"
        tier_color = "accent"
    elif score >= 5.5:
        tier = "GOOD"
        tier_color = "accent"
    elif score >= 4.0:
        tier = "OK"
        tier_color = "yellow-400"
    else:
        tier = "SKIP"
        tier_color = "danger"

    # Quick directional call from data we already have (no extra API calls)
    chg = quote["change_pct"]
    if chg > 0.5:
        intraday_action = "BUY" if score >= 7 else "LEAN BUY"
        intraday_color = "emerald"
    elif chg < -0.5:
        intraday_action = "SELL" if score >= 7 else "LEAN SELL"
        intraday_color = "rose"
    else:
        intraday_action = "HOLD"
        intraday_color = "amber"

    return {
        "ticker": ticker,
        "name": name,
        "price": quote["price"],
        "change_pct": quote["change_pct"],
        "intraday_action": intraday_action,
        "intraday_color": intraday_color,
        "day_high": quote.get("day_high"),
        "day_low": quote.get("day_low"),
        "volume": quote.get("volume"),
        "avg_volume": int(avg_vol) if avg_vol else None,
        "atr_pct": round(atr_pct, 2),
        "day_range_pct": round(day_range, 2) if day_range else None,
        "range_position": round(range_pos * 100, 0) if range_pos is not None else None,
        "score": round(score, 1),
        "tier": tier,
        "tier_color": tier_color,
        "factors": factors,
    }


def rank_day_trade_candidates(universe: list[dict]) -> list[dict]:
    """Score every stock in the universe and return ranked by score (desc)."""
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(_score_one_candidate, universe):
            if r is not None:
                results.append(r)
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ---------- per-stock position sizer ----------

def intraday_verdict(ticker: str, quote: dict | None = None, bars: list | None = None) -> dict | None:
    """
    Quick Buy / Sell / Hold verdict for the active ticker on the live desk.
    Accepts pre-fetched quote/bars to avoid duplicate yfinance calls.
    """
    if quote is None:
        quote = fetch_quote(ticker)
    if bars is None:
        bars = fetch_history(ticker, period="3mo", interval="1d")
    if not quote:
        return None

    day_range = _intraday_range_pct(quote)
    range_pos = _position_in_range(quote)

    price = quote["price"]
    change_pct = quote.get("change_pct", 0)
    has_bars = bars and len(bars) >= 15

    # SMAs from history (only if bars are cached — never blocks on yfinance)
    sma5 = sma20 = None
    avg_vol = None
    if has_bars:
        closes = [b["close"] for b in bars[-5:]]
        sma5 = sum(closes) / len(closes)
        closes_20 = [b["close"] for b in bars[-20:]]
        sma20 = sum(closes_20) / len(closes_20)
        avg_vol = _avg_volume(bars)

    # Build verdict
    signals_bull = 0
    signals_bear = 0
    reasons = []

    # 1. Price vs short-term average (only if history is cached)
    if sma5 is not None:
        if price > sma5 * 1.005:
            signals_bull += 1
            reasons.append("Price is above the 5-day average — short-term buyers are in control.")
        elif price < sma5 * 0.995:
            signals_bear += 1
            reasons.append("Price is below the 5-day average — short-term sellers have the upper hand.")
        else:
            reasons.append("Price is right at its 5-day average — no short-term edge either way.")

    # 2. Price vs 20-day average (only if history is cached)
    if sma20 is not None:
        if price > sma20 * 1.01:
            signals_bull += 1
            reasons.append("Trading above the 20-day average — the intermediate trend supports going long.")
        elif price < sma20 * 0.99:
            signals_bear += 1
            reasons.append("Trading below the 20-day average — the intermediate trend favours sellers.")

    # 3. Today's direction
    if change_pct > 0.5:
        signals_bull += 1
        reasons.append(f"Up {change_pct:+.1f}% today — intraday momentum is with the buyers.")
    elif change_pct < -0.5:
        signals_bear += 1
        reasons.append(f"Down {change_pct:+.1f}% today — intraday momentum is with the sellers.")
    else:
        reasons.append(f"Flat today ({change_pct:+.1f}%) — no clear intraday direction yet.")

    # 4. Position in day range
    if range_pos is not None:
        if range_pos > 0.75:
            signals_bull += 1
            reasons.append("Price is near the day's high — strength into the close is typically bullish.")
        elif range_pos < 0.25:
            signals_bear += 1
            reasons.append("Price is near the day's low — weakness suggests sellers are pressing.")

    # 5. Volume check (only if we have average volume from history).
    # Accuracy: mid-session the day's volume is only partially printed, so it
    # was being compared against a full-day average and almost always read as
    # "below average" before lunch. Compare against the volume expected so far.
    today_vol = quote.get("volume", 0)
    expected_so_far = avg_vol * _session_fraction_elapsed() if avg_vol else None
    if expected_so_far and today_vol and today_vol > expected_so_far * 1.3:
        reasons.append(f"Volume is {today_vol/expected_so_far:.1f}x the average pace — the move has institutional conviction behind it.")
    elif expected_so_far and today_vol < expected_so_far * 0.5:
        reasons.append("Volume is below average pace — any move today lacks conviction and could reverse easily.")

    # Verdict
    net = signals_bull - signals_bear
    if net >= 2:
        action = "BUY"
        action_color = "emerald"
        summary = "Multiple signals point up — short-term momentum, price structure, and today's action all favour buyers."
    elif net == 1:
        action = "LEAN BUY"
        action_color = "emerald"
        summary = "Slightly more signals are bullish than bearish, but it's not a slam dunk. Consider a smaller position or wait for confirmation."
    elif net <= -2:
        action = "SELL"
        action_color = "rose"
        summary = "Multiple signals point down — short-term trend, intraday action, and price structure all favour sellers or staying out."
    elif net == -1:
        action = "LEAN SELL"
        action_color = "rose"
        summary = "Slightly more signals are bearish. Either short if your broker supports it, or stay on the sidelines."
    else:
        action = "HOLD"
        action_color = "amber"
        summary = "Signals are evenly split — no clear edge for either direction. Sit tight and wait for a cleaner setup."

    return {
        "action": action,
        "action_color": action_color,
        "summary": summary,
        "reasons": reasons,
        "signals_bull": signals_bull,
        "signals_bear": signals_bear,
        "net": net,
    }


def size_day_trade(ticker: str, capital: float, max_risk_pct: float) -> dict | None:
    """
    Day-trading position sizer.

    The model:
      - Stop-loss distance = 1 × ATR (typical day-trader convention)
      - Max loss per trade = capital × max_risk_pct% (e.g. 2% of ₹1L = ₹2000)
      - Shares = floor(max_loss / (price × stop_pct))
      - Position value must still fit inside total capital
    """
    if capital <= 0 or max_risk_pct <= 0:
        return None

    quote = fetch_quote(ticker)
    bars = fetch_history(ticker, period="3mo", interval="1d")
    if not quote or not bars or len(bars) < 15:
        return None

    atr_pct = _atr_pct(bars)
    if not atr_pct:
        return None

    price = quote["price"]
    stop_distance_rs = price * (atr_pct / 100.0)  # rupees per share
    stop_price = price - stop_distance_rs
    target_price = price + (stop_distance_rs * 1.5)  # 1.5:1 reward:risk target

    risk_budget = capital * (max_risk_pct / 100.0)  # max rupees we can lose on this trade
    shares_by_risk = int(risk_budget // stop_distance_rs) if stop_distance_rs > 0 else 0
    shares_by_capital = int(capital // price) if price > 0 else 0
    shares = min(shares_by_risk, shares_by_capital)

    if shares < 1:
        return {
            "ok": False,
            "reason": "unaffordable_or_too_risky",
            "price": price,
            "atr_pct": round(atr_pct, 2),
            "stop_distance_rs": round(stop_distance_rs, 2),
            "explanation": (
                f"At ₹{price:,.2f} per share with an ATR-based stop of ₹{stop_distance_rs:,.2f}, "
                f"you can't fit even one share within your ₹{risk_budget:,.0f} risk budget "
                f"({max_risk_pct}% of ₹{capital:,.0f}). Either raise your risk tolerance, pick a less "
                f"volatile stock, or wait until capital is higher."
            ),
        }

    position_value = shares * price
    max_loss_rs = shares * stop_distance_rs
    max_loss_pct_of_capital = (max_loss_rs / capital) * 100
    target_profit_rs = shares * (target_price - price)

    # Sanity: the stop hit the risk-budget cap first?
    constrained_by = "risk" if shares_by_risk < shares_by_capital else "capital"

    return {
        "ok": True,
        "ticker": ticker,
        "price": price,
        "atr_pct": round(atr_pct, 2),
        "capital": capital,
        "max_risk_pct": max_risk_pct,
        "risk_budget_rs": round(risk_budget, 0),
        "shares": shares,
        "position_value": round(position_value, 0),
        "stop_price": round(stop_price, 2),
        "stop_distance_rs": round(stop_distance_rs, 2),
        "stop_distance_pct": round(atr_pct, 2),
        "target_price": round(target_price, 2),
        "target_profit_rs": round(target_profit_rs, 0),
        "max_loss_rs": round(max_loss_rs, 0),
        "max_loss_pct_of_capital": round(max_loss_pct_of_capital, 2),
        "reward_risk_ratio": 1.5,
        "constrained_by": constrained_by,
        "explanation": (
            f"Buy **{shares} shares** at ₹{price:,.2f} (total ₹{position_value:,.0f}). "
            f"Place your stop-loss at ₹{stop_price:,.2f} — that's 1 ATR ({atr_pct:.1f}%) below entry, "
            f"which is where the stock would breach its typical daily range. If hit, you lose "
            f"₹{max_loss_rs:,.0f} ({max_loss_pct_of_capital:.2f}% of capital). Target "
            f"₹{target_price:,.2f} for ~₹{target_profit_rs:,.0f} profit — that's a 1.5:1 "
            f"reward:risk trade, the minimum worth taking for day trading."
        ),
    }
