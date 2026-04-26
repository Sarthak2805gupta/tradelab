# =============================================================================
# TRADING ANALYSIS & RISK TOOLS SUITE
# All 11 tools combined in one file
#
# TOOLS INCLUDED:
#   ANALYSIS TOOLS:
#     1. Multi-timeframe Confluence Analyzer
#     2. Support & Resistance Detector
#     3. Sector Rotation Tracker
#     4. Relative Strength Ranker
#     5. Correlation Matrix
#     6. Market Breadth Dashboard
#
#   RISK & PORTFOLIO TOOLS:
#     7.  Position Sizing Calculator
#     8.  Portfolio Risk Dashboard
#     9.  Trade Journal with Analytics
#     10. Monte Carlo Simulator
#     11. Risk of Ruin Calculator
#
# HOW TO INSTALL REQUIRED LIBRARIES (run these in your terminal first):
#   pip install yfinance pandas numpy scipy matplotlib seaborn tabulate
#
# HOW TO RUN:
#   python trading_analysis_suite.py
#
# WORKS WITH NSE STOCKS: Use symbol like "RELIANCE.NS", "TCS.NS", "NIFTY50.NS"
# =============================================================================

# --- IMPORT LIBRARIES ---
# These are external Python packages we need to install (see above)
import yfinance as yf          # Downloads free stock data from Yahoo Finance
import pandas as pd            # Used for tables (DataFrames) and data manipulation
import numpy as np             # Used for math/statistics (arrays, calculations)
import matplotlib.pyplot as plt  # Used for drawing charts and graphs
import matplotlib.gridspec as gridspec  # Helps arrange multiple charts on one figure
import seaborn as sns          # Makes prettier heatmaps and statistical charts
from scipy import stats        # For statistical calculations (z-score, etc.)
from tabulate import tabulate  # Prints clean formatted tables in the terminal
import warnings                # Used to suppress irrelevant warning messages
import os                      # Used to clear the terminal screen
import json                    # Used to save/load trade journal data as a file
from datetime import datetime, timedelta  # Used for dates and time calculations
import random                  # Used in Monte Carlo simulation (random number generation)

# Suppress harmless warnings so output stays clean
warnings.filterwarnings('ignore')


# =============================================================================
# HELPER FUNCTIONS
# These are small utility functions used by multiple tools below
# =============================================================================

def clear_screen():
    """Clears the terminal screen so menus look fresh."""
    # 'cls' clears screen on Windows, 'clear' works on Mac/Linux
    os.system('cls' if os.name == 'nt' else 'clear')


def download_data(symbol, period="6mo", interval="1d"):
    """
    Downloads historical stock price data from Yahoo Finance.

    Parameters:
        symbol  : Stock ticker, e.g. "RELIANCE.NS" for NSE, "AAPL" for US
        period  : How far back to download, e.g. "1mo", "3mo", "6mo", "1y", "2y"
        interval: Candle size, e.g. "1d" = daily, "1h" = hourly, "15m" = 15-minute

    Returns:
        A pandas DataFrame with columns: Open, High, Low, Close, Volume
        Returns None if download fails.
    """
    try:
        print(f"  Downloading data for {symbol}...")
        # yf.download() fetches price data from Yahoo Finance (it's free!)
        df = yf.download(symbol, period=period, interval=interval, progress=False)

        # If the DataFrame is empty, the symbol was probably wrong
        if df.empty:
            print(f"  ERROR: No data found for '{symbol}'. Check the symbol name.")
            return None

        # Flatten multi-level column names (yfinance sometimes returns them nested)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df  # Return the table of price data

    except Exception as e:
        # If anything goes wrong, print the error and return None
        print(f"  ERROR downloading {symbol}: {e}")
        return None


def calculate_rsi(close_prices, period=14):
    """
    Calculates RSI (Relative Strength Index) - a momentum indicator (0 to 100).
    - RSI above 70 = overbought (price may fall soon)
    - RSI below 30 = oversold (price may rise soon)

    Parameters:
        close_prices : A pandas Series of closing prices
        period       : Lookback window, default is 14 days

    Returns:
        A pandas Series of RSI values
    """
    # Calculate day-to-day price change
    delta = close_prices.diff()

    # Separate gains (positive changes) and losses (negative changes)
    gain = delta.where(delta > 0, 0)   # Keep gains, set losses to 0
    loss = -delta.where(delta < 0, 0)  # Keep losses (as positive), set gains to 0

    # Calculate the average gain and loss over the period using Exponential Moving Average
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    # RSI formula: 100 - (100 / (1 + RS)) where RS = avg_gain / avg_loss
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(close_prices, fast=12, slow=26, signal=9):
    """
    Calculates MACD (Moving Average Convergence Divergence).
    MACD is used to spot trend changes and momentum.

    Parameters:
        close_prices : pandas Series of closing prices
        fast         : Short EMA period (default 12)
        slow         : Long EMA period (default 26)
        signal       : Signal line EMA period (default 9)

    Returns:
        macd_line    : Difference between fast and slow EMA
        signal_line  : Smoothed version of macd_line
        histogram    : Difference between macd_line and signal_line
    """
    # EMA = Exponential Moving Average (gives more weight to recent prices)
    ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
    ema_slow = close_prices.ewm(span=slow, adjust=False).mean()

    # MACD line = fast EMA minus slow EMA
    macd_line = ema_fast - ema_slow

    # Signal line = EMA of the MACD line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    # Histogram shows the gap between MACD and signal
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_atr(df, period=14):
    """
    Calculates ATR (Average True Range) - measures market volatility.
    Higher ATR = more volatile market (wider price swings).

    Parameters:
        df     : DataFrame with 'High', 'Low', 'Close' columns
        period : Lookback window, default 14 days

    Returns:
        A pandas Series of ATR values
    """
    # True Range is the largest of these 3 values:
    high_low   = df['High'] - df['Low']                     # Today's range
    high_close = abs(df['High'] - df['Close'].shift(1))     # Gap up
    low_close  = abs(df['Low'] - df['Close'].shift(1))      # Gap down

    # True Range = max of the three above
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    # ATR = rolling average of True Range
    atr = true_range.rolling(window=period).mean()

    return atr


def get_symbol_input(prompt="Enter stock symbol (e.g. RELIANCE.NS): "):
    """Asks the user to type a stock symbol and returns it in uppercase."""
    symbol = input(prompt).strip().upper()
    return symbol


def press_enter_to_continue():
    """Pauses the program and waits for the user to press Enter."""
    input("\n  Press Enter to return to menu...")


# =============================================================================
# TOOL 1: MULTI-TIMEFRAME CONFLUENCE ANALYZER
# =============================================================================

def tool_1_multi_timeframe_confluence():
    """
    Analyzes a stock across 3 timeframes (daily, weekly, monthly).
    Checks if RSI, MACD, and Moving Averages all agree on the same direction.
    When multiple timeframes agree (confluence), the signal is stronger.
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 1: MULTI-TIMEFRAME CONFLUENCE ANALYZER")
    print("=" * 60)
    print("  This tool checks RSI, MACD, and Moving Averages")
    print("  across Daily, Weekly, and Monthly timeframes.")
    print("  When all agree = strong signal (confluence).")
    print()

    # Ask user for the stock symbol
    symbol = get_symbol_input("  Enter stock symbol (e.g. RELIANCE.NS, TCS.NS): ")

    # We will analyze 3 timeframes
    # Each tuple is: (label, yfinance_period, yfinance_interval)
    timeframes = [
        ("Daily",   "6mo",  "1d"),    # Last 6 months, daily candles
        ("Weekly",  "2y",   "1wk"),   # Last 2 years, weekly candles
        ("Monthly", "5y",   "1mo"),   # Last 5 years, monthly candles
    ]

    print()
    results = []  # We'll collect results for each timeframe here

    for tf_label, tf_period, tf_interval in timeframes:
        print(f"  Analyzing {tf_label} timeframe...")

        # Download data for this timeframe
        df = download_data(symbol, period=tf_period, interval=tf_interval)
        if df is None:
            continue  # Skip this timeframe if data download failed

        close = df['Close']  # Extract just the closing price column

        # --- Calculate indicators ---
        rsi = calculate_rsi(close)
        macd_line, signal_line, _ = calculate_macd(close)

        # Moving Averages: SMA = Simple Moving Average (average of last N prices)
        sma_20 = close.rolling(20).mean()   # 20-period SMA (short term)
        sma_50 = close.rolling(50).mean()   # 50-period SMA (medium term)

        # Get the most recent values of each indicator
        latest_close  = float(close.iloc[-1])
        latest_rsi    = float(rsi.iloc[-1])
        latest_macd   = float(macd_line.iloc[-1])
        latest_signal = float(signal_line.iloc[-1])
        latest_sma20  = float(sma_20.iloc[-1])
        latest_sma50  = float(sma_50.iloc[-1])

        # --- Generate signals ---
        # RSI signal: >55 = bullish, <45 = bearish, else neutral
        if latest_rsi > 55:
            rsi_signal = "BULLISH"
        elif latest_rsi < 45:
            rsi_signal = "BEARISH"
        else:
            rsi_signal = "NEUTRAL"

        # MACD signal: if MACD line is above signal line = bullish
        if latest_macd > latest_signal:
            macd_signal = "BULLISH"
        elif latest_macd < latest_signal:
            macd_signal = "BEARISH"
        else:
            macd_signal = "NEUTRAL"

        # Price vs SMA signal: price above both SMAs = bullish
        if latest_close > latest_sma20 and latest_close > latest_sma50:
            price_signal = "BULLISH"
        elif latest_close < latest_sma20 and latest_close < latest_sma50:
            price_signal = "BEARISH"
        else:
            price_signal = "NEUTRAL"

        # Count how many indicators are bullish/bearish
        signals = [rsi_signal, macd_signal, price_signal]
        bull_count = signals.count("BULLISH")
        bear_count = signals.count("BEARISH")

        # Determine overall signal for this timeframe
        if bull_count >= 2:
            overall = "BULLISH"
        elif bear_count >= 2:
            overall = "BEARISH"
        else:
            overall = "MIXED"

        # Store this timeframe's result
        results.append({
            "Timeframe":    tf_label,
            "Close":        f"{latest_close:.2f}",
            "RSI":          f"{latest_rsi:.1f} ({rsi_signal})",
            "MACD":         macd_signal,
            "Price vs SMA": price_signal,
            "Overall":      overall
        })

    # --- Display Results ---
    print()
    print(f"  CONFLUENCE ANALYSIS FOR: {symbol}")
    print("-" * 60)

    if results:
        # Convert list of dicts to a DataFrame for clean printing
        df_results = pd.DataFrame(results)
        # tabulate() makes a clean ASCII table
        print(tabulate(df_results, headers='keys', tablefmt='rounded_outline', showindex=False))

        # Check for confluence (all 3 timeframes agree)
        overalls = [r["Overall"] for r in results]
        print()
        if overalls.count("BULLISH") == 3:
            print("  *** STRONG BULLISH CONFLUENCE - All timeframes agree: BUY signal ***")
        elif overalls.count("BEARISH") == 3:
            print("  *** STRONG BEARISH CONFLUENCE - All timeframes agree: SELL signal ***")
        elif overalls.count("BULLISH") == 2:
            print("  >> MODERATE BULLISH CONFLUENCE - 2 of 3 timeframes bullish")
        elif overalls.count("BEARISH") == 2:
            print("  >> MODERATE BEARISH CONFLUENCE - 2 of 3 timeframes bearish")
        else:
            print("  -- NO CONFLUENCE - Timeframes are mixed, wait for clarity")

    press_enter_to_continue()


# =============================================================================
# TOOL 2: SUPPORT & RESISTANCE DETECTOR
# =============================================================================

def tool_2_support_resistance():
    """
    Detects key Support and Resistance levels using pivot points.
    Support = price level where stock tends to stop falling (buyers step in)
    Resistance = price level where stock tends to stop rising (sellers step in)
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 2: SUPPORT & RESISTANCE DETECTOR")
    print("=" * 60)
    print("  Finds key price levels using Pivot Points.")
    print("  Support levels = where price may bounce UP")
    print("  Resistance levels = where price may bounce DOWN")
    print()

    symbol = get_symbol_input("  Enter stock symbol (e.g. RELIANCE.NS): ")

    # Download 3 months of daily data
    df = download_data(symbol, period="3mo", interval="1d")
    if df is None:
        press_enter_to_continue()
        return

    # --- Classic Pivot Point Formula ---
    # Uses the most recent day's High, Low, Close to compute pivot levels
    last_high  = float(df['High'].iloc[-1])   # Highest price of last candle
    last_low   = float(df['Low'].iloc[-1])    # Lowest price of last candle
    last_close = float(df['Close'].iloc[-1])  # Closing price of last candle

    # Pivot Point = average of High, Low, Close
    pivot = (last_high + last_low + last_close) / 3

    # Resistance levels (above current price)
    r1 = (2 * pivot) - last_low         # Resistance 1 (nearest above)
    r2 = pivot + (last_high - last_low)  # Resistance 2
    r3 = last_high + 2 * (pivot - last_low)  # Resistance 3 (furthest above)

    # Support levels (below current price)
    s1 = (2 * pivot) - last_high        # Support 1 (nearest below)
    s2 = pivot - (last_high - last_low)  # Support 2
    s3 = last_low - 2 * (last_high - pivot)  # Support 3 (furthest below)

    # --- Swing High / Swing Low Detection ---
    # A swing high = a candle whose high is higher than the 2 candles before AND after it
    # This finds natural price "peaks" and "valleys"
    highs = df['High'].values
    lows  = df['Low'].values
    swing_highs = []
    swing_lows  = []

    # Look at each candle (skip first 2 and last 2 to compare neighbors)
    for i in range(2, len(df) - 2):
        # Swing High: this bar's high is greater than surrounding bars
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])

        # Swing Low: this bar's low is less than surrounding bars
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])

    # --- Display Results ---
    print()
    print(f"  SUPPORT & RESISTANCE LEVELS FOR: {symbol}")
    print(f"  Current Price: {last_close:.2f}")
    print("-" * 50)

    # Build a table of levels
    levels = [
        ["R3 (Strong Resistance)", f"{r3:.2f}", "RESISTANCE"],
        ["R2 (Resistance)",        f"{r2:.2f}", "RESISTANCE"],
        ["R1 (Nearest Resistance)",f"{r1:.2f}", "RESISTANCE"],
        ["PIVOT",                  f"{pivot:.2f}", "PIVOT"],
        ["S1 (Nearest Support)",   f"{s1:.2f}", "SUPPORT"],
        ["S2 (Support)",           f"{s2:.2f}", "SUPPORT"],
        ["S3 (Strong Support)",    f"{s3:.2f}", "SUPPORT"],
    ]

    # Print the table using tabulate
    print(tabulate(levels, headers=["Level", "Price", "Type"],
                   tablefmt='rounded_outline'))

    # Show swing levels found
    print()
    if swing_highs:
        print(f"  Top 3 Swing Highs (recent): {sorted(swing_highs, reverse=True)[:3]}")
    if swing_lows:
        print(f"  Top 3 Swing Lows  (recent): {sorted(swing_lows)[:3]}")

    # --- Plot Chart ---
    print()
    print("  Generating chart...")

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle(f"Support & Resistance: {symbol}", fontsize=14, fontweight='bold')

    # Plot closing price as a line
    ax.plot(df.index, df['Close'], color='#2196F3', linewidth=1.5, label='Close Price')

    # Plot each level as a horizontal dashed line
    colors_map = {"RESISTANCE": "red", "PIVOT": "orange", "SUPPORT": "green"}
    for label, price_str, level_type in levels:
        ax.axhline(y=float(price_str), color=colors_map[level_type],
                   linestyle='--', linewidth=0.8, alpha=0.7)
        ax.text(df.index[0], float(price_str), f" {label} ({price_str})",
                color=colors_map[level_type], fontsize=7, va='bottom')

    ax.set_ylabel("Price")
    ax.set_xlabel("Date")
    ax.legend()
    plt.tight_layout()
    plt.savefig("support_resistance.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Chart saved as 'support_resistance.png'")

    press_enter_to_continue()


# =============================================================================
# TOOL 3: SECTOR ROTATION TRACKER
# =============================================================================

def tool_3_sector_rotation():
    """
    Compares the performance of multiple sector ETFs / indices.
    Shows which sectors are gaining and which are losing.
    Helps identify where money is "rotating" in the market.
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 3: SECTOR ROTATION TRACKER")
    print("=" * 60)
    print("  Compares sector performance over different periods.")
    print("  Uses US sector ETFs as a proxy (works globally).")
    print()

    # US Sector ETFs (from SPDR) - universally recognized
    # Each is a fund that tracks one sector of the economy
    sectors = {
        "Technology":    "XLK",   # Tech companies (Apple, Microsoft, etc.)
        "Healthcare":    "XLV",   # Pharma, hospitals, biotech
        "Financials":    "XLF",   # Banks, insurance, investment firms
        "Energy":        "XLE",   # Oil, gas, renewable energy
        "Consumer Disc": "XLY",   # Cars, retail, restaurants (discretionary spending)
        "Consumer Stpl": "XLP",   # Food, beverages, household products (staples)
        "Industrials":   "XLI",   # Manufacturing, aerospace, defense
        "Materials":     "XLB",   # Mining, chemicals, packaging
        "Utilities":     "XLU",   # Electric, water, gas utilities
        "Real Estate":   "XLRE",  # REITs and real estate companies
        "Communication": "XLC",   # Telecom, media, social media
    }

    print("  Downloading sector data...")

    # Time periods to compare performance (in trading days)
    periods_to_compare = {
        "1W":  5,    # 1 week = ~5 trading days
        "1M":  21,   # 1 month = ~21 trading days
        "3M":  63,   # 3 months = ~63 trading days
        "6M":  126,  # 6 months = ~126 trading days
        "1Y":  252,  # 1 year = ~252 trading days
    }

    results = []  # Collect sector performance data here

    for sector_name, ticker in sectors.items():
        # Download 1 year of data for each sector ETF
        df = download_data(ticker, period="1y", interval="1d")
        if df is None or len(df) < 10:
            continue  # Skip if not enough data

        close = df['Close']  # Get closing prices

        row = {"Sector": sector_name, "Ticker": ticker}

        # Calculate % return for each time period
        for period_label, days in periods_to_compare.items():
            if len(close) > days:
                # Return = (current price - price N days ago) / price N days ago * 100
                past_price    = float(close.iloc[-days - 1])
                current_price = float(close.iloc[-1])
                pct_return    = ((current_price - past_price) / past_price) * 100
                row[period_label] = f"{pct_return:+.2f}%"  # +/- sign prefix
            else:
                row[period_label] = "N/A"

        results.append(row)

    # --- Display Results ---
    print()
    print("  SECTOR PERFORMANCE COMPARISON")
    print("-" * 70)
    if results:
        df_results = pd.DataFrame(results)
        print(tabulate(df_results, headers='keys', tablefmt='rounded_outline', showindex=False))

    print()
    print("  TIP: Money flowing INTO strong sectors = Sector Rotation in action.")
    print("       Defensive sectors (Utilities, Staples) rise before market downturns.")
    print("       Cyclical sectors (Tech, Consumer Disc) rise in bull markets.")

    press_enter_to_continue()


# =============================================================================
# TOOL 4: RELATIVE STRENGTH RANKER
# =============================================================================

def tool_4_relative_strength():
    """
    Ranks a list of stocks by their Relative Strength (RS).
    RS compares how a stock performed vs a benchmark (e.g. Nifty 50).
    RS > 1.0 means the stock beat the benchmark (outperformer).
    RS < 1.0 means the stock lagged the benchmark (underperformer).
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 4: RELATIVE STRENGTH RANKER")
    print("=" * 60)
    print("  Ranks stocks by performance vs a benchmark index.")
    print("  RS > 1.0 = outperforming the market (BUY candidate)")
    print("  RS < 1.0 = underperforming the market (avoid/sell)")
    print()

    # Ask for the benchmark symbol
    print("  Common benchmarks:")
    print("    ^NSEI  = Nifty 50 (Indian market)")
    print("    ^BSESN = BSE Sensex (Indian market)")
    print("    ^GSPC  = S&P 500 (US market)")
    print()
    benchmark = input("  Enter benchmark symbol (default: ^NSEI): ").strip().upper()
    if not benchmark:
        benchmark = "^NSEI"  # Default to Nifty 50

    # Ask for stock symbols (user can type multiple, comma-separated)
    print()
    print("  Enter up to 10 stock symbols separated by commas.")
    print("  Example: RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS")
    raw = input("  Symbols: ").strip().upper()

    # Split by comma and clean each symbol
    symbols = [s.strip() for s in raw.split(",") if s.strip()]
    if not symbols:
        print("  No symbols entered.")
        press_enter_to_continue()
        return

    # Download benchmark data (Nifty 50)
    print()
    print(f"  Downloading benchmark: {benchmark}")
    bench_df = download_data(benchmark, period="1y", interval="1d")
    if bench_df is None:
        press_enter_to_continue()
        return

    # Calculate benchmark's 1-year return
    bench_close = bench_df['Close']
    bench_return = float(bench_close.iloc[-1]) / float(bench_close.iloc[0])  # ratio

    results = []  # Store results for each stock

    for symbol in symbols:
        df = download_data(symbol, period="1y", interval="1d")
        if df is None:
            continue

        close = df['Close']
        if len(close) < 2:
            continue

        # Stock's 1-year return (as a ratio)
        stock_return = float(close.iloc[-1]) / float(close.iloc[0])

        # Relative Strength = stock return / benchmark return
        # RS > 1 means stock grew MORE than the benchmark
        rs = stock_return / bench_return

        # Calculate RSI for additional signal
        rsi_val = float(calculate_rsi(close).iloc[-1])

        results.append({
            "Symbol":         symbol,
            "Current Price":  f"{float(close.iloc[-1]):.2f}",
            "1Y Return":      f"{(stock_return - 1) * 100:+.2f}%",
            "RS vs Benchmark":f"{rs:.3f}",
            "RSI (14)":       f"{rsi_val:.1f}",
            "Signal":         "OUTPERFORMER" if rs > 1.05 else ("LAGGARD" if rs < 0.95 else "NEUTRAL")
        })

    # Sort by Relative Strength descending (strongest first)
    results.sort(key=lambda x: float(x["RS vs Benchmark"]), reverse=True)

    # --- Display Results ---
    print()
    print(f"  RELATIVE STRENGTH RANKING vs {benchmark}")
    print("-" * 70)
    if results:
        df_results = pd.DataFrame(results)
        print(tabulate(df_results, headers='keys', tablefmt='rounded_outline', showindex=False))

    print()
    print(f"  Benchmark 1Y Return: {(bench_return - 1) * 100:+.2f}%")

    press_enter_to_continue()


# =============================================================================
# TOOL 5: CORRELATION MATRIX
# =============================================================================

def tool_5_correlation_matrix():
    """
    Creates a correlation matrix showing how stocks move relative to each other.
    Correlation = +1.0 means they move together perfectly (100% related)
    Correlation = -1.0 means they move in opposite directions
    Correlation = 0.0 means they move independently (great for diversification!)
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 5: CORRELATION MATRIX")
    print("=" * 60)
    print("  Shows how stocks move relative to each other.")
    print("  Correlation near +1.0 = move together (no diversification benefit)")
    print("  Correlation near -1.0 = move opposite (hedging benefit)")
    print("  Correlation near  0.0 = independent (best for diversification)")
    print()

    print("  Enter symbols separated by commas (2 to 15 stocks).")
    print("  Example: RELIANCE.NS, TCS.NS, HDFCBANK.NS, INFY.NS, ^NSEI")
    raw = input("  Symbols: ").strip().upper()

    symbols = [s.strip() for s in raw.split(",") if s.strip()]
    if len(symbols) < 2:
        print("  Please enter at least 2 symbols.")
        press_enter_to_continue()
        return

    # Download 1 year of daily close prices for each symbol
    close_data = {}
    for sym in symbols:
        df = download_data(sym, period="1y", interval="1d")
        if df is not None and len(df) > 10:
            close_data[sym] = df['Close']  # Store closing prices

    if len(close_data) < 2:
        print("  Not enough data to compute correlation.")
        press_enter_to_continue()
        return

    # Combine all closing prices into one DataFrame, aligned by date
    combined = pd.DataFrame(close_data)

    # Calculate daily % returns (not prices) for correlation
    # We use returns because two stocks at different price scales need normalization
    returns = combined.pct_change().dropna()

    # Compute correlation matrix - every stock vs every other stock
    corr_matrix = returns.corr()

    # --- Display as a text table ---
    print()
    print("  CORRELATION MATRIX (based on daily returns, last 1 year)")
    print("-" * 60)
    # Round to 2 decimal places for clean display
    print(tabulate(corr_matrix.round(2), headers='keys', tablefmt='rounded_outline'))

    # --- Plot as a heatmap ---
    print()
    print("  Generating heatmap...")

    fig, ax = plt.subplots(figsize=(max(6, len(symbols)), max(5, len(symbols) - 1)))
    fig.suptitle("Correlation Matrix (Daily Returns)", fontsize=13, fontweight='bold')

    # seaborn heatmap: annot=True shows numbers inside each cell
    # cmap='RdYlGn' = Red for negative, Yellow for neutral, Green for positive
    sns.heatmap(
        corr_matrix,
        annot=True,          # Show correlation numbers inside each cell
        fmt=".2f",           # Format to 2 decimal places
        cmap='RdYlGn',       # Red-Yellow-Green colormap
        center=0,            # Center the colormap at 0
        vmin=-1, vmax=1,     # Min and max of color scale
        ax=ax,
        linewidths=0.5       # Grid lines between cells
    )

    plt.tight_layout()
    plt.savefig("correlation_matrix.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Heatmap saved as 'correlation_matrix.png'")

    print()
    print("  INTERPRETATION GUIDE:")
    print("  Green (near +1.0) = Strong positive correlation (move together)")
    print("  Red   (near -1.0) = Strong negative correlation (move opposite)")
    print("  White (near  0.0) = No correlation (good diversification)")

    press_enter_to_continue()


# =============================================================================
# TOOL 6: MARKET BREADTH DASHBOARD
# =============================================================================

def tool_6_market_breadth():
    """
    Market Breadth measures the health of the overall market by checking
    how many stocks are advancing vs declining, and how many are above
    their moving averages. Strong breadth = healthy broad rally.
    Weak breadth with rising index = warning sign (narrow rally).
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 6: MARKET BREADTH DASHBOARD")
    print("=" * 60)
    print("  Measures overall market health.")
    print("  Strong breadth = most stocks rising (healthy market)")
    print("  Weak breadth = only a few stocks carry the index (risky)")
    print()

    # A representative set of Nifty 50 stocks
    # We'll analyze these as a proxy for the broader Indian market
    print("  Using a sample of 20 Nifty 50 stocks for breadth analysis...")

    nifty_sample = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
        "ICICIBANK.NS", "KOTAKBANK.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "AXISBANK.NS",
        "SBIN.NS", "TITAN.NS", "WIPRO.NS", "TECHM.NS", "HCLTECH.NS",
        "MARUTI.NS", "ULTRACEMCO.NS", "SUNPHARMA.NS", "POWERGRID.NS", "NTPC.NS"
    ]

    advancing   = 0   # Count of stocks above their 20-day SMA
    declining   = 0   # Count of stocks below their 20-day SMA
    above_50sma = 0   # Count of stocks above their 50-day SMA
    above_200sma= 0   # Count of stocks above their 200-day SMA
    new_highs   = 0   # Stocks at 52-week high
    new_lows    = 0   # Stocks at 52-week low
    total       = 0   # Total stocks successfully processed

    for sym in nifty_sample:
        df = download_data(sym, period="1y", interval="1d")
        if df is None or len(df) < 50:
            continue

        close = df['Close']
        latest = float(close.iloc[-1])

        # Check moving averages
        sma20  = float(close.rolling(20).mean().iloc[-1])
        sma50  = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

        # 52-week high and low
        high_52w = float(close.max())
        low_52w  = float(close.min())

        # Count breadth metrics
        if latest > sma20:
            advancing += 1
        else:
            declining += 1

        if latest > sma50:
            above_50sma += 1

        if sma200 and latest > sma200:
            above_200sma += 1

        # Within 2% of 52-week high = new high zone
        if latest >= high_52w * 0.98:
            new_highs += 1

        # Within 2% of 52-week low = new low zone
        if latest <= low_52w * 1.02:
            new_lows += 1

        total += 1

    # --- Display Dashboard ---
    print()
    print(f"  MARKET BREADTH DASHBOARD ({total} stocks analyzed)")
    print("=" * 55)

    if total > 0:
        # Calculate percentages
        pct_advance    = (advancing / total) * 100
        pct_above50    = (above_50sma / total) * 100
        pct_above200   = (above_200sma / total) * 100
        ad_ratio       = advancing / declining if declining > 0 else float('inf')

        breadth_data = [
            ["Advancing (above 20 SMA)",  advancing,    f"{pct_advance:.1f}%"],
            ["Declining (below 20 SMA)",  declining,    f"{100 - pct_advance:.1f}%"],
            ["Above 50-day SMA",          above_50sma,  f"{pct_above50:.1f}%"],
            ["Above 200-day SMA",         above_200sma, f"{pct_above200:.1f}%"],
            ["Near 52-Week Highs",        new_highs,    f"{(new_highs/total)*100:.1f}%"],
            ["Near 52-Week Lows",         new_lows,     f"{(new_lows/total)*100:.1f}%"],
            ["Advance/Decline Ratio",     f"{ad_ratio:.2f}", "(>1.5 = healthy)"],
        ]

        print(tabulate(breadth_data, headers=["Metric", "Count", "Percentage"],
                       tablefmt='rounded_outline'))

        print()
        # Overall breadth interpretation
        if pct_advance >= 70:
            print("  *** STRONG BREADTH: Broad-based rally. Market is healthy. ***")
        elif pct_advance >= 50:
            print("  >>  MODERATE BREADTH: Mixed market. Some strength, some weakness.")
        else:
            print("  !!! WEAK BREADTH: Most stocks falling. Be cautious. !!!")

        if above_50sma >= total * 0.7:
            print("  Majority of stocks above 50 SMA = Medium-term trend is UP.")
        elif above_50sma <= total * 0.3:
            print("  Most stocks below 50 SMA = Medium-term trend is DOWN.")

    press_enter_to_continue()


# =============================================================================
# TOOL 7: POSITION SIZING CALCULATOR
# =============================================================================

def tool_7_position_sizing():
    """
    Calculates how many shares/units to buy based on your risk tolerance.
    Uses the "% Risk per trade" method - the most professional approach.
    You decide: if this trade goes wrong and hits stop loss, how much money are you OK losing?
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 7: POSITION SIZING CALCULATOR")
    print("=" * 60)
    print("  Calculates the right number of shares to buy")
    print("  so you never risk more than you're comfortable with.")
    print()
    print("  FORMULA: Position Size = Amount Risked / Risk Per Share")
    print("  Risk Per Share = Entry Price - Stop Loss Price")
    print()

    try:
        # Get user inputs
        account_size  = float(input("  Total account capital (₹): "))
        risk_pct      = float(input("  Max risk per trade (% of capital, e.g. 1): "))
        entry_price   = float(input("  Entry price per share (₹): "))
        stop_loss     = float(input("  Stop loss price per share (₹): "))
        target_price  = float(input("  Target price per share (₹, press Enter to skip): ") or 0)

    except ValueError:
        print("  Invalid input. Please enter numbers only.")
        press_enter_to_continue()
        return

    # --- Calculations ---
    # Maximum money you're willing to lose on this trade
    amount_to_risk = account_size * (risk_pct / 100)

    # Risk per share = how much you lose if stop loss is hit
    risk_per_share = entry_price - stop_loss

    if risk_per_share <= 0:
        print("  ERROR: Stop loss must be BELOW entry price for a long trade.")
        press_enter_to_continue()
        return

    # Number of shares = amount willing to risk / risk per share
    num_shares = amount_to_risk / risk_per_share

    # Round down to whole shares (you can't buy 23.7 shares)
    num_shares = int(num_shares)

    # Total capital needed for this position
    total_investment = num_shares * entry_price

    # Percentage of portfolio this trade uses
    portfolio_pct = (total_investment / account_size) * 100

    # Reward/Risk ratio (only if target is provided)
    if target_price > 0:
        reward_per_share = target_price - entry_price
        rr_ratio = reward_per_share / risk_per_share
        potential_profit = reward_per_share * num_shares
    else:
        rr_ratio = None
        potential_profit = None

    # --- Display Results ---
    print()
    print("  POSITION SIZING RESULTS")
    print("=" * 55)

    results_table = [
        ["Account Size",         f"₹{account_size:,.2f}"],
        ["Risk Per Trade",       f"{risk_pct}%  =  ₹{amount_to_risk:,.2f}"],
        ["Entry Price",          f"₹{entry_price:.2f}"],
        ["Stop Loss",            f"₹{stop_loss:.2f}"],
        ["Risk Per Share",       f"₹{risk_per_share:.2f}"],
        ["---", "---"],
        ["NUMBER OF SHARES",     f"{num_shares} shares"],
        ["Total Investment",     f"₹{total_investment:,.2f}  ({portfolio_pct:.1f}% of portfolio)"],
        ["Max Loss if SL Hit",   f"₹{risk_per_share * num_shares:,.2f}"],
    ]

    if rr_ratio is not None:
        results_table.append(["Target Price",      f"₹{target_price:.2f}"])
        results_table.append(["Reward:Risk Ratio", f"{rr_ratio:.2f}:1  {'✓ GOOD' if rr_ratio >= 2 else '✗ POOR (aim for 2:1+)'}"])
        results_table.append(["Potential Profit",  f"₹{potential_profit:,.2f}"])

    print(tabulate(results_table, headers=["Parameter", "Value"],
                   tablefmt='rounded_outline'))

    print()
    if portfolio_pct > 20:
        print("  WARNING: This trade uses more than 20% of your portfolio.")
        print("           Consider reducing position size for better risk management.")

    press_enter_to_continue()


# =============================================================================
# TOOL 8: PORTFOLIO RISK DASHBOARD
# =============================================================================

def tool_8_portfolio_risk():
    """
    Analyzes a portfolio of stocks to show:
    - Individual stock returns and volatility
    - Portfolio-level return (weighted average)
    - Value at Risk (VaR): worst expected daily loss 95% of the time
    - Portfolio volatility vs individual stocks
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 8: PORTFOLIO RISK DASHBOARD")
    print("=" * 60)
    print("  Analyzes your portfolio's overall risk and return.")
    print()
    print("  Enter your portfolio holdings.")
    print("  Format: Enter one stock at a time. Press Enter with no symbol to finish.")
    print()

    holdings = {}  # Dictionary: symbol -> invested amount

    # Collect user's portfolio
    while True:
        sym = input(f"  Stock symbol {len(holdings)+1} (or press Enter to finish): ").strip().upper()
        if not sym:
            break  # User pressed Enter with no input = done

        try:
            amount = float(input(f"    Investment amount in {sym} (₹): "))
            holdings[sym] = amount
        except ValueError:
            print("  Please enter a number.")

    if len(holdings) < 2:
        print("  Please enter at least 2 holdings for a portfolio analysis.")
        press_enter_to_continue()
        return

    total_portfolio_value = sum(holdings.values())  # Total money invested

    # Download 1 year of data for each stock and calculate stats
    close_data = {}
    stock_stats = []

    for sym, invested in holdings.items():
        df = download_data(sym, period="1y", interval="1d")
        if df is None:
            continue

        close = df['Close']
        close_data[sym] = close

        # Daily returns (% change each day)
        daily_returns = close.pct_change().dropna()

        # Annualized return: average daily return * 252 trading days
        annual_return = daily_returns.mean() * 252 * 100

        # Annualized volatility (std deviation of daily returns * sqrt(252))
        annual_vol = daily_returns.std() * (252 ** 0.5) * 100

        # Weight = this stock's investment as fraction of total portfolio
        weight = invested / total_portfolio_value

        stock_stats.append({
            "Symbol":     sym,
            "Invested":   f"₹{invested:,.0f}",
            "Weight":     f"{weight*100:.1f}%",
            "Annual Return": f"{annual_return:+.2f}%",
            "Annual Vol":    f"{annual_vol:.2f}%",
        })

    # --- Portfolio-Level Metrics ---
    # Combine all close prices aligned by date
    if len(close_data) < 2:
        print("\n  ERROR: Not enough valid data downloaded.")
        print("  Tip: Use .NS suffix for NSE stocks (e.g. ITC.NS, RELIANCE.NS)")
        press_enter_to_continue()
        return

    combined = pd.DataFrame(close_data)
    port_returns = combined.pct_change().dropna()

    # Portfolio weights as a list, in the same order as columns
    weights_list = []
    for sym in combined.columns:
        w = holdings.get(sym, 0) / total_portfolio_value
        weights_list.append(w)
    weights_array = np.array(weights_list)

    # Weighted portfolio daily return
    port_daily_returns = port_returns.dot(weights_array)

    # Portfolio stats
    port_annual_return = port_daily_returns.mean() * 252 * 100
    port_annual_vol    = port_daily_returns.std() * (252 ** 0.5) * 100

    # Value at Risk (VaR) at 95% confidence level
    # This means: on 95% of days, you won't lose more than this amount
    var_95 = np.percentile(port_daily_returns, 5)  # 5th percentile of daily returns
    var_amount = abs(var_95) * total_portfolio_value

    # --- Display Results ---
    print()
    print("  INDIVIDUAL STOCK ANALYSIS")
    print("-" * 60)
    if stock_stats:
        print(tabulate(pd.DataFrame(stock_stats), headers='keys',
                       tablefmt='rounded_outline', showindex=False))

    print()
    print("  PORTFOLIO SUMMARY")
    print("=" * 55)

    summary = [
        ["Total Portfolio Value",   f"₹{total_portfolio_value:,.2f}"],
        ["Portfolio Annual Return", f"{port_annual_return:+.2f}%"],
        ["Portfolio Volatility",    f"{port_annual_vol:.2f}%"],
        ["Value at Risk (95% VaR)", f"₹{var_amount:,.2f} per day"],
        ["VaR Interpretation",      f"95% of days, loss < ₹{var_amount:,.0f}"],
    ]

    print(tabulate(summary, headers=["Metric", "Value"], tablefmt='rounded_outline'))

    press_enter_to_continue()


# =============================================================================
# TOOL 9: TRADE JOURNAL WITH ANALYTICS
# =============================================================================

# File where trades are saved (so they persist between sessions)
JOURNAL_FILE = "trade_journal.json"

def load_trades():
    """Loads saved trades from a JSON file. Returns empty list if file doesn't exist."""
    if os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, 'r') as f:
            return json.load(f)  # Read JSON file and convert to Python list
    return []  # Return empty list if no file exists yet

def save_trades(trades):
    """Saves the list of trades to a JSON file."""
    with open(JOURNAL_FILE, 'w') as f:
        json.dump(trades, f, indent=2)  # Save as formatted JSON
    print(f"  Trades saved to '{JOURNAL_FILE}'")

def tool_9_trade_journal():
    """
    A simple trade journal where you log your trades (buy/sell).
    Tracks profit/loss, win rate, average return per trade, and more.
    All data is saved to a file so it persists between sessions.
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 9: TRADE JOURNAL WITH ANALYTICS")
    print("=" * 60)

    trades = load_trades()  # Load existing trades from file

    while True:
        print()
        print("  OPTIONS:")
        print("  1. Add a new trade")
        print("  2. View all trades")
        print("  3. View analytics")
        print("  4. Delete a trade")
        print("  5. Back to main menu")
        print()
        choice = input("  Choose (1-5): ").strip()

        if choice == "1":
            # --- Add new trade ---
            print()
            try:
                symbol    = input("  Symbol (e.g. RELIANCE.NS): ").strip().upper()
                direction = input("  Direction (LONG/SHORT): ").strip().upper()
                entry     = float(input("  Entry price: "))
                exit_p    = float(input("  Exit price (0 if still open): "))
                qty       = float(input("  Quantity (shares): "))
                date_in   = input("  Entry date (YYYY-MM-DD or press Enter for today): ").strip()
                notes     = input("  Notes (optional): ").strip()

                if not date_in:
                    date_in = datetime.today().strftime('%Y-%m-%d')

                # Calculate P&L
                if direction == "LONG":
                    pnl = (exit_p - entry) * qty if exit_p > 0 else None
                else:  # SHORT trade
                    pnl = (entry - exit_p) * qty if exit_p > 0 else None

                # Create trade record as a dictionary
                trade = {
                    "id":        len(trades) + 1,
                    "symbol":    symbol,
                    "direction": direction,
                    "entry":     entry,
                    "exit":      exit_p,
                    "qty":       qty,
                    "date":      date_in,
                    "pnl":       round(pnl, 2) if pnl is not None else None,
                    "status":    "CLOSED" if exit_p > 0 else "OPEN",
                    "notes":     notes,
                }

                trades.append(trade)
                save_trades(trades)
                print(f"  Trade added! P&L: ₹{pnl:+,.2f}" if pnl else "  Trade added as OPEN.")

            except ValueError:
                print("  Invalid input. Please enter numbers for prices and quantity.")

        elif choice == "2":
            # --- View all trades ---
            print()
            if not trades:
                print("  No trades recorded yet.")
            else:
                display_trades = []
                for t in trades:
                    display_trades.append({
                        "ID":        t["id"],
                        "Date":      t["date"],
                        "Symbol":    t["symbol"],
                        "Direction": t["direction"],
                        "Entry":     f"₹{t['entry']:.2f}",
                        "Exit":      f"₹{t['exit']:.2f}" if t['exit'] > 0 else "OPEN",
                        "Qty":       t["qty"],
                        "P&L":       f"₹{t['pnl']:+,.2f}" if t['pnl'] else "Open",
                        "Status":    t["status"],
                    })
                print(tabulate(pd.DataFrame(display_trades), headers='keys',
                               tablefmt='rounded_outline', showindex=False))

        elif choice == "3":
            # --- Analytics ---
            print()
            closed_trades = [t for t in trades if t['status'] == 'CLOSED' and t['pnl'] is not None]

            if len(closed_trades) < 1:
                print("  No closed trades to analyze yet.")
                continue

            pnls        = [t['pnl'] for t in closed_trades]
            winners     = [p for p in pnls if p > 0]
            losers      = [p for p in pnls if p < 0]
            total_pnl   = sum(pnls)
            win_rate    = (len(winners) / len(pnls)) * 100 if pnls else 0
            avg_win     = sum(winners) / len(winners) if winners else 0
            avg_loss    = sum(losers)  / len(losers)  if losers  else 0
            profit_factor = abs(sum(winners) / sum(losers)) if sum(losers) != 0 else float('inf')

            analytics = [
                ["Total Trades",       len(pnls)],
                ["Winning Trades",     len(winners)],
                ["Losing Trades",      len(losers)],
                ["Win Rate",           f"{win_rate:.1f}%"],
                ["Total P&L",          f"₹{total_pnl:+,.2f}"],
                ["Average Win",        f"₹{avg_win:+,.2f}"],
                ["Average Loss",       f"₹{avg_loss:+,.2f}"],
                ["Profit Factor",      f"{profit_factor:.2f}  (>1.5 is good)"],
                ["Best Trade",         f"₹{max(pnls):+,.2f}"],
                ["Worst Trade",        f"₹{min(pnls):+,.2f}"],
            ]

            print("  TRADE ANALYTICS")
            print(tabulate(analytics, headers=["Metric", "Value"], tablefmt='rounded_outline'))

        elif choice == "4":
            # --- Delete a trade ---
            trade_id = input("  Enter trade ID to delete: ").strip()
            trades = [t for t in trades if str(t['id']) != trade_id]
            save_trades(trades)
            print(f"  Trade {trade_id} deleted.")

        elif choice == "5":
            break  # Return to main menu

        else:
            print("  Invalid choice.")


# =============================================================================
# TOOL 10: MONTE CARLO SIMULATOR
# =============================================================================

def tool_10_monte_carlo():
    """
    Monte Carlo Simulation: Simulates thousands of possible future price paths
    using random sampling based on a stock's historical return and volatility.
    Gives you a range of possible outcomes (best case, worst case, median).
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 10: MONTE CARLO SIMULATOR")
    print("=" * 60)
    print("  Simulates 1000 possible future price paths.")
    print("  Uses historical return and volatility as inputs.")
    print("  Helps estimate probability of reaching your target.")
    print()

    symbol = get_symbol_input("  Enter stock symbol (e.g. TCS.NS): ")

    # Download historical data
    df = download_data(symbol, period="2y", interval="1d")
    if df is None:
        press_enter_to_continue()
        return

    close = df['Close']

    try:
        # How many days into the future to simulate
        days_ahead = int(input("  Forecast horizon in trading days (e.g. 252 = 1 year): "))
        num_simulations = 1000  # Number of simulation paths to run
    except ValueError:
        print("  Invalid input.")
        press_enter_to_continue()
        return

    # Calculate historical daily return statistics
    daily_returns = close.pct_change().dropna()
    mu    = daily_returns.mean()     # Average daily return
    sigma = daily_returns.std()      # Daily volatility (standard deviation)

    current_price = float(close.iloc[-1])  # Starting price for simulations

    print(f"\n  Historical daily return: {mu*100:.4f}%")
    print(f"  Historical daily volatility: {sigma*100:.4f}%")
    print(f"  Running {num_simulations} simulations for {days_ahead} days...")

    # --- Run Simulations ---
    # Each simulation is one possible price path
    simulation_results = np.zeros((days_ahead, num_simulations))

    for sim in range(num_simulations):
        prices = [current_price]  # Start at current price

        for day in range(days_ahead - 1):
            # Geometric Brownian Motion formula:
            # Next price = Current price * e^((mu - sigma^2/2)*dt + sigma*Z)
            # where Z is a random number from a normal distribution
            random_shock = np.random.normal(0, 1)  # Random daily shock
            daily_return = np.exp((mu - 0.5 * sigma**2) + sigma * random_shock)
            next_price = prices[-1] * daily_return
            prices.append(next_price)

        simulation_results[:, sim] = prices  # Store this simulation's path

    # Final prices after all days
    final_prices = simulation_results[-1, :]

    # --- Statistics on outcomes ---
    percentile_5  = np.percentile(final_prices, 5)   # Worst 5% scenario
    percentile_25 = np.percentile(final_prices, 25)  # 25th percentile
    percentile_50 = np.percentile(final_prices, 50)  # Median (most likely)
    percentile_75 = np.percentile(final_prices, 75)  # 75th percentile
    percentile_95 = np.percentile(final_prices, 95)  # Best 5% scenario

    print()
    print(f"  MONTE CARLO RESULTS FOR: {symbol}")
    print(f"  Starting Price: ₹{current_price:.2f}  |  Forecast: {days_ahead} days")
    print("=" * 55)

    mc_table = [
        ["Worst Case (5th %ile)",  f"₹{percentile_5:.2f}",  f"{((percentile_5/current_price)-1)*100:+.1f}%"],
        ["Bear Case  (25th %ile)", f"₹{percentile_25:.2f}", f"{((percentile_25/current_price)-1)*100:+.1f}%"],
        ["Base Case  (Median)",    f"₹{percentile_50:.2f}", f"{((percentile_50/current_price)-1)*100:+.1f}%"],
        ["Bull Case  (75th %ile)", f"₹{percentile_75:.2f}", f"{((percentile_75/current_price)-1)*100:+.1f}%"],
        ["Best Case  (95th %ile)", f"₹{percentile_95:.2f}", f"{((percentile_95/current_price)-1)*100:+.1f}%"],
    ]

    print(tabulate(mc_table, headers=["Scenario", "Price", "Return"],
                   tablefmt='rounded_outline'))

    # Probability of gain
    prob_profit = (final_prices > current_price).mean() * 100
    print(f"\n  Probability of profit after {days_ahead} days: {prob_profit:.1f}%")

    # --- Plot Simulations ---
    print("\n  Generating Monte Carlo chart...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Monte Carlo Simulation: {symbol} ({days_ahead} days, {num_simulations} runs)",
                 fontsize=12, fontweight='bold')

    # Left chart: simulation paths (show only 200 to avoid clutter)
    for i in range(min(200, num_simulations)):
        ax1.plot(simulation_results[:, i], alpha=0.05, color='#2196F3', linewidth=0.5)

    # Add percentile lines on top
    ax1.plot(np.percentile(simulation_results, 5, axis=1),  color='red',    linewidth=2, label='5th %ile')
    ax1.plot(np.percentile(simulation_results, 50, axis=1), color='orange', linewidth=2, label='Median')
    ax1.plot(np.percentile(simulation_results, 95, axis=1), color='green',  linewidth=2, label='95th %ile')
    ax1.axhline(current_price, color='black', linestyle='--', linewidth=1, label='Current Price')
    ax1.set_title("Price Paths")
    ax1.set_ylabel("Price (₹)")
    ax1.set_xlabel("Days")
    ax1.legend(fontsize=8)

    # Right chart: distribution of final prices
    ax2.hist(final_prices, bins=50, color='#2196F3', edgecolor='white', alpha=0.8)
    ax2.axvline(current_price, color='black', linestyle='--', linewidth=2, label='Current')
    ax2.axvline(percentile_5,  color='red',   linestyle='--', linewidth=1.5, label='5th %ile')
    ax2.axvline(percentile_50, color='orange',linestyle='--', linewidth=1.5, label='Median')
    ax2.axvline(percentile_95, color='green', linestyle='--', linewidth=1.5, label='95th %ile')
    ax2.set_title("Distribution of Final Prices")
    ax2.set_xlabel("Price (₹)")
    ax2.set_ylabel("Frequency")
    ax2.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig("monte_carlo.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Chart saved as 'monte_carlo.png'")

    press_enter_to_continue()


# =============================================================================
# TOOL 11: RISK OF RUIN CALCULATOR
# =============================================================================

def tool_11_risk_of_ruin():
    """
    Risk of Ruin calculates the probability that you will blow up your
    trading account (lose a defined % of capital you can't recover from).
    It depends on: win rate, reward:risk ratio, and % risked per trade.

    Formula: Risk of Ruin ≈ ((1 - Edge) / (1 + Edge)) ^ (Capital / Risk Per Trade)
    where Edge = win_rate - (1 - win_rate) / RR_ratio
    """
    clear_screen()
    print("=" * 60)
    print("  TOOL 11: RISK OF RUIN CALCULATOR")
    print("=" * 60)
    print("  Estimates the probability of losing all (or most) of")
    print("  your trading capital based on your strategy stats.")
    print()
    print("  KEY INSIGHT: Even a profitable strategy can 'ruin' you")
    print("  if you risk too much per trade!")
    print()

    try:
        win_rate       = float(input("  Your win rate % (e.g. 55): ")) / 100  # Convert to decimal
        rr_ratio       = float(input("  Reward:Risk ratio (e.g. 2 means 2:1): "))
        risk_per_trade = float(input("  % of capital risked per trade (e.g. 2): ")) / 100
        ruin_threshold = float(input("  Ruin threshold % (e.g. 50 = lose 50% of account): ")) / 100

    except ValueError:
        print("  Invalid input.")
        press_enter_to_continue()
        return

    # --- Calculate Trader's Edge ---
    # Edge = expected value per trade (positive = profitable strategy)
    loss_rate = 1 - win_rate
    edge = (win_rate * rr_ratio - loss_rate)  # Expected R per trade

    print()
    print(f"  Your Trading Edge: {edge:.4f} ({edge*100:.2f}% per trade)")

    if edge <= 0:
        print("  WARNING: Your strategy has NEGATIVE edge. Risk of ruin is near 100%.")
        print("  Improve your win rate or increase your reward:risk ratio first.")
        press_enter_to_continue()
        return

    # --- Risk of Ruin using simulation (Monte Carlo approach) ---
    # We simulate 10,000 trading sequences and count how many blow up
    num_simulations  = 10000    # Number of trading sequences to simulate
    num_trades       = 1000     # Max trades per simulation

    # How many trades does it take to recover from ruin threshold?
    ruin_count = 0  # Count how many simulations ended in ruin

    for _ in range(num_simulations):
        capital = 1.0  # Start with 100% of capital (normalized to 1.0)
        ruined  = False

        for _ in range(num_trades):
            # Randomly decide: was this trade a win or loss?
            # random.random() gives a number between 0 and 1
            if random.random() < win_rate:
                # Win: capital increases by risk_per_trade * rr_ratio
                capital += risk_per_trade * rr_ratio
            else:
                # Loss: capital decreases by risk_per_trade
                capital -= risk_per_trade

            # Check if we've hit the ruin threshold
            if capital <= (1.0 - ruin_threshold):
                ruined = True
                break  # No need to continue this simulation

        if ruined:
            ruin_count += 1

    # Risk of Ruin = fraction of simulations that resulted in ruin
    risk_of_ruin_pct = (ruin_count / num_simulations) * 100

    # --- Show results for different risk levels ---
    print()
    print("  RISK OF RUIN ANALYSIS")
    print("=" * 60)

    ruin_table = [
        ["Win Rate",        f"{win_rate*100:.1f}%"],
        ["Reward:Risk",     f"{rr_ratio:.1f}:1"],
        ["Risk Per Trade",  f"{risk_per_trade*100:.1f}%"],
        ["Ruin Threshold",  f"{ruin_threshold*100:.0f}% drawdown"],
        ["Simulations Run", f"{num_simulations:,}"],
        ["Trading Edge",    f"{edge*100:.2f}% per trade"],
        ["RISK OF RUIN",    f"{risk_of_ruin_pct:.2f}%"],
    ]

    print(tabulate(ruin_table, headers=["Metric", "Value"], tablefmt='rounded_outline'))

    print()
    if risk_of_ruin_pct < 1:
        print("  *** EXCELLENT: Risk of ruin < 1%. Your system is very robust. ***")
    elif risk_of_ruin_pct < 5:
        print("  >>  GOOD: Risk of ruin is manageable. Stay disciplined.")
    elif risk_of_ruin_pct < 20:
        print("  !   WARNING: Moderate risk. Consider reducing position size.")
    else:
        print("  !!! DANGER: High risk of ruin. Reduce your risk per trade immediately!")

    # --- Sensitivity table: how does ruin change with different risk per trade? ---
    print()
    print("  SENSITIVITY: Risk of Ruin at Different Risk-Per-Trade Levels")
    print("-" * 50)

    sensitivity_rows = []
    for risk_pct_test in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        r = risk_pct_test / 100
        ruin_c = 0
        for _ in range(5000):  # Fewer simulations for speed
            cap = 1.0
            for _ in range(num_trades):
                if random.random() < win_rate:
                    cap += r * rr_ratio
                else:
                    cap -= r
                if cap <= (1.0 - ruin_threshold):
                    ruin_c += 1
                    break
        ruin_pct = (ruin_c / 5000) * 100
        sensitivity_rows.append([f"{risk_pct_test:.1f}%", f"{ruin_pct:.1f}%",
                                  "SAFE" if ruin_pct < 5 else ("CAUTION" if ruin_pct < 20 else "DANGER")])

    print(tabulate(sensitivity_rows, headers=["Risk Per Trade", "Ruin Probability", "Verdict"],
                   tablefmt='rounded_outline'))

    press_enter_to_continue()


# =============================================================================
# MAIN MENU
# =============================================================================

def main_menu():
    """
    Displays the main menu and routes the user to the selected tool.
    Runs in a loop until the user chooses to exit.
    """
    while True:
        clear_screen()
        print()
        print("=" * 65)
        print("       TRADING ANALYSIS & RISK TOOLS SUITE")
        print("       All 11 Tools | Powered by yfinance (free data)")
        print("=" * 65)
        print()
        print("  ── ANALYSIS TOOLS ─────────────────────────────────────")
        print("   1.  Multi-Timeframe Confluence Analyzer")
        print("   2.  Support & Resistance Detector")
        print("   3.  Sector Rotation Tracker")
        print("   4.  Relative Strength Ranker")
        print("   5.  Correlation Matrix")
        print("   6.  Market Breadth Dashboard")
        print()
        print("  ── RISK & PORTFOLIO TOOLS ──────────────────────────────")
        print("   7.  Position Sizing Calculator")
        print("   8.  Portfolio Risk Dashboard")
        print("   9.  Trade Journal with Analytics")
        print("   10. Monte Carlo Simulator")
        print("   11. Risk of Ruin Calculator")
        print()
        print("   0.  Exit")
        print()
        print("=" * 65)

        # Get user's choice
        choice = input("  Select tool (0-11): ").strip()

        # Route to the correct tool based on choice
        if   choice == "1":  tool_1_multi_timeframe_confluence()
        elif choice == "2":  tool_2_support_resistance()
        elif choice == "3":  tool_3_sector_rotation()
        elif choice == "4":  tool_4_relative_strength()
        elif choice == "5":  tool_5_correlation_matrix()
        elif choice == "6":  tool_6_market_breadth()
        elif choice == "7":  tool_7_position_sizing()
        elif choice == "8":  tool_8_portfolio_risk()
        elif choice == "9":  tool_9_trade_journal()
        elif choice == "10": tool_10_monte_carlo()
        elif choice == "11": tool_11_risk_of_ruin()
        elif choice == "0":
            clear_screen()
            print()
            print("  Exiting Trading Suite. Goodbye!")
            print()
            break  # Exit the loop and end the program
        else:
            print("  Invalid choice. Please enter a number from 0 to 11.")
            input("  Press Enter to try again...")


# =============================================================================
# ENTRY POINT
# This block runs when you execute the script directly:  python trading_analysis_suite.py
# It does NOT run if you import this file from another script.
# =============================================================================

if __name__ == "__main__":
    main_menu()