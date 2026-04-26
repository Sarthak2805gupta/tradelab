# ============================================================
# CANDLESTICK PATTERN DETECTOR FOR INDIAN STOCKS
# ============================================================
# This script:
#   1. Downloads real stock data from Yahoo Finance
#   2. Manually detects common candlestick patterns
#   3. Prints a summary of recent patterns found
#
# INSTALL REQUIRED LIBRARIES FIRST:
#   pip install yfinance pandas
# ============================================================


# ── Imports ──────────────────────────────────────────────────
import yfinance as yf        # Downloads real stock price data from Yahoo Finance
import pandas as pd          # For working with tabular data (DataFrames)


# ── STEP 1: Download Stock Data ───────────────────────────────
def get_stock_data(ticker, period="3mo"):
    """
    Downloads historical OHLCV data for a given stock ticker.

    Parameters:
        ticker (str): Stock symbol e.g. "RELIANCE.NS" (.NS = NSE India)
        period (str): How far back to look. Options: 1mo, 3mo, 6mo, 1y

    Returns:
        df (DataFrame): Table with columns Open, High, Low, Close, Volume
    """

    print(f"\nDownloading data for: {ticker}")

    # yf.download fetches data from Yahoo Finance
    # "RELIANCE.NS" means Reliance Industries on NSE (National Stock Exchange)
    # For BSE stocks use ".BO" suffix e.g. "RELIANCE.BO"
    df = yf.download(ticker, period=period, auto_adjust=True)

    # Drop rows where any value is missing (NaN = Not a Number)
    df.dropna(inplace=True)

    # Flatten multi-level column names if present (yfinance sometimes creates them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Downloaded {len(df)} trading days of data")
    print(f"Date range: {df.index[0].date()} to {df.index[-1].date()}")

    return df


# ── STEP 2: Helper Functions ──────────────────────────────────

def body_size(row):
    """
    Returns the absolute size of the candle body.
    Body = distance between Open and Close prices.
    Example: Open=100, Close=110 → body = 10
    """
    return abs(row['Close'] - row['Open'])


def candle_range(row):
    """
    Returns the full range of the candle (High to Low).
    Example: High=115, Low=95 → range = 20
    """
    return row['High'] - row['Low']


def upper_wick(row):
    """
    Returns the length of the upper wick (shadow).
    Upper wick = High minus the top of the body.
    For bullish (green) candle: top of body = Close
    For bearish (red) candle:  top of body = Open
    """
    top_of_body = max(row['Open'], row['Close'])   # Whichever is higher
    return row['High'] - top_of_body


def lower_wick(row):
    """
    Returns the length of the lower wick (shadow).
    Lower wick = bottom of body minus Low.
    For bullish (green) candle: bottom of body = Open
    For bearish (red) candle:  bottom of body = Close
    """
    bottom_of_body = min(row['Open'], row['Close'])  # Whichever is lower
    return bottom_of_body - row['Low']


def is_bullish(row):
    """Returns True if the candle is green (price went up)."""
    return row['Close'] > row['Open']


def is_bearish(row):
    """Returns True if the candle is red (price went down)."""
    return row['Close'] < row['Open']


# ── STEP 3: Single Candle Pattern Detectors ──────────────────

def detect_doji(row):
    """
    DOJI: Open ≈ Close (tiny or no body)
    Meaning: Market indecision — bulls and bears are in balance.
    Signal: Possible reversal coming (need confirmation next day).

    Rule: Body is less than 10% of the total candle range.
    """
    total_range = candle_range(row)

    # Avoid division by zero on a day with no price movement
    if total_range == 0:
        return False

    body = body_size(row)

    # Body must be very small relative to the full range
    return body / total_range < 0.1


def detect_hammer(row):
    """
    HAMMER: Long lower wick, small body at the top.
    Meaning: Sellers pushed price down but buyers recovered strongly.
    Signal: Bullish reversal (only valid after a downtrend).

    Rules:
        - Lower wick is at least 2x the body size
        - Upper wick is very small (less than 10% of body)
        - Body is in the upper half of the candle
    """
    body = body_size(row)
    l_wick = lower_wick(row)
    u_wick = upper_wick(row)
    total = candle_range(row)

    # Avoid zero-body candles
    if body == 0 or total == 0:
        return False

    return (
        l_wick >= 2 * body       and   # Long lower wick
        u_wick <= 0.1 * body     and   # Very short upper wick
        body >= 0.1 * total            # Body not too tiny
    )


def detect_shooting_star(row):
    """
    SHOOTING STAR: Long upper wick, small body at the bottom.
    Meaning: Buyers pushed price up but sellers rejected the move.
    Signal: Bearish reversal (only valid after an uptrend).

    Rules (mirror image of Hammer):
        - Upper wick is at least 2x the body size
        - Lower wick is very small
        - Body is in the lower half of the candle
    """
    body = body_size(row)
    l_wick = lower_wick(row)
    u_wick = upper_wick(row)
    total = candle_range(row)

    if body == 0 or total == 0:
        return False

    return (
        u_wick >= 2 * body       and   # Long upper wick
        l_wick <= 0.1 * body     and   # Very short lower wick
        body >= 0.1 * total            # Body not too tiny
    )


def detect_marubozu(row):
    """
    MARUBOZU: Large body with NO wicks (or very tiny wicks).
    Meaning: Strong momentum — either buyers or sellers were totally in control.
    Signal: Trend continuation.
        - Green Marubozu = strong bullish momentum
        - Red Marubozu   = strong bearish momentum

    Rule: Wicks are each less than 5% of the total candle range.
    """
    total = candle_range(row)

    if total == 0:
        return False, None

    u_wick = upper_wick(row)
    l_wick = lower_wick(row)

    # Both wicks must be negligibly small
    is_maru = u_wick / total < 0.05 and l_wick / total < 0.05

    if is_maru:
        direction = "Bullish" if is_bullish(row) else "Bearish"
        return True, direction

    return False, None


# ── STEP 4: Two-Candle Pattern Detectors ─────────────────────

def detect_engulfing(prev, curr):
    """
    ENGULFING: The second candle's body completely covers the first candle's body.

    BULLISH ENGULFING:
        - First candle is bearish (red)
        - Second candle is bullish (green) and larger
        - Signal: Bullish reversal after downtrend

    BEARISH ENGULFING:
        - First candle is bullish (green)
        - Second candle is bearish (red) and larger
        - Signal: Bearish reversal after uptrend

    Parameters:
        prev (Series): Previous day's candle data
        curr (Series): Today's candle data
    """

    # ── Bullish Engulfing ──
    if (is_bearish(prev) and            # Previous candle was red
        is_bullish(curr) and            # Current candle is green
        curr['Open']  < prev['Close']   # Green opens below red's close
        and curr['Close'] > prev['Open'] # Green closes above red's open
    ):
        return "Bullish Engulfing"

    # ── Bearish Engulfing ──
    if (is_bullish(prev) and            # Previous candle was green
        is_bearish(curr) and            # Current candle is red
        curr['Open']  > prev['Close']   # Red opens above green's close
        and curr['Close'] < prev['Open'] # Red closes below green's open
    ):
        return "Bearish Engulfing"

    return None   # No pattern found


def detect_harami(prev, curr):
    """
    HARAMI (means 'pregnant' in Japanese): Small candle inside the previous large candle.
    The second candle is completely contained within the first candle's body.

    BULLISH HARAMI:
        - First candle is large and bearish (red)
        - Second candle is small and bullish (green), inside the red body
        - Signal: Potential bullish reversal

    BEARISH HARAMI:
        - First candle is large and bullish (green)
        - Second candle is small and bearish (red), inside the green body
        - Signal: Potential bearish reversal
    """

    prev_top    = max(prev['Open'], prev['Close'])   # Top of previous body
    prev_bottom = min(prev['Open'], prev['Close'])   # Bottom of previous body
    curr_top    = max(curr['Open'], curr['Close'])   # Top of current body
    curr_bottom = min(curr['Open'], curr['Close'])   # Bottom of current body

    # Current candle's body must be inside previous candle's body
    body_inside = (curr_top < prev_top) and (curr_bottom > prev_bottom)

    if not body_inside:
        return None

    if is_bearish(prev) and is_bullish(curr):
        return "Bullish Harami"

    if is_bullish(prev) and is_bearish(curr):
        return "Bearish Harami"

    return None


# ── STEP 5: Three-Candle Pattern Detectors ───────────────────

def detect_morning_evening_star(c1, c2, c3):
    """
    MORNING STAR (Bullish reversal after downtrend):
        Candle 1: Large bearish (red) candle
        Candle 2: Small body (doji or small candle) — gap down
        Candle 3: Large bullish (green) candle closing into candle 1's body

    EVENING STAR (Bearish reversal after uptrend):
        Candle 1: Large bullish (green) candle
        Candle 2: Small body — gap up
        Candle 3: Large bearish (red) candle closing into candle 1's body

    Parameters:
        c1, c2, c3: Candle data for 3 consecutive days
    """

    # Calculate body sizes
    body1 = body_size(c1)
    body2 = body_size(c2)
    body3 = body_size(c3)

    # The middle candle must be small (less than 30% of candle 1's body)
    if body1 == 0 or body2 >= 0.3 * body1:
        return None

    # ── Morning Star ──
    if (is_bearish(c1) and           # Day 1: large red
        body3 >= 0.5 * body1 and     # Day 3: large green (at least half of day 1)
        is_bullish(c3) and
        c3['Close'] > (c1['Open'] + c1['Close']) / 2  # Day 3 closes above midpoint of day 1
    ):
        return "Morning Star"

    # ── Evening Star ──
    if (is_bullish(c1) and           # Day 1: large green
        body3 >= 0.5 * body1 and     # Day 3: large red (at least half of day 1)
        is_bearish(c3) and
        c3['Close'] < (c1['Open'] + c1['Close']) / 2  # Day 3 closes below midpoint of day 1
    ):
        return "Evening Star"

    return None


def detect_three_soldiers_crows(c1, c2, c3):
    """
    THREE WHITE SOLDIERS (Strong bullish continuation):
        Three consecutive large bullish (green) candles, each opening inside
        the previous candle's body and closing higher.

    THREE BLACK CROWS (Strong bearish continuation):
        Three consecutive large bearish (red) candles, each opening inside
        the previous candle's body and closing lower.
    """

    # ── Three White Soldiers ──
    if (is_bullish(c1) and is_bullish(c2) and is_bullish(c3)   # All three green
        and c2['Close'] > c1['Close']                           # Each closes higher
        and c3['Close'] > c2['Close']
        and c2['Open']  > c1['Open']                            # Each opens higher
        and c3['Open']  > c2['Open']
    ):
        return "Three White Soldiers"

    # ── Three Black Crows ──
    if (is_bearish(c1) and is_bearish(c2) and is_bearish(c3)   # All three red
        and c2['Close'] < c1['Close']                           # Each closes lower
        and c3['Close'] < c2['Close']
        and c2['Open']  < c1['Open']                            # Each opens lower
        and c3['Open']  < c2['Open']
    ):
        return "Three Black Crows"

    return None


# ── STEP 6: Run All Detectors on the Full Dataset ────────────

def scan_all_patterns(df):
    """
    Loops through all candles in the dataset and checks for every pattern.
    Returns a list of detected patterns with date and price info.

    Parameters:
        df (DataFrame): Stock OHLCV data

    Returns:
        results (list of dicts): Each dict has date, pattern name, signal, and close price
    """

    results = []   # We'll collect all found patterns here

    # We need at least 3 rows to check 3-candle patterns
    # range(2, len(df)) means we start from index 2 (the third row)
    for i in range(2, len(df)):

        # Get current row and the two before it
        row  = df.iloc[i]       # Today's candle
        prev = df.iloc[i - 1]   # Yesterday's candle
        prev2 = df.iloc[i - 2]  # Two days ago

        date       = df.index[i].date()   # The calendar date
        close      = round(row['Close'], 2)  # Round to 2 decimal places

        # ── Single candle checks ──

        if detect_doji(row):
            results.append({
                'Date': date, 'Pattern': 'Doji',
                'Signal': 'Indecision / Possible Reversal', 'Close': close
            })

        if detect_hammer(row):
            results.append({
                'Date': date, 'Pattern': 'Hammer',
                'Signal': 'Bullish Reversal', 'Close': close
            })

        if detect_shooting_star(row):
            results.append({
                'Date': date, 'Pattern': 'Shooting Star',
                'Signal': 'Bearish Reversal', 'Close': close
            })

        maru_found, maru_dir = detect_marubozu(row)
        if maru_found:
            results.append({
                'Date': date, 'Pattern': f'{maru_dir} Marubozu',
                'Signal': f'{maru_dir} Momentum', 'Close': close
            })

        # ── Two candle checks ──

        engulf = detect_engulfing(prev, row)
        if engulf:
            results.append({
                'Date': date, 'Pattern': engulf,
                'Signal': 'Bullish Reversal' if 'Bullish' in engulf else 'Bearish Reversal',
                'Close': close
            })

        harami = detect_harami(prev, row)
        if harami:
            results.append({
                'Date': date, 'Pattern': harami,
                'Signal': 'Bullish Reversal' if 'Bullish' in harami else 'Bearish Reversal',
                'Close': close
            })

        # ── Three candle checks ──

        star = detect_morning_evening_star(prev2, prev, row)
        if star:
            results.append({
                'Date': date, 'Pattern': star,
                'Signal': 'Bullish Reversal' if 'Morning' in star else 'Bearish Reversal',
                'Close': close
            })

        soldiers = detect_three_soldiers_crows(prev2, prev, row)
        if soldiers:
            results.append({
                'Date': date, 'Pattern': soldiers,
                'Signal': 'Bullish Continuation' if 'Soldiers' in soldiers else 'Bearish Continuation',
                'Close': close
            })

    return results


# ── STEP 7: Main Program ──────────────────────────────────────

def main():
    """
    Main function — runs the full pattern scanner on a list of Indian stocks.
    Prints a nicely formatted summary of patterns found.
    """

    # List of Indian stocks to scan (NSE symbols with .NS suffix)
    # Add or remove any stocks you want to track
    stocks = [
        "RELIANCE.NS",   # Reliance Industries
        "TCS.NS",        # Tata Consultancy Services
        "INFY.NS",       # Infosys
        "HDFCBANK.NS",   # HDFC Bank
        "SBIN.NS",       # State Bank of India
    ]

    # Loop through each stock
    for ticker in stocks:

        # Download 3 months of daily data
        df = get_stock_data(ticker, period="3mo")

        # Run all pattern detectors
        patterns = scan_all_patterns(df)

        print(f"\n{'='*55}")
        print(f"  PATTERNS FOUND FOR: {ticker}")
        print(f"{'='*55}")

        if len(patterns) == 0:
            # No patterns found in the selected period
            print("  No significant patterns found in last 3 months.")
        else:
            # Convert list of dicts to a DataFrame for clean printing
            results_df = pd.DataFrame(patterns)

            # Show only the most recent 10 patterns (most relevant)
            recent = results_df.tail(10)

            # Print each row nicely
            for _, row in recent.iterrows():
                print(f"  {row['Date']}  |  {row['Pattern']:<25} |  {row['Signal']:<25}  |  Close: ₹{row['Close']}")

    print(f"\n{'='*55}")
    print("Scan complete!")
    print("REMINDER: Patterns are signals, not guarantees.")
    print("Always confirm with volume and other indicators.")
    print(f"{'='*55}\n")


# ── Entry Point ───────────────────────────────────────────────
# This block runs only when you execute this file directly
# (not when it's imported by another script)
if __name__ == "__main__":
    main()