# ============================================================
# ADVANCED & SPECIALIST INDICATORS
# Final extension to the indicator library
# ============================================================
#
# INDICATORS IN THIS FILE:
#
# TREND (Reduced-Lag Moving Averages):
#   1.  DEMA  — Double EMA — half the lag of standard EMA
#   2.  TEMA  — Triple EMA — even less lag than DEMA
#   3.  Hull MA (HMA) — smoothest, most responsive MA
#   4.  VWMA  — Volume Weighted MA — volume-adjusted fair value
#   5.  Williams Alligator — 3 offset SMAs showing trend state
#
# MOMENTUM:
#   6.  TRIX  — Triple-smoothed ROC — noise filter extraordinaire
#   7.  PPO   — Percentage Price Oscillator — MACD as percentage
#   8.  DPO   — Detrended Price Oscillator — isolates price cycles
#
# MARKET BREADTH (index-level, needs multiple tickers):
#   9.  Advance-Decline Line — stocks rising vs falling
#   10. McClellan Oscillator  — smoothed A-D momentum
#   11. New Highs / New Lows  — 52-week extreme ratio
#
# VOLUME:
#   12. Klinger Oscillator    — long-term money flow
#   13. Force Index           — price change × volume
#   14. Ease of Movement (EMV) — price movement per volume unit
#
# VOLATILITY:
#   15. Ulcer Index           — downside-only drawdown risk
#
# HOW TO USE:
#   Standalone:
#       python advanced_indicators.py
#       python advanced_indicators.py TATAMOTORS
#       python advanced_indicators.py INFY 2y
#
#   Import into screener/backtester:
#       from advanced_indicators import calc_hma, calc_trix, calc_force_index
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
# SECTION 2 — REDUCED-LAG MOVING AVERAGES
# The core problem with SMA and EMA: they lag behind price.
# The more smoothing you apply, the more lag you introduce.
# These four MAs solve that problem in different ways.
# ════════════════════════════════════════════════════════════

def calc_ema(series, period):
    """Standard EMA — helper used by all indicators below."""
    return series.ewm(span=period, adjust=False).mean()


# ── 2a: DEMA — Double Exponential Moving Average ─────────────
def calc_dema(series, period):
    """
    DEMA — Double Exponential Moving Average.
    Created by Patrick Mulloy (1994), published in Stocks & Commodities.

    Standard EMA has a lag of roughly period/2 bars.
    DEMA halves that lag by applying a correction factor.

    The intuition behind the formula:
        If EMA already lags behind price, and you apply EMA again
        to that lagging line, the second EMA lags even MORE.
        The trick: subtract the extra lag instead of adding it.

    Formula:
        EMA1  = EMA(price, period)
        EMA2  = EMA(EMA1, period)    ← EMA of EMA
        DEMA  = 2 × EMA1 − EMA2

    Why 2 × EMA1 − EMA2?
        EMA1 lags price by L bars.
        EMA2 lags EMA1 by L bars → total lag = 2L bars.
        DEMA = EMA1 + (EMA1 − EMA2) = EMA1 + correction
        The correction (EMA1 − EMA2) cancels out one period of lag.
        Net result: lag reduced from L to approximately 0.

    Practical effect:
        DEMA tracks price much more closely than EMA.
        It turns sooner, crosses signals form faster.
        The trade-off: slightly more noise than EMA.
        Use DEMA where speed matters more than smoothness.

    Parameters:
        series (Series): Price data (usually close)
        period (int): EMA period

    Returns:
        Series: DEMA values
    """
    ema1 = calc_ema(series, period)
    ema2 = calc_ema(ema1,   period)
    dema = (2 * ema1) - ema2
    return dema.round(4)


# ── 2b: TEMA — Triple Exponential Moving Average ─────────────
def calc_tema(series, period):
    """
    TEMA — Triple Exponential Moving Average.
    Also by Patrick Mulloy (1994) — the logical extension of DEMA.

    Takes DEMA one step further: apply the lag-reduction trick
    using three layers of EMA instead of two.

    Formula:
        EMA1  = EMA(price, period)
        EMA2  = EMA(EMA1, period)
        EMA3  = EMA(EMA2, period)
        TEMA  = 3×EMA1 − 3×EMA2 + EMA3

    This is the result of applying the binomial correction formula:
        TEMA = EMA1×3 − EMA2×3 + EMA3×1
    (Coefficients: 3, -3, 1 — derived from Pascal's triangle)

    Each additional EMA layer costs more lag but the correction
    removes more lag. TEMA achieves near-zero lag.

    DEMA vs TEMA vs EMA in practice:
        EMA  → smoothest, slowest to react
        DEMA → faster, slightly noisier
        TEMA → fastest, most noise-prone

    When to use TEMA:
        Fast-moving markets where catching the trend early is critical.
        Intraday scalping on 1-minute or 5-minute charts.
        NOT for daily charts of slow-moving large caps (too noisy).

    Parameters:
        series (Series): Price data
        period (int): EMA period

    Returns:
        Series: TEMA values
    """
    ema1 = calc_ema(series, period)
    ema2 = calc_ema(ema1,   period)
    ema3 = calc_ema(ema2,   period)
    tema = (3 * ema1) - (3 * ema2) + ema3
    return tema.round(4)


# ── 2c: Hull Moving Average (HMA) ────────────────────────────
def calc_hma(series, period):
    """
    Hull Moving Average (HMA), created by Alan Hull in 2005.
    Considered the best moving average for minimising lag while
    maintaining smoothness. Widely used in professional trading systems.

    The problem with DEMA/TEMA: removing lag often adds noise.
    Hull's insight: use WEIGHTED moving averages (WMA) instead of EMA,
    and apply the correction in a clever two-step way.

    Formula:
        Step 1: WMA of half the period (fast WMA)
        Step 2: WMA of full period (slow WMA)
        Step 3: Raw = 2 × WMA(period/2) − WMA(period)
                → This removes lag but is still noisy
        Step 4: HMA = WMA(√period) of Raw
                → Final smoothing using square root of period

    Why √period for the final step?
        Square root gives just enough smoothing to remove the noise
        introduced in Step 3 without reintroducing significant lag.
        It's the minimum smoothing needed for a clean line.

    WMA vs EMA:
        EMA weights decrease EXPONENTIALLY (more weight to recent bars)
        WMA weights decrease LINEARLY (today = N, yesterday = N-1, etc.)
        WMA is more responsive to the most recent price action.

    Properties of HMA:
        1. Almost zero lag — turns almost immediately when trend changes
        2. Very smooth despite the low lag
        3. Works on any timeframe
        4. The direction of HMA slope is very clear (rising or falling)

    Trading use:
        HMA slope direction = trend direction
        HMA rising → uptrend → buy
        HMA falling → downtrend → sell/avoid
        HMA flattening → trend ending → reduce position

    Parameters:
        series (Series): Price data
        period (int): Main period

    Returns:
        Series: HMA values
    """

    def wma(s, n):
        """
        Weighted Moving Average.
        Weights: today=n, yesterday=n-1, ..., oldest=1
        Sum of weights = n(n+1)/2
        """
        weights = np.arange(1, n + 1, dtype=float)   # [1, 2, 3, ..., n]

        def weighted_mean(window):
            if len(window) < n:
                return float('nan')
            return np.dot(window, weights) / weights.sum()

        return s.rolling(window=n, min_periods=n).apply(weighted_mean, raw=True)

    half_period = max(int(period / 2), 1)
    sqrt_period = max(int(np.sqrt(period)), 1)

    # Step 1 & 2: Two WMAs
    wma_half = wma(series, half_period)
    wma_full = wma(series, period)

    # Step 3: Remove lag (raw series)
    raw = 2 * wma_half - wma_full

    # Step 4: Smooth with WMA(√period) for clean final line
    hma = wma(raw, sqrt_period)

    return hma.round(4)


# ── 2d: VWMA — Volume Weighted Moving Average ────────────────
def calc_vwma(df, period=20):
    """
    VWMA — Volume Weighted Moving Average.

    A simple but powerful improvement on SMA: instead of giving
    equal weight to each day's price, weight each day's price
    by how much volume traded that day.

    Rationale:
        A day with 10 crore shares traded is far more significant
        than a day with 10 lakh shares traded.
        VWMA incorporates this by giving the high-volume days
        more influence on the average.

    Formula:
        VWMA = Sum(Close × Volume over N days) /
               Sum(Volume over N days)

    This is essentially the "fair value" as determined by the
    actual weight of money that traded at each price level.

    VWMA vs SMA:
        SMA: simple average of prices, ignores volume
        VWMA: volume-weighted average, prices that traded
              on high-volume days have more influence

    When VWMA > SMA:
        High-volume days were at higher prices → institutions
        were buying on the strong days → bullish bias

    When VWMA < SMA:
        High-volume days were at lower prices → institutions
        were selling on the strong volume days → bearish bias

    The spread between VWMA and SMA is itself a signal:
        Growing spread (VWMA diverging from SMA) → one side
        gaining dominance in the volume-weighted picture.

    Parameters:
        df (DataFrame): Must have Close and Volume
        period (int): Rolling period (default 20)

    Returns:
        Series: VWMA values
    """
    close  = df['Close']
    volume = df['Volume'].astype(float)

    # Price × Volume for each day
    pv = close * volume

    # VWMA = rolling sum of (Price × Volume) / rolling sum of Volume
    vwma = (pv.rolling(window=period, min_periods=period).sum() /
            volume.rolling(window=period, min_periods=period).sum())

    return vwma.round(4)


# ── 2e: Williams Alligator ────────────────────────────────────
def calc_alligator(df):
    """
    Williams Alligator, created by Bill Williams.
    Published in "Trading Chaos" (1995).

    The Alligator uses three smoothed moving averages with offsets
    to describe the state of the market as an alligator:

        SLEEPING (lines intertwined):
            Market is in a range, no trend.
            Do NOT trade trend-following strategies.
            "The alligator is sleeping."

        AWAKENING (lines starting to separate):
            A trend is forming.
            Prepare to enter in the direction of separation.
            "The alligator is waking up."

        EATING (lines well separated, ordered):
            Strong trend in progress.
            Ride the trend.
            "The alligator is eating."

        SATED (lines starting to converge again):
            Trend is exhausting.
            Start taking profits.
            "The alligator is getting full."

    ─────────────────────────────────────────────────────────
    The Three Lines:

    JAW (Blue line):
        SMMA(13, shifted 8 bars forward) — slowest, widest jaw
        Uses 13-bar Smoothed Moving Average of midprice,
        displaced 8 bars to the right.

    TEETH (Red line):
        SMMA(8, shifted 5 bars forward) — medium
        Uses 8-bar SMMA of midprice, displaced 5 bars.

    LIPS (Green line):
        SMMA(5, shifted 3 bars forward) — fastest
        Uses 5-bar SMMA of midprice, displaced 3 bars.

    Midprice = (High + Low) / 2

    SMMA (Smoothed MA) is a type of EMA with alpha = 1/period.
    It is smoother than standard EMA and is Bill Williams' preferred
    averaging method.

    ─────────────────────────────────────────────────────────
    Trading Signals:

    BUY when:
        Lips crosses above Teeth AND Teeth crosses above Jaw
        = Lines ordered: Lips > Teeth > Jaw (fully awake, uptrend)
        Price must be ABOVE all three lines.

    SELL when:
        Lips crosses below Teeth AND Teeth crosses below Jaw
        = Lines ordered: Lips < Teeth < Jaw (downtrend)
        Price must be BELOW all three lines.

    EXIT / AVOID:
        Lines tangled or crossing frequently = sleeping alligator
        = choppy market, no trend-following trades.

    The displacement (offset) is intentional — it visualises the
    momentum of the lines rather than just their current values.
    Looking at the displaced lines, you can see where each MA
    was pointing on past bars, revealing the trajectory of momentum.

    Parameters:
        df (DataFrame): Must have High and Low

    Returns:
        jaw, teeth, lips (all Series, already displaced)
    """

    midprice = (df['High'] + df['Low']) / 2

    def smma(series, period):
        """
        Smoothed Moving Average (SMMA).
        Similar to EMA with alpha = 1/period (gentler smoothing).
        SMMA(n) is equivalent to EMA(2n - 1).
        """
        return series.ewm(alpha=1.0/period, adjust=False).mean()

    # Calculate the three SMAs
    jaw_raw   = smma(midprice, 13)
    teeth_raw = smma(midprice, 8)
    lips_raw  = smma(midprice, 5)

    # Apply forward displacement (shift BACKWARDS in index = display ahead)
    # .shift(-n) shifts the values n positions into the future on the chart
    jaw   = jaw_raw.shift(-8).round(4)
    teeth = teeth_raw.shift(-5).round(4)
    lips  = lips_raw.shift(-3).round(4)

    return jaw, teeth, lips


def detect_alligator_signals(df):
    """
    Detects Alligator awakening/sleeping signals.

    Returns:
        List of signal dicts
    """
    jaw, teeth, lips = calc_alligator(df)
    signals = []

    for i in range(1, len(df) - 8):   # Need future bars for displaced lines
        close   = df['Close'].iloc[i]
        j_now   = jaw.iloc[i]
        t_now   = teeth.iloc[i]
        l_now   = lips.iloc[i]
        j_prev  = jaw.iloc[i-1]
        t_prev  = teeth.iloc[i-1]
        l_prev  = lips.iloc[i-1]
        date    = df.index[i].date()

        if any(pd.isna(v) for v in [j_now, t_now, l_now, j_prev, t_prev, l_prev]):
            continue

        # BUY: lines just became fully ordered bullish (Lips > Teeth > Jaw)
        # and previous bar was NOT fully ordered
        bull_now  = l_now > t_now > j_now
        bull_prev = l_prev > t_prev > j_prev

        if bull_now and not bull_prev and close > j_now:
            signals.append({
                'Date'  : date,
                'Type'  : 'Alligator',
                'Signal': 'BUY',
                'Close' : round(close, 2),
                'Detail': f'Alligator awake — bullish. Lips>{round(l_now,1)} Teeth>{round(t_now,1)} Jaw>{round(j_now,1)}'
            })

        # SELL: lines just became fully ordered bearish
        bear_now  = l_now < t_now < j_now
        bear_prev = l_prev < t_prev < j_prev

        if bear_now and not bear_prev and close < j_now:
            signals.append({
                'Date'  : date,
                'Type'  : 'Alligator',
                'Signal': 'SELL',
                'Close' : round(close, 2),
                'Detail': f'Alligator awake — bearish. Lips<{round(l_now,1)} Teeth<{round(t_now,1)} Jaw<{round(j_now,1)}'
            })

    return signals


# ════════════════════════════════════════════════════════════
# SECTION 3 — MOMENTUM INDICATORS
# ════════════════════════════════════════════════════════════

# ── 3a: TRIX ─────────────────────────────────────────────────
def calc_trix(prices, period=15, signal_period=9):
    """
    TRIX — Triple Exponential Smoothed Rate of Change.
    Created by Jack Hutson, published in 1983.

    TRIX is a momentum oscillator that measures the PERCENTAGE
    RATE OF CHANGE of a triple-smoothed EMA.

    Formula:
        EMA1 = EMA(price, period)
        EMA2 = EMA(EMA1, period)
        EMA3 = EMA(EMA2, period)
        TRIX = (EMA3 - EMA3[prev day]) / EMA3[prev day] × 100

    In other words: TRIX = 1-period ROC of the triple-smoothed EMA.

    ─────────────────────────────────────────────────────────
    Why three layers of smoothing?
        Each EMA layer filters out noise.
        One EMA: some noise remains.
        Two EMAs (like MACD): less noise.
        Three EMAs: very little noise — only meaningful trends survive.

    The triple smoothing makes TRIX an excellent FILTER:
        Short-term noise that confuses MACD is completely eliminated.
        Only SUSTAINED momentum moves show up in TRIX.
        This dramatically reduces false signals compared to MACD.

    TRIX vs MACD:
        MACD uses two EMAs (fast and slow), showing their difference.
        TRIX uses one period triple-smoothed, showing its rate of change.
        TRIX produces fewer signals but they are more reliable.
        MACD is more responsive; TRIX is more selective.

    Signal Line:
        Like MACD has a signal line (EMA of MACD),
        TRIX has a signal line (EMA of TRIX).
        TRIX crossing its signal line = buy/sell.

    Interpretation:
        TRIX > 0  : Triple-smoothed price is rising → uptrend
        TRIX < 0  : Triple-smoothed price is falling → downtrend
        TRIX crossing zero → major trend change (very reliable)
        TRIX crossing signal line → shorter-term signal

    Divergence:
        Price making new highs but TRIX declining → bearish divergence
        Price making new lows but TRIX rising → bullish divergence

    Parameters:
        prices (Series): Closing prices
        period (int): EMA period for triple smoothing (default 15)
        signal_period (int): Signal line EMA period (default 9)

    Returns:
        trix (Series), signal (Series)
    """

    ema1 = calc_ema(prices, period)
    ema2 = calc_ema(ema1,   period)
    ema3 = calc_ema(ema2,   period)

    # 1-period percentage rate of change of EMA3
    trix   = ((ema3 - ema3.shift(1)) / ema3.shift(1).replace(0, float('nan'))) * 100
    signal = calc_ema(trix, signal_period)

    return trix.round(6), signal.round(6)


# ── 3b: PPO — Percentage Price Oscillator ────────────────────
def calc_ppo(prices, fast=12, slow=26, signal=9):
    """
    PPO — Percentage Price Oscillator.

    PPO is MACD expressed as a percentage of the slow EMA,
    rather than as an absolute value.

    Formula:
        MACD Line  = EMA(12) - EMA(26)
        PPO        = (EMA(12) - EMA(26)) / EMA(26) × 100
        PPO Signal = EMA(9) of PPO
        PPO Hist   = PPO - PPO Signal

    PPO = MACD / EMA(26) × 100

    ─────────────────────────────────────────────────────────
    Why PPO instead of MACD?
        MACD is in ABSOLUTE price units (rupees).
        This makes comparison across different stocks impossible:
            MACD of 50 for a ₹500 stock is very different from
            MACD of 50 for a ₹5000 stock.

        PPO normalises by price level, expressing as a percentage:
            PPO of 2.5% means the same thing regardless of stock price.

    When to use PPO over MACD:
        1. Comparing momentum across stocks with different price levels
           (e.g. which stock has stronger momentum: HDFC at ₹1600 or
           Reliance at ₹2600? PPO gives comparable readings.)

        2. Backtesting a strategy across many different stocks
           (PPO thresholds work consistently; MACD thresholds don't)

        3. When screening for stocks with strong momentum
           (a PPO > 2.5% filter is meaningful; MACD > 50 is not)

    All MACD signals work identically with PPO:
        Crossover, zero line, divergence, histogram analysis.
        The only difference is the scale.

    Parameters:
        prices (Series): Closing prices
        fast (int): Fast EMA period (default 12)
        slow (int): Slow EMA period (default 26)
        signal (int): Signal line period (default 9)

    Returns:
        ppo (Series), signal_line (Series), histogram (Series)
    """

    ema_fast = calc_ema(prices, fast)
    ema_slow = calc_ema(prices, slow)

    # PPO = percentage difference between fast and slow EMA
    ppo_line    = ((ema_fast - ema_slow) /
                   ema_slow.replace(0, float('nan'))) * 100
    signal_line = calc_ema(ppo_line, signal)
    histogram   = ppo_line - signal_line

    return ppo_line.round(4), signal_line.round(4), histogram.round(4)


# ── 3c: DPO — Detrended Price Oscillator ─────────────────────
def calc_dpo(prices, period=20):
    """
    DPO — Detrended Price Oscillator.

    DPO removes the dominant trend from price data to reveal the
    underlying CYCLES in price movement.

    Most prices show both a trend AND cycles around that trend.
    For example, a stock might be in a 6-month uptrend, but within
    that trend it cycles up and down every 3-4 weeks.
    DPO filters out the trend and lets you see those cycles clearly.

    Formula:
        DPO = Close - SMA(period) shifted (period/2 + 1) days back

    The shift is crucial:
        By comparing today's close to the SMA from (period/2 + 1) bars ago,
        we centre the comparison in time — this eliminates the
        directional trend component and leaves only the cyclic component.

    Interpretation:
        DPO oscillates above and below zero.
        DPO peaks and troughs identify the CYCLE HIGH and CYCLE LOW points.
        The time between peaks = the dominant cycle length.

        DPO at a peak → price at top of its cycle → sell signal
        DPO at a trough → price at bottom of its cycle → buy signal

    DPO is NOT designed for identifying trends (use ADX/Supertrend for that).
    It's specifically for identifying the timing of cyclic moves
    within an established trend.

    Practical use:
        1. Measure the cycle: count bars between DPO peaks
           → this is your dominant cycle length
        2. Buy when DPO troughs in an uptrend (cycle low in a bullish market)
        3. Sell when DPO peaks in a downtrend (cycle high in a bearish market)

    Parameters:
        prices (Series): Closing prices
        period (int): Cycle detection period (default 20)

    Returns:
        Series: DPO values
    """

    # Shift by (period/2 + 1) to centre the comparison
    shift      = int(period / 2) + 1
    shifted_ma = prices.rolling(window=period, min_periods=period).mean().shift(shift)
    dpo        = prices - shifted_ma

    return dpo.round(4)


# ════════════════════════════════════════════════════════════
# SECTION 4 — MARKET BREADTH INDICATORS
# These work on a UNIVERSE of stocks, not a single ticker.
# They tell you whether the overall market is healthy.
# ════════════════════════════════════════════════════════════

def calc_advance_decline(tickers, period="6mo"):
    """
    Advance-Decline Line (A-D Line).

    The most fundamental market breadth indicator.
    Measures how many stocks are advancing (going up) vs
    declining (going down) each day.

    Formula:
        A-D Value(day) = Number of advancing stocks
                         - Number of declining stocks

        A-D Line = Cumulative sum of A-D values

    Interpretation:
        A-D Line rising while index rising → healthy rally
            → most stocks participating → sustainable uptrend

        A-D Line falling while index rising → unhealthy rally
            → fewer stocks participating → divergence = WARNING
            → the index is being held up by only a few large caps
            → this divergence often precedes a market top

        A-D Line rising while index falling → likely bottom
            → most stocks already recovering → index lag → buy signal

    Historical importance:
        The A-D Line divergence warned before major crashes:
        1929, 1987, 2000, 2008 — in each case, the A-D Line peaked
        months before the index peaked.

    Parameters:
        tickers (list): List of stock symbols (e.g. Nifty 50)
        period (str): Historical period to analyse

    Returns:
        DataFrame with columns: advancing, declining, unchanged, ad_value, ad_line
    """
    print(f"\n  Downloading {len(tickers)} stocks for breadth analysis...")

    # Download all close prices at once (faster than one by one)
    data = yf.download(tickers, period=period, auto_adjust=True,
                       progress=False)['Close']
    data.dropna(how='all', inplace=True)

    # Daily percentage change for each stock
    returns = data.pct_change()

    # Count advancing, declining, unchanged each day
    advancing  = (returns > 0).sum(axis=1)
    declining  = (returns < 0).sum(axis=1)
    unchanged  = (returns == 0).sum(axis=1)

    # A-D Value = difference each day
    ad_value = advancing - declining

    # A-D Line = cumulative sum
    ad_line  = ad_value.cumsum()

    result = pd.DataFrame({
        'Advancing' : advancing,
        'Declining' : declining,
        'Unchanged' : unchanged,
        'AD_Value'  : ad_value,
        'AD_Line'   : ad_line,
    })

    return result


def calc_mcclellan_oscillator(ad_data):
    """
    McClellan Oscillator, created by Sherman and Marian McClellan (1969).

    The McClellan Oscillator smooths the A-D Line to reveal
    short-term momentum in market breadth.

    Formula:
        McClellan = EMA(19) of AD_Value - EMA(39) of AD_Value

    This is exactly like MACD but applied to the Advance-Decline value
    instead of price. Like MACD:
        Positive = upward momentum in breadth
        Negative = downward momentum in breadth
        Crossing zero = breadth momentum reversing

    The McClellan Summation Index (sum of the oscillator) is a
    longer-term version — not calculated here but easily derived.

    Interpretation:
        McClellan > +100  : Overbought breadth — market extended
        McClellan < -100  : Oversold breadth — potential rally coming
        McClellan crossing zero from below → breadth improving (BUY)
        McClellan crossing zero from above → breadth deteriorating (SELL)
        Divergence with index → major signal (similar to price divergence)

    Parameters:
        ad_data (DataFrame): Output of calc_advance_decline()

    Returns:
        Series: McClellan Oscillator values
    """

    ad_value = ad_data['AD_Value']

    ema19 = calc_ema(ad_value, 19)
    ema39 = calc_ema(ad_value, 39)

    mcclellan = ema19 - ema39
    return mcclellan.round(2)


def calc_new_highs_lows(tickers, period="1y"):
    """
    New 52-Week Highs and Lows.

    Counts how many stocks are making new 52-week highs
    vs new 52-week lows each day.

    A strong bull market sees many new highs and few new lows.
    A deteriorating market sees the ratio flip — new lows start
    outnumbering new highs even before the index falls.

    Formula:
        New High: Close today = highest close of the last 252 trading days
        New Low:  Close today = lowest close of the last 252 trading days
        NH-NL Index = New Highs - New Lows
        NH-NL Ratio = New Highs / (New Highs + New Lows) × 100

    Interpretation:
        NH-NL > 0  : More stocks at yearly highs than lows → bullish
        NH-NL < 0  : More stocks at yearly lows than highs → bearish
        NH-NL Ratio > 70% → broad rally, high participation → sustainable
        NH-NL Ratio < 30% → narrow rally → breadth divergence → warning
        Ratio dropping from 80%+ to below 50% → major warning signal

    Parameters:
        tickers (list): List of stock symbols
        period (str): Must be at least "1y" to calculate 52-week extremes

    Returns:
        DataFrame with new_highs, new_lows, nh_nl_diff, nh_nl_ratio
    """
    print(f"\n  Downloading {len(tickers)} stocks for New High/Low analysis...")

    data = yf.download(tickers, period=period, auto_adjust=True,
                       progress=False)['Close']
    data.dropna(how='all', inplace=True)

    window = 252   # 252 trading days = approximately 1 year

    # For each day, is today's close the highest in the last 252 days?
    rolling_max = data.rolling(window=window, min_periods=window).max()
    rolling_min = data.rolling(window=window, min_periods=window).min()

    new_highs = (data >= rolling_max).sum(axis=1)
    new_lows  = (data <= rolling_min).sum(axis=1)

    nh_nl_diff  = new_highs - new_lows
    total       = (new_highs + new_lows).replace(0, float('nan'))
    nh_nl_ratio = (new_highs / total * 100).round(2)

    result = pd.DataFrame({
        'New_Highs'   : new_highs,
        'New_Lows'    : new_lows,
        'NH_NL_Diff'  : nh_nl_diff,
        'NH_NL_Ratio' : nh_nl_ratio,
    })

    return result


# ════════════════════════════════════════════════════════════
# SECTION 5 — VOLUME INDICATORS
# ════════════════════════════════════════════════════════════

# ── 5a: Klinger Volume Oscillator ────────────────────────────
def calc_klinger(df, fast=34, slow=55, signal=13):
    """
    Klinger Volume Oscillator (KVO), created by Stephen Klinger (1977).

    The Klinger Oscillator attempts to determine the long-term
    money flow trend in a stock while remaining sensitive enough
    to detect short-term fluctuations.

    Key concept — Volume Force (VF):
        Not all volume is equal. Volume is more significant when:
        1. Price is moving in a consistent direction
        2. The daily range is expanding
        3. The close is near the high (positive) or low (negative)

    Volume Force Formula:
        Typical Price = (High + Low + Close) / 3

        Trend = +1 if TP > TP[yesterday]
        Trend = -1 if TP ≤ TP[yesterday]

        Daily Range (cm) = |High - Low|

        DM (Directional Movement for Klinger) = High - Low

        VF = Volume × |2 × DM/cm - 1| × Trend × 100

    KVO = EMA(VF, fast) - EMA(VF, slow)
    Signal = EMA(KVO, signal_period)

    ─────────────────────────────────────────────────────────
    Interpretation:
        KVO positive → bullish money flow → more buying than selling
        KVO negative → bearish money flow → more selling
        KVO crossing above signal line → BUY
        KVO crossing below signal line → SELL
        KVO crossing zero → long-term money flow direction changed

    KVO excels at catching major trend reversals before they become
    obvious in price. The divergence between KVO and price direction
    is its strongest signal.

    Parameters:
        df (DataFrame): Must have High, Low, Close, Volume
        fast (int): Fast EMA period (default 34)
        slow (int): Slow EMA period (default 55)
        signal (int): Signal line period (default 13)

    Returns:
        kvo (Series), signal_line (Series)
    """

    high  = df['High']
    low   = df['Low']
    close = df['Close']
    vol   = df['Volume'].astype(float)

    # Typical price
    tp = (high + low + close) / 3

    # Trend direction: is typical price rising or falling?
    trend = np.where(tp > tp.shift(1), 1, -1)
    trend = pd.Series(trend, index=df.index)

    # Daily range
    dm = high - low

    # Cumulative price movement (rolling sum)
    cm = dm.rolling(window=2, min_periods=2).sum()

    # Volume Force
    dm_cm_ratio = (dm / cm.replace(0, float('nan'))).fillna(0)
    vf = vol * np.abs(2 * dm_cm_ratio - 1) * trend * 100

    # KVO = difference between fast and slow EMA of VF
    kvo         = calc_ema(vf, fast) - calc_ema(vf, slow)
    signal_line = calc_ema(kvo, signal)

    return kvo.round(2), signal_line.round(2)


# ── 5b: Force Index ──────────────────────────────────────────
def calc_force_index(df, period=13):
    """
    Force Index, created by Dr Alexander Elder.
    Published in "Trading for a Living" (1993).

    The simplest and most transparent volume-price indicator:
    it multiplies the directional price change by volume.

    Formula (raw):
        Force(today) = (Close today - Close yesterday) × Volume today

    This gives you the RAW FORCE behind each day's move.
    Then smooth it with EMA to remove noise:
        Force Index(n) = EMA(n) of raw Force

    ─────────────────────────────────────────────────────────
    Why this works:
        Force = Direction × Magnitude × Participation
        Direction   → whether close is higher or lower (sign of change)
        Magnitude   → how much price moved (size of change)
        Participation → how many shares traded (volume)

        A large price move with huge volume = very large Force.
        A small price move with tiny volume = very small Force.

    Interpretation:
        Force Index > 0  : Buyers are winning (bullish)
        Force Index < 0  : Sellers are winning (bearish)
        Rising Force Index → momentum building
        Falling Force Index → momentum fading

    Elder's two-period uses:
        2-period Force Index (very fast, almost raw):
            → Entry timing: buy when 2-period FI dips below zero
              in an uptrend (momentary selling in a bull market)
        13-period Force Index (smoothed, trend):
            → Trend filter: positive = uptrend, negative = downtrend

    The simplicity is the strength: Force Index is impossible to
    misunderstand. It directly measures what it says it measures.

    Parameters:
        df (DataFrame): Must have Close and Volume
        period (int): EMA smoothing period (default 13)

    Returns:
        Series: Force Index values
    """

    # Raw force: price change × volume
    raw_force = df['Close'].diff(1) * df['Volume'].astype(float)

    # Smooth with EMA
    force_index = calc_ema(raw_force, period)

    return force_index.round(2)


# ── 5c: Ease of Movement (EMV) ───────────────────────────────
def calc_ease_of_movement(df, period=14):
    """
    Ease of Movement (EMV), created by Richard Arms Jr.

    The core question EMV answers: how EASILY is price moving?

    Two stocks both move ₹10 today. But:
        Stock A moved ₹10 on 1 crore shares → hard to move (heavy volume)
        Stock B moved ₹10 on 10 lakh shares → easy to move (light volume)

    EMV captures this ratio of price movement to volume.

    Formula:
        Midpoint Move = ((High + Low)/2) - ((High[prev] + Low[prev])/2)
        Box Ratio     = Volume / (High - Low)
        Raw EMV       = Midpoint Move / Box Ratio
        EMV           = SMA(Raw EMV, period)

    The "Box Ratio" is the volume per unit of price range.
    High box ratio = lots of volume needed to move each unit of price.
    Low box ratio  = little volume needed to move price (price moves easily).

    ─────────────────────────────────────────────────────────
    Interpretation:
        EMV > 0  : Prices are rising with ease → buyers in control
        EMV < 0  : Prices are falling with ease → sellers in control
        EMV near zero → price is not moving easily in either direction
                        → possible congestion or consolidation

        Large positive EMV → price rising on LOW volume (easy move up)
                             → could indicate lack of selling pressure,
                               but also could mean thin/unsustained rally
        Large negative EMV → price falling easily on low volume
                             → sellers in control, little buying interest

    Primary use:
        Divergence with price.
        If price is rising but EMV is declining → price having increasing
        difficulty moving up → possible exhaustion ahead.

    Parameters:
        df (DataFrame): Must have High, Low, Volume
        period (int): Smoothing period (default 14)

    Returns:
        Series: EMV values
    """

    # Midpoint of today's range vs midpoint of yesterday's range
    mid_today = (df['High'] + df['Low']) / 2
    mid_prev  = mid_today.shift(1)
    mid_move  = mid_today - mid_prev

    # Box ratio: volume per unit of price range
    hl_range  = (df['High'] - df['Low']).replace(0, float('nan'))
    box_ratio = df['Volume'].astype(float) / hl_range

    # Raw EMV = how easily did price move relative to volume?
    raw_emv = mid_move / box_ratio.replace(0, float('nan'))

    # Smooth to remove noise
    emv = raw_emv.rolling(window=period, min_periods=period).mean()

    # Scale to reasonable units (EMV values can be very small)
    emv = emv * 1e6

    return emv.round(6)


# ════════════════════════════════════════════════════════════
# SECTION 6 — VOLATILITY
# ════════════════════════════════════════════════════════════

def calc_ulcer_index(prices, period=14):
    """
    Ulcer Index, created by Peter Martin and Byron McCann (1987).
    Published in "The Investor's Guide to Fidelity Funds."

    Named "Ulcer" because it measures the kind of drawdowns that
    give investors ulcers — sustained, deep losses.

    The critical difference from ATR and standard volatility:
        ATR and standard deviation measure BOTH upside and downside
        volatility equally. A stock that goes up 5% daily has the
        same ATR as one that goes down 5% daily.

        Ulcer Index measures ONLY downside volatility —
        specifically, drawdowns from recent peaks.

    Formula:
        Step 1: For each day, calculate the Percentage Drawdown (PD):
                PD = (Price - Highest Price in last N days) /
                      Highest Price in last N days × 100
                PD is always ≤ 0 (it's a loss from peak)

        Step 2: Square all the percentage drawdowns
                (squaring penalises deeper drawdowns more than shallow ones)

        Step 3: Ulcer Index = √(Average of squared PDs over N days)

    This is essentially the RMS (Root Mean Square) of drawdowns —
    the same mathematical structure as standard deviation, but
    applied only to the drawdown values.

    ─────────────────────────────────────────────────────────
    Interpretation:
        UI = 5%   → Moderate drawdowns — comfortable to hold
        UI = 10%  → Significant drawdowns — stressful but manageable
        UI = 20%  → Large drawdowns — painful, may cause panic selling
        UI = 30%+ → Very deep/sustained drawdowns — extreme stress

    Practical uses:
        1. Compare two strategies with the same return:
           Lower Ulcer Index = less painful to hold → better strategy

        2. Martin Ratio = Return / Ulcer Index
           (Ulcer Index version of Sharpe Ratio — uses only downside risk)

        3. Screen for low-volatility/low-drawdown stocks
           Stocks with UI < 5 are smooth, comfortable long positions
           Stocks with UI > 20 are "rollercoaster" positions

        4. Position sizing: larger position in low-UI stocks,
           smaller position in high-UI stocks

    Parameters:
        prices (Series): Closing prices
        period (int): Lookback period (default 14)

    Returns:
        Series: Ulcer Index values (percentage)
    """

    # Step 1: Rolling maximum over the period
    rolling_max = prices.rolling(window=period, min_periods=period).max()

    # Step 2: Percentage drawdown from rolling max (always ≤ 0)
    pct_drawdown = ((prices - rolling_max) / rolling_max) * 100

    # Step 3: Square the drawdowns and take rolling mean
    squared_dd = pct_drawdown ** 2
    mean_sq_dd = squared_dd.rolling(window=period, min_periods=period).mean()

    # Step 4: Square root gives the Ulcer Index
    ulcer_index = np.sqrt(mean_sq_dd)

    return ulcer_index.round(4)


def calc_martin_ratio(prices, period=14, annual_return_pct=None):
    """
    Martin Ratio — the Ulcer Index version of the Sharpe Ratio.

    Martin Ratio = Annualised Return / Ulcer Index

    Higher is better:
        > 3.0 : Excellent — high return with very low drawdown stress
        > 1.0 : Good — returns justify the drawdown pain
        < 1.0 : Poor — drawdown pain exceeds returns
        < 0   : Returns are negative

    Parameters:
        prices (Series): Closing prices
        period (int): Ulcer Index period
        annual_return_pct (float): Annualised return as %. If None, calculated.

    Returns:
        float: Martin Ratio (a single number for the whole period)
    """

    if annual_return_pct is None:
        total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100
        years = len(prices) / 252
        annual_return_pct = ((1 + total_return/100) ** (1/max(years, 0.01)) - 1) * 100

    ui = calc_ulcer_index(prices, period)
    avg_ui = ui.dropna().mean()

    if avg_ui == 0:
        return float('inf')

    return round(annual_return_pct / avg_ui, 3)


# ════════════════════════════════════════════════════════════
# SECTION 7 — PRINT SUMMARY
# ════════════════════════════════════════════════════════════

def print_advanced_summary(df, ticker):
    """Prints current readings for all advanced indicators."""

    last  = df.iloc[-1]
    close = round(last['Close'], 2)

    print(f"\n{'='*70}")
    print(f"  ADVANCED INDICATORS — {ticker}")
    print(f"  As of: {df.index[-1].date()}")
    print(f"{'='*70}")

    # ── Reduced-lag MAs ──
    dema_val = round(calc_dema(df['Close'], 20).iloc[-1], 2)
    tema_val = round(calc_tema(df['Close'], 20).iloc[-1], 2)
    hma_val  = round(calc_hma(df['Close'],  20).iloc[-1], 2)
    vwma_val = round(calc_vwma(df, 20).iloc[-1], 2)
    sma_val  = round(df['Close'].rolling(20).mean().iloc[-1], 2)

    print(f"\n  ── Reduced-Lag Moving Averages (period=20) ──")
    print(f"  SMA 20   : ₹{sma_val}  (reference — most lag)")
    print(f"  EMA 20   : ₹{round(calc_ema(df['Close'],20).iloc[-1],2)}  (less lag than SMA)")
    print(f"  DEMA 20  : ₹{dema_val}  (half the lag of EMA)")
    print(f"  TEMA 20  : ₹{tema_val}  (near-zero lag)")
    print(f"  HMA 20   : ₹{hma_val}   (smoothest + fast)")
    print(f"  VWMA 20  : ₹{vwma_val}  (volume-weighted fair value)")

    # ── Alligator ──
    jaw, teeth, lips = calc_alligator(df)
    j_val = round(jaw.iloc[-1],   2) if not pd.isna(jaw.iloc[-1])   else 'N/A'
    t_val = round(teeth.iloc[-1], 2) if not pd.isna(teeth.iloc[-1]) else 'N/A'
    l_val = round(lips.iloc[-1],  2) if not pd.isna(lips.iloc[-1])  else 'N/A'
    if not isinstance(j_val, str):
        if l_val > t_val > j_val:
            gator = "EATING (bullish trend, lines ordered up)"
        elif l_val < t_val < j_val:
            gator = "EATING (bearish trend, lines ordered down)"
        else:
            gator = "SLEEPING/WAKING (lines tangled — no clear trend)"
    else:
        gator = "N/A"
    print(f"\n  ── Williams Alligator ──")
    print(f"  Jaw={j_val}  Teeth={t_val}  Lips={l_val}")
    print(f"  State : {gator}")

    # ── TRIX ──
    trix, trix_sig = calc_trix(df['Close'])
    trix_val    = round(trix.iloc[-1], 5)
    trix_sv     = round(trix_sig.iloc[-1], 5)
    print(f"\n  ── TRIX (15) ──")
    print(f"  TRIX    : {trix_val}")
    print(f"  Signal  : {trix_sv}")
    print(f"  Trend   : {'Positive momentum' if trix_val > 0 else 'Negative momentum'}")

    # ── PPO ──
    ppo, ppo_sig, ppo_hist = calc_ppo(df['Close'])
    ppo_val = round(ppo.iloc[-1], 4)
    ppos_val = round(ppo_sig.iloc[-1], 4)
    print(f"\n  ── PPO (12,26,9) ──")
    print(f"  PPO     : {ppo_val}%  Signal: {ppos_val}%")
    print(f"  Trend   : {'Bullish momentum' if ppo_val > 0 else 'Bearish momentum'}")

    # ── DPO ──
    dpo = calc_dpo(df['Close'])
    dpo_val = round(dpo.iloc[-1], 2)
    print(f"\n  ── DPO (20) ──")
    print(f"  DPO     : ₹{dpo_val}  ({'cycle high zone' if dpo_val > 0 else 'cycle low zone'})")

    # ── Volume indicators ──
    kvo, kvo_sig = calc_klinger(df)
    fi           = calc_force_index(df)
    emv          = calc_ease_of_movement(df)
    kvo_val      = round(kvo.iloc[-1], 0)
    fi_val       = round(fi.iloc[-1], 0)
    emv_val      = round(emv.iloc[-1], 4)

    print(f"\n  ── Volume Indicators ──")
    print(f"  Klinger Osc   : {kvo_val:,}  ({'positive MF' if kvo_val > 0 else 'negative MF'})")
    print(f"  Force Index(13): {fi_val:,}  ({'buyers winning' if fi_val > 0 else 'sellers winning'})")
    print(f"  Ease of Move  : {emv_val}  ({'easy upward move' if emv_val > 0 else 'easy downward move'})")

    # ── Ulcer Index ──
    ui     = calc_ulcer_index(df['Close'])
    ui_val = round(ui.iloc[-1], 2)
    mr     = calc_martin_ratio(df['Close'])
    ui_zone = ("Low pain (<5%)" if ui_val < 5
               else "Moderate (5-10%)" if ui_val < 10
               else "High pain (10-20%)" if ui_val < 20
               else "Severe pain (>20%)")
    print(f"\n  ── Ulcer Index (14) ──")
    print(f"  Ulcer Index   : {ui_val}%  → {ui_zone}")
    print(f"  Martin Ratio  : {mr}  (return/drawdown — higher is better)")

    print(f"\n{'='*70}\n")


# ════════════════════════════════════════════════════════════
# SECTION 8 — 4-PANEL CHART
# ════════════════════════════════════════════════════════════

def plot_advanced_chart(df, ticker):
    """
    4-panel chart:
        1. Price + HMA + DEMA + TEMA + Alligator
        2. TRIX + PPO
        3. Klinger + Force Index
        4. Ulcer Index + EMV
    """
    # matplotlib is only needed for this CLI chart; imported lazily so the web app never loads it.
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    hma  = calc_hma(df['Close'],  20)
    dema = calc_dema(df['Close'], 20)
    tema = calc_tema(df['Close'], 20)
    vwma = calc_vwma(df, 20)
    jaw, teeth, lips = calc_alligator(df)
    trix_line, trix_sig = calc_trix(df['Close'])
    ppo_line, ppo_sig, ppo_hist = calc_ppo(df['Close'])
    kvo, kvo_sig = calc_klinger(df)
    fi   = calc_force_index(df)
    emv  = calc_ease_of_movement(df)
    ui   = calc_ulcer_index(df['Close'])

    fig = plt.figure(figsize=(16, 14))
    gs  = gridspec.GridSpec(4, 1, height_ratios=[4, 2, 2, 2], hspace=0.08)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax4 = fig.add_subplot(gs[3], sharex=ax1)

    # ── Panel 1: Price + MAs + Alligator ──
    ax1.plot(df.index, df['Close'], color='#444441', linewidth=1.3,
             label='Close', zorder=5)
    ax1.plot(df.index, hma,  color='#1D9E75', linewidth=2,
             label='HMA 20',  zorder=4)
    ax1.plot(df.index, dema, color='#378ADD', linewidth=1.2,
             linestyle='--', label='DEMA 20', alpha=0.8)
    ax1.plot(df.index, tema, color='#7F77DD', linewidth=1.2,
             linestyle=':', label='TEMA 20', alpha=0.8)
    ax1.plot(df.index, vwma, color='#EF9F27', linewidth=1.2,
             linestyle='-.', label='VWMA 20', alpha=0.8)

    # Alligator lines
    ax1.plot(df.index, jaw,   color='#378ADD', linewidth=1.5,
             linestyle='-', label='Jaw (13,8)',   alpha=0.6)
    ax1.plot(df.index, teeth, color='#E24B4A', linewidth=1.5,
             linestyle='-', label='Teeth (8,5)',  alpha=0.6)
    ax1.plot(df.index, lips,  color='#1D9E75', linewidth=1.5,
             linestyle='-', label='Lips (5,3)',   alpha=0.6)

    ax1.set_title(f'{ticker} — Advanced Indicators', fontsize=13)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.legend(fontsize=7, loc='upper left', ncol=4)
    ax1.grid(True, alpha=0.2)

    # ── Panel 2: TRIX + PPO ──
    ax2.plot(df.index, trix_line, color='#534AB7', linewidth=1.8,
             label='TRIX (15)')
    ax2.plot(df.index, trix_sig,  color='#EF9F27', linewidth=1.2,
             linestyle='--', label='TRIX signal', alpha=0.8)
    ax2.axhline(y=0, color='#888780', linewidth=0.8)
    ax2.fill_between(df.index, trix_line, 0,
                     where=(trix_line >= 0), alpha=0.1, color='#1D9E75')
    ax2.fill_between(df.index, trix_line, 0,
                     where=(trix_line < 0),  alpha=0.1, color='#E24B4A')
    ax2.set_ylabel('TRIX', fontsize=10)
    ax2.legend(fontsize=8, loc='upper left')

    ax2_r = ax2.twinx()
    ax2_r.plot(df.index, ppo_line, color='#D4537E', linewidth=1.2,
               linestyle='-.', label='PPO %', alpha=0.8)
    ax2_r.set_ylabel('PPO %', fontsize=9)
    ax2_r.legend(fontsize=8, loc='upper right')
    ax2.grid(True, alpha=0.2)

    # ── Panel 3: Klinger + Force Index ──
    kvo_colors = ['#1D9E75' if v >= 0 else '#E24B4A' for v in kvo]
    ax3.bar(df.index, kvo, color=kvo_colors, alpha=0.5, width=1, label='Klinger KVO')
    ax3.plot(df.index, kvo_sig, color='#EF9F27', linewidth=1.5,
             label='KVO signal')
    ax3.axhline(y=0, color='#888780', linewidth=0.8)
    ax3.set_ylabel('Klinger', fontsize=10)
    ax3.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M' if abs(x) >= 1e6
                          else f'{x/1e3:.0f}K'))
    ax3.legend(fontsize=8, loc='upper left')

    ax3_r = ax3.twinx()
    ax3_r.plot(df.index, fi, color='#534AB7', linewidth=1.5,
               label='Force Index (13)', alpha=0.8)
    ax3_r.axhline(y=0, color='#534AB7', linewidth=0.5, linestyle=':', alpha=0.4)
    ax3_r.set_ylabel('Force Index', fontsize=9)
    ax3_r.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M' if abs(x) >= 1e6
                          else f'{x/1e3:.0f}K'))
    ax3_r.legend(fontsize=8, loc='upper right')
    ax3.grid(True, alpha=0.2)

    # ── Panel 4: Ulcer Index + EMV ──
    ax4.plot(df.index, ui, color='#E24B4A', linewidth=2,
             label='Ulcer Index %')
    ax4.fill_between(df.index, ui, 0, alpha=0.15, color='#E24B4A')
    ax4.axhline(y=10, color='#EF9F27', linewidth=1, linestyle='--',
                alpha=0.7, label='UI=10 (high)')
    ax4.axhline(y=5, color='#1D9E75', linewidth=1, linestyle='--',
                alpha=0.7, label='UI=5 (moderate)')
    ax4.set_ylabel('Ulcer Index %', fontsize=10)
    ax4.legend(fontsize=8, loc='upper left')

    ax4_r = ax4.twinx()
    ax4_r.bar(df.index, emv,
              color=['#1D9E75' if v >= 0 else '#E24B4A' for v in emv],
              alpha=0.4, width=1, label='Ease of Move')
    ax4_r.axhline(y=0, color='#888780', linewidth=0.5)
    ax4_r.set_ylabel('EMV', fontsize=9)
    ax4_r.legend(fontsize=8, loc='upper right')
    ax4.grid(True, alpha=0.2)

    plt.tight_layout()
    fname = f"{ticker.replace('.','_')}_advanced_indicators.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"\nChart saved: {fname}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 9 — BREADTH ANALYSIS (multi-stock)
# ════════════════════════════════════════════════════════════

# A representative set of Nifty 50 stocks for breadth analysis
NIFTY_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFOSYS.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "NESTLEIND.NS",
    "BAJFINANCE.NS", "POWERGRID.NS", "NTPC.NS", "TECHM.NS", "TATAMOTORS.NS",
    "ONGC.NS", "TATASTEEL.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS", "COALINDIA.NS",
    "INDUSINDBK.NS", "DRREDDY.NS", "CIPLA.NS", "EICHERMOT.NS", "BRITANNIA.NS",
    "APOLLOHOSP.NS", "BPCL.NS", "GRASIM.NS", "TATACONSUM.NS", "DIVISLAB.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "M&M.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "ADANIPORTS.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS", "ADANIENT.NS", "UPL.NS",
]


def run_breadth_analysis(tickers=None, period="1y"):
    """
    Runs the full breadth analysis on a list of stocks.
    Prints summary and plots A-D Line + McClellan + New Highs/Lows.
    """
    if tickers is None:
        tickers = NIFTY_50_TICKERS

    print(f"\nRunning breadth analysis on {len(tickers)} stocks...")

    # Calculate all breadth indicators
    ad_data  = calc_advance_decline(tickers, period)
    mcclell  = calc_mcclellan_oscillator(ad_data)
    nh_nl    = calc_new_highs_lows(tickers, period)

    # Print current readings
    print(f"\n{'='*60}")
    print(f"  MARKET BREADTH ANALYSIS — Nifty {len(tickers)}")
    print(f"  As of: {ad_data.index[-1].date()}")
    print(f"{'='*60}")

    last_ad = ad_data.iloc[-1]
    adv  = int(last_ad['Advancing'])
    decl = int(last_ad['Declining'])
    total_stocks = adv + decl + int(last_ad['Unchanged'])
    ad_pct = round(adv / total_stocks * 100, 1) if total_stocks > 0 else 0

    print(f"\n  Today's breadth:")
    print(f"  Advancing : {adv} ({ad_pct}%)")
    print(f"  Declining : {decl} ({round(decl/total_stocks*100,1) if total_stocks>0 else 0}%)")
    print(f"  A-D Line  : {int(ad_data['AD_Line'].iloc[-1]):,}")

    mcclell_val = round(mcclell.iloc[-1], 2)
    mc_zone = ("Overbought (>100)" if mcclell_val > 100
               else "Oversold (<-100)" if mcclell_val < -100
               else "Neutral")
    print(f"\n  McClellan Oscillator: {mcclell_val}  → {mc_zone}")

    if len(nh_nl.dropna()) > 0:
        nh_row  = nh_nl.dropna().iloc[-1]
        nh_val  = int(nh_row['New_Highs'])
        nl_val  = int(nh_row['New_Lows'])
        ratio   = round(nh_row['NH_NL_Ratio'], 1)
        print(f"\n  New 52-week Highs : {nh_val}")
        print(f"  New 52-week Lows  : {nl_val}")
        print(f"  NH/NL Ratio       : {ratio}%  "
              f"({'Bullish breadth' if ratio > 60 else 'Bearish breadth' if ratio < 40 else 'Mixed'})")

    # Trend of A-D Line (last 5 days)
    ad_5d_change = int(ad_data['AD_Line'].iloc[-1] - ad_data['AD_Line'].iloc[-5])
    ad_trend = "rising (breadth improving)" if ad_5d_change > 0 else "falling (breadth deteriorating)"
    print(f"\n  A-D Line (5d change): {ad_5d_change:+,}  → {ad_trend}")

    print(f"\n{'='*60}\n")

    # Plot breadth charts
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    # A-D Line
    axes[0].plot(ad_data.index, ad_data['AD_Line'],
                 color='#378ADD', linewidth=2, label='A-D Line')
    axes[0].fill_between(ad_data.index, ad_data['AD_Line'], 0,
                         where=(ad_data['AD_Line'] >= 0), alpha=0.1, color='#1D9E75')
    axes[0].fill_between(ad_data.index, ad_data['AD_Line'], 0,
                         where=(ad_data['AD_Line'] < 0), alpha=0.1, color='#E24B4A')
    axes[0].axhline(y=0, color='#888780', linewidth=0.8)
    axes[0].set_title(f'Market Breadth — Nifty {len(tickers)}', fontsize=13)
    axes[0].set_ylabel('A-D Line', fontsize=10)
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.2)

    # McClellan Oscillator
    mc_colors = ['#1D9E75' if v >= 0 else '#E24B4A' for v in mcclell]
    axes[1].bar(ad_data.index, mcclell, color=mc_colors, alpha=0.7, width=1)
    axes[1].axhline(y=100,  color='#E24B4A', linewidth=1,
                    linestyle='--', alpha=0.7, label='Overbought (+100)')
    axes[1].axhline(y=-100, color='#1D9E75', linewidth=1,
                    linestyle='--', alpha=0.7, label='Oversold (−100)')
    axes[1].axhline(y=0, color='#888780', linewidth=0.8)
    axes[1].set_ylabel('McClellan', fontsize=10)
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.2)

    # New Highs/Lows
    nh_nl_clean = nh_nl.dropna()
    if len(nh_nl_clean) > 0:
        axes[2].bar(nh_nl_clean.index, nh_nl_clean['New_Highs'],
                    color='#1D9E75', alpha=0.7, width=1, label='New 52w Highs')
        axes[2].bar(nh_nl_clean.index, -nh_nl_clean['New_Lows'],
                    color='#E24B4A', alpha=0.7, width=1, label='New 52w Lows (inverted)')
        axes[2].axhline(y=0, color='#888780', linewidth=0.8)
        axes[2].set_ylabel('New Highs/Lows', fontsize=10)
        axes[2].legend(fontsize=9)
        axes[2].grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig('market_breadth.png', dpi=150, bbox_inches='tight')
    print("Breadth chart saved: market_breadth.png")
    plt.show()

    return ad_data, mcclell, nh_nl


# ════════════════════════════════════════════════════════════
# SECTION 10 — MAIN
# ════════════════════════════════════════════════════════════

def main():
    """
    Usage:
        python advanced_indicators.py                  → RELIANCE.NS, 1y
        python advanced_indicators.py TATAMOTORS        → any stock
        python advanced_indicators.py INFY 2y           → with period
        python advanced_indicators.py --breadth         → market breadth only
    """
    args = sys.argv[1:]

    # Check for breadth-only mode
    if '--breadth' in args:
        run_breadth_analysis()
        return

    ticker_input = args[0] if args else "RELIANCE"
    period       = args[1] if len(args) > 1 else "1y"

    if not ticker_input.endswith('.NS'):
        ticker = ticker_input.upper() + '.NS'
    else:
        ticker = ticker_input.upper()

    # Single stock analysis
    df = get_data(ticker, period)
    print_advanced_summary(df, ticker)
    plot_advanced_chart(df, ticker)

    # Also run breadth analysis on Nifty 50
    print("\nRunning market breadth analysis (Nifty 50)...")
    run_breadth_analysis(period="6mo")


if __name__ == "__main__":
    main()