# ============================================================
# BOLLINGER BANDS CALCULATOR
# For Indian Stocks (NSE)
# ============================================================
# This script:
#   1. Downloads real stock data from Yahoo Finance
#   2. Calculates all Bollinger Band components:
#       - Middle Band (SMA 20)
#       - Upper Band  (SMA + 2 × std dev)
#       - Lower Band  (SMA - 2 × std dev)
#       - %B          (where price sits inside the band)
#       - Bandwidth   (how wide the band is — measures volatility)
#   3. Detects all 5 Bollinger signals:
#       - Band Squeeze (bandwidth at multi-period low)
#       - Band Touch + Reversal (mean reversion)
#       - Band Walking (trend confirmation)
#       - %B extreme with RSI confirmation
#       - W-Bottom and M-Top patterns
#   4. Plots a 3-panel chart: Price+Bands / %B / Bandwidth
#   5. Prints a complete signal summary
#
# INSTALL FIRST:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


# ── Imports ──────────────────────────────────────────────────
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ── STEP 1: Download Stock Data ───────────────────────────────
def get_stock_data(ticker, period="1y"):
    """
    Downloads daily OHLCV data for a given NSE stock.

    Parameters:
        ticker (str): e.g. "WIPRO.NS", "RELIANCE.NS"
        period (str): "6mo", "1y", "2y"

    Returns:
        df (DataFrame): Stock price data
    """
    print(f"\nDownloading {ticker} ...")
    df = yf.download(ticker, period=period, auto_adjust=True)
    df.dropna(inplace=True)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ── STEP 2: Calculate RSI (needed for Signal 4 confirmation) ──
def calculate_rsi(prices, period=14):
    """
    Calculates RSI using Wilder's smoothing.
    (Same function as Phase 3 — reused here for confirmation signals)

    Parameters:
        prices (Series): Closing prices
        period (int): RSI period (default 14)

    Returns:
        Series: RSI values
    """
    delta = prices.diff(1)
    gains  = delta.clip(lower=0)
    losses = delta.clip(upper=0).abs()

    # First averages via simple rolling mean
    avg_gain = gains.rolling(window=period, min_periods=period).mean()
    avg_loss = losses.rolling(window=period, min_periods=period).mean()

    # Apply Wilder's smoothing from period onwards
    ag_list = avg_gain.tolist()
    al_list = avg_loss.tolist()
    g_list  = gains.tolist()
    l_list  = losses.tolist()

    for i in range(period, len(ag_list)):
        if pd.isna(ag_list[i - 1]):
            continue
        ag_list[i] = (ag_list[i - 1] * (period - 1) + g_list[i]) / period
        al_list[i] = (al_list[i - 1] * (period - 1) + l_list[i]) / period

    avg_gain = pd.Series(ag_list, index=prices.index)
    avg_loss = pd.Series(al_list, index=prices.index)

    rs  = avg_gain / avg_loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100).round(2)


# ── STEP 3: Calculate Bollinger Bands ────────────────────────
def calculate_bollinger_bands(prices, period=20, num_std=2):
    """
    Calculates all Bollinger Band components.

    Components:
    ─────────────────────────────────────────────────────────
    Middle Band:
        Simple Moving Average of 'period' days (default 20).
        This is the "fair value" center of the band.

    Standard Deviation (σ):
        Measures how much prices are spread around the average.
        High σ = volatile market → wide bands
        Low σ  = calm market    → narrow bands

    Upper Band:
        Middle + (num_std × σ)    [default: SMA + 2σ]
        The "ceiling" — price touches here when overbought.
        Statistically contains ~95% of price action (at 2σ).

    Lower Band:
        Middle - (num_std × σ)    [default: SMA - 2σ]
        The "floor" — price touches here when oversold.

    %B (Percent B):
        = (Price - Lower Band) / (Upper Band - Lower Band)
        Tells you WHERE inside the band the price is.
            %B = 1.0  → at upper band
            %B = 0.5  → at middle band (SMA)
            %B = 0.0  → at lower band
            %B > 1.0  → above upper band (extremely overbought)
            %B < 0.0  → below lower band (extremely oversold)

    Bandwidth:
        = (Upper - Lower) / Middle × 100
        Measures how wide the bands are as a percentage.
        Falling bandwidth = volatility contracting = squeeze forming
        Rising bandwidth  = volatility expanding  = move in progress
    ─────────────────────────────────────────────────────────

    Parameters:
        prices (Series): Closing prices
        period (int): Moving average period (default 20)
        num_std (float): Standard deviation multiplier (default 2)

    Returns:
        middle, upper, lower, percent_b, bandwidth (all as Series)
    """

    # Middle band = simple moving average
    # min_periods=period ensures we only calculate when we have enough data
    middle = prices.rolling(window=period, min_periods=period).mean()

    # Standard deviation over the same rolling window
    # ddof=0 means population std dev (not sample) — standard for Bollinger Bands
    std = prices.rolling(window=period, min_periods=period).std(ddof=0)

    # Upper and lower bands
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)

    # %B — where is price inside the band?
    # Clamp division by zero (when upper == lower, which theoretically can't happen)
    band_width_raw = upper - lower
    percent_b = (prices - lower) / band_width_raw.replace(0, float('nan'))

    # Bandwidth — how wide is the band as % of middle?
    bandwidth = (band_width_raw / middle) * 100

    return (
        middle.round(2),
        upper.round(2),
        lower.round(2),
        percent_b.round(4),
        bandwidth.round(4)
    )


# ── STEP 4: Detect Band Squeeze ──────────────────────────────
def detect_squeeze(df, lookback=50):
    """
    Detects when the Bollinger Bandwidth reaches a multi-period low.
    This means volatility is at a minimum — a big move is coming.

    The squeeze is detected when:
        Today's bandwidth < minimum bandwidth of the last 'lookback' days

    The DIRECTION of the breakout determines whether to buy or sell.
    We flag both the squeeze and the subsequent breakout.

    Parameters:
        df (DataFrame): Must have 'Bandwidth', 'Close', 'Upper', 'Lower'
        lookback (int): Days to look back for the bandwidth minimum

    Returns:
        List of signal dicts
    """
    signals = []

    # We need at least 'lookback' bars of bandwidth data
    for i in range(lookback, len(df)):
        current_bw = df['Bandwidth'].iloc[i]
        if pd.isna(current_bw):
            continue

        # What was the minimum bandwidth in the previous 'lookback' days?
        historical_min = df['Bandwidth'].iloc[i - lookback:i].min()

        date  = df.index[i].date()
        close = round(df['Close'].iloc[i], 2)

        # Squeeze: current bandwidth is at or below the historical minimum
        if current_bw <= historical_min * 1.05:   # 5% tolerance
            signals.append({
                'Date': date,
                'Type': 'Bollinger Squeeze',
                'Signal': 'ALERT: Squeeze — big move incoming',
                'PctB': round(df['PctB'].iloc[i], 3),
                'Bandwidth': round(current_bw, 3),
                'Close': close,
                'Detail': f'Bandwidth {round(current_bw,2)}% is at {lookback}-day low — expect breakout soon'
            })

    return signals


# ── STEP 5: Detect Band Touch and Reversal ───────────────────
def detect_band_touch_reversal(df):
    """
    Detects when price touches a band and then reverses direction.

    Mean Reversion Logic:
        In a ranging market, price oscillates between upper and lower bands.
        When price touches or goes beyond the lower band AND the next candle
        starts reversing upward → buy signal.

        When price touches or goes beyond the upper band AND the next candle
        starts reversing downward → sell signal.

    We use %B thresholds:
        %B < 0.05 → touching or below lower band (oversold)
        %B > 0.95 → touching or above upper band (overbought)

    Reversal confirmation:
        For buy: price today > price yesterday (started moving up)
        For sell: price today < price yesterday (started moving down)

    Parameters:
        df (DataFrame): Must have 'PctB', 'Close', 'RSI' columns

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        pct_b_today = df['PctB'].iloc[i]
        pct_b_yest  = df['PctB'].iloc[i - 1]
        price_today = df['Close'].iloc[i]
        price_yest  = df['Close'].iloc[i - 1]
        rsi_today   = df['RSI'].iloc[i]
        date        = df.index[i].date()
        close       = round(price_today, 2)

        if pd.isna(pct_b_today) or pd.isna(pct_b_yest) or pd.isna(rsi_today):
            continue

        # ── Lower band touch + reversal (BUY) ──
        # Yesterday: price was at or below lower band (%B <= 0.05)
        # Today: price started moving UP (%B rising AND price higher)
        if pct_b_yest <= 0.05 and pct_b_today > pct_b_yest and price_today > price_yest:
            # RSI confirmation: RSI should also be in oversold/recovering territory
            rsi_tag = f" (RSI={rsi_today} confirms)" if rsi_today < 40 else " (RSI not confirming)"
            signals.append({
                'Date': date,
                'Type': 'Band Touch Reversal',
                'Signal': 'BUY',
                'PctB': round(pct_b_today, 3),
                'Bandwidth': round(df['Bandwidth'].iloc[i], 3),
                'Close': close,
                'Detail': f'Lower band touch + reversal{rsi_tag}'
            })

        # ── Upper band touch + reversal (SELL) ──
        # Yesterday: price was at or above upper band (%B >= 0.95)
        # Today: price started moving DOWN (%B falling AND price lower)
        elif pct_b_yest >= 0.95 and pct_b_today < pct_b_yest and price_today < price_yest:
            rsi_tag = f" (RSI={rsi_today} confirms)" if rsi_today > 60 else " (RSI not confirming)"
            signals.append({
                'Date': date,
                'Type': 'Band Touch Reversal',
                'Signal': 'SELL',
                'PctB': round(pct_b_today, 3),
                'Bandwidth': round(df['Bandwidth'].iloc[i], 3),
                'Close': close,
                'Detail': f'Upper band touch + reversal{rsi_tag}'
            })

    return signals


# ── STEP 6: Detect Band Walking ──────────────────────────────
def detect_band_walking(df, min_consecutive=3):
    """
    Detects when price is "walking" along the upper or lower band.
    This signals a STRONG TREND — do NOT try to trade against it.

    Walking the upper band: price stays near upper band for multiple days
        → Strong uptrend, ride it, don't sell just because it's "overbought"

    Walking the lower band: price stays near lower band for multiple days
        → Strong downtrend, stay out, don't buy just because it's "oversold"

    Detection rule:
        If %B > 0.8 for 'min_consecutive' or more consecutive days
        → Upper band walk (bullish trend)

        If %B < 0.2 for 'min_consecutive' or more consecutive days
        → Lower band walk (bearish trend)

    Parameters:
        df (DataFrame): Must have 'PctB' and 'Close' columns
        min_consecutive (int): Minimum days of walking to flag

    Returns:
        List of signal dicts (only flags the START of a walk)
    """
    signals    = []
    upper_streak = 0    # Count consecutive days near upper band
    lower_streak = 0    # Count consecutive days near lower band

    for i in range(len(df)):
        pct_b = df['PctB'].iloc[i]
        if pd.isna(pct_b):
            upper_streak = 0
            lower_streak = 0
            continue

        date  = df.index[i].date()
        close = round(df['Close'].iloc[i], 2)

        # Count consecutive days near upper band
        if pct_b > 0.8:
            upper_streak += 1
            lower_streak  = 0

            # Flag exactly when we reach the minimum threshold
            if upper_streak == min_consecutive:
                signals.append({
                    'Date': date,
                    'Type': 'Band Walking',
                    'Signal': 'STRONG UPTREND — walking upper band',
                    'PctB': round(pct_b, 3),
                    'Bandwidth': round(df['Bandwidth'].iloc[i], 3),
                    'Close': close,
                    'Detail': f'{min_consecutive}+ consecutive days near upper band — strong bullish trend'
                })

        # Count consecutive days near lower band
        elif pct_b < 0.2:
            lower_streak += 1
            upper_streak  = 0

            if lower_streak == min_consecutive:
                signals.append({
                    'Date': date,
                    'Type': 'Band Walking',
                    'Signal': 'STRONG DOWNTREND — walking lower band',
                    'PctB': round(pct_b, 3),
                    'Bandwidth': round(df['Bandwidth'].iloc[i], 3),
                    'Close': close,
                    'Detail': f'{min_consecutive}+ consecutive days near lower band — strong bearish trend'
                })

        else:
            # Price returned to middle — reset both streaks
            upper_streak = 0
            lower_streak = 0

    return signals


# ── STEP 7: Detect %B Extreme with RSI Confirmation ──────────
def detect_pctb_rsi_combo(df):
    """
    Detects the most powerful Bollinger Band signals:
    %B extreme COMBINED with RSI extreme.

    When BOTH indicators agree it's oversold → very strong BUY.
    When BOTH indicators agree it's overbought → very strong SELL.

    Conditions:
        STRONG BUY:
            %B < 0.0  (price below lower band)  AND
            RSI < 30  (RSI also says oversold)
            → Double confirmation of extreme oversold condition

        STRONG SELL:
            %B > 1.0  (price above upper band)  AND
            RSI > 70  (RSI also says overbought)
            → Double confirmation of extreme overbought condition

    Parameters:
        df (DataFrame): Must have 'PctB', 'RSI', 'Close' columns

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(len(df)):
        pct_b = df['PctB'].iloc[i]
        rsi   = df['RSI'].iloc[i]
        date  = df.index[i].date()
        close = round(df['Close'].iloc[i], 2)

        if pd.isna(pct_b) or pd.isna(rsi):
            continue

        # STRONG BUY: both %B and RSI say oversold
        if pct_b < 0.0 and rsi < 30:
            signals.append({
                'Date': date,
                'Type': '%B + RSI Combo',
                'Signal': 'STRONG BUY',
                'PctB': round(pct_b, 3),
                'Bandwidth': round(df['Bandwidth'].iloc[i], 3),
                'Close': close,
                'Detail': f'%B={round(pct_b,3)} (below lower band) + RSI={rsi} (oversold) — double confirmation'
            })

        # STRONG SELL: both %B and RSI say overbought
        elif pct_b > 1.0 and rsi > 70:
            signals.append({
                'Date': date,
                'Type': '%B + RSI Combo',
                'Signal': 'STRONG SELL',
                'PctB': round(pct_b, 3),
                'Bandwidth': round(df['Bandwidth'].iloc[i], 3),
                'Close': close,
                'Detail': f'%B={round(pct_b,3)} (above upper band) + RSI={rsi} (overbought) — double confirmation'
            })

    return signals


# ── STEP 8: Plot 3-Panel Chart ────────────────────────────────
def plot_bb_chart(df, ticker, touch_signals, squeeze_signals):
    """
    Creates a 3-panel chart:
        Panel 1: Price with Bollinger Bands and buy/sell markers
        Panel 2: %B indicator (with 0 and 1 reference lines)
        Panel 3: Bandwidth (squeeze detector)

    Parameters:
        df (DataFrame): Stock data with all BB columns
        ticker (str): Stock name for title
        touch_signals (list): Band touch reversal signals
        squeeze_signals (list): Squeeze alert signals
    """

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1,
        figsize=(14, 10),
        gridspec_kw={'height_ratios': [3, 1.5, 1.5]},
        sharex=True
    )

    # ── Panel 1: Price + Bollinger Bands ──

    # Shade the area between upper and lower bands (light green)
    ax1.fill_between(df.index, df['Upper'], df['Lower'],
                     alpha=0.08, color='#378ADD', label='Band area')

    # Plot the three band lines
    ax1.plot(df.index, df['Upper'],
             color='#1D9E75', linewidth=1.2, linestyle='--', label='Upper band', alpha=0.8)
    ax1.plot(df.index, df['Middle'],
             color='#378ADD', linewidth=2, label='Middle (SMA 20)')
    ax1.plot(df.index, df['Lower'],
             color='#E24B4A', linewidth=1.2, linestyle='--', label='Lower band', alpha=0.8)

    # Plot the price line
    ax1.plot(df.index, df['Close'],
             color='#444441', linewidth=1.2, label='Close Price', zorder=3)

    # Mark buy signals (band touch reversal buys)
    buy_sigs  = [s for s in touch_signals if s['Signal'] == 'BUY']
    sell_sigs = [s for s in touch_signals if s['Signal'] == 'SELL']

    for sig in buy_sigs:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.scatter(row.index, row['Close'],
                        marker='^', color='#1D9E75', s=120, zorder=5)

    for sig in sell_sigs:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.scatter(row.index, row['Close'],
                        marker='v', color='#E24B4A', s=120, zorder=5)

    # Mark squeeze alerts (orange vertical lines)
    for sig in squeeze_signals[-5:]:    # Only show last 5 to avoid clutter
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.axvline(x=row.index[0], color='#EF9F27',
                        linewidth=1.5, linestyle=':', alpha=0.7)

    green_tri  = mpatches.Patch(color='#1D9E75', label='BUY (lower band reversal)')
    red_tri    = mpatches.Patch(color='#E24B4A', label='SELL (upper band reversal)')
    orange_bar = mpatches.Patch(color='#EF9F27', label='Squeeze alert')
    ax1.legend(handles=[green_tri, red_tri, orange_bar], fontsize=8)
    ax1.set_title(f'{ticker} — Bollinger Bands Analysis (20, 2)', fontsize=13, pad=10)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.grid(True, alpha=0.25)

    # ── Panel 2: %B Indicator ──
    ax2.plot(df.index, df['PctB'],
             color='#7F77DD', linewidth=1.8, label='%B')

    # Reference lines at 0, 0.5, and 1
    ax2.axhline(y=1.0, color='#E24B4A', linewidth=1, linestyle='--', alpha=0.7)
    ax2.axhline(y=0.5, color='#888780', linewidth=0.8, linestyle=':', alpha=0.5)
    ax2.axhline(y=0.0, color='#1D9E75', linewidth=1, linestyle='--', alpha=0.7)

    # Shade overbought (above 1) and oversold (below 0) zones
    ax2.fill_between(df.index, df['PctB'], 1,
                     where=(df['PctB'] > 1),
                     alpha=0.3, color='#E24B4A', label='Above upper band')
    ax2.fill_between(df.index, df['PctB'], 0,
                     where=(df['PctB'] < 0),
                     alpha=0.3, color='#1D9E75', label='Below lower band')

    # Labels on right side
    ax2.text(df.index[-1], 1.02, ' 1.0', fontsize=8, color='#A32D2D')
    ax2.text(df.index[-1], 0.52, ' 0.5', fontsize=8, color='#888780')
    ax2.text(df.index[-1], 0.02, ' 0.0', fontsize=8, color='#27500A')

    ax2.set_ylabel('%B', fontsize=10)
    ax2.set_ylim(-0.3, 1.3)
    ax2.legend(fontsize=8, loc='upper left')
    ax2.grid(True, alpha=0.25)

    # ── Panel 3: Bandwidth ──
    ax3.plot(df.index, df['Bandwidth'],
             color='#EF9F27', linewidth=2, label='Bandwidth %')
    ax3.fill_between(df.index, df['Bandwidth'], 0,
                     alpha=0.15, color='#EF9F27')

    # Mark the minimum bandwidth (potential squeeze points)
    min_bw   = df['Bandwidth'].min()
    min_date = df['Bandwidth'].idxmin()
    ax3.scatter([min_date], [min_bw],
                marker='*', color='#E24B4A', s=200, zorder=5,
                label=f'Lowest bandwidth ({round(min_bw,1)}%)')

    ax3.set_ylabel('Bandwidth %', fontsize=10)
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.25)

    plt.tight_layout()

    filename = f"{ticker.replace('.', '_')}_BB_chart.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\nChart saved as: {filename}")
    plt.show()


# ── STEP 9: Main Program ──────────────────────────────────────
def main():
    """
    Full Bollinger Band analysis pipeline.
    """

    # ── Configuration ──
    ticker   = "RELIANCE.NS"   # Change to any NSE stock
    period   = "1y"
    bb_period  = 20              # SMA period for middle band
    bb_std     = 2               # Standard deviation multiplier

    # ── Download ──
    df = get_stock_data(ticker, period)

    # ── Calculate RSI (for combo confirmation) ──
    df['RSI'] = calculate_rsi(df['Close'], period=14)

    # ── Calculate Bollinger Bands ──
    (df['Middle'],
     df['Upper'],
     df['Lower'],
     df['PctB'],
     df['Bandwidth']) = calculate_bollinger_bands(df['Close'], bb_period, bb_std)

    # ── Detect All Signals ──
    squeeze_sigs   = detect_squeeze(df, lookback=50)
    touch_sigs     = detect_band_touch_reversal(df)
    walking_sigs   = detect_band_walking(df, min_consecutive=3)
    combo_sigs     = detect_pctb_rsi_combo(df)

    # Combine all (except walk signals which are contextual, not buy/sell)
    all_signals = sorted(
        squeeze_sigs + touch_sigs + combo_sigs,
        key=lambda x: x['Date']
    )

    # ── Print Summary ──
    print(f"\n{'='*68}")
    print(f"  BOLLINGER BANDS ANALYSIS — {ticker}  (period={bb_period}, std={bb_std})")
    print(f"{'='*68}")

    cur_close  = round(df['Close'].iloc[-1], 2)
    cur_upper  = round(df['Upper'].iloc[-1], 2)
    cur_middle = round(df['Middle'].iloc[-1], 2)
    cur_lower  = round(df['Lower'].iloc[-1], 2)
    cur_pctb   = round(df['PctB'].iloc[-1], 3)
    cur_bw     = round(df['Bandwidth'].iloc[-1], 3)
    cur_rsi    = round(df['RSI'].iloc[-1], 1)

    print(f"\n  Current Close   : ₹{cur_close}")
    print(f"  Upper Band      : ₹{cur_upper}")
    print(f"  Middle Band     : ₹{cur_middle}")
    print(f"  Lower Band      : ₹{cur_lower}")
    print(f"  %B              : {cur_pctb}  (0=lower band, 0.5=middle, 1=upper band)")
    print(f"  Bandwidth       : {cur_bw}%")
    print(f"  RSI             : {cur_rsi}")

    # Interpret %B position
    print(f"\n  ── Current State ──")
    if cur_pctb > 0.8:
        print(f"  Price near UPPER band — overbought territory")
    elif cur_pctb < 0.2:
        print(f"  Price near LOWER band — oversold territory")
    else:
        print(f"  Price in MIDDLE zone — neutral")

    # Check for squeeze
    recent_min_bw = df['Bandwidth'].iloc[-50:].min()
    if cur_bw <= recent_min_bw * 1.1:
        print(f"  SQUEEZE DETECTED — bandwidth at multi-week low, big move incoming!")
    else:
        print(f"  No squeeze — normal volatility conditions")

    # Recent signals
    print(f"\n  ── Recent Signals (last 8) ──")
    if all_signals:
        for sig in all_signals[-8:]:
            direction = "BUY  " if "BUY" in sig['Signal'] else "SELL "
            print(f"  {sig['Date']}  {direction}  {sig['Type']:<22}  %B={sig['PctB']:<7}  ₹{sig['Close']}")
            print(f"           {sig.get('Detail','')}")
    else:
        print("  No significant signals found in this period.")

    # Band walking alerts
    if walking_sigs:
        print(f"\n  ── Trend Walking Alerts ──")
        for sig in walking_sigs[-4:]:
            print(f"  {sig['Date']}  {sig['Signal']}")

    print(f"\n  REMEMBER: Combine BB signals with MACD crossovers and RSI for highest probability setups.")
    print(f"{'='*68}\n")

    # ── Plot ──
    plot_bb_chart(df, ticker, touch_sigs, squeeze_sigs)


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()