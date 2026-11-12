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

    # Score-based signal
    score = 0
    if latest_sma20 and latest_sma50 and latest_sma20 > latest_sma50:
        score += 1
    elif latest_sma20 and latest_sma50:
        score -= 1
    if latest_rsi is not None:
        if latest_rsi > 60:
            score += 1
        elif latest_rsi < 40:
            score -= 1
    if latest_macd is not None and latest_signal is not None:
        if latest_macd > latest_signal:
            score += 1
        else:
            score -= 1

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
