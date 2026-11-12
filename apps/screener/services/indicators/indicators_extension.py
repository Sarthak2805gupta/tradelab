# ============================================================
# INDICATORS EXTENSION — "WORTH ADDING" SET
# extends complete_indicators.py
# ============================================================
#
# NEW INDICATORS IN THIS FILE:
#
# TREND:
#   1.  Ichimoku Cloud       — 5-line system: trend, momentum, S/R all-in-one
#   2.  Parabolic SAR        — trailing stop dots above/below price
#
# MOMENTUM:
#   3.  Williams %R          — inverted Stochastic, fast and sensitive
#   4.  Awesome Oscillator   — SMA(5) - SMA(34) of midprice histogram
#   5.  Momentum (MOM)       — simplest momentum: Close - Close[N]
#
# VOLATILITY:
#   6.  Historical Volatility (HV) — annualised std dev of returns
#
# VOLUME:
#   7.  Chaikin Money Flow (CMF)  — weighted buying/selling pressure
#   8.  Accumulation/Distribution  — more accurate OBV using close position
#   9.  Volume ROC                 — % change in volume
#
# TREND STRENGTH:
#   10. Aroon Up / Aroon Down / Aroon Oscillator
#
# PRICE LEVELS:
#   11. Pivot Points (Classic daily pivots)
#   12. Camarilla Pivot Points
#   13. Fibonacci Retracements + Extensions
#
# HOW TO USE:
#   This file works standalone OR alongside complete_indicators.py.
#   Import any function you need:
#       from indicators_extension import calc_ichimoku, calc_pivot_points
#
#   Or run directly for a full analysis:
#       python indicators_extension.py
#       python indicators_extension.py HDFCBANK
#       python indicators_extension.py SBIN 2y
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import numpy as np
import sys
import warnings

warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════
# SECTION 1 — DATA DOWNLOAD
# ════════════════════════════════════════════════════════════

def get_data(ticker, period="1y"):
    """Downloads OHLCV data from Yahoo Finance."""
    print(f"\nDownloading {ticker} ({period}) ...")
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    df.dropna(inplace=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    print(f"Got {len(df)} days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ════════════════════════════════════════════════════════════
# SECTION 2 — TREND INDICATORS
# ════════════════════════════════════════════════════════════

# ── 2a: Ichimoku Cloud ───────────────────────────────────────
def calc_ichimoku(df,
                  tenkan_period=9,
                  kijun_period=26,
                  senkou_b_period=52,
                  displacement=26):
    """
    Ichimoku Cloud (Ichimoku Kinko Hyo — "one glance equilibrium chart").
    Created by Japanese journalist Goichi Hosoda in the late 1930s,
    published in 1969. Extremely popular across Asian markets.

    The system has 5 lines. Understanding all 5 together gives you
    trend direction, momentum, support, resistance, and signal
    all in a single glance — hence "one glance."

    ─────────────────────────────────────────────────────────
    LINE 1: Tenkan-sen (Conversion Line) — period=9
        = (Highest High + Lowest Low) over last 9 days / 2

        This is the midpoint of the 9-day price range.
        Think of it as a fast "equilibrium line."
        When price is above Tenkan → short-term bullish momentum.
        Tenkan crossing Kijun → signal line crossover (like MACD).

    LINE 2: Kijun-sen (Base Line) — period=26
        = (Highest High + Lowest Low) over last 26 days / 2

        The midpoint of the 26-day range.
        The most important single line in the system.
        Acts as dynamic support/resistance.
        When price is above Kijun → medium-term bullish.
        Kijun is often used as a trailing stop in trending markets.

    LINE 3: Senkou Span A (Leading Span A)
        = (Tenkan + Kijun) / 2, plotted 26 days INTO THE FUTURE

        The faster boundary of the "cloud" (Kumo).
        It's plotted 26 periods ahead — this is what makes Ichimoku
        unique: it shows you future support/resistance levels TODAY.

    LINE 4: Senkou Span B (Leading Span B) — period=52
        = (Highest High + Lowest Low) over last 52 days / 2,
          plotted 26 days INTO THE FUTURE

        The slower boundary of the cloud.
        Together with Span A, these two form the Kumo (cloud).

    THE CLOUD (Kumo):
        Area between Span A and Span B.
        Price ABOVE the cloud → uptrend
        Price BELOW the cloud → downtrend
        Price INSIDE the cloud → ranging / indecision

        Thick cloud = strong support/resistance
        Thin cloud  = weak support/resistance, easy to break through

        Cloud colour:
        Green cloud (Span A > Span B) → bullish cloud
        Red cloud   (Span A < Span B) → bearish cloud

    LINE 5: Chikou Span (Lagging Span)
        = Today's closing price, plotted 26 days IN THE PAST

        Used to confirm the current trend.
        Chikou above price from 26 days ago → bullish confirmation
        Chikou below price from 26 days ago → bearish confirmation

    ─────────────────────────────────────────────────────────
    TRADING SIGNALS:
        Strong BUY (all conditions met):
            1. Price above the cloud
            2. Cloud is green (Span A > Span B)
            3. Tenkan above Kijun
            4. Chikou above price from 26 days ago
            → All 4 = maximum bullish confirmation

        TK Cross BUY:
            Tenkan crosses above Kijun while price is above cloud
            → Momentum + trend aligned

        Cloud Breakout BUY:
            Price closes above the cloud after being below or inside
            → Major trend change signal

        Strong SELL: mirror of above conditions

    ─────────────────────────────────────────────────────────
    Standard settings: 9, 26, 52, 26
    These come from the Japanese trading week (6 days)
    and trading month (26 days). For modern 5-day week,
    some traders use 7, 22, 44, 22 but 9/26/52 remains standard.

    Parameters:
        df (DataFrame): Must have High, Low, Close
        tenkan_period (int): Conversion line period (default 9)
        kijun_period (int): Base line period (default 26)
        senkou_b_period (int): Slow cloud boundary period (default 52)
        displacement (int): How far ahead to plot cloud (default 26)

    Returns:
        tenkan, kijun, senkou_a, senkou_b, chikou (all Series)
    """

    high  = df['High']
    low   = df['Low']
    close = df['Close']

    # Tenkan-sen: midpoint of 9-day high-low range
    tenkan = ((high.rolling(window=tenkan_period).max() +
               low.rolling(window=tenkan_period).min()) / 2).round(2)

    # Kijun-sen: midpoint of 26-day high-low range
    kijun  = ((high.rolling(window=kijun_period).max() +
               low.rolling(window=kijun_period).min()) / 2).round(2)

    # Senkou Span A: average of Tenkan and Kijun, shifted 26 periods forward
    # .shift(-displacement) moves the values forward in time on the chart
    senkou_a = ((tenkan + kijun) / 2).shift(-displacement).round(2)

    # Senkou Span B: midpoint of 52-day range, shifted 26 periods forward
    senkou_b = ((high.rolling(window=senkou_b_period).max() +
                 low.rolling(window=senkou_b_period).min()) / 2
                ).shift(-displacement).round(2)

    # Chikou Span: today's close shifted 26 periods BACKWARDS (into the past)
    # .shift(displacement) moves it backward on the chart
    chikou = close.shift(displacement).round(2)

    return tenkan, kijun, senkou_a, senkou_b, chikou


def detect_ichimoku_signals(df):
    """
    Detects the main Ichimoku trading signals.

    Returns:
        List of signal dicts with date, signal type, and detail
    """
    tenkan, kijun, senkou_a, senkou_b, chikou = calc_ichimoku(df)

    signals = []

    for i in range(1, len(df)):
        close    = df['Close'].iloc[i]
        t_now    = tenkan.iloc[i]
        t_prev   = tenkan.iloc[i-1]
        k_now    = kijun.iloc[i]
        k_prev   = kijun.iloc[i-1]
        sa_now   = senkou_a.iloc[i]
        sb_now   = senkou_b.iloc[i]
        date     = df.index[i].date()

        if any(pd.isna(v) for v in [t_now, t_prev, k_now, k_prev]):
            continue

        # Determine cloud top and bottom
        cloud_top    = max(sa_now, sb_now) if not pd.isna(sa_now) and not pd.isna(sb_now) else float('nan')
        cloud_bottom = min(sa_now, sb_now) if not pd.isna(sa_now) and not pd.isna(sb_now) else float('nan')

        # ── TK Cross (Tenkan crosses Kijun) ──
        # The most important short-term Ichimoku signal

        # Bullish TK cross: Tenkan crosses ABOVE Kijun
        if t_prev < k_prev and t_now > k_now:
            position = ("above cloud (strong)" if not pd.isna(cloud_top) and close > cloud_top
                       else "inside cloud (weak)" if not pd.isna(cloud_top) and close > cloud_bottom
                       else "below cloud (very weak)")
            signals.append({
                'Date'  : date,
                'Type'  : 'Ichimoku TK Cross',
                'Signal': 'BUY',
                'Close' : round(close, 2),
                'Detail': f'Tenkan crossed above Kijun — price {position}'
            })

        # Bearish TK cross: Tenkan crosses BELOW Kijun
        elif t_prev > k_prev and t_now < k_now:
            position = ("below cloud (strong)" if not pd.isna(cloud_bottom) and close < cloud_bottom
                       else "inside cloud (weak)" if not pd.isna(cloud_top) and close < cloud_top
                       else "above cloud (very weak)")
            signals.append({
                'Date'  : date,
                'Type'  : 'Ichimoku TK Cross',
                'Signal': 'SELL',
                'Close' : round(close, 2),
                'Detail': f'Tenkan crossed below Kijun — price {position}'
            })

        # ── Cloud Breakout ──
        if not pd.isna(cloud_top) and not pd.isna(cloud_bottom):
            close_prev = df['Close'].iloc[i-1]

            # Price broke ABOVE the cloud
            if close_prev < cloud_top and close > cloud_top:
                cloud_colour = "green (bullish)" if sa_now > sb_now else "red (caution)"
                signals.append({
                    'Date'  : date,
                    'Type'  : 'Ichimoku Cloud Break',
                    'Signal': 'BUY',
                    'Close' : round(close, 2),
                    'Detail': f'Price broke above cloud (cloud is {cloud_colour})'
                })

            # Price broke BELOW the cloud
            elif close_prev > cloud_bottom and close < cloud_bottom:
                signals.append({
                    'Date'  : date,
                    'Type'  : 'Ichimoku Cloud Break',
                    'Signal': 'SELL',
                    'Close' : round(close, 2),
                    'Detail': 'Price broke below cloud'
                })

    return signals


# ── 2b: Parabolic SAR ─────────────────────────────────────────
def calc_parabolic_sar(df,
                       initial_af=0.02,
                       max_af=0.20,
                       step_af=0.02):
    """
    Parabolic SAR (Stop And Reverse), created by J. Welles Wilder (1978).
    The same person who created RSI, ATR, and ADX.

    SAR = Stop And Reverse. It places a dot above or below price that acts
    as both a trailing stop loss AND a trend direction indicator.

    DOT BELOW PRICE → uptrend is active (SAR is your stop loss level)
    DOT ABOVE PRICE → downtrend is active (SAR is your resistance level)

    When price crosses the SAR dot:
        → Trend has REVERSED
        → Exit current position
        → Enter the opposite position (hence "Stop AND Reverse")

    ─────────────────────────────────────────────────────────
    The Formula (conceptually):

    SAR accelerates towards price over time using an
    "Acceleration Factor" (AF).

    AF starts at initial_af (0.02) each time a new trend begins.
    Every time price makes a new high (in uptrend) or new low (in downtrend),
    AF increases by step_af (0.02), up to a maximum of max_af (0.20).

    This means:
        - At the START of a trend, SAR moves slowly
          (dot is far from price — gives the trend room to breathe)
        - As the trend CONTINUES and price keeps making new extremes,
          SAR accelerates and gets closer to price
          (dot tightens — protects profits as trend matures)
        - The maximum AF of 0.20 prevents SAR from getting too close
          and causing premature exits

    Uptrend SAR formula:
        SAR(today) = SAR(yesterday) + AF × (EP - SAR(yesterday))
        where EP = Extreme Point = highest high seen during this uptrend

    Downtrend SAR: mirror image, EP = lowest low.

    ─────────────────────────────────────────────────────────
    WHY PARABOLIC? The curve of SAR accelerating towards price
    looks like a parabola when drawn on a chart.

    BEST USED: In trending markets with ADX > 25.
    AVOID IN: Sideways/ranging markets — SAR will flip constantly
              giving many false signals.

    PAIRING: Use with Supertrend for confirmation:
        Both SAR and Supertrend bullish → strong uptrend, high confidence
        SAR and Supertrend disagree → wait, trend is unclear

    Parameters:
        df (DataFrame): Must have High, Low, Close
        initial_af (float): Starting acceleration factor (default 0.02)
        max_af (float): Maximum acceleration factor (default 0.20)
        step_af (float): AF increment per new extreme (default 0.02)

    Returns:
        sar (Series): SAR values
        trend (Series): +1 = uptrend (dot below), -1 = downtrend (dot above)
    """

    high  = df['High'].values
    low   = df['Low'].values
    close = df['Close'].values
    n     = len(df)

    sar    = np.zeros(n)
    trend  = np.zeros(n, dtype=int)
    ep     = np.zeros(n)    # Extreme Point
    af     = np.zeros(n)    # Acceleration Factor

    # Initialise: assume uptrend starting from the first bar
    # SAR starts at the first day's low, EP at the first day's high
    trend[0] = 1
    sar[0]   = low[0]
    ep[0]    = high[0]
    af[0]    = initial_af

    for i in range(1, n):
        prev_sar   = sar[i-1]
        prev_trend = trend[i-1]
        prev_ep    = ep[i-1]
        prev_af    = af[i-1]

        if prev_trend == 1:
            # ── Currently in UPTREND ──

            # Calculate next SAR
            new_sar = prev_sar + prev_af * (prev_ep - prev_sar)

            # SAR must NOT be above the previous two lows
            # (Wilder's rule to prevent premature reversal signals)
            new_sar = min(new_sar, low[i-1])
            if i >= 2:
                new_sar = min(new_sar, low[i-2])

            if close[i] < new_sar:
                # Price crossed below SAR → trend REVERSED to downtrend
                trend[i] = -1
                sar[i]   = prev_ep      # New SAR = highest high of previous uptrend
                ep[i]    = low[i]       # New EP = today's low (tracking new lows)
                af[i]    = initial_af   # Reset AF for new trend
            else:
                # Uptrend continues
                trend[i] = 1
                sar[i]   = new_sar

                if high[i] > prev_ep:
                    # New extreme high → increase AF (SAR accelerates)
                    ep[i] = high[i]
                    af[i] = min(prev_af + step_af, max_af)
                else:
                    ep[i] = prev_ep
                    af[i] = prev_af

        else:
            # ── Currently in DOWNTREND ──

            # Calculate next SAR
            new_sar = prev_sar + prev_af * (prev_ep - prev_sar)

            # SAR must NOT be below the previous two highs
            new_sar = max(new_sar, high[i-1])
            if i >= 2:
                new_sar = max(new_sar, high[i-2])

            if close[i] > new_sar:
                # Price crossed above SAR → trend REVERSED to uptrend
                trend[i] = 1
                sar[i]   = prev_ep      # New SAR = lowest low of previous downtrend
                ep[i]    = high[i]      # New EP = today's high
                af[i]    = initial_af   # Reset AF
            else:
                # Downtrend continues
                trend[i] = -1
                sar[i]   = new_sar

                if low[i] < prev_ep:
                    # New extreme low → increase AF
                    ep[i] = low[i]
                    af[i] = min(prev_af + step_af, max_af)
                else:
                    ep[i] = prev_ep
                    af[i] = prev_af

    sar_series   = pd.Series(sar,   index=df.index).round(2)
    trend_series = pd.Series(trend, index=df.index)
    return sar_series, trend_series


def detect_sar_signals(df):
    """
    Detects Parabolic SAR reversal signals.

    Returns:
        List of signal dicts
    """
    sar, trend = calc_parabolic_sar(df)
    signals = []

    for i in range(1, len(df)):
        t_now  = trend.iloc[i]
        t_prev = trend.iloc[i-1]
        date   = df.index[i].date()
        close  = round(df['Close'].iloc[i], 2)
        sar_v  = round(sar.iloc[i], 2)

        # Trend flipped from -1 to +1 → SAR reversal BUY
        if t_prev == -1 and t_now == 1:
            signals.append({
                'Date'  : date,
                'Type'  : 'Parabolic SAR',
                'Signal': 'BUY',
                'Close' : close,
                'Detail': f'SAR flipped below price. SAR support at ₹{sar_v}'
            })
        # Trend flipped from +1 to -1 → SAR reversal SELL
        elif t_prev == 1 and t_now == -1:
            signals.append({
                'Date'  : date,
                'Type'  : 'Parabolic SAR',
                'Signal': 'SELL',
                'Close' : close,
                'Detail': f'SAR flipped above price. SAR resistance at ₹{sar_v}'
            })

    return signals


# ════════════════════════════════════════════════════════════
# SECTION 3 — MOMENTUM INDICATORS
# ════════════════════════════════════════════════════════════

# ── 3a: Williams %R ──────────────────────────────────────────
def calc_williams_r(df, period=14):
    """
    Williams %R, created by Larry Williams in 1966.

    Conceptually identical to Stochastic %K but INVERTED and
    using a different scale (-100 to 0 instead of 0 to 100).

    Formula:
        %R = (Highest High in N days - Close) /
             (Highest High in N days - Lowest Low in N days) × -100

    Scale:
        0    = Close is at the N-day HIGH  (maximum bullish)
        -100 = Close is at the N-day LOW   (maximum bearish)
        -20  = Overbought threshold (equivalent to Stochastic 80)
        -80  = Oversold threshold  (equivalent to Stochastic 20)

    Interpretation:
        %R above -20  (e.g. -10, -5): Overbought → consider selling
        %R below -80  (e.g. -90, -95): Oversold → consider buying

    Williams %R vs Stochastic:
        They measure the same thing. %R = -(100 - %K).
        Williams %R reacts slightly FASTER because it uses no smoothing
        (Stochastic smooths %K into "slow stochastic" with a 3-period MA).
        This makes %R better for catching very short-term turns,
        but also noisier.

    Key insight from Larry Williams:
        "Failure swings" — when %R reaches overbought/oversold and
        then FAILS to make a new extreme on the next move, it signals
        a likely reversal. This is the same concept as RSI failure swings.

    Parameters:
        df (DataFrame): Must have High, Low, Close
        period (int): Lookback period (default 14)

    Returns:
        Series: Williams %R values (range: -100 to 0)
    """

    highest_high = df['High'].rolling(window=period, min_periods=period).max()
    lowest_low   = df['Low'].rolling(window=period,  min_periods=period).min()

    hl_range = (highest_high - lowest_low).replace(0, float('nan'))

    # Note the negative sign — this is what makes it "inverted"
    williams_r = ((highest_high - df['Close']) / hl_range) * -100

    return williams_r.round(2)


# ── 3b: Awesome Oscillator ────────────────────────────────────
def calc_awesome_oscillator(df):
    """
    Awesome Oscillator (AO), created by Bill Williams.

    Despite the name, it's conceptually simple:
    It measures momentum by comparing a fast midprice average
    to a slow midprice average — similar to MACD but using
    midprice (High+Low)/2 instead of close, and simple averages
    instead of exponential averages.

    Formula:
        Midprice = (High + Low) / 2
        AO = SMA(Midprice, 5) - SMA(Midprice, 34)

    Why midprice? Midprice includes both the high and low of the day,
    capturing intraday range, not just the closing price. This makes AO
    respond to the full price action of each session.

    Interpretation:
        AO > 0  : Short-term momentum is above long-term → bullish
        AO < 0  : Short-term momentum is below long-term → bearish
        AO crossing zero → momentum shift (similar to MACD zero cross)

    The Histogram:
        Green bar: AO is higher than the previous bar (momentum accelerating)
        Red bar:   AO is lower than the previous bar  (momentum decelerating)

        Note: A green bar does NOT mean AO is positive — it just means
        it moved UP from the previous bar. AO can be negative but have
        green bars (negative but improving momentum).

    Bill Williams Trading Signals:
        Saucer: 3 consecutive histogram bars, middle one the lowest/highest
                → momentum reversal signal within the current trend
        Zero Line Cross: AO crosses above/below zero
        Twin Peaks: Two peaks/troughs on opposite sides of zero line
                    → divergence signal

    Parameters:
        df (DataFrame): Must have High and Low

    Returns:
        Series: AO values
    """

    midprice = (df['High'] + df['Low']) / 2

    # Fast SMA (5 periods) minus Slow SMA (34 periods)
    sma5  = midprice.rolling(window=5,  min_periods=5).mean()
    sma34 = midprice.rolling(window=34, min_periods=34).mean()

    ao = sma5 - sma34

    return ao.round(4)


# ── 3c: Momentum (MOM) ───────────────────────────────────────
def calc_momentum(prices, period=10):
    """
    Momentum (MOM) — the simplest and most transparent momentum indicator.

    Formula:
        MOM = Close(today) - Close(N days ago)

    That's it. There is no smoothing, no normalisation,
    no complex calculation. Just the raw price change.

    This is the foundation that more complex indicators (MACD, ROC)
    are built on. MACD smooths momentum using EMAs. ROC normalises it
    as a percentage. But raw momentum captures it directly.

    Interpretation:
        MOM > 0  : Price is higher than N days ago → positive momentum
        MOM < 0  : Price is lower than N days ago  → negative momentum
        MOM = 0  : Price unchanged → no momentum

        MOM rising while positive  : Accelerating upward
        MOM falling while positive : Decelerating — rally losing steam
        MOM rising from negative   : Downtrend losing momentum
        MOM crossing zero          : Momentum reversal

    MOM vs ROC:
        MOM = Close - Close[N]  (absolute change — depends on price level)
        ROC = (Close - Close[N]) / Close[N] × 100  (% change)

        Use MOM when comparing one stock to itself over time.
        Use ROC when comparing momentum across different stocks
        (because ROC normalises for price level).

    Parameters:
        prices (Series): Closing prices
        period (int): Lookback period (default 10)

    Returns:
        Series: MOM values in price units
    """
    return (prices - prices.shift(period)).round(4)


# ════════════════════════════════════════════════════════════
# SECTION 4 — VOLATILITY INDICATORS
# ════════════════════════════════════════════════════════════

# ── 4a: Historical Volatility ────────────────────────────────
def calc_historical_volatility(prices, period=20, annualise=True):
    """
    Historical Volatility (HV) — also called Realised Volatility.

    The most fundamental volatility measure: the standard deviation
    of daily returns, annualised to express it as a yearly percentage.

    Formula:
        Daily Return = ln(Close today / Close yesterday)
                     = log return (more accurate than % return for compounding)

        HV(20) = StdDev(Daily Returns over 20 days) × √252 × 100
                                                        ↑
                                               252 trading days per year
                                               Square root because volatility
                                               scales with √time

    What it means:
        HV = 20%  → The stock typically moves ±20% per year
                    → Daily move of roughly ±20/√252 = ±1.26%
        HV = 50%  → Highly volatile — moves ±50% per year
                    → Typical for small/midcap stocks
        HV = 10%  → Low volatility — stable, large-cap stock

    Why this matters for trading:
        1. Options pricing: HV is the direct input to Black-Scholes.
           If HV = 25% but implied volatility = 40%, options are expensive.
           If HV = 25% but IV = 15%, options are cheap — buy them.

        2. Stop loss sizing: ATR-based stops use daily range.
           HV-based stops use statistical distribution of returns.
           A 2× daily sigma stop (2 × HV/√252 × price) means only
           5% of days will hit the stop by random chance alone.

        3. Position sizing: Higher HV → smaller position size.
           Kelly criterion and fixed-fraction methods both scale
           inversely with volatility.

        4. Trend detection: Rising HV during a price move confirms
           the move is real. Falling HV despite price movement = weak move.

    HV vs ATR:
        ATR: measures average RANGE (High - Low or True Range)
        HV:  measures std dev of RETURNS (based on daily close-to-close)
        ATR is better for stop losses (uses intraday range)
        HV is better for options and position sizing (statistical)

    Parameters:
        prices (Series): Closing prices
        period (int): Rolling window (default 20 days)
        annualise (bool): Multiply by √252 to get annual % (default True)

    Returns:
        Series: HV as a percentage (e.g. 25.4 means 25.4% annual volatility)
    """

    # Log returns: ln(today/yesterday)
    # Using log returns rather than % returns for mathematical correctness
    # (log returns are additive over time, % returns are multiplicative)
    log_returns = np.log(prices / prices.shift(1))

    # Rolling standard deviation of log returns
    rolling_std = log_returns.rolling(window=period, min_periods=period).std()

    if annualise:
        # Multiply by √252 to annualise (252 trading days in a year)
        # Multiply by 100 to express as percentage
        hv = rolling_std * np.sqrt(252) * 100
    else:
        hv = rolling_std * 100

    return hv.round(4)


# ════════════════════════════════════════════════════════════
# SECTION 5 — VOLUME INDICATORS
# ════════════════════════════════════════════════════════════

# ── 5a: Chaikin Money Flow (CMF) ─────────────────────────────
def calc_cmf(df, period=20):
    """
    Chaikin Money Flow (CMF), created by Marc Chaikin.

    CMF improves on OBV by asking a more nuanced question:
    Not just whether the day was up or down, but WHERE within
    the day's range did the stock close?

    A stock that closes at its HIGH for the day shows maximum
    buying conviction — buyers pushed price all the way to the top.
    A stock that closes at its LOW for the day shows maximum
    selling pressure — sellers won the day completely.
    A close in the middle is neutral.

    This "close location value" is called the Money Flow Multiplier:

        MF Multiplier = (Close - Low - (High - Close)) / (High - Low)
                      = (2 × Close - High - Low) / (High - Low)

        Range: -1 to +1
        +1  = Close at the day's High  (maximum buying pressure)
        -1  = Close at the day's Low   (maximum selling pressure)
         0  = Close at the exact middle

        Money Flow Volume = MF Multiplier × Volume

    CMF = Sum(Money Flow Volume over N days) /
          Sum(Volume over N days)

    Interpretation:
        CMF > 0   : Net buying pressure over N days → accumulation
        CMF < 0   : Net selling pressure over N days → distribution
        CMF > +0.25 : Strong accumulation
        CMF < -0.25 : Strong distribution
        CMF crossing zero → shift from accumulation to distribution

    CMF vs OBV:
        OBV: A close 1 pip above yesterday's close = same as 5% above
             (binary — either the whole volume is added or subtracted)
        CMF: A close near the middle adds little; near the high adds a lot
             (weighted — reflects where the close is within the range)
        CMF is more accurate but responds more slowly to sudden moves.

    Parameters:
        df (DataFrame): Must have High, Low, Close, Volume
        period (int): Lookback period (default 20)

    Returns:
        Series: CMF values (range: approximately -1 to +1)
    """

    high  = df['High']
    low   = df['Low']
    close = df['Close']
    vol   = df['Volume']

    # Money Flow Multiplier — where did price close within the range?
    hl_range = (high - low).replace(0, float('nan'))
    mf_mult  = (2 * close - high - low) / hl_range

    # Money Flow Volume — weight the volume by the multiplier
    mf_volume = mf_mult * vol

    # CMF = rolling sum of MF Volume / rolling sum of Volume
    cmf = (mf_volume.rolling(window=period, min_periods=period).sum() /
           vol.rolling(window=period, min_periods=period).sum())

    return cmf.round(4)


# ── 5b: Accumulation/Distribution Line ───────────────────────
def calc_accumulation_distribution(df):
    """
    Accumulation/Distribution Line (A/D Line), created by Marc Chaikin.

    The A/D Line is a more accurate version of OBV.

    OBV problem: If a stock closes up by just 1 paisa but on 10 crore
    shares of volume, OBV adds the full 10 crore shares as "buying."
    But what if the stock opened at ₹100, hit ₹120 (high), then closed
    at ₹101? Technically bullish (close > open) but the close is near
    the LOW of the day's range. Most of the day's action was selling.

    A/D Line fixes this using the same Money Flow Multiplier as CMF:
        AD = Previous AD + (MF Multiplier × Volume)

    This means:
        A day that closes at its high contributes fully to the A/D Line
        A day that closes at its low subtracts fully from the A/D Line
        A day that closes in the middle contributes very little

    The A/D Line tracks CUMULATIVE money flow, like OBV,
    but with this more nuanced daily weighting.

    Trading use:
        A/D Line rising while price rises → confirmed uptrend (bullish)
        A/D Line falling while price rises → bearish divergence
                                              (distribution — insiders selling)
        A/D Line rising while price falls → bullish divergence
                                              (accumulation — insiders buying)

    The divergence signals are very powerful because they reveal
    what institutional money is doing BEFORE the price reflects it.

    Parameters:
        df (DataFrame): Must have High, Low, Close, Volume

    Returns:
        Series: Cumulative A/D Line values
    """

    high  = df['High']
    low   = df['Low']
    close = df['Close']
    vol   = df['Volume']

    # Money Flow Multiplier (same as CMF)
    hl_range = (high - low).replace(0, float('nan'))
    mf_mult  = (2 * close - high - low) / hl_range

    # Money Flow Volume for each day
    mf_volume = mf_mult * vol

    # Cumulative sum = the A/D Line
    ad_line = mf_volume.cumsum()

    return ad_line.round(0)


# ── 5c: Volume Rate of Change ────────────────────────────────
def calc_volume_roc(volume, period=14):
    """
    Volume Rate of Change (VROC).

    The same ROC concept applied to volume instead of price.

    Formula:
        VROC = (Volume today - Volume N days ago) /
                Volume N days ago × 100

    Interpretation:
        VROC > 0  : Volume is HIGHER than N days ago → increasing interest
        VROC < 0  : Volume is LOWER than N days ago  → decreasing interest

        High positive VROC on an up-day  → strong bullish move, real buying
        High positive VROC on a down-day → strong selling, possible panic
        Very high VROC (> 100–200%)      → volume climax, possible reversal

    Use cases:
        1. Confirm breakouts: a price breakout with VROC > 50% is reliable.
           A breakout with VROC near zero is a false breakout.

        2. Spot exhaustion: when VROC reaches extreme levels (> 200%)
           during a sustained move, the move may be exhausting itself.

        3. Divergence: price making new highs but VROC falling
           → participation is declining → rally losing steam

    Parameters:
        volume (Series): Daily trading volume
        period (int): Lookback period (default 14)

    Returns:
        Series: VROC as a percentage
    """

    prev_vol = volume.shift(period).replace(0, float('nan'))
    vroc = ((volume - prev_vol) / prev_vol) * 100

    return vroc.round(2)


# ════════════════════════════════════════════════════════════
# SECTION 6 — TREND STRENGTH
# ════════════════════════════════════════════════════════════

# ── 6a: Aroon ────────────────────────────────────────────────
def calc_aroon(df, period=25):
    """
    Aroon Indicator, created by Tushar Chande in 1995.
    "Aroon" means "dawn's early light" in Sanskrit — the first light
    of a new trend.

    The key insight: in a strong uptrend, price regularly makes
    new highs. In a strong downtrend, price regularly makes new lows.
    Aroon measures HOW RECENTLY the N-period high/low was made.

    Formula:
        Aroon Up   = ((N - Periods since N-day High)  / N) × 100
        Aroon Down = ((N - Periods since N-day Low)   / N) × 100

    Range: 0 to 100

    Aroon Up = 100: The N-day high was TODAY (maximum upward strength)
    Aroon Up = 0:   The N-day high was N periods ago (no recent highs)
    Aroon Down = 100: The N-day low was TODAY (maximum downward strength)

    Aroon Oscillator = Aroon Up - Aroon Down (range: -100 to +100)
        > 0  : Uptrend
        > 50 : Strong uptrend
        < 0  : Downtrend
        < -50: Strong downtrend

    ─────────────────────────────────────────────────────────
    AROON vs ADX:
        ADX measures STRENGTH of a trend (how strong is the move?)
        Aroon detects the BEGINNING of new trends (is a trend forming?)

        Aroon reacts FASTER to trend changes because it's based on
        the recency of new highs/lows, not on a smoothed directional
        movement calculation.

        Use Aroon to find new trends EARLY.
        Use ADX to confirm the trend has real strength.
        Use both together for the strongest signals.

    KEY SIGNALS:
        Aroon Up crosses above Aroon Down → uptrend starting
        Aroon Up crosses below Aroon Down → downtrend starting
        Both lines below 50              → ranging, no trend
        Aroon Up near 100 + Down near 0  → very strong uptrend
        Aroon Down near 100 + Up near 0  → very strong downtrend

    Parameters:
        df (DataFrame): Must have High and Low
        period (int): Lookback period (default 25)

    Returns:
        aroon_up (Series), aroon_down (Series), aroon_osc (Series)
    """

    n = period

    # For each day, find how many periods ago the N-day high/low occurred
    # rolling(n+1) gives us the window including today

    # periods_since_high: 0 means the high was TODAY, n means it was n days ago
    def periods_since_high(window):
        """Returns how many bars ago the max occurred in this window."""
        # argmax gives the index of the maximum within the window
        # The last element of the window is "today" (index = n-1 within window)
        idx = np.argmax(window)
        return len(window) - 1 - idx   # 0 = today, n-1 = oldest

    def periods_since_low(window):
        """Returns how many bars ago the min occurred in this window."""
        idx = np.argmin(window)
        return len(window) - 1 - idx

    # Apply rolling calculation
    high_series = df['High']
    low_series  = df['Low']

    bars_since_high = high_series.rolling(window=n+1, min_periods=n+1).apply(
        periods_since_high, raw=True
    )
    bars_since_low = low_series.rolling(window=n+1, min_periods=n+1).apply(
        periods_since_low, raw=True
    )

    # Aroon formula
    aroon_up   = ((n - bars_since_high) / n * 100).round(2)
    aroon_down = ((n - bars_since_low)  / n * 100).round(2)
    aroon_osc  = (aroon_up - aroon_down).round(2)

    return aroon_up, aroon_down, aroon_osc


def detect_aroon_signals(df, period=25):
    """
    Detects Aroon crossover and trend signals.

    Returns:
        List of signal dicts
    """
    aroon_up, aroon_down, aroon_osc = calc_aroon(df, period)
    signals = []

    for i in range(1, len(df)):
        au_now  = aroon_up.iloc[i]
        au_prev = aroon_up.iloc[i-1]
        ad_now  = aroon_down.iloc[i]
        ad_prev = aroon_down.iloc[i-1]
        date    = df.index[i].date()
        close   = round(df['Close'].iloc[i], 2)

        if any(pd.isna(v) for v in [au_now, au_prev, ad_now, ad_prev]):
            continue

        # Aroon Up crosses above Aroon Down → uptrend forming
        if au_prev < ad_prev and au_now > ad_now:
            strength = "strong" if au_now > 70 else "moderate"
            signals.append({
                'Date'  : date,
                'Type'  : 'Aroon',
                'Signal': 'BUY',
                'Close' : close,
                'Detail': f'Aroon Up({round(au_now,0)}) crossed Aroon Down({round(ad_now,0)}) — {strength} uptrend forming'
            })

        # Aroon Down crosses above Aroon Up → downtrend forming
        elif au_prev > ad_prev and au_now < ad_now:
            strength = "strong" if ad_now > 70 else "moderate"
            signals.append({
                'Date'  : date,
                'Type'  : 'Aroon',
                'Signal': 'SELL',
                'Close' : close,
                'Detail': f'Aroon Down({round(ad_now,0)}) crossed Aroon Up({round(au_now,0)}) — {strength} downtrend forming'
            })

    return signals


# ════════════════════════════════════════════════════════════
# SECTION 7 — PRICE LEVELS
# ════════════════════════════════════════════════════════════

# ── 7a: Classic Pivot Points ─────────────────────────────────
def calc_pivot_points(df):
    """
    Classic Daily Pivot Points.

    Used by EVERY professional intraday trader in India.
    NSE traders watch these levels religiously because so many
    people watch them, they become self-fulfilling support/resistance.

    Calculated from the PREVIOUS day's High, Low, and Close.
    Applied to the CURRENT trading day.

    ─────────────────────────────────────────────────────────
    Formulas:
        Pivot Point (PP) = (High + Low + Close) / 3
            → The most important level. Acts as the "fair value"
              of the day. Price above PP → bullish bias for the day.
              Price below PP → bearish bias for the day.

        Resistance 1 (R1) = 2 × PP - Low
        Resistance 2 (R2) = PP + (High - Low)
        Resistance 3 (R3) = High + 2 × (PP - Low)

        Support 1 (S1) = 2 × PP - High
        Support 2 (S2) = PP - (High - Low)
        Support 3 (S3) = Low - 2 × (High - PP)

    How traders use them:
        Opening above PP with volume → buy, target R1, stop below PP
        Opening below PP with volume → sell, target S1, stop above PP
        R1 hit → scale out 50%, hold rest to R2
        S1 hit → scale out 50%, hold rest to S2
        R3/S3 → extreme targets, rarely reached in one session

    These levels are recalculated every day using previous day's data.
    They are FIXED levels for the day — they don't change intraday.
    This is different from Bollinger Bands or Supertrend which move
    throughout the day.

    Parameters:
        df (DataFrame): Must have High, Low, Close

    Returns:
        DataFrame with columns: PP, R1, R2, R3, S1, S2, S3
        (each value applies to the NEXT trading day)
    """

    # .shift(1) means: use yesterday's OHLC to calculate today's levels
    high  = df['High'].shift(1)
    low   = df['Low'].shift(1)
    close = df['Close'].shift(1)

    pp = (high + low + close) / 3

    r1 = (2 * pp) - low
    r2 = pp + (high - low)
    r3 = high + 2 * (pp - low)

    s1 = (2 * pp) - high
    s2 = pp - (high - low)
    s3 = low - 2 * (high - pp)

    pivots = pd.DataFrame({
        'PP': pp, 'R1': r1, 'R2': r2, 'R3': r3,
        'S1': s1, 'S2': s2, 'S3': s3
    }, index=df.index).round(2)

    return pivots


# ── 7b: Camarilla Pivot Points ────────────────────────────────
def calc_camarilla_pivots(df):
    """
    Camarilla Pivot Points.

    Created by Nick Scott in 1989. The name comes from the Latin
    "camarilla" (small group) — referring to the small group of
    floor traders who originally used this system.

    The key difference from Classic Pivots:
        Camarilla pivots are MUCH TIGHTER (closer to current price)
        and are specifically designed for INTRADAY MEAN REVERSION.

    The philosophy: most intraday price movements are random noise
    around a mean. Camarilla identifies the boundaries where price
    is statistically "too far" from fair value and likely to revert.

    ─────────────────────────────────────────────────────────
    Formulas (using previous day's High, Low, Close):
        Range = High - Low

        H4 = Close + Range × 1.1/2       (key resistance — sell here)
        H3 = Close + Range × 1.1/4       (minor resistance)
        H2 = Close + Range × 1.1/6
        H1 = Close + Range × 1.1/12

        L1 = Close - Range × 1.1/12
        L2 = Close - Range × 1.1/6
        L3 = Close - Range × 1.1/4       (minor support)
        L4 = Close - Range × 1.1/2       (key support — buy here)

    The 1.1 multiplier was empirically derived by Nick Scott from
    extensive observation of price behaviour.

    ─────────────────────────────────────────────────────────
    KEY LEVELS — H4 and L4:

        L4: If price opens below L4 or falls to L4, it is statistically
            at an extreme for the day. Buy here, stop below L3.
            Target: at least L3 or H1 (mean reversion back to centre).

        H4: If price opens above H4 or rises to H4, sell/short here.
            Target: at least H3 or L1 (mean reversion back to centre).

        H3 / L3 reversal zone:
            If price approaches H3, look for signs of reversal (sell)
            If price approaches L3, look for signs of reversal (buy)

        BREAKOUT (when to IGNORE mean reversion):
            If price BREAKS and CLOSES beyond H4 or L4 → trend day!
            Don't fade it. Instead, go WITH the breakout.
            A close above H4 = very bullish, may continue next day.
            A close below L4 = very bearish, may continue next day.

    Camarilla vs Classic Pivots:
        Classic: wider levels, useful for multi-hour moves
        Camarilla: tighter levels, built for minute-to-minute scalping
        Professional intraday traders in India use BOTH

    Parameters:
        df (DataFrame): Must have High, Low, Close

    Returns:
        DataFrame with columns: H1, H2, H3, H4, L1, L2, L3, L4
    """

    high  = df['High'].shift(1)
    low   = df['Low'].shift(1)
    close = df['Close'].shift(1)

    rnge  = high - low      # Previous day's range

    # Camarilla levels — all anchored to yesterday's close
    h4 = close + rnge * (1.1 / 2)
    h3 = close + rnge * (1.1 / 4)
    h2 = close + rnge * (1.1 / 6)
    h1 = close + rnge * (1.1 / 12)

    l1 = close - rnge * (1.1 / 12)
    l2 = close - rnge * (1.1 / 6)
    l3 = close - rnge * (1.1 / 4)
    l4 = close - rnge * (1.1 / 2)

    cam = pd.DataFrame({
        'H4': h4, 'H3': h3, 'H2': h2, 'H1': h1,
        'L1': l1, 'L2': l2, 'L3': l3, 'L4': l4
    }, index=df.index).round(2)

    return cam


# ── 7c: Fibonacci Retracements + Extensions ──────────────────
def calc_fibonacci_levels(swing_high, swing_low, direction='up'):
    """
    Fibonacci Retracement and Extension Levels.

    These are NOT time-series indicators — they are STATIC PRICE LEVELS
    calculated from a chosen swing high and swing low.

    The basis: Fibonacci numbers (0, 1, 1, 2, 3, 5, 8, 13, 21, 34...)
    Each number divided by the next gives ~0.618 (the "Golden Ratio").
    These ratios appear throughout nature and financial markets.

    Fibonacci Ratios:
        23.6%  = 1 - 0.764 (less important)
        38.2%  = 1 - 0.618
        50.0%  = not a Fibonacci ratio but universally watched
        61.8%  = the "Golden Ratio" (most important retracement level)
        78.6%  = √0.618 (deep retracement, often last support before reversal)

    Retracements (inside the swing range):
        In an uptrend, price pulls back from the high.
        The question is: how far will it pull back before resuming?
        38.2%, 50%, and 61.8% are the most-watched support levels.

        Example: Stock moves from ₹100 to ₹200 (swing high).
        38.2% retracement = ₹200 - (₹100 × 0.382) = ₹161.8
        61.8% retracement = ₹200 - (₹100 × 0.618) = ₹138.2

    Extensions (beyond the swing high):
        After a retracement, price often continues to the extension levels.
        127.2%, 161.8%, and 261.8% are the key targets.

        Example: After retracing from ₹200 down to ₹161.8 (38.2%),
        price resumes the uptrend. Targets:
        127.2% extension = ₹200 + (₹100 × 0.272) = ₹227.2
        161.8% extension = ₹200 + (₹100 × 0.618) = ₹261.8

    Why markets respect these levels:
        Because enough traders watch them and place orders there —
        they become self-fulfilling prophecies. The 61.8% level
        is watched by millions of traders globally.

    Parameters:
        swing_high (float): The recent peak price
        swing_low  (float): The recent trough price
        direction  (str):  'up' = uptrend (low to high)
                           'down' = downtrend (high to low)

    Returns:
        dict with all retracement and extension levels
    """

    rng = swing_high - swing_low

    if direction == 'up':
        # Retracements: levels BELOW the swing high (pullback support)
        retracements = {
            '0%'    : swing_high,
            '23.6%' : swing_high - rng * 0.236,
            '38.2%' : swing_high - rng * 0.382,
            '50.0%' : swing_high - rng * 0.500,
            '61.8%' : swing_high - rng * 0.618,
            '78.6%' : swing_high - rng * 0.786,
            '100%'  : swing_low,
        }
        # Extensions: levels ABOVE the swing high (breakout targets)
        extensions = {
            '127.2%': swing_high + rng * 0.272,
            '161.8%': swing_high + rng * 0.618,
            '200.0%': swing_high + rng * 1.000,
            '261.8%': swing_high + rng * 1.618,
        }

    else:  # downtrend
        # Retracements: levels ABOVE the swing low (bounce resistance)
        retracements = {
            '0%'    : swing_low,
            '23.6%' : swing_low + rng * 0.236,
            '38.2%' : swing_low + rng * 0.382,
            '50.0%' : swing_low + rng * 0.500,
            '61.8%' : swing_low + rng * 0.618,
            '78.6%' : swing_low + rng * 0.786,
            '100%'  : swing_high,
        }
        # Extensions: levels BELOW the swing low (breakdown targets)
        extensions = {
            '127.2%': swing_low - rng * 0.272,
            '161.8%': swing_low - rng * 0.618,
            '200.0%': swing_low - rng * 1.000,
            '261.8%': swing_low - rng * 1.618,
        }

    # Round all values
    retracements = {k: round(v, 2) for k, v in retracements.items()}
    extensions   = {k: round(v, 2) for k, v in extensions.items()}

    return {'retracements': retracements, 'extensions': extensions,
            'swing_high': swing_high, 'swing_low': swing_low,
            'direction': direction}


def auto_fibonacci(df, lookback=60):
    """
    Automatically identifies the most recent significant swing
    and calculates Fibonacci levels from it.

    Finds the highest high and lowest low in the last 'lookback' days,
    determines which came first to identify the trend direction,
    then calculates Fibonacci retracements and extensions.

    Parameters:
        df (DataFrame): Must have High and Low
        lookback (int): How many days to look back for the swing (default 60)

    Returns:
        dict from calc_fibonacci_levels()
    """
    recent  = df.iloc[-lookback:]
    sh_idx  = recent['High'].idxmax()   # Index of the swing high
    sl_idx  = recent['Low'].idxmin()    # Index of the swing low
    sh      = recent['High'].max()
    sl      = recent['Low'].min()

    # Determine trend: if the low came BEFORE the high → uptrend
    # (price went from low to high)
    direction = 'up' if sl_idx < sh_idx else 'down'

    return calc_fibonacci_levels(sh, sl, direction)


# ════════════════════════════════════════════════════════════
# SECTION 8 — SIGNAL RUNNER
# ════════════════════════════════════════════════════════════

def run_all_extension_signals(df):
    """
    Runs all detectable signals from this extension file.

    Returns:
        List of signal dicts sorted by date
    """
    signals = []
    signals += detect_ichimoku_signals(df)
    signals += detect_sar_signals(df)
    signals += detect_aroon_signals(df)
    signals.sort(key=lambda x: x['Date'])
    return signals


# ════════════════════════════════════════════════════════════
# SECTION 9 — PRINT SUMMARY
# ════════════════════════════════════════════════════════════

def print_extension_summary(df, ticker):
    """
    Prints current readings for all new indicators.
    """
    last = df.iloc[-1]

    print(f"\n{'='*70}")
    print(f"  EXTENSION INDICATORS — {ticker}")
    print(f"  As of: {df.index[-1].date()}")
    print(f"{'='*70}")

    close = round(last['Close'], 2)

    # ── Ichimoku ──
    tenkan, kijun, sa, sb, chikou = calc_ichimoku(df)
    t_val  = round(tenkan.iloc[-1], 2)
    k_val  = round(kijun.iloc[-1], 2)
    sa_val = round(sa.iloc[-26], 2) if len(sa) > 26 else float('nan')  # current cloud
    sb_val = round(sb.iloc[-26], 2) if len(sb) > 26 else float('nan')

    cloud_top = max(sa_val, sb_val) if not pd.isna(sa_val) else float('nan')
    cloud_bot = min(sa_val, sb_val) if not pd.isna(sa_val) else float('nan')

    if not pd.isna(cloud_top):
        if close > cloud_top:
            ichi_pos = "ABOVE cloud (bullish)"
        elif close < cloud_bot:
            ichi_pos = "BELOW cloud (bearish)"
        else:
            ichi_pos = "INSIDE cloud (neutral)"
    else:
        ichi_pos = "N/A"

    print(f"\n  ── Ichimoku Cloud ──")
    print(f"  Tenkan (9)     : ₹{t_val}")
    print(f"  Kijun  (26)    : ₹{k_val}")
    print(f"  Cloud top/bot  : ₹{cloud_top} / ₹{cloud_bot}")
    print(f"  Price position : {ichi_pos}")
    print(f"  TK signal      : {'Bullish (Tenkan > Kijun)' if t_val > k_val else 'Bearish (Tenkan < Kijun)'}")

    # ── Parabolic SAR ──
    sar, trend = calc_parabolic_sar(df)
    sar_val    = round(sar.iloc[-1], 2)
    trend_val  = int(trend.iloc[-1])
    print(f"\n  ── Parabolic SAR ──")
    print(f"  SAR level      : ₹{sar_val}")
    print(f"  Trend          : {'BULLISH — dot below price' if trend_val == 1 else 'BEARISH — dot above price'}")
    print(f"  Distance       : {round(abs(close - sar_val)/close*100, 2)}% from current price")

    # ── Williams %R ──
    wr = calc_williams_r(df)
    wr_val = round(wr.iloc[-1], 1)
    wr_zone = ("Overbought (above -20)" if wr_val > -20
               else "Oversold (below -80)" if wr_val < -80
               else "Neutral")
    print(f"\n  ── Williams %R ──")
    print(f"  %R (14)        : {wr_val}  → {wr_zone}")

    # ── Awesome Oscillator ──
    ao = calc_awesome_oscillator(df)
    ao_val  = round(ao.iloc[-1], 4)
    ao_prev = round(ao.iloc[-2], 4)
    ao_dir  = "rising (green bar)" if ao_val > ao_prev else "falling (red bar)"
    print(f"\n  ── Awesome Oscillator ──")
    print(f"  AO value       : {ao_val}  {ao_dir}")
    print(f"  Momentum       : {'Positive (above zero)' if ao_val > 0 else 'Negative (below zero)'}")

    # ── Momentum ──
    mom = calc_momentum(df['Close'])
    mom_val = round(mom.iloc[-1], 2)
    print(f"\n  ── Momentum (MOM 10) ──")
    print(f"  MOM value      : ₹{mom_val}  ({'positive' if mom_val > 0 else 'negative'})")

    # ── Historical Volatility ──
    hv = calc_historical_volatility(df['Close'])
    hv_val = round(hv.iloc[-1], 2)
    hv_zone = ("Low (<15%)" if hv_val < 15
               else "Normal (15-30%)" if hv_val < 30
               else "High (30-50%)" if hv_val < 50
               else "Very High (>50%)")
    print(f"\n  ── Historical Volatility (HV 20) ──")
    print(f"  HV (annualised): {hv_val}%  → {hv_zone}")
    print(f"  Daily expected : ±{round(hv_val/np.sqrt(252), 2)}%  (1 sigma)")

    # ── CMF ──
    cmf = calc_cmf(df)
    cmf_val = round(cmf.iloc[-1], 4)
    cmf_str = ("Strong accumulation" if cmf_val > 0.25
               else "Mild accumulation" if cmf_val > 0
               else "Mild distribution" if cmf_val > -0.25
               else "Strong distribution")
    print(f"\n  ── Chaikin Money Flow (CMF 20) ──")
    print(f"  CMF value      : {cmf_val}  → {cmf_str}")

    # ── Aroon ──
    aroon_up, aroon_down, aroon_osc = calc_aroon(df)
    au_val  = round(aroon_up.iloc[-1], 1)
    ad_val  = round(aroon_down.iloc[-1], 1)
    osc_val = round(aroon_osc.iloc[-1], 1)
    aroon_str = ("Strong uptrend" if au_val > 70 and ad_val < 30
                 else "Strong downtrend" if ad_val > 70 and au_val < 30
                 else "Ranging (no clear trend)")
    print(f"\n  ── Aroon (25) ──")
    print(f"  Aroon Up       : {au_val}")
    print(f"  Aroon Down     : {ad_val}")
    print(f"  Aroon Osc      : {osc_val}  → {aroon_str}")

    # ── Pivot Points ──
    pivots = calc_pivot_points(df)
    cam    = calc_camarilla_pivots(df)
    pp_row = pivots.iloc[-1]
    cam_row = cam.iloc[-1]
    print(f"\n  ── Today's Pivot Points (Classic) ──")
    print(f"  R3={pp_row['R3']}  R2={pp_row['R2']}  R1={pp_row['R1']}  "
          f"PP={pp_row['PP']}  S1={pp_row['S1']}  S2={pp_row['S2']}  S3={pp_row['S3']}")
    print(f"  Price vs PP    : {'Above (bullish day bias)' if close > pp_row['PP'] else 'Below (bearish day bias)'}")

    print(f"\n  ── Today's Camarilla Pivots ──")
    print(f"  H4={cam_row['H4']}  H3={cam_row['H3']}  H1={cam_row['H1']}  "
          f"L1={cam_row['L1']}  L3={cam_row['L3']}  L4={cam_row['L4']}")
    print(f"  Buy zone at L4 = ₹{cam_row['L4']}  |  Sell zone at H4 = ₹{cam_row['H4']}")

    # ── Fibonacci ──
    fib = auto_fibonacci(df, lookback=60)
    print(f"\n  ── Fibonacci Levels (last 60 days) ──")
    print(f"  Swing High: ₹{fib['swing_high']}  Swing Low: ₹{fib['swing_low']}  Trend: {fib['direction'].upper()}")
    print(f"  Retracements: ", end='')
    for level, price in list(fib['retracements'].items())[1:-1]:
        print(f"  {level}=₹{price}", end='')
    print(f"\n  Extensions:   ", end='')
    for level, price in fib['extensions'].items():
        print(f"  {level}=₹{price}", end='')
    print()

    print(f"\n{'='*70}\n")


# ════════════════════════════════════════════════════════════
# SECTION 10 — 4-PANEL CHART
# ════════════════════════════════════════════════════════════

def plot_extension_chart(df, ticker):
    """
    4-panel chart:
        1. Price + Ichimoku Cloud + Parabolic SAR + Pivot
        2. Williams %R + Aroon
        3. Awesome Oscillator + Momentum
        4. CMF + Historical Volatility
    """
    # matplotlib is only needed for this CLI chart; imported lazily so the web app never loads it.
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    # Calculate all series
    tenkan, kijun, senkou_a, senkou_b, chikou = calc_ichimoku(df)
    sar, trend = calc_parabolic_sar(df)
    wr         = calc_williams_r(df)
    ao         = calc_awesome_oscillator(df)
    mom        = calc_momentum(df['Close'])
    hv         = calc_historical_volatility(df['Close'])
    cmf        = calc_cmf(df)
    aroon_up, aroon_down, aroon_osc = calc_aroon(df)
    pivots     = calc_pivot_points(df)

    fig = plt.figure(figsize=(16, 14))
    gs  = gridspec.GridSpec(4, 1, height_ratios=[4, 2, 2, 2], hspace=0.08)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)

    # ── Panel 1: Price + Ichimoku + SAR ──

    # Ichimoku cloud (shade between Span A and Span B)
    # Use iloc[-26] offset approximation for alignment
    ax1.fill_between(df.index, senkou_a.values, senkou_b.values,
                     where=(senkou_a >= senkou_b),
                     alpha=0.15, color='#1D9E75', label='Bullish cloud')
    ax1.fill_between(df.index, senkou_a.values, senkou_b.values,
                     where=(senkou_a < senkou_b),
                     alpha=0.15, color='#E24B4A', label='Bearish cloud')

    # Ichimoku lines
    ax1.plot(df.index, tenkan, color='#378ADD', linewidth=1.2,
             linestyle='--', label='Tenkan (9)', alpha=0.8)
    ax1.plot(df.index, kijun,  color='#E24B4A', linewidth=1.5,
             linestyle='--', label='Kijun (26)',  alpha=0.8)

    # Price
    ax1.plot(df.index, df['Close'], color='#444441',
             linewidth=1.3, label='Close', zorder=4)

    # Parabolic SAR dots
    up_idx   = trend == 1
    down_idx = trend == -1
    ax1.scatter(df.index[up_idx.values],   sar[up_idx.values],
                c='#1D9E75', s=6, marker='o', zorder=5, label='SAR (bull)')
    ax1.scatter(df.index[down_idx.values], sar[down_idx.values],
                c='#E24B4A', s=6, marker='o', zorder=5, label='SAR (bear)')

    # Today's pivot point
    today_pp = pivots['PP'].iloc[-1]
    ax1.axhline(y=today_pp, color='#EF9F27', linewidth=1,
                linestyle=':', alpha=0.7, label=f'Pivot ₹{today_pp}')

    ax1.set_title(f'{ticker} — Extension Indicators', fontsize=13)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.legend(fontsize=7, loc='upper left', ncol=4)
    ax1.grid(True, alpha=0.2)

    # ── Panel 2: Williams %R + Aroon ──
    ax2.plot(df.index, wr, color='#7F77DD', linewidth=1.5, label='Williams %R (14)')
    ax2.axhline(y=-20, color='#E24B4A', linewidth=1, linestyle='--', alpha=0.7)
    ax2.axhline(y=-80, color='#1D9E75', linewidth=1, linestyle='--', alpha=0.7)
    ax2.fill_between(df.index, wr, -20, where=(wr > -20), alpha=0.15, color='#E24B4A')
    ax2.fill_between(df.index, wr, -80, where=(wr < -80), alpha=0.15, color='#1D9E75')
    ax2.set_ylim(-105, 5)
    ax2.set_ylabel('%R / Aroon', fontsize=10)

    ax2_r = ax2.twinx()
    ax2_r.plot(df.index, aroon_up,   color='#1D9E75', linewidth=1.2,
               linestyle='-.', alpha=0.7, label='Aroon Up')
    ax2_r.plot(df.index, aroon_down, color='#E24B4A', linewidth=1.2,
               linestyle='-.', alpha=0.7, label='Aroon Dn')
    ax2_r.set_ylim(-10, 110)
    ax2_r.set_ylabel('Aroon', fontsize=9)
    ax2.legend(fontsize=8, loc='upper left')
    ax2_r.legend(fontsize=8, loc='upper right')
    ax2.grid(True, alpha=0.2)

    # ── Panel 3: Awesome Oscillator + Momentum ──
    # AO as histogram (green if rising, red if falling)
    ao_colors = ['#1D9E75' if ao.iloc[i] >= ao.iloc[i-1] else '#E24B4A'
                 for i in range(len(ao))]
    ao_colors[0] = '#888780'
    ax3.bar(df.index, ao, color=ao_colors, alpha=0.7, width=1, label='AO')
    ax3.axhline(y=0, color='#888780', linewidth=0.8)
    ax3.set_ylabel('AO', fontsize=10)
    ax3.legend(fontsize=8, loc='upper left')

    ax3_r = ax3.twinx()
    ax3_r.plot(df.index, mom, color='#534AB7', linewidth=1.5,
               label='MOM (10)', alpha=0.8)
    ax3_r.axhline(y=0, color='#534AB7', linewidth=0.5, linestyle=':', alpha=0.4)
    ax3_r.set_ylabel('MOM (₹)', fontsize=9)
    ax3_r.legend(fontsize=8, loc='upper right')
    ax3.grid(True, alpha=0.2)

    # ── Panel 4: CMF + Historical Volatility ──
    ax4.bar(df.index, cmf,
            color=['#1D9E75' if v >= 0 else '#E24B4A' for v in cmf],
            alpha=0.7, width=1, label='CMF (20)')
    ax4.axhline(y=0.25,  color='#1D9E75', linewidth=1, linestyle='--', alpha=0.6)
    ax4.axhline(y=-0.25, color='#E24B4A', linewidth=1, linestyle='--', alpha=0.6)
    ax4.axhline(y=0, color='#888780', linewidth=0.8)
    ax4.set_ylabel('CMF', fontsize=10)
    ax4.legend(fontsize=8, loc='upper left')

    ax4_r = ax4.twinx()
    ax4_r.plot(df.index, hv, color='#EF9F27', linewidth=1.8,
               label='HV % (20d annualised)')
    ax4_r.set_ylabel('HV %', fontsize=9)
    ax4_r.legend(fontsize=8, loc='upper right')
    ax4.grid(True, alpha=0.2)

    plt.tight_layout()
    fname = f"{ticker.replace('.','_')}_extension_indicators.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"\nChart saved: {fname}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 11 — MAIN
# ════════════════════════════════════════════════════════════

def main():
    """
    Usage:
        python indicators_extension.py                → RELIANCE.NS, 1y
        python indicators_extension.py HDFCBANK       → any NSE stock
        python indicators_extension.py SBIN 2y        → with period
    """
    args   = sys.argv[1:]
    ticker_input = args[0] if args else "RELIANCE"
    period       = args[1] if len(args) > 1 else "1y"

    if not ticker_input.endswith('.NS'):
        ticker = ticker_input.upper() + '.NS'
    else:
        ticker = ticker_input.upper()

    df = get_data(ticker, period)

    # Print full summary
    print_extension_summary(df, ticker)

    # Run all detectable signals
    signals = run_all_extension_signals(df)
    if signals:
        print(f"\n  ── All Signals (last 10) ──")
        for sig in signals[-10:]:
            tag = "BUY   " if sig['Signal'] == 'BUY' else "SELL  "
            print(f"  {sig['Date']}  {tag}  {sig['Type']:<25}  ₹{sig['Close']}")
            print(f"           {sig['Detail']}")

    # Plot chart
    plot_extension_chart(df, ticker)


if __name__ == "__main__":
    main()