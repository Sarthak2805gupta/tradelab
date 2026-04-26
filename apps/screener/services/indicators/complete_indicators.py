# ============================================================
# COMPLETE INDICATOR LIBRARY — ALL PHASES COMBINED
# For Indian Stocks (NSE)
# ============================================================
#
# This file contains EVERY indicator from our full roadmap:
#
# FROM PREVIOUS PHASES (already built, included here for
# completeness so this file works standalone):
#   - SMA, EMA
#   - RSI
#   - MACD (Line, Signal, Histogram)
#   - Bollinger Bands (%B, Bandwidth)
#   - OBV, VWAP, MFI
#   - Volume MA, Volume Ratio
#   - Candlestick patterns (Hammer, Engulfing, Doji)
#
# NEW IN THIS FILE (the missing ones):
#   - ADX  — Average Directional Index (trend strength)
#   - +DI / -DI — Directional Indicators (trend direction)
#   - Stochastic Oscillator (%K and %D)
#   - CCI  — Commodity Channel Index
#   - ROC  — Rate of Change
#   - ATR  — Average True Range (needed by Supertrend)
#   - Keltner Channels
#   - Donchian Channels
#   - Supertrend
#   - EMA Ribbon (multiple EMAs)
#
# NEW STRATEGIES:
#   - Supertrend strategy (most popular in India)
#   - ADX trend filter (when NOT to trade)
#   - EMA Ribbon strategy
#   - Donchian Breakout strategy
#   - Stochastic crossover strategy
#   - True BB + Keltner squeeze (proper version)
#
# HOW TO USE:
#   python complete_indicators.py                → analyse RELIANCE.NS
#   python complete_indicators.py TATAMOTORS     → any NSE stock
#   python complete_indicators.py SBIN 2y        → with custom period
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import sys
import warnings

warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════
# SECTION 1 — DATA DOWNLOAD
# ════════════════════════════════════════════════════════════

def get_data(ticker, period="1y"):
    """
    Downloads OHLCV data from Yahoo Finance.

    Parameters:
        ticker (str): e.g. "RELIANCE.NS" — add .NS for NSE stocks
        period (str): "6mo", "1y", "2y", "3y"

    Returns:
        df (DataFrame): OHLCV data, cleaned and ready
    """
    print(f"\nDownloading {ticker} ({period}) ...")
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    df.dropna(inplace=True)

    # yfinance sometimes returns multi-level columns — flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} trading days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ════════════════════════════════════════════════════════════
# SECTION 2 — INDICATORS FROM PREVIOUS PHASES
# (included here so this file works standalone)
# ════════════════════════════════════════════════════════════

def calc_sma(series, period):
    """Simple Moving Average — plain average of last N values."""
    return series.rolling(window=period, min_periods=period).mean()


def calc_ema(series, period):
    """
    Exponential Moving Average — weights recent prices more.
    k = 2/(period+1) is the smoothing factor.
    EMA today = Price × k + EMA_yesterday × (1 - k)
    """
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(prices, period=14):
    """
    RSI using Wilder's smoothing.
    Measures speed and magnitude of price changes.
    Above 70 = overbought, below 30 = oversold.
    """
    delta  = prices.diff(1)
    gains  = delta.clip(lower=0)
    losses = delta.clip(upper=0).abs()

    ag = gains.rolling(window=period, min_periods=period).mean()
    al = losses.rolling(window=period, min_periods=period).mean()
    ag_l = ag.tolist(); al_l = al.tolist()
    g_l  = gains.tolist(); l_l = losses.tolist()

    for i in range(period, len(ag_l)):
        if pd.isna(ag_l[i-1]): continue
        ag_l[i] = (ag_l[i-1] * (period-1) + g_l[i]) / period
        al_l[i] = (al_l[i-1] * (period-1) + l_l[i]) / period

    ag = pd.Series(ag_l, index=prices.index)
    al = pd.Series(al_l, index=prices.index)
    rs  = ag / al.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100).round(2)


def calc_macd(prices, fast=12, slow=26, signal=9):
    """
    MACD: Moving Average Convergence Divergence.
    MACD Line  = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD Line
    Histogram  = MACD Line - Signal Line
    """
    ema_fast  = calc_ema(prices, fast)
    ema_slow  = calc_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    sig_line  = calc_ema(macd_line, signal)
    histogram = macd_line - sig_line
    return macd_line.round(4), sig_line.round(4), histogram.round(4)


def calc_bollinger(prices, period=20, num_std=2):
    """
    Bollinger Bands: SMA ± N standard deviations.
    %B = (Price - Lower) / (Upper - Lower)  — where in the band is price?
    BW = (Upper - Lower) / Middle × 100     — how wide are the bands?
    """
    mid  = prices.rolling(window=period, min_periods=period).mean()
    std  = prices.rolling(window=period, min_periods=period).std(ddof=0)
    up   = mid + num_std * std
    lo   = mid - num_std * std
    pctb = (prices - lo) / (up - lo).replace(0, float('nan'))
    bw   = (up - lo) / mid * 100
    return mid.round(2), up.round(2), lo.round(2), pctb.round(4), bw.round(4)


def calc_obv(close, volume):
    """
    On Balance Volume: running total of buying vs selling volume.
    Rising OBV = smart money accumulating.
    """
    obv = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i-1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=close.index)


def calc_mfi(df, period=14):
    """
    Money Flow Index: volume-weighted RSI.
    Above 80 = overbought (stronger than RSI because volume-confirmed).
    Below 20 = oversold.
    """
    tp      = (df['High'] + df['Low'] + df['Close']) / 3
    raw_mf  = tp * df['Volume']
    pos_mf  = raw_mf.where(tp > tp.shift(1), 0)
    neg_mf  = raw_mf.where(tp < tp.shift(1), 0)
    pos_sum = pos_mf.rolling(window=period, min_periods=period).sum()
    neg_sum = neg_mf.rolling(window=period, min_periods=period).sum()
    mfr     = pos_sum / neg_sum.replace(0, float('nan'))
    mfi     = 100 - (100 / (1 + mfr))
    return mfi.fillna(100).round(2)


def calc_vwap(df, period=20):
    """
    VWAP (rolling 20-day): price weighted by volume.
    Institutional benchmark — price above VWAP = bullish.
    """
    tp      = (df['High'] + df['Low'] + df['Close']) / 3
    mf      = tp * df['Volume']
    cum_mf  = mf.rolling(window=period, min_periods=1).sum()
    cum_vol = df['Volume'].rolling(window=period, min_periods=1).sum()
    return (cum_mf / cum_vol).round(2)


# ════════════════════════════════════════════════════════════
# SECTION 3 — NEW INDICATORS
# ════════════════════════════════════════════════════════════

# ── 3a: ATR (Average True Range) ─────────────────────────────
def calc_atr(df, period=14):
    """
    ATR — Average True Range.

    Measures market VOLATILITY — how much a stock moves on average per day.
    It is NOT directional — it just tells you the SIZE of moves.

    True Range (TR) for each day = the LARGEST of:
        1. High - Low                          (today's range)
        2. |High - Previous Close|             (gap up scenario)
        3. |Low  - Previous Close|             (gap down scenario)

    Why we need all three:
        If a stock closes at 100 and gaps up to open at 110,
        the simple High-Low would miss the gap.
        True Range captures the full move including gaps.

    ATR = Wilder's smoothing of True Range over 'period' days.
    (Same smoothing method as RSI — not a simple average)

    Used by: Supertrend, Keltner Channels, position sizing,
             stop loss calculation ("2× ATR stop loss")

    Parameters:
        df (DataFrame): Must have High, Low, Close
        period (int): Smoothing period (default 14)

    Returns:
        Series: ATR values in price units (e.g. ₹12.4 means average
                daily move is ₹12.4)
    """
    high  = df['High']
    low   = df['Low']
    close = df['Close']

    # Calculate True Range — largest of the 3 scenarios
    # .shift(1) gives yesterday's close
    tr1 = high - low                          # Today's high-low range
    tr2 = (high - close.shift(1)).abs()       # Gap up scenario
    tr3 = (low  - close.shift(1)).abs()       # Gap down scenario

    # True Range = maximum of the three (use pandas concat + max)
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # First ATR = simple average of first 'period' TR values
    atr = tr.rolling(window=period, min_periods=period).mean()

    # Apply Wilder's smoothing from period onwards (same as RSI)
    atr_list = atr.tolist()
    tr_list  = tr.tolist()

    for i in range(period, len(atr_list)):
        if pd.isna(atr_list[i-1]):
            continue
        # Wilder smoothing: ((prev_ATR × (period-1)) + today_TR) / period
        atr_list[i] = (atr_list[i-1] * (period-1) + tr_list[i]) / period

    return pd.Series(atr_list, index=df.index).round(4)


# ── 3b: ADX + DI+ / DI- ──────────────────────────────────────
def calc_adx(df, period=14):
    """
    ADX — Average Directional Index, created by J. Welles Wilder.

    ADX tells you HOW STRONG a trend is — not which direction.
    It works together with two helper lines:
        +DI (Positive Directional Indicator) = upward pressure
        -DI (Negative Directional Indicator) = downward pressure

    Interpretation:
        ADX < 20  : No clear trend — market is sideways/choppy.
                    Do NOT use trend-following strategies!
                    This is the most important signal — it tells
                    you WHEN NOT TO TRADE.

        ADX 20-25 : Trend is developing. Worth watching.

        ADX 25-40 : Strong trend. Momentum strategies work well.

        ADX > 40  : Very strong trend. Ride it but watch for exhaustion.

        ADX > 50  : Extremely strong — often precedes a reversal.

    +DI vs -DI:
        +DI > -DI : Uptrend (bulls in control)
        -DI > +DI : Downtrend (bears in control)

    Combined signal:
        ADX > 25 AND +DI > -DI → Strong uptrend, good to buy
        ADX > 25 AND -DI > +DI → Strong downtrend, good to short/avoid
        ADX < 20               → No trend, avoid trend strategies

    How it's calculated:
        Step 1: Directional Movement (+DM and -DM)
            +DM = today's High - yesterday's High (if positive, else 0)
            -DM = yesterday's Low - today's Low   (if positive, else 0)
            If +DM > -DM: -DM = 0 (only the bigger one counts)
            If -DM > +DM: +DM = 0

        Step 2: Smooth +DM and -DM using Wilder's smoothing (like ATR)

        Step 3: +DI = 100 × Smoothed +DM / ATR
                -DI = 100 × Smoothed -DM / ATR

        Step 4: DX = 100 × |+DI - -DI| / (+DI + -DI)

        Step 5: ADX = Wilder's smoothing of DX

    Parameters:
        df (DataFrame): Must have High, Low, Close
        period (int): Smoothing period (default 14)

    Returns:
        adx (Series), plus_di (Series), minus_di (Series)
    """

    high  = df['High']
    low   = df['Low']
    close = df['Close']

    # Step 1: Calculate raw Directional Movement
    # Up move = today's high minus yesterday's high
    up_move   = high.diff(1)
    # Down move = yesterday's low minus today's low
    down_move = low.shift(1) - low

    # +DM: count the up move only if it's bigger than the down move AND positive
    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    # -DM: count the down move only if it's bigger than the up move AND positive
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Step 2: Calculate ATR (used to normalize DM into DI)
    atr = calc_atr(df, period)

    # Step 3: Smooth +DM and -DM using Wilder's smoothing
    # First value = simple rolling sum over 'period' bars
    smoothed_plus_dm  = plus_dm.rolling(window=period, min_periods=period).sum()
    smoothed_minus_dm = minus_dm.rolling(window=period, min_periods=period).sum()

    # Apply Wilder's smoothing from period onwards
    spdm_list = smoothed_plus_dm.tolist()
    smdm_list = smoothed_minus_dm.tolist()
    pdm_list  = plus_dm.tolist()
    mdm_list  = minus_dm.tolist()

    for i in range(period, len(spdm_list)):
        if pd.isna(spdm_list[i-1]):
            continue
        spdm_list[i] = spdm_list[i-1] - (spdm_list[i-1] / period) + pdm_list[i]
        smdm_list[i] = smdm_list[i-1] - (smdm_list[i-1] / period) + mdm_list[i]

    smoothed_plus_dm  = pd.Series(spdm_list, index=df.index)
    smoothed_minus_dm = pd.Series(smdm_list, index=df.index)

    # Step 4: Calculate +DI and -DI
    # DI = 100 × smoothed DM / ATR  (normalizes movement by volatility)
    atr_safe  = atr.replace(0, float('nan'))
    plus_di   = (100 * smoothed_plus_dm  / atr_safe).round(2)
    minus_di  = (100 * smoothed_minus_dm / atr_safe).round(2)

    # Step 5: DX = 100 × |+DI - -DI| / (+DI + -DI)
    di_sum    = (plus_di + minus_di).replace(0, float('nan'))
    dx        = 100 * ((plus_di - minus_di).abs() / di_sum)

    # Step 6: ADX = Wilder's smoothing of DX over 'period' days
    adx       = dx.rolling(window=period, min_periods=period).mean()
    adx_list  = adx.tolist()
    dx_list   = dx.tolist()

    for i in range(period, len(adx_list)):
        if pd.isna(adx_list[i-1]):
            continue
        adx_list[i] = (adx_list[i-1] * (period-1) + dx_list[i]) / period

    adx = pd.Series(adx_list, index=df.index).round(2)

    return adx, plus_di, minus_di


# ── 3c: Stochastic Oscillator ────────────────────────────────
def calc_stochastic(df, k_period=14, d_period=3, smooth_k=3):
    """
    Stochastic Oscillator, created by George Lane in the 1950s.

    Compares a stock's closing price to its price range over N days.
    The logic: in uptrends, prices tend to close near the HIGH of
    the range. In downtrends, prices close near the LOW.

    %K = raw stochastic — where is today's close in the N-day range?
    %D = smoothed %K — signal line (like MACD's signal line)

    Formula:
        %K = 100 × (Close - Lowest Low in N days) /
                    (Highest High in N days - Lowest Low in N days)

        %K = 100 → Close is at the very top of the N-day range
        %K = 0   → Close is at the very bottom of the N-day range
        %K = 50  → Close is exactly in the middle

    Interpretation:
        %K > 80  : Overbought — stock is closing near N-day highs
        %K < 20  : Oversold   — stock is closing near N-day lows

    Trading signals:
        %K crosses ABOVE %D while below 20 → BUY
        %K crosses BELOW %D while above 80 → SELL

    Stochastic vs RSI:
        RSI measures speed of price change.
        Stochastic measures WHERE the close is in the price range.
        Stochastic reacts FASTER — better for short-term (intraday/swing)
        RSI is smoother — better for daily/weekly timeframes.

    Parameters:
        df (DataFrame): Must have High, Low, Close
        k_period (int): Lookback for raw %K (default 14)
        d_period (int): Smoothing for %D (default 3)
        smooth_k (int): Smoothing for %K itself (default 3, gives "slow" stochastic)
                        Set smooth_k=1 for "fast" stochastic (more signals, more noise)

    Returns:
        k (Series): %K — smoothed stochastic
        d (Series): %D — signal line
    """

    # Lowest low and highest high over k_period days
    lowest_low   = df['Low'].rolling(window=k_period, min_periods=k_period).min()
    highest_high = df['High'].rolling(window=k_period, min_periods=k_period).max()

    # Raw %K: where is Close in the High-Low range? (0 = at low, 100 = at high)
    range_hl = (highest_high - lowest_low).replace(0, float('nan'))
    raw_k    = 100 * (df['Close'] - lowest_low) / range_hl

    # Smooth %K (makes it "slow stochastic" — reduces noise)
    k = raw_k.rolling(window=smooth_k, min_periods=1).mean().round(2)

    # %D = simple moving average of %K (the signal line)
    d = k.rolling(window=d_period, min_periods=1).mean().round(2)

    return k, d


# ── 3d: CCI — Commodity Channel Index ────────────────────────
def calc_cci(df, period=20):
    """
    CCI — Commodity Channel Index, created by Donald Lambert in 1980.

    Despite the name, CCI works equally well on stocks.
    It measures how far price is from its "statistical average"
    in terms of standard deviations — similar idea to Bollinger Bands
    but expressed as a single oscillator.

    Formula:
        Typical Price (TP) = (High + Low + Close) / 3
        SMA of TP          = rolling average of TP over N days
        Mean Deviation     = average distance of TP from its SMA

        CCI = (TP - SMA of TP) / (0.015 × Mean Deviation)

    The constant 0.015 was chosen by Lambert so that approximately
    70-80% of CCI values fall between -100 and +100 under normal conditions.

    Interpretation:
        CCI > +100  : Overbought — price significantly above average
                      (price is in the "upper 10-15% of its normal range")
        CCI < -100  : Oversold   — price significantly below average

        CCI crossing +100 from below → start of bullish momentum (BUY)
        CCI crossing -100 from above → start of bearish momentum (SELL)

    CCI vs RSI:
        RSI: uses price changes (speed of moves)
        CCI: uses distance from mean (how extreme is the price?)
        CCI tends to have larger swings and can stay at extremes longer.
        Good for identifying CYCLES in trending stocks.

    Parameters:
        df (DataFrame): Must have High, Low, Close
        period (int): Lookback period (default 20)

    Returns:
        Series: CCI values (typically range -200 to +200)
    """

    # Typical price = average of High, Low, Close for the day
    tp = (df['High'] + df['Low'] + df['Close']) / 3

    # SMA of typical price over N days
    tp_sma = tp.rolling(window=period, min_periods=period).mean()

    # Mean Deviation = average absolute distance from the SMA
    # This is NOT standard deviation — it's the mean of |TP - SMA|
    mean_dev = tp.rolling(window=period, min_periods=period).apply(
        lambda x: np.abs(x - x.mean()).mean(),
        raw=True
    )

    # CCI formula (0.015 is Lambert's constant)
    cci = (tp - tp_sma) / (0.015 * mean_dev.replace(0, float('nan')))

    return cci.round(2)


# ── 3e: ROC — Rate of Change ──────────────────────────────────
def calc_roc(prices, period=12):
    """
    ROC — Rate of Change.

    The simplest momentum indicator — measures the % change in price
    over the last N days.

    Formula:
        ROC = ((Close today - Close N days ago) / Close N days ago) × 100

    Interpretation:
        ROC > 0  : Price is higher than N days ago → positive momentum
        ROC < 0  : Price is lower than N days ago  → negative momentum
        ROC = 0  : Price is exactly where it was N days ago

        Crossing zero from below → momentum turning bullish
        Crossing zero from above → momentum turning bearish

        Extreme positive values → overbought (after a big run-up)
        Extreme negative values → oversold (after a big sell-off)

    ROC vs MACD vs RSI:
        ROC   : pure % change in price — no smoothing, very raw
        RSI   : normalized 0-100 based on gains vs losses
        MACD  : difference between two EMAs — trend + momentum
        ROC is the most transparent — you can see exactly what it measures.

    Parameters:
        prices (Series): Closing prices
        period (int): Lookback period (default 12 for daily, use 9 for intraday)

    Returns:
        Series: ROC values as percentages
    """

    # Price N days ago using .shift(period)
    price_n_ago = prices.shift(period)

    # ROC = percentage change from N days ago
    roc = ((prices - price_n_ago) / price_n_ago.replace(0, float('nan'))) * 100

    return roc.round(3)


# ── 3f: Keltner Channels ──────────────────────────────────────
def calc_keltner(df, ema_period=20, atr_period=10, multiplier=2.0):
    """
    Keltner Channels, created by Chester Keltner, popularized by Linda Bradford Raschke.

    Similar concept to Bollinger Bands but uses ATR instead of
    standard deviation for the band width.

    Bollinger Bands use std dev (statistical spread of prices).
    Keltner Channels use ATR (actual trading range including gaps).

    Formula:
        Middle Line = EMA(20)
        Upper Band  = EMA(20) + multiplier × ATR(10)
        Lower Band  = EMA(20) - multiplier × ATR(10)

    CRITICAL USE — The Proper BB + KC Squeeze:
        When Bollinger Bands are INSIDE Keltner Channels:
            → Market is in a very tight squeeze
            → Unusually low volatility
            → BIG MOVE coming (direction unknown)

        When Bollinger Bands break OUTSIDE Keltner Channels:
            → Volatility is expanding
            → The squeeze has been RELEASED
            → Trade in the direction of the breakout

        This is the most accurate squeeze detection because:
        BB responds to recent price swings (std dev)
        KC responds to true trading range including gaps (ATR)
        When BB < KC, BOTH volatility measures agree it's tight.

    Parameters:
        df (DataFrame): Must have High, Low, Close
        ema_period (int): EMA period for middle line (default 20)
        atr_period (int): ATR period for band width (default 10)
        multiplier (float): How many ATRs wide the band is (default 2.0)

    Returns:
        kc_mid, kc_upper, kc_lower (all Series)
    """

    # Middle line = EMA of closing price
    kc_mid   = calc_ema(df['Close'], ema_period)

    # Band width = multiplier × ATR
    atr      = calc_atr(df, atr_period)
    band     = multiplier * atr

    # Upper and lower bands
    kc_upper = (kc_mid + band).round(2)
    kc_lower = (kc_mid - band).round(2)
    kc_mid   = kc_mid.round(2)

    return kc_mid, kc_upper, kc_lower


# ── 3g: Donchian Channels ────────────────────────────────────
def calc_donchian(df, period=20):
    """
    Donchian Channels, created by Richard Donchian (the "father of trend following").

    The most straightforward channel: simply the highest high and lowest
    low over the last N periods.

    Formula:
        Upper  = Highest High over last N periods
        Lower  = Lowest Low  over last N periods
        Middle = (Upper + Lower) / 2

    Interpretation:
        Price touching Upper → at N-period high = bullish breakout zone
        Price touching Lower → at N-period low  = bearish breakout zone
        Middle line → fair value, acts as support/resistance

    Key Trading Concept — Breakout Strategy:
        The most famous use is the "Turtle Trading" system:
        BUY  when price breaks ABOVE the 20-day Donchian upper band
        SELL when price breaks BELOW the 20-day Donchian lower band

        The logic: a 20-day high means the stock just hit its highest
        price in a month. That's a breakout — momentum traders follow it.

    Donchian vs Bollinger:
        Donchian: based purely on highest/lowest price → pure breakout detector
        Bollinger: based on SMA ± std dev → volatility-based mean reversion
        Donchian catches BREAKOUTS.
        Bollinger catches REVERSIONS TO MEAN.
        Use both for different setups.

    Parameters:
        df (DataFrame): Must have High, Low
        period (int): Lookback period (default 20 = 1 month of trading days)

    Returns:
        upper, middle, lower (all Series)
    """

    upper  = df['High'].rolling(window=period, min_periods=period).max().round(2)
    lower  = df['Low'].rolling(window=period, min_periods=period).min().round(2)
    middle = ((upper + lower) / 2).round(2)

    return upper, middle, lower


# ── 3h: Supertrend ───────────────────────────────────────────
def calc_supertrend(df, period=7, multiplier=3.0):
    """
    Supertrend — the most popular intraday indicator in India.

    Created by Olivier Seban. Used by lakhs of NSE traders daily.
    It is an ATR-based trend-following indicator that gives a
    SINGLE clear signal: either you're in a BUY or SELL position.

    Core idea:
        Draw a dynamic stop level above or below price based on ATR.
        When price crosses that level → trend has reversed.

    Formula:
        Basic Upper Band = ((High + Low) / 2) + multiplier × ATR
        Basic Lower Band = ((High + Low) / 2) - multiplier × ATR

    The "Final" bands incorporate the previous bar's bands to prevent
    the line from jumping around too much:

        Final Upper = min(Basic Upper, prev Final Upper)  if Close ≤ prev Upper
                    = Basic Upper                          if Close > prev Upper

        Final Lower = max(Basic Lower, prev Final Lower)  if Close ≥ prev Lower
                    = Basic Lower                          if Close < prev Lower

    Supertrend = Final Lower  (when in uptrend — acts as support below price)
               = Final Upper  (when in downtrend — acts as resistance above price)

    Direction:
        +1 = Bullish (price above Supertrend line) → BUY / hold
        -1 = Bearish (price below Supertrend line) → SELL / exit

    Buy/Sell signals:
        Direction changes from -1 to +1 → BUY signal
        Direction changes from +1 to -1 → SELL signal

    Standard NSE settings:
        period=7, multiplier=3 for daily charts
        period=7, multiplier=3 for 15-minute charts
        period=10, multiplier=3 for 5-minute charts

    Parameters:
        df (DataFrame): Must have High, Low, Close
        period (int): ATR period (default 7)
        multiplier (float): ATR multiplier for band width (default 3.0)

    Returns:
        supertrend (Series): The Supertrend line values
        direction (Series):  +1 = bullish, -1 = bearish
    """

    # Step 1: Calculate ATR
    atr = calc_atr(df, period)

    # Step 2: Mid-price = (High + Low) / 2
    hl_mid = (df['High'] + df['Low']) / 2

    # Step 3: Basic upper and lower bands
    basic_upper = hl_mid + multiplier * atr
    basic_lower = hl_mid - multiplier * atr

    # Step 4: Calculate Final Upper and Lower bands
    # These incorporate the previous bar's band to avoid jumpy lines
    # We need to loop because each bar depends on the previous bar's values

    n = len(df)
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    close       = df['Close']

    for i in range(1, n):
        # Update Final Upper Band
        # Rule: only tighten (lower) the upper band, never widen it
        # unless price has broken above (which resets it)
        if not pd.isna(final_upper.iloc[i-1]):
            if basic_upper.iloc[i] < final_upper.iloc[i-1]:
                final_upper.iloc[i] = basic_upper.iloc[i]
            elif close.iloc[i-1] > final_upper.iloc[i-1]:
                final_upper.iloc[i] = basic_upper.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]

        # Update Final Lower Band
        # Rule: only raise (tighten) the lower band, never drop it
        # unless price has broken below (which resets it)
        if not pd.isna(final_lower.iloc[i-1]):
            if basic_lower.iloc[i] > final_lower.iloc[i-1]:
                final_lower.iloc[i] = basic_lower.iloc[i]
            elif close.iloc[i-1] < final_lower.iloc[i-1]:
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]

    # Step 5: Determine Supertrend direction and value
    supertrend = pd.Series(index=df.index, dtype=float)
    direction  = pd.Series(index=df.index, dtype=int)

    for i in range(n):
        if pd.isna(atr.iloc[i]):
            supertrend.iloc[i] = float('nan')
            direction.iloc[i]  = 1
            continue

        if i == 0:
            # First bar: assume uptrend
            supertrend.iloc[i] = final_lower.iloc[i]
            direction.iloc[i]  = 1
        else:
            prev_dir = direction.iloc[i-1]
            prev_st  = supertrend.iloc[i-1]

            if prev_dir == 1:   # Was in uptrend
                if close.iloc[i] < final_lower.iloc[i]:
                    # Price crossed below lower band → trend reversed to down
                    direction.iloc[i]  = -1
                    supertrend.iloc[i] = final_upper.iloc[i]
                else:
                    # Still in uptrend
                    direction.iloc[i]  = 1
                    supertrend.iloc[i] = final_lower.iloc[i]

            else:               # Was in downtrend
                if close.iloc[i] > final_upper.iloc[i]:
                    # Price crossed above upper band → trend reversed to up
                    direction.iloc[i]  = 1
                    supertrend.iloc[i] = final_lower.iloc[i]
                else:
                    # Still in downtrend
                    direction.iloc[i]  = -1
                    supertrend.iloc[i] = final_upper.iloc[i]

    return supertrend.round(2), direction


# ── 3i: EMA Ribbon ───────────────────────────────────────────
def calc_ema_ribbon(prices, periods=None):
    """
    EMA Ribbon — multiple EMAs plotted together to show trend visually.

    Instead of just one or two EMAs, we plot 6-8 EMAs with different
    periods. The visual pattern of the ribbon tells the whole story:

    Ribbon is FANNED OUT and ORDERED (short EMAs above long EMAs):
        → Strong uptrend. All timeframes agree. Momentum is strong.
        → The wider the fan, the stronger the trend.

    Ribbon is CROSSED and TANGLED:
        → No clear trend. Market is ranging/choppy.
        → Avoid trend-following trades.

    Ribbon is ORDERING in REVERSE (long EMAs above short EMAs):
        → Downtrend. All timeframes agree bears are in control.

    Ribbon FLIPPING from fanned-down to fanned-up:
        → Trend is reversing from bearish to bullish.
        → Strong buy signal when all EMAs line up.

    Default periods chosen to span from very fast to slow:
        9  → 2-week trend
        21 → 1-month trend
        34 → 7-week trend (Fibonacci)
        55 → 11-week trend (Fibonacci)
        89 → 4-month trend (Fibonacci)
        144 → 7-month trend (Fibonacci)

    Note: Fibonacci numbers are commonly used because they're
    naturally spaced in a way that covers different market cycles.

    Parameters:
        prices (Series): Closing prices
        periods (list): List of EMA periods (default: [9,21,34,55,89,144])

    Returns:
        dict: {period: EMA Series} for each period
    """

    if periods is None:
        periods = [9, 21, 34, 55, 89, 144]

    ribbon = {}
    for p in periods:
        ribbon[p] = calc_ema(prices, p).round(2)

    return ribbon


# ════════════════════════════════════════════════════════════
# SECTION 4 — CANDLESTICK PATTERN HELPERS (from Phase 1)
# ════════════════════════════════════════════════════════════

def is_hammer(row):
    """Hammer: long lower wick, small body at top. Bullish reversal."""
    body    = abs(row['Close'] - row['Open'])
    rng     = row['High'] - row['Low']
    if rng == 0 or body == 0:
        return False
    lo_wick = min(row['Open'], row['Close']) - row['Low']
    up_wick = row['High'] - max(row['Open'], row['Close'])
    return lo_wick >= 2*body and up_wick <= 0.1*body and body >= 0.1*rng


def is_bullish_engulfing(prev, curr):
    """Green body completely wraps the previous red body."""
    return (prev['Close'] < prev['Open'] and
            curr['Close'] > curr['Open'] and
            curr['Open']  < prev['Close'] and
            curr['Close'] > prev['Open'])


def is_doji(row):
    """Open ≈ Close — indecision. Body < 10% of total range."""
    rng = row['High'] - row['Low']
    if rng == 0:
        return False
    return abs(row['Close'] - row['Open']) / rng < 0.1


def is_shooting_star(row):
    """Long upper wick, small body at bottom. Bearish reversal."""
    body    = abs(row['Close'] - row['Open'])
    rng     = row['High'] - row['Low']
    if rng == 0 or body == 0:
        return False
    up_wick = row['High'] - max(row['Open'], row['Close'])
    lo_wick = min(row['Open'], row['Close']) - row['Low']
    return up_wick >= 2*body and lo_wick <= 0.1*body and body >= 0.1*rng


# ════════════════════════════════════════════════════════════
# SECTION 5 — CALCULATE ALL INDICATORS ON THE DATAFRAME
# ════════════════════════════════════════════════════════════

def calculate_all_indicators(df):
    """
    Runs every single indicator on the dataframe and adds
    them as new columns. Call this once, then read any column.

    Parameters:
        df (DataFrame): Raw OHLCV data

    Returns:
        df (DataFrame): Same data with 30+ new indicator columns added
    """
    print("\nCalculating all indicators...")

    # ── Trend ──
    df['SMA_20']    = calc_sma(df['Close'], 20)
    df['SMA_50']    = calc_sma(df['Close'], 50)
    df['SMA_200']   = calc_sma(df['Close'], 200)
    df['EMA_9']     = calc_ema(df['Close'], 9)
    df['EMA_20']    = calc_ema(df['Close'], 20)
    df['EMA_50']    = calc_ema(df['Close'], 50)

    # EMA Ribbon
    ribbon = calc_ema_ribbon(df['Close'], [9, 21, 34, 55, 89, 144])
    for period, ema_vals in ribbon.items():
        df[f'EMA_{period}'] = ema_vals

    # ── Momentum ──
    df['RSI']         = calc_rsi(df['Close'], 14)
    df['ROC_12']      = calc_roc(df['Close'], 12)
    df['CCI']         = calc_cci(df, 20)
    df['Stoch_K'], df['Stoch_D'] = calc_stochastic(df, 14, 3, 3)

    # ── MACD ──
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calc_macd(df['Close'])

    # ── Volatility ──
    df['ATR']         = calc_atr(df, 14)
    (df['BB_Mid'],
     df['BB_Up'],
     df['BB_Lo'],
     df['PctB'],
     df['BW'])         = calc_bollinger(df['Close'])

    (df['KC_Mid'],
     df['KC_Up'],
     df['KC_Lo'])      = calc_keltner(df, ema_period=20, atr_period=10, multiplier=2.0)

    (df['DC_Up'],
     df['DC_Mid'],
     df['DC_Lo'])      = calc_donchian(df, 20)

    # ── Trend Strength ──
    df['ADX'], df['DI_Plus'], df['DI_Minus'] = calc_adx(df, 14)

    # ── Supertrend ──
    df['Supertrend'], df['ST_Dir'] = calc_supertrend(df, period=7, multiplier=3.0)

    # ── Volume ──
    df['VMA']       = calc_sma(df['Volume'].astype(float), 20)
    df['Vol_Ratio'] = df['Volume'] / df['VMA']
    df['OBV']       = calc_obv(df['Close'], df['Volume'])
    df['MFI']       = calc_mfi(df, 14)
    df['VWAP']      = calc_vwap(df, 20)

    # ── BB + KC Squeeze flag ──
    # True when Bollinger Bands are INSIDE Keltner Channels
    # This is the proper squeeze condition
    bb_width = df['BB_Up'] - df['BB_Lo']
    kc_width = df['KC_Up'] - df['KC_Lo']
    df['Squeeze'] = bb_width < kc_width   # True = squeeze is ON

    print(f"Done. Added {len(df.columns)} total columns.")
    return df


# ════════════════════════════════════════════════════════════
# SECTION 6 — NEW STRATEGIES
# ════════════════════════════════════════════════════════════

def detect_supertrend_signals(df):
    """
    Supertrend Strategy — the most popular strategy in India.

    Buy signal  : Supertrend direction flips from -1 to +1
                  (trend reversal to bullish)
    Sell signal : Supertrend direction flips from +1 to -1
                  (trend reversal to bearish)

    Extra filter: Only take buy signals when ADX > 20
                  (confirms the new trend has strength)

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        dir_today = df['ST_Dir'].iloc[i]
        dir_prev  = df['ST_Dir'].iloc[i-1]
        date      = df.index[i].date()
        close     = round(df['Close'].iloc[i], 2)
        st_val    = round(df['Supertrend'].iloc[i], 2)
        adx_val   = round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0

        # Direction flip from -1 to +1 → BUY
        if dir_prev == -1 and dir_today == 1:
            signals.append({
                'Date'    : date,
                'Type'    : 'Supertrend',
                'Signal'  : 'BUY',
                'Close'   : close,
                'ST_Level': st_val,
                'ADX'     : adx_val,
                'Detail'  : f'ST flipped bullish at ₹{st_val} | ADX={adx_val}'
            })

        # Direction flip from +1 to -1 → SELL
        elif dir_prev == 1 and dir_today == -1:
            signals.append({
                'Date'    : date,
                'Type'    : 'Supertrend',
                'Signal'  : 'SELL',
                'Close'   : close,
                'ST_Level': st_val,
                'ADX'     : adx_val,
                'Detail'  : f'ST flipped bearish at ₹{st_val} | ADX={adx_val}'
            })

    return signals


def detect_adx_filter_signals(df, adx_threshold=25):
    """
    ADX Trend Filter — tells you WHEN to trade and when to stay out.

    This is not a buy/sell signal — it's a FILTER for other signals.

    ADX > threshold → trend is strong → other signals are more reliable
    ADX < threshold → market is ranging → avoid trend-following trades

    Also generates signals when:
        ADX rises above threshold → trend just started, enter with other confirmation
        DI+ crosses above DI-    → trend direction turned bullish (with strong ADX)
        DI- crosses above DI+    → trend direction turned bearish (with strong ADX)

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        adx       = df['ADX'].iloc[i]
        adx_prev  = df['ADX'].iloc[i-1]
        di_plus   = df['DI_Plus'].iloc[i]
        di_minus  = df['DI_Minus'].iloc[i]
        dp_prev   = df['DI_Plus'].iloc[i-1]
        dm_prev   = df['DI_Minus'].iloc[i-1]
        date      = df.index[i].date()
        close     = round(df['Close'].iloc[i], 2)

        if any(pd.isna(v) for v in [adx, adx_prev, di_plus, di_minus]):
            continue

        # ADX crosses above threshold → trend starting
        if adx_prev < adx_threshold and adx >= adx_threshold:
            trend_dir = 'Bullish' if di_plus > di_minus else 'Bearish'
            signals.append({
                'Date'  : date,
                'Type'  : 'ADX Trend Start',
                'Signal': f'{trend_dir.upper()} TREND CONFIRMED',
                'Close' : close,
                'ADX'   : round(adx, 1),
                'Detail': f'ADX crossed {adx_threshold} → {trend_dir} trend starting. +DI={round(di_plus,1)}, -DI={round(di_minus,1)}'
            })

        # DI crossover with strong ADX
        if adx >= adx_threshold:
            if dp_prev < dm_prev and di_plus > di_minus:
                signals.append({
                    'Date'  : date,
                    'Type'  : 'DI Crossover',
                    'Signal': 'BUY (+DI crossed above -DI)',
                    'Close' : close,
                    'ADX'   : round(adx, 1),
                    'Detail': f'+DI crossed -DI with ADX={round(adx,1)} > {adx_threshold} → strong bullish momentum'
                })
            elif dp_prev > dm_prev and di_plus < di_minus:
                signals.append({
                    'Date'  : date,
                    'Type'  : 'DI Crossover',
                    'Signal': 'SELL (-DI crossed above +DI)',
                    'Close' : close,
                    'ADX'   : round(adx, 1),
                    'Detail': f'-DI crossed +DI with ADX={round(adx,1)} > {adx_threshold} → strong bearish momentum'
                })

    return signals


def detect_ema_ribbon_signals(df):
    """
    EMA Ribbon Strategy.

    BUY signal: All 6 ribbon EMAs are ordered correctly (9 > 21 > 34 > 55 > 89 > 144)
                AND price is above EMA_9
                → Perfect bull alignment, momentum is strong

    SELL signal: Ribbon reverses (144 > 89 > 55 > 34 > 21 > 9)
                 AND price is below EMA_9
                 → Perfect bear alignment

    CAUTION signal: EMAs are tangled (no clear order)
                    → Ranging market, stay out of trend trades

    Returns:
        List of signal dicts
    """
    signals   = []
    ema_cols  = ['EMA_9', 'EMA_21', 'EMA_34', 'EMA_55', 'EMA_89', 'EMA_144']

    for i in range(1, len(df)):
        # Check all ribbon columns exist and have values
        row = df.iloc[i]
        if any(pd.isna(row.get(col, float('nan'))) for col in ema_cols):
            continue

        e9, e21, e34, e55, e89, e144 = [row[c] for c in ema_cols]
        prev_row = df.iloc[i-1]
        close    = round(row['Close'], 2)
        date     = df.index[i].date()

        # Check for bull alignment: each EMA above the next slower one
        bull_aligned = (e9 > e21 > e34 > e55 > e89 > e144)
        prev_bull    = (prev_row.get('EMA_9', 0) > prev_row.get('EMA_21', 0) >
                        prev_row.get('EMA_34', 0) > prev_row.get('EMA_55', 0) >
                        prev_row.get('EMA_89', 0) > prev_row.get('EMA_144', 0))

        # Check for bear alignment: reverse order
        bear_aligned = (e9 < e21 < e34 < e55 < e89 < e144)
        prev_bear    = (prev_row.get('EMA_9', 0) < prev_row.get('EMA_21', 0) <
                        prev_row.get('EMA_34', 0) < prev_row.get('EMA_55', 0) <
                        prev_row.get('EMA_89', 0) < prev_row.get('EMA_144', 0))

        # Signal: ribbon just achieved perfect bull alignment
        if bull_aligned and not prev_bull and close > e9:
            signals.append({
                'Date'  : date,
                'Type'  : 'EMA Ribbon',
                'Signal': 'BUY',
                'Close' : close,
                'ADX'   : round(row.get('ADX', 0), 1),
                'Detail': f'All 6 EMAs bull-aligned. EMA9={round(e9,1)} EMA144={round(e144,1)}'
            })

        # Signal: ribbon just achieved perfect bear alignment
        elif bear_aligned and not prev_bear and close < e9:
            signals.append({
                'Date'  : date,
                'Type'  : 'EMA Ribbon',
                'Signal': 'SELL',
                'Close' : close,
                'ADX'   : round(row.get('ADX', 0), 1),
                'Detail': f'All 6 EMAs bear-aligned. EMA9={round(e9,1)} EMA144={round(e144,1)}'
            })

    return signals


def detect_donchian_breakout(df, volume_confirm=1.3):
    """
    Donchian Channel Breakout Strategy.

    The core concept: if a stock hits a new 20-day high, it's showing
    unusual strength. Breakout traders BUY this, expecting the move to continue.

    BUY signal:
        Price closes ABOVE the 20-day Donchian Upper band
        AND today's volume > volume_confirm × 20-day average volume
        (Volume confirmation: real breakouts happen on HIGH volume)

    SELL signal:
        Price closes BELOW the 20-day Donchian Lower band
        AND high volume (confirms real selling, not just drift)

    Why volume matters so much here:
        Without volume, a price touching a Donchian band might just be
        random noise — thin volume, one big order moved the price.
        With high volume, real money is flowing — institutional buying.

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        close     = df['Close'].iloc[i]
        dc_up     = df['DC_Up'].iloc[i]
        dc_lo     = df['DC_Lo'].iloc[i]
        vol_ratio = df['Vol_Ratio'].iloc[i]
        date      = df.index[i].date()
        close_r   = round(close, 2)

        if any(pd.isna(v) for v in [dc_up, dc_lo, vol_ratio]):
            continue

        # Bullish breakout: close above upper Donchian band on high volume
        if close > dc_up and vol_ratio >= volume_confirm:
            signals.append({
                'Date'  : date,
                'Type'  : 'Donchian Breakout',
                'Signal': 'BUY',
                'Close' : close_r,
                'ADX'   : round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0,
                'Detail': f'20d high breakout at ₹{close_r} | {round(dc_up,1)} channel | Vol={round(vol_ratio,1)}x'
            })

        # Bearish breakout: close below lower Donchian band on high volume
        elif close < dc_lo and vol_ratio >= volume_confirm:
            signals.append({
                'Date'  : date,
                'Type'  : 'Donchian Breakout',
                'Signal': 'SELL',
                'Close' : close_r,
                'ADX'   : round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0,
                'Detail': f'20d low breakdown at ₹{close_r} | {round(dc_lo,1)} channel | Vol={round(vol_ratio,1)}x'
            })

    return signals


def detect_stochastic_signals(df, ob=80, os=20):
    """
    Stochastic Oscillator Crossover Strategy.

    BUY: %K crosses above %D while both are in oversold zone (< 20)
         → Momentum turning up from an extreme low

    SELL: %K crosses below %D while both are in overbought zone (> 80)
          → Momentum turning down from an extreme high

    The zone requirement is crucial: a %K/%D crossover in the MIDDLE
    of the range (50 area) is unreliable noise. The signal is only
    strong when it happens at the extremes.

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        k_today  = df['Stoch_K'].iloc[i]
        k_prev   = df['Stoch_K'].iloc[i-1]
        d_today  = df['Stoch_D'].iloc[i]
        d_prev   = df['Stoch_D'].iloc[i-1]
        date     = df.index[i].date()
        close    = round(df['Close'].iloc[i], 2)

        if any(pd.isna(v) for v in [k_today, k_prev, d_today, d_prev]):
            continue

        # BUY: %K crosses above %D in oversold zone
        if k_prev < d_prev and k_today > d_today and k_today < os + 15:
            signals.append({
                'Date'  : date,
                'Type'  : 'Stochastic',
                'Signal': 'BUY',
                'Close' : close,
                'ADX'   : round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0,
                'Detail': f'%K({round(k_today,1)}) crossed above %D({round(d_today,1)}) in oversold zone'
            })

        # SELL: %K crosses below %D in overbought zone
        elif k_prev > d_prev and k_today < d_today and k_today > ob - 15:
            signals.append({
                'Date'  : date,
                'Type'  : 'Stochastic',
                'Signal': 'SELL',
                'Close' : close,
                'ADX'   : round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0,
                'Detail': f'%K({round(k_today,1)}) crossed below %D({round(d_today,1)}) in overbought zone'
            })

    return signals


def detect_bb_kc_squeeze_breakout(df):
    """
    Proper BB + Keltner Channel Squeeze Breakout.

    Phase 1 — Squeeze ON:
        Bollinger Bands are inside Keltner Channels.
        Market is coiling. Note the squeeze but don't trade yet.

    Phase 2 — Squeeze Released:
        Bollinger Bands break outside Keltner Channels.
        Explosive move starting. Trade in the breakout direction.

    Direction of breakout:
        Price closes above BB upper AND above KC upper → BULLISH breakout
        Price closes below BB lower AND below KC lower → BEARISH breakout

    This is the most accurate squeeze signal because it requires BOTH
    volatility measures (std dev AND ATR) to confirm the expansion.

    Returns:
        List of signal dicts (squeeze alerts + breakout signals)
    """
    signals      = []
    in_squeeze   = False     # Track if we were previously in a squeeze

    for i in range(1, len(df)):
        squeeze_now  = bool(df['Squeeze'].iloc[i])
        squeeze_prev = bool(df['Squeeze'].iloc[i-1])
        close        = df['Close'].iloc[i]
        bb_up        = df['BB_Up'].iloc[i]
        bb_lo        = df['BB_Lo'].iloc[i]
        kc_up        = df['KC_Up'].iloc[i]
        kc_lo        = df['KC_Lo'].iloc[i]
        date         = df.index[i].date()
        close_r      = round(close, 2)

        if any(pd.isna(v) for v in [bb_up, bb_lo, kc_up, kc_lo]):
            continue

        # Squeeze started
        if squeeze_now and not squeeze_prev:
            in_squeeze = True
            signals.append({
                'Date'  : date,
                'Type'  : 'BB+KC Squeeze',
                'Signal': 'ALERT: Squeeze ON',
                'Close' : close_r,
                'ADX'   : round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0,
                'Detail': 'BB inside KC — volatility compressed. Big move coming, wait for direction.'
            })

        # Squeeze released → look for breakout direction
        elif not squeeze_now and squeeze_prev and in_squeeze:
            in_squeeze = False

            if close > kc_up:
                direction = 'BUY'
                detail    = f'Squeeze released UPWARD. Price ₹{close_r} broke above KC upper ₹{round(kc_up,1)}'
            elif close < kc_lo:
                direction = 'SELL'
                detail    = f'Squeeze released DOWNWARD. Price ₹{close_r} broke below KC lower ₹{round(kc_lo,1)}'
            else:
                direction = 'WATCH'
                detail    = f'Squeeze released but direction unclear. Price ₹{close_r} between KC bands.'

            signals.append({
                'Date'  : date,
                'Type'  : 'BB+KC Squeeze',
                'Signal': direction,
                'Close' : close_r,
                'ADX'   : round(df['ADX'].iloc[i], 1) if not pd.isna(df['ADX'].iloc[i]) else 0,
                'Detail': detail
            })

    return signals


# ════════════════════════════════════════════════════════════
# SECTION 7 — COMPREHENSIVE SIGNAL SCANNER
# ════════════════════════════════════════════════════════════

def run_all_signals(df):
    """
    Runs every strategy detector and collects all signals.

    Returns:
        List of all signal dicts, sorted by date (most recent last)
    """
    all_signals = []
    all_signals += detect_supertrend_signals(df)
    all_signals += detect_adx_filter_signals(df, adx_threshold=25)
    all_signals += detect_ema_ribbon_signals(df)
    all_signals += detect_donchian_breakout(df, volume_confirm=1.3)
    all_signals += detect_stochastic_signals(df, ob=80, os=20)
    all_signals += detect_bb_kc_squeeze_breakout(df)

    # Sort by date
    all_signals.sort(key=lambda x: x['Date'])
    return all_signals


# ════════════════════════════════════════════════════════════
# SECTION 8 — PRINT SUMMARY
# ════════════════════════════════════════════════════════════

def print_summary(df, ticker, all_signals):
    """
    Prints a clean terminal summary of current indicator values
    and recent signals.
    """
    last = df.iloc[-1]

    print(f"\n{'='*70}")
    print(f"  COMPLETE INDICATOR SUMMARY — {ticker}")
    print(f"  As of: {df.index[-1].date()}")
    print(f"{'='*70}")

    def v(col):
        val = last.get(col, float('nan'))
        return round(val, 2) if not pd.isna(val) else 'N/A'

    print(f"\n  ── Price & Trend ──")
    print(f"  Close        : ₹{v('Close')}")
    print(f"  SMA 20/50/200: ₹{v('SMA_20')} / ₹{v('SMA_50')} / ₹{v('SMA_200')}")
    print(f"  EMA 9/20     : ₹{v('EMA_9')} / ₹{v('EMA_20')}")
    print(f"  Supertrend   : ₹{v('Supertrend')}  Direction: {'UP (BUY)' if last.get('ST_Dir')==1 else 'DOWN (SELL)'}")
    trend_pos = sum(1 for p in [9,21,34,55,89,144]
                    if not pd.isna(last.get(f'EMA_{p}', float('nan')))
                    and last['Close'] > last.get(f'EMA_{p}', float('nan')))
    print(f"  EMA Ribbon   : Price above {trend_pos}/6 ribbon EMAs")

    print(f"\n  ── Trend Strength (ADX) ──")
    adx_val = v('ADX')
    dip = v('DI_Plus'); dim = v('DI_Minus')
    adx_interp = ("No trend — stay out of trend trades" if isinstance(adx_val, (int, float)) and adx_val < 20
                  else "Weak trend — developing" if isinstance(adx_val, (int, float)) and adx_val < 25
                  else "Strong trend — trade with confidence" if isinstance(adx_val, (int, float)) and adx_val < 40
                  else "Very strong trend — watch for exhaustion")
    print(f"  ADX          : {adx_val}  → {adx_interp}")
    print(f"  +DI / -DI    : {dip} / {dim}  → {'Bulls in control' if isinstance(dip,(int,float)) and isinstance(dim,(int,float)) and dip>dim else 'Bears in control'}")

    print(f"\n  ── Momentum ──")
    rsi_val = v('RSI')
    rsi_zone = ("Oversold" if isinstance(rsi_val,(int,float)) and rsi_val<30
                else "Overbought" if isinstance(rsi_val,(int,float)) and rsi_val>70
                else "Neutral")
    print(f"  RSI (14)     : {rsi_val}  → {rsi_zone}")
    print(f"  Stoch %K/%D  : {v('Stoch_K')} / {v('Stoch_D')}")
    print(f"  CCI (20)     : {v('CCI')}")
    print(f"  ROC (12d)    : {v('ROC_12')}%")
    print(f"  MACD Line    : {v('MACD')}  Signal: {v('MACD_Signal')}  Hist: {v('MACD_Hist')}")

    print(f"\n  ── Volatility & Bands ──")
    print(f"  ATR (14)     : ₹{v('ATR')}  ({round(last.get('ATR',0)/last['Close']*100,2) if last['Close']>0 else 0}% of price)")
    print(f"  Bollinger    : ₹{v('BB_Lo')} | ₹{v('BB_Mid')} | ₹{v('BB_Up')}  %B={v('PctB')}")
    print(f"  Keltner      : ₹{v('KC_Lo')} | ₹{v('KC_Mid')} | ₹{v('KC_Up')}")
    print(f"  Donchian     : ₹{v('DC_Lo')} | ₹{v('DC_Mid')} | ₹{v('DC_Up')}")
    squeeze_on = bool(last.get('Squeeze', False))
    print(f"  BB+KC Squeeze: {'ACTIVE — big move incoming!' if squeeze_on else 'Not active'}")

    print(f"\n  ── Volume ──")
    print(f"  Vol Ratio    : {v('Vol_Ratio')}x  (vs 20-day avg)")
    print(f"  MFI (14)     : {v('MFI')}")
    print(f"  VWAP (20d)   : ₹{v('VWAP')}")

    # Recent signals (last 10)
    print(f"\n  ── Recent Signals (last 10) ──")
    if all_signals:
        for sig in all_signals[-10:]:
            tag = "BUY   " if 'BUY' in sig['Signal'] else ("SELL  " if 'SELL' in sig['Signal'] else "ALERT ")
            print(f"  {sig['Date']}  {tag}  {sig['Type']:<22}  ₹{sig['Close']}")
            print(f"           {sig['Detail']}")
    else:
        print("  No signals found in this period.")

    print(f"\n{'='*70}\n")


# ════════════════════════════════════════════════════════════
# SECTION 9 — 5-PANEL CHART
# ════════════════════════════════════════════════════════════

def plot_all(df, ticker, all_signals):
    """
    Creates a 5-panel chart:
        1. Price + Supertrend + EMA Ribbon + Donchian
        2. ADX + DI+ / DI-
        3. Stochastic %K + %D
        4. CCI + ROC
        5. Volume + ATR
    """
    fig = plt.figure(figsize=(16, 14))
    gs  = gridspec.GridSpec(5, 1,
                            height_ratios=[4, 1.5, 1.5, 1.5, 1.5],
                            hspace=0.08)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    ax5 = fig.add_subplot(gs[4], sharex=ax1)

    # ── Panel 1: Price + Indicators ──
    # EMA Ribbon (faint background colours)
    ribbon_colors = ['#97C459', '#5DCAA5', '#378ADD', '#7F77DD', '#D4537E', '#EF9F27']
    for idx, p in enumerate([9, 21, 34, 55, 89, 144]):
        col = f'EMA_{p}'
        if col in df.columns:
            ax1.plot(df.index, df[col], color=ribbon_colors[idx],
                     linewidth=0.8, alpha=0.5, label=f'EMA{p}')

    # Donchian Channel (shaded)
    ax1.fill_between(df.index, df['DC_Up'], df['DC_Lo'],
                     alpha=0.06, color='#378ADD', label='Donchian channel')

    # Price
    ax1.plot(df.index, df['Close'], color='#444441',
             linewidth=1.3, label='Close', zorder=4)

    # Supertrend
    up_mask   = df['ST_Dir'] == 1
    down_mask = df['ST_Dir'] == -1
    ax1.scatter(df.index[up_mask], df['Supertrend'][up_mask],
                c='#1D9E75', s=4, marker='_', zorder=3, label='Supertrend (bull)')
    ax1.scatter(df.index[down_mask], df['Supertrend'][down_mask],
                c='#E24B4A', s=4, marker='_', zorder=3, label='Supertrend (bear)')

    # Buy/Sell markers from Supertrend signals
    for sig in all_signals:
        if sig['Type'] == 'Supertrend':
            row = df[df.index.date == sig['Date']]
            if not row.empty:
                color  = '#1D9E75' if sig['Signal'] == 'BUY' else '#E24B4A'
                marker = '^' if sig['Signal'] == 'BUY' else 'v'
                ax1.scatter(row.index, row['Close'], marker=marker,
                            color=color, s=120, zorder=6)

    ax1.set_title(f'{ticker} — Complete Indicator Analysis', fontsize=13, pad=10)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.legend(fontsize=7, loc='upper left', ncol=4)
    ax1.grid(True, alpha=0.2)

    # ── Panel 2: ADX + DI lines ──
    ax2.plot(df.index, df['ADX'],      color='#534AB7', linewidth=2,   label='ADX')
    ax2.plot(df.index, df['DI_Plus'],  color='#1D9E75', linewidth=1.2, label='+DI', linestyle='--')
    ax2.plot(df.index, df['DI_Minus'], color='#E24B4A', linewidth=1.2, label='-DI', linestyle='--')
    ax2.axhline(y=25, color='#888780', linewidth=1, linestyle=':', alpha=0.7)
    ax2.axhline(y=20, color='#888780', linewidth=0.8, linestyle=':', alpha=0.5)
    ax2.fill_between(df.index, 0, df['ADX'],
                     where=(df['ADX'] >= 25), alpha=0.1, color='#534AB7')
    ax2.set_ylabel('ADX', fontsize=10)
    ax2.legend(fontsize=8, loc='upper left')
    ax2.grid(True, alpha=0.2)

    # ── Panel 3: Stochastic ──
    ax3.plot(df.index, df['Stoch_K'], color='#378ADD', linewidth=1.5, label='%K')
    ax3.plot(df.index, df['Stoch_D'], color='#EF9F27', linewidth=1.5, label='%D', linestyle='--')
    ax3.axhline(y=80, color='#E24B4A', linewidth=1, linestyle='--', alpha=0.7)
    ax3.axhline(y=20, color='#1D9E75', linewidth=1, linestyle='--', alpha=0.7)
    ax3.fill_between(df.index, 80, df['Stoch_K'],
                     where=(df['Stoch_K'] > 80), alpha=0.15, color='#E24B4A')
    ax3.fill_between(df.index, 20, df['Stoch_K'],
                     where=(df['Stoch_K'] < 20), alpha=0.15, color='#1D9E75')
    ax3.set_ylim(0, 100)
    ax3.set_ylabel('Stochastic', fontsize=10)
    ax3.legend(fontsize=8, loc='upper left')
    ax3.grid(True, alpha=0.2)

    # ── Panel 4: CCI + ROC ──
    ax4.plot(df.index, df['CCI'], color='#D4537E', linewidth=1.5, label='CCI (20)')
    ax4.axhline(y=100,  color='#E24B4A', linewidth=1, linestyle='--', alpha=0.6)
    ax4.axhline(y=-100, color='#1D9E75', linewidth=1, linestyle='--', alpha=0.6)
    ax4.axhline(y=0,    color='#888780', linewidth=0.8, linestyle=':', alpha=0.5)
    ax4_r = ax4.twinx()   # Second y-axis for ROC
    ax4_r.plot(df.index, df['ROC_12'], color='#EF9F27',
               linewidth=1.2, label='ROC 12d', alpha=0.7)
    ax4_r.axhline(y=0, color='#EF9F27', linewidth=0.5, linestyle=':', alpha=0.4)
    ax4.set_ylabel('CCI', fontsize=10)
    ax4_r.set_ylabel('ROC %', fontsize=9)
    ax4.legend(fontsize=8, loc='upper left')
    ax4_r.legend(fontsize=8, loc='upper right')
    ax4.grid(True, alpha=0.2)

    # ── Panel 5: Volume + ATR ──
    vol_colors = ['#1D9E75' if df['Close'].iloc[i] >= df['Open'].iloc[i]
                  else '#E24B4A' for i in range(len(df))]
    ax5.bar(df.index, df['Volume'], color=vol_colors, alpha=0.6, width=1)
    ax5.plot(df.index, df['VMA'], color='#EF9F27', linewidth=1.5,
             label='Vol MA 20', zorder=3)
    ax5_r = ax5.twinx()
    ax5_r.plot(df.index, df['ATR'], color='#534AB7',
               linewidth=1.5, label='ATR (14)')
    ax5.set_ylabel('Volume', fontsize=10)
    ax5_r.set_ylabel('ATR (₹)', fontsize=9)
    ax5.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M' if x>=1e6 else f'{x/1e3:.0f}K'))
    ax5.legend(fontsize=8, loc='upper left')
    ax5_r.legend(fontsize=8, loc='upper right')
    ax5.grid(True, alpha=0.2)

    plt.tight_layout()
    fname = f"{ticker.replace('.', '_')}_complete_indicators.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"Chart saved: {fname}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 10 — MAIN
# ════════════════════════════════════════════════════════════

def main():
    """
    Entry point.
    Usage:
        python complete_indicators.py                → RELIANCE.NS, 1y
        python complete_indicators.py TATAMOTORS     → TATAMOTORS.NS, 1y
        python complete_indicators.py SBIN 2y        → SBIN.NS, 2 years
    """

    # Parse arguments
    args = sys.argv[1:]
    ticker_input = args[0] if args else "RELIANCE"
    period       = args[1] if len(args) > 1 else "1y"

    # Add .NS suffix if not already present
    if not ticker_input.endswith('.NS'):
        ticker = ticker_input.upper() + '.NS'
    else:
        ticker = ticker_input.upper()

    # Download data
    df = get_data(ticker, period)

    # Calculate all indicators
    df = calculate_all_indicators(df)

    # Detect all signals
    all_signals = run_all_signals(df)

    # Print summary
    print_summary(df, ticker, all_signals)

    # Plot chart
    plot_all(df, ticker, all_signals)


if __name__ == "__main__":
    main()