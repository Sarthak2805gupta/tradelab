# ============================================================
# UPGRADED NIFTY STOCK SCREENER — v2.0
# Score: 0 to 13 (was 0 to 8 in v1)
# ============================================================
#
# WHAT'S NEW vs screener.py (v1):
#   All indicator functions are now imported from
#   complete_indicators.py instead of being duplicated here.
#
#   5 new scoring conditions added:
#     9.  ADX > 25             (trend strength confirmed)
#     10. Supertrend bullish   (most popular Indian indicator)
#     11. Donchian breakout    (20-day high with volume)
#     12. Stochastic oversold  (faster momentum signal than RSI)
#     13. BB+KC squeeze active (coiled, big move incoming)
#
# REQUIRES:
#   complete_indicators.py in the same folder as this file
#
# HOW TO RUN:
#   python screener_v2.py                    # Nifty 50 (fast)
#   python screener_v2.py --index nifty100   # Nifty 100
#   python screener_v2.py --index nifty500   # Full sample
#   python screener_v2.py --ticker RELIANCE  # Single stock
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
import os
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# ── Allow importing advanced_indicators.py from project root ──
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _root not in sys.path:
    sys.path.insert(0, _root)

# ── Import ALL indicator functions from our complete library ──
# This single import replaces ~200 lines of duplicated code
from complete_indicators import (
    # Trend
    calc_sma, calc_ema,
    # Momentum
    calc_rsi, calc_macd,
    calc_stochastic, calc_cci, calc_roc,
    # Volatility & Bands
    calc_bollinger, calc_atr,
    calc_keltner, calc_donchian,
    # Trend strength
    calc_adx,
    # Supertrend
    calc_supertrend,
    # Volume
    calc_obv, calc_mfi, calc_vwap,
    # EMA Ribbon
    calc_ema_ribbon,
    # Candlestick patterns
    is_hammer, is_bullish_engulfing, is_doji,
)

# ── Import extension indicators (same folder) ─────────────────
from indicators_extension import (
    calc_ichimoku,
    calc_parabolic_sar,
    calc_williams_r,
    calc_cmf,
    calc_aroon,
)

# ── Import advanced indicators (project root) ─────────────────
from indicators.advanced_indicators import (
    calc_hma,
    calc_force_index,
)
from indicators_extension import (
    calc_ichimoku, calc_parabolic_sar, calc_williams_r,
    calc_cmf, calc_aroon, calc_pivot_points, calc_camarilla_pivots,
    auto_fibonacci
)

# ════════════════════════════════════════════════════════════
# SECTION 1 — NIFTY INDEX STOCK LISTS (same as v1)
# ════════════════════════════════════════════════════════════

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

NIFTY_100 = NIFTY_50 + [
    "AMBUJACEM.NS", "BANKBARODA.NS", "BERGEPAINT.NS", "BIOCON.NS",
    "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS", "COLPAL.NS", "DABUR.NS",
    "DLF.NS", "GAIL.NS", "GODREJCP.NS", "HAVELLS.NS", "ICICIPRULI.NS",
    "INDHOTEL.NS", "IOC.NS", "IRCTC.NS", "LUPIN.NS", "MARICO.NS",
    "MCDOWELL-N.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "OFSS.NS", "PAGEIND.NS",
    "PEL.NS", "PIDILITIND.NS", "PNB.NS", "RECLTD.NS", "SAIL.NS",
    "SIEMENS.NS", "SRF.NS", "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS",
    "VOLTAS.NS", "ZOMATO.NS", "LTIM.NS", "ATGL.NS", "ICICIGI.NS", "PGHH.NS",
]

NIFTY_500_SAMPLE = NIFTY_100 + [
    "AUROPHARMA.NS", "BEL.NS", "BHEL.NS", "CROMPTON.NS", "CUMMINSIND.NS",
    "ESCORTS.NS", "FEDERALBNK.NS", "FORTIS.NS", "GODREJPROP.NS", "HAL.NS",
    "IDFCFIRSTB.NS", "INDIGO.NS", "INTELLECT.NS", "IGL.NS", "JINDALSTEL.NS",
    "JUBLFOOD.NS", "KAJARIACER.NS", "KPITTECH.NS", "LALPATHLAB.NS",
    "LAURUSLABS.NS", "LICHSGFIN.NS", "MANAPPURAM.NS", "MOTHERSON.NS",
    "MPHASIS.NS", "MRF.NS", "NMDC.NS", "OBEROIRLTY.NS", "PERSISTENT.NS",
    "PETRONET.NS", "POLYCAB.NS", "RBLBANK.NS", "TATACOMM.NS", "TATACHEM.NS",
    "TATAELXSI.NS", "TORNTPOWER.NS", "TRIDENT.NS", "UNIONBANK.NS", "VBL.NS",
]

INDEX_MAP = {
    'nifty50':  NIFTY_50,
    'nifty100': NIFTY_100,
    'nifty500': NIFTY_500_SAMPLE,
}


# ════════════════════════════════════════════════════════════
# SECTION 2 — DATA DOWNLOAD + ALL INDICATORS
# ════════════════════════════════════════════════════════════

def download_and_calculate(ticker, period="1y"):
    """
    Downloads OHLCV data and calculates ALL indicators using
    functions imported from complete_indicators.py.

    Parameters:
        ticker (str): e.g. "RELIANCE.NS"
        period (str): "1y" gives enough data for SMA 200

    Returns:
        df (DataFrame) with all indicator columns, or None if failed
    """
    try:
        df = yf.download(ticker, period=period,
                         auto_adjust=True, progress=False)

        if len(df) < 210:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.dropna(subset=['Open','High','Low','Close','Volume'], inplace=True)

        if len(df) < 210:
            return None

        # ── All indicators via imported functions ──

        # Trend
        df['SMA_20']  = calc_sma(df['Close'], 20)
        df['SMA_50']  = calc_sma(df['Close'], 50)
        df['SMA_200'] = calc_sma(df['Close'], 200)
        df['EMA_9']   = calc_ema(df['Close'], 9)
        df['EMA_20']  = calc_ema(df['Close'], 20)

        # EMA Ribbon
        ribbon = calc_ema_ribbon(df['Close'], [9, 21, 34, 55, 89, 144])
        for p, vals in ribbon.items():
            df[f'EMA_{p}'] = vals

        # Momentum
        df['RSI']            = calc_rsi(df['Close'], 14)
        df['Stoch_K'], df['Stoch_D'] = calc_stochastic(df, 14, 3, 3)
        df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calc_macd(df['Close'])

        # Volatility & Bands
        df['ATR'] = calc_atr(df, 14)
        (df['BB_Mid'], df['BB_Up'], df['BB_Lo'],
         df['PctB'],  df['BW'])   = calc_bollinger(df['Close'])
        (df['KC_Mid'], df['KC_Up'], df['KC_Lo']) = calc_keltner(df)
        (df['DC_Up'],  df['DC_Mid'], df['DC_Lo']) = calc_donchian(df, 20)

        # BB + KC squeeze flag
        df['Squeeze'] = (df['BB_Up'] - df['BB_Lo']) < (df['KC_Up'] - df['KC_Lo'])

        # Trend strength
        df['ADX'], df['DI_Plus'], df['DI_Minus'] = calc_adx(df, 14)

        # Supertrend
        df['Supertrend'], df['ST_Dir'] = calc_supertrend(df, period=7, multiplier=3.0)

        # Volume
        df['VMA']       = calc_sma(df['Volume'].astype(float), 20)
        df['Vol_Ratio'] = df['Volume'] / df['VMA']
        df['OBV']       = calc_obv(df['Close'], df['Volume'])
        df['MFI']       = calc_mfi(df, 14)

        # MACD crossover flag
        df['MACD_Cross_Up'] = (
            (df['MACD'] > df['MACD_Signal']) &
            (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
        )

        # ── Extension indicators ─────────────────────────────

        # Ichimoku Cloud (9/26/52 standard settings)
        df['Ich_Tenkan'], df['Ich_Kijun'], _, _, _ = calc_ichimoku(df)
        # Cloud AT bar i = SpanA/B calculated from data 26 bars ago
        df['Ich_Cloud_A'] = ((df['Ich_Tenkan'] + df['Ich_Kijun']) / 2).shift(26)
        df['Ich_Cloud_B'] = (
            (df['High'].rolling(52).max() + df['Low'].rolling(52).min()) / 2
        ).shift(26)

        # Parabolic SAR (Wilder — stop-and-reverse)
        df['PSAR'], df['PSAR_Trend'] = calc_parabolic_sar(df)

        # Williams %R (inverted Stochastic, no smoothing — faster signal)
        df['Williams_R'] = calc_williams_r(df, 14)

        # Chaikin Money Flow (institutional accumulation / distribution)
        df['CMF'] = calc_cmf(df, 20)

        # Aroon (detects emerging trends faster than ADX)
        df['Aroon_Up'], df['Aroon_Dn'], df['Aroon_Osc'] = calc_aroon(df, 25)

        # Hull MA (Alan Hull's low-lag moving average)
        df['HMA_21'] = calc_hma(df['Close'], 21)

        # Force Index (Dr Elder — price change × volume)
        df['Force_Idx'] = calc_force_index(df, 13)

        return df

    except Exception:
        return None


# ════════════════════════════════════════════════════════════
# SECTION 3 — UPGRADED SCORING ENGINE (0 to 20)
# ════════════════════════════════════════════════════════════

def score_stock(df, ticker):
    """
    Scores a stock across 20 conditions.

    Original 8 conditions (from v1 screener):
        1.  Price above SMA 200
        2.  SMA 50 above SMA 200 (Golden Cross zone)
        3.  RSI between 30–55 (sweet spot pullback)
        4.  MACD bullish crossover in last 3 days
        5.  Bollinger squeeze OR near lower band
        6.  Volume > 1.5x average
        7.  OBV trending up (last 10 days)
        8.  Bullish candlestick pattern in last 3 days

    Conditions 9–13 (from complete_indicators.py):
        9.  ADX > 25                  — trend has real strength
        10. Supertrend direction = +1 — ST says bullish
        11. Donchian upper breakout   — new 20-day high
        12. Stochastic oversold       — %K < 30 and rising
        13. BB + KC squeeze active    — coiled for big move

    NEW conditions 14–20 (from indicators_extension + advanced_indicators):
        14. Ichimoku bullish          — price above cloud + TK cross
        15. Parabolic SAR bullish     — dot below price (uptrend dot)
        16. Williams %R recovery      — oversold (<-60) and rising
        17. CMF > 0.05                — net institutional accumulation
        18. Aroon Up > 70 & dominant  — trend emergence confirmed
        19. HMA(21) slope rising      — low-lag trend filter bullish
        20. Force Index > 0           — price × volume momentum positive

    Score interpretation:
        17–20 : Exceptional — full multi-system alignment, very rare
        13–16 : Strong setup — high priority watchlist
        8–12  : Good setup — moderate priority
        4–7   : Watch only
        0–3   : Skip

    Parameters:
        df (DataFrame): Stock data with all indicators
        ticker (str): Stock symbol

    Returns:
        dict with score, signals, and key indicator values
    """

    if len(df) < 210:
        return None

    last  = df.iloc[-1]
    prev  = df.iloc[-2]
    prev2 = df.iloc[-3]

    close     = round(last['Close'], 2)
    sma50     = last['SMA_50']
    sma200    = last['SMA_200']
    rsi       = last['RSI']
    pctb      = last['PctB']
    bw        = last['BW']
    vol_ratio = last['Vol_Ratio']
    adx       = last['ADX']
    st_dir    = last['ST_Dir']
    stoch_k   = last['Stoch_K']
    stoch_k_p = prev['Stoch_K']
    squeeze   = bool(last['Squeeze'])

    # Extension indicator values
    ich_tenkan   = last['Ich_Tenkan']
    ich_kijun    = last['Ich_Kijun']
    ich_cloud_a  = last['Ich_Cloud_A']
    ich_cloud_b  = last['Ich_Cloud_B']
    psar_trend   = last['PSAR_Trend']
    williams_r   = last['Williams_R']
    williams_r_p = prev['Williams_R']
    cmf          = last['CMF']
    aroon_up     = last['Aroon_Up']
    aroon_dn     = last['Aroon_Dn']
    hma_now      = last['HMA_21']
    hma_prev3    = df['HMA_21'].iloc[-4]   # 3 bars ago
    force_idx    = last['Force_Idx']

    if any(pd.isna(v) for v in [sma50, sma200, rsi, pctb, vol_ratio]):
        return None

    score   = 0
    signals = []

    # ── Original 8 conditions ──────────────────────────────

    # 1. Price above SMA 200 (long-term uptrend)
    if close > sma200:
        score += 1
        signals.append(f"Above SMA200 (₹{round(sma200,1)})")

    # 2. Golden Cross zone (SMA50 > SMA200)
    if sma50 > sma200:
        score += 1
        signals.append("Golden Cross zone")

    # 3. RSI in sweet spot (30–55: pullback in uptrend)
    if 30 <= rsi <= 55:
        score += 1
        signals.append(f"RSI sweet spot ({round(rsi,1)})")
    elif rsi < 30:
        signals.append(f"RSI oversold ({round(rsi,1)}) — reversal watch")

    # 4. MACD bullish crossover in last 3 days
    macd_cross = False
    for lb in range(1, 4):
        if len(df) > lb + 1:
            m_now  = df['MACD'].iloc[-lb]
            m_prev = df['MACD'].iloc[-lb-1]
            s_now  = df['MACD_Signal'].iloc[-lb]
            s_prev = df['MACD_Signal'].iloc[-lb-1]
            if not any(pd.isna(v) for v in [m_now, m_prev, s_now, s_prev]):
                if m_prev < s_prev and m_now > s_now:
                    macd_cross = True
                    signals.append(f"MACD bullish cross ({lb-1}d ago)" if lb > 1 else "MACD bullish cross (today)")
                    break
    if macd_cross:
        score += 1

    # 5. Bollinger squeeze OR near lower band
    bw_min = df['BW'].iloc[-50:].min() if len(df) >= 50 else df['BW'].min()
    if bw <= bw_min * 1.05:
        score += 1
        signals.append(f"BB Squeeze (BW={round(bw,1)}%)")
    elif pctb < 0.15:
        score += 1
        signals.append(f"Near lower BB (%B={round(pctb,2)})")

    # 6. High volume
    if not pd.isna(vol_ratio) and vol_ratio >= 1.5:
        score += 1
        signals.append(f"High volume ({round(vol_ratio,1)}x)")

    # 7. OBV trending up (last 10 days)
    obv_series = df['OBV'].iloc[-11:]
    if len(obv_series) >= 11:
        if obv_series.iloc[-1] > obv_series.iloc[0]:
            score += 1
            signals.append("OBV rising (10d)")

    # 8. Bullish candlestick pattern (last 3 days)
    pattern_found = False
    for lb in [1, 2, 3]:
        if len(df) >= lb:
            row = df.iloc[-lb]
            if is_hammer(row):
                signals.append(f"Hammer ({lb}d ago)")
                pattern_found = True
                break
    if not pattern_found:
        for lb in [1, 2, 3]:
            if len(df) >= lb + 1:
                c = df.iloc[-lb]; p = df.iloc[-lb-1]
                if is_bullish_engulfing(p, c):
                    signals.append(f"Bullish engulfing ({lb}d ago)")
                    pattern_found = True
                    break
    if pattern_found:
        score += 1

    # ── NEW conditions 9–13 ────────────────────────────────

    # 9. ADX > 25 (trend has real strength — not just noise)
    if not pd.isna(adx) and adx > 25:
        score += 1
        di_p = round(last['DI_Plus'], 1)
        di_m = round(last['DI_Minus'], 1)
        trend_dir = "bullish" if di_p > di_m else "bearish"
        signals.append(f"ADX={round(adx,1)} > 25 ({trend_dir} trend confirmed)")

    # 10. Supertrend is bullish (+1 direction)
    if not pd.isna(st_dir) and st_dir == 1:
        score += 1
        signals.append(f"Supertrend bullish (support ₹{round(last['Supertrend'],1)})")

    # 11. Donchian upper breakout in last 2 days (new 20-day high with volume)
    donchian_break = False
    for lb in [1, 2]:
        if len(df) >= lb:
            c_row = df.iloc[-lb]
            if (c_row['Close'] > c_row['DC_Up'] and
                    not pd.isna(c_row['Vol_Ratio']) and
                    c_row['Vol_Ratio'] >= 1.3):
                signals.append(f"Donchian breakout ({lb}d ago, {round(c_row['Vol_Ratio'],1)}x vol)")
                donchian_break = True
                break
    if donchian_break:
        score += 1

    # 12. Stochastic oversold and turning up
    # %K was below 30 and is now rising (faster signal than RSI)
    if (not pd.isna(stoch_k) and not pd.isna(stoch_k_p) and
            stoch_k < 35 and stoch_k > stoch_k_p):
        score += 1
        signals.append(f"Stochastic oversold+rising (%K={round(stoch_k,1)})")

    # 13. BB + KC squeeze active (coiled, big move pending)
    if squeeze:
        score += 1
        signals.append("BB+KC Squeeze active — expect breakout soon")

    # ── NEW conditions 14–20 (extension + advanced indicators) ─

    # 14. Ichimoku bullish: price above cloud AND Tenkan >= Kijun
    if not any(pd.isna(v) for v in [ich_cloud_a, ich_cloud_b, ich_tenkan, ich_kijun]):
        cloud_top = max(ich_cloud_a, ich_cloud_b)
        if close > cloud_top and ich_tenkan >= ich_kijun:
            score += 1
            signals.append(f"Ichimoku bullish (above cloud, TK≥KJ)")
        elif close > cloud_top:
            signals.append(f"Ichimoku: above cloud (TK cross pending)")

    # 15. Parabolic SAR bullish (dot below price = uptrend active)
    if not pd.isna(psar_trend) and psar_trend == 1:
        score += 1
        signals.append(f"PSAR bullish (stop ₹{round(last['PSAR'], 1)})")

    # 16. Williams %R: oversold and recovering (< -60 and rising)
    if (not pd.isna(williams_r) and not pd.isna(williams_r_p) and
            williams_r < -60 and williams_r > williams_r_p):
        score += 1
        signals.append(f"Williams %R recovering ({round(williams_r, 0):.0f})")

    # 17. CMF positive: institutional accumulation dominating
    if not pd.isna(cmf) and cmf > 0.05:
        score += 1
        signals.append(f"CMF={round(cmf, 2)} — smart money accumulating")

    # 18. Aroon Up > 70 and dominant over Aroon Down (trend emerging)
    if (not pd.isna(aroon_up) and not pd.isna(aroon_dn) and
            aroon_up > 70 and aroon_up > aroon_dn):
        score += 1
        signals.append(f"Aroon Up={round(aroon_up, 0):.0f} > Down={round(aroon_dn, 0):.0f} (trend forming)")

    # 19. HMA(21) slope rising — low-lag trend filter confirms uptrend
    if (not pd.isna(hma_now) and not pd.isna(hma_prev3) and
            hma_now > hma_prev3):
        score += 1
        signals.append(f"HMA(21) rising → trend confirmed")

    # 20. Force Index > 0 — buyers dominating (price change × volume)
    if not pd.isna(force_idx) and force_idx > 0:
        fi_str = f"{round(force_idx / 1e6, 1)}M" if abs(force_idx) >= 1e6 else f"{round(force_idx, 0):.0f}"
        score += 1
        signals.append(f"Force Index positive ({fi_str})")

    # ── Additional info ─────────────────────────────────────

    high_52w = df['High'].iloc[-252:].max() if len(df) >= 252 else df['High'].max()
    low_52w  = df['Low'].iloc[-252:].min()  if len(df) >= 252 else df['Low'].min()
    pct_from_high = (close - high_52w) / high_52w * 100

    one_month_ago = df['Close'].iloc[-22] if len(df) >= 22 else df['Close'].iloc[0]
    pct_1m = (close - one_month_ago) / one_month_ago * 100

    # ── Ichimoku cloud position (Above / In / Below) ────────────
    if not any(pd.isna(v) for v in [ich_cloud_a, ich_cloud_b]):
        cloud_top = max(ich_cloud_a, ich_cloud_b)
        cloud_bot = min(ich_cloud_a, ich_cloud_b)
        ich_status = 'Above' if close > cloud_top else ('Below' if close < cloud_bot else 'In')
    else:
        ich_status = '—'

    return {
        'Ticker'       : ticker.replace('.NS', ''),
        'Score'        : score,
        'Close'        : close,
        'RSI'          : round(rsi, 1),
        'ADX'          : round(adx, 1) if not pd.isna(adx) else 0,
        'ST_Dir'       : int(st_dir) if not pd.isna(st_dir) else 0,
        'Stoch_K'      : round(stoch_k, 1) if not pd.isna(stoch_k) else 0,
        'Vol_Ratio'    : round(vol_ratio, 2),
        '1M_Chg%'      : round(pct_1m, 1),
        'From52wHigh%' : round(pct_from_high, 1),
        'Signals'      : ' | '.join(signals) if signals else 'No signals',
        # ── New indicator values ────────────────────────────────
        'Ich_Cloud'    : ich_status,
        'PSAR_Dir'     : int(psar_trend) if not pd.isna(psar_trend) else 0,
        'Williams_R'   : round(williams_r, 1) if not pd.isna(williams_r) else 0,
        'CMF'          : round(cmf, 3) if not pd.isna(cmf) else 0,
        'Aroon_Up'     : round(aroon_up, 1) if not pd.isna(aroon_up) else 0,
        'Aroon_Dn'     : round(aroon_dn, 1) if not pd.isna(aroon_dn) else 0,
        'HMA_Dir'      : (1 if not pd.isna(hma_now) and not pd.isna(hma_prev3)
                          and hma_now > hma_prev3 else -1),
    }


# ════════════════════════════════════════════════════════════
# SECTION 4 — SCREENER LOOP
# ════════════════════════════════════════════════════════════

def run_screener(tickers, index_name="Nifty 50", top_n=15):
    """
    Loops through all tickers, scores each one, returns top picks.
    Identical to v1 except uses the upgraded score_stock() above.
    """
    print(f"\n{'='*65}")
    print(f"  NIFTY SCREENER v2.0 — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Index: {index_name} | Stocks: {len(tickers)} | Max score: 20")
    print(f"{'='*65}")
    print(f"\n  Scanning {len(tickers)} stocks...\n")

    results = []
    failed  = []

    for idx, ticker in enumerate(tickers):
        pct = int((idx + 1) / len(tickers) * 30)
        bar = '█' * pct + '░' * (30 - pct)
        print(f"\r  [{bar}] {idx+1}/{len(tickers)} — {ticker:<20}", end='', flush=True)

        df = download_and_calculate(ticker, period="1y")

        if df is None:
            failed.append(ticker)
            continue

        result = score_stock(df, ticker)
        if result is not None:
            results.append(result)

        time.sleep(0.15)

    print(f"\n\n  Scanned {len(results)} stocks ({len(failed)} failed)")

    if not results:
        print("  No results.")
        return pd.DataFrame()

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(
        by=['Score', 'ADX', 'Vol_Ratio'],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    return results_df


# ════════════════════════════════════════════════════════════
# SECTION 5 — OUTPUT
# ════════════════════════════════════════════════════════════

def print_watchlist(results_df, top_n=15):
    """Prints formatted watchlist with the 20-point scoring."""

    top = results_df.head(top_n)

    print(f"\n{'='*100}")
    print(f"  TOP {top_n} STOCKS — TODAY'S WATCHLIST  (max score = 20)")
    print(f"{'='*100}")
    print(f"  {'#':<3} {'Ticker':<12} {'Score':>6} {'Close':>8} {'RSI':>5} "
          f"{'ADX':>5} {'ST':>4} {'Vol':>5} {'1M%':>6} {'52wH%':>7}  Signals")
    print(f"  {'-'*98}")

    for rank, row in top.iterrows():
        st_arrow = "UP" if row['ST_Dir'] == 1 else "DN"
        print(
            f"  {rank+1:<3} {row['Ticker']:<12} {row['Score']:>4}/20  "
            f"₹{row['Close']:>7.1f}  {row['RSI']:>4.1f}  {row['ADX']:>4.1f}  "
            f"{st_arrow:>4}  {row['Vol_Ratio']:>4.1f}x  "
            f"{row['1M_Chg%']:>+5.1f}%  {row['From52wHigh%']:>+6.1f}%"
        )
        print(f"       {row['Signals'][:90]}")
        print()

    print(f"{'='*100}")


def print_market_summary(results_df):
    """Market summary adapted for 20-point scoring."""

    total    = len(results_df)
    strong   = len(results_df[results_df['Score'] >= 13])
    moderate = len(results_df[(results_df['Score'] >= 8) & (results_df['Score'] < 13)])
    weak     = len(results_df[results_df['Score'] < 8])

    avg_rsi  = results_df['RSI'].mean()
    avg_adx  = results_df['ADX'].mean()
    pct_bull_st = len(results_df[results_df['ST_Dir'] == 1]) / total * 100
    pct_adv  = len(results_df[results_df['1M_Chg%'] > 0]) / total * 100

    print(f"\n  ── Market Summary ──")
    print(f"  Stocks scanned              : {total}")
    print(f"  Strong signals (13–20/20)   : {strong}  ({round(strong/total*100,1)}%)")
    print(f"  Moderate signals (8–12/20)  : {moderate}  ({round(moderate/total*100,1)}%)")
    print(f"  Weak / no signal (0–7/20)   : {weak}  ({round(weak/total*100,1)}%)")
    print(f"  Average RSI               : {round(avg_rsi,1)}")
    print(f"  Average ADX               : {round(avg_adx,1)}")
    print(f"  Stocks with Supertrend UP : {round(pct_bull_st,1)}%")
    print(f"  Stocks up in last month   : {round(pct_adv,1)}%")

    if avg_rsi > 60 and pct_bull_st > 65:
        mood = "BULLISH — Most stocks trending up with strong Supertrend. Be selective."
    elif avg_rsi < 40 and pct_bull_st < 35:
        mood = "BEARISH — Market under pressure. Only trade highest-conviction setups."
    elif avg_adx > 25 and pct_bull_st > 55:
        mood = "BULLISH BIAS — Trend is strong. Good conditions for momentum trades."
    elif avg_adx < 18:
        mood = "CHOPPY — ADX is low market-wide. Trend strategies will struggle. Be patient."
    else:
        mood = "NEUTRAL — Mixed signals. Wait for clearer setups."

    print(f"\n  Market mood: {mood}")


def save_results(results_df, index_name):
    """Saves full results to CSV."""
    cols = ['Ticker', 'Score', 'Close', 'RSI', 'ADX', 'ST_Dir',
            'Stoch_K', 'Vol_Ratio', '1M_Chg%', 'From52wHigh%', 'Signals']
    filename = f"screener_v2_{index_name}_{datetime.now().strftime('%Y%m%d')}.csv"
    results_df[cols].to_csv(filename, index=False)
    print(f"\n  Results saved: {filename}")


def plot_results(results_df, top_n=15):
    """Score distribution and top picks chart."""

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: score distribution (0–20 now)
    score_counts = results_df['Score'].value_counts().sort_index()
    colors_map   = {s: ('#E24B4A' if s < 8 else '#EF9F27' if s < 13 else '#1D9E75')
                    for s in range(21)}
    bar_colors   = [colors_map.get(s, '#888780') for s in score_counts.index]

    ax1.bar(score_counts.index, score_counts.values,
            color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.5)

    for score, count in score_counts.items():
        ax1.text(score, count + 0.2, str(count),
                 ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax1.set_xlabel('Signal Score (0–20)', fontsize=11)
    ax1.set_ylabel('Number of Stocks', fontsize=11)
    ax1.set_title('Score Distribution (v2 — max 20)', fontsize=12)
    ax1.set_xticks(range(21))
    ax1.grid(True, alpha=0.2, axis='y')
    ax1.axvline(x=12.5, color='#1D9E75', linewidth=1.5,
                linestyle='--', alpha=0.7, label='Strong threshold (13+)')
    ax1.legend(fontsize=9)

    # Right: top N stocks horizontal bar
    top        = results_df.head(top_n).copy()
    top_labels = top['Ticker'].values
    top_scores = top['Score'].values
    top_adx    = top['ADX'].values

    # Colour by ADX strength
    bar_cols = []
    for adx in top_adx:
        if adx > 35:   bar_cols.append('#085041')
        elif adx > 25: bar_cols.append('#1D9E75')
        elif adx > 18: bar_cols.append('#EF9F27')
        else:          bar_cols.append('#E24B4A')

    y_pos = range(len(top_labels))
    ax2.barh(y_pos, top_scores, color=bar_cols, alpha=0.85,
             edgecolor='white', linewidth=0.5, height=0.6)

    for i, (score, adx) in enumerate(zip(top_scores, top_adx)):
        ax2.text(score + 0.05, i, f'ADX={round(adx,0):.0f}',
                 va='center', fontsize=8)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(top_labels, fontsize=9)
    ax2.set_xlabel('Signal Score (max 20)', fontsize=11)
    ax2.set_title(f'Top {top_n} Stocks', fontsize=12)
    ax2.set_xlim(0, 21)
    ax2.axvline(x=13, color='#1D9E75', linewidth=1, linestyle='--',
                alpha=0.7, label='Strong (9+)')
    ax2.grid(True, alpha=0.2, axis='x')
    ax2.legend(fontsize=9)
    ax2.invert_yaxis()

    plt.suptitle(f"Screener v2.0 (20-pt) — {datetime.now().strftime('%d %B %Y')}",
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    fname = f"screener_v2_chart_{datetime.now().strftime('%Y%m%d')}.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"  Chart saved: {fname}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 6 — MAIN
# ════════════════════════════════════════════════════════════

def main():
    """
    Usage:
        python screener_v2.py                      → Nifty 50
        python screener_v2.py --index nifty100     → Nifty 100
        python screener_v2.py --ticker RELIANCE    → Single stock
    """
    args = sys.argv[1:]
    index_name    = 'nifty50'
    single_ticker = None

    if '--index' in args:
        idx = args.index('--index')
        if idx + 1 < len(args):
            index_name = args[idx+1].lower()

    if '--ticker' in args:
        idx = args.index('--ticker')
        if idx + 1 < len(args):
            t = args[idx+1]
            if not t.endswith('.NS'):
                t = t + '.NS'
            single_ticker = t

    if single_ticker:
        tickers = [single_ticker]
        label   = single_ticker.replace('.NS', '')
    else:
        tickers = INDEX_MAP.get(index_name, NIFTY_50)
        label   = index_name.upper()

    results_df = run_screener(tickers, index_name=label)

    if results_df.empty:
        return

    print_watchlist(results_df, top_n=15)
    print_market_summary(results_df)
    save_results(results_df, index_name)
    plot_results(results_df, top_n=15)

    print(f"\n  Screener v2 complete.\n")


if __name__ == "__main__":
    main()