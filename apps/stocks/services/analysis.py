"""
Analysis engine: pulls history via the fetcher, runs indicators,
and produces a structured plain-English report for the /analysis page.
"""
from __future__ import annotations

import pandas as pd

from . import indicators, financials as financials_svc
from .fetcher import fetch_quote, fetch_history, fetch_fundamentals


def _history_df(ticker: str) -> pd.DataFrame:
    bars = fetch_history(ticker, period="1y", interval="1d")
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
    return df


def analyze(ticker: str) -> dict:
    quote = fetch_quote(ticker)
    fundamentals = fetch_fundamentals(ticker)
    df = _history_df(ticker)

    if df.empty or quote is None:
        return {
            "ticker": ticker,
            "ok": False,
            "error": (
                f"Couldn't fetch data for {ticker}. This could mean the symbol doesn't exist, "
                f"the stock is delisted, or yfinance is temporarily rate-limited. "
                f"Try again in 30 seconds, or check the spelling."
            ),
        }

    ind = indicators.compute_all(df)

    # Trend from SMA stack
    if ind["sma20"] and ind["sma50"]:
        if ind["sma20"] > ind["sma50"] * 1.01:
            trend = "Uptrend"
        elif ind["sma20"] < ind["sma50"] * 0.99:
            trend = "Downtrend"
        else:
            trend = "Sideways"
    else:
        trend = "Sideways"

    # Momentum from RSI
    rsi_v = ind.get("rsi") or 50
    if rsi_v > 65:
        momentum = "Strong"
    elif rsi_v < 35:
        momentum = "Weak"
    else:
        momentum = "Neutral"

    # Risk: distance from 52w high/low + ATR-ish proxy via BB width
    bb_width = 0.0
    if ind.get("bb_upper") and ind.get("bb_lower") and ind.get("close"):
        bb_width = (ind["bb_upper"] - ind["bb_lower"]) / ind["close"]
    if bb_width > 0.15:
        risk = "High"
    elif bb_width > 0.07:
        risk = "Medium"
    else:
        risk = "Low"

    # Action from verdict + risk
    verdict = ind.get("verdict", "NEUTRAL")
    if verdict == "BULLISH" and risk != "High":
        action = "Buy"
    elif verdict == "BEARISH":
        action = "Avoid"
    else:
        action = "Watch"

    reasons = []
    if ind["sma20"] and ind["sma50"]:
        if ind["sma20"] > ind["sma50"]:
            reasons.append(
                f"Recent prices (last ~1 month avg ₹{ind['sma20']:,.2f}) are running "
                f"above the longer-term average (₹{ind['sma50']:,.2f}) — buyers have been in control lately."
            )
        else:
            reasons.append(
                f"Recent prices (last ~1 month avg ₹{ind['sma20']:,.2f}) are running "
                f"below the longer-term average (₹{ind['sma50']:,.2f}) — the stock has been cooling off."
            )

    if rsi_v > 65:
        rsi_plain = "looking overheated, buyers may be tiring"
    elif rsi_v < 35:
        rsi_plain = "looking oversold, sellers may be exhausted"
    else:
        rsi_plain = "sitting in a balanced zone, no extreme either way"
    reasons.append(f"Momentum gauge reads {rsi_v:.0f} out of 100 — {rsi_plain}.")

    if ind.get("macd") is not None and ind.get("macd_signal") is not None:
        if ind["macd"] > ind["macd_signal"]:
            reasons.append("Trend strength is picking up — momentum is shifting in the buyers' favour.")
        else:
            reasons.append("Trend strength is fading — momentum is leaning toward sellers right now.")

    if ind.get("support") and ind.get("resistance"):
        reasons.append(
            f"Over the last month it has bounced between ₹{ind['support']:,.2f} (floor it keeps holding) "
            f"and ₹{ind['resistance']:,.2f} (ceiling it keeps hitting)."
        )

    confidence = min(100, abs(ind.get("score", 0)) * 25 + 25)

    financials_block = financials_svc.get_financials(ticker)
    company_profile = financials_svc.get_company_profile(ticker)
    buy_rating = _compute_buy_rating(ind, financials_block, rsi_v, fundamentals=fundamentals)

    return {
        "ok": True,
        "ticker": ticker,
        "name": fundamentals.get("long_name") or ticker,
        "quote": quote,
        "fundamentals": fundamentals,
        "indicators": ind,
        "trend": trend,
        "momentum": momentum,
        "risk": risk,
        "action": action,
        "confidence": confidence,
        "reasons": reasons,
        "financials": financials_block,
        "profile": company_profile,
        "buy_rating": buy_rating,
    }


# Sector median benchmarks for relative valuation scoring
# Source: rough Indian market medians as of 2025-2026
SECTOR_BENCHMARKS = {
    "technology":          {"pe": 22, "pb": 5.0, "roe": 0.25, "de": 15},
    "financial services":  {"pe": 15, "pb": 2.0, "roe": 0.14, "de": None},  # banks have no debt/equity
    "energy":              {"pe": 12, "pb": 1.5, "roe": 0.12, "de": 50},
    "consumer defensive":  {"pe": 30, "pb": 8.0, "roe": 0.25, "de": 20},
    "consumer cyclical":   {"pe": 25, "pb": 4.0, "roe": 0.15, "de": 40},
    "healthcare":          {"pe": 25, "pb": 4.0, "roe": 0.18, "de": 20},
    "industrials":         {"pe": 20, "pb": 3.0, "roe": 0.15, "de": 50},
    "basic materials":     {"pe": 12, "pb": 1.5, "roe": 0.12, "de": 40},
    "communication services": {"pe": 20, "pb": 3.0, "roe": 0.15, "de": 30},
    "real estate":         {"pe": 25, "pb": 2.5, "roe": 0.10, "de": 60},
    "utilities":           {"pe": 15, "pb": 2.0, "roe": 0.12, "de": 80},
}
DEFAULT_BENCHMARK = {"pe": 20, "pb": 3.0, "roe": 0.15, "de": 40}


def _compute_buy_rating(ind: dict, fin: dict | None, rsi_v: float, fundamentals: dict | None = None) -> dict:
    """
    Produce a 0-10 "should I buy this?" score. Purely additive from 0 — the stock
    earns points for what's actually good about it. No arbitrary baseline.

    10 points available across 4 categories:
      - Technicals (0-3):  trend, MACD, volatility
      - Momentum (0-2):    RSI zone
      - Fundamentals (0-3): strengths minus concerns
      - Growth (0-2):      revenue trajectory

    A stock with nothing going for it gets 0. A stock where everything is perfect
    gets 10. Most stocks land between 3-7.

    Categories (max 10):
      - Technicals  (0-2.5): trend + MACD + volatility
      - Momentum    (0-2):   RSI zone
      - Fundamentals(0-2.5): strengths - concerns
      - Valuation   (0-1.5): PE/ROE relative to sector
      - Growth      (0-1.5): revenue trajectory
    """
    score = 0.0
    factors = []
    sub_scores = {}  # category -> earned points for the radar chart

    # === TECHNICALS (0-2.5 points) ===
    tech_earned = 0
    trend_score = ind.get("score", 0) if ind else 0

    # Trend: 0-1.5
    if trend_score >= 2:
        t = 1.5
        factors.append({"label": "Strong trend", "pts": "1.5 / 1.5", "positive": True, "cat": "Technicals",
            "why": "All trend indicators agree — price climbing on all timeframes."})
    elif trend_score == 1:
        t = 1.0
        factors.append({"label": "Mild uptrend", "pts": "1 / 1.5", "positive": True, "cat": "Technicals",
            "why": "Most indicators point up. Trend favours buyers, just not strongly."})
    elif trend_score == 0:
        t = 0.75
        factors.append({"label": "No clear trend", "pts": "0.75 / 1.5", "positive": None, "cat": "Technicals",
            "why": "Signals cancel out. Stock is drifting sideways."})
    elif trend_score == -1:
        t = 0.3
        factors.append({"label": "Mild downtrend", "pts": "0.3 / 1.5", "positive": False, "cat": "Technicals",
            "why": "More indicators point down. Momentum working against buyers."})
    else:
        t = 0
        factors.append({"label": "Strong downtrend", "pts": "0 / 1.5", "positive": False, "cat": "Technicals",
            "why": "Every indicator is negative. Buying here is catching a falling knife."})
    tech_earned += t

    # MACD: 0-0.5
    if ind and ind.get("macd") is not None and ind.get("macd_signal") is not None:
        if ind["macd"] > ind["macd_signal"]:
            tech_earned += 0.5
            factors.append({"label": "MACD positive", "pts": "0.5 / 0.5", "positive": True, "cat": "Technicals",
                "why": "Short-term momentum just turned positive."})
        else:
            factors.append({"label": "MACD negative", "pts": "0 / 0.5", "positive": False, "cat": "Technicals",
                "why": "Momentum is fading — rally losing steam."})

    # Volatility: 0-0.5
    if ind:
        close = ind.get("close") or 0
        bb_up = ind.get("bb_upper") or 0
        bb_lo = ind.get("bb_lower") or 0
        if close and bb_up and bb_lo:
            bb_w = (bb_up - bb_lo) / close
            if bb_w < 0.07:
                tech_earned += 0.5
                factors.append({"label": "Low volatility", "pts": "0.5 / 0.5", "positive": True, "cat": "Technicals",
                    "why": "Tight Bollinger Bands — calm stock, tight stop-loss possible."})
            elif bb_w < 0.12:
                tech_earned += 0.25
                factors.append({"label": "Normal volatility", "pts": "0.25 / 0.5", "positive": None, "cat": "Technicals",
                    "why": "Average price swings. Standard risk."})
            else:
                factors.append({"label": "High volatility", "pts": "0 / 0.5", "positive": False, "cat": "Technicals",
                    "why": "Wide swings — stop-loss must be far, more rupees at risk."})

    score += tech_earned
    sub_scores["Technicals"] = {"earned": round(tech_earned, 2), "max": 2.5}

    # === MOMENTUM (0-2 points) ===
    if 50 <= rsi_v <= 65:
        m = 2.0
        factors.append({"label": f"RSI {rsi_v:.0f} — ideal", "pts": "2 / 2", "positive": True, "cat": "Momentum",
            "why": f"Buyers in control, not overextended. Sweet spot for entry."})
    elif 40 <= rsi_v < 50:
        m = 1.0
        factors.append({"label": f"RSI {rsi_v:.0f} — neutral", "pts": "1 / 2", "positive": None, "cat": "Momentum",
            "why": "Neither side dominates. Could go either way."})
    elif 65 < rsi_v <= 75:
        m = 1.0
        factors.append({"label": f"RSI {rsi_v:.0f} — stretched", "pts": "1 / 2", "positive": None, "cat": "Momentum",
            "why": "Strong but getting extended. Pullback wouldn't surprise."})
    elif rsi_v > 75:
        m = 0.0
        factors.append({"label": f"RSI {rsi_v:.0f} — overbought", "pts": "0 / 2", "positive": False, "cat": "Momentum",
            "why": "Rally overheated. Pullback statistically overdue."})
    elif 30 <= rsi_v < 40:
        m = 0.5
        factors.append({"label": f"RSI {rsi_v:.0f} — weak", "pts": "0.5 / 2", "positive": None, "cat": "Momentum",
            "why": "Weak but could bounce. Oversold is a setup, not a guarantee."})
    else:
        m = 0.0
        factors.append({"label": f"RSI {rsi_v:.0f} — oversold", "pts": "0 / 2", "positive": False, "cat": "Momentum",
            "why": "Extreme selling. Contrarian opportunity or value trap."})
    score += m
    sub_scores["Momentum"] = {"earned": round(m, 2), "max": 2}

    # === FUNDAMENTALS (0-2.5 points) ===
    fund_earned = 0
    n_str = len(fin["strengths"]) if fin and fin.get("strengths") else 0
    n_con = len(fin["concerns"]) if fin and fin.get("concerns") else 0

    if fin:
        str_pts = min(1.5, n_str * 0.4)
        fund_earned += str_pts
        if n_str > 0:
            factors.append({"label": f"{n_str} strength{'s' if n_str != 1 else ''}", "pts": f"{str_pts:.1f} / 1.5", "positive": True, "cat": "Fundamentals",
                "why": "Healthy business — good margins, ROE, or low debt."})
        else:
            factors.append({"label": "No strengths", "pts": "0 / 1.5", "positive": False, "cat": "Fundamentals",
                "why": "No fundamental metrics stand out positively."})

        con_pen = min(1.0, n_con * 0.5)
        clean = max(0.0, 1.0 - con_pen)
        fund_earned += clean
        if n_con == 0:
            factors.append({"label": "No red flags", "pts": "1 / 1", "positive": True, "cat": "Fundamentals",
                "why": "Clean financials — no concerning metrics found."})
        else:
            factors.append({"label": f"{n_con} concern{'s' if n_con != 1 else ''}", "pts": f"{clean:.1f} / 1", "positive": False if con_pen >= 0.5 else None, "cat": "Fundamentals",
                "why": "Red flags — thin margins, high PE, or heavy debt."})
    else:
        fund_earned = 1.25
        factors.append({"label": "No data", "pts": "1.25 / 2.5", "positive": None, "cat": "Fundamentals",
            "why": "No income statement available (ETF/futures)."})

    score += fund_earned
    sub_scores["Fundamentals"] = {"earned": round(fund_earned, 2), "max": 2.5}

    # === VALUATION — sector-relative (0-1.5 points) ===
    val_earned = 0
    sector = ((fundamentals or {}).get("sector") or "").lower()
    bench = SECTOR_BENCHMARKS.get(sector, DEFAULT_BENCHMARK)
    snap = fin.get("snapshot", {}) if fin else {}

    pe = snap.get("trailing_pe")
    roe = snap.get("roe")

    if pe and bench["pe"]:
        pe_ratio = pe / bench["pe"]
        if pe_ratio < 0.7:
            val_earned += 0.75
            factors.append({"label": f"PE {pe:.0f} — cheap vs sector ({bench['pe']})", "pts": "0.75 / 0.75", "positive": True, "cat": "Valuation",
                "why": f"Trading at {pe:.0f}x earnings vs sector median {bench['pe']}x. Undervalued relative to peers."})
        elif pe_ratio < 1.1:
            val_earned += 0.5
            factors.append({"label": f"PE {pe:.0f} — fair vs sector ({bench['pe']})", "pts": "0.5 / 0.75", "positive": None, "cat": "Valuation",
                "why": f"PE of {pe:.0f}x is in line with sector median {bench['pe']}x. Fair value."})
        elif pe_ratio < 1.5:
            val_earned += 0.2
            factors.append({"label": f"PE {pe:.0f} — pricey vs sector ({bench['pe']})", "pts": "0.2 / 0.75", "positive": False, "cat": "Valuation",
                "why": f"PE of {pe:.0f}x is above sector median {bench['pe']}x. Paying a premium — needs growth to justify."})
        else:
            factors.append({"label": f"PE {pe:.0f} — expensive vs sector ({bench['pe']})", "pts": "0 / 0.75", "positive": False, "cat": "Valuation",
                "why": f"PE of {pe:.0f}x is well above sector median {bench['pe']}x. Overvalued unless growth is exceptional."})
    else:
        val_earned += 0.35
        factors.append({"label": "PE unavailable", "pts": "0.35 / 0.75", "positive": None, "cat": "Valuation",
            "why": "Can't assess PE valuation. Neutral."})

    if roe is not None and bench.get("roe"):
        roe_pct = roe * 100
        bench_roe = bench["roe"] * 100
        if roe > bench["roe"] * 1.3:
            val_earned += 0.75
            factors.append({"label": f"ROE {roe_pct:.0f}% — above sector ({bench_roe:.0f}%)", "pts": "0.75 / 0.75", "positive": True, "cat": "Valuation",
                "why": f"Return on equity of {roe_pct:.0f}% beats sector median {bench_roe:.0f}%. Capital compounding efficiently."})
        elif roe > bench["roe"] * 0.8:
            val_earned += 0.4
            factors.append({"label": f"ROE {roe_pct:.0f}% — in line ({bench_roe:.0f}%)", "pts": "0.4 / 0.75", "positive": None, "cat": "Valuation",
                "why": f"ROE of {roe_pct:.0f}% is close to sector median {bench_roe:.0f}%. Adequate."})
        else:
            factors.append({"label": f"ROE {roe_pct:.0f}% — below sector ({bench_roe:.0f}%)", "pts": "0 / 0.75", "positive": False, "cat": "Valuation",
                "why": f"ROE of {roe_pct:.0f}% trails sector median {bench_roe:.0f}%. Capital not working hard enough."})
    else:
        val_earned += 0.35
        factors.append({"label": "ROE unavailable", "pts": "0.35 / 0.75", "positive": None, "cat": "Valuation",
            "why": "Can't assess return on equity. Neutral."})

    score += val_earned
    sub_scores["Valuation"] = {"earned": round(val_earned, 2), "max": 1.5}

    # === GROWTH (0-1.5 points) ===
    growth_earned = 0
    if fin and fin.get("yoy_revenue_pct") is not None:
        yoy = fin["yoy_revenue_pct"]
        if yoy > 20:
            growth_earned = 1.5
            factors.append({"label": f"Rev {yoy:+.0f}% Y/Y", "pts": "1.5 / 1.5", "positive": True, "cat": "Growth",
                "why": "20%+ revenue growth. Genuine expansion."})
        elif yoy > 10:
            growth_earned = 1.2
            factors.append({"label": f"Rev {yoy:+.0f}% Y/Y", "pts": "1.2 / 1.5", "positive": True, "cat": "Growth",
                "why": "Solid double-digit growth."})
        elif yoy > 0:
            growth_earned = 0.75
            factors.append({"label": f"Rev {yoy:+.0f}% Y/Y", "pts": "0.75 / 1.5", "positive": None, "cat": "Growth",
                "why": "Growing but slowly. Barely above inflation."})
        elif yoy > -5:
            growth_earned = 0.3
            factors.append({"label": f"Rev flat ({yoy:+.0f}%)", "pts": "0.3 / 1.5", "positive": None, "cat": "Growth",
                "why": "Stagnant revenue. Yellow flag."})
        else:
            factors.append({"label": f"Rev {yoy:+.0f}% Y/Y", "pts": "0 / 1.5", "positive": False, "cat": "Growth",
                "why": "Revenue shrinking. Serious red flag."})
    elif fin:
        growth_earned = 0.75
        factors.append({"label": "Data incomplete", "pts": "0.75 / 1.5", "positive": None, "cat": "Growth",
            "why": "Can't compute Y/Y growth. Neutral."})
    else:
        growth_earned = 0.75
        factors.append({"label": "No data", "pts": "0.75 / 1.5", "positive": None, "cat": "Growth",
            "why": "No income statement. Neutral."})

    score += growth_earned
    sub_scores["Growth"] = {"earned": round(growth_earned, 2), "max": 1.5}

    # Clamp to [0, 10]
    score = max(0.0, min(10.0, score))
    rounded = round(score, 1)

    # Tier
    if rounded >= 8.0:
        tier = "STRONG BUY"
        tier_color = "accent"
        tier_description = "High-conviction setup. Technicals and fundamentals both line up in your favour."
    elif rounded >= 6.5:
        tier = "BUY"
        tier_color = "accent"
        tier_description = "Above-average opportunity. Worth a position, but size sensibly."
    elif rounded >= 5.0:
        tier = "HOLD / WATCH"
        tier_color = "yellow-400"
        tier_description = "Mixed signals. Existing holders can hold; new buyers should wait for a clearer setup."
    elif rounded >= 3.5:
        tier = "AVOID"
        tier_color = "yellow-400"
        tier_description = "Red flags outweigh the positives right now. Sit this one out unless you have a strong thesis."
    else:
        tier = "STRONG AVOID"
        tier_color = "danger"
        tier_description = "Multiple serious concerns. Not a good entry point for most investors."

    return {
        "score": rounded,
        "score_int": int(round(rounded)),
        "tier": tier,
        "tier_color": tier_color,
        "tier_description": tier_description,
        "factors": factors,
        "sub_scores": sub_scores,
    }
