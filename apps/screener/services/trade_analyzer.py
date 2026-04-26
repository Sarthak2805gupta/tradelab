# ============================================================
# TRADE ANALYZER — trade_analyzer.py
# ============================================================
#
# PURPOSE:
#   Takes screener output (CSV or ticker list) and automatically
#   answers the three questions for every candidate:
#     1. Is the entry clean?
#     2. Is there room to run?
#     3. Does the R:R justify the trade?
#
# If all three pass → prints a complete TRADE SETUP card
# If any fails     → prints SKIP with the exact reason
#
# HOW TO USE:
#   # After running screener_v3.py which saves a CSV:
#   python trade_analyzer.py --csv screener_v3_nifty50_20260409.csv
#
#   # Or pass tickers directly:
#   python trade_analyzer.py --tickers HDFCBANK TITAN ICICIBANK
#
#   # Or pipe screener output (run both together):
#   python trade_analyzer.py --index nifty50
#
# CONFIGURE at top of file:
#   RISK_PER_TRADE  → your max loss per trade in rupees
#   MIN_RR          → minimum reward:risk ratio (default 2.0)
#   ATR_STOP_MULT   → how many ATRs below entry for stop (default 2.0)
#   MIN_ROOM_PCT    → minimum % room to nearest resistance (default 4.0)
#
# REQUIRES:
#   complete_indicators.py, indicators_extension.py in same folder
# ============================================================

import yfinance as yf
import pandas as pd
import numpy as np
import sys
import os
import warnings
import glob
from datetime import datetime

warnings.filterwarnings('ignore')

# ── Import indicators ──────────────────────────────────────
from complete_indicators import (
    calc_sma, calc_ema, calc_rsi, calc_atr,
    calc_bollinger, calc_donchian, calc_supertrend, calc_adx,
    calc_obv, calc_macd,
)
from indicators_extension import (
    calc_pivot_points, calc_camarilla_pivots, auto_fibonacci,
)

# ════════════════════════════════════════════════════════════
# SECTION 1 — CONFIGURATION
# Edit these values to match your trading style
# ════════════════════════════════════════════════════════════

CONFIG = {
    # ── Risk management ──────────────────────────────────────
    'RISK_PER_TRADE'    : 2000,   # Rs 2,000 max loss per trade
                                  # This determines your position size

    'ATR_STOP_MULT'     : 2.0,    # Stop loss = Entry − (ATR_STOP_MULT × ATR)
                                  # 2.0 = keeps stop outside normal daily noise
                                  # 1.5 = tighter stop, smaller position
                                  # 2.5 = wider stop, safer but smaller size

    'MIN_RR'            : 2.0,    # Minimum Reward:Risk ratio to take a trade
                                  # 2.0 = target must be 2× the stop distance
                                  # 2.5 = more selective, fewer but better trades

    # ── Entry quality ─────────────────────────────────────────
    'MAX_FROM_SUPPORT'  : 5.0,    # % — max distance price can be FROM support
                                  # If price is 6% above SMA20, entry is "late"
                                  # Lower = stricter (need to be closer to support)

    'MIN_ROOM_PCT'      : 4.0,    # % — minimum clear room to nearest resistance
                                  # If nearest resistance is only 2% away, skip
                                  # This ensures the target has enough space

    'MAX_RSI_ENTRY'     : 62,     # RSI must be below this for a clean entry
                                  # Above 62 = already extended, late entry

    'MIN_RSI_ENTRY'     : 25,     # RSI must be above this (too oversold = danger)

    # ── Volume filter ─────────────────────────────────────────
    'VOL_DECLINING_DAYS': 5,      # Check if volume declined over last N days
                                  # of pullback (healthy pullback = low volume)

    # ── Output ────────────────────────────────────────────────
    'SHOW_SKIPPED'      : True,   # Show WHY each stock was skipped
    'TOP_N'             : 10,     # Max trade setups to show
}



# ════════════════════════════════════════════════════════════
# SECTION 2 — DATA DOWNLOAD
# ════════════════════════════════════════════════════════════

def get_data(ticker, period='6mo', raw_df=None):
    """Downloads OHLCV (or uses a pre-loaded DataFrame) and calculates all indicators needed."""
    try:
        if raw_df is not None:
            # Use caller-supplied OHLCV — avoids a network round-trip
            df = raw_df.copy()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.dropna(inplace=True)
        else:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.dropna(inplace=True)
        if len(df) < 60:
            return None

        # Core indicators
        df['SMA_20']  = calc_sma(df['Close'], 20)
        df['SMA_50']  = calc_sma(df['Close'], 50)
        df['SMA_200'] = calc_sma(df['Close'], 200)
        df['EMA_9']   = calc_ema(df['Close'], 9)
        df['RSI']     = calc_rsi(df['Close'], 14)
        df['ATR']     = calc_atr(df, 14)
        df['VMA_20']  = calc_sma(df['Volume'].astype(float), 20)
        df['Vol_Ratio'] = df['Volume'] / df['VMA_20']

        # Donchian for resistance detection
        df['DC_Up'], df['DC_Mid'], df['DC_Lo'] = calc_donchian(df, 20)

        # Bollinger for support/resistance
        (df['BB_Mid'], df['BB_Up'], df['BB_Lo'],
         df['PctB'],   df['BW']) = calc_bollinger(df['Close'])

        # Supertrend (direction + level)
        df['ST_Line'], df['ST_Dir'] = calc_supertrend(df, 7, 3.0)

        # ADX for trend strength
        df['ADX'], df['DI_Plus'], df['DI_Minus'] = calc_adx(df, 14)

        # OBV for volume trend
        df['OBV'] = calc_obv(df['Close'], df['Volume'])

        # MACD
        df['MACD'], df['MACD_Sig'], df['MACD_Hist'] = calc_macd(df['Close'])

        # Pivot points — calc returns a DataFrame; take last row as plain float dict
        pivots_df    = calc_pivot_points(df)
        camarilla_df = calc_camarilla_pivots(df)
        pivots    = {k: float(v) for k, v in pivots_df.iloc[-1].items()    if not pd.isna(v)}
        camarilla = {k: float(v) for k, v in camarilla_df.iloc[-1].items() if not pd.isna(v)}

        # Fibonacci levels from recent swing
        try:
            fibs = auto_fibonacci(df, lookback=60)
        except Exception:
            fibs = {}

        return df, pivots, camarilla, fibs

    except Exception as e:
        return None


# ════════════════════════════════════════════════════════════
# SECTION 3 — SUPPORT DETECTION
# Finds the best support level near current price
# ════════════════════════════════════════════════════════════

def find_support_levels(df, pivots, fibs):
    """
    Identifies all potential support levels near current price.

    Support levels checked (in priority order):
        1. SMA 20 — first dynamic support in uptrend
        2. SMA 50 — medium-term trend support
        3. SMA 200 — long-term trend floor
        4. Pivot S1 — most-watched daily floor trader level
        5. Pivot S2 — secondary floor
        6. Supertrend line — trailing stop level
        7. Fibonacci 38.2% — shallow retracement support
        8. Fibonacci 61.8% — golden ratio support (strongest)
        9. Donchian mid — channel midline
        10. Bollinger Band lower — statistical floor

    Returns:
        List of (level_price, level_name, distance_pct) sorted by closeness
    """
    last = df.iloc[-1]
    close = float(last['Close'])
    levels = []

    def add(price, name):
        if price and not np.isnan(price) and price > 0:
            dist_pct = (close - price) / price * 100
            levels.append({
                'price'   : round(price, 2),
                'name'    : name,
                'dist_pct': round(dist_pct, 2),
            })

    # Dynamic MA supports
    add(float(last['SMA_20']),  'SMA 20')
    add(float(last['SMA_50']),  'SMA 50')
    add(float(last['SMA_200']), 'SMA 200')
    add(float(last['BB_Lo']),   'BB Lower')
    add(float(last['DC_Mid']),  'Donchian Mid')
    add(float(last['ST_Line']), 'Supertrend')

    # Pivot supports (today's levels)
    for key in ['S1', 'S2', 'S3']:
        val = pivots.get(key)
        if val:
            add(float(val), f'Pivot {key}')

    # Fibonacci supports
    for label, val in fibs.items():
        if any(x in label for x in ['38.2', '50.0', '61.8', '78.6']):
            if val and not np.isnan(val):
                add(float(val), f'Fib {label}')

    # Keep only levels BELOW current price (supports)
    supports = [l for l in levels if l['dist_pct'] >= 0]
    # Sort by closest to price
    supports.sort(key=lambda x: x['dist_pct'])
    return supports


# ════════════════════════════════════════════════════════════
# SECTION 4 — RESISTANCE DETECTION
# Finds the nearest resistance above current price
# ════════════════════════════════════════════════════════════

def find_resistance_levels(df, pivots, fibs):
    """
    Identifies all potential resistance levels above current price.

    Resistance levels checked:
        1. Pivot R1, R2 — most-watched intraday ceiling levels
        2. Donchian Upper — N-day high (breakout point)
        3. 52-week high — psychological ceiling
        4. Fibonacci extensions 127.2%, 161.8% — breakout targets
        5. Bollinger Band upper — statistical ceiling
        6. Round numbers (nearest Rs 50 / Rs 100 above price)

    Returns:
        List of (level, name, pct_away) sorted by nearest first
    """
    last = df.iloc[-1]
    close = float(last['Close'])

    high_52w = df['High'].iloc[-252:].max() if len(df) >= 252 else df['High'].max()

    levels = []

    def add(price, name):
        if price and not np.isnan(price) and price > close:
            dist_pct = (price - close) / close * 100
            levels.append({
                'price'   : round(price, 2),
                'name'    : name,
                'dist_pct': round(dist_pct, 2),
            })

    # Pivot resistances
    for key in ['R1', 'R2', 'R3']:
        val = pivots.get(key)
        if val:
            add(float(val), f'Pivot {key}')

    # Channel / band resistances
    add(float(last['DC_Up']),  'Donchian Upper (20d high)')
    add(float(last['BB_Up']),  'Bollinger Upper')
    add(float(high_52w),       '52-week High')

    # Fibonacci extensions (targets after breakout)
    for label, val in fibs.items():
        if any(x in label for x in ['127.2', '161.8', '261.8']):
            if val and not np.isnan(val):
                add(float(val), f'Fib {label}')

    # Psychological round number resistance
    # Nearest Rs 50 above price for stocks under Rs 500
    # Nearest Rs 100 above for stocks Rs 500-2000
    # Nearest Rs 500 above for stocks above Rs 2000
    step = 50 if close < 500 else (100 if close < 2000 else 500)
    round_level = (int(close / step) + 1) * step
    add(round_level, f'Round number (Rs{round_level})')

    # Sort by nearest
    levels.sort(key=lambda x: x['dist_pct'])
    return levels



# ════════════════════════════════════════════════════════════
# SECTION 5 — THE THREE QUESTIONS
# Each function returns (pass: bool, reason: str, detail: dict)
# ════════════════════════════════════════════════════════════

def q1_is_entry_clean(df, supports, config):
    """
    QUESTION 1: Is the entry clean?

    An entry is "clean" when price is at or near a logical support
    level — not chasing a stock that has already run significantly.

    Three sub-checks:
        A. Price is close to a support level (within MAX_FROM_SUPPORT %)
           → You are buying at support, not in the middle of nowhere
        B. RSI is in the buy zone (MIN_RSI to MAX_RSI)
           → Not overbought (chasing) or too oversold (danger)
        C. Pullback volume is declining (last N days)
           → Sellers are losing conviction, buyers about to take over

    Why each check matters:
        A. Buying at support gives you a natural stop loss level.
           Buying in the middle of a range means your stop is arbitrary.
        B. RSI above 62 = already extended. You're buying what everyone
           else already bought. RSI 30-55 = healthy pullback entry.
        C. Declining pullback volume is the most bullish pattern possible.
           It means: sellers are running out of shares to sell.
           When selling dries up in an uptrend, price bounces.
    """
    last   = df.iloc[-1]
    close  = float(last['Close'])
    rsi    = float(last['RSI']) if not pd.isna(last['RSI']) else 50
    atr    = float(last['ATR']) if not pd.isna(last['ATR']) else 0
    detail = {}

    # ── Sub-check A: Near support ────────────────────────────
    if not supports:
        return False, "No support levels found near price", detail

    nearest_support = supports[0]
    dist_from_support = nearest_support['dist_pct']
    detail['nearest_support'] = nearest_support

    if dist_from_support > config['MAX_FROM_SUPPORT']:
        return (False,
                f"Price too far from nearest support: "
                f"{dist_from_support:.1f}% above {nearest_support['name']} "
                f"(max allowed: {config['MAX_FROM_SUPPORT']}%)",
                detail)

    # ── Sub-check B: RSI in buy zone ─────────────────────────
    detail['rsi'] = round(rsi, 1)

    if rsi > config['MAX_RSI_ENTRY']:
        return (False,
                f"RSI too high for clean entry: RSI={round(rsi,1)} "
                f"(max: {config['MAX_RSI_ENTRY']}). Stock already extended.",
                detail)

    if rsi < config['MIN_RSI_ENTRY']:
        return (False,
                f"RSI dangerously low: RSI={round(rsi,1)} "
                f"(min: {config['MIN_RSI_ENTRY']}). Potential further downside.",
                detail)

    # ── Sub-check C: Pullback volume declining ────────────────
    n = config['VOL_DECLINING_DAYS']
    if len(df) >= n + 1:
        recent_vols = df['Volume'].iloc[-(n+1):].tolist()
        # Check if price has been in a pullback (lower closes)
        recent_closes = df['Close'].iloc[-(n+1):].tolist()
        in_pullback = recent_closes[-1] < recent_closes[0]   # price fell over period

        if in_pullback:
            # Volume should be declining during a healthy pullback
            vol_trend = np.polyfit(range(len(recent_vols)), recent_vols, 1)[0]
            vol_declining = vol_trend < 0
            detail['pullback_vol_declining'] = vol_declining
            if not vol_declining:
                # Volume rising on pullback = distribution, not healthy correction
                return (False,
                        f"Volume rising on pullback (selling pressure increasing). "
                        f"Wait for volume to dry up before entering.",
                        detail)
        else:
            detail['pullback_vol_declining'] = 'N/A (price not pulling back)'

    detail['entry_zone_low']  = round(close - 0.5 * atr, 2)
    detail['entry_zone_high'] = round(close + 0.2 * atr, 2)

    return (True,
            f"Entry clean: {dist_from_support:.1f}% from {nearest_support['name']}, "
            f"RSI={round(rsi,1)} in buy zone",
            detail)


def q2_is_there_room(df, resistances, config):
    """
    QUESTION 2: Is there room to run?

    Checks whether there is enough clear space between current
    price and the nearest resistance to make the trade worthwhile.

    Two sub-checks:
        A. The nearest resistance is at least MIN_ROOM_PCT % away
           → There's real upside potential before hitting a wall
        B. Identify the best target (furthest resistance that's still
           within a reasonable range, or the second resistance)

    Why MIN_ROOM_PCT = 4% minimum?
        A stock that hits resistance in 2% gives you no room.
        After brokerage, slippage, and taxes, a 2% move barely
        covers costs. You need at least 4-6% room for the trade
        to be worth the risk of a 2-3% stop loss.

    The "best target" is the first major resistance that
    would give a reward:risk of at least 2:1.
    """
    last  = df.iloc[-1]
    close = float(last['Close'])
    detail = {}

    if not resistances:
        return False, "No resistance levels found above price", detail

    nearest_resistance = resistances[0]
    room_pct           = nearest_resistance['dist_pct']
    detail['nearest_resistance'] = nearest_resistance
    detail['all_resistances']    = resistances[:4]

    # ── Sub-check A: Enough room ──────────────────────────────
    if room_pct < config['MIN_ROOM_PCT']:
        return (False,
                f"Not enough room: nearest resistance ({nearest_resistance['name']}) "
                f"is only {room_pct:.1f}% away "
                f"(minimum needed: {config['MIN_ROOM_PCT']}%)",
                detail)

    # ── Sub-check B: Identify best target ─────────────────────
    # Target = the best resistance level for taking profit
    # Prefer the second resistance if it's within reach (within 15%)
    # This gives a more meaningful profit target
    target = nearest_resistance
    if len(resistances) >= 2 and resistances[1]['dist_pct'] <= 15:
        # Use the second resistance as target (more ambitious but still realistic)
        target = resistances[1]

    detail['target'] = target

    return (True,
            f"Room available: {room_pct:.1f}% to nearest resistance "
            f"({nearest_resistance['name']}). Target: {target['name']} "
            f"at Rs{target['price']} (+{target['dist_pct']:.1f}%)",
            detail)


def q3_rr_justified(df, supports, resistances, config):
    """
    QUESTION 3: Does the Reward:Risk justify the trade?

    Calculates the complete trade setup:
        Entry price  = current close (or entry zone midpoint)
        Stop loss    = entry − (ATR_STOP_MULT × ATR)
        Target       = nearest clean resistance
        R:R ratio    = (Target − Entry) / (Entry − Stop)

    Only accepts trades with R:R >= MIN_RR (default 2.0).

    Why 2:1 minimum?
        At a 2:1 ratio with a 50% win rate:
            50 winning trades × 2 units = +100 units
            50 losing trades × 1 unit  = -50 units
            Net: +50 units profit

        Below 2:1, you need a very high win rate to be profitable.
        Above 2:1, you can be wrong more than half the time and
        still make money. This is the mathematical foundation of
        professional trading.

    Also calculates:
        Position size = RISK_PER_TRADE / stop_distance_in_rupees
        Capital required = position_size × entry_price
        Maximum loss = exactly RISK_PER_TRADE (controlled risk)
    """
    last    = df.iloc[-1]
    close   = float(last['Close'])
    atr     = float(last['ATR']) if not pd.isna(last['ATR']) else (close * 0.015)
    detail  = {}

    # Entry price = current close
    entry = close

    # Stop loss = entry − (multiplier × ATR)
    stop_distance = config['ATR_STOP_MULT'] * atr
    stop_loss     = round(entry - stop_distance, 2)
    stop_pct      = round(stop_distance / entry * 100, 2)

    # Target = nearest resistance with sufficient room
    if not resistances:
        return False, "No resistance levels found for target", detail

    # Find the best target: enough room AND gives R:R >= MIN_RR
    target_price = None
    target_name  = None

    for res in resistances:
        reward_rupees = res['price'] - entry
        if reward_rupees <= 0:
            continue
        rr = reward_rupees / stop_distance
        if rr >= config['MIN_RR']:
            target_price = res['price']
            target_name  = res['name']
            rr_ratio     = round(rr, 2)
            break

    if target_price is None:
        # No resistance gives 2:1 — calculate what R:R the best target gives
        if resistances:
            best = resistances[0]
            reward = best['price'] - entry
            actual_rr = round(reward / stop_distance, 2) if stop_distance > 0 else 0
            return (False,
                    f"R:R too low. Best target ({best['name']} at Rs{best['price']}) "
                    f"gives only {actual_rr:.1f}:1 (minimum: {config['MIN_RR']}:1). "
                    f"Need price pullback closer to support to improve entry.",
                    detail)
        return False, "Cannot calculate R:R — no valid target found", detail

    # Position sizing
    risk_rupees  = config['RISK_PER_TRADE']
    shares       = int(risk_rupees / stop_distance)
    capital_reqd = round(shares * entry, 0)
    max_loss     = round(shares * stop_distance, 0)
    max_gain     = round(shares * (target_price - entry), 0)

    detail.update({
        'entry'        : round(entry, 2),
        'stop_loss'    : stop_loss,
        'stop_pct'     : stop_pct,
        'stop_distance': round(stop_distance, 2),
        'target'       : target_price,
        'target_name'  : target_name,
        'rr_ratio'     : rr_ratio,
        'atr'          : round(atr, 2),
        'shares'       : shares,
        'capital_reqd' : capital_reqd,
        'max_loss'     : max_loss,
        'max_gain'     : max_gain,
    })

    return (True,
            f"R:R = {rr_ratio}:1 ✓ | "
            f"Entry Rs{round(entry,1)} → Stop Rs{stop_loss} → "
            f"Target Rs{target_price} ({target_name})",
            detail)



# ════════════════════════════════════════════════════════════
# SECTION 6 — CONFIDENCE GRADING
# Grades the trade setup A/B/C based on signal quality
# ════════════════════════════════════════════════════════════

def grade_trade(df, rr_detail, supports):
    """
    Assigns a confidence grade to passing trades.

    Grade A — Highest confidence:
        Multiple support levels at entry zone (confluence)
        R:R >= 3:1 (exceptional reward)
        ADX > 25 (strong trend)
        RSI 30-50 (ideal buy zone)
        Volume drying up on pullback

    Grade B — Good confidence:
        At least one solid support level
        R:R >= 2:1 (required minimum)
        ADX 20-25 (trend developing)
        RSI 45-60 (slightly extended but acceptable)

    Grade C — Acceptable, use smaller size:
        Barely passes all three questions
        R:R just above 2:1
        ADX borderline (<20)
        Entry near upper bound of buy zone

    This grading helps you size positions:
        Grade A → Full position (RISK_PER_TRADE × 1.0)
        Grade B → Standard position (RISK_PER_TRADE × 0.75)
        Grade C → Half position (RISK_PER_TRADE × 0.5)
    """
    last    = df.iloc[-1]
    rsi     = float(last['RSI']) if not pd.isna(last['RSI']) else 50
    adx     = float(last['ADX']) if not pd.isna(last['ADX']) else 0
    rr      = rr_detail.get('rr_ratio', 0)

    score = 0

    # R:R scoring
    if rr >= 3.5:   score += 3
    elif rr >= 2.5: score += 2
    elif rr >= 2.0: score += 1

    # ADX scoring
    if adx > 30:    score += 3
    elif adx > 25:  score += 2
    elif adx > 20:  score += 1

    # RSI scoring (ideal = 30-50)
    if 30 <= rsi <= 50:   score += 3
    elif 25 <= rsi <= 55: score += 2
    elif rsi <= 62:       score += 1

    # Multiple support confluence
    if len(supports) >= 3 and supports[2]['dist_pct'] < 3:
        score += 2   # Three support levels within 3% = strong confluence
    elif len(supports) >= 2 and supports[1]['dist_pct'] < 4:
        score += 1   # Two supports nearby

    # OBV trend
    obv_trend = df['OBV'].iloc[-10:].iloc[-1] > df['OBV'].iloc[-10:].iloc[0]
    if obv_trend:
        score += 1   # Volume accumulation continuing

    # Supertrend direction
    if not pd.isna(last['ST_Dir']) and int(last['ST_Dir']) == 1:
        score += 2   # Supertrend bullish = trend confirmed

    # Grade assignment
    if score >= 11:
        grade = 'A'
        size_mult = 1.0
        grade_desc = 'High confidence — full position size'
    elif score >= 7:
        grade = 'B'
        size_mult = 0.75
        grade_desc = 'Good setup — standard position size (75%)'
    else:
        grade = 'C'
        size_mult = 0.5
        grade_desc = 'Acceptable — use half position size (50%)'

    return grade, size_mult, grade_desc, score


# ════════════════════════════════════════════════════════════
# SECTION 7 — MAIN ANALYSIS FUNCTION
# Runs all three questions on a single ticker
# ════════════════════════════════════════════════════════════

def analyze_ticker(ticker, config, prefetched_df=None):
    """
    Runs the complete three-question analysis on one ticker.

    Args:
        ticker:        ticker symbol (e.g. 'RELIANCE.NS')
        config:        CONFIG dict
        prefetched_df: optional raw OHLCV DataFrame (skips yfinance download)

    Returns a dict with:
        verdict: 'TRADE' or 'SKIP'
        reason:  human-readable explanation
        setup:   complete trade setup dict (if TRADE)
        q1/q2/q3: individual question results
    """
    # Download + indicators (uses cached OHLCV if provided)
    result = get_data(ticker, raw_df=prefetched_df)
    if result is None:
        return {
            'ticker' : ticker.replace('.NS', ''),
            'verdict': 'ERROR',
            'reason' : 'Data download failed',
        }

    df, pivots, camarilla, fibs = result
    last  = df.iloc[-1]
    close = float(last['Close'])
    atr   = float(last['ATR']) if not pd.isna(last['ATR']) else 0

    # Detect support and resistance levels
    supports    = find_support_levels(df, pivots, fibs)
    resistances = find_resistance_levels(df, pivots, fibs)

    # ── Question 1 ────────────────────────────────────────────
    q1_pass, q1_reason, q1_detail = q1_is_entry_clean(df, supports, config)

    # ── Question 2 ────────────────────────────────────────────
    q2_pass, q2_reason, q2_detail = q2_is_there_room(df, resistances, config)

    # ── Question 3 ────────────────────────────────────────────
    q3_pass, q3_reason, q3_detail = q3_rr_justified(df, supports, resistances, config)

    # ── Verdict ───────────────────────────────────────────────
    all_pass = q1_pass and q2_pass and q3_pass

    if all_pass:
        grade, size_mult, grade_desc, grade_score = grade_trade(df, q3_detail, supports)

        # Adjust position size by confidence grade
        adjusted_risk   = config['RISK_PER_TRADE'] * size_mult
        adjusted_shares = int(adjusted_risk / q3_detail['stop_distance']) if q3_detail.get('stop_distance') else 0
        adjusted_capital = round(adjusted_shares * close, 0)

        setup = {
            **q3_detail,
            'grade'          : grade,
            'grade_score'    : grade_score,
            'grade_desc'     : grade_desc,
            'size_mult'      : size_mult,
            'adj_shares'     : adjusted_shares,
            'adj_capital'    : adjusted_capital,
            'adj_max_loss'   : round(adjusted_shares * q3_detail.get('stop_distance', 0), 0),
            'adj_max_gain'   : round(adjusted_shares * (q3_detail.get('target', close) - close), 0),
            'nearest_support': supports[0] if supports else {},
            'q1_detail'      : q1_detail,
            'q2_detail'      : q2_detail,
            'rsi'            : round(float(last['RSI']) if not pd.isna(last['RSI']) else 0, 1),
            'adx'            : round(float(last['ADX']) if not pd.isna(last['ADX']) else 0, 1),
            'vol_ratio'      : round(float(last['Vol_Ratio']), 2),
            'close'          : close,
            'atr'            : atr,
        }

        return {
            'ticker'  : ticker.replace('.NS', ''),
            'verdict' : 'TRADE',
            'reason'  : f"All 3 checks passed | Grade {grade}",
            'setup'   : setup,
            'q1_pass' : True,  'q1_reason': q1_reason,
            'q2_pass' : True,  'q2_reason': q2_reason,
            'q3_pass' : True,  'q3_reason': q3_reason,
        }

    else:
        # Find which question(s) failed
        failed = []
        if not q1_pass: failed.append(f"Q1 FAIL: {q1_reason}")
        if not q2_pass: failed.append(f"Q2 FAIL: {q2_reason}")
        if not q3_pass: failed.append(f"Q3 FAIL: {q3_reason}")

        return {
            'ticker'  : ticker.replace('.NS', ''),
            'verdict' : 'SKIP',
            'reason'  : ' | '.join(failed),
            'close'   : close,
            'q1_pass' : q1_pass, 'q1_reason': q1_reason,
            'q2_pass' : q2_pass, 'q2_reason': q2_reason,
            'q3_pass' : q3_pass, 'q3_reason': q3_reason,
        }



# ════════════════════════════════════════════════════════════
# SECTION 8 — OUTPUT FORMATTING
# Prints a clean trade card for each qualifying setup
# ════════════════════════════════════════════════════════════

def print_trade_card(result, rank=None):
    """
    Prints a complete trade setup card for a qualifying stock.

    Example output:
    ═══════════════════════════════════════════════════════════
      #1  HDFCBANK  ★★★ Grade A — High confidence
    ═══════════════════════════════════════════════════════════

      ENTRY ZONE    Rs 1,638 – 1,645  (current: Rs 1,641)
      STOP LOSS     Rs 1,597          (-2.7%)  ← 2 × ATR below entry
      TARGET        Rs 1,710          (+4.2%)  ← Pivot R2
      RISK:REWARD   3.1 : 1

      ── Position Sizing ──────────────────────────────────
      Position size     : 45 shares
      Capital required  : Rs 73,845
      Max loss          : Rs 2,000   (if stop hit)
      Max gain          : Rs 6,165   (if target hit)

      ── Why this entry? ──────────────────────────────────
      Q1 Entry  ✓  2.1% from SMA 20. RSI=42.1 in buy zone.
      Q2 Room   ✓  8.3% to Pivot R2. Path clear of resistance.
      Q3 R:R    ✓  3.1:1 meets minimum of 2.0:1

      ── Key levels nearby ────────────────────────────────
      Support  : SMA 20 = Rs 1,607 | Pivot S1 = Rs 1,588
      Resist   : Pivot R1 = Rs 1,672 | Pivot R2 = Rs 1,710
    """
    s = result['setup']
    ticker = result['ticker']
    grade  = s['grade']
    stars  = {'A': '★★★', 'B': '★★☆', 'C': '★☆☆'}.get(grade, '★☆☆')
    rank_str = f"#{rank}  " if rank else ""

    width = 62

    print(f"\n  {'═'*width}")
    print(f"  {rank_str}{ticker:<12}  {stars} Grade {grade} — {s['grade_desc']}")
    print(f"  {'═'*width}")

    # Entry / Stop / Target block
    entry_lo = s.get('entry_zone_low',  round(s['entry'] * 0.997, 2))
    entry_hi = s.get('entry_zone_high', round(s['entry'] * 1.002, 2))
    stop_pct = s['stop_pct']
    tgt_pct  = round((s['target'] - s['entry']) / s['entry'] * 100, 1)

    print(f"\n  {'ENTRY ZONE':<16} Rs{entry_lo:,.1f} – {entry_hi:,.1f}   (now: Rs{s['entry']:,.1f})")
    print(f"  {'STOP LOSS':<16} Rs{s['stop_loss']:,.1f}   (-{stop_pct:.1f}%)  ← {s.get('atr_mult', 2.0)}× ATR below entry")
    print(f"  {'TARGET':<16} Rs{s['target']:,.1f}   (+{tgt_pct:.1f}%)  ← {s.get('target_name','resistance')}")
    print(f"  {'RISK:REWARD':<16} {s['rr_ratio']:.1f} : 1")

    # Position sizing
    print(f"\n  ── Position Sizing {'─'*43}")
    print(f"  {'Position size':<20}: {s['adj_shares']} shares  ({s['size_mult']*100:.0f}% of max — Grade {grade})")
    print(f"  {'Capital required':<20}: Rs{s['adj_capital']:,.0f}")
    print(f"  {'Max loss':<20}: Rs{s['adj_max_loss']:,.0f}   (if stop hit)")
    print(f"  {'Max gain':<20}: Rs{s['adj_max_gain']:,.0f}   (if target hit)")

    # The three question results
    print(f"\n  ── Why this entry? {'─'*43}")
    q1_sym = '✓' if result['q1_pass'] else '✗'
    q2_sym = '✓' if result['q2_pass'] else '✗'
    q3_sym = '✓' if result['q3_pass'] else '✗'
    print(f"  Q1 Entry  {q1_sym}  {result['q1_reason']}")
    print(f"  Q2 Room   {q2_sym}  {result['q2_reason']}")
    print(f"  Q3 R:R    {q3_sym}  {result['q3_reason']}")

    # Key levels
    q2d = s.get('q2_detail', {})
    resistances = q2d.get('all_resistances', [])
    res_str = '  |  '.join([f"{r['name']}=Rs{r['price']:,.1f}" for r in resistances[:2]])

    sup = s.get('nearest_support', {})
    sup_str = f"{sup.get('name','?')}=Rs{sup.get('price','?')}" if sup else ''
    if s.get('q1_detail', {}).get('nearest_support'):
        ns = s['q1_detail']['nearest_support']
        sup_str = f"{ns.get('name','?')}=Rs{ns.get('price','?'):,.1f}"

    print(f"\n  ── Key levels {'─'*48}")
    print(f"  Support  : {sup_str}")
    print(f"  Resist   : {res_str}")
    print(f"  ATR={s['atr']:.1f}  RSI={s.get('rsi',0):.1f}  ADX={s.get('adx',0):.1f}  Vol={s.get('vol_ratio',0):.1f}x")
    print(f"  {'═'*width}")


def print_skipped(result):
    """Prints a one-liner for skipped stocks with the reason."""
    q1 = '✓' if result.get('q1_pass') else '✗'
    q2 = '✓' if result.get('q2_pass') else '✗'
    q3 = '✓' if result.get('q3_pass') else '✗'
    close = result.get('close', 0)
    reason = result.get('reason','').split(' | ')[0]  # First failure reason
    print(f"  SKIP  {result['ticker']:<12}  [Q1{q1} Q2{q2} Q3{q3}]  Rs{close:.1f}  {reason[:60]}")


# ════════════════════════════════════════════════════════════
# SECTION 9 — MAIN RUNNER
# ════════════════════════════════════════════════════════════

def run_analysis(tickers, config, label='Analysis'):
    """
    Runs the full three-question analysis on a list of tickers.

    Prints:
        - Trade cards for all passing stocks (best grade first)
        - Skip list with reasons (if SHOW_SKIPPED=True)
        - Summary stats
    """
    import time

    print(f"\n{'='*66}")
    print(f"  TRADE ANALYZER — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Candidates: {len(tickers)} | Risk/trade: Rs{config['RISK_PER_TRADE']:,}")
    print(f"  Min R:R: {config['MIN_RR']}:1 | Stop mult: {config['ATR_STOP_MULT']}×ATR")
    print(f"{'='*66}\n")

    trades  = []
    skipped = []
    errors  = []

    for i, ticker in enumerate(tickers):
        if not ticker.endswith('.NS'):
            ticker = ticker.upper() + '.NS'

        pct = int((i+1) / len(tickers) * 20)
        bar = '█' * pct + '░' * (20-pct)
        print(f"\r  [{bar}] {i+1}/{len(tickers)}  {ticker:<20}", end='', flush=True)

        result = analyze_ticker(ticker, config)

        if result['verdict'] == 'TRADE':
            trades.append(result)
        elif result['verdict'] == 'SKIP':
            skipped.append(result)
        else:
            errors.append(result)

        time.sleep(0.1)

    print(f"\n\n  ── Scan complete ──")
    print(f"  Candidates analyzed : {len(tickers)}")
    print(f"  Trade setups found  : {len(trades)}")
    print(f"  Skipped             : {len(skipped)}")
    print(f"  Errors              : {len(errors)}")

    # Sort trades: Grade A first, then B, then C, then by R:R descending
    grade_order = {'A': 0, 'B': 1, 'C': 2}
    trades.sort(key=lambda r: (
        grade_order.get(r['setup']['grade'], 3),
        -r['setup'].get('rr_ratio', 0)
    ))

    # Print trade cards
    if trades:
        print(f"\n\n{'='*66}")
        print(f"  TRADE SETUPS  ({len(trades)} found)")
        print(f"{'='*66}")
        for rank, result in enumerate(trades[:config['TOP_N']], 1):
            print_trade_card(result, rank=rank)
    else:
        print(f"\n  No trade setups found today.")
        print(f"  Most common reason: check skip list below.")
        print(f"  Consider: market may be in a run-up phase (entries late).")
        print(f"  Wait for next pullback closer to support levels.")

    # Print skipped
    if config['SHOW_SKIPPED'] and skipped:
        print(f"\n\n  ── Skipped ({len(skipped)} stocks) ──────────────────────────────")
        for r in skipped:
            print_skipped(r)

    # Summary
    if trades:
        total_capital = sum(t['setup']['adj_capital'] for t in trades[:3])
        total_risk    = sum(t['setup']['adj_max_loss'] for t in trades[:3])
        print(f"\n  ── Portfolio summary (top 3 trades) ──────────────────────────")
        print(f"  Total capital needed  : Rs{total_capital:,.0f}")
        print(f"  Total risk            : Rs{total_risk:,.0f}")
        print(f"  ──────────────────────────────────────────────────────────────")

    return trades, skipped


# ════════════════════════════════════════════════════════════
# SECTION 10 — MAIN
# ════════════════════════════════════════════════════════════

# Stock lists (reuse from screener)
NIFTY_50 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFOSYS.NS",
    "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","HCLTECH.NS",
    "SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","WIPRO.NS","NESTLEIND.NS",
    "BAJFINANCE.NS","POWERGRID.NS","NTPC.NS","TECHM.NS","TATAMOTORS.NS",
    "ONGC.NS","TATASTEEL.NS","ADANIENT.NS","BAJAJFINSV.NS","JSWSTEEL.NS",
    "COALINDIA.NS","INDUSINDBK.NS","DRREDDY.NS","CIPLA.NS","EICHERMOT.NS",
    "BRITANNIA.NS","APOLLOHOSP.NS","BPCL.NS","GRASIM.NS","TATACONSUM.NS",
    "DIVISLAB.NS","HEROMOTOCO.NS","HINDALCO.NS","M&M.NS","SBILIFE.NS",
    "HDFCLIFE.NS","ADANIPORTS.NS","UPL.NS","SHREECEM.NS","BAJAJ-AUTO.NS",
]


def main():
    """
    Usage:
        # Use after screener — pass tickers from screener output:
        python trade_analyzer.py --tickers HDFCBANK TITAN ICICIBANK SBIN

        # Load from screener CSV automatically:
        python trade_analyzer.py --csv screener_v3_nifty50_20260409.csv

        # Run on full index (screener + analysis together):
        python trade_analyzer.py --index nifty50

        # Adjust risk and R:R:
        python trade_analyzer.py --tickers RELIANCE --risk 5000 --rr 2.5
    """
    args = sys.argv[1:]
    tickers = []
    label   = 'Nifty 50'

    # Parse arguments
    i = 0
    while i < len(args):
        if args[i] == '--tickers':
            # Collect all tickers until next flag
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                t = args[i].upper()
                if not t.endswith('.NS'):
                    t += '.NS'
                tickers.append(t)
                i += 1

        elif args[i] == '--csv' and i+1 < len(args):
            # Load tickers from screener CSV
            csv_file = args[i+1]
            try:
                df_csv = pd.read_csv(csv_file)
                # CSV has 'Ticker' column (without .NS)
                csv_tickers = df_csv['Ticker'].tolist()
                tickers = [t + '.NS' if not t.endswith('.NS') else t
                           for t in csv_tickers]
                label = f"CSV: {csv_file}"
                print(f"  Loaded {len(tickers)} tickers from {csv_file}")
            except Exception as e:
                print(f"  Error reading CSV: {e}")
                sys.exit(1)
            i += 2

        elif args[i] == '--index' and i+1 < len(args):
            idx = args[i+1].lower()
            tickers = NIFTY_50   # extend with nifty100 if needed
            label   = f'Nifty {idx}'
            i += 2

        elif args[i] == '--risk' and i+1 < len(args):
            CONFIG['RISK_PER_TRADE'] = int(args[i+1])
            i += 2

        elif args[i] == '--rr' and i+1 < len(args):
            CONFIG['MIN_RR'] = float(args[i+1])
            i += 2

        elif args[i] == '--stop' and i+1 < len(args):
            CONFIG['ATR_STOP_MULT'] = float(args[i+1])
            i += 2

        else:
            i += 1

    # Default: find latest screener CSV automatically
    if not tickers:
        csv_files = sorted(glob.glob('screener_v3_*.csv'), reverse=True)
        if csv_files:
            latest = csv_files[0]
            print(f"  Auto-loading latest screener output: {latest}")
            try:
                df_csv = pd.read_csv(latest)
                csv_tickers = df_csv['Ticker'].tolist()
                tickers = [t + '.NS' if not t.endswith('.NS') else t
                           for t in csv_tickers]
                label = f"Latest screener: {latest}"
            except Exception:
                pass

    # If still no tickers, use Nifty 50
    if not tickers:
        print("  No tickers specified. Using Nifty 50.")
        print("  Tip: run screener_v3.py first, then this auto-loads its output.")
        tickers = NIFTY_50
        label   = 'Nifty 50'

    run_analysis(tickers, CONFIG, label=label)
    print(f"\n  Trade Analyzer complete.\n")


if __name__ == '__main__':
    main()