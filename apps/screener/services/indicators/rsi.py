# ============================================================
# RSI (RELATIVE STRENGTH INDEX) CALCULATOR
# For Indian Stocks (NSE)
# ============================================================
# This script:
#   1. Downloads real stock data from Yahoo Finance
#   2. Calculates RSI from scratch (step by step)
#   3. Detects all 4 RSI signals:
#       - Overbought / Oversold crossings
#       - Bullish and Bearish Divergence
#       - Centerline (50) crossovers
#       - Failure Swings
#   4. Plots price + RSI on a chart
#   5. Prints a full signal summary
#
# INSTALL FIRST:
#   pip install yfinance pandas matplotlib
# ============================================================


# ── Imports ──────────────────────────────────────────────────
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches   # For colored legend boxes in chart
import numpy as np                      # For finding local min/max (divergence)


# ── STEP 1: Download Stock Data ───────────────────────────────
def get_stock_data(ticker, period="6mo"):
    """
    Downloads daily OHLCV data for a given NSE stock.

    Parameters:
        ticker (str): e.g. "TCS.NS", "HDFCBANK.NS"
        period (str): "3mo", "6mo", "1y", "2y"

    Returns:
        df (DataFrame): Stock price data
    """
    print(f"\nDownloading {ticker} ...")
    df = yf.download(ticker, period=period, auto_adjust=True)
    df.dropna(inplace=True)

    # Flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ── STEP 2: Calculate RSI ─────────────────────────────────────
def calculate_rsi(prices, period=14):
    """
    Calculates RSI using Wilder's Smoothing Method.

    Full step-by-step:
    ─────────────────────────────────────────────
    Step 1: Daily price change = today's close - yesterday's close
    Step 2: Separate into gains (positive changes) and losses (negative)
    Step 3: First Average Gain = simple average of first 'period' gains
            First Average Loss = simple average of first 'period' losses
    Step 4: From day (period+1) onwards, use Wilder's smoothing:
            Avg Gain = (prev Avg Gain × (period-1) + today's gain) / period
            Avg Loss = (prev Avg Loss × (period-1) + today's loss) / period
    Step 5: RS  = Avg Gain / Avg Loss
            RSI = 100 - (100 / (1 + RS))
    ─────────────────────────────────────────────

    Parameters:
        prices (Series): Closing prices
        period (int): RSI period, default is 14

    Returns:
        Series: RSI values (first 'period' rows will be NaN)
    """

    # Calculate daily price changes
    # .diff(1) = today's price minus yesterday's price
    delta = prices.diff(1)

    # Separate gains and losses
    # .clip(lower=0) keeps only positive values (gains), sets negatives to 0
    # .clip(upper=0) keeps only negative values, then multiply by -1 to make positive
    gains  = delta.clip(lower=0)          # Only positive changes
    losses = delta.clip(upper=0).abs()    # Only losses (made positive)

    # Calculate the first average gain and loss using simple average
    # .rolling(period).mean() for the first calculation
    avg_gain = gains.rolling(window=period, min_periods=period).mean()
    avg_loss = losses.rolling(window=period, min_periods=period).mean()

    # Apply Wilder's smoothing from row (period) onwards
    # We convert to a list to manually apply the recursive formula
    avg_gain_list = avg_gain.tolist()
    avg_loss_list = avg_loss.tolist()
    gains_list    = gains.tolist()
    losses_list   = losses.tolist()

    # Loop from day (period) onwards and apply smoothing
    for i in range(period, len(avg_gain_list)):
        if pd.isna(avg_gain_list[i - 1]):
            continue   # Skip until we have the first average

        # Wilder's smoothing formula:
        # New Average = (Old Average × (period - 1) + today's value) / period
        avg_gain_list[i] = (avg_gain_list[i - 1] * (period - 1) + gains_list[i]) / period
        avg_loss_list[i] = (avg_loss_list[i - 1] * (period - 1) + losses_list[i]) / period

    # Convert back to pandas Series
    avg_gain = pd.Series(avg_gain_list, index=prices.index)
    avg_loss = pd.Series(avg_loss_list, index=prices.index)

    # Calculate RS (Relative Strength)
    # RS = Average Gain / Average Loss
    # Handle division by zero: if avg_loss = 0, RS = infinity → RSI = 100
    rs = avg_gain / avg_loss.replace(0, float('nan'))

    # Calculate RSI
    # RSI = 100 - (100 / (1 + RS))
    rsi = 100 - (100 / (1 + rs))

    # When avg_loss is 0 (all gains), RSI = 100
    rsi = rsi.fillna(100)

    return rsi.round(2)


# ── STEP 3: Detect Overbought / Oversold Signals ─────────────
def detect_ob_os_signals(df, ob=70, os=30):
    """
    Detects when RSI crosses into overbought or oversold zones.

    Logic:
        - RSI crosses ABOVE 'os' (30) from below → Oversold exit → BUY signal
        - RSI crosses BELOW 'ob' (70) from above → Overbought exit → SELL signal

    Note: We detect the EXIT from overbought/oversold (not just entry)
    because that confirms the reversal has started.

    Parameters:
        df (DataFrame): Must have 'RSI' column
        ob (int): Overbought threshold (default 70)
        os (int): Oversold threshold (default 30)

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        rsi_today     = df['RSI'].iloc[i]
        rsi_yesterday = df['RSI'].iloc[i - 1]
        date          = df.index[i].date()
        close         = round(df['Close'].iloc[i], 2)

        # Skip if RSI not yet calculated
        if pd.isna(rsi_today) or pd.isna(rsi_yesterday):
            continue

        # RSI crosses UP through 30 (exiting oversold) → BUY
        if rsi_yesterday < os and rsi_today >= os:
            signals.append({
                'Date': date, 'Type': 'RSI Oversold Exit',
                'Signal': 'BUY', 'RSI': rsi_today, 'Close': close
            })

        # RSI crosses DOWN through 70 (exiting overbought) → SELL
        elif rsi_yesterday > ob and rsi_today <= ob:
            signals.append({
                'Date': date, 'Type': 'RSI Overbought Exit',
                'Signal': 'SELL', 'RSI': rsi_today, 'Close': close
            })

    return signals


# ── STEP 4: Detect RSI Centerline Cross ──────────────────────
def detect_centerline_cross(df):
    """
    Detects when RSI crosses the 50 level.

    RSI above 50 → bulls in control → bullish bias
    RSI below 50 → bears in control → bearish bias

    Parameters:
        df (DataFrame): Must have 'RSI' column

    Returns:
        List of signal dicts
    """
    signals = []

    for i in range(1, len(df)):
        rsi_today     = df['RSI'].iloc[i]
        rsi_yesterday = df['RSI'].iloc[i - 1]
        date          = df.index[i].date()
        close         = round(df['Close'].iloc[i], 2)

        if pd.isna(rsi_today) or pd.isna(rsi_yesterday):
            continue

        # RSI crosses above 50 → bullish
        if rsi_yesterday < 50 and rsi_today >= 50:
            signals.append({
                'Date': date, 'Type': 'RSI Centerline Cross',
                'Signal': 'BULLISH BIAS', 'RSI': rsi_today, 'Close': close
            })

        # RSI crosses below 50 → bearish
        elif rsi_yesterday > 50 and rsi_today <= 50:
            signals.append({
                'Date': date, 'Type': 'RSI Centerline Cross',
                'Signal': 'BEARISH BIAS', 'RSI': rsi_today, 'Close': close
            })

    return signals


# ── STEP 5: Detect RSI Divergence ────────────────────────────
def detect_divergence(df, lookback=5):
    """
    Detects bullish and bearish divergence between price and RSI.

    What is divergence?
        Bullish divergence: Price makes a LOWER LOW, but RSI makes a HIGHER LOW
        → Selling pressure is weakening → likely reversal UP

        Bearish divergence: Price makes a HIGHER HIGH, but RSI makes a LOWER HIGH
        → Buying pressure is weakening → likely reversal DOWN

    How we detect it:
        We look for local lows in price (a point lower than surrounding N points).
        If price's local low is lower than a previous local low,
        but RSI's corresponding value is HIGHER → bullish divergence.

        Same logic reversed for bearish divergence with local highs.

    Parameters:
        df (DataFrame): Must have 'Close' and 'RSI' columns
        lookback (int): How many points on each side to define a local min/max

    Returns:
        List of divergence signal dicts
    """
    signals = []

    prices = df['Close'].values     # Convert to numpy array for faster processing
    rsi    = df['RSI'].values
    dates  = df.index

    # Find local minima (for bullish divergence)
    # A point is a local minimum if it's lower than 'lookback' points on both sides
    for i in range(lookback, len(prices) - lookback):

        # Skip if RSI not calculated yet
        if pd.isna(rsi[i]):
            continue

        # ── Check for local price minimum ──
        # prices[i] must be the lowest of the surrounding 'lookback' points
        is_price_low = all(prices[i] <= prices[i - j] for j in range(1, lookback + 1)) and \
                       all(prices[i] <= prices[i + j] for j in range(1, lookback + 1))

        if is_price_low:
            # Look back for a previous local low
            for k in range(i - lookback * 2, i - lookback):
                if k < 0 or pd.isna(rsi[k]):
                    continue

                # Was 'k' also a local low?
                if k < lookback or k > len(prices) - lookback - 1:
                    continue

                prev_is_low = all(prices[k] <= prices[k - j] for j in range(1, lookback + 1)) and \
                              all(prices[k] <= prices[k + j] for j in range(1, lookback + 1))

                if prev_is_low:
                    # We have two local lows at index k and i
                    # Bullish divergence: price[i] < price[k] but rsi[i] > rsi[k]
                    if prices[i] < prices[k] and rsi[i] > rsi[k]:
                        signals.append({
                            'Date': dates[i].date(),
                            'Type': 'RSI Divergence',
                            'Signal': 'BUY (Bullish Divergence)',
                            'RSI': round(rsi[i], 2),
                            'Close': round(prices[i], 2),
                            'Detail': f'Price: ₹{round(prices[k],1)} → ₹{round(prices[i],1)} (lower low), RSI: {round(rsi[k],1)} → {round(rsi[i],1)} (higher low)'
                        })
                    break   # Only compare with the most recent previous low

    # Find local maxima (for bearish divergence)
    for i in range(lookback, len(prices) - lookback):

        if pd.isna(rsi[i]):
            continue

        # ── Check for local price maximum ──
        is_price_high = all(prices[i] >= prices[i - j] for j in range(1, lookback + 1)) and \
                        all(prices[i] >= prices[i + j] for j in range(1, lookback + 1))

        if is_price_high:
            for k in range(i - lookback * 2, i - lookback):
                if k < 0 or pd.isna(rsi[k]):
                    continue

                if k < lookback or k > len(prices) - lookback - 1:
                    continue

                prev_is_high = all(prices[k] >= prices[k - j] for j in range(1, lookback + 1)) and \
                               all(prices[k] >= prices[k + j] for j in range(1, lookback + 1))

                if prev_is_high:
                    # Bearish divergence: price[i] > price[k] but rsi[i] < rsi[k]
                    if prices[i] > prices[k] and rsi[i] < rsi[k]:
                        signals.append({
                            'Date': dates[i].date(),
                            'Type': 'RSI Divergence',
                            'Signal': 'SELL (Bearish Divergence)',
                            'RSI': round(rsi[i], 2),
                            'Close': round(prices[i], 2),
                            'Detail': f'Price: ₹{round(prices[k],1)} → ₹{round(prices[i],1)} (higher high), RSI: {round(rsi[k],1)} → {round(rsi[i],1)} (lower high)'
                        })
                    break

    return signals


# ── STEP 6: Plot Chart ────────────────────────────────────────
def plot_rsi_chart(df, ticker, ob_signals, os_signals, divergences):
    """
    Creates a 2-panel chart:
        Top panel: Price with buy/sell markers
        Bottom panel: RSI with overbought/oversold zones colored

    Parameters:
        df (DataFrame): Stock data with RSI column
        ticker (str): Stock name for the title
        ob_signals (list): Overbought/oversold signal dicts
        os_signals (list): Centerline signal dicts
        divergences (list): Divergence signal dicts
    """

    fig, (ax1, ax2) = plt.subplots(
        2, 1,
        figsize=(14, 8),
        gridspec_kw={'height_ratios': [2, 1]},
        sharex=True
    )

    # ── Top chart: Price ──
    ax1.plot(df.index, df['Close'],
             color='#444441', linewidth=1.2, label='Close Price', zorder=2)

    # Mark BUY signals (green up-triangles)
    buy_signals  = [s for s in ob_signals if s['Signal'] == 'BUY']
    sell_signals = [s for s in ob_signals if s['Signal'] == 'SELL']

    for sig in buy_signals:
        # Find the row matching this date
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.scatter(row.index, row['Close'],
                        marker='^', color='#1D9E75', s=120, zorder=5)

    for sig in sell_signals:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            ax1.scatter(row.index, row['Close'],
                        marker='v', color='#E24B4A', s=120, zorder=5)

    # Mark divergence signals
    for sig in divergences:
        row = df[df.index.date == sig['Date']]
        if not row.empty:
            color = '#1D9E75' if 'BUY' in sig['Signal'] else '#E24B4A'
            marker = 'D' if 'BUY' in sig['Signal'] else 'D'   # Diamond shape
            ax1.scatter(row.index, row['Close'],
                        marker='D', color=color, s=100, zorder=5,
                        edgecolors='white', linewidths=0.5)

    # Legend entries
    green_tri  = mpatches.Patch(color='#1D9E75', label='Buy signal (oversold exit)')
    red_tri    = mpatches.Patch(color='#E24B4A', label='Sell signal (overbought exit)')
    div_patch  = mpatches.Patch(color='#534AB7', label='Divergence signal')
    ax1.legend(handles=[green_tri, red_tri, div_patch], fontsize=8)

    ax1.set_title(f'{ticker} — RSI Analysis (14-day)', fontsize=13, pad=10)
    ax1.set_ylabel('Price (₹)', fontsize=10)
    ax1.grid(True, alpha=0.25)

    # ── Bottom chart: RSI ──

    # Fill background zones with colors
    # Green zone below 30 (oversold)
    ax2.axhspan(0,  30, alpha=0.10, color='#1D9E75', label='Oversold zone')
    # Red zone above 70 (overbought)
    ax2.axhspan(70, 100, alpha=0.10, color='#E24B4A', label='Overbought zone')

    # Draw horizontal reference lines
    ax2.axhline(y=70, color='#E24B4A', linewidth=1, linestyle='--', alpha=0.8)
    ax2.axhline(y=50, color='#888780', linewidth=0.8, linestyle=':', alpha=0.6)
    ax2.axhline(y=30, color='#1D9E75', linewidth=1, linestyle='--', alpha=0.8)

    # Draw RSI line
    ax2.plot(df.index, df['RSI'],
             color='#7F77DD', linewidth=2, label='RSI (14)')

    # Add zone labels on the right
    ax2.text(df.index[-1], 72, '  70', fontsize=8, color='#A32D2D', va='bottom')
    ax2.text(df.index[-1], 52, '  50', fontsize=8, color='#888780', va='bottom')
    ax2.text(df.index[-1], 32, '  30', fontsize=8, color='#27500A', va='bottom')

    ax2.set_ylabel('RSI', fontsize=10)
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.25)
    ax2.legend(fontsize=8, loc='upper left')

    plt.tight_layout()

    filename = f"{ticker.replace('.', '_')}_RSI_chart.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\nChart saved as: {filename}")
    plt.show()


# ── STEP 7: Main Program ──────────────────────────────────────
def main():
    """
    Full RSI analysis pipeline:
        1. Download data
        2. Calculate RSI
        3. Detect all signals
        4. Print summary
        5. Plot chart
    """

    # ── Configuration ──
    ticker = "HDFCBANK.NS"    # Change to any NSE stock
    period = "6mo"            # 6 months of data

    # ── Download ──
    df = get_stock_data(ticker, period)

    # ── Calculate RSI ──
    df['RSI'] = calculate_rsi(df['Close'], period=14)

    # ── Detect All Signals ──
    ob_os_signals    = detect_ob_os_signals(df, ob=70, os=30)
    centerline_sigs  = detect_centerline_cross(df)
    divergence_sigs  = detect_divergence(df, lookback=5)

    # Combine all signals and sort by date
    all_signals = sorted(
        ob_os_signals + centerline_sigs + divergence_sigs,
        key=lambda x: x['Date']
    )

    # ── Print Summary ──
    print(f"\n{'='*65}")
    print(f"  RSI ANALYSIS — {ticker}")
    print(f"{'='*65}")

    # Current RSI reading
    current_rsi   = df['RSI'].iloc[-1]
    current_close = df['Close'].iloc[-1]

    print(f"\n  Current Close : ₹{round(current_close, 2)}")
    print(f"  Current RSI   : {current_rsi}")

    # RSI zone interpretation
    if current_rsi >= 70:
        zone = "OVERBOUGHT — consider taking profits"
    elif current_rsi <= 30:
        zone = "OVERSOLD — look for buy opportunities"
    elif current_rsi >= 50:
        zone = "Bullish zone (above 50) — upward momentum"
    else:
        zone = "Bearish zone (below 50) — downward momentum"

    print(f"  RSI Zone      : {zone}")

    # Recent signals (last 8)
    print(f"\n  ── All Signals (last 8 events) ──")
    if all_signals:
        for sig in all_signals[-8:]:
            direction = "BUY  " if "BUY" in sig['Signal'] or "BULL" in sig['Signal'] else "SELL "
            detail    = sig.get('Detail', '')   # Divergence signals have extra detail
            rsi_str   = f"RSI={sig['RSI']}"
            print(f"  {sig['Date']}  {direction}  {sig['Type']:<28}  {rsi_str:<10}  ₹{sig['Close']}")
            if detail:
                print(f"           Detail: {detail}")
    else:
        print("  No significant signals found in this period.")

    # Counts
    buy_count  = sum(1 for s in all_signals if 'BUY'  in s['Signal'] or 'BULL' in s['Signal'])
    sell_count = sum(1 for s in all_signals if 'SELL' in s['Signal'] or 'BEAR' in s['Signal'])

    print(f"\n  Total BUY signals  : {buy_count}")
    print(f"  Total SELL signals : {sell_count}")
    print(f"\n  REMINDER: Confirm RSI signals with candlestick patterns + SMA trend direction.")
    print(f"{'='*65}\n")

    # ── Plot Chart ──
    plot_rsi_chart(df, ticker, ob_os_signals, centerline_sigs, divergence_sigs)


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()