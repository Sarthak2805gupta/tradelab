"""
Quarterly financials + fundamentals strength narrative for the analysis page.

Pulls quarterly income statements from yfinance, computes the numbers retail
investors actually look at (Y/Y revenue growth, net margin, EPS trend),
formats them in Indian crore/lakh notation, and generates a plain-English
"why this stock looks strong/weak" verdict based on the fundamentals.

Returns None for tickers that don't have a proper income statement
(ETFs, commodity futures, indices) — the template skips the card in that case.
"""
from __future__ import annotations

import math
from typing import Any

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def _is_finite_number(x: Any) -> bool:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return False
    return not math.isnan(f) and not math.isinf(f)


def _format_inr(value: float) -> str:
    """Format a rupee amount into Indian-style Cr/L notation."""
    if not _is_finite_number(value):
        return "—"
    v = float(value)
    absv = abs(v)
    if absv >= 1e7:  # 1 crore
        # Above 1000 Cr, use 'KCr' (thousand crore = 10000 Cr) for readability
        cr = v / 1e7
        if abs(cr) >= 1000:
            return f"{cr/1000:.2f}KCr"
        return f"{cr:,.2f}Cr"
    if absv >= 1e5:  # 1 lakh
        return f"{v/1e5:,.2f}L"
    return f"₹{v:,.0f}"


def _pct(curr: float, prev: float) -> float | None:
    if not (_is_finite_number(curr) and _is_finite_number(prev)) or prev == 0:
        return None
    return (curr - prev) / abs(prev) * 100.0


def _safe_row(df, label: str) -> list[float]:
    """Return a row from the financials dataframe as a list of floats, tolerating missing rows."""
    if df is None or df.empty or label not in df.index:
        return []
    raw = list(df.loc[label])
    out = []
    for v in raw:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(float("nan"))
    return out


def _quarter_label(ts) -> str:
    """Turn a pandas Timestamp into 'Q2 FY26' style. Indian FY ends in March."""
    try:
        month = ts.month
        year = ts.year
    except Exception:
        return str(ts)
    # Indian fiscal year: Apr-Jun=Q1, Jul-Sep=Q2, Oct-Dec=Q3, Jan-Mar=Q4
    if month >= 4:
        q = (month - 4) // 3 + 1
        fy = year + 1
    else:
        q = 4
        fy = year
    return f"Q{q} FY{str(fy)[-2:]}"


_fx_cache = {"rate": None}


def _usd_to_inr() -> float:
    """Fetch USD->INR rate, cached for the process lifetime. ~92 is a sane fallback."""
    if _fx_cache["rate"]:
        return _fx_cache["rate"]
    try:
        rate = float(yf.Ticker("INR=X").fast_info.last_price)
        if rate and rate > 50:  # sanity
            _fx_cache["rate"] = rate
            return rate
    except Exception:
        pass
    return 90.0  # fallback


# Sector -> relevant learning modules mapping
SECTOR_LEARN_MAP = {
    "technology": ["fundamental-analysis", "technical-analysis", "swing-trading"],
    "financial services": ["fundamental-analysis", "balance-sheet", "risk-management"],
    "energy": ["fundamental-analysis", "balance-sheet", "swing-trading"],
    "consumer cyclical": ["fundamental-analysis", "stocks-ipos-indices", "swing-trading"],
    "consumer defensive": ["fundamental-analysis", "mutual-funds", "risk-management"],
    "healthcare": ["fundamental-analysis", "balance-sheet", "risk-management"],
    "industrials": ["fundamental-analysis", "balance-sheet", "technical-analysis"],
    "basic materials": ["fundamental-analysis", "swing-trading", "technical-analysis"],
    "communication services": ["fundamental-analysis", "stocks-ipos-indices", "technical-analysis"],
    "real estate": ["fundamental-analysis", "balance-sheet", "risk-management"],
    "utilities": ["fundamental-analysis", "balance-sheet", "mutual-funds"],
}


def get_company_profile(ticker: str) -> dict | None:
    """
    Pull company story, sector context, key events (dividends, splits),
    and upcoming calendar from yfinance. Returns None for ETFs/futures.
    """
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception:
        return None

    summary = info.get("longBusinessSummary")
    if not summary:
        return None  # ETFs/futures/indices don't have this

    sector = info.get("sector", "")
    industry = info.get("industry", "")

    # Company basics
    profile = {
        "name": info.get("longName") or info.get("shortName") or ticker,
        "summary": summary,
        "sector": sector,
        "industry": industry,
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website"),
        "city": info.get("city"),
        "country": info.get("country"),
    }

    # Sector learning links — resolve slugs to titles here so the template doesn't need a custom tag
    sector_key = sector.lower() if sector else ""
    learn_slugs = SECTOR_LEARN_MAP.get(sector_key, ["fundamental-analysis", "technical-analysis"])
    try:
        from apps.learning.models import Module
        modules_qs = Module.objects.filter(slug__in=learn_slugs).values_list("slug", "title")
        slug_to_title = dict(modules_qs)
        profile["learn_modules"] = [
            {"slug": s, "title": slug_to_title[s]}
            for s in learn_slugs if s in slug_to_title
        ]
    except Exception:
        profile["learn_modules"] = []

    # Dividend history
    try:
        divs = t.dividends
        if divs is not None and not divs.empty:
            div_list = []
            for dt, val in divs.tail(8).items():
                div_list.append({
                    "date": dt.strftime("%d %b %Y"),
                    "amount": round(float(val), 2),
                })
            profile["dividends"] = list(reversed(div_list))
        else:
            profile["dividends"] = []
    except Exception:
        profile["dividends"] = []

    # Stock splits
    try:
        splits = t.splits
        if splits is not None and not splits.empty:
            split_list = []
            for dt, val in splits.items():
                if val > 0:
                    split_list.append({
                        "date": dt.strftime("%d %b %Y"),
                        "ratio": f"{int(val)}:1",
                    })
            profile["splits"] = split_list
        else:
            profile["splits"] = []
    except Exception:
        profile["splits"] = []

    # Upcoming calendar (next earnings, ex-dividend)
    try:
        cal = t.calendar
        if cal and isinstance(cal, dict):
            profile["next_earnings"] = None
            earnings_dates = cal.get("Earnings Date")
            if earnings_dates and len(earnings_dates) > 0:
                ed = earnings_dates[0]
                if hasattr(ed, "strftime"):
                    profile["next_earnings"] = ed.strftime("%d %b %Y")
                else:
                    profile["next_earnings"] = str(ed)
            ex_div = cal.get("Ex-Dividend Date")
            if ex_div:
                if hasattr(ex_div, "strftime"):
                    profile["ex_dividend_date"] = ex_div.strftime("%d %b %Y")
                else:
                    profile["ex_dividend_date"] = str(ex_div)
            else:
                profile["ex_dividend_date"] = None
        else:
            profile["next_earnings"] = None
            profile["ex_dividend_date"] = None
    except Exception:
        profile["next_earnings"] = None
        profile["ex_dividend_date"] = None

    return profile


def get_financials(ticker: str) -> dict | None:
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        qdf = t.quarterly_income_stmt
        info = t.info or {}
    except Exception:
        return None
    if qdf is None or qdf.empty:
        return None

    # yfinance reports some Indian ADRs (notably Infosys) in USD even when queried
    # via the .NS ticker. Convert to INR so the Cr/L formatting is accurate.
    fin_ccy = (info.get("financialCurrency") or "INR").upper()
    money_scale = _usd_to_inr() if fin_ccy == "USD" else 1.0

    revenue = [v * money_scale if not math.isnan(v) else v for v in _safe_row(qdf, "Total Revenue")]
    net_income = [v * money_scale if not math.isnan(v) else v for v in _safe_row(qdf, "Net Income")]
    eps = _safe_row(qdf, "Basic EPS")
    if not eps:
        eps = _safe_row(qdf, "Diluted EPS")
    eps = [v * money_scale if not math.isnan(v) else v for v in eps]

    if not revenue or all(math.isnan(r) for r in revenue):
        # No usable income statement — likely an ETF/index/futures contract.
        return None

    periods = list(qdf.columns)

    # Build a history list, newest first. yfinance orders columns newest->oldest already.
    history = []
    for i, period in enumerate(periods):
        rev = revenue[i] if i < len(revenue) else float("nan")
        ni = net_income[i] if i < len(net_income) else float("nan")
        ep = eps[i] if i < len(eps) else float("nan")
        margin = (ni / rev * 100.0) if (_is_finite_number(rev) and _is_finite_number(ni) and rev) else None
        history.append({
            "quarter": _quarter_label(period),
            "period_ts": period.isoformat() if hasattr(period, "isoformat") else str(period),
            "revenue": rev if _is_finite_number(rev) else None,
            "revenue_str": _format_inr(rev),
            "net_income": ni if _is_finite_number(ni) else None,
            "net_income_str": _format_inr(ni),
            "eps": round(ep, 2) if _is_finite_number(ep) else None,
            "margin": round(margin, 2) if margin is not None else None,
        })

    # Latest quarter snapshot
    latest = history[0]
    # Y/Y comparison: latest vs the same quarter one year earlier (4 steps back).
    # Accuracy: with fewer than 5 quarters there is no true year-ago quarter;
    # the old code silently compared against whatever the oldest quarter was
    # (e.g. 2 quarters back) and still labelled it "Y/Y". Now it's None, and
    # the rating treats growth as "data incomplete" instead of guessing.
    if len(history) > 4:
        yoy = history[4]
        yoy_revenue_pct = _pct(latest["revenue"], yoy["revenue"])
        yoy_profit_pct = _pct(latest["net_income"], yoy["net_income"])
        yoy_eps_pct = _pct(latest["eps"], yoy["eps"]) if (latest["eps"] and yoy["eps"]) else None
    else:
        yoy_revenue_pct = yoy_profit_pct = yoy_eps_pct = None

    # Q/Q (just previous quarter)
    prev = history[1] if len(history) > 1 else None
    qoq_revenue_pct = _pct(latest["revenue"], prev["revenue"]) if prev else None

    # Build the snapshot from info we already fetched above
    snapshot = {
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "trailing_eps": info.get("trailingEps"),
        "profit_margin": info.get("profitMargins"),  # 0..1
        "roe": info.get("returnOnEquity"),  # 0..1
        "debt_to_equity": info.get("debtToEquity"),
        "dividend_yield": info.get("dividendYield"),  # yfinance returns as percent (e.g. 0.41 = 0.41%)
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "long_name": info.get("longName") or info.get("shortName"),
        "financial_currency": fin_ccy,
    }

    strengths, concerns = _assess(snapshot, latest, yoy_revenue_pct, yoy_profit_pct,
                                  sector=info.get("sector"))

    return {
        "available": True,
        "latest": latest,
        "yoy_revenue_pct": round(yoy_revenue_pct, 2) if yoy_revenue_pct is not None else None,
        "yoy_profit_pct": round(yoy_profit_pct, 2) if yoy_profit_pct is not None else None,
        "yoy_eps_pct": round(yoy_eps_pct, 2) if yoy_eps_pct is not None else None,
        "qoq_revenue_pct": round(qoq_revenue_pct, 2) if qoq_revenue_pct is not None else None,
        "history": history[:8],  # last 8 quarters
        "snapshot": snapshot,
        "strengths": strengths,
        "concerns": concerns,
    }


# Sectors where debt is the raw material of the business (banks, NBFCs,
# insurers): a high debt/equity ratio is structural, not a warning sign.
LEVERAGE_NEUTRAL_SECTORS = {"financial services"}


def _assess(snap: dict, latest: dict, yoy_rev: float | None, yoy_profit: float | None,
            sector: str | None = None):
    """Produce plain-English strength/concern bullets about the company's fundamentals."""
    strengths = []
    concerns = []
    sector_key = (sector or "").strip().lower()

    # Revenue growth
    if yoy_rev is not None:
        if yoy_rev > 15:
            strengths.append(
                f"Strong top-line growth — revenue is up {yoy_rev:+.1f}% year-on-year, "
                f"which means the business is genuinely expanding, not just riding price hikes."
            )
        elif yoy_rev > 5:
            strengths.append(
                f"Steady revenue growth of {yoy_rev:+.1f}% year-on-year — a healthy rate "
                f"for a mature company in line with nominal GDP growth."
            )
        elif yoy_rev > 0:
            concerns.append(
                f"Revenue growth is slow ({yoy_rev:+.1f}% Y/Y) — barely keeping up with "
                f"inflation. Check whether this is a temporary slowdown or a structural issue."
            )
        else:
            concerns.append(
                f"Revenue has *shrunk* {yoy_rev:+.1f}% year-on-year. That's a red flag — "
                f"dig into whether demand is weakening or a business line was divested."
            )

    # Profit growth vs revenue growth (operating leverage check)
    if yoy_profit is not None and yoy_rev is not None:
        if yoy_profit > yoy_rev + 5:
            strengths.append(
                f"Profit is growing faster than revenue ({yoy_profit:+.1f}% vs {yoy_rev:+.1f}%) — "
                f"that's operating leverage working in your favour. Margins are expanding."
            )
        elif yoy_profit < yoy_rev - 5 and yoy_profit is not None:
            concerns.append(
                f"Profit grew slower than revenue ({yoy_profit:+.1f}% vs {yoy_rev:+.1f}%) — "
                f"suggests rising input costs, employee expenses, or interest costs are squeezing margins."
            )

    # Net margin absolute
    if latest.get("margin") is not None:
        m = latest["margin"]
        if m > 20:
            strengths.append(
                f"Premium net margin of {m:.1f}% — rare and usually signals strong pricing power "
                f"(brand, network effects, or scale economics)."
            )
        elif m > 10:
            strengths.append(f"Healthy net margin of {m:.1f}% — solid profitability cushion.")
        elif m > 5:
            pass  # unremarkable
        elif m > 0:
            concerns.append(
                f"Thin net margin of {m:.1f}% leaves little buffer — a small cost shock or "
                f"price war can flip this business into losses."
            )
        else:
            concerns.append(f"Net margin is *negative* ({m:.1f}%) — the company is loss-making this quarter.")

    # PE
    pe = snap.get("trailing_pe")
    if _is_finite_number(pe):
        if pe < 0:
            concerns.append("Negative PE — trailing earnings are in the red.")
        elif pe < 15:
            strengths.append(
                f"Trades at {pe:.1f}x trailing earnings — cheap on the absolute scale, worth "
                f"comparing with sector peers to rule out a value trap."
            )
        elif pe < 30:
            pass
        elif pe < 60:
            concerns.append(
                f"PE of {pe:.1f}x is rich — the market is pricing in strong growth. "
                f"A single bad quarter could compress the multiple meaningfully."
            )
        else:
            concerns.append(
                f"PE of {pe:.1f}x is very expensive — extreme premium. Either the growth story "
                f"is exceptional or the stock is overheated; be cautious."
            )

    # ROE
    roe = snap.get("roe")
    if _is_finite_number(roe):
        roe_pct = roe * 100
        if roe_pct > 20:
            strengths.append(
                f"Return on equity of {roe_pct:.1f}% — the company compounds shareholder capital "
                f"at an excellent rate. This is one of the best single metrics for long-term quality."
            )
        elif roe_pct > 12:
            strengths.append(f"Return on equity of {roe_pct:.1f}% — reasonable capital efficiency.")
        elif roe_pct > 0:
            concerns.append(f"Return on equity is only {roe_pct:.1f}% — capital isn't working hard enough.")

    # Debt / equity — skipped for banks/NBFCs, whose balance sheets are
    # leveraged by design (deposits and borrowings fund the loan book), so
    # the generic "high leverage" warning would fire on every bank.
    de = snap.get("debt_to_equity")
    if _is_finite_number(de) and sector_key not in LEVERAGE_NEUTRAL_SECTORS:
        # yfinance returns this as a number like 35.6 meaning 35.6% or 0.356 ratio depending on version
        # Normalise: if >5 assume it's a percent
        de_ratio = de / 100.0 if de > 5 else de
        if de_ratio < 0.5:
            strengths.append(f"Low leverage (D/E ≈ {de_ratio:.2f}) — the balance sheet is conservative and can weather a downturn.")
        elif de_ratio > 1.5:
            concerns.append(
                f"High leverage (D/E ≈ {de_ratio:.2f}) — amplifies gains in good times but magnifies pain "
                f"when rates rise or earnings dip. Watch interest coverage closely."
            )

    # Dividend yield — yfinance returns as a percent already (e.g. 0.41 means 0.41%)
    dy = snap.get("dividend_yield")
    if _is_finite_number(dy) and dy > 1.5:
        strengths.append(f"Pays a {dy:.1f}% dividend yield — real cash returns while you wait.")

    return strengths, concerns
