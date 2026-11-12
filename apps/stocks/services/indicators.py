"""
Pure-pandas/numpy technical indicators. All functions accept a DataFrame
with at least a 'Close' column (and 'High'/'Low' where required) and return
either a Series, dict, or scalar.

Accuracy notes (see git history for the before/after):
  * sma() needs a full window before it reports a value. Previously an
    "SMA50" computed on 20 bars was really a 20-bar average, which could
    flip the trend verdict on short histories.
  * rsi() returns 100 when there have been no losses in the window (the
    textbook value) instead of a neutral 50.
  * bollinger() uses the population standard deviation (ddof=0), which is
    how Bollinger Bands are defined and how charting platforms draw them.
    pandas' default (ddof=1) made the bands ~2.6% too wide at window=20.

Trend score (compute_all "score" / "verdict"), reworked after a backtest:
  The old score added up SMA20-vs-SMA50, RSI>60/<40 and MACD-vs-signal.
  Replaying it weekly on 224 NSE stocks over 2017-2026 showed no edge: its
  "BULLISH" picks did no better than its "BEARISH" ones over the next 1-3
  months (rank correlation with 3-month excess return about -0.005). The
  three signals that did predict, in both 2017-22 and 2023-26, were:
    * price vs its 200-day average (long-term trend),
    * the 11-month return excluding the latest month (price momentum),
    * how close the price is to its 1-year high.
  Each now votes +1 / 0 / -1, so the score keeps its -3..+3 range and the
  BULLISH (>= 2) / BEARISH (<= -2) cut-offs. The windows fit inside the
  ~1 year of daily bars the site already fetches. The backtest script lives
  in tools/backtest/.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    # No losses at all in the window → RSI is 100 by definition; no gains and
    # no losses (flat price / warm-up) → neutral 50.
    out = out.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    return out.fillna(50)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "hist": hist}


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> dict:
    mid = close.rolling(window=window, min_periods=1).mean()
    std = close.rolling(window=window, min_periods=1).std(ddof=0).fillna(0)
    return {"mid": mid, "upper": mid + num_std * std, "lower": mid - num_std * std}


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's Average True Range (the standard smoothed definition)."""
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    prev_close = df["Close"].astype(float).shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def support_resistance(df: pd.DataFrame, lookback: int = 30) -> dict:
    recent = df.tail(lookback)
    if recent.empty:
        return {"support": None, "resistance": None}
    return {
        "support": float(recent["Low"].min()),
        "resistance": float(recent["High"].max()),
    }


MOMENTUM_SKIP = 21        # leave out the latest month (short-term reversal noise)
MOMENTUM_LOOKBACK = 230   # ~11 months; fits in a 1y daily fetch (~245 bars)
HIGH_WINDOW = 231
HIGH_MIN_BARS = 200


def momentum_11_1(close: pd.Series) -> float | None:
    """Return from ~11 months ago to 1 month ago, or None without enough history."""
    if len(close) <= MOMENTUM_LOOKBACK:
        return None
    start = float(close.iloc[-1 - MOMENTUM_LOOKBACK])
    end = float(close.iloc[-1 - MOMENTUM_SKIP])
    if not start or math.isnan(start) or math.isnan(end):
        return None
    return end / start - 1


def pct_of_year_high(close: pd.Series) -> float | None:
    """Latest close as a fraction of the highest close of the past ~year."""
    if len(close) < HIGH_MIN_BARS:
        return None
    hi = float(close.tail(HIGH_WINDOW).max())
    return float(close.iloc[-1]) / hi if hi else None


def trend_votes(close: float | None, sma200: float | None, mom: float | None, pct_high: float | None) -> dict:
    """The three backtested trend votes (+1 / 0 / -1 each, 0 when data is missing)."""
    votes = {"long_trend": 0, "momentum": 0, "year_high": 0}
    if close and sma200:
        gap = close / sma200 - 1
        votes["long_trend"] = 1 if gap > 0.05 else (-1 if gap < -0.05 else 0)
    if mom is not None:
        votes["momentum"] = 1 if mom > 0.10 else (-1 if mom < -0.10 else 0)
    if pct_high is not None:
        votes["year_high"] = 1 if pct_high >= 0.90 else (-1 if pct_high < 0.75 else 0)
    return votes


def _last(s: pd.Series) -> float | None:
    """Latest value as a float, or None when the series is empty or still warming up (NaN)."""
    if not len(s):
        return None
    v = float(s.iloc[-1])
    return None if math.isnan(v) else v


def compute_all(df: pd.DataFrame) -> dict:
    """Run every indicator and return latest scalar values + the signal verdict."""
    if df is None or df.empty or "Close" not in df:
        return {}

    close = df["Close"].astype(float)
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    sma200 = sma(close, 200)
    rsi14 = rsi(close, 14)
    macd_d = macd(close)
    bb = bollinger(close)
    sr = support_resistance(df)

    latest_close = _last(close)
    latest_sma20 = _last(sma20)
    latest_sma50 = _last(sma50)
    latest_rsi = _last(rsi14)
    latest_macd = _last(macd_d["macd"])
    latest_signal = _last(macd_d["signal"])
    latest_sma200 = _last(sma200)
    mom = momentum_11_1(close)
    pct_high = pct_of_year_high(close)

    # Score-based signal: the three backtested trend votes (see module docstring)
    votes = trend_votes(latest_close, latest_sma200, mom, pct_high)
    score = sum(votes.values())

    if score >= 2:
        verdict = "BULLISH"
    elif score <= -2:
        verdict = "BEARISH"
    else:
        verdict = "NEUTRAL"

    return {
        "close": latest_close,
        "sma20": latest_sma20,
        "sma50": latest_sma50,
        "sma200": latest_sma200,
        "momentum_11m": mom,
        "pct_of_high": pct_high,
        "votes": votes,
        "rsi": latest_rsi,
        "macd": latest_macd,
        "macd_signal": latest_signal,
        "bb_upper": _last(bb["upper"]),
        "bb_lower": _last(bb["lower"]),
        "support": sr["support"],
        "resistance": sr["resistance"],
        "verdict": verdict,
        "score": score,
    }
