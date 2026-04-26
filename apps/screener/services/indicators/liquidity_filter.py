# ============================================================
# LIQUIDITY FILTER MODULE
# Add this to screener_v2.py or use standalone
# ============================================================
#
# Three liquidity measures:
#   1. Average Daily Value (ADV)   — rupee volume filter
#   2. Amihud Illiquidity Ratio    — price impact per rupee
#   3. Volume Consistency Score    — does volume hold up daily?
#
# HOW TO USE:
#   Option A: Import into screener_v2.py:
#       from liquidity_filter import check_liquidity, LIQUIDITY_PRESETS
#
#   Option B: Copy the functions directly into screener_v2.py
#
# RUN STANDALONE:
#   python liquidity_filter.py
#   python liquidity_filter.py SBIN large
#   python liquidity_filter.py TATAMOTORS medium
# ============================================================


import pandas as pd
import numpy as np
import yfinance as yf
import sys
import warnings

warnings.filterwarnings('ignore')


# ════════════════════════════════════════════════════════════
# SECTION 1 — CONFIGURATION PRESETS
# Choose based on your typical trade size in rupees
# ════════════════════════════════════════════════════════════

LIQUIDITY_PRESETS = {

    'small': {
        # Retail traders with up to Rs 50,000 per trade
        'min_adv_crores'     : 0.5,     # Rs 50 lakh/day minimum
        'min_avg_volume'     : 25000,   # 25,000 shares/day minimum
        'max_amihud'         : 0.5,     # Max illiquidity ratio
        'min_consistency_pct': 60,      # Active on 60% of days
        'description'        : 'Small retail (up to Rs 50k per trade)',
    },

    'medium': {
        # Traders with Rs 50,000 to Rs 2,00,000 per trade
        'min_adv_crores'     : 2.0,     # Rs 2 crore/day minimum
        'min_avg_volume'     : 75000,   # 75,000 shares/day minimum
        'max_amihud'         : 0.2,     # Stricter impact cost
        'min_consistency_pct': 70,      # Active on 70% of days
        'description'        : 'Medium retail (Rs 50k-2L per trade)',
    },

    'large': {
        # Traders with Rs 2,00,000 to Rs 10,00,000 per trade
        'min_adv_crores'     : 10.0,    # Rs 10 crore/day minimum
        'min_avg_volume'     : 200000,  # 2 lakh shares/day minimum
        'max_amihud'         : 0.05,    # Very low impact cost
        'min_consistency_pct': 80,      # Active on 80% of days
        'description'        : 'Large retail (Rs 2L-10L per trade)',
    },

    'institutional': {
        # HNI or institutional with Rs 10,00,000+ per trade
        'min_adv_crores'     : 50.0,    # Rs 50 crore/day minimum
        'min_avg_volume'     : 500000,  # 5 lakh shares/day minimum
        'max_amihud'         : 0.01,    # Near-zero impact cost
        'min_consistency_pct': 90,      # Active on 90% of days
        'description'        : 'Institutional / HNI (Rs 10L+ per trade)',
    },
}


# ════════════════════════════════════════════════════════════
# SECTION 2 — MEASURE 1: AVERAGE DAILY VALUE (ADV)
# ════════════════════════════════════════════════════════════

def calc_adv(df, period=20):
    """
    Average Daily Value (ADV) — how many RUPEES trade each day.

    This is the most important liquidity measure for retail traders.
    It answers: is there enough money flowing through this stock that
    your order is invisible — that it does not move the price?

    The Rule of 1%:
        Your trade size should be less than 1% of the stock's ADV.
        If you want to trade Rs 1 lakh, the stock needs Rs 1 crore/day ADV.
        If you want to trade Rs 5 lakh, the stock needs Rs 5 crore/day ADV.

    Why rupees instead of shares?
        Share count alone is misleading:
        - Stock A: 1,00,000 shares at Rs 10 = Rs 10 lakh/day (illiquid)
        - Stock B: 1,00,000 shares at Rs 1000 = Rs 10 crore/day (liquid)
        Same share count, 100x difference in actual tradeable liquidity.

    Parameters:
        df (DataFrame): Must have Close and Volume columns
        period (int): Rolling average period (default 20 = 1 month)

    Returns:
        dict with adv_crores, adv_shares, daily_value series
    """

    # Rupees traded each day = closing price times shares traded
    daily_value = df['Close'] * df['Volume']

    # Rolling 20-day mean to smooth out unusual days
    adv_rupees = daily_value.rolling(window=period, min_periods=period).mean()

    # Convert to crores for readable numbers (1 crore = 10 million)
    adv_crores = adv_rupees / 1e7

    # Average shares per day
    adv_shares = df['Volume'].rolling(window=period, min_periods=period).mean()

    latest_crores = adv_crores.iloc[-1]
    latest_shares = adv_shares.iloc[-1]

    return {
        'adv_crores' : round(latest_crores, 2) if not pd.isna(latest_crores) else 0.0,
        'adv_shares' : int(latest_shares)       if not pd.isna(latest_shares) else 0,
        'daily_value': daily_value,
    }


# ════════════════════════════════════════════════════════════
# SECTION 3 — MEASURE 2: AMIHUD ILLIQUIDITY RATIO
# ════════════════════════════════════════════════════════════

def calc_amihud(df, period=20):
    """
    Amihud Illiquidity Ratio — price impact per unit of volume.

    Created by Professor Yakov Amihud (2002, Journal of Financial Markets).
    Used by fund managers and researchers worldwide to measure how much
    the price of a stock moves in response to trading activity.

    The core question this answers:
        If I put Rs 1 lakh into this stock right now,
        by how much will the price move against me?

    Formula:
        For each day:
            |Return| = |Close / Close[yesterday] - 1|
            Volume in crores = (Close x Volume) / 1 crore
            Daily Amihud = |Return| / Volume in crores

        Amihud(N) = Average of daily Amihud over N days

    Reading the ratio:
        Near 0.00 : Extremely liquid. HDFC Bank, Reliance — massive
                    daily volume, price barely responds to any single trade.
                    You can enter and exit without any price impact.

        0.01-0.10 : Very liquid. Most Nifty 100 stocks.
                    Your Rs 1-2 lakh order is completely invisible.

        0.10-0.30 : Liquid. Nifty 500 stocks.
                    Manageable for retail traders, be mindful of size.

        0.30-0.50 : Moderately illiquid.
                    Your order will move the price slightly. Use limits.

        Above 0.50: Illiquid. Every Rs 1 lakh you trade causes noticeable
                    price movement. Impact cost eats your profits.

        Above 1.00: Very illiquid. Avoid unless you are an expert
                    trading very small position sizes.

    Parameters:
        df (DataFrame): Must have Close and Volume columns
        period (int): Rolling average period (default 20)

    Returns:
        float: Amihud ratio (lower is more liquid, better)
    """

    close = df['Close']

    # Absolute daily return — how much did price move today?
    abs_return = (close / close.shift(1) - 1).abs()

    # Rupee volume in crores — how much money changed hands?
    rupee_vol_crores = (close * df['Volume']) / 1e7
    rupee_vol_crores = rupee_vol_crores.replace(0, float('nan'))

    # Amihud for each day: price move per crore of volume
    daily_amihud = abs_return / rupee_vol_crores

    # Remove extreme outliers — one unusual day should not skew the average
    # Cap at 99th percentile before averaging
    p99          = daily_amihud.quantile(0.99)
    daily_capped = daily_amihud.clip(upper=p99)

    # Rolling average over the period
    amihud_avg = daily_capped.rolling(window=period, min_periods=period).mean()

    result = amihud_avg.iloc[-1]
    return round(result, 4) if not pd.isna(result) else 999.0


# ════════════════════════════════════════════════════════════
# SECTION 4 — MEASURE 3: VOLUME CONSISTENCY
# ════════════════════════════════════════════════════════════

def calc_volume_consistency(df, min_volume=10000, period=60):
    """
    Volume Consistency — does this stock actually trade every day?

    Average volume can be dangerously misleading.

    Example of the trap:
        Day 1 to 58 : 2,000 shares/day  (near-zero liquidity)
        Day 59       : 5,00,00,000 shares (block deal — one-off event)
        Day 60       : 3,000 shares/day  (back to nothing)
        Average      : ~87,000 shares/day
        Looks liquid but is NOT liquid.

    Volume consistency fixes this by asking:
        On what percentage of recent days did the stock
        actually trade above a meaningful minimum volume?

    If a stock trades above the minimum on only 30% of days,
    its average volume number is completely meaningless for you
    as a trader who needs to execute every day.

    Parameters:
        df (DataFrame): Must have Volume column
        min_volume (int): Minimum acceptable daily shares (default 10,000)
        period (int): How many recent days to analyse (default 60)

    Returns:
        dict with consistency_pct, zero_volume_days, is_consistent
    """

    # Use the most recent 'period' days
    recent_vol = df['Volume'].iloc[-period:]

    # What fraction of days had volume above the threshold?
    days_above  = (recent_vol >= min_volume).sum()
    total_days  = len(recent_vol)
    consistency = round((days_above / total_days) * 100, 1)

    # Count truly dead days (zero volume = circuit filters, suspension, etc.)
    zero_days = (recent_vol == 0).sum()

    return {
        'consistency_pct' : consistency,
        'zero_volume_days': int(zero_days),
        'is_consistent'   : consistency >= 70,
    }


# ════════════════════════════════════════════════════════════
# SECTION 5 — MASTER LIQUIDITY CHECK
# This is the single function you call from the screener
# ════════════════════════════════════════════════════════════

def check_liquidity(df, ticker, preset='medium'):
    """
    Master liquidity check — runs all three measures and returns
    a pass/fail decision with detailed diagnostic information.

    Call this BEFORE running any indicator scoring on a stock.
    If liquidity fails, skip the stock completely — no point
    calculating 13 indicators on a stock you cannot actually trade.

    Time saved: calculating all indicators takes ~0.5s per stock.
    The liquidity check takes ~0.01s. Filtering out illiquid stocks
    early saves significant time on a 500-stock scan.

    Parameters:
        df (DataFrame): OHLCV data (needs at least 20 rows)
        ticker (str): Stock symbol for human-readable messages
        preset (str): 'small', 'medium', 'large', 'institutional'

    Returns:
        dict with:
            passes (bool)      : True = liquid enough to trade your size
            adv_crores (float) : Average daily value in crores
            adv_shares (int)   : Average daily shares
            amihud (float)     : Amihud illiquidity ratio
            consistency (float): Percentage of days above minimum volume
            zero_days (int)    : Days with zero volume in last 60 days
            reasons (list)     : Human-readable strings for each failure
            grade (str)        : 'A', 'B', 'C', 'D', or 'F'
    """

    config  = LIQUIDITY_PRESETS.get(preset, LIQUIDITY_PRESETS['medium'])
    reasons = []
    passes  = True

    # Need at least 20 days of data to be meaningful
    if len(df) < 20:
        return {
            'passes'     : False,
            'adv_crores' : 0,
            'adv_shares' : 0,
            'amihud'     : 999,
            'consistency': 0,
            'zero_days'  : 0,
            'reasons'    : ['Insufficient data — need at least 20 days'],
            'grade'      : 'F',
        }

    # ── Check 1: Average Daily Value ──────────────────────────
    adv        = calc_adv(df, period=20)
    adv_crores = adv['adv_crores']
    adv_shares = adv['adv_shares']

    if adv_crores < config['min_adv_crores']:
        passes = False
        reasons.append(
            f"ADV Rs{adv_crores:.1f}Cr < required Rs{config['min_adv_crores']}Cr/day"
        )

    if adv_shares < config['min_avg_volume']:
        passes = False
        reasons.append(
            f"Avg volume {adv_shares:,} shares < required {config['min_avg_volume']:,}/day"
        )

    # ── Check 2: Amihud Illiquidity Ratio ─────────────────────
    amihud = calc_amihud(df, period=20)

    if amihud > config['max_amihud']:
        passes = False
        reasons.append(
            f"Amihud {amihud:.3f} > max {config['max_amihud']} "
            f"(price moves too much per unit of volume)"
        )

    # ── Check 3: Volume Consistency ───────────────────────────
    min_threshold = max(config['min_avg_volume'] // 5, 5000)
    consistency   = calc_volume_consistency(
        df,
        min_volume=min_threshold,
        period=min(60, len(df))
    )

    if consistency['consistency_pct'] < config['min_consistency_pct']:
        passes = False
        reasons.append(
            f"Volume consistency {consistency['consistency_pct']}% "
            f"< required {config['min_consistency_pct']}% "
            f"(stock does not trade reliably every day)"
        )

    if consistency['zero_volume_days'] > 3:
        passes = False
        reasons.append(
            f"{consistency['zero_volume_days']} zero-volume days in last 60 days "
            f"(possible circuit filters or trading halt history)"
        )

    # ── Assign a Liquidity Grade ───────────────────────────────
    # Grade reflects how far above or below the thresholds the stock sits
    # A stock 5x above threshold is much more comfortably liquid than
    # a stock just barely passing
    adv_ratio   = adv_crores / max(config['min_adv_crores'], 0.01)
    ami_ratio   = config['max_amihud'] / max(amihud, 0.001)
    cons_ratio  = consistency['consistency_pct'] / 100

    # Weighted composite: ADV most important, then Amihud, then consistency
    composite = adv_ratio * 0.5 + ami_ratio * 0.3 + cons_ratio * 0.2

    if composite >= 5.0:   grade = 'A'   # Extremely liquid
    elif composite >= 2.0: grade = 'B'   # Very liquid
    elif composite >= 1.0: grade = 'C'   # Adequately liquid
    elif composite >= 0.5: grade = 'D'   # Borderline
    else:                  grade = 'F'   # Illiquid — reject

    return {
        'passes'     : passes,
        'adv_crores' : adv_crores,
        'adv_shares' : adv_shares,
        'amihud'     : amihud,
        'consistency': consistency['consistency_pct'],
        'zero_days'  : consistency['zero_volume_days'],
        'reasons'    : reasons,
        'grade'      : grade,
    }


# ════════════════════════════════════════════════════════════
# SECTION 6 — HOW TO INTEGRATE INTO screener_v2.py
# ════════════════════════════════════════════════════════════

INTEGRATION_GUIDE = """
STEP 1 — Import at top of screener_v2.py:
──────────────────────────────────────────────────────────
    from liquidity_filter import check_liquidity, LIQUIDITY_PRESETS

STEP 2 — Add preset selection in main():
──────────────────────────────────────────────────────────
    # Add this near the top of main() or as a command-line argument
    LIQUIDITY_PRESET = 'medium'   # change to 'small', 'large', etc.

STEP 3 — Add to run_screener() BEFORE scoring:
──────────────────────────────────────────────────────────
    # Existing code:
    df = download_and_calculate(ticker, period="1y")
    if df is None:
        failed.append(ticker)
        continue

    # NEW — add these lines right here:
    liq = check_liquidity(df, ticker, preset=LIQUIDITY_PRESET)
    if not liq['passes']:
        illiquid.append({
            'Ticker' : ticker.replace('.NS', ''),
            'ADV_Cr' : liq['adv_crores'],
            'Grade'  : liq['grade'],
            'Reason' : liq['reasons'][0] if liq['reasons'] else '',
        })
        continue   # Skip indicator scoring entirely

    # Existing code continues:
    result = score_stock(df, ticker)

STEP 4 — Add liquidity info to the score_stock() return dict:
──────────────────────────────────────────────────────────
    return {
        'Ticker'      : ticker.replace('.NS', ''),
        'Score'       : score,
        'Liq_Grade'   : liq['grade'],      # ADD
        'ADV_Crores'  : liq['adv_crores'], # ADD
        ... rest of existing fields ...
    }

STEP 5 — Show skipped stocks in print_market_summary():
──────────────────────────────────────────────────────────
    if illiquid:
        print(f"  Stocks skipped (illiquid): {len(illiquid)}")
        for s in illiquid[:5]:
            print(f"    {s['Ticker']:<15} Rs{s['ADV_Cr']}Cr/day  {s['Reason']}")

STEP 6 — Update the watchlist header to show grade:
──────────────────────────────────────────────────────────
    # In print_watchlist(), change the header line to include [Grade]:
    print(f"  {'#'} {'Ticker':<12} {'Score':>6} {'Liq':>4} ...")
    print(f"  {rank+1} {row['Ticker']:<12} {row['Score']:>4}/13  "
          f"[{row.get('Liq_Grade','?')}] ...")
"""


# ════════════════════════════════════════════════════════════
# SECTION 7 — STANDALONE DEMO
# ════════════════════════════════════════════════════════════

def demo():
    """
    Demonstrates the liquidity filter on a single stock.
    """
    ticker_input = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    preset       = sys.argv[2] if len(sys.argv) > 2 else "medium"

    if preset not in LIQUIDITY_PRESETS:
        print(f"Unknown preset '{preset}'. Use: small, medium, large, institutional")
        return

    ticker = ticker_input.upper()
    if not ticker.endswith('.NS'):
        ticker += '.NS'

    config = LIQUIDITY_PRESETS[preset]

    print(f"\n{'='*62}")
    print(f"  LIQUIDITY ANALYSIS — {ticker}")
    print(f"  Preset: {preset.upper()} — {config['description']}")
    print(f"{'='*62}")

    print(f"\n  Downloading 3 months of data...")
    df = yf.download(ticker, period="3mo", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)

    if len(df) < 20:
        print("  Insufficient data downloaded.")
        return

    result = check_liquidity(df, ticker, preset=preset)

    # Overall result
    verdict = "PASSES - liquid enough to trade" if result['passes'] else "FAILS - do not trade this size"
    print(f"\n  Overall : {verdict}")
    print(f"  Grade   : {result['grade']}  (A=best, F=fail)")

    # Detailed measures
    print(f"\n  ── Measure 1: Average Daily Value ──")
    print(f"  ADV            : Rs {result['adv_crores']:.2f} crore/day")
    print(f"  Avg shares     : {result['adv_shares']:,} shares/day")
    print(f"  Required       : Rs {config['min_adv_crores']} crore / "
          f"{config['min_avg_volume']:,} shares")

    adv_ok = (result['adv_crores'] >= config['min_adv_crores'] and
              result['adv_shares'] >= config['min_avg_volume'])
    print(f"  Status         : {'PASS' if adv_ok else 'FAIL'}")

    print(f"\n  ── Measure 2: Amihud Illiquidity Ratio ──")
    amihud_interp = (
        "Extremely liquid" if result['amihud'] < 0.01 else
        "Very liquid"      if result['amihud'] < 0.10 else
        "Liquid"           if result['amihud'] < 0.30 else
        "Moderately illiquid" if result['amihud'] < 0.50 else
        "Illiquid"
    )
    print(f"  Amihud ratio   : {result['amihud']:.4f}  ({amihud_interp})")
    print(f"  Required max   : {config['max_amihud']}")
    print(f"  Status         : {'PASS' if result['amihud'] <= config['max_amihud'] else 'FAIL'}")

    print(f"\n  ── Measure 3: Volume Consistency ──")
    print(f"  Consistency    : {result['consistency']:.1f}% of days above minimum")
    print(f"  Zero-vol days  : {result['zero_days']} in last 60 days")
    print(f"  Required       : {config['min_consistency_pct']}% consistency, 0-3 zero days")
    cons_ok = (result['consistency'] >= config['min_consistency_pct'] and
               result['zero_days'] <= 3)
    print(f"  Status         : {'PASS' if cons_ok else 'FAIL'}")

    if result['reasons']:
        print(f"\n  ── Failure Reasons ──")
        for r in result['reasons']:
            print(f"  x {r}")
    else:
        print(f"\n  All three liquidity checks passed.")

    # Practical implication
    print(f"\n  ── What This Means Practically ──")
    adv_rs = result['adv_crores'] * 1e7
    max_safe_trade = adv_rs * 0.01   # 1% of ADV rule
    print(f"  Max safe trade size : Rs {max_safe_trade:,.0f}")
    print(f"  (1% of daily ADV — your order stays invisible to the market)")

    print(f"\n{'='*62}\n")


if __name__ == "__main__":
    demo()