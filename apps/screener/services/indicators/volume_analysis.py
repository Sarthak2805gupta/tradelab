# ============================================================
# VOLUME ANALYSIS — ALL 5 INDICATORS
# For Indian Stocks (NSE)
# ============================================================
# This script calculates:
#   1. Volume Moving Average (VMA) — is today's volume significant?
#   2. OBV (On Balance Volume)     — cumulative buying vs selling pressure
#   3. VWAP (Volume Weighted Avg Price) — institutional fair value
#   4. MFI (Money Flow Index)      — volume-weighted RSI
#   5. Volume-Price Confirmation   — is the price move trusted?
#
# Signals detected:
#   - High volume breakouts (price + volume both surge)
#   - OBV divergence (price up but OBV flat/down = warning)
#   - VWAP crossovers (intraday trend changes)
#   - MFI overbought/oversold (with volume backing)
#   - Volume climax (exhaustion top or bottom)
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np


# ── STEP 1: Download Stock Data ───────────────────────────────
def get_stock_data(ticker, period="6mo"):
    """
    Downloads daily OHLCV data.
    Volume analysis needs at least 3-6 months of data for meaningful signals.

    Parameters:
        ticker (str): e.g. "SBIN.NS", "ICICIBANK.NS"
        period (str): "3mo", "6mo", "1y"

    Returns:
        df (DataFrame): OHLCV data — Open, High, Low, Close, Volume
    """
    print(f"\nDownloading {ticker} ...")
    df = yf.download(ticker, period=period, auto_adjust=True)
    df.dropna(inplace=True)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ── STEP 2: Volume Moving Average ────────────────────────────
def calculate_volume_ma(volume, period=20):
    """
    Calculates the simple moving average of volume.

    Used to judge whether TODAY's volume is high or low
    compared to recent history. A volume spike only matters
    when it's significantly above average.

    Interpretation:
        Volume Ratio = Today's Volume / VMA

        > 2.0x  → very high volume — major event, strong signal
        > 1.5x  → high volume — significant move, trust the signal
        1.0x    → average volume — normal day
        < 0.7x  → low volume — don't trust price movement today

    Parameters:
        volume (Series): Daily volume data
        period (int): Period for the moving average (default 20)

    Returns:
        Series: Volume Moving Average
    """
    return volume.rolling(window=period, min_periods=period).mean()


# ── STEP 3: On Balance Volume (OBV) ──────────────────────────
def calculate_obv(df):
    """
    Calculates OBV — the running total of buying vs selling volume.

    Logic for each day:
        If Close > Previous Close:
            OBV = Previous OBV + Today's Volume   (buyers won, add volume)
        If Close < Previous Close:
            OBV = Previous OBV - Today's Volume   (sellers won, subtract)
        If Close = Previous Close:
            OBV = Previous OBV                    (no change)

    Why OBV works:
        It tracks the CUMULATIVE PRESSURE of buyers vs sellers.
        Smart money (institutions) accumulate shares quietly —
        the price might not move much, but OBV rises steadily.
        When retail investors notice and push price up, OBV is
        already high — confirming the move.

        When OBV diverges from price (price up, OBV flat or down),
        it means big money is SELLING into the retail buying —
        this is called DISTRIBUTION and signals a coming reversal.

    Parameters:
        df (DataFrame): Must have 'Close' and 'Volume' columns

    Returns:
        Series: OBV values
    """
    # Start with an empty list to build OBV
    obv_values = [0]   # First value is 0 (arbitrary starting point)

    # Loop through each day starting from day 2 (index 1)
    for i in range(1, len(df)):
        close_today = df['Close'].iloc[i]
        close_prev  = df['Close'].iloc[i - 1]
        vol_today   = df['Volume'].iloc[i]
        prev_obv    = obv_values[-1]   # Last OBV value

        if close_today > close_prev:
            # Bullish day — add volume to OBV
            obv_values.append(prev_obv + vol_today)
        elif close_today < close_prev:
            # Bearish day — subtract volume from OBV
            obv_values.append(prev_obv - vol_today)
        else:
            # Flat day — OBV unchanged
            obv_values.append(prev_obv)

    return pd.Series(obv_values, index=df.index)


# ── STEP 4: VWAP ─────────────────────────────────────────────
def calculate_vwap(df):
    """
    Calculates VWAP — Volume Weighted Average Price.

    True VWAP resets every day and uses tick-by-tick data.
    Since we only have daily data (not intraday), we calculate
    a rolling VWAP using the typical price and volume.

    Formula:
        Typical Price (TP) = (High + Low + Close) / 3
        VWAP = Cumulative(TP × Volume) / Cumulative(Volume)

    Why "typical price" and not just close?
        Using (H+L+C)/3 gives a better representation of the
        day's true average trading price, since trading happens
        at all price levels throughout the day — not just the close.

    Daily data VWAP interpretation:
        Price consistently above VWAP → stock trading above "fair value" → bullish
        Price consistently below VWAP → stock trading below "fair value" → bearish
        Price crossing VWAP → potential trend change

    Note: For actual intraday VWAP, you need 5-min or 1-min data.
          This daily version gives a medium-term fair value reference.

    Parameters:
        df (DataFrame): Must have 'High', 'Low', 'Close', 'Volume'

    Returns:
        Series: VWAP values
    """
    # Typical price = average of High, Low, Close for the day
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3

    # Money Flow = Typical Price × Volume (represents the "weight" of each day)
    money_flow = typical_price * df['Volume']

    # Cumulative sums for the rolling VWAP calculation
    # We use a 20-day rolling window (equivalent to 1 month of trading)
    period = 20
    cumulative_mf  = money_flow.rolling(window=period, min_periods=1).sum()
    cumulative_vol = df['Volume'].rolling(window=period, min_periods=1).sum()

    # VWAP = Cumulative Money Flow / Cumulative Volume
    vwap = cumulative_mf / cumulative_vol

    return vwap.round(2)


# ── STEP 5: Money Flow Index (MFI) ───────────────────────────
def calculate_mfi(df, period=14):
    """
    Calculates MFI — a volume-weighted version of RSI.

    Think of MFI as RSI that also accounts for how much
    money was flowing in or out on each day.

    Step-by-step:

    Step 1 — Typical Price:
        TP = (High + Low + Close) / 3
        This is the "center of gravity" of the day's price range.

    Step 2 — Raw Money Flow:
        Raw MF = TP × Volume
        This represents the total money that moved on this day.

    Step 3 — Classify as Positive or Negative:
        If today's TP > yesterday's TP → Positive Money Flow
        If today's TP < yesterday's TP → Negative Money Flow

    Step 4 — Sum over N days:
        Positive Money Flow = sum of all positive Raw MF values in N days
        Negative Money Flow = sum of all negative Raw MF values in N days

    Step 5 — Money Flow Ratio and MFI:
        MFR = Positive MF / Negative MF
        MFI = 100 - (100 / (1 + MFR))

    Interpretation:
        MFI > 80 → Overbought (stronger than RSI > 70 — volume confirmed)
        MFI < 20 → Oversold  (stronger than RSI < 30)
        MFI diverging from price → reversal signal

    Parameters:
        df (DataFrame): Must have 'High', 'Low', 'Close', 'Volume'
        period (int): Lookback period (default 14, same as RSI)

    Returns:
        Series: MFI values (0 to 100)
    """

    # Step 1: Typical price
    tp = (df['High'] + df['Low'] + df['Close']) / 3

    # Step 2: Raw money flow for each day
    raw_mf = tp * df['Volume']

    # Step 3: Separate into positive and negative
    # Compare today's TP with yesterday's TP using .shift(1)
    positive_mf = raw_mf.where(tp > tp.shift(1), 0)   # Keep value if TP rose, else 0
    negative_mf = raw_mf.where(tp < tp.shift(1), 0)   # Keep value if TP fell, else 0

    # Step 4: Sum over rolling period
    pos_sum = positive_mf.rolling(window=period, min_periods=period).sum()
    neg_sum = negative_mf.rolling(window=period, min_periods=period).sum()

    # Step 5: Calculate MFI
    # Handle division by zero (when neg_sum = 0 on very bullish runs)
    mfr = pos_sum / neg_sum.replace(0, float('nan'))
    mfi = 100 - (100 / (1 + mfr))

    # When neg_sum is 0, MFI = 100 (all buying, no selling)
    mfi = mfi.fillna(100)

    return mfi.round(2)


# ── STEP 6: Detect Volume-Price Signals ──────────────────────
def detect_volume_signals(df):
    """
    Detects all meaningful volume-based signals:

    1. HIGH VOLUME BREAKOUT:
       Price moves significantly (>1.5%) on volume >1.5x average.
       This is the strongest signal — real move, not a fake-out.

    2. LOW VOLUME WARNING:
       Price moves but volume is below 0.7x average.
       The move lacks conviction — likely to reverse.

    3. OBV DIVERGENCE (Bearish):
       Price is making higher highs, but OBV is flat or falling.
       Smart money is distributing (selling) → reversal coming.

    4. OBV DIVERGENCE (Bullish):
       Price is making lower lows, but OBV is flat or rising.
       Smart money is accumulating (buying) → reversal coming.

    5. VOLUME CLIMAX:
       Extreme volume spike (>3x average) after a sustained move.
       Often signals exhaustion — the move may be ending.
       Also known as "selling climax" (at bottoms) or "buying climax" (at tops).

    6. MFI EXTREME:
       MFI > 80 = overbought with volume confirmation → consider selling
       MFI < 20 = oversold with volume confirmation → consider buying

    Parameters:
        df (DataFrame): Must have Close, Volume, OBV, VMA, MFI columns

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(20, len(df)):   # Start at 20 to ensure VMA is ready
        date      = df.index[i].date()
        close     = round(df['Close'].iloc[i], 2)
        close_prev = df['Close'].iloc[i - 1]
        vol       = df['Volume'].iloc[i]
        vma       = df['VMA'].iloc[i]
        obv_now   = df['OBV'].iloc[i]
        mfi       = df['MFI'].iloc[i]

        if pd.isna(vma) or pd.isna(mfi):
            continue

        # Volume ratio: how many times is today's volume vs average?
        vol_ratio = vol / vma if vma > 0 else 1.0

        # Price change percentage
        pct_change = (close - close_prev) / close_prev * 100

        # ── Signal 1: High Volume Breakout ──
        # Large price move AND high volume = strong confirmation
        if abs(pct_change) > 1.5 and vol_ratio > 1.5:
            direction = "BUY" if pct_change > 0 else "SELL"
            signals.append({
                'Date': date, 'Type': 'High Volume Breakout',
                'Signal': direction,
                'Volume_Ratio': round(vol_ratio, 2),
                'Price_Change': round(pct_change, 2),
                'MFI': mfi, 'Close': close,
                'Detail': f'Price {round(pct_change,1)}% on {round(vol_ratio,1)}x average volume'
            })

        # ── Signal 2: Low Volume Warning ──
        # Price moved but on thin volume = unreliable
        elif abs(pct_change) > 1.0 and vol_ratio < 0.7:
            signals.append({
                'Date': date, 'Type': 'Low Volume Warning',
                'Signal': 'WARN',
                'Volume_Ratio': round(vol_ratio, 2),
                'Price_Change': round(pct_change, 2),
                'MFI': mfi, 'Close': close,
                'Detail': f'Price moved {round(pct_change,1)}% but only {round(vol_ratio,1)}x volume — low conviction'
            })

        # ── Signal 3: Volume Climax ──
        # Extreme volume (>3x average) = possible exhaustion
        if vol_ratio > 3.0:
            # Look back to see if we've had a sustained move (5 days)
            price_5d_ago = df['Close'].iloc[i - 5]
            trend_5d = (close - price_5d_ago) / price_5d_ago * 100

            if abs(trend_5d) > 5:   # At least 5% move in last 5 days
                climax_type = "SELLING CLIMAX (potential bottom)" if trend_5d < 0 else "BUYING CLIMAX (potential top)"
                signals.append({
                    'Date': date, 'Type': 'Volume Climax',
                    'Signal': 'ALERT',
                    'Volume_Ratio': round(vol_ratio, 2),
                    'Price_Change': round(pct_change, 2),
                    'MFI': mfi, 'Close': close,
                    'Detail': f'{climax_type} — {round(vol_ratio,1)}x average volume after {round(trend_5d,1)}% 5-day move'
                })

        # ── Signal 4: MFI Extreme ──
        # Volume-weighted RSI at extremes = high probability reversal
        if i > 0:
            mfi_prev = df['MFI'].iloc[i - 1]
            if not pd.isna(mfi_prev):
                # MFI exits overbought (crosses below 80)
                if mfi_prev > 80 and mfi <= 80:
                    signals.append({
                        'Date': date, 'Type': 'MFI Signal',
                        'Signal': 'SELL',
                        'Volume_Ratio': round(vol_ratio, 2),
                        'Price_Change': round(pct_change, 2),
                        'MFI': mfi, 'Close': close,
                        'Detail': f'MFI exited overbought zone ({round(mfi_prev,1)} → {mfi}) — volume-confirmed sell'
                    })
                # MFI exits oversold (crosses above 20)
                elif mfi_prev < 20 and mfi >= 20:
                    signals.append({
                        'Date': date, 'Type': 'MFI Signal',
                        'Signal': 'BUY',
                        'Volume_Ratio': round(vol_ratio, 2),
                        'Price_Change': round(pct_change, 2),
                        'MFI': mfi, 'Close': close,
                        'Detail': f'MFI exited oversold zone ({round(mfi_prev,1)} → {mfi}) — volume-confirmed buy'
                    })

    return signals


# ── STEP 7: Detect OBV Divergence ────────────────────────────
def detect_obv_divergence(df, lookback=10):
    """
    Detects divergence between price and OBV.

    Bearish OBV divergence:
        Price makes a higher high, but OBV makes a lower high or stays flat.
        → Smart money is selling into the price rally.
        → Reversal down is likely.

    Bullish OBV divergence:
        Price makes a lower low, but OBV makes a higher low or stays flat.
        → Smart money is buying despite the price drop.
        → Reversal up is likely.

    Parameters:
        df (DataFrame): Must have 'Close' and 'OBV' columns
        lookback (int): Days to compare for divergence

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(lookback * 2, len(df)):
        # Compare current vs lookback periods
        price_now  = df['Close'].iloc[i]
        price_prev = df['Close'].iloc[i - lookback]
        obv_now    = df['OBV'].iloc[i]
        obv_prev   = df['OBV'].iloc[i - lookback]
        date       = df.index[i].date()
        close      = round(price_now, 2)

        if pd.isna(obv_now) or pd.isna(obv_prev):
            continue

        # Price change and OBV change over lookback period
        price_change_pct = (price_now - price_prev) / price_prev * 100
        obv_change_pct   = (obv_now - obv_prev) / abs(obv_prev) * 100 if obv_prev != 0 else 0

        # ── Bearish divergence ──
        # Price significantly higher but OBV significantly lower
        if price_change_pct > 5 and obv_change_pct < -5:
            signals.append({
                'Date': date, 'Type': 'OBV Divergence',
                'Signal': 'SELL (Bearish OBV Divergence)',
                'Volume_Ratio': round(df['Volume'].iloc[i] / df['VMA'].iloc[i], 2),
                'Price_Change': round(price_change_pct, 2),
                'MFI': round(df['MFI'].iloc[i], 1),
                'Close': close,
                'Detail': f'Price +{round(price_change_pct,1)}% but OBV {round(obv_change_pct,1)}% — distribution!'
            })

        # ── Bullish divergence ──
        # Price significantly lower but OBV significantly higher
        elif price_change_pct < -5 and obv_change_pct > 5:
            signals.append({
                'Date': date, 'Type': 'OBV Divergence',
                'Signal': 'BUY (Bullish OBV Divergence)',
                'Volume_Ratio': round(df['Volume'].iloc[i] / df['VMA'].iloc[i], 2),
                'Price_Change': round(price_change_pct, 2),
                'MFI': round(df['MFI'].iloc[i], 1),
                'Close': close,
                'Detail': f'Price {round(price_change_pct,1)}% but OBV +{round(obv_change_pct,1)}% — accumulation!'
            })

    return signals


# ── STEP 8: Plot 4-Panel Chart ────────────────────────────────
def plot_volume_chart(df, ticker, signals):
    """
    Creates a 4-panel chart:
        Panel 1: Price with VWAP
        Panel 2: Volume bars with VMA line
        Panel 3: OBV line
        Panel 4: MFI oscillator

    Parameters:
        df (DataFrame): Full stock data with all indicators
        ticker (str): Stock symbol for title
        signals (list): All detected signals
    """

    fig = plt.figure(figsize=(14, 12))

    # Create 4 rows with different heights using GridSpec
    gs = gridspec.GridSpec(4, 1, height_ratios=[3, 1.5, 1.5, 1.5], hspace=0.08)
    ax1 = fig.add_subplot(gs[0])   # Price + VWAP
    ax2 = fig.add_subplot(gs[1], sharex=ax1)   # Volume
    ax3 = fig.add_subplot(gs[2], sharex=ax1)   # OBV
    ax4 = fig.add_subplot(gs[3], sharex=ax1)   # MFI

    # ── Panel 1: Price + VWAP ──
    ax1.plot(df.index, df['Close'],
             color='#444441', linewidth=1.2, label='Close Price')
    ax1.plot(df.index, df['VWAP'],
             color='#7F77DD', linewidth=1.8, linestyle='--', label='VWAP (rolling 20d)')

    # Shade above/below VWAP
    ax1.fill_between(df.index, df['Close'], df['VWAP'],
                     where=(df['Close'] >= df['VWAP']),
                     alpha=0.08, color='#1D9E75')
    ax1.fill_between(df.index, df['Close'], df['VWAP'],
                     where=(df['Close'] < df['VWAP']),
                     alpha=0.08, color='#E24B4A')

    # Mark high volume breakout signals
    buy_sigs  = [s for s in signals if s['Signal'] == 'BUY' and s['Type'] == 'High Volume Breakout']
    sell_sigs = [s for s in signals if s['Signal'] == 'SELL' and s['Type'] == 'High Volume Breakout']

    for sig in buy_sigs:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.scatter(row.index, row['Close'], marker='^', color='#1D9E75', s=100, zorder=5)

    for sig in sell_sigs:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.scatter(row.index, row['Close'], marker='v', color='#E24B4A', s=100, zorder=5)

    ax1.set_title(f'{ticker} — Volume Analysis', fontsize=13, pad=10)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.legend(fontsize=8, loc='upper left')
    ax1.grid(True, alpha=0.25)

    # ── Panel 2: Volume Bars + VMA ──
    # Color each bar by direction (green if up day, red if down)
    colors = ['#1D9E75' if df['Close'].iloc[i] >= df['Open'].iloc[i]
              else '#E24B4A' for i in range(len(df))]

    ax2.bar(df.index, df['Volume'], color=colors, alpha=0.7, width=1, label='Volume')
    ax2.plot(df.index, df['VMA'],
             color='#EF9F27', linewidth=1.8, label='Volume MA (20)', zorder=3)

    # Mark volume climax bars
    climax_sigs = [s for s in signals if s['Type'] == 'Volume Climax']
    for sig in climax_sigs:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax2.scatter(row.index, row['Volume'], marker='*',
                        color='#534AB7', s=200, zorder=5)

    ax2.set_ylabel('Volume', fontsize=10)
    ax2.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: f'{x/1e6:.1f}M' if x >= 1e6 else f'{x/1e3:.0f}K')
    )
    ax2.legend(fontsize=8, loc='upper left')
    ax2.grid(True, alpha=0.25)

    # ── Panel 3: OBV ──
    ax3.plot(df.index, df['OBV'],
             color='#378ADD', linewidth=1.8, label='OBV')

    # Add OBV trend line (20-day EMA of OBV)
    obv_ema = df['OBV'].ewm(span=20, adjust=False).mean()
    ax3.plot(df.index, obv_ema,
             color='#EF9F27', linewidth=1.2, linestyle='--', label='OBV EMA(20)')

    ax3.set_ylabel('OBV', fontsize=10)
    ax3.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M' if abs(x) >= 1e6 else f'{x/1e3:.0f}K')
    )
    ax3.legend(fontsize=8, loc='upper left')
    ax3.grid(True, alpha=0.25)

    # ── Panel 4: MFI ──
    # Color the MFI line based on zone
    ax4.fill_between(df.index, df['MFI'], 80,
                     where=(df['MFI'] > 80), alpha=0.25, color='#E24B4A')
    ax4.fill_between(df.index, df['MFI'], 20,
                     where=(df['MFI'] < 20), alpha=0.25, color='#1D9E75')

    ax4.plot(df.index, df['MFI'],
             color='#D4537E', linewidth=1.8, label='MFI (14)')

    ax4.axhline(y=80, color='#E24B4A', linewidth=1, linestyle='--', alpha=0.7)
    ax4.axhline(y=50, color='#888780', linewidth=0.8, linestyle=':', alpha=0.5)
    ax4.axhline(y=20, color='#1D9E75', linewidth=1, linestyle='--', alpha=0.7)

    ax4.text(df.index[-1], 81, ' 80', fontsize=8, color='#A32D2D')
    ax4.text(df.index[-1], 21, ' 20', fontsize=8, color='#27500A')

    ax4.set_ylabel('MFI', fontsize=10)
    ax4.set_ylim(0, 100)
    ax4.legend(fontsize=8, loc='upper left')
    ax4.grid(True, alpha=0.25)

    plt.tight_layout()

    filename = f"{ticker.replace('.', '_')}_Volume_chart.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\nChart saved as: {filename}")
    plt.show()


# ── STEP 9: Main Program ──────────────────────────────────────
def main():
    """
    Full volume analysis pipeline.
    """

    # ── Configuration ──
    ticker = "SBIN.NS"    # Change to any NSE stock
    period = "6mo"        # 6 months — good balance of data and relevance

    # ── Download ──
    df = get_stock_data(ticker, period)

    # ── Calculate All Volume Indicators ──

    # Volume Moving Average (20-day)
    df['VMA'] = calculate_volume_ma(df['Volume'], period=20)

    # Volume Ratio (today vs average)
    df['Vol_Ratio'] = df['Volume'] / df['VMA']

    # OBV — cumulative buying vs selling
    df['OBV'] = calculate_obv(df)

    # VWAP — rolling 20-day volume-weighted average price
    df['VWAP'] = calculate_vwap(df)

    # MFI — volume-weighted RSI
    df['MFI'] = calculate_mfi(df, period=14)

    # ── Detect Signals ──
    volume_signals = detect_volume_signals(df)
    obv_signals    = detect_obv_divergence(df, lookback=10)

    all_signals = sorted(
        volume_signals + obv_signals,
        key=lambda x: x['Date']
    )

    # ── Print Summary ──
    print(f"\n{'='*70}")
    print(f"  VOLUME ANALYSIS — {ticker}")
    print(f"{'='*70}")

    # Current readings
    cur_close     = round(df['Close'].iloc[-1], 2)
    cur_vwap      = round(df['VWAP'].iloc[-1], 2)
    cur_vol       = int(df['Volume'].iloc[-1])
    cur_vma       = int(df['VMA'].iloc[-1])
    cur_vol_ratio = round(df['Vol_Ratio'].iloc[-1], 2)
    cur_mfi       = round(df['MFI'].iloc[-1], 1)
    cur_obv       = int(df['OBV'].iloc[-1])

    print(f"\n  Current Close    : ₹{cur_close}")
    print(f"  VWAP (20d)       : ₹{cur_vwap}")
    print(f"  Today's Volume   : {cur_vol:,}")
    print(f"  20d Avg Volume   : {cur_vma:,}")
    print(f"  Volume Ratio     : {cur_vol_ratio}x average")
    print(f"  MFI (14)         : {cur_mfi}")
    print(f"  OBV              : {cur_obv:,}")

    # Volume assessment
    print(f"\n  ── Volume Assessment ──")

    if cur_vol_ratio > 2.0:
        print(f"  Volume is VERY HIGH ({cur_vol_ratio}x) — major activity today, trust the price move")
    elif cur_vol_ratio > 1.5:
        print(f"  Volume is HIGH ({cur_vol_ratio}x) — significant activity, signal is reliable")
    elif cur_vol_ratio < 0.7:
        print(f"  Volume is LOW ({cur_vol_ratio}x) — low conviction, be cautious about today's move")
    else:
        print(f"  Volume is normal ({cur_vol_ratio}x) — average activity")

    if cur_close > cur_vwap:
        print(f"  Price ABOVE VWAP → trading above fair value → bullish bias")
    else:
        print(f"  Price BELOW VWAP → trading below fair value → bearish bias")

    if cur_mfi > 80:
        print(f"  MFI OVERBOUGHT ({cur_mfi}) — volume-confirmed excess buying, consider selling")
    elif cur_mfi < 20:
        print(f"  MFI OVERSOLD ({cur_mfi}) — volume-confirmed excess selling, consider buying")
    else:
        print(f"  MFI neutral ({cur_mfi}) — no extreme volume pressure")

    # Recent signals (last 10)
    print(f"\n  ── Recent Volume Signals (last 10) ──")
    if all_signals:
        for sig in all_signals[-10:]:
            tag = "BUY  " if "BUY" in sig['Signal'] else ("SELL " if "SELL" in sig['Signal'] else "ALERT")
            print(f"  {sig['Date']}  {tag}  {sig['Type']:<28}  Vol={sig['Volume_Ratio']}x  MFI={sig['MFI']}  ₹{sig['Close']}")
            print(f"           {sig['Detail']}")
    else:
        print("  No significant volume signals found in this period.")

    # Signal counts
    buy_count  = sum(1 for s in all_signals if 'BUY'  in s['Signal'])
    sell_count = sum(1 for s in all_signals if 'SELL' in s['Signal'])
    warn_count = sum(1 for s in all_signals if 'WARN' in s['Signal'] or 'ALERT' in s['Signal'])

    print(f"\n  BUY signals   : {buy_count}")
    print(f"  SELL signals  : {sell_count}")
    print(f"  Warnings      : {warn_count}")
    print(f"\n  KEY RULE: Only act on price signals that are supported by high volume (>1.5x average).")
    print(f"{'='*70}\n")

    # ── Plot ──
    plot_volume_chart(df, ticker, all_signals)


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()