"""
Deep technical indicator readings — uses the rich indicator library ported
from the Flask screener (apps/screener/services/indicators/) to compute
Supertrend, ADX, Ichimoku, CMF, Aroon, and candlestick patterns, then
renders them as plain-English readings for the Analysis page.
"""
from __future__ import annotations

import math

import pandas as pd

# Import the screener services package first — triggers sys.path injection so
# the flat module imports below (complete_indicators, indicators_extension)
# resolve. Without this, Django will never find the modules.
import apps.screener.services  # noqa: F401


def _last_float(series, default=None):
    try:
        v = float(series.iloc[-1])
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def compute(df: pd.DataFrame) -> list[dict]:
    """Return a list of indicator readings: {name, verdict, bullish, reading, detail}."""
    if df is None or df.empty or len(df) < 60:
        return []

    # Flask's functions expect capitalised OHLCV columns
    cols_in = set(df.columns)
    if not {"Open", "High", "Low", "Close", "Volume"}.issubset(cols_in):
        # Try lowercase-to-titlecase remap
        remap = {c: c.title() for c in df.columns if c.lower() in {"open", "high", "low", "close", "volume"}}
        df = df.rename(columns=remap)

    readings: list[dict] = []

    # ── Supertrend ───────────────────────────────────────────────────────
    try:
        from complete_indicators import calc_supertrend  # type: ignore
        st_line, direction = calc_supertrend(df, period=7, multiplier=3.0)
        dir_last = int(direction.iloc[-1])
        st_val = _last_float(st_line)
        close = _last_float(df["Close"])
        bullish = dir_last == 1
        readings.append({
            "name": "Supertrend",
            "verdict": "BULLISH" if bullish else "BEARISH",
            "bullish": bullish,
            "reading": f"Trailing stop at ₹{st_val:,.2f}" if st_val else "—",
            "detail": (
                f"Price ₹{close:,.2f} is {'above' if bullish else 'below'} the Supertrend line — "
                f"the trend is {'up. Use ₹' + f'{st_val:,.2f}' + ' as your stop-loss.' if bullish else 'down. Avoid fresh long entries.'}"
            ),
        })
    except Exception:
        pass

    # ── ADX + DI ─────────────────────────────────────────────────────────
    try:
        from complete_indicators import calc_adx  # type: ignore
        adx, plus_di, minus_di = calc_adx(df, period=14)
        adx_v = _last_float(adx)
        pdi = _last_float(plus_di)
        mdi = _last_float(minus_di)
        if adx_v is not None:
            if adx_v < 20:
                strength, bullish = "NO TREND", None
                detail = f"ADX {adx_v:.0f} — market is choppy/sideways. Trend-following strategies will fail here; wait for ADX > 25 before trusting a move."
            elif adx_v < 25:
                strength, bullish = "DEVELOPING", None
                detail = f"ADX {adx_v:.0f} — a trend is forming but not yet confirmed. Early entries are risky."
            else:
                dir_bull = pdi is not None and mdi is not None and pdi > mdi
                strength = "STRONG " + ("UP" if dir_bull else "DOWN") + "TREND"
                bullish = bool(dir_bull)
                detail = (
                    f"ADX {adx_v:.0f} with +DI {pdi:.1f} vs −DI {mdi:.1f} — "
                    f"{'bulls' if dir_bull else 'bears'} in control. "
                    f"{'Momentum strategies work well here.' if adx_v < 40 else 'Very strong — watch for exhaustion.'}"
                )
            readings.append({
                "name": "ADX (trend strength)",
                "verdict": strength,
                "bullish": bullish,
                "reading": f"ADX {adx_v:.0f}",
                "detail": detail,
            })
    except Exception:
        pass

    # ── Ichimoku Cloud ───────────────────────────────────────────────────
    try:
        from indicators_extension import calc_ichimoku  # type: ignore
        tenkan, kijun, span_a, span_b, chikou = calc_ichimoku(df)
        close = _last_float(df["Close"])
        a = _last_float(span_a)
        b = _last_float(span_b)
        if close and a and b:
            top = max(a, b)
            bot = min(a, b)
            if close > top:
                verdict, bullish = "ABOVE CLOUD", True
                detail = f"Price ₹{close:,.2f} is above the cloud (top ₹{top:,.2f}). Long-term trend is bullish; cloud acts as support on any dip."
            elif close < bot:
                verdict, bullish = "BELOW CLOUD", False
                detail = f"Price ₹{close:,.2f} is below the cloud (bottom ₹{bot:,.2f}). Long-term trend is bearish; avoid fresh longs."
            else:
                verdict, bullish = "INSIDE CLOUD", None
                detail = f"Price ₹{close:,.2f} is inside the cloud (₹{bot:,.2f} – ₹{top:,.2f}). No clear trend — wait for a breakout either direction."
            readings.append({
                "name": "Ichimoku Cloud",
                "verdict": verdict,
                "bullish": bullish,
                "reading": f"Cloud ₹{bot:,.0f} – ₹{top:,.0f}",
                "detail": detail,
            })
    except Exception:
        pass

    # ── CMF (Chaikin Money Flow) ─────────────────────────────────────────
    try:
        from indicators_extension import calc_cmf  # type: ignore
        cmf_s = calc_cmf(df, period=20)
        cmf_v = _last_float(cmf_s)
        if cmf_v is not None:
            if cmf_v > 0.1:
                verdict, bullish = "STRONG ACCUMULATION", True
                detail = f"CMF {cmf_v:+.2f} — big money is buying. Price moves are backed by real volume, not noise."
            elif cmf_v > 0:
                verdict, bullish = "MILD ACCUMULATION", True
                detail = f"CMF {cmf_v:+.2f} — modest buying pressure, but not decisive."
            elif cmf_v > -0.1:
                verdict, bullish = "MILD DISTRIBUTION", False
                detail = f"CMF {cmf_v:+.2f} — sellers have slight upper hand; rallies may be fading."
            else:
                verdict, bullish = "STRONG DISTRIBUTION", False
                detail = f"CMF {cmf_v:+.2f} — institutional selling. Any bounce is likely a fake rally."
            readings.append({
                "name": "CMF (money flow)",
                "verdict": verdict,
                "bullish": bullish,
                "reading": f"CMF {cmf_v:+.2f}",
                "detail": detail,
            })
    except Exception:
        pass

    # ── Aroon ────────────────────────────────────────────────────────────
    try:
        from indicators_extension import calc_aroon  # type: ignore
        aroon_up, aroon_dn = calc_aroon(df, period=25)
        au = _last_float(aroon_up)
        ad = _last_float(aroon_dn)
        if au is not None and ad is not None:
            if au > 70 and ad < 30:
                verdict, bullish = "STRONG UPTREND", True
                detail = f"Aroon Up {au:.0f} vs Down {ad:.0f} — clear new highs being made; trend is freshly bullish."
            elif ad > 70 and au < 30:
                verdict, bullish = "STRONG DOWNTREND", False
                detail = f"Aroon Down {ad:.0f} vs Up {au:.0f} — new lows being made; trend is freshly bearish."
            else:
                verdict, bullish = "CONSOLIDATING", None
                detail = f"Aroon Up {au:.0f} / Down {ad:.0f} — neither side dominant, price is range-bound."
            readings.append({
                "name": "Aroon",
                "verdict": verdict,
                "bullish": bullish,
                "reading": f"Up {au:.0f} / Dn {ad:.0f}",
                "detail": detail,
            })
    except Exception:
        pass

    # ── Candlestick pattern on the most recent bar ───────────────────────
    try:
        from complete_indicators import is_hammer, is_bullish_engulfing, is_doji, is_shooting_star  # type: ignore
        row = df.iloc[-1]
        prev = df.iloc[-2]
        pattern = None
        if is_bullish_engulfing(prev, row):
            pattern = ("Bullish Engulfing", True, "Reversal signal — today's green candle completely swallowed yesterday's red one. Buyers took control decisively.")
        elif is_hammer(row):
            pattern = ("Hammer", True, "Reversal signal — a long lower wick shows buyers aggressively rejected lower prices. Watch for confirmation on the next bar.")
        elif is_shooting_star(row):
            pattern = ("Shooting Star", False, "Reversal signal — a long upper wick shows sellers rejected higher prices. Short-term weakness likely.")
        elif is_doji(row):
            pattern = ("Doji", None, "Indecision — open and close are nearly equal. Bulls and bears are evenly matched; wait for direction.")
        if pattern:
            name, bullish, detail = pattern
            readings.append({
                "name": "Candlestick pattern",
                "verdict": name.upper(),
                "bullish": bullish,
                "reading": name,
                "detail": detail,
            })
    except Exception:
        pass

    return readings
