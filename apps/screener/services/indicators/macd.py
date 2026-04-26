# ============================================================
# MACD (MOVING AVERAGE CONVERGENCE DIVERGENCE)
# For Indian Stocks (NSE)
# ============================================================
# This script:
#   1. Downloads real stock data from Yahoo Finance
#   2. Calculates all three MACD components from scratch:
#       - MACD Line  (EMA12 - EMA26)
#       - Signal Line (EMA9 of MACD Line)
#       - Histogram  (MACD - Signal)
#   3. Detects all 4 MACD signals:
#       - Signal Line crossovers (primary buy/sell trigger)
#       - Zero line crossovers (trend confirmation)
#       - Histogram momentum shifts (earliest warning)
#       - MACD divergence (reversal warning)
#   4. Plots a 3-panel chart: Price / MACD / Histogram
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
        ticker (str): e.g. "RELIANCE.NS", "TCS.NS"
        period (str): "6mo", "1y", "2y"

    Returns:
        df (DataFrame): Stock price data with OHLCV columns
    """
    print(f"\nDownloading {ticker} ...")
    df = yf.download(ticker, period=period, auto_adjust=True)
    df.dropna(inplace=True)

    # Flatten multi-level columns (yfinance sometimes creates them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ── STEP 2: Calculate EMA (helper function) ───────────────────
def calculate_ema(series, period):
    """
    Calculates Exponential Moving Average.

    Formula:
        k = 2 / (period + 1)          ← smoothing multiplier
        EMA today = Price × k + EMA_yesterday × (1 - k)

    Parameters:
        series (Series): Any numeric pandas Series
        period (int): Number of periods

    Returns:
        Series: EMA values
    """
    # pandas .ewm() handles the exponential weighting
    # adjust=False uses the recursive formula above (standard method)
    # span=period sets k = 2/(period+1)
    return series.ewm(span=period, adjust=False).mean()


# ── STEP 3: Calculate MACD Components ────────────────────────
def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    Calculates all three MACD components.

    Component 1 — MACD Line:
        = EMA(fast) - EMA(slow)
        = EMA(12)   - EMA(26)    [default]

        When positive: fast EMA is above slow EMA = uptrend
        When negative: fast EMA is below slow EMA = downtrend

    Component 2 — Signal Line:
        = EMA(9) of the MACD Line
        Smooths the MACD line to reduce noise.
        Used to generate crossover buy/sell signals.

    Component 3 — Histogram:
        = MACD Line - Signal Line
        Shows the DISTANCE between MACD and Signal.
        Positive = MACD above Signal = bullish momentum
        Negative = MACD below Signal = bearish momentum
        Growing bars = momentum increasing
        Shrinking bars = momentum weakening (early warning)

    Parameters:
        prices (Series): Closing prices
        fast (int): Fast EMA period (default 12)
        slow (int): Slow EMA period (default 26)
        signal (int): Signal line EMA period (default 9)

    Returns:
        macd_line, signal_line, histogram (all as pandas Series)
    """

    # Calculate both EMAs
    ema_fast = calculate_ema(prices, fast)    # EMA 12 — reacts quickly to price changes
    ema_slow = calculate_ema(prices, slow)    # EMA 26 — smoother, reacts slowly

    # MACD line = difference between the two EMAs
    macd_line = ema_fast - ema_slow

    # Signal line = EMA of the MACD line itself
    signal_line = calculate_ema(macd_line, signal)

    # Histogram = gap between MACD and Signal
    histogram = macd_line - signal_line

    return macd_line.round(4), signal_line.round(4), histogram.round(4)


# ── STEP 4: Detect Signal Line Crossovers ────────────────────
def detect_crossovers(df):
    """
    Detects when MACD Line crosses the Signal Line.

    Bullish crossover: MACD was below Signal yesterday,
                       MACD is above Signal today → BUY signal

    Bearish crossover: MACD was above Signal yesterday,
                       MACD is below Signal today → SELL signal

    EXTRA POWER RULE:
        Crossover below zero line → stronger bullish signal
        Crossover above zero line → stronger bearish signal

    Parameters:
        df (DataFrame): Must have 'MACD', 'Signal', 'Close' columns

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        macd_today     = df['MACD'].iloc[i]
        macd_yesterday = df['MACD'].iloc[i - 1]
        sig_today      = df['Signal'].iloc[i]
        sig_yesterday  = df['Signal'].iloc[i - 1]
        date           = df.index[i].date()
        close          = round(df['Close'].iloc[i], 2)

        # ── Bullish crossover: MACD crosses above Signal ──
        if macd_yesterday < sig_yesterday and macd_today > sig_today:
            # Extra power: if this crossover happens below zero line
            zone = "below zero (strong)" if macd_today < 0 else "above zero (moderate)"
            signals.append({
                'Date': date,
                'Type': 'Signal Line Crossover',
                'Signal': 'BUY',
                'MACD': round(macd_today, 3),
                'Histogram': round(df['Histogram'].iloc[i], 3),
                'Close': close,
                'Detail': f'Bullish crossover {zone}'
            })

        # ── Bearish crossover: MACD crosses below Signal ──
        elif macd_yesterday > sig_yesterday and macd_today < sig_today:
            zone = "above zero (strong)" if macd_today > 0 else "below zero (moderate)"
            signals.append({
                'Date': date,
                'Type': 'Signal Line Crossover',
                'Signal': 'SELL',
                'MACD': round(macd_today, 3),
                'Histogram': round(df['Histogram'].iloc[i], 3),
                'Close': close,
                'Detail': f'Bearish crossover {zone}'
            })

    return signals


# ── STEP 5: Detect Zero Line Crossovers ──────────────────────
def detect_zero_crossovers(df):
    """
    Detects when the MACD Line crosses the zero level.

    MACD crosses above zero:
        EMA 12 just moved above EMA 26.
        The trend has officially turned bullish.
        Signal: BULLISH CONFIRMATION

    MACD crosses below zero:
        EMA 12 just moved below EMA 26.
        The trend has officially turned bearish.
        Signal: BEARISH CONFIRMATION

    This is a slower, more reliable signal than the crossover.
    Use it to CONFIRM the overall trend direction.

    Parameters:
        df (DataFrame): Must have 'MACD' and 'Close' columns

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        macd_today     = df['MACD'].iloc[i]
        macd_yesterday = df['MACD'].iloc[i - 1]
        date           = df.index[i].date()
        close          = round(df['Close'].iloc[i], 2)

        # MACD crosses above zero → trend turns bullish
        if macd_yesterday < 0 and macd_today >= 0:
            signals.append({
                'Date': date,
                'Type': 'Zero Line Cross',
                'Signal': 'BULLISH TREND',
                'MACD': round(macd_today, 3),
                'Histogram': round(df['Histogram'].iloc[i], 3),
                'Close': close,
                'Detail': 'MACD crossed above zero — trend confirmed bullish'
            })

        # MACD crosses below zero → trend turns bearish
        elif macd_yesterday > 0 and macd_today <= 0:
            signals.append({
                'Date': date,
                'Type': 'Zero Line Cross',
                'Signal': 'BEARISH TREND',
                'MACD': round(macd_today, 3),
                'Histogram': round(df['Histogram'].iloc[i], 3),
                'Close': close,
                'Detail': 'MACD crossed below zero — trend confirmed bearish'
            })

    return signals


# ── STEP 6: Detect Histogram Momentum Shifts ─────────────────
def detect_histogram_momentum(df):
    """
    Detects when histogram bars start shrinking (momentum fading).

    This is the EARLIEST warning signal — it happens BEFORE the
    MACD/Signal crossover. Use it to prepare for a position change.

    Logic:
        If histogram was positive and growing, then starts shrinking:
            → Bullish momentum is fading → consider tightening stop loss

        If histogram was negative and growing (more negative), then starts shrinking:
            → Bearish momentum is fading → consider preparing to buy

    We use a 3-bar rule:
        If the histogram reverses direction for 2 consecutive bars,
        we flag it as a momentum shift.

    Parameters:
        df (DataFrame): Must have 'Histogram' column

    Returns:
        List of signal dicts
    """
    signals = []

    # We need at least 3 bars to detect a reversal in direction
    for i in range(2, len(df)):
        h_now  = df['Histogram'].iloc[i]        # Today
        h_prev = df['Histogram'].iloc[i - 1]    # Yesterday
        h_prev2 = df['Histogram'].iloc[i - 2]   # Day before yesterday
        date   = df.index[i].date()
        close  = round(df['Close'].iloc[i], 2)

        # ── Bullish momentum fade ──
        # Histogram was growing positive (h_prev2 < h_prev > h_now),
        # but now h_now < h_prev → bars shrinking while still positive
        if h_prev2 > 0 and h_prev > 0 and h_now > 0:
            if h_prev > h_prev2 and h_now < h_prev:  # Was growing, now shrinking
                signals.append({
                    'Date': date,
                    'Type': 'Histogram Momentum',
                    'Signal': 'WARN: Bullish momentum fading',
                    'MACD': round(df['MACD'].iloc[i], 3),
                    'Histogram': round(h_now, 3),
                    'Close': close,
                    'Detail': f'Histogram peaked at {round(h_prev,3)}, now {round(h_now,3)}'
                })

        # ── Bearish momentum fade ──
        # Histogram was growing negative (more negative each day),
        # but now h_now > h_prev → bars shrinking (becoming less negative)
        elif h_prev2 < 0 and h_prev < 0 and h_now < 0:
            if h_prev < h_prev2 and h_now > h_prev:  # Was growing negative, now shrinking
                signals.append({
                    'Date': date,
                    'Type': 'Histogram Momentum',
                    'Signal': 'ALERT: Bearish momentum fading (prepare to buy)',
                    'MACD': round(df['MACD'].iloc[i], 3),
                    'Histogram': round(h_now, 3),
                    'Close': close,
                    'Detail': f'Histogram troughed at {round(h_prev,3)}, now {round(h_now,3)}'
                })

    return signals


# ── STEP 7: Detect MACD Divergence ───────────────────────────
def detect_macd_divergence(df, lookback=6):
    """
    Detects bullish and bearish divergence between price and MACD Line.

    Bullish divergence:
        Price makes a LOWER LOW, but MACD makes a HIGHER LOW
        → Sellers are weakening → reversal up is likely
        → BUY signal (strongest when MACD is below zero)

    Bearish divergence:
        Price makes a HIGHER HIGH, but MACD makes a LOWER HIGH
        → Buyers are weakening → reversal down is likely
        → SELL signal (strongest when MACD is above zero)

    Parameters:
        df (DataFrame): Must have 'Close' and 'MACD' columns
        lookback (int): Points on each side to define a local peak/trough

    Returns:
        List of divergence signal dicts
    """
    signals  = []
    prices   = df['Close'].values
    macd_arr = df['MACD'].values
    dates    = df.index

    # ── Bullish divergence (using local price lows) ──
    for i in range(lookback, len(prices) - lookback):
        if pd.isna(macd_arr[i]):
            continue

        # Is prices[i] a local minimum?
        is_low = (all(prices[i] <= prices[i-j] for j in range(1, lookback+1)) and
                  all(prices[i] <= prices[i+j] for j in range(1, lookback+1)))

        if is_low:
            # Find the previous local low to compare with
            for k in range(max(0, i - lookback * 3), i - lookback):
                if k < lookback:
                    continue
                if pd.isna(macd_arr[k]):
                    continue

                prev_is_low = (all(prices[k] <= prices[k-j] for j in range(1, min(lookback+1, k+1))) and
                               k + lookback < len(prices) and
                               all(prices[k] <= prices[k+j] for j in range(1, lookback+1)))

                if prev_is_low:
                    # Bullish divergence: price lower, but MACD higher
                    if prices[i] < prices[k] and macd_arr[i] > macd_arr[k]:
                        signals.append({
                            'Date': dates[i].date(),
                            'Type': 'MACD Divergence',
                            'Signal': 'BUY (Bullish Divergence)',
                            'MACD': round(macd_arr[i], 3),
                            'Histogram': round(df['Histogram'].iloc[i], 3),
                            'Close': round(prices[i], 2),
                            'Detail': (f'Price: ₹{round(prices[k],1)} → ₹{round(prices[i],1)} '
                                       f'(lower low), MACD: {round(macd_arr[k],2)} → {round(macd_arr[i],2)} (higher low)')
                        })
                    break   # Only compare with most recent previous low

    # ── Bearish divergence (using local price highs) ──
    for i in range(lookback, len(prices) - lookback):
        if pd.isna(macd_arr[i]):
            continue

        # Is prices[i] a local maximum?
        is_high = (all(prices[i] >= prices[i-j] for j in range(1, lookback+1)) and
                   all(prices[i] >= prices[i+j] for j in range(1, lookback+1)))

        if is_high:
            for k in range(max(0, i - lookback * 3), i - lookback):
                if k < lookback:
                    continue
                if pd.isna(macd_arr[k]):
                    continue

                prev_is_high = (all(prices[k] >= prices[k-j] for j in range(1, min(lookback+1, k+1))) and
                                k + lookback < len(prices) and
                                all(prices[k] >= prices[k+j] for j in range(1, lookback+1)))

                if prev_is_high:
                    # Bearish divergence: price higher, but MACD lower
                    if prices[i] > prices[k] and macd_arr[i] < macd_arr[k]:
                        signals.append({
                            'Date': dates[i].date(),
                            'Type': 'MACD Divergence',
                            'Signal': 'SELL (Bearish Divergence)',
                            'MACD': round(macd_arr[i], 3),
                            'Histogram': round(df['Histogram'].iloc[i], 3),
                            'Close': round(prices[i], 2),
                            'Detail': (f'Price: ₹{round(prices[k],1)} → ₹{round(prices[i],1)} '
                                       f'(higher high), MACD: {round(macd_arr[k],2)} → {round(macd_arr[i],2)} (lower high)')
                        })
                    break

    return signals


# ── STEP 8: Plot 3-Panel Chart ────────────────────────────────
def plot_macd_chart(df, ticker, crossover_signals, zero_signals):
    """
    Creates a 3-panel chart:
        Panel 1: Price with buy/sell markers
        Panel 2: MACD Line and Signal Line
        Panel 3: Histogram (coloured green/red)

    Parameters:
        df (DataFrame): Stock data with MACD, Signal, Histogram columns
        ticker (str): Stock name for the chart title
        crossover_signals: Buy/sell crossover signal list
        zero_signals: Zero line crossover signal list
    """

    # 3 panels with different heights
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1,
        figsize=(14, 10),
        gridspec_kw={'height_ratios': [3, 2, 1.5]},  # Price is tallest
        sharex=True
    )

    # ── Panel 1: Price ──
    ax1.plot(df.index, df['Close'],
             color='#444441', linewidth=1.2, label='Close Price')

    # Mark buy signals (green up triangles)
    for sig in crossover_signals:
        if sig['Signal'] == 'BUY':
            row = df[df.index.date == sig['Date']]
            if not row.empty:
                ax1.scatter(row.index, row['Close'],
                            marker='^', color='#1D9E75', s=130, zorder=5)

    # Mark sell signals (red down triangles)
    for sig in crossover_signals:
        if sig['Signal'] == 'SELL':
            row = df[df.index.date == sig['Date']]
            if not row.empty:
                ax1.scatter(row.index, row['Close'],
                            marker='v', color='#E24B4A', s=130, zorder=5)

    green_patch = mpatches.Patch(color='#1D9E75', label='BUY (bullish crossover)')
    red_patch   = mpatches.Patch(color='#E24B4A', label='SELL (bearish crossover)')
    ax1.legend(handles=[green_patch, red_patch], fontsize=8)
    ax1.set_title(f'{ticker} — MACD Analysis (12, 26, 9)', fontsize=13, pad=10)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.grid(True, alpha=0.25)

    # ── Panel 2: MACD and Signal Lines ──
    ax2.plot(df.index, df['MACD'],
             color='#378ADD', linewidth=2, label='MACD line')
    ax2.plot(df.index, df['Signal'],
             color='#EF9F27', linewidth=1.5, linestyle='--', label='Signal line')
    ax2.axhline(y=0, color='#888780', linewidth=0.8, linestyle='-', alpha=0.5)

    # Shade area between MACD and Signal
    # Green when MACD > Signal (bullish), red when MACD < Signal (bearish)
    ax2.fill_between(df.index, df['MACD'], df['Signal'],
                     where=(df['MACD'] >= df['Signal']),
                     alpha=0.15, color='#1D9E75', label='Bullish zone')
    ax2.fill_between(df.index, df['MACD'], df['Signal'],
                     where=(df['MACD'] < df['Signal']),
                     alpha=0.15, color='#E24B4A', label='Bearish zone')

    ax2.set_ylabel('MACD', fontsize=10)
    ax2.legend(fontsize=8, loc='upper left')
    ax2.grid(True, alpha=0.25)

    # ── Panel 3: Histogram ──
    # Color each bar green (positive) or red (negative)
    colors = ['#1D9E75' if v >= 0 else '#E24B4A' for v in df['Histogram']]
    ax3.bar(df.index, df['Histogram'],
            color=colors, alpha=0.8, width=1)
    ax3.axhline(y=0, color='#888780', linewidth=0.8)
    ax3.set_ylabel('Histogram', fontsize=10)
    ax3.grid(True, alpha=0.25)

    plt.tight_layout()

    filename = f"{ticker.replace('.', '_')}_MACD_chart.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\nChart saved as: {filename}")
    plt.show()


# ── STEP 9: Main Program ──────────────────────────────────────
def main():
    """
    Full MACD analysis pipeline:
        1. Download data
        2. Calculate all MACD components
        3. Detect all 4 signal types
        4. Print signal summary with interpretation
        5. Plot 3-panel chart
    """

    # ── Configuration ──
    ticker = "INFY.NS"    # Change to any NSE stock
    period = "1y"         # 1 year of data

    # MACD standard parameters (12, 26, 9) — don't change unless you know why
    fast_period   = 12
    slow_period   = 26
    signal_period = 9

    # ── Download ──
    df = get_stock_data(ticker, period)

    # ── Calculate MACD ──
    df['MACD'], df['Signal'], df['Histogram'] = calculate_macd(
        df['Close'], fast_period, slow_period, signal_period
    )

    # ── Detect All Signals ──
    crossover_sigs  = detect_crossovers(df)
    zero_sigs       = detect_zero_crossovers(df)
    momentum_sigs   = detect_histogram_momentum(df)
    divergence_sigs = detect_macd_divergence(df, lookback=6)

    # Combine all signals sorted by date
    all_signals = sorted(
        crossover_sigs + zero_sigs + divergence_sigs,
        key=lambda x: x['Date']
    )

    # ── Print Summary ──
    print(f"\n{'='*68}")
    print(f"  MACD ANALYSIS — {ticker}  ({fast_period}, {slow_period}, {signal_period})")
    print(f"{'='*68}")

    # Current readings
    cur_close  = round(df['Close'].iloc[-1], 2)
    cur_macd   = round(df['MACD'].iloc[-1], 3)
    cur_signal = round(df['Signal'].iloc[-1], 3)
    cur_hist   = round(df['Histogram'].iloc[-1], 3)

    print(f"\n  Current Close     : ₹{cur_close}")
    print(f"  Current MACD      : {cur_macd}")
    print(f"  Current Signal    : {cur_signal}")
    print(f"  Current Histogram : {cur_hist}")

    # Interpret current state
    print(f"\n  ── Current State ──")

    if cur_macd > 0:
        print(f"  MACD above zero   → Trend is BULLISH (EMA12 > EMA26)")
    else:
        print(f"  MACD below zero   → Trend is BEARISH (EMA12 < EMA26)")

    if cur_macd > cur_signal:
        print(f"  MACD above Signal → Bullish momentum active")
    else:
        print(f"  MACD below Signal → Bearish momentum active")

    if cur_hist > 0:
        print(f"  Histogram positive → Buyers are in control")
    else:
        print(f"  Histogram negative → Sellers are in control")

    # Recent signals (last 8)
    print(f"\n  ── Recent Signals (last 8) ──")
    if all_signals:
        for sig in all_signals[-8:]:
            direction = "BUY  " if "BUY" in sig['Signal'] or "BULL" in sig['Signal'] else "SELL "
            print(f"  {sig['Date']}  {direction}  {sig['Type']:<28}  MACD={sig['MACD']:<9}  ₹{sig['Close']}")
            print(f"           {sig.get('Detail', '')}")
    else:
        print("  No significant signals found in this period.")

    # Momentum warnings (these are different — not buy/sell, just alerts)
    recent_momentum = momentum_sigs[-5:] if momentum_sigs else []
    if recent_momentum:
        print(f"\n  ── Momentum Warnings (last 5) ──")
        for sig in recent_momentum:
            print(f"  {sig['Date']}  {sig['Signal']:<40}  ₹{sig['Close']}")

    # Signal counts
    buy_count  = sum(1 for s in all_signals if 'BUY'  in s['Signal'] or 'BULL' in s['Signal'])
    sell_count = sum(1 for s in all_signals if 'SELL' in s['Signal'] or 'BEAR' in s['Signal'])
    print(f"\n  Total BUY signals  : {buy_count}")
    print(f"  Total SELL signals : {sell_count}")

    print(f"\n  TIP: Strongest setups = MACD crossover + RSI at extreme + price above SMA 200.")
    print(f"{'='*68}\n")

    # ── Plot Chart ──
    plot_macd_chart(df, ticker, crossover_sigs, zero_sigs)


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()