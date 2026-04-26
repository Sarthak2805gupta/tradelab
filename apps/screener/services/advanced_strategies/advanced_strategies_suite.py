# =============================================================================
# ADVANCED STRATEGIES TOOLS SUITE
# All 5 tools combined in one file
#
# TOOLS INCLUDED:
#   1. Pairs Trading Engine
#   2. Statistical Arbitrage
#   3. ML Prediction Model
#   4. Options Strategy Builder
#   5. Supertrend + ATR Strategy
#
# HOW TO INSTALL REQUIRED LIBRARIES (run these in your terminal first):
#   pip install yfinance pandas numpy scipy matplotlib seaborn tabulate
#   pip install scikit-learn statsmodels
#
# HOW TO RUN:
#   python advanced_strategies_suite.py
#
# NSE STOCK FORMAT: Add ".NS" suffix → e.g. RELIANCE.NS, TCS.NS, INFY.NS
# US STOCKS: Just the ticker → AAPL, MSFT, TSLA
# INDICES:   ^NSEI (Nifty50), ^BSESN (Sensex), ^GSPC (S&P500)
# =============================================================================

# --- STANDARD LIBRARY IMPORTS ---
import os                           # For clearing terminal screen
import warnings                     # To suppress harmless warnings
from datetime import datetime       # For timestamps

# --- DATA & MATH LIBRARIES ---
import numpy as np                  # Arrays and mathematical operations
import pandas as pd                 # Data tables (DataFrames)

# --- VISUALIZATION ---
import matplotlib.pyplot as plt     # Charts and graphs
import matplotlib.gridspec as gs    # Advanced chart layout
import seaborn as sns               # Statistical visualization (heatmaps etc.)

# --- STATISTICS ---
from scipy import stats             # Statistical tests (z-score, normality tests)

# --- MACHINE LEARNING ---
# scikit-learn: the most popular Python ML library
from sklearn.ensemble import RandomForestClassifier  # Random Forest model
from sklearn.linear_model import LogisticRegression  # Logistic Regression model
from sklearn.preprocessing import StandardScaler     # Feature normalization
from sklearn.model_selection import train_test_split # Split data into train/test
from sklearn.metrics import (
    accuracy_score,           # % of correct predictions
    classification_report,    # Precision, recall, F1 per class
    confusion_matrix          # Table of correct vs wrong predictions
)

# --- MARKET DATA ---
import yfinance as yf               # Free stock data from Yahoo Finance

# --- FORMATTED OUTPUT ---
from tabulate import tabulate       # Clean ASCII tables in terminal

# Suppress irrelevant warnings (e.g., from pandas or yfinance)
warnings.filterwarnings('ignore')


# =============================================================================
# SHARED HELPER FUNCTIONS
# Used by multiple tools throughout this file
# =============================================================================

def clear_screen():
    """Clears the terminal screen so menus look clean."""
    os.system('cls' if os.name == 'nt' else 'clear')


def press_enter_to_continue():
    """Pauses program and waits for user to press Enter."""
    input("\n  Press Enter to return to menu...")


def download_data(symbol, period="1y", interval="1d"):
    """
    Downloads historical stock price data from Yahoo Finance (free).

    Parameters:
        symbol   : Stock ticker e.g. "RELIANCE.NS", "TCS.NS", "AAPL"
        period   : How far back: "1mo", "3mo", "6mo", "1y", "2y", "5y"
        interval : Candle size: "1d"=daily, "1wk"=weekly, "1h"=hourly

    Returns:
        pandas DataFrame with Open, High, Low, Close, Volume columns
        Returns None if download fails.
    """
    try:
        print(f"    Downloading {symbol}...")
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty:
            print(f"    No data for '{symbol}'. Check symbol name.")
            return None
        # Flatten multi-level column headers (yfinance sometimes creates them)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"    Error downloading {symbol}: {e}")
        return None


def calculate_rsi(close, period=14):
    """
    RSI (Relative Strength Index): 0-100 momentum oscillator.
    > 70 = overbought, < 30 = oversold.
    """
    delta    = close.diff()
    gain     = delta.where(delta > 0, 0)
    loss     = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_atr(df, period=14):
    """
    ATR (Average True Range): measures volatility.
    High ATR = high volatility (bigger price swings).
    """
    hl        = df['High'] - df['Low']                        # High-Low range
    hc        = abs(df['High'] - df['Close'].shift(1))        # High vs prev close
    lc        = abs(df['Low']  - df['Close'].shift(1))        # Low  vs prev close
    true_range = pd.concat([hl, hc, lc], axis=1).max(axis=1) # Largest of three
    return true_range.rolling(period).mean()                  # Rolling average


def calculate_macd(close, fast=12, slow=26, signal=9):
    """MACD trend indicator. Returns (macd_line, signal_line, histogram)."""
    ema_fast    = close.ewm(span=fast,   adjust=False).mean()
    ema_slow    = close.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def get_symbol(prompt="  Enter symbol (e.g. RELIANCE.NS): "):
    """Asks user to enter a stock symbol and returns it uppercased."""
    return input(prompt).strip().upper()


# =============================================================================
# TOOL 1: PAIRS TRADING ENGINE
# =============================================================================

def tool_1_pairs_trading():
    """
    PAIRS TRADING ENGINE

    Pairs Trading is a market-neutral strategy that:
    1. Finds two stocks that historically move together (high correlation)
    2. Calculates the "spread" between them (price ratio or difference)
    3. When the spread diverges abnormally → trade expecting it to revert
       - Spread too HIGH → Short the expensive one, Buy the cheap one
       - Spread too LOW  → Buy the expensive one, Short the cheap one

    Key concepts:
    - Cointegration: two stocks whose prices move together long-term
    - Spread: the difference between the two prices (or their ratio)
    - Z-Score: how many standard deviations the spread is from its mean
      Z > +2 = spread is unusually high → expect reversion → SELL spread
      Z < -2 = spread is unusually low  → expect reversion → BUY spread
    """
    clear_screen()
    print("=" * 65)
    print("  TOOL 1: PAIRS TRADING ENGINE")
    print("=" * 65)
    print()
    print("  CONCEPT: Find 2 correlated stocks. Trade when their")
    print("  price relationship (spread) diverges unusually.")
    print()
    print("  GOOD PAIRS EXAMPLES (same sector):")
    print("  • HDFCBANK.NS  vs  ICICIBANK.NS  (private banks)")
    print("  • TCS.NS       vs  INFY.NS        (IT companies)")
    print("  • RELIANCE.NS  vs  BHARTIARTL.NS  (large cap)")
    print("  • HINDUNILVR.NS vs ITC.NS         (FMCG)")
    print()

    # Get the two stock symbols from user
    sym1 = get_symbol("  Enter Stock 1 symbol: ")
    sym2 = get_symbol("  Enter Stock 2 symbol: ")

    # Download 2 years of daily data for both stocks
    print()
    df1 = download_data(sym1, period="2y", interval="1d")
    df2 = download_data(sym2, period="2y", interval="1d")

    if df1 is None or df2 is None:
        print("  Could not download data. Check symbols and try again.")
        press_enter_to_continue()
        return

    # --- Align both datasets to the same dates ---
    # Both stocks may have slightly different trading days (holidays etc.)
    # We merge on the date index and only keep rows where BOTH have data
    close1 = df1['Close'].rename(sym1)  # Rename column to symbol name
    close2 = df2['Close'].rename(sym2)
    combined = pd.concat([close1, close2], axis=1).dropna()  # Remove rows with NaN

    if len(combined) < 60:
        print("  Not enough overlapping data for pairs analysis (need 60+ days).")
        press_enter_to_continue()
        return

    print(f"  Aligned data: {len(combined)} trading days of common history.")

    # --- Step 1: Correlation Analysis ---
    # How closely do these two stocks move together?
    correlation = combined[sym1].corr(combined[sym2])

    print()
    print(f"  STEP 1: CORRELATION ANALYSIS")
    print(f"  Correlation between {sym1} and {sym2}: {correlation:.4f}")
    if correlation > 0.85:
        print("  ✓ VERY HIGH correlation — excellent pair for trading!")
    elif correlation > 0.70:
        print("  ~ GOOD correlation — acceptable pair.")
    elif correlation > 0.50:
        print("  ~ MODERATE correlation — risky pair, use caution.")
    else:
        print("  ✗ LOW correlation — NOT suitable for pairs trading.")

    # --- Step 2: Cointegration Test (Engle-Granger) ---
    # Correlation alone isn't enough. We need COINTEGRATION:
    # This means the spread between the two is "mean-reverting" (comes back to average)
    # We import statsmodels here (only needed in this tool)
    try:
        from statsmodels.tsa.stattools import coint   # Cointegration test
        coint_stat, p_value, _ = coint(combined[sym1], combined[sym2])
        # p_value < 0.05 means cointegrated (statistically significant)
        cointegrated = p_value < 0.05
        print()
        print(f"  STEP 2: COINTEGRATION TEST (Engle-Granger)")
        print(f"  P-value: {p_value:.4f}  (< 0.05 = cointegrated)")
        print(f"  Result:  {'✓ COINTEGRATED — spread is mean-reverting' if cointegrated else '✗ NOT cointegrated — spread may drift permanently'}")
    except ImportError:
        print("  statsmodels not installed. Run: pip install statsmodels")
        cointegrated = None
        p_value = None

    # --- Step 3: Calculate the Spread ---
    # Spread = price of Stock1 minus a scaled version of Stock2
    # We use linear regression to find the best "hedge ratio"
    # hedge_ratio = how many units of Stock2 to hold per unit of Stock1

    # Simple linear regression: Stock1 = alpha + hedge_ratio * Stock2
    slope, intercept, r_value, _, _ = stats.linregress(
        combined[sym2],   # X = Stock 2 prices
        combined[sym1]    # Y = Stock 1 prices
    )
    hedge_ratio = slope   # This is how many shares of Stock2 per 1 share of Stock1

    # Spread = Stock1 price - (hedge_ratio * Stock2 price)
    spread = combined[sym1] - hedge_ratio * combined[sym2]

    print()
    print(f"  STEP 3: SPREAD CALCULATION")
    print(f"  Hedge Ratio: {hedge_ratio:.4f}")
    print(f"  (Hold 1 share of {sym1} vs {hedge_ratio:.2f} shares of {sym2})")

    # --- Step 4: Z-Score of the Spread ---
    # Z-Score = (current value - mean) / standard deviation
    # Tells us how "unusual" the current spread is
    spread_mean = spread.mean()       # Average spread over the period
    spread_std  = spread.std()        # Standard deviation of spread
    zscore = (spread - spread_mean) / spread_std  # Z-score series

    current_zscore  = float(zscore.iloc[-1])   # Latest z-score
    current_spread  = float(spread.iloc[-1])   # Latest spread value
    current_price1  = float(combined[sym1].iloc[-1])
    current_price2  = float(combined[sym2].iloc[-1])

    # --- Step 5: Generate Trading Signal ---
    # Trading thresholds (standard practice: ±2 for entry, ±0.5 for exit)
    entry_threshold = 2.0   # Enter trade when z-score exceeds this
    exit_threshold  = 0.5   # Exit trade when z-score comes back to this

    if current_zscore > entry_threshold:
        signal      = "SELL SPREAD"
        action_sym1 = f"SHORT {sym1}"     # Stock 1 is expensive relative to Stock 2
        action_sym2 = f"BUY   {sym2}"     # Stock 2 is cheap relative to Stock 1
        signal_desc = f"Spread is {current_zscore:.2f} std devs ABOVE mean → expect fall"
    elif current_zscore < -entry_threshold:
        signal      = "BUY SPREAD"
        action_sym1 = f"BUY   {sym1}"     # Stock 1 is cheap relative to Stock 2
        action_sym2 = f"SHORT {sym2}"     # Stock 2 is expensive relative to Stock 1
        signal_desc = f"Spread is {abs(current_zscore):.2f} std devs BELOW mean → expect rise"
    elif abs(current_zscore) < exit_threshold:
        signal      = "EXIT / FLAT"
        action_sym1 = f"CLOSE {sym1} position"
        action_sym2 = f"CLOSE {sym2} position"
        signal_desc = "Spread has reverted to mean → close any open trades"
    else:
        signal      = "WAIT"
        action_sym1 = "No action"
        action_sym2 = "No action"
        signal_desc = "Spread within normal range — wait for divergence"

    # --- Display Summary ---
    print()
    print("  PAIRS TRADING DASHBOARD")
    print("=" * 65)

    summary = [
        ["Stock 1",             f"{sym1}  @ ₹{current_price1:.2f}"],
        ["Stock 2",             f"{sym2}  @ ₹{current_price2:.2f}"],
        ["Correlation",         f"{correlation:.4f}"],
        ["P-value (Coint.)",    f"{p_value:.4f}" if p_value else "N/A"],
        ["Cointegrated",        "YES ✓" if cointegrated else "NO ✗"],
        ["Hedge Ratio",         f"{hedge_ratio:.4f}"],
        ["Spread Mean",         f"{spread_mean:.4f}"],
        ["Spread Std Dev",      f"{spread_std:.4f}"],
        ["Current Spread",      f"{current_spread:.4f}"],
        ["Current Z-Score",     f"{current_zscore:.4f}"],
        ["─────────────",       "─────────────────────────────────"],
        ["SIGNAL",              signal],
        ["Action on Stock 1",   action_sym1],
        ["Action on Stock 2",   action_sym2],
        ["Reasoning",           signal_desc],
    ]

    print(tabulate(summary, headers=["Metric", "Value"], tablefmt='rounded_outline'))

    # --- Backtesting: Historical signal performance ---
    print()
    print("  BACKTESTING SIGNALS (last 2 years):")

    # Generate historical signals based on z-score
    signals_series   = pd.Series(index=zscore.index, dtype=str)
    in_position      = False       # Track if we're currently in a trade
    trade_returns    = []          # List of returns from each completed trade
    entry_spread_val = None        # Spread value when we entered the trade

    for i in range(len(zscore)):
        z = zscore.iloc[i]
        sp = spread.iloc[i]

        if not in_position:
            if z > entry_threshold:
                in_position      = True
                entry_spread_val = sp
                trade_direction  = -1     # Short spread (expect it to fall)
            elif z < -entry_threshold:
                in_position      = True
                entry_spread_val = sp
                trade_direction  = 1      # Long spread (expect it to rise)

        elif in_position:
            if abs(z) < exit_threshold:
                # Exit: calculate trade return
                exit_spread_val = sp
                trade_return = trade_direction * (exit_spread_val - entry_spread_val)
                trade_returns.append(trade_return)
                in_position = False

    # Calculate backtest stats
    if trade_returns:
        winners    = [r for r in trade_returns if r > 0]
        losers     = [r for r in trade_returns if r <= 0]
        win_rate   = len(winners) / len(trade_returns) * 100
        avg_return = sum(trade_returns) / len(trade_returns)

        backtest_table = [
            ["Total Trades",   len(trade_returns)],
            ["Winning Trades", len(winners)],
            ["Losing Trades",  len(losers)],
            ["Win Rate",       f"{win_rate:.1f}%"],
            ["Avg Return/Trade", f"{avg_return:.4f} (spread units)"],
            ["Best Trade",     f"{max(trade_returns):.4f}"],
            ["Worst Trade",    f"{min(trade_returns):.4f}"],
        ]
        print(tabulate(backtest_table, headers=["Metric", "Value"], tablefmt='rounded_outline'))
    else:
        print("  Not enough signal crossings for backtest in this period.")

    # --- Chart ---
    print()
    print("  Generating pairs trading chart...")

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f"Pairs Trading: {sym1} vs {sym2}", fontsize=13, fontweight='bold')

    # Panel 1: Normalized prices (both stocks scaled to 100 at start)
    norm1 = combined[sym1] / float(combined[sym1].iloc[0]) * 100
    norm2 = combined[sym2] / float(combined[sym2].iloc[0]) * 100
    ax1.plot(combined.index, norm1, label=sym1, color='#2196F3', linewidth=1.5)
    ax1.plot(combined.index, norm2, label=sym2, color='#FF9800', linewidth=1.5)
    ax1.set_title("Normalized Price (Base=100)")
    ax1.legend()
    ax1.grid(alpha=0.3)

    # Panel 2: Spread
    ax2.plot(combined.index, spread, color='#9C27B0', linewidth=1.2, label='Spread')
    ax2.axhline(spread_mean, color='black', linestyle='--', linewidth=1, label='Mean')
    ax2.axhline(spread_mean + 2*spread_std, color='red',   linestyle='--', linewidth=0.8, label='+2σ')
    ax2.axhline(spread_mean - 2*spread_std, color='green', linestyle='--', linewidth=0.8, label='-2σ')
    ax2.set_title("Spread (Stock1 - HedgeRatio × Stock2)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    # Panel 3: Z-Score with trading signal zones
    ax3.plot(combined.index, zscore, color='#4CAF50', linewidth=1.2, label='Z-Score')
    ax3.axhline(0,              color='black', linestyle='-',  linewidth=0.8)
    ax3.axhline(entry_threshold,  color='red',   linestyle='--', linewidth=1, label=f'Sell ({entry_threshold})')
    ax3.axhline(-entry_threshold, color='green', linestyle='--', linewidth=1, label=f'Buy (-{entry_threshold})')
    ax3.axhline(exit_threshold,   color='gray',  linestyle=':',  linewidth=0.8)
    ax3.axhline(-exit_threshold,  color='gray',  linestyle=':',  linewidth=0.8)
    ax3.fill_between(combined.index, entry_threshold, 4,
                     alpha=0.1, color='red', label='Short zone')
    ax3.fill_between(combined.index, -4, -entry_threshold,
                     alpha=0.1, color='green', label='Buy zone')
    # Plot a dot at the latest z-score position
    ax3.scatter(combined.index[-1], current_zscore,
                color='blue', s=100, zorder=5, label=f'Now ({current_zscore:.2f})')
    ax3.set_ylim(-4, 4)
    ax3.set_title("Z-Score of Spread")
    ax3.legend(fontsize=8)
    ax3.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("pairs_trading.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Chart saved as 'pairs_trading.png'")

    press_enter_to_continue()


# =============================================================================
# TOOL 2: STATISTICAL ARBITRAGE
# =============================================================================

def tool_2_statistical_arbitrage():
    """
    STATISTICAL ARBITRAGE

    Statistical Arbitrage (StatArb) extends pairs trading to a BASKET of stocks.
    Instead of just 2 stocks, we:
    1. Take a group of related stocks (e.g., all banking stocks)
    2. Find how each stock relates to the group average
    3. Flag stocks that have diverged too far from their expected level
    4. Trade expecting the stock to revert back to the group

    Key metrics used:
    - Z-Score vs group: How far is a stock from the basket's mean?
    - Mean Reversion Score: Probability the stock reverts
    - Momentum vs basket: Is the stock gaining/losing relative to peers?
    """
    clear_screen()
    print("=" * 65)
    print("  TOOL 2: STATISTICAL ARBITRAGE")
    print("=" * 65)
    print()
    print("  Finds stocks that have diverged from their peer group.")
    print("  Trades the divergence expecting reversion to the group mean.")
    print()
    print("  PRESET BASKETS (or enter your own):")
    print("  1. Nifty Private Banks (HDFCBANK.NS, ICICIBANK.NS, KOTAKBANK.NS,")
    print("                          AXISBANK.NS, INDUSINDBK.NS)")
    print("  2. Nifty IT (TCS.NS, INFY.NS, WIPRO.NS, HCLTECH.NS, TECHM.NS)")
    print("  3. FMCG (HINDUNILVR.NS, ITC.NS, BRITANNIA.NS, NESTLEIND.NS)")
    print("  4. Custom basket (enter your own symbols)")
    print()

    basket_choice = input("  Choose basket (1-4): ").strip()

    # Define preset baskets
    presets = {
        "1": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS"],
        "2": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
        "3": ["HINDUNILVR.NS", "ITC.NS", "BRITANNIA.NS", "NESTLEIND.NS"],
    }

    if basket_choice in presets:
        symbols = presets[basket_choice]
        print(f"  Using preset basket: {', '.join(symbols)}")
    elif basket_choice == "4":
        raw = input("  Enter symbols separated by commas: ").strip().upper()
        symbols = [s.strip() for s in raw.split(",") if s.strip()]
        if len(symbols) < 3:
            print("  Please enter at least 3 symbols for a basket.")
            press_enter_to_continue()
            return
    else:
        print("  Invalid choice.")
        press_enter_to_continue()
        return

    # Download data for all stocks in the basket
    print()
    print("  Downloading basket data...")
    close_data = {}
    for sym in symbols:
        df = download_data(sym, period="1y", interval="1d")
        if df is not None and len(df) > 60:
            close_data[sym] = df['Close']

    if len(close_data) < 3:
        print("  Not enough data downloaded. Check symbols.")
        press_enter_to_continue()
        return

    # Combine into one DataFrame, aligned by date
    prices = pd.DataFrame(close_data).dropna()

    # --- Normalize prices to percentage returns from start ---
    # So all stocks start at 100 regardless of their absolute price
    normalized = prices / prices.iloc[0] * 100   # Each stock starts at 100

    # --- Calculate Z-Scores relative to basket ---
    # For each day, calculate the basket average and std dev
    # Then find how many standard deviations each stock is from the basket
    basket_mean = normalized.mean(axis=1)  # Average of all stocks each day
    basket_std  = normalized.std(axis=1)   # Std dev across stocks each day

    # Z-score for each stock vs the basket
    zscores = normalized.subtract(basket_mean, axis=0).divide(basket_std, axis=0)

    # --- Current Signals ---
    results = []
    lookback = 20  # Days to check for mean reversion tendency

    for sym in prices.columns:
        # Latest normalized price vs basket
        latest_norm     = float(normalized[sym].iloc[-1])
        basket_now      = float(basket_mean.iloc[-1])
        current_zscore  = float(zscores[sym].iloc[-1])

        # 1-week and 1-month returns for this stock
        ret_1w  = (float(prices[sym].iloc[-1]) / float(prices[sym].iloc[-5])  - 1) * 100 if len(prices) > 5  else 0
        ret_1m  = (float(prices[sym].iloc[-1]) / float(prices[sym].iloc[-21]) - 1) * 100 if len(prices) > 21 else 0

        # Mean Reversion tendency: what fraction of time in last 20 days
        # did the z-score move toward zero? (indicator of mean reversion)
        recent_z    = zscores[sym].iloc[-lookback:]
        sign_now    = np.sign(recent_z.iloc[-1])   # Current direction (+/-)
        reversions  = sum(
            1 for i in range(1, len(recent_z))
            if abs(recent_z.iloc[i]) < abs(recent_z.iloc[i-1])
        )
        reversion_score = reversions / (lookback - 1) * 100  # % of days reverting

        # Signal based on z-score
        if current_zscore > 2.0:
            signal = "SHORT"     # Expensive vs basket → expect to underperform
        elif current_zscore < -2.0:
            signal = "BUY"       # Cheap vs basket → expect to outperform
        elif current_zscore > 1.0:
            signal = "WEAK SHORT"
        elif current_zscore < -1.0:
            signal = "WEAK BUY"
        else:
            signal = "NEUTRAL"

        results.append({
            "Symbol":          sym,
            "Norm. Price":     f"{latest_norm:.1f}",
            "Basket Avg":      f"{basket_now:.1f}",
            "Z-Score":         f"{current_zscore:+.3f}",
            "1W Return":       f"{ret_1w:+.2f}%",
            "1M Return":       f"{ret_1m:+.2f}%",
            "Revert Score":    f"{reversion_score:.0f}%",
            "SIGNAL":          signal,
        })

    # Sort by z-score (most extreme divergences first)
    results.sort(key=lambda x: abs(float(x["Z-Score"])), reverse=True)

    # --- Display Results ---
    print()
    print("  STATISTICAL ARBITRAGE SIGNALS")
    print("=" * 70)
    print(tabulate(pd.DataFrame(results), headers='keys',
                   tablefmt='rounded_outline', showindex=False))

    print()
    print("  INTERPRETATION:")
    print("  Z-Score > +2.0 = Stock is 2 std devs ABOVE basket → SHORT (overvalued vs peers)")
    print("  Z-Score < -2.0 = Stock is 2 std devs BELOW basket → BUY  (undervalued vs peers)")
    print("  Revert Score = % of recent days where stock moved back toward basket average")
    print("  Higher Revert Score = more likely to continue reverting")

    # --- Correlation Heatmap of the basket ---
    print()
    print("  Generating basket correlation heatmap...")

    daily_returns = prices.pct_change().dropna()   # Daily % returns
    corr_matrix   = daily_returns.corr()           # Correlation of returns

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Statistical Arbitrage — Basket Analysis", fontsize=13, fontweight='bold')

    # Left: Normalized price paths
    for sym in normalized.columns:
        ax1.plot(normalized.index, normalized[sym], linewidth=1.2, label=sym, alpha=0.8)
    ax1.plot(normalized.index, basket_mean, 'k--', linewidth=2, label='Basket Mean')
    ax1.set_title("Normalized Prices (Base = 100)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # Right: Correlation heatmap
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap='RdYlGn',
                center=0, vmin=-1, vmax=1, ax=ax2, linewidths=0.5)
    ax2.set_title("Basket Correlation Matrix")

    plt.tight_layout()
    plt.savefig("stat_arb.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Chart saved as 'stat_arb.png'")

    press_enter_to_continue()


# =============================================================================
# TOOL 3: ML PREDICTION MODEL
# =============================================================================

def tool_3_ml_prediction():
    """
    ML PREDICTION MODEL

    Uses Machine Learning to predict whether tomorrow's closing price
    will be HIGHER or LOWER than today's close.

    This is a CLASSIFICATION problem:
    - Target: 1 = price went UP tomorrow, 0 = price went DOWN

    FEATURES (inputs to the model):
    - RSI (14): Momentum indicator
    - MACD: Trend direction
    - ATR (14): Volatility
    - SMA 5/20/50: Short/medium/long moving averages (price vs SMA)
    - Bollinger Band position: Where price is within the band
    - Volume ratio: Today's volume vs 20-day average
    - Day of week: Some days trend differently
    - Returns: 1-day, 3-day, 5-day past returns

    MODELS USED:
    1. Random Forest  — ensemble of decision trees (robust, handles non-linearity)
    2. Logistic Regression — linear baseline model

    IMPORTANT DISCLAIMER:
    ML models for stock price prediction are educational tools.
    Markets are partially efficient and no model is 100% accurate.
    Never trade based solely on ML predictions. Use as one of many signals.
    """
    clear_screen()
    print("=" * 65)
    print("  TOOL 3: ML PREDICTION MODEL")
    print("=" * 65)
    print()
    print("  Trains a Random Forest + Logistic Regression model")
    print("  to predict UP or DOWN direction for next day.")
    print()
    print("  ⚠ DISCLAIMER: For educational use only.")
    print("  Never trade based solely on ML predictions.")
    print()

    symbol = get_symbol("  Enter stock symbol (e.g. TCS.NS, RELIANCE.NS): ")

    # Download 3 years of data (more data = better ML training)
    print()
    df = download_data(symbol, period="3y", interval="1d")
    if df is None or len(df) < 200:
        print("  Need at least 200 days of data. Try a more liquid stock.")
        press_enter_to_continue()
        return

    close  = df['Close']
    high   = df['High']
    low    = df['Low']
    volume = df['Volume']

    # =================================================================
    # FEATURE ENGINEERING
    # Creating meaningful inputs (features) from raw price/volume data
    # =================================================================

    features = pd.DataFrame(index=df.index)   # Empty DataFrame, same dates as df

    # --- Momentum Features ---
    features['rsi_14']  = calculate_rsi(close, 14)   # RSI momentum
    features['rsi_7']   = calculate_rsi(close, 7)    # Shorter RSI

    # --- MACD Features ---
    macd_l, sig_l, hist = calculate_macd(close)
    features['macd_line']    = macd_l             # MACD line value
    features['macd_signal']  = sig_l              # Signal line value
    features['macd_hist']    = hist               # Histogram (macd - signal)
    features['macd_cross']   = (macd_l > sig_l).astype(int)  # 1 if bullish cross

    # --- Volatility Features ---
    atr = calculate_atr(df, 14)
    features['atr_14']       = atr                # Raw ATR
    features['atr_pct']      = atr / close * 100  # ATR as % of price (normalized)

    # --- Moving Average Features ---
    sma5  = close.rolling(5).mean()
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    # Distance from price to each SMA (as %)
    features['price_vs_sma5']  = (close - sma5)  / sma5  * 100
    features['price_vs_sma20'] = (close - sma20) / sma20 * 100
    features['price_vs_sma50'] = (close - sma50) / sma50 * 100
    features['sma5_vs_sma20']  = (sma5 - sma20)  / sma20 * 100  # Short vs long trend

    # --- Bollinger Bands ---
    # Bollinger Bands = SMA ± 2 standard deviations
    sma20_std  = close.rolling(20).std()          # Rolling standard deviation
    upper_band = sma20 + 2 * sma20_std            # Upper band
    lower_band = sma20 - 2 * sma20_std            # Lower band
    band_width = upper_band - lower_band           # Band width (volatility proxy)
    # %B = where is price within the bands? 0 = at lower band, 1 = at upper band
    features['bb_pct_b'] = (close - lower_band) / band_width

    # --- Volume Features ---
    vol_sma20 = volume.rolling(20).mean()
    features['vol_ratio'] = volume / vol_sma20    # Today's volume vs 20-day average

    # --- Return Features (past N-day returns) ---
    features['ret_1d'] = close.pct_change(1) * 100   # Yesterday's return
    features['ret_3d'] = close.pct_change(3) * 100   # 3-day return
    features['ret_5d'] = close.pct_change(5) * 100   # 5-day return

    # --- Calendar Feature ---
    features['day_of_week'] = pd.to_datetime(df.index).dayofweek  # 0=Mon, 4=Fri

    # --- High/Low Position ---
    # Where did today's close land within the day's range?
    # 1.0 = closed at day's high, 0.0 = closed at day's low
    features['hl_position'] = (close - low) / (high - low + 1e-10)

    # =================================================================
    # TARGET VARIABLE
    # 1 = next day's close is HIGHER than today's close → BUY signal
    # 0 = next day's close is LOWER  than today's close → No trade
    # =================================================================

    # shift(-1) moves tomorrow's close into today's row
    target = (close.shift(-1) > close).astype(int)
    target.name = 'target'

    # --- Combine features and target ---
    data = pd.concat([features, target], axis=1).dropna()  # Remove rows with NaN

    X = data.drop('target', axis=1)   # All columns except target = features
    y = data['target']                 # Just the target column

    feature_names = X.columns.tolist()  # Save feature names for importance display

    print(f"  Total samples: {len(X)}")
    print(f"  Features used: {len(feature_names)}")
    print(f"  Positive class (UP days): {y.sum()} ({y.mean()*100:.1f}%)")
    print(f"  Negative class (DOWN days): {(1-y).sum()} ({(1-y.mean())*100:.1f}%)")

    # =================================================================
    # TRAIN / TEST SPLIT
    # We split chronologically (not randomly!) because stock data is time series.
    # Using 80% for training, 20% for testing (the most recent period)
    # =================================================================

    split_idx    = int(len(X) * 0.8)       # Index where we split train/test
    X_train      = X.iloc[:split_idx]       # First 80% for training
    X_test       = X.iloc[split_idx:]       # Last 20% for testing
    y_train      = y.iloc[:split_idx]
    y_test       = y.iloc[split_idx:]

    print(f"  Training samples: {len(X_train)} | Test samples: {len(X_test)}")

    # =================================================================
    # FEATURE SCALING
    # Logistic Regression needs features on the same scale.
    # StandardScaler: transforms each feature to mean=0, std=1
    # =================================================================
    scaler    = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)   # Fit AND transform training data
    X_test_s  = scaler.transform(X_test)        # Only transform test data (no fit!)

    # =================================================================
    # MODEL 1: RANDOM FOREST CLASSIFIER
    # An ensemble of 200 decision trees.
    # Each tree votes UP or DOWN, and the majority wins.
    # =================================================================
    print()
    print("  Training Random Forest model...")
    rf_model = RandomForestClassifier(
        n_estimators=200,     # Number of trees in the forest
        max_depth=5,          # Maximum depth of each tree (prevents overfitting)
        min_samples_split=20, # Minimum samples to split a node (prevents overfitting)
        random_state=42,      # Fixed seed for reproducibility
        n_jobs=-1             # Use all CPU cores for speed
    )
    rf_model.fit(X_train, y_train)                  # Train on training data
    rf_predictions   = rf_model.predict(X_test)     # Predict on test data
    rf_probabilities = rf_model.predict_proba(X_test)[:, 1]  # Probability of UP
    rf_accuracy      = accuracy_score(y_test, rf_predictions)

    # =================================================================
    # MODEL 2: LOGISTIC REGRESSION (baseline)
    # A linear model that estimates P(UP) using a logistic function.
    # Simpler than Random Forest but still useful as a benchmark.
    # =================================================================
    print("  Training Logistic Regression model...")
    lr_model = LogisticRegression(max_iter=1000, random_state=42)
    lr_model.fit(X_train_s, y_train)                # Train on scaled data
    lr_predictions   = lr_model.predict(X_test_s)
    lr_probabilities = lr_model.predict_proba(X_test_s)[:, 1]
    lr_accuracy      = accuracy_score(y_test, lr_predictions)

    # =================================================================
    # PREDICT TOMORROW
    # Use the most recent row of features to predict tomorrow
    # =================================================================
    latest_features = X.iloc[-1:]                              # Latest day's features
    rf_tomorrow_prob = rf_model.predict_proba(latest_features)[0, 1]  # P(UP)
    lr_tomorrow_prob = lr_model.predict_proba(scaler.transform(latest_features))[0, 1]

    rf_tomorrow = "UP ↑" if rf_tomorrow_prob > 0.5 else "DOWN ↓"
    lr_tomorrow = "UP ↑" if lr_tomorrow_prob > 0.5 else "DOWN ↓"

    # Ensemble: average the two models' probabilities
    ensemble_prob = (rf_tomorrow_prob + lr_tomorrow_prob) / 2
    ensemble_pred = "UP ↑" if ensemble_prob > 0.5 else "DOWN ↓"

    # --- Display Results ---
    print()
    print(f"  ML PREDICTION RESULTS FOR: {symbol}")
    print("=" * 65)

    model_table = [
        ["Random Forest",      f"{rf_accuracy*100:.1f}%", f"{rf_tomorrow_prob*100:.1f}%", rf_tomorrow],
        ["Logistic Regression",f"{lr_accuracy*100:.1f}%", f"{lr_tomorrow_prob*100:.1f}%", lr_tomorrow],
        ["Ensemble (Average)", "—",                        f"{ensemble_prob*100:.1f}%",   ensemble_pred],
    ]
    print(tabulate(model_table,
                   headers=["Model", "Test Accuracy", "P(UP Tomorrow)", "Prediction"],
                   tablefmt='rounded_outline'))

    # --- Feature Importance (Random Forest) ---
    print()
    print("  TOP 10 MOST IMPORTANT FEATURES (Random Forest):")
    importances = rf_model.feature_importances_      # How much each feature contributes
    feat_imp    = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)

    imp_table = [[f, f"{v*100:.2f}%"] for f, v in feat_imp[:10]]
    print(tabulate(imp_table, headers=["Feature", "Importance"], tablefmt='rounded_outline'))

    # --- Confusion Matrix ---
    print()
    print("  CONFUSION MATRIX (Random Forest on test set):")
    print("  Rows = Actual | Columns = Predicted")
    cm = confusion_matrix(y_test, rf_predictions)
    cm_df = pd.DataFrame(
        cm,
        index=["Actual DOWN", "Actual UP"],
        columns=["Pred DOWN", "Pred UP"]
    )
    print(tabulate(cm_df, headers='keys', tablefmt='rounded_outline'))

    # --- Classification Report ---
    print()
    print("  CLASSIFICATION REPORT (Random Forest):")
    print(classification_report(y_test, rf_predictions,
                                 target_names=["DOWN (0)", "UP (1)"]))

    # --- Plot: Feature Importance + Cumulative Return of following signals ---
    print()
    print("  Generating ML chart...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"ML Prediction Model: {symbol}", fontsize=13, fontweight='bold')

    # Left: Feature Importance bar chart
    top_n       = 10
    feat_labels = [f[0] for f in feat_imp[:top_n]]
    feat_values = [f[1] for f in feat_imp[:top_n]]
    bars = ax1.barh(feat_labels[::-1], feat_values[::-1], color='#2196F3', alpha=0.8)
    ax1.set_title("Feature Importance (Random Forest)")
    ax1.set_xlabel("Importance Score")
    ax1.grid(alpha=0.3, axis='x')

    # Right: Cumulative return of strategy vs Buy & Hold (on test set)
    test_closes  = close.iloc[split_idx: split_idx + len(rf_predictions)].values
    actual_rets  = pd.Series(test_closes).pct_change().fillna(0).values

    # Strategy: Go long when model predicts UP, sit out when DOWN
    strategy_rets = np.where(rf_predictions[:-1] == 1, actual_rets[1:], 0)

    # Cumulative return = product of (1 + daily return) - 1
    cum_bnh      = np.cumprod(1 + actual_rets[1:]) - 1       # Buy and hold
    cum_strategy = np.cumprod(1 + strategy_rets)   - 1       # ML strategy

    ax2.plot(cum_bnh      * 100, label='Buy & Hold',    color='#FF9800', linewidth=1.5)
    ax2.plot(cum_strategy * 100, label='ML Strategy',   color='#4CAF50', linewidth=1.5)
    ax2.axhline(0, color='gray', linestyle='--', linewidth=0.8)
    ax2.set_title("Strategy vs Buy & Hold (Test Period)")
    ax2.set_xlabel("Trading Days")
    ax2.set_ylabel("Cumulative Return (%)")
    ax2.legend()
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("ml_prediction.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Chart saved as 'ml_prediction.png'")

    print()
    print("  ⚠ REMINDER: This model is for education only.")
    print("  Accuracy above 55% is considered good for financial data.")
    print("  Always combine with fundamental analysis and risk management.")

    press_enter_to_continue()


# =============================================================================
# TOOL 4: OPTIONS STRATEGY BUILDER
# =============================================================================

def tool_4_options_strategy():
    """
    OPTIONS STRATEGY BUILDER

    Helps you visualize and analyze common options strategies by plotting
    their profit/loss payoff diagrams at expiration.

    STRATEGIES AVAILABLE:
    1. Long Call       — Buy a call option (bullish, limited risk)
    2. Long Put        — Buy a put option (bearish, limited risk)
    3. Bull Call Spread — Buy lower call, sell higher call (bullish, cheaper)
    4. Bear Put Spread  — Buy higher put, sell lower put (bearish, cheaper)
    5. Long Straddle    — Buy call + put at same strike (bet on big move)
    6. Iron Condor      — Sell call spread + sell put spread (bet on no move)
    7. Covered Call     — Own stock + sell call (income strategy)
    8. Protective Put   — Own stock + buy put (downside protection)

    KEY OPTIONS TERMS:
    - Strike Price : The price at which you can buy/sell the underlying
    - Premium      : The cost of buying the option (what you pay)
    - Expiry       : The date when the option contract expires
    - Breakeven    : The stock price where you neither make nor lose money
    - Max Profit   : The most you can make from this trade
    - Max Loss     : The most you can lose from this trade
    """
    clear_screen()
    print("=" * 65)
    print("  TOOL 4: OPTIONS STRATEGY BUILDER")
    print("=" * 65)
    print()
    print("  Build and visualize options strategies with P&L diagrams.")
    print()

    while True:
        print("  STRATEGIES:")
        print("  1.  Long Call         (Bullish | Limited risk)")
        print("  2.  Long Put          (Bearish | Limited risk)")
        print("  3.  Bull Call Spread  (Bullish | Cheaper than long call)")
        print("  4.  Bear Put Spread   (Bearish | Cheaper than long put)")
        print("  5.  Long Straddle     (Big move expected | Either direction)")
        print("  6.  Iron Condor       (Sideways market | Sell volatility)")
        print("  7.  Covered Call      (Income | Own stock + sell call)")
        print("  8.  Protective Put    (Protection | Own stock + buy put)")
        print("  9.  Back to main menu")
        print()
        choice = input("  Choose strategy (1-9): ").strip()

        if choice == "9":
            break

        # -------------------------------------------------------
        # Helper: get a positive float from the user
        def get_float(prompt):
            while True:
                try:
                    val = float(input(prompt))
                    if val <= 0:
                        print("  Please enter a positive number.")
                        continue
                    return val
                except ValueError:
                    print("  Invalid input. Enter a number.")

        # -------------------------------------------------------
        # Helper: plot the payoff diagram
        def plot_payoff(price_range, pnl_values, strategy_name,
                        breakevens, max_profit, max_loss, spot):
            """
            Plots the P&L payoff diagram for an options strategy.

            Parameters:
                price_range  : array of stock prices at expiry (x-axis)
                pnl_values   : array of P&L values at each price (y-axis)
                strategy_name: name of the strategy for chart title
                breakevens   : list of breakeven prices
                max_profit   : maximum possible profit
                max_loss     : maximum possible loss
                spot         : current stock price
            """
            fig, ax = plt.subplots(figsize=(11, 6))
            fig.suptitle(f"Options Strategy: {strategy_name}", fontsize=13, fontweight='bold')

            # Plot the P&L curve
            ax.plot(price_range, pnl_values, color='#2196F3', linewidth=2.5, label='P&L at Expiry')

            # Shade profit area (green) and loss area (red)
            ax.fill_between(price_range, pnl_values, 0,
                            where=[p > 0 for p in pnl_values],
                            color='green', alpha=0.2, label='Profit Zone')
            ax.fill_between(price_range, pnl_values, 0,
                            where=[p <= 0 for p in pnl_values],
                            color='red', alpha=0.2, label='Loss Zone')

            # Breakeven lines
            for be in breakevens:
                ax.axvline(be, color='orange', linestyle='--', linewidth=1.5,
                           label=f'Breakeven @ {be:.2f}')

            # Current stock price line
            ax.axvline(spot, color='purple', linestyle=':', linewidth=1.5,
                       label=f'Current Price @ {spot:.2f}')

            # Zero P&L line
            ax.axhline(0, color='black', linewidth=0.8)

            # Annotate max profit / max loss
            if max_profit != float('inf'):
                ax.text(price_range[0], max_profit * 0.9,
                        f"Max Profit: {max_profit:+.2f}", fontsize=9, color='green')
            if max_loss != float('-inf'):
                ax.text(price_range[0], max_loss * 0.9,
                        f"Max Loss: {max_loss:+.2f}", fontsize=9, color='red')

            ax.set_xlabel("Stock Price at Expiry")
            ax.set_ylabel("Profit / Loss (₹ per share)")
            ax.legend(fontsize=9)
            ax.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(f"options_{strategy_name.replace(' ','_').lower()}.png",
                        dpi=120, bbox_inches='tight')
            plt.show()
            filename = f"options_{strategy_name.replace(' ','_').lower()}.png"
            print(f"  Chart saved as '{filename}'")

        # -------------------------------------------------------
        # Helper: display strategy summary table
        def show_summary(strategy_name, spot, breakevens, max_profit, max_loss, legs):
            print()
            print(f"  STRATEGY: {strategy_name}")
            print("=" * 55)
            print()
            print("  LEGS (components of this strategy):")
            for leg in legs:
                print(f"    {leg}")
            print()

            summary = [
                ["Current Stock Price", f"₹{spot:.2f}"],
                ["Breakeven Price(s)",  " | ".join([f"₹{b:.2f}" for b in breakevens])],
                ["Max Profit",          f"₹{max_profit:.2f}" if max_profit != float('inf') else "UNLIMITED"],
                ["Max Loss",            f"₹{max_loss:.2f}"],
            ]
            print(tabulate(summary, headers=["Metric", "Value"], tablefmt='rounded_outline'))

        # ============================================================
        # STRATEGY 1: LONG CALL
        # ============================================================
        if choice == "1":
            print()
            print("  LONG CALL: You buy a call option.")
            print("  Profit if stock rises above breakeven.")
            print("  Max loss = premium paid (if stock stays below strike).")
            print()
            spot    = get_float("  Current stock price (₹): ")
            strike  = get_float("  Call strike price (₹): ")
            premium = get_float("  Premium paid (₹ per share): ")
            lots    = get_float("  Number of lots (1 lot = 1 share for calculation): ")

            # Price range: 50% below to 50% above current price
            prices = np.linspace(spot * 0.5, spot * 1.5, 300)

            # P&L formula for Long Call:
            # At expiry: max(stock price - strike, 0) - premium paid
            pnl = (np.maximum(prices - strike, 0) - premium) * lots

            breakeven   = strike + premium           # Price needs to exceed this to profit
            max_profit  = float('inf')               # Theoretically unlimited upside
            max_loss    = -premium * lots            # Lose the premium if stock < strike

            show_summary("Long Call", spot, [breakeven], max_profit, max_loss,
                         [f"BUY 1 Call @ Strike={strike}, Premium={premium}"])
            plot_payoff(prices, pnl, "Long Call", [breakeven], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 2: LONG PUT
        # ============================================================
        elif choice == "2":
            print()
            print("  LONG PUT: You buy a put option.")
            print("  Profit if stock falls below breakeven.")
            print("  Max loss = premium paid.")
            print()
            spot    = get_float("  Current stock price (₹): ")
            strike  = get_float("  Put strike price (₹): ")
            premium = get_float("  Premium paid (₹ per share): ")
            lots    = get_float("  Lots: ")

            prices = np.linspace(spot * 0.5, spot * 1.5, 300)

            # P&L formula for Long Put:
            # max(strike - stock price, 0) - premium
            pnl = (np.maximum(strike - prices, 0) - premium) * lots

            breakeven  = strike - premium
            max_profit = (strike - premium) * lots   # If stock goes to 0
            max_loss   = -premium * lots

            show_summary("Long Put", spot, [breakeven], max_profit, max_loss,
                         [f"BUY 1 Put @ Strike={strike}, Premium={premium}"])
            plot_payoff(prices, pnl, "Long Put", [breakeven], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 3: BULL CALL SPREAD
        # ============================================================
        elif choice == "3":
            print()
            print("  BULL CALL SPREAD:")
            print("  Buy a lower strike call, sell a higher strike call.")
            print("  Cheaper than buying a plain call, but caps your upside.")
            print()
            spot     = get_float("  Current stock price (₹): ")
            strike_l = get_float("  LOWER strike (buy call) (₹): ")
            prem_l   = get_float("  Premium PAID for lower call (₹): ")
            strike_h = get_float("  HIGHER strike (sell call) (₹): ")
            prem_h   = get_float("  Premium RECEIVED for higher call (₹): ")
            lots     = get_float("  Lots: ")

            if strike_h <= strike_l:
                print("  Higher strike must be above lower strike.")
                continue

            net_debit = prem_l - prem_h   # Net cost of the spread

            prices = np.linspace(spot * 0.5, spot * 1.5, 300)

            # P&L = Long call P&L + Short call P&L
            long_call_pnl  =  np.maximum(prices - strike_l, 0) - prem_l
            short_call_pnl = -np.maximum(prices - strike_h, 0) + prem_h
            pnl = (long_call_pnl + short_call_pnl) * lots

            breakeven  = strike_l + net_debit
            max_profit = (strike_h - strike_l - net_debit) * lots
            max_loss   = -net_debit * lots

            show_summary("Bull Call Spread", spot, [breakeven], max_profit, max_loss, [
                f"BUY  1 Call @ {strike_l}, Premium = {prem_l}",
                f"SELL 1 Call @ {strike_h}, Premium = {prem_h}",
                f"Net Cost (Debit) = {net_debit:.2f} per share"
            ])
            plot_payoff(prices, pnl, "Bull Call Spread", [breakeven], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 4: BEAR PUT SPREAD
        # ============================================================
        elif choice == "4":
            print()
            print("  BEAR PUT SPREAD:")
            print("  Buy a higher strike put, sell a lower strike put.")
            print("  Cheaper than a plain put, but caps your downside profit.")
            print()
            spot     = get_float("  Current stock price (₹): ")
            strike_h = get_float("  HIGHER strike (buy put) (₹): ")
            prem_h   = get_float("  Premium PAID for higher put (₹): ")
            strike_l = get_float("  LOWER strike (sell put) (₹): ")
            prem_l   = get_float("  Premium RECEIVED for lower put (₹): ")
            lots     = get_float("  Lots: ")

            net_debit = prem_h - prem_l

            prices = np.linspace(spot * 0.5, spot * 1.5, 300)

            long_put_pnl  =  np.maximum(strike_h - prices, 0) - prem_h
            short_put_pnl = -np.maximum(strike_l - prices, 0) + prem_l
            pnl = (long_put_pnl + short_put_pnl) * lots

            breakeven  = strike_h - net_debit
            max_profit = (strike_h - strike_l - net_debit) * lots
            max_loss   = -net_debit * lots

            show_summary("Bear Put Spread", spot, [breakeven], max_profit, max_loss, [
                f"BUY  1 Put @ {strike_h}, Premium = {prem_h}",
                f"SELL 1 Put @ {strike_l}, Premium = {prem_l}",
                f"Net Cost = {net_debit:.2f} per share"
            ])
            plot_payoff(prices, pnl, "Bear Put Spread", [breakeven], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 5: LONG STRADDLE
        # ============================================================
        elif choice == "5":
            print()
            print("  LONG STRADDLE:")
            print("  Buy a call AND a put at the SAME strike.")
            print("  Profit if stock moves strongly in EITHER direction.")
            print("  Lose if stock stays near the strike (time decay kills you).")
            print()
            spot        = get_float("  Current stock price (₹): ")
            strike      = get_float("  Strike price (both call and put) (₹): ")
            call_prem   = get_float("  Call premium paid (₹): ")
            put_prem    = get_float("  Put premium paid (₹): ")
            lots        = get_float("  Lots: ")

            total_prem = call_prem + put_prem  # Total cost of the straddle

            prices = np.linspace(spot * 0.3, spot * 1.7, 300)

            call_pnl = np.maximum(prices - strike, 0) - call_prem
            put_pnl  = np.maximum(strike - prices, 0) - put_prem
            pnl      = (call_pnl + put_pnl) * lots

            be_up      = strike + total_prem   # Need to go above this to profit on upside
            be_down    = strike - total_prem   # Need to go below this to profit on downside
            max_profit = float('inf')          # Unlimited if big move
            max_loss   = -total_prem * lots    # Lose all premiums if stock at strike

            show_summary("Long Straddle", spot, [be_down, be_up], max_profit, max_loss, [
                f"BUY 1 Call @ Strike={strike}, Premium={call_prem}",
                f"BUY 1 Put  @ Strike={strike}, Premium={put_prem}",
                f"Total Premium Paid = {total_prem:.2f}",
            ])
            plot_payoff(prices, pnl, "Long Straddle", [be_down, be_up], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 6: IRON CONDOR
        # ============================================================
        elif choice == "6":
            print()
            print("  IRON CONDOR:")
            print("  Sell an OTM call spread + Sell an OTM put spread.")
            print("  Profit if stock stays between the two short strikes.")
            print("  Best in low-volatility, range-bound markets.")
            print()
            spot  = get_float("  Current stock price (₹): ")
            print("  Enter 4 strikes (from lowest to highest):")
            lp    = get_float("  Long Put  strike (lowest, e.g. 400): ")
            sp    = get_float("  Short Put strike (e.g. 450): ")
            sc    = get_float("  Short Call strike (e.g. 550): ")
            lc    = get_float("  Long Call strike (highest, e.g. 600): ")
            lp_p  = get_float("  Long Put premium PAID (₹): ")
            sp_p  = get_float("  Short Put premium RECEIVED (₹): ")
            sc_p  = get_float("  Short Call premium RECEIVED (₹): ")
            lc_p  = get_float("  Long Call premium PAID (₹): ")
            lots  = get_float("  Lots: ")

            # Net premium received (positive = credit received)
            net_credit = sp_p + sc_p - lp_p - lc_p

            prices = np.linspace(spot * 0.5, spot * 1.5, 300)

            # Each leg's P&L:
            long_put_pnl   =  np.maximum(lp - prices, 0) - lp_p   # Buy put at lp
            short_put_pnl  = -np.maximum(sp - prices, 0) + sp_p   # Sell put at sp
            short_call_pnl = -np.maximum(prices - sc, 0) + sc_p   # Sell call at sc
            long_call_pnl  =  np.maximum(prices - lc, 0) - lc_p   # Buy call at lc
            pnl = (long_put_pnl + short_put_pnl + short_call_pnl + long_call_pnl) * lots

            be_down    = sp - net_credit     # Lower breakeven
            be_up      = sc + net_credit     # Upper breakeven
            max_profit = net_credit * lots   # If stock stays between sp and sc
            max_loss   = -(min(sp - lp, lc - sc) - net_credit) * lots

            show_summary("Iron Condor", spot, [be_down, be_up], max_profit, max_loss, [
                f"BUY  Put  @ {lp}  (pay {lp_p})",
                f"SELL Put  @ {sp}  (receive {sp_p})",
                f"SELL Call @ {sc}  (receive {sc_p})",
                f"BUY  Call @ {lc}  (pay {lc_p})",
                f"Net Credit = {net_credit:.2f} per share",
            ])
            plot_payoff(prices, pnl, "Iron Condor", [be_down, be_up], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 7: COVERED CALL
        # ============================================================
        elif choice == "7":
            print()
            print("  COVERED CALL:")
            print("  You own the stock + Sell a call option against it.")
            print("  Earn income from premium. Cap upside at strike price.")
            print("  Good for: slightly bullish or sideways view on a stock you hold.")
            print()
            spot    = get_float("  Your stock's current price (₹): ")
            buy_px  = get_float("  Your original buy price of stock (₹): ")
            strike  = get_float("  Call strike you're selling (₹): ")
            premium = get_float("  Premium RECEIVED from selling call (₹): ")
            lots    = get_float("  Lots: ")

            prices = np.linspace(spot * 0.5, spot * 1.5, 300)

            # Stock P&L: (current price at expiry - your buy price)
            stock_pnl = prices - buy_px
            # Short call P&L: receive premium, but obligated to sell at strike if exercised
            short_call_pnl = np.where(
                prices > strike,
                -(prices - strike) + premium,   # Stock called away: premium - loss above strike
                premium                          # Stock not called: keep the premium
            )
            pnl = (stock_pnl + short_call_pnl) * lots

            breakeven   = buy_px - premium          # Effective cost basis reduced by premium
            max_profit  = (strike - buy_px + premium) * lots
            max_loss    = -(buy_px - premium) * lots   # If stock goes to 0

            show_summary("Covered Call", spot, [breakeven], max_profit, max_loss, [
                f"LONG Stock @ {buy_px} (current: {spot})",
                f"SELL Call @ {strike}, Premium = {premium}",
                f"Effective Cost Basis = {breakeven:.2f}",
            ])
            plot_payoff(prices, pnl, "Covered Call", [breakeven], max_profit, max_loss, spot)

        # ============================================================
        # STRATEGY 8: PROTECTIVE PUT
        # ============================================================
        elif choice == "8":
            print()
            print("  PROTECTIVE PUT (Married Put):")
            print("  You own the stock + Buy a put option as insurance.")
            print("  Limits your downside risk. Small cost = peace of mind.")
            print()
            spot    = get_float("  Current stock price (₹): ")
            buy_px  = get_float("  Your original buy price of stock (₹): ")
            strike  = get_float("  Put strike (protection level) (₹): ")
            premium = get_float("  Premium PAID for put (₹): ")
            lots    = get_float("  Lots: ")

            prices = np.linspace(spot * 0.3, spot * 1.5, 300)

            stock_pnl    = prices - buy_px
            long_put_pnl = np.maximum(strike - prices, 0) - premium
            pnl = (stock_pnl + long_put_pnl) * lots

            breakeven  = buy_px + premium           # Need price above this to profit
            max_profit = float('inf')               # Unlimited upside
            max_loss   = -(buy_px - strike + premium) * lots   # Floored at strike

            show_summary("Protective Put", spot, [breakeven], max_profit, max_loss, [
                f"LONG Stock @ {buy_px} (current: {spot})",
                f"BUY Put @ {strike}, Premium = {premium}",
                f"Max loss capped at ₹{(buy_px - strike + premium):.2f} per share",
            ])
            plot_payoff(prices, pnl, "Protective Put", [breakeven], max_profit, max_loss, spot)

        else:
            print("  Invalid choice.")


# =============================================================================
# TOOL 5: SUPERTREND + ATR STRATEGY
# =============================================================================

def tool_5_supertrend_atr():
    """
    SUPERTREND + ATR STRATEGY

    Supertrend is a popular trend-following indicator that uses ATR
    (Average True Range) to define dynamic support/resistance bands.

    HOW SUPERTREND WORKS:
    1. Calculate ATR (volatility measure)
    2. Create Upper Band = (High+Low)/2 + multiplier × ATR
    3. Create Lower Band = (High+Low)/2 - multiplier × ATR
    4. Supertrend tracks which band is "active":
       - When price ABOVE supertrend line → UPTREND → BUY signal (line = support)
       - When price BELOW supertrend line → DOWNTREND → SELL signal (line = resistance)
    5. When price crosses the supertrend line → SIGNAL CHANGE

    ATR TRAILING STOP:
    - Uses ATR to set dynamic stop-loss levels that trail the price
    - In uptrend: Stop = Close - (multiplier × ATR)
    - In downtrend: Stop = Close + (multiplier × ATR)

    BACKTEST:
    - Simulates buying and selling based on supertrend signals
    - Tracks each trade: entry, exit, P&L, win/loss
    """
    clear_screen()
    print("=" * 65)
    print("  TOOL 5: SUPERTREND + ATR STRATEGY")
    print("=" * 65)
    print()
    print("  Supertrend is a trend-following indicator.")
    print("  BUY  when price crosses ABOVE the Supertrend line.")
    print("  SELL when price crosses BELOW the Supertrend line.")
    print()

    symbol = get_symbol("  Enter stock symbol (e.g. RELIANCE.NS, TCS.NS): ")

    # Download 2 years of daily data
    df = download_data(symbol, period="2y", interval="1d")
    if df is None or len(df) < 50:
        print("  Not enough data.")
        press_enter_to_continue()
        return

    try:
        atr_period  = int(input("  ATR period (default 10, press Enter): ") or "10")
        multiplier  = float(input("  ATR multiplier (default 3.0, press Enter): ") or "3.0")
    except ValueError:
        atr_period, multiplier = 10, 3.0

    # --- Calculate ATR ---
    atr = calculate_atr(df, atr_period)

    # --- Calculate Supertrend ---
    hl2 = (df['High'] + df['Low']) / 2   # Midpoint of each candle

    # Basic upper and lower bands
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    # Final bands (adjusted to never move against the trend)
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()

    close = df['Close']

    # Adjust bands: upper band only moves DOWN, lower band only moves UP
    # This prevents the bands from wiggling back and forth
    for i in range(1, len(df)):
        # Upper band: don't let it go higher than previous upper band
        # (unless price broke above previous upper band = new uptrend)
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]

        # Lower band: don't let it go lower than previous lower band
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]

    # Supertrend direction: 1 = uptrend (use lower band), -1 = downtrend (use upper band)
    supertrend_dir  = pd.Series(1, index=df.index)    # Start assuming uptrend
    supertrend_line = pd.Series(index=df.index, dtype=float)

    for i in range(1, len(df)):
        prev_dir = supertrend_dir.iloc[i-1]

        # If previous direction was UP (using lower band)
        if prev_dir == 1:
            if close.iloc[i] < final_lower.iloc[i]:
                # Price fell below lower band → switch to DOWNTREND
                supertrend_dir.iloc[i]  = -1
                supertrend_line.iloc[i] = final_upper.iloc[i]  # Use upper band as resistance
            else:
                supertrend_dir.iloc[i]  = 1
                supertrend_line.iloc[i] = final_lower.iloc[i]  # Continue using lower band as support

        # If previous direction was DOWN (using upper band)
        else:
            if close.iloc[i] > final_upper.iloc[i]:
                # Price rose above upper band → switch to UPTREND
                supertrend_dir.iloc[i]  = 1
                supertrend_line.iloc[i] = final_lower.iloc[i]
            else:
                supertrend_dir.iloc[i]  = -1
                supertrend_line.iloc[i] = final_upper.iloc[i]

    # --- ATR Trailing Stop ---
    # Trail the stop loss with price movement using ATR
    atr_stop_long  = close - multiplier * atr   # Stop for long trades (below price)
    atr_stop_short = close + multiplier * atr   # Stop for short trades (above price)

    # --- Generate Buy/Sell Signals ---
    # Signal occurs when direction CHANGES
    buy_signals  = []   # Dates where BUY signal occurs
    sell_signals = []   # Dates where SELL signal occurs

    for i in range(1, len(df)):
        prev_dir = supertrend_dir.iloc[i-1]
        curr_dir = supertrend_dir.iloc[i]
        date     = df.index[i]

        if prev_dir == -1 and curr_dir == 1:    # Switched from DOWN to UP
            buy_signals.append((date, float(close.iloc[i])))
        elif prev_dir == 1 and curr_dir == -1:  # Switched from UP to DOWN
            sell_signals.append((date, float(close.iloc[i])))

    # --- Backtesting ---
    # Simulate trading: buy at each BUY signal, sell at next SELL signal
    all_signals = (
        [(d, p, "BUY")  for d, p in buy_signals] +
        [(d, p, "SELL") for d, p in sell_signals]
    )
    all_signals.sort(key=lambda x: x[0])   # Sort by date

    trades       = []         # Track completed trades
    in_trade     = False      # Are we currently in a trade?
    entry_price  = None
    entry_date   = None

    for date, price, sig_type in all_signals:
        if sig_type == "BUY" and not in_trade:
            # Enter long trade
            in_trade    = True
            entry_price = price
            entry_date  = date

        elif sig_type == "SELL" and in_trade:
            # Exit long trade
            exit_price = price
            pnl_pct    = (exit_price - entry_price) / entry_price * 100
            trades.append({
                "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                "Exit Date":   date.strftime("%Y-%m-%d"),
                "Entry Price": f"₹{entry_price:.2f}",
                "Exit Price":  f"₹{exit_price:.2f}",
                "Return %":    f"{pnl_pct:+.2f}%",
                "Result":      "WIN ✓" if pnl_pct > 0 else "LOSS ✗",
            })
            in_trade = False

    # --- Current Signal ---
    current_dir   = supertrend_dir.iloc[-1]
    current_line  = float(supertrend_line.iloc[-1])
    current_price = float(close.iloc[-1])
    current_atr   = float(atr.iloc[-1])

    current_signal = "BUY / HOLD LONG" if current_dir == 1 else "SELL / HOLD SHORT"
    current_stop   = float(atr_stop_long.iloc[-1]) if current_dir == 1 else float(atr_stop_short.iloc[-1])

    # --- Display Current Signal ---
    print()
    print(f"  SUPERTREND SIGNAL FOR: {symbol}")
    print("=" * 55)

    signal_table = [
        ["Current Price",      f"₹{current_price:.2f}"],
        ["ATR (14)",           f"₹{current_atr:.2f}"],
        ["Supertrend Line",    f"₹{current_line:.2f}"],
        ["Current Direction",  "UPTREND ↑" if current_dir == 1 else "DOWNTREND ↓"],
        ["SIGNAL",             current_signal],
        ["ATR Trailing Stop",  f"₹{current_stop:.2f}"],
        ["Risk per share",     f"₹{abs(current_price - current_stop):.2f}"],
    ]
    print(tabulate(signal_table, headers=["Metric", "Value"], tablefmt='rounded_outline'))

    # --- Backtest Summary ---
    print()
    if trades:
        print(f"  BACKTEST: {len(trades)} completed trades (last 2 years)")
        print("-" * 55)

        returns     = [float(t["Return %"].replace('%','').replace('+','')) for t in trades]
        winners     = [r for r in returns if r > 0]
        losers      = [r for r in returns if r <= 0]
        win_rate    = len(winners) / len(returns) * 100 if returns else 0
        avg_win     = sum(winners) / len(winners) if winners else 0
        avg_loss    = sum(losers)  / len(losers)  if losers  else 0
        total_return= sum(returns)

        bt_summary = [
            ["Total Trades",       len(returns)],
            ["Winning Trades",     len(winners)],
            ["Losing Trades",      len(losers)],
            ["Win Rate",           f"{win_rate:.1f}%"],
            ["Avg Win",            f"{avg_win:+.2f}%"],
            ["Avg Loss",           f"{avg_loss:+.2f}%"],
            ["Sum of All Returns", f"{total_return:+.2f}%"],
            ["Best Trade",         f"{max(returns):+.2f}%"],
            ["Worst Trade",        f"{min(returns):+.2f}%"],
        ]
        print(tabulate(bt_summary, headers=["Metric", "Value"], tablefmt='rounded_outline'))

        print()
        print("  INDIVIDUAL TRADES:")
        print(tabulate(pd.DataFrame(trades), headers='keys',
                       tablefmt='rounded_outline', showindex=False))
    else:
        print("  Not enough signals for a complete backtest in this period.")

    # --- Chart ---
    print()
    print("  Generating Supertrend chart...")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                    gridspec_kw={'height_ratios': [3, 1]},
                                    sharex=True)
    fig.suptitle(f"Supertrend + ATR Strategy: {symbol} "
                 f"(ATR={atr_period}, Mult={multiplier})",
                 fontsize=13, fontweight='bold')

    # --- Top chart: Price + Supertrend ---
    # Separate uptrend and downtrend segments for coloring
    up_mask   = supertrend_dir == 1    # Boolean mask where direction is UP
    down_mask = supertrend_dir == -1   # Boolean mask where direction is DOWN

    ax1.plot(close.index, close, color='#37474F', linewidth=1.2, label='Price', zorder=3)

    # Plot supertrend line in green during uptrend, red during downtrend
    st_up   = supertrend_line.where(up_mask)    # Only show uptrend segment
    st_down = supertrend_line.where(down_mask)  # Only show downtrend segment
    ax1.plot(st_up.index,   st_up,   color='#4CAF50', linewidth=2, label='Supertrend (Up)',   zorder=2)
    ax1.plot(st_down.index, st_down, color='#F44336', linewidth=2, label='Supertrend (Down)', zorder=2)

    # ATR Trailing Stops (dotted lines)
    ax1.plot(atr_stop_long.index,  atr_stop_long,  'g:', linewidth=0.8, alpha=0.7, label='ATR Long Stop')
    ax1.plot(atr_stop_short.index, atr_stop_short, 'r:', linewidth=0.8, alpha=0.7, label='ATR Short Stop')

    # Plot BUY signals as green triangles pointing up
    if buy_signals:
        buy_dates  = [b[0] for b in buy_signals]
        buy_prices = [b[1] for b in buy_signals]
        ax1.scatter(buy_dates, buy_prices, marker='^', color='#4CAF50',
                    s=120, zorder=5, label='BUY Signal')

    # Plot SELL signals as red triangles pointing down
    if sell_signals:
        sell_dates  = [s[0] for s in sell_signals]
        sell_prices = [s[1] for s in sell_signals]
        ax1.scatter(sell_dates, sell_prices, marker='v', color='#F44336',
                    s=120, zorder=5, label='SELL Signal')

    ax1.set_title("Price with Supertrend Band & ATR Trailing Stop")
    ax1.set_ylabel("Price (₹)")
    ax1.legend(fontsize=8, loc='upper left')
    ax1.grid(alpha=0.3)

    # --- Bottom chart: ATR ---
    ax2.plot(atr.index, atr, color='#9C27B0', linewidth=1.2, label='ATR')
    ax2.fill_between(atr.index, atr, alpha=0.2, color='#9C27B0')
    ax2.set_title("ATR (Volatility)")
    ax2.set_ylabel("ATR Value")
    ax2.set_xlabel("Date")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("supertrend_atr.png", dpi=120, bbox_inches='tight')
    plt.show()
    print("  Chart saved as 'supertrend_atr.png'")

    print()
    print("  HOW TO USE THIS STRATEGY:")
    print("  1. When price crosses ABOVE Supertrend line → BUY")
    print("  2. Use ATR Trailing Stop as your stop-loss level")
    print("  3. When price crosses BELOW Supertrend line → EXIT / SELL")
    print("  4. Works best on liquid stocks/indices in trending markets")
    print("  5. Combine with RSI or volume for confirmation")

    press_enter_to_continue()


# =============================================================================
# MAIN MENU
# =============================================================================

def main_menu():
    """
    Shows the main menu and routes the user to the selected tool.
    Runs in a loop until the user chooses to exit.
    """
    while True:
        clear_screen()
        print()
        print("=" * 65)
        print("       ADVANCED STRATEGIES TOOLS SUITE")
        print("       5 Professional Trading Strategies in Python")
        print("=" * 65)
        print()
        print("  ── ADVANCED STRATEGIES ─────────────────────────────────")
        print()
        print("   1.  Pairs Trading Engine")
        print("       Cointegration test, Z-score signals, backtest")
        print()
        print("   2.  Statistical Arbitrage")
        print("       Basket analysis, mean reversion, correlation heatmap")
        print()
        print("   3.  ML Prediction Model")
        print("       Random Forest + Logistic Regression, feature importance")
        print()
        print("   4.  Options Strategy Builder")
        print("       8 strategies: Calls, Puts, Spreads, Condors, Straddles")
        print()
        print("   5.  Supertrend + ATR Strategy")
        print("       Dynamic trend signals, ATR trailing stop, backtest")
        print()
        print("   0.  Exit")
        print()
        print("=" * 65)
        print()
        print("  INSTALL LIBRARIES (first time only):")
        print("  pip install yfinance pandas numpy scipy matplotlib")
        print("  pip install seaborn tabulate scikit-learn statsmodels")
        print()

        choice = input("  Select tool (0-5): ").strip()

        if   choice == "1":  tool_1_pairs_trading()
        elif choice == "2":  tool_2_statistical_arbitrage()
        elif choice == "3":  tool_3_ml_prediction()
        elif choice == "4":  tool_4_options_strategy()
        elif choice == "5":  tool_5_supertrend_atr()
        elif choice == "0":
            clear_screen()
            print()
            print("  Exiting Advanced Strategies Suite. Goodbye!")
            print()
            break
        else:
            print("  Invalid choice. Enter 0 to 5.")
            input("  Press Enter to try again...")


# =============================================================================
# ENTRY POINT
# Run with: python advanced_strategies_suite.py
# =============================================================================

if __name__ == "__main__":
    main_menu()         