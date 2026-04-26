# ============================================================
# NIFTY 500 STOCK SCREENER — DAILY MORNING WATCHLIST
# The Final Goal — Phase 8
# ============================================================
# This screener combines everything from Phases 1-7:
#
#   Phase 1 — Candlestick Patterns  → pattern detection
#   Phase 2 — SMA & EMA             → trend direction
#   Phase 3 — RSI                   → momentum & zones
#   Phase 4 — MACD                  → momentum crossovers
#   Phase 5 — Bollinger Bands       → volatility & squeeze
#   Phase 6 — Volume Analysis       → OBV, MFI, Vol ratio
#   Phase 7 — Strategies            → 4 scoring conditions
#
# OUTPUT:
#   - Console table: Top 15 stocks ranked by signal score
#   - CSV file: Full results for all scanned stocks
#   - Chart: Score distribution and top picks visualization
#   - Summary: Market mood and best opportunities
#
# HOW TO RUN:
#   python screener.py                    # Scan Nifty 50 (fast, ~30s)
#   python screener.py --index nifty100   # Scan Nifty 100 (~1 min)
#   python screener.py --index nifty500   # Full Nifty 500 (~5 min)
#   python screener.py --ticker RELIANCE  # Scan a single stock
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import time
import sys
import warnings
from datetime import datetime

# Suppress yfinance warnings for cleaner output
warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════
# SECTION 1 — NIFTY INDEX STOCK LISTS
# ════════════════════════════════════════════════════════════

# Nifty 50 — the 50 largest Indian companies by market cap
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFOSYS.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "NESTLEIND.NS",
    "BAJFINANCE.NS", "POWERGRID.NS", "NTPC.NS", "TECHM.NS", "TATAMOTORS.NS",
    "ONGC.NS", "TATASTEEL.NS", "ADANIENT.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS",
    "COALINDIA.NS", "INDUSINDBK.NS", "DRREDDY.NS", "CIPLA.NS", "EICHERMOT.NS",
    "BRITANNIA.NS", "APOLLOHOSP.NS", "BPCL.NS", "GRASIM.NS", "TATACONSUM.NS",
    "DIVISLAB.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "M&M.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "ADANIPORTS.NS", "UPL.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS",
]

# Nifty 100 — adds midcap leaders to the Nifty 50
NIFTY_100 = NIFTY_50 + [
    "AMBUJACEM.NS", "BANKBARODA.NS", "BERGEPAINT.NS", "BIOCON.NS",
    "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS", "COLPAL.NS", "DABUR.NS",
    "DLF.NS", "GAIL.NS", "GODREJCP.NS", "HAVELLS.NS", "ICICIPRULI.NS",
    "INDHOTEL.NS", "IOC.NS", "IRCTC.NS", "LUPIN.NS", "MARICO.NS",
    "MCDOWELL-N.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "OFSS.NS", "PAGEIND.NS",
    "PEL.NS", "PIDILITIND.NS", "PNB.NS", "RECLTD.NS", "SAIL.NS",
    "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS",
    "VOLTAS.NS", "WHIRLPOOL.NS", "ZEEL.NS", "ZOMATO.NS", "PAYTM.NS",
    "NYKAA.NS", "POLICYBZR.NS", "DELHIVERY.NS", "LTIM.NS", "ATGL.NS",
    "ADANIGREEN.NS", "ADANITRANS.NS", "AWL.NS", "ICICIGI.NS", "PGHH.NS",
]

# For a full Nifty 500 scan, add more tickers here
# This is a representative subset for demonstration
NIFTY_500_SAMPLE = NIFTY_100 + [
    "AUROPHARMA.NS", "BALRAMCHIN.NS", "BEL.NS", "BHEL.NS", "CROMPTON.NS",
    "CUMMINSIND.NS", "ESCORTS.NS", "FEDERALBNK.NS", "FORTIS.NS", "GMRINFRA.NS",
    "GODREJPROP.NS", "GRANULES.NS", "GUJGASLTD.NS", "HAL.NS", "IDBI.NS",
    "IDFCFIRSTB.NS", "INDIGO.NS", "INDUSTOWER.NS", "INTELLECT.NS", "IGL.NS",
    "JINDALSTEL.NS", "JUBLFOOD.NS", "KAJARIACER.NS", "KPITTECH.NS",
    "L&TFH.NS", "LALPATHLAB.NS", "LAURUSLABS.NS", "LICHSGFIN.NS",
    "MANAPPURAM.NS", "MFSL.NS", "MOTHERSON.NS", "MPHASIS.NS", "MRF.NS",
    "NATCOPHARM.NS", "NMDC.NS", "OBEROIRLTY.NS", "PERSISTENT.NS",
    "PETRONET.NS", "PFIZER.NS", "POLYCAB.NS", "RBLBANK.NS", "SCHAEFFLER.NS",
    "SONACOMS.NS", "SYNGENE.NS", "TATACOMM.NS", "TATACHEM.NS", "TATAELXSI.NS",
    "TORNTPOWER.NS", "TRIDENT.NS", "UNIONBANK.NS", "VBL.NS", "VEDL.NS",
]

INDEX_MAP = {
    'nifty50':  NIFTY_50,
    'nifty100': NIFTY_100,
    'nifty500': NIFTY_500_SAMPLE,
}


# ════════════════════════════════════════════════════════════
# SECTION 2 — ALL INDICATOR CALCULATIONS
# (Collected from Phases 2–6)
# ════════════════════════════════════════════════════════════

def calc_sma(series, period):
    return series.rolling(window=period, min_periods=period).mean()

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_rsi(prices, period=14):
    """RSI using Wilder's smoothing."""
    delta  = prices.diff(1)
    gains  = delta.clip(lower=0)
    losses = delta.clip(upper=0).abs()
    ag = gains.rolling(window=period, min_periods=period).mean()
    al = losses.rolling(window=period, min_periods=period).mean()
    ag_list = ag.tolist(); al_list = al.tolist()
    g_list  = gains.tolist(); l_list = losses.tolist()
    for i in range(period, len(ag_list)):
        if pd.isna(ag_list[i-1]): continue
        ag_list[i] = (ag_list[i-1]*(period-1) + g_list[i]) / period
        al_list[i] = (al_list[i-1]*(period-1) + l_list[i]) / period
    ag = pd.Series(ag_list, index=prices.index)
    al = pd.Series(al_list, index=prices.index)
    rs  = ag / al.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100).round(2)

def calc_macd(prices, fast=12, slow=26, signal=9):
    """Returns MACD line, Signal line, Histogram."""
    ema_fast  = calc_ema(prices, fast)
    ema_slow  = calc_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    sig_line  = calc_ema(macd_line, signal)
    histogram = macd_line - sig_line
    return macd_line, sig_line, histogram

def calc_bollinger(prices, period=20, num_std=2):
    """Returns middle, upper, lower bands, %B, bandwidth."""
    mid  = prices.rolling(window=period, min_periods=period).mean()
    std  = prices.rolling(window=period, min_periods=period).std(ddof=0)
    up   = mid + num_std * std
    lo   = mid - num_std * std
    pctb = (prices - lo) / (up - lo).replace(0, float('nan'))
    bw   = (up - lo) / mid * 100
    return mid, up, lo, pctb, bw

def calc_obv(close, volume):
    """On Balance Volume — cumulative buying vs selling pressure."""
    obv = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i-1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=close.index)

def calc_mfi(df, period=14):
    """Money Flow Index — volume-weighted RSI."""
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    raw_mf   = tp * df['Volume']
    pos_mf   = raw_mf.where(tp > tp.shift(1), 0)
    neg_mf   = raw_mf.where(tp < tp.shift(1), 0)
    pos_sum  = pos_mf.rolling(window=period, min_periods=period).sum()
    neg_sum  = neg_mf.rolling(window=period, min_periods=period).sum()
    mfr      = pos_sum / neg_sum.replace(0, float('nan'))
    mfi      = 100 - (100 / (1 + mfr))
    return mfi.fillna(100).round(2)


# ════════════════════════════════════════════════════════════
# SECTION 3 — CANDLESTICK PATTERN HELPERS
# (From Phase 1)
# ════════════════════════════════════════════════════════════

def is_hammer(row):
    """Hammer: long lower wick, small body, tiny upper wick."""
    body = abs(row['Close'] - row['Open'])
    rng  = row['High'] - row['Low']
    if rng == 0 or body == 0: return False
    lo_wick = min(row['Open'], row['Close']) - row['Low']
    up_wick = row['High'] - max(row['Open'], row['Close'])
    return lo_wick >= 2*body and up_wick <= 0.1*body and body >= 0.1*rng

def is_bullish_engulfing(prev, curr):
    """Green candle body completely wraps the previous red candle."""
    return (prev['Close'] < prev['Open'] and
            curr['Close'] > curr['Open'] and
            curr['Open']  < prev['Close'] and
            curr['Close'] > prev['Open'])

def is_doji(row):
    """Open ≈ Close — indecision candle."""
    rng = row['High'] - row['Low']
    if rng == 0: return False
    return abs(row['Close'] - row['Open']) / rng < 0.1


# ════════════════════════════════════════════════════════════
# SECTION 4 — THE SCORING ENGINE
# Each condition adds 1 point to the score (max = 8)
# ════════════════════════════════════════════════════════════

def score_stock(df, ticker):
    """
    Scores a single stock against all indicators and strategies.

    Returns a dict with:
        score (int):      0–8 total score
        signals (list):   which conditions were triggered
        indicators (dict): current values of key indicators
        last (Series):    most recent row of data

    The 8 scoring conditions (1 point each):
    ─────────────────────────────────────────
    1. TREND: Price above SMA 200 (long-term uptrend)
    2. TREND: SMA 50 above SMA 200 (Golden Cross zone)
    3. MOMENTUM: RSI between 30–55 (pullback in uptrend)
    4. MOMENTUM: MACD bullish crossover in last 3 days
    5. VOLATILITY: Bollinger Band squeeze (bandwidth at low)
       OR %B near lower band (mean reversion setup)
    6. VOLUME: Today's volume > 1.5x 20-day average
    7. VOLUME: OBV trending up (last 10 days OBV is rising)
    8. PATTERN: Bullish candlestick pattern in last 3 days
       (Hammer, Bullish Engulfing, or Morning Star)
    ─────────────────────────────────────────

    Parameters:
        df (DataFrame): 6 months of OHLCV data with all indicators
        ticker (str): Stock symbol for labelling

    Returns:
        dict with score, signals, indicators, metadata
    """

    # We need at least 210 rows for SMA 200 + buffer
    if len(df) < 210:
        return None

    # Get the last row (most recent trading day)
    last   = df.iloc[-1]
    prev   = df.iloc[-2]
    prev2  = df.iloc[-3]

    # Current indicator values
    close      = round(last['Close'], 2)
    sma50      = last['SMA_50']
    sma200     = last['SMA_200']
    rsi        = last['RSI']
    macd       = last['MACD']
    signal_ln  = last['Signal']
    pctb       = last['PctB']
    bw         = last['BW']
    vol_ratio  = last['Vol_Ratio']
    mfi        = last['MFI']
    obv_now    = last['OBV']

    # Skip if any critical indicator is NaN
    if any(pd.isna(v) for v in [sma50, sma200, rsi, macd, pctb, vol_ratio]):
        return None

    score   = 0
    signals = []   # Human-readable reasons for each point

    # ── Condition 1: Price above SMA 200 ──────────────────────
    # The stock is in a long-term uptrend
    if close > sma200:
        score += 1
        signals.append(f"Above SMA200 (₹{round(sma200,1)})")

    # ── Condition 2: SMA 50 above SMA 200 ────────────────────
    # Golden Cross zone — medium-term trend also bullish
    if sma50 > sma200:
        score += 1
        signals.append("Golden Cross zone (SMA50>SMA200)")

    # ── Condition 3: RSI in sweet spot ───────────────────────
    # RSI between 30–55: stock has pulled back from overbought
    # but momentum is just starting to turn up — ideal entry zone
    if 30 <= rsi <= 55:
        score += 1
        signals.append(f"RSI in sweet spot ({round(rsi,1)})")
    elif rsi < 30:
        # Extra flag: extremely oversold — potential mean reversion
        signals.append(f"RSI oversold ({round(rsi,1)}) — mean reversion alert")

    # ── Condition 4: MACD bullish crossover ──────────────────
    # Check if MACD crossed above Signal in last 3 days
    # (fresh crossovers are most powerful)
    macd_cross_recent = False
    for lookback in range(1, 4):   # Check today, yesterday, day before
        if len(df) > lookback + 1:
            m_now  = df['MACD'].iloc[-lookback]
            m_prev = df['MACD'].iloc[-lookback - 1]
            s_now  = df['Signal'].iloc[-lookback]
            s_prev = df['Signal'].iloc[-lookback - 1]
            if not any(pd.isna(v) for v in [m_now, m_prev, s_now, s_prev]):
                if m_prev < s_prev and m_now > s_now:
                    macd_cross_recent = True
                    days_ago = lookback - 1
                    break

    if macd_cross_recent:
        score += 1
        label = "today" if days_ago == 0 else f"{days_ago}d ago"
        signals.append(f"MACD bullish cross ({label})")

    # ── Condition 5: Bollinger setup ─────────────────────────
    # Either a squeeze (bands very narrow) OR price near lower band
    # Squeeze: bandwidth at 50-day low (coiled, ready to move)
    # Lower band touch: potential mean reversion buy
    bw_series     = df['BW'].dropna()
    bw_50day_min  = bw_series.iloc[-50:].min() if len(bw_series) >= 50 else bw_series.min()
    is_squeeze    = bw <= bw_50day_min * 1.05    # Within 5% of 50-day min bandwidth
    lower_touch   = pctb < 0.15                  # Price near lower Bollinger Band

    if is_squeeze:
        score += 1
        signals.append(f"BB Squeeze (BW={round(bw,1)}% at 50d low)")
    elif lower_touch:
        score += 1
        signals.append(f"Near lower BB (%B={round(pctb,2)})")

    # ── Condition 6: High volume ──────────────────────────────
    # Today's volume is at least 1.5x the 20-day average
    # This confirms that the price move has conviction
    if not pd.isna(vol_ratio) and vol_ratio >= 1.5:
        score += 1
        signals.append(f"High volume ({round(vol_ratio,1)}x avg)")

    # ── Condition 7: OBV trending up ─────────────────────────
    # OBV in the last 10 days is rising — smart money is accumulating
    obv_series = df['OBV'].iloc[-11:]   # Last 11 rows = 10 changes
    if len(obv_series) >= 11:
        obv_change_10d = obv_series.iloc[-1] - obv_series.iloc[0]
        # Positive OBV change over 10 days = buying pressure building
        if obv_change_10d > 0:
            score += 1
            signals.append("OBV trending up (10d)")

    # ── Condition 8: Bullish candlestick pattern ──────────────
    # Check last 3 days for any bullish reversal pattern
    pattern_found = False

    # Check for Hammer on last 3 days
    for lookback in [1, 2, 3]:
        if len(df) >= lookback:
            row = df.iloc[-lookback]
            if is_hammer(row):
                signals.append(f"Hammer pattern ({lookback}d ago)")
                pattern_found = True
                break

    # Check for Bullish Engulfing on last 3 days
    if not pattern_found:
        for lookback in [1, 2, 3]:
            if len(df) >= lookback + 1:
                c = df.iloc[-lookback]
                p = df.iloc[-lookback - 1]
                if is_bullish_engulfing(p, c):
                    signals.append(f"Bullish engulfing ({lookback}d ago)")
                    pattern_found = True
                    break

    # Check for Doji (indecision, potential reversal)
    if not pattern_found and is_doji(last):
        signals.append("Doji — watch for direction")
        # Doji alone doesn't add a point — it's a watch signal only

    if pattern_found:
        score += 1

    # ── Calculate additional info ──────────────────────────────
    # 52-week high/low context
    high_52w = df['High'].iloc[-252:].max() if len(df) >= 252 else df['High'].max()
    low_52w  = df['Low'].iloc[-252:].min()  if len(df) >= 252 else df['Low'].min()
    pct_from_high = (close - high_52w) / high_52w * 100

    # 1-month price change
    one_month_ago = df['Close'].iloc[-22] if len(df) >= 22 else df['Close'].iloc[0]
    pct_1m = (close - one_month_ago) / one_month_ago * 100

    return {
        'Ticker'       : ticker.replace('.NS', ''),
        'Score'        : score,
        'Close'        : close,
        'RSI'          : round(rsi, 1),
        'MFI'          : round(mfi, 1),
        'MACD'         : round(macd, 3),
        'PctB'         : round(pctb, 2),
        'Vol_Ratio'    : round(vol_ratio, 2),
        '1M_Chg%'      : round(pct_1m, 1),
        'From52wHigh%' : round(pct_from_high, 1),
        'Signals'      : ' | '.join(signals) if signals else 'No signals',
        'N_Signals'    : len(signals),
    }


# ════════════════════════════════════════════════════════════
# SECTION 5 — DATA DOWNLOAD AND PROCESSING
# ════════════════════════════════════════════════════════════

def download_and_process(ticker, period="6mo"):
    """
    Downloads OHLCV data for one ticker and calculates all indicators.

    Uses a try/except because yfinance can occasionally fail for
    specific tickers (delisted stocks, network timeouts, etc.).
    We return None for any failed download so the screener can
    skip to the next stock without crashing.

    Parameters:
        ticker (str): e.g. "RELIANCE.NS"
        period (str): "6mo" gives enough data for all indicators

    Returns:
        df (DataFrame) with all indicator columns, or None if failed
    """
    try:
        # Download historical data
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)

        # Skip if too little data
        if len(df) < 210:
            return None

        # Flatten multi-level columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Drop any rows with missing OHLCV values
        df.dropna(subset=['Open','High','Low','Close','Volume'], inplace=True)

        if len(df) < 210:
            return None

        # ── Calculate all indicators ──

        # Trend
        df['SMA_20']  = calc_sma(df['Close'], 20)
        df['SMA_50']  = calc_sma(df['Close'], 50)
        df['SMA_200'] = calc_sma(df['Close'], 200)

        # Momentum
        df['RSI'] = calc_rsi(df['Close'], 14)

        # MACD
        df['MACD'], df['Signal'], df['Histogram'] = calc_macd(df['Close'])

        # Bollinger Bands
        df['BB_Mid'], df['BB_Up'], df['BB_Lo'], df['PctB'], df['BW'] = calc_bollinger(df['Close'])

        # Volume
        df['VMA']       = calc_sma(df['Volume'].astype(float), 20)
        df['Vol_Ratio'] = df['Volume'] / df['VMA']

        # OBV
        df['OBV'] = calc_obv(df['Close'], df['Volume'])

        # MFI
        df['MFI'] = calc_mfi(df, period=14)

        return df

    except Exception:
        # Silently skip failed downloads
        return None


# ════════════════════════════════════════════════════════════
# SECTION 6 — MAIN SCREENER
# ════════════════════════════════════════════════════════════

def run_screener(tickers, index_name="Nifty 50", top_n=15):
    """
    Main screening function — loops through all tickers,
    scores each one, ranks them, and returns the top picks.

    Parameters:
        tickers (list): List of NSE ticker symbols
        index_name (str): Label for the output
        top_n (int): How many top stocks to show

    Returns:
        results_df (DataFrame): All scored stocks sorted by score
    """

    print(f"\n{'='*65}")
    print(f"  NIFTY STOCK SCREENER — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Index: {index_name} | Stocks: {len(tickers)}")
    print(f"{'='*65}")
    print(f"\n  Scanning {len(tickers)} stocks...\n")

    results = []
    failed  = []

    for idx, ticker in enumerate(tickers):
        # Progress indicator
        pct  = int((idx + 1) / len(tickers) * 30)
        bar  = '█' * pct + '░' * (30 - pct)
        print(f"\r  [{bar}] {idx+1}/{len(tickers)} — {ticker:<20}", end='', flush=True)

        # Download and process
        df = download_and_process(ticker, period="1y")   # 1 year for SMA 200

        if df is None:
            failed.append(ticker)
            continue

        # Score the stock
        result = score_stock(df, ticker)

        if result is not None:
            results.append(result)

        # Small delay to be respectful to Yahoo Finance
        time.sleep(0.15)

    print(f"\n\n  Scanned {len(results)} stocks successfully ({len(failed)} failed)")

    if not results:
        print("  No results — check internet connection")
        return pd.DataFrame()

    # Convert to DataFrame and sort by score (descending), then RSI
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(
        by=['Score', 'Vol_Ratio'],
        ascending=[False, False]
    ).reset_index(drop=True)

    return results_df


# ════════════════════════════════════════════════════════════
# SECTION 7 — OUTPUT: PRINT, SAVE, CHART
# ════════════════════════════════════════════════════════════

def print_watchlist(results_df, top_n=15):
    """
    Prints a clean, formatted watchlist table to the console.

    Parameters:
        results_df (DataFrame): All scored stocks
        top_n (int): How many to display
    """

    top = results_df.head(top_n)

    print(f"\n{'='*95}")
    print(f"  TOP {top_n} STOCKS — TODAY'S WATCHLIST")
    print(f"{'='*95}")
    print(f"  {'#':<3} {'Ticker':<12} {'Score':>5} {'Close':>8} {'RSI':>5} {'MFI':>5} "
          f"{'Vol':>5} {'1M%':>6} {'52wH%':>7}  Signals")
    print(f"  {'-'*93}")

    for rank, row in top.iterrows():
        # Color-code score (text markers since terminal may not support colors)
        score_str = f"{'★'*row['Score']:<8}" if row['Score'] >= 6 else f"{row['Score']}/8"

        print(
            f"  {rank+1:<3} {row['Ticker']:<12} {row['Score']:>3}/8  "
            f"₹{row['Close']:>7.1f}  {row['RSI']:>4.1f}  {row['MFI']:>4.1f}  "
            f"{row['Vol_Ratio']:>4.1f}x  {row['1M_Chg%']:>+5.1f}%  {row['From52wHigh%']:>+6.1f}%"
        )
        # Print signals on next line, indented
        print(f"       {row['Signals'][:85]}")
        print()

    print(f"{'='*95}")


def print_market_summary(results_df):
    """
    Prints a market-wide summary:
    how many stocks are in each signal strength bucket,
    which sectors seem strong, and overall market mood.

    Parameters:
        results_df (DataFrame): All scored stocks
    """

    total    = len(results_df)
    strong   = len(results_df[results_df['Score'] >= 6])
    moderate = len(results_df[(results_df['Score'] >= 4) & (results_df['Score'] < 6)])
    weak     = len(results_df[results_df['Score'] < 4])

    # Average RSI tells us overall market temperature
    avg_rsi = results_df['RSI'].mean()

    # % of stocks in uptrend (above SMA 200 implied by high scores)
    # We use 1M change as a proxy
    pct_advancing = len(results_df[results_df['1M_Chg%'] > 0]) / total * 100

    print(f"\n  ── Market Summary ──")
    print(f"  Total stocks scanned      : {total}")
    print(f"  Strong signals (6–8/8)    : {strong}  ({round(strong/total*100,1)}%)")
    print(f"  Moderate signals (4–5/8)  : {moderate}  ({round(moderate/total*100,1)}%)")
    print(f"  Weak / no signal (0–3/8)  : {weak}  ({round(weak/total*100,1)}%)")
    print(f"  Average RSI (universe)    : {round(avg_rsi,1)}")
    print(f"  Stocks up in last month   : {round(pct_advancing,1)}%")

    # Overall market mood interpretation
    if avg_rsi > 60 and pct_advancing > 60:
        mood = "BULLISH — Most stocks are trending up. Be selective, avoid overbought entries."
    elif avg_rsi < 40 and pct_advancing < 40:
        mood = "BEARISH — Market under pressure. Only trade highest-conviction setups."
    elif strong > total * 0.2:
        mood = "BULLISH BIAS — Many stocks setting up. Good conditions for swing trades."
    else:
        mood = "NEUTRAL — Mixed signals. Wait for clearer setups before committing capital."

    print(f"\n  Market mood: {mood}")
    print(f"\n  NOTE: Always check news and upcoming results before entering any trade.")
    print(f"        Use these as a STARTING POINT for deeper analysis, not final buy signals.")


def save_results(results_df, index_name):
    """
    Saves the full results to a CSV file for further analysis.
    The CSV can be opened in Excel for custom filtering.

    Parameters:
        results_df (DataFrame): All scored stocks
        index_name (str): Used in filename
    """

    filename = f"screener_results_{index_name}_{datetime.now().strftime('%Y%m%d')}.csv"

    # Select and reorder columns for the CSV
    cols = ['Ticker', 'Score', 'Close', 'RSI', 'MFI', 'MACD',
            'PctB', 'Vol_Ratio', '1M_Chg%', 'From52wHigh%', 'Signals']

    results_df[cols].to_csv(filename, index=False)
    print(f"\n  Full results saved to: {filename}")
    print(f"  Open this file in Excel to sort/filter by any column.")


def plot_screener_results(results_df, top_n=15):
    """
    Creates a dashboard chart with:
        Left:  Score distribution bar chart (how many stocks at each score level)
        Right: Top N stocks bar chart with RSI color coding

    Parameters:
        results_df (DataFrame): All scored stocks
        top_n (int): How many top stocks to show on right panel
    """

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # ── Left: Score distribution ──
    score_counts = results_df['Score'].value_counts().sort_index()
    colors = ['#E24B4A', '#E24B4A', '#E24B4A', '#EF9F27',
              '#EF9F27', '#1D9E75', '#1D9E75', '#085041', '#085041']

    ax1.bar(score_counts.index, score_counts.values,
            color=[colors[s] for s in score_counts.index],
            alpha=0.85, edgecolor='white', linewidth=0.5)

    ax1.set_xlabel('Signal Score (0–8)', fontsize=11)
    ax1.set_ylabel('Number of Stocks', fontsize=11)
    ax1.set_title('Score Distribution Across Universe', fontsize=12, pad=10)
    ax1.set_xticks(range(9))
    ax1.grid(True, alpha=0.25, axis='y')

    # Add count labels on top of each bar
    for score, count in score_counts.items():
        ax1.text(score, count + 0.3, str(count),
                 ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Color legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#1D9E75', alpha=0.85, label='Strong (5–8)'),
        Patch(facecolor='#EF9F27', alpha=0.85, label='Moderate (3–4)'),
        Patch(facecolor='#E24B4A', alpha=0.85, label='Weak (0–2)'),
    ]
    ax1.legend(handles=legend_elements, fontsize=9, loc='upper right')

    # ── Right: Top N stocks ──
    top = results_df.head(top_n).copy()
    top_labels  = top['Ticker'].values
    top_scores  = top['Score'].values
    top_rsi     = top['RSI'].values

    # Color bars by RSI: green = oversold, amber = neutral, red = overbought
    bar_colors = []
    for rsi in top_rsi:
        if rsi < 40:
            bar_colors.append('#1D9E75')   # Oversold — good entry
        elif rsi < 60:
            bar_colors.append('#378ADD')   # Neutral — watch
        else:
            bar_colors.append('#EF9F27')   # Getting hot — be careful

    y_pos = range(len(top_labels))
    ax2.barh(y_pos, top_scores, color=bar_colors, alpha=0.85,
             edgecolor='white', linewidth=0.5, height=0.6)

    # Add RSI labels on the right
    for i, (score, rsi) in enumerate(zip(top_scores, top_rsi)):
        ax2.text(score + 0.05, i, f'RSI={rsi}',
                 va='center', fontsize=8, color='#444441')

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(top_labels, fontsize=9)
    ax2.set_xlabel('Signal Score', fontsize=11)
    ax2.set_title(f'Top {top_n} Stocks by Score', fontsize=12, pad=10)
    ax2.set_xlim(0, 9.5)
    ax2.axvline(x=6, color='#1D9E75', linewidth=1, linestyle='--',
                alpha=0.7, label='Strong threshold (6)')
    ax2.grid(True, alpha=0.25, axis='x')
    ax2.legend(fontsize=9)
    ax2.invert_yaxis()   # Highest score at top

    plt.suptitle(f"Daily Stock Screener — {datetime.now().strftime('%d %B %Y')}",
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    filename = f"screener_chart_{datetime.now().strftime('%Y%m%d')}.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"  Chart saved as: {filename}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 8 — MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════

def main():
    """
    Main entry point — parses command line arguments and runs the screener.

    Usage:
        python screener.py                       → Nifty 50 (default, fast)
        python screener.py --index nifty100      → Nifty 100
        python screener.py --index nifty500      → Full sample (~500 stocks)
        python screener.py --ticker RELIANCE.NS  → Single stock deep dive
    """

    # ── Parse command line arguments ──
    args = sys.argv[1:]

    # Default: scan Nifty 50
    index_name = 'nifty50'
    single_ticker = None

    # Check for --index flag
    if '--index' in args:
        idx = args.index('--index')
        if idx + 1 < len(args):
            index_name = args[idx + 1].lower()

    # Check for --ticker flag (scan a single stock)
    if '--ticker' in args:
        idx = args.index('--ticker')
        if idx + 1 < len(args):
            t = args[idx + 1]
            if not t.endswith('.NS'):
                t = t + '.NS'
            single_ticker = t

    # ── Select the ticker list ──
    if single_ticker:
        tickers    = [single_ticker]
        label      = single_ticker.replace('.NS', '')
    else:
        tickers    = INDEX_MAP.get(index_name, NIFTY_50)
        label      = index_name.upper()

    # ── Run the screener ──
    results_df = run_screener(tickers, index_name=label, top_n=15)

    if results_df.empty:
        print("\n  No results. Exiting.")
        return

    # ── Output ──
    print_watchlist(results_df, top_n=15)
    print_market_summary(results_df)
    save_results(results_df, index_name)
    plot_screener_results(results_df, top_n=15)

    print(f"\n  Screener complete. Good trading!\n")


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()