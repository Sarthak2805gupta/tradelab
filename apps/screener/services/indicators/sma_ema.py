# ============================================================
# SMA & EMA CALCULATOR WITH CROSSOVER DETECTION
# For Indian Stocks (NSE)
# ============================================================
# This script:
#   1. Downloads real stock data from Yahoo Finance
#   2. Calculates SMA and EMA manually (so you understand the math)
#   3. Detects Golden Cross, Death Cross, and price crossovers
#   4. Plots everything on a chart
#   5. Prints a trading signal summary
#
# INSTALL REQUIRED LIBRARIES FIRST (run once in terminal):
#   pip install yfinance pandas matplotlib
# ============================================================


# ── Imports ──────────────────────────────────────────────────
import yfinance as yf            # Downloads stock price data
import pandas as pd              # For working with tabular data
import matplotlib.pyplot as plt  # For plotting charts
import matplotlib.dates as mdates # For formatting dates on chart axis


# ── STEP 1: Download Stock Data ───────────────────────────────
def get_stock_data(ticker, period="1y"):
    """
    Downloads 1 year of daily OHLCV data for a given NSE stock.

    Parameters:
        ticker (str): e.g. "RELIANCE.NS"
        period (str): "6mo", "1y", "2y" etc.

    Returns:
        df (DataFrame): Table with Open, High, Low, Close, Volume columns
    """
    print(f"\nDownloading data for {ticker} ...")

    # Download from Yahoo Finance
    df = yf.download(ticker, period=period, auto_adjust=True)

    # Drop any rows with missing values
    df.dropna(inplace=True)

    # Flatten multi-level columns if yfinance returns them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} trading days | {df.index[0].date()} to {df.index[-1].date()}")
    return df


# ── STEP 2: Calculate SMA ─────────────────────────────────────
def calculate_sma(prices, period):
    """
    Simple Moving Average — plain average of last N prices.

    How it works:
        Day 5 SMA(5) = average of days 1,2,3,4,5
        Day 6 SMA(5) = average of days 2,3,4,5,6   (window slides)
        ...

    Parameters:
        prices (Series): Closing prices
        period (int): Number of days to average

    Returns:
        Series: SMA values (first (period-1) values will be NaN)
    """
    # pandas .rolling(period).mean() does exactly this sliding window average
    # min_periods=period means we need at least 'period' data points before calculating
    sma = prices.rolling(window=period, min_periods=period).mean()

    return sma


# ── STEP 3: Calculate EMA ─────────────────────────────────────
def calculate_ema(prices, period):
    """
    Exponential Moving Average — gives more weight to recent prices.

    Formula:
        k = 2 / (period + 1)            ← smoothing factor (multiplier)
        EMA today = Price × k + EMA_yesterday × (1 - k)

    Example with period=10:
        k = 2/(10+1) = 0.1818
        If EMA_yesterday=1000, Price_today=1100:
        EMA = 1100×0.1818 + 1000×0.8182 = 200 + 818 = 1018

    Notice: recent price gets 18.18% weight, but old EMA carries 81.82%.
    This means EMA "remembers" history but leans towards recent prices.

    Parameters:
        prices (Series): Closing prices
        period (int): Number of days for the EMA period

    Returns:
        Series: EMA values
    """
    # pandas .ewm() handles EMA calculation for us
    # adjust=False means it uses the recursive formula above (not a weighted average)
    ema = prices.ewm(span=period, adjust=False).mean()

    return ema


# ── STEP 4: Detect Crossover Signals ─────────────────────────
def detect_crossovers(df, fast_col, slow_col, signal_name):
    """
    Detects when one line crosses another (e.g., SMA50 crosses SMA200).

    How crossover detection works:
        - If fast line is ABOVE slow line today but was BELOW yesterday → crossover up (bullish)
        - If fast line is BELOW slow line today but was ABOVE yesterday → crossover down (bearish)

    Parameters:
        df (DataFrame): Must contain the fast_col and slow_col columns
        fast_col (str): Column name of the faster moving average
        slow_col (str): Column name of the slower moving average
        signal_name (str): Label for the signal (e.g., "Golden/Death Cross")

    Returns:
        List of dicts with date and type of each crossover found
    """

    crossovers = []   # We'll collect detected crossovers here

    # We need at least 2 rows to compare today vs yesterday
    # So we start from index 1 (second row)
    for i in range(1, len(df)):

        # Get today's and yesterday's values for both MAs
        fast_today      = df[fast_col].iloc[i]
        fast_yesterday  = df[fast_col].iloc[i - 1]
        slow_today      = df[slow_col].iloc[i]
        slow_yesterday  = df[slow_col].iloc[i - 1]

        # Skip if any value is NaN (not calculated yet — beginning of the data)
        if any(pd.isna(v) for v in [fast_today, fast_yesterday, slow_today, slow_yesterday]):
            continue

        date = df.index[i].date()

        # ── Bullish crossover: fast crosses ABOVE slow ──
        # Yesterday: fast < slow  →  Today: fast > slow
        if fast_yesterday < slow_yesterday and fast_today > slow_today:
            crossovers.append({
                'Date': date,
                'Signal': f'BULLISH {signal_name}',
                'Close': round(df['Close'].iloc[i], 2)
            })

        # ── Bearish crossover: fast crosses BELOW slow ──
        # Yesterday: fast > slow  →  Today: fast < slow
        elif fast_yesterday > slow_yesterday and fast_today < slow_today:
            crossovers.append({
                'Date': date,
                'Signal': f'BEARISH {signal_name}',
                'Close': round(df['Close'].iloc[i], 2)
            })

    return crossovers


# ── STEP 5: Plot the Chart ────────────────────────────────────
def plot_chart(df, ticker):
    """
    Creates a chart showing:
        - Candlestick-style closing price (as a line)
        - SMA 20, SMA 50, SMA 200
        - EMA 20, EMA 50
        - Golden Cross and Death Cross markers
        - Volume bar chart at the bottom

    Parameters:
        df (DataFrame): Stock data with MA columns added
        ticker (str): Stock name for the chart title
    """

    # Create a figure with 2 rows:
    # Row 1 (taller): Price + Moving Averages
    # Row 2 (shorter): Volume
    fig, (ax1, ax2) = plt.subplots(
        2, 1,
        figsize=(14, 8),           # Width=14 inches, Height=8 inches
        gridspec_kw={'height_ratios': [3, 1]},  # Top chart 3x taller than bottom
        sharex=True                 # Both charts share the same x-axis (dates)
    )

    # ── Top chart: Price and MAs ──

    # Plot closing price (thin gray line)
    ax1.plot(df.index, df['Close'], color='gray', linewidth=0.8,
             alpha=0.7, label='Close Price', zorder=1)

    # Plot SMA lines
    ax1.plot(df.index, df['SMA_20'],  color='#378ADD', linewidth=1.5,
             linestyle='--', label='SMA 20', zorder=2)
    ax1.plot(df.index, df['SMA_50'],  color='#1D9E75', linewidth=2,
             label='SMA 50', zorder=2)
    ax1.plot(df.index, df['SMA_200'], color='#E24B4A', linewidth=2,
             linestyle=':', label='SMA 200', zorder=2)

    # Plot EMA lines
    ax1.plot(df.index, df['EMA_20'], color='#EF9F27', linewidth=1.5,
             linestyle='-.', label='EMA 20', zorder=2)

    # Mark Golden Cross points (green triangle pointing up)
    golden = df[df['Golden_Cross'] == True]
    if len(golden) > 0:
        ax1.scatter(golden.index, golden['Close'],
                    marker='^',          # Triangle up = bullish
                    color='#1D9E75',
                    s=150,               # Size of the marker
                    zorder=5,
                    label='Golden Cross')

    # Mark Death Cross points (red triangle pointing down)
    death = df[df['Death_Cross'] == True]
    if len(death) > 0:
        ax1.scatter(death.index, death['Close'],
                    marker='v',          # Triangle down = bearish
                    color='#E24B4A',
                    s=150,
                    zorder=5,
                    label='Death Cross')

    # Add chart labels and formatting
    ax1.set_title(f'{ticker} — Moving Average Analysis', fontsize=14, pad=12)
    ax1.set_ylabel('Price (₹)', fontsize=11)
    ax1.legend(loc='upper left', fontsize=8, framealpha=0.8)
    ax1.grid(True, alpha=0.3)            # Light grid lines

    # ── Bottom chart: Volume ──

    # Color volume bars green if close > open (up day), red if down day
    colors = ['#1D9E75' if c >= o else '#E24B4A'
              for c, o in zip(df['Close'], df['Open'])]

    ax2.bar(df.index, df['Volume'],
            color=colors,
            alpha=0.7,
            width=1)         # Width=1 so bars touch each other (no gaps)

    ax2.set_ylabel('Volume', fontsize=11)
    ax2.grid(True, alpha=0.3)

    # Format x-axis dates nicely
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45)

    # Adjust layout to prevent overlapping
    plt.tight_layout()

    # Save chart as a PNG image file
    filename = f"{ticker.replace('.', '_')}_MA_chart.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\nChart saved as: {filename}")

    # Display the chart on screen
    plt.show()


# ── STEP 6: Main Program ──────────────────────────────────────
def main():
    """
    Main function — runs the full analysis pipeline.
    """

    # ── Configuration ──
    # Change this to any NSE stock you want to analyze
    ticker = "RELIANCE.NS"
    period = "1y"              # 1 year of data

    # ── Download data ──
    df = get_stock_data(ticker, period)

    # ── Calculate all Moving Averages ──
    # We add each MA as a new column to the dataframe

    df['SMA_20']  = calculate_sma(df['Close'], 20)   # 20-day Simple MA
    df['SMA_50']  = calculate_sma(df['Close'], 50)   # 50-day Simple MA
    df['SMA_200'] = calculate_sma(df['Close'], 200)  # 200-day Simple MA (needs 200+ days of data)

    df['EMA_20']  = calculate_ema(df['Close'], 20)   # 20-day Exponential MA
    df['EMA_50']  = calculate_ema(df['Close'], 50)   # 50-day Exponential MA

    # ── Detect Golden Cross and Death Cross ──
    # Golden Cross: SMA_50 crosses above SMA_200 → major bullish signal
    # Death Cross:  SMA_50 crosses below SMA_200 → major bearish signal

    # Method: compare today's positions with yesterday's
    # .shift(1) gives yesterday's values
    sma50_above_200_today     = df['SMA_50'] > df['SMA_200']
    sma50_above_200_yesterday = df['SMA_50'].shift(1) > df['SMA_200'].shift(1)

    # Golden Cross = was below yesterday, now above today
    df['Golden_Cross'] = (~sma50_above_200_yesterday) & sma50_above_200_today

    # Death Cross = was above yesterday, now below today
    df['Death_Cross']  = sma50_above_200_yesterday & (~sma50_above_200_today)

    # ── Detect Price-MA Crossovers ──
    crossovers_20  = detect_crossovers(df, 'Close', 'SMA_20',  'Price/SMA20 Cross')
    crossovers_50  = detect_crossovers(df, 'Close', 'SMA_50',  'Price/SMA50 Cross')
    golden_crosses = detect_crossovers(df, 'SMA_50', 'SMA_200', 'Golden/Death Cross')

    # ── Print Summary ──
    print(f"\n{'='*60}")
    print(f"  MOVING AVERAGE ANALYSIS: {ticker}")
    print(f"{'='*60}")

    # Current price and MA values
    last_close   = round(df['Close'].iloc[-1], 2)
    last_sma20   = round(df['SMA_20'].iloc[-1], 2)
    last_sma50   = round(df['SMA_50'].iloc[-1], 2)
    last_sma200  = round(df['SMA_200'].iloc[-1], 2)
    last_ema20   = round(df['EMA_20'].iloc[-1], 2)

    print(f"\n  Current Price : ₹{last_close}")
    print(f"  SMA 20        : ₹{last_sma20}")
    print(f"  SMA 50        : ₹{last_sma50}")
    print(f"  SMA 200       : ₹{last_sma200}")
    print(f"  EMA 20        : ₹{last_ema20}")

    # Trend assessment based on MA positions
    print(f"\n  ── Trend Assessment ──")
    if last_close > last_sma200:
        print(f"  Price is ABOVE SMA 200 → Long-term UPTREND")
    else:
        print(f"  Price is BELOW SMA 200 → Long-term DOWNTREND")

    if last_sma50 > last_sma200:
        print(f"  SMA 50 > SMA 200 → Currently in GOLDEN CROSS zone (bullish)")
    else:
        print(f"  SMA 50 < SMA 200 → Currently in DEATH CROSS zone (bearish)")

    if last_close > last_sma20:
        print(f"  Price is ABOVE SMA 20 → Short-term momentum is UP")
    else:
        print(f"  Price is BELOW SMA 20 → Short-term momentum is DOWN")

    # Recent crossover signals (last 5)
    all_signals = sorted(crossovers_20 + crossovers_50 + golden_crosses,
                         key=lambda x: x['Date'])

    print(f"\n  ── Recent Crossover Signals (last 5) ──")
    if all_signals:
        for sig in all_signals[-5:]:   # Show only the 5 most recent
            tag = "BUY  " if "BULLISH" in sig['Signal'] else "SELL "
            print(f"  {sig['Date']}  {tag}  {sig['Signal']:<40}  Close: ₹{sig['Close']}")
    else:
        print("  No crossover signals found in this period.")

    print(f"\n{'='*60}")
    print("  REMINDER: MAs lag — always confirm with RSI, MACD, volume.")
    print(f"{'='*60}\n")

    # ── Plot Chart ──
    plot_chart(df, ticker)


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()