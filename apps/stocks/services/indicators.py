"""
Pure-pandas/numpy technical indicators. All functions accept a DataFrame
with at least a 'Close' column (and 'High'/'Low' where required) and return
either a Series, dict, or scalar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=1).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "hist": hist}


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> dict:
    mid = close.rolling(window=window, min_periods=1).mean()
    std = close.rolling(window=window, min_periods=1).std().fillna(0)
    return {"mid": mid, "upper": mid + num_std * std, "lower": mid - num_std * std}


def support_resistance(df: pd.DataFrame, lookback: int = 30) -> dict:
    recent = df.tail(lookback)
    if recent.empty:
        return {"support": None, "resistance": None}
    return {
        "support": float(recent["Low"].min()),
        "resistance": float(recent["High"].max()),
    }


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

    last = lambda s: float(s.iloc[-1]) if len(s) else None

    latest_close = last(close)
    latest_sma20 = last(sma20)
    latest_sma50 = last(sma50)
    latest_rsi = last(rsi14)
    latest_macd = last(macd_d["macd"])
    latest_signal = last(macd_d["signal"])

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
        "bb_upper": last(bb["upper"]),
        "bb_lower": last(bb["lower"]),
        "support": sr["support"],
        "resistance": sr["resistance"],
        "verdict": verdict,
        "score": score,
    }
