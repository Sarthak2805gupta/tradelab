"""
Long-term commodities desk: lets users compare ETF exposure vs Futures exposure
for the same underlying metal/commodity, and produces a plain-English verdict
aimed at retail investors thinking in months/years rather than days.

The framing is opinionated on purpose: for a long-term retail holder, an ETF is
almost always the right answer. The job of this module is to *show the reasoning*
so the user understands why, and to flag the cases where futures are the only
available route (because no liquid Indian ETF exists for the commodity).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import indicators
from .fetcher import fetch_quote, fetch_history


COMMODITIES = [
    {
        "key": "gold",
        "name": "Gold",
        "emoji": "🥇",
        "etf": {
            "ticker": "GOLDBEES.NS",
            "name": "Nippon India Gold BeES",
            "expense_ratio": 0.82,
        },
        "futures": {
            "ticker": "GC=F",
            "name": "COMEX Gold Futures",
            "lot_size": 100,
            "unit": "troy oz",
        },
        "thesis": (
            "Gold is the classic inflation hedge and crisis store of value. Indian "
            "households already hold roughly 25,000 tonnes of physical gold — owning a "
            "gold ETF is the digital version of that, with no purity, storage, locker, "
            "or making-charge worries. Long-term it tracks INR depreciation + global "
            "real-rate moves."
        ),
    },
    {
        "key": "silver",
        "name": "Silver",
        "emoji": "🥈",
        "etf": {
            "ticker": "SILVERBEES.NS",
            "name": "Nippon India Silver ETF",
            "expense_ratio": 0.50,
        },
        "futures": {
            "ticker": "SI=F",
            "name": "COMEX Silver Futures",
            "lot_size": 5000,
            "unit": "troy oz",
        },
        "thesis": (
            "Silver is half precious metal, half industrial commodity — solar panels, "
            "EV wiring, and electronics drive structural demand. It moves with gold but "
            "is roughly twice as volatile, so it rewards patience and punishes leverage."
        ),
    },
    {
        "key": "copper",
        "name": "Copper",
        "emoji": "🟫",
        "etf": None,
        "futures": {
            "ticker": "HG=F",
            "name": "COMEX Copper Futures",
            "lot_size": 25000,
            "unit": "lbs",
        },
        "thesis": (
            "Copper is the bellwether of global industrial activity — nicknamed "
            "'Dr. Copper' because its price often forecasts the world economy. There is "
            "no clean Indian copper ETF, so retail exposure means MCX copper futures or "
            "going indirect via copper-mining and cables-and-wires equities."
        ),
    },
    {
        "key": "crude",
        "name": "Crude Oil",
        "emoji": "🛢️",
        "etf": None,
        "futures": {
            "ticker": "CL=F",
            "name": "NYMEX WTI Crude Futures",
            "lot_size": 100,
            "unit": "barrels",
        },
        "thesis": (
            "Crude is geopolitically volatile and India imports ~85% of its oil — a "
            "rising crude price hurts the rupee, inflation, and downstream industries. "
            "There is no liquid Indian crude ETF, so direct exposure is futures-only. "
            "Most retail investors should get crude exposure indirectly via oil-marketing "
            "companies or upstream producers."
        ),
    },
]


# ---------- internal helpers ----------

def _trend_block(ticker: str) -> dict:
    """Run the same indicator stack used for equities and return a small summary."""
    bars = fetch_history(ticker, period="1y", interval="1d")
    if not bars:
        return {"available": False}
    df = pd.DataFrame(bars).rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })
    ind = indicators.compute_all(df)
    if not ind:
        return {"available": False}

    sma20 = ind.get("sma20") or 0
    sma50 = ind.get("sma50") or 0
    rsi = ind.get("rsi") or 50
    bb_upper = ind.get("bb_upper") or 0
    bb_lower = ind.get("bb_lower") or 0
    close = ind.get("close") or 0

    if sma20 and sma50:
        if sma20 > sma50 * 1.02:
            trend = "Uptrend"
        elif sma20 < sma50 * 0.98:
            trend = "Downtrend"
        else:
            trend = "Sideways"
    else:
        trend = "Unknown"

    bb_width = ((bb_upper - bb_lower) / close) if (bb_upper and bb_lower and close) else 0
    if bb_width > 0.15:
        volatility = "High"
    elif bb_width > 0.07:
        volatility = "Medium"
    else:
        volatility = "Low"

    return {
        "available": True,
        "trend": trend,
        "rsi": round(rsi, 1),
        "volatility": volatility,
        "verdict": ind.get("verdict", "NEUTRAL"),
        "score": ind.get("score", 0),
    }


def _parallel_fetch(jobs: dict) -> dict:
    """Run a dict of {key: callable} concurrently and return {key: result}."""
    out = {}
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        futs = {pool.submit(fn): k for k, fn in jobs.items()}
        for fut in futs:
            k = futs[fut]
            try:
                out[k] = fut.result(timeout=8)
            except Exception:
                out[k] = None
    return out


# ---------- public API ----------

def get_spec(key: str) -> dict | None:
    return next((c for c in COMMODITIES if c["key"] == key), None)


def list_commodities() -> list[dict]:
    """Light listing for the index page — name, emoji, latest price for each instrument."""
    from .fetcher import fetch_quotes
    tickers = []
    for spec in COMMODITIES:
        if spec["etf"]:
            tickers.append(spec["etf"]["ticker"])
        if spec["futures"]:
            tickers.append(spec["futures"]["ticker"])
    quotes = fetch_quotes(tickers)  # one DB query; cold misses fetched in parallel with a deadline

    out = []
    for spec in COMMODITIES:
        out.append({
            "spec": spec,
            "etf_quote": quotes.get(spec["etf"]["ticker"]) if spec["etf"] else None,
            "fut_quote": quotes.get(spec["futures"]["ticker"]) if spec["futures"] else None,
        })
    return out


def build_position_sizer(spec: dict, etf_quote: dict | None, fut_quote: dict | None,
                         amount: float, risk_pct: float) -> dict | None:
    """
    Translate "I have ₹X to invest and I'm OK losing at most Y% of it" into a
    concrete plan for both vehicles, then declare a winner.

    The math for ETF is straightforward: units × price = capital deployed.
    The math for futures is harder: a single lot has a notional value much larger
    than the typical retail capital, and a 10% adverse move on the notional is
    the actual loss (leverage cuts both ways). We use a 10% adverse move as the
    'reasonable shock' baseline because that's roughly a 1-in-12-month event for
    most metals.
    """
    if amount <= 0 or risk_pct <= 0:
        return None

    risk_budget = amount * (risk_pct / 100.0)  # rupees the user is willing to lose
    shock = 0.10  # baseline 10% adverse move scenario
    out = {
        "amount": amount,
        "risk_pct": risk_pct,
        "risk_budget": risk_budget,
        "shock_pct": shock * 100,
        "etf": None,
        "futures": None,
        "verdict": None,
        "verdict_reason": None,
    }

    # ----- ETF plan -----
    if spec.get("etf") and etf_quote:
        price = etf_quote["price"]
        units = int(amount // price)
        deployed = units * price
        leftover = amount - deployed
        loss_on_shock = deployed * shock
        fits_risk = loss_on_shock <= risk_budget
        out["etf"] = {
            "available": True,
            "units": units,
            "price": price,
            "deployed": deployed,
            "leftover": leftover,
            "loss_on_shock": loss_on_shock,
            "loss_on_shock_pct": (loss_on_shock / amount * 100) if amount else 0,
            "fits_risk": fits_risk,
            "explanation": (
                f"At ₹{price:,.2f} per unit, your ₹{amount:,.0f} buys {units} units of "
                f"{spec['etf']['name']} ({spec['etf']['ticker']}), deploying ₹{deployed:,.0f} "
                f"with ₹{leftover:,.0f} in cash. A 10% adverse move would cost you "
                f"₹{loss_on_shock:,.0f} ({loss_on_shock/amount*100:.1f}% of your capital)."
            ),
        }
    else:
        out["etf"] = {"available": False, "fits_risk": False}

    # ----- Futures plan -----
    if spec.get("futures") and fut_quote:
        contract_price = fut_quote["price"]  # per unit (per oz, per lb, per barrel)
        lot_size = spec["futures"].get("lot_size", 1)
        notional_per_lot = contract_price * lot_size
        # Indian retail margin on commodity futures is roughly 5-10% of notional. Use 8% as a midpoint.
        margin_pct = 0.08
        margin_per_lot = notional_per_lot * margin_pct
        # International contracts (GC=F, CL=F) are quoted in USD — convert.
        ticker = spec["futures"].get("ticker", "")
        if ticker.endswith("=F"):
            try:
                fx = float(__import__("yfinance").Ticker("INR=X").fast_info.last_price)
            except Exception:
                fx = 90.0
            notional_per_lot *= fx
            margin_per_lot *= fx

        lots_affordable = int(amount // margin_per_lot) if margin_per_lot else 0
        if lots_affordable < 1:
            out["futures"] = {
                "available": True,
                "affordable": False,
                "notional_per_lot": notional_per_lot,
                "margin_per_lot": margin_per_lot,
                "explanation": (
                    f"One lot of {spec['futures']['name']} controls {lot_size} {spec['futures']['unit']} "
                    f"with a notional value of ~₹{notional_per_lot:,.0f}. The margin required (~8%) is "
                    f"₹{margin_per_lot:,.0f}, which is more than your ₹{amount:,.0f} capital. "
                    f"You can't even open one lot — futures aren't accessible at this size."
                ),
                "fits_risk": False,
            }
        else:
            position_notional = lots_affordable * notional_per_lot
            margin_used = lots_affordable * margin_per_lot
            loss_on_shock = position_notional * shock  # leveraged loss is on notional, not margin!
            fits_risk = loss_on_shock <= risk_budget
            out["futures"] = {
                "available": True,
                "affordable": True,
                "lots": lots_affordable,
                "notional_per_lot": notional_per_lot,
                "margin_per_lot": margin_per_lot,
                "position_notional": position_notional,
                "margin_used": margin_used,
                "loss_on_shock": loss_on_shock,
                "loss_on_shock_pct": (loss_on_shock / amount * 100) if amount else 0,
                "fits_risk": fits_risk,
                "explanation": (
                    f"₹{amount:,.0f} margin lets you carry {lots_affordable} lot(s), each controlling "
                    f"~₹{notional_per_lot:,.0f} notional. Total notional exposure: ₹{position_notional:,.0f} "
                    f"on just ₹{margin_used:,.0f} of your capital — that's the leverage. A 10% adverse "
                    f"move on the underlying costs you ₹{loss_on_shock:,.0f} "
                    f"({loss_on_shock/amount*100:.1f}% of your capital), and if it exceeds your margin you'll "
                    f"face a margin call."
                ),
            }
    else:
        out["futures"] = {"available": False, "fits_risk": False}

    # ----- Verdict -----
    etf = out["etf"]
    fut = out["futures"]

    if etf and etf.get("fits_risk"):
        out["verdict"] = "ETF"
        out["verdict_reason"] = (
            f"Your ₹{amount:,.0f} capital and {risk_pct}% risk tolerance fit comfortably inside the "
            f"ETF route. Buy {etf['units']} units, expect ~{etf['loss_on_shock_pct']:.1f}% downside on a "
            f"reasonable shock — well within your {risk_pct}% budget. No margin calls, no rollover, "
            f"hold for as long as you like."
        )
    elif fut and fut.get("affordable") and fut.get("fits_risk"):
        out["verdict"] = "FUTURES"
        out["verdict_reason"] = (
            f"No ETF available (or it didn't fit). Futures fit your capital and risk: {fut['lots']} "
            f"lot(s), worst-case ~{fut['loss_on_shock_pct']:.1f}% loss on a 10% adverse move. Stay disciplined "
            f"about stop-losses and budget for monthly rollover costs."
        )
    elif etf and etf.get("available"):
        out["verdict"] = "ETF (over budget)"
        out["verdict_reason"] = (
            f"The ETF is the safer route but your {risk_pct}% risk tolerance is tight: a 10% shock would "
            f"cost ~{etf['loss_on_shock_pct']:.1f}% of capital, which is above your stated comfort. Either "
            f"raise your risk tolerance, hold a smaller position, or pair with safer assets to dilute exposure."
        )
    elif fut and fut.get("available") and not fut.get("affordable"):
        out["verdict"] = "TOO SMALL"
        out["verdict_reason"] = (
            f"Your capital is below one futures lot's margin and there's no ETF available for "
            f"{spec['name'].lower()}. Consider equity proxies (mining/refining stocks) or wait until "
            f"you can deploy a larger sum."
        )
    elif fut and fut.get("affordable") and not fut.get("fits_risk"):
        out["verdict"] = "TOO RISKY"
        out["verdict_reason"] = (
            f"Futures are affordable but the leverage blows past your {risk_pct}% loss budget — a 10% "
            f"adverse move would cost ~{fut['loss_on_shock_pct']:.0f}% of your capital. Either size down "
            f"to fewer lots than the calculator suggests, raise your risk tolerance, or skip direct "
            f"{spec['name'].lower()} exposure and use equity proxies (mining/refining stocks) instead."
        )
    else:
        out["verdict"] = "NO FIT"
        out["verdict_reason"] = "Neither vehicle fits cleanly. Reconsider amount or risk tolerance."

    return out


def build_commodity_view(key: str) -> dict | None:
    spec = get_spec(key)
    if not spec:
        return None

    jobs = {}
    if spec["etf"]:
        jobs["etf_q"] = lambda: fetch_quote(spec["etf"]["ticker"])
        jobs["etf_t"] = lambda: _trend_block(spec["etf"]["ticker"])
    if spec["futures"]:
        jobs["fut_q"] = lambda: fetch_quote(spec["futures"]["ticker"])
        jobs["fut_t"] = lambda: _trend_block(spec["futures"]["ticker"])

    res = _parallel_fetch(jobs)
    etf_quote = res.get("etf_q")
    fut_quote = res.get("fut_q")
    etf_trend = res.get("etf_t") or {"available": False}
    fut_trend = res.get("fut_t") or {"available": False}

    recommendation = _recommend(spec, etf_quote, fut_quote, etf_trend, fut_trend)

    return {
        "spec": spec,
        "etf_quote": etf_quote,
        "fut_quote": fut_quote,
        "etf_trend": etf_trend,
        "fut_trend": fut_trend,
        "recommendation": recommendation,
    }


# ---------- recommendation engine ----------

PROS_ETF = [
    "No expiry, no rollover — buy once and hold for years.",
    "No leverage, so no margin calls or forced liquidation in a drawdown.",
    "Capital required = price of one unit (often ₹50–₹250), not lakhs of margin.",
    "Held in your demat like any stock. Buy/sell via the same broker app you already use.",
    "Tracks the spot price closely after a small expense ratio.",
]
CONS_ETF = [
    "Annual expense ratio (~0.5–0.8%) eats into returns slightly.",
    "Slight tracking error vs the spot metal price.",
    "Post-2023 debt-fund tax changes: gold/silver ETF gains are taxed at your slab rate "
    "regardless of holding period (the old 20% with indexation after 3 years is gone).",
]
PROS_FUT = [
    "Leverage means a small margin controls a large notional position — capital-efficient if you know what you're doing.",
    "Tracks the underlying very tightly for the active month — minimal tracking error.",
    "Cheaper to hold than an ETF *if* the market is in backwardation (rare for metals).",
    "Tighter bid-ask spreads than most ETFs in active months.",
]
CONS_FUT = [
    "Monthly rollover — every expiry you must close and reopen, paying brokerage and spread each time.",
    "Daily mark-to-market: an adverse move triggers margin calls within 24 hours.",
    "Contango (the usual state for metals) means each rollover bleeds 0.3–1% — over a year that compounds to 4–12% of pure friction.",
    "Lot sizes are large — one MCX gold lot is 1 kg ≈ ₹70+ lakh notional.",
    "Treated as non-speculative business income for tax, with mandatory audit if turnover crosses limits.",
    "Requires constant monitoring — you can't 'set and forget' a futures position.",
]


def _recommend(spec, etf_quote, fut_quote, etf_trend, fut_trend) -> dict:
    """Build a structured ETF-vs-Futures recommendation for a long-term retail investor."""
    has_etf = spec["etf"] is not None and etf_quote is not None
    has_fut = spec["futures"] is not None and fut_quote is not None

    score_etf = 0
    score_fut = 0
    reasoning = []  # list of {"label": ..., "text": ..., "delta": "ETF +1" or similar}

    # 1. The big one: time horizon
    if has_etf:
        score_etf += 3
        reasoning.append({
            "label": "Time horizon: long-term",
            "text": (
                "You're thinking in years, not weeks. That single fact decides ~80% of this "
                "question. Futures bleed money to rollover every month, while an ETF you can "
                "hold for a decade with one trade."
            ),
            "delta": "ETF +3",
        })

    # 2. Availability constraint
    if has_fut and not has_etf:
        score_fut += 2
        reasoning.append({
            "label": f"No clean ETF exists for {spec['name']}",
            "text": (
                f"On Indian exchanges there's no liquid {spec['name'].lower()} ETF, which forces "
                f"the hand. If you want pure exposure your only direct route is futures (or going "
                f"indirect via mining/refining equities, which is a different bet entirely)."
            ),
            "delta": "Futures +2",
        })

    # 3. Trend check on the ETF (or futures if ETF unavailable)
    primary_trend = etf_trend if has_etf and etf_trend.get("available") else fut_trend
    if primary_trend.get("available"):
        t = primary_trend["trend"]
        v = primary_trend["volatility"]
        rsi = primary_trend["rsi"]

        if t == "Uptrend":
            score_etf += 1
            reasoning.append({
                "label": "Trend check",
                "text": (
                    f"{spec['name']} is in a confirmed uptrend on the daily chart (20-day average "
                    f"above 50-day, RSI {rsi}). For a long-term entry this is a 'momentum is on "
                    f"your side' signal — don't chase blindly, but no need to wait for a pullback "
                    f"that may not come."
                ),
                "delta": "ETF +1",
            })
        elif t == "Downtrend":
            reasoning.append({
                "label": "Trend check",
                "text": (
                    f"{spec['name']} is in a downtrend (RSI {rsi}). For long-term buying this is "
                    f"actually a feature — you're getting a discount — but consider staggering "
                    f"buys SIP-style over 3–6 months rather than going all-in at one price. The "
                    f"trend doesn't change the ETF-vs-Futures answer; it changes how fast you deploy."
                ),
                "delta": "Neutral",
            })
        else:
            reasoning.append({
                "label": "Trend check",
                "text": (
                    f"{spec['name']} is consolidating sideways (RSI {rsi}). No urgency either way — "
                    f"start a small position and add on weakness."
                ),
                "delta": "Neutral",
            })

        if v == "High":
            score_fut -= 1
            reasoning.append({
                "label": "Volatility regime: high",
                "text": (
                    "Bollinger band width is wide right now, which means price swings are large. "
                    "In high-volatility regimes futures are doubly dangerous because daily MTM "
                    "swings can hit margin requirements unpredictably and force you out near a "
                    "low. ETFs absorb the same swings on paper without any margin call risk."
                ),
                "delta": "Futures −1",
            })
        elif v == "Low" and has_fut:
            reasoning.append({
                "label": "Volatility regime: low",
                "text": (
                    "Volatility is currently low. For an active short-term trader this would be "
                    "the easier environment for futures, but for a long-term holder it's irrelevant — "
                    "today's calm doesn't change tomorrow's storm risk."
                ),
                "delta": "Neutral",
            })

    # 4. Capital efficiency
    if has_etf and etf_quote:
        score_etf += 1
        reasoning.append({
            "label": "Capital efficiency for retail",
            "text": (
                f"At ₹{etf_quote['price']:.2f} per unit you can start a {spec['name'].lower()} "
                f"position with as little as ₹{etf_quote['price']:.0f}. Compare to one futures lot "
                f"which requires several lakhs in margin and exposes you to crores in notional "
                f"value. For retail position-sizing the ETF wins on flexibility alone — you can "
                f"add ₹2,000 a month and it just works."
            ),
            "delta": "ETF +1",
        })

    # 5. Tax friction
    if has_etf and has_fut:
        reasoning.append({
            "label": "Tax friction",
            "text": (
                "ETF gains are taxed at your slab rate (post-2023 changes). Futures are taxed as "
                "non-speculative business income — also at slab rate, but you pick up audit "
                "obligations once turnover crosses ₹10 cr (₹2 cr if profit margin is below 6%). "
                "For a casual long-term investor, the ETF route keeps your ITR simple."
            ),
            "delta": "ETF +0 (tie on rate, win on simplicity)",
        })

    # Final verdict
    if score_etf > score_fut:
        verdict = "BUY THE ETF"
        verdict_color = "accent"
        if has_etf:
            action = (
                f"Accumulate {spec['etf']['ticker']} ({spec['etf']['name']}) via SIP or staggered "
                f"buys over the next 3–6 months. Don't try to nail a single perfect entry — "
                f"average in. Target a portfolio allocation of 5–10% to {spec['name'].lower()} "
                f"if this is your first commodity position."
            )
        else:
            action = (
                f"ETF route preferred but no Indian ETF tracks {spec['name'].lower()} cleanly. "
                f"Consider an equity proxy (mining/refining stocks) instead of futures."
            )
    elif score_fut > score_etf:
        verdict = "USE FUTURES (carefully)"
        verdict_color = "yellow-400"
        action = (
            f"With no ETF available, futures are the only direct route to {spec['name'].lower()}. "
            f"Size positions so that a 10% adverse move costs you no more than 2% of your total "
            f"portfolio, budget for monthly rollover costs (~0.5% per month is realistic for "
            f"{spec['name'].lower()}), and never carry a position into expiry without a plan."
        )
    else:
        verdict = "NEUTRAL — your call"
        verdict_color = "muted"
        action = (
            "Both vehicles are viable. Pick based on your tax situation, your time available "
            "to monitor positions, and how active you want to be."
        )

    return {
        "verdict": verdict,
        "verdict_color": verdict_color,
        "action": action,
        "score_etf": score_etf,
        "score_fut": score_fut,
        "reasoning": reasoning,
        "pros_etf": PROS_ETF,
        "cons_etf": CONS_ETF,
        "pros_fut": PROS_FUT,
        "cons_fut": CONS_FUT,
        "has_etf": has_etf,
        "has_fut": has_fut,
    }
