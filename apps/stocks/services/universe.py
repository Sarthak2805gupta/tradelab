"""
Static stock universes used across the app:

  - QUICK_PICKS: curated groups shown on the Analysis page
  - SEARCH_UNIVERSE: ticker autocomplete data (quick picks + bundled NSE list)
  - NIFTY50 / SENSEX / BANK membership sets for the day-trade filter chips
  - equity_universe(): the de-duplicated, non-commodity quick picks that the
    Risk Analyser and the Live desk rankings score

Moved out of views.py so the views stay thin and these lists can be
imported without pulling in the whole view module (the context processor
used to import views.py just to read SEARCH_UNIVERSE).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import commodities

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


def _build_commodity_quick_picks() -> dict:
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


def _build_search_universe() -> list[dict]:
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
    data_path = Path(__file__).resolve().parent.parent / "data" / "nse_stocks.json"
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


def equity_universe() -> list[dict]:
    """
    The equity quick-picks, de-duplicated and without the commodities group
    (ETFs/futures have different risk characteristics). Used by the Risk
    Analyser screen and the Live desk day-trade rankings.
    """
    out = []
    seen = set()
    for group in QUICK_PICKS:
        if "commodities" in group["label"].lower():
            continue
        for s in group["stocks"]:
            if s["ticker"] in seen:
                continue
            seen.add(s["ticker"])
            out.append(s)
    return out
