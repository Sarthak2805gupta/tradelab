# ============================================================
# NIFTY STOCK SCREENER — v3.0
# ============================================================
#
# BUILT ON: screener_v2.py (20-point scoring, all indicators)
#
# 6 NEW IMPROVEMENTS IN v3:
#
#   FILTER 1 — Liquidity Pre-Filter
#       Before scoring any stock, check it is actually tradeable.
#       Three measures: ADV (average daily rupee volume), Amihud
#       illiquidity ratio, and volume consistency (% of days active).
#       Illiquid stocks are logged but never scored — saving time.
#
#   FILTER 2 — Fundamental Quality Gate
#       Remove structurally broken stocks regardless of technicals.
#       Checks: PE ratio, promoter holding %, debt-to-equity, and
#       revenue growth. All free via yfinance.info.
#
#   FILTER 3 — Weighted Scoring (replaces equal 1-point system)
#       Not all signals are equally meaningful. Supertrend flip = 3pts.
#       MACD cross = 2pts. RSI level = 1pt. Max score ~35 weighted pts.
#       Score differences now carry real information.
#
#   FILTER 4 — Relative Strength vs Nifty 50
#       Stocks outperforming the index are the true leaders.
#       RS score added as bonus points on top of indicator score.
#       Ranks stocks by composite (indicator + RS) for better ordering.
#
#   FILTER 5 — Market Regime Detection
#       Detects whether the market is Bull / Bear / Sideways using
#       Nifty 50 breadth (% above SMA 50) and index trend.
#       Thresholds for watchlist qualification adjust dynamically —
#       in bear markets only the very highest scores make the cut.
#
#   FILTER 6 — Weekly Timeframe Confirmation (MTF Gate)
#       Daily signals are only scored if the weekly trend agrees.
#       A daily RSI oversold in a weekly downtrend = trap.
#       The same signal in a weekly uptrend = 3x more reliable.
#
# REQUIRES (same folder):
#   complete_indicators.py
#   indicators_extension.py
#   advanced_indicators.py
#
# HOW TO RUN:
#   python screener_v3.py                         # Nifty 50
#   python screener_v3.py --index nifty100        # Nifty 100
#   python screener_v3.py --index nifty500        # Full sample
#   python screener_v3.py --ticker RELIANCE       # Single stock
#   python screener_v3.py --preset large          # Large trader liquidity
#   python screener_v3.py --no-fundamentals       # Skip fundamental check
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import time
import sys
import os
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _root not in sys.path:
    sys.path.insert(0, _root)

from complete_indicators import (
    calc_sma, calc_ema,
    calc_rsi, calc_macd,
    calc_stochastic, calc_cci, calc_roc,
    calc_bollinger, calc_atr,
    calc_keltner, calc_donchian,
    calc_adx, calc_supertrend,
    calc_obv, calc_mfi, calc_vwap,
    calc_ema_ribbon,
    is_hammer, is_bullish_engulfing, is_doji,
)
from indicators_extension import (
    calc_ichimoku, calc_parabolic_sar, calc_williams_r,
    calc_cmf, calc_aroon, calc_pivot_points, calc_camarilla_pivots,
)
from indicators.advanced_indicators import (
    calc_hma, calc_force_index,
)


# ════════════════════════════════════════════════════════════
# STOCK LISTS  (unchanged from v2)
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
    "AMBUJACEM.NS","BANKBARODA.NS","BERGEPAINT.NS","BIOCON.NS","BOSCHLTD.NS",
    "CANBK.NS","CHOLAFIN.NS","COLPAL.NS","DABUR.NS","DLF.NS","GAIL.NS",
    "GODREJCP.NS","HAVELLS.NS","ICICIPRULI.NS","INDHOTEL.NS","IOC.NS","IRCTC.NS",
    "LUPIN.NS","MARICO.NS","MCDOWELL-N.NS","MUTHOOTFIN.NS","NAUKRI.NS","OFSS.NS",
    "PAGEIND.NS","PEL.NS","PIDILITIND.NS","PNB.NS","RECLTD.NS","SAIL.NS",
    "SIEMENS.NS","SRF.NS","TORNTPHARM.NS","TRENT.NS","TVSMOTOR.NS","VOLTAS.NS",
    "ZOMATO.NS","LTIM.NS","ATGL.NS","ICICIGI.NS","PGHH.NS",
]
NIFTY_500_SAMPLE = NIFTY_100 + [
    "AUROPHARMA.NS","BEL.NS","BHEL.NS","CROMPTON.NS","CUMMINSIND.NS",
    "ESCORTS.NS","FEDERALBNK.NS","FORTIS.NS","GODREJPROP.NS","HAL.NS",
    "IDFCFIRSTB.NS","INDIGO.NS","INTELLECT.NS","IGL.NS","JINDALSTEL.NS",
    "JUBLFOOD.NS","KAJARIACER.NS","KPITTECH.NS","LALPATHLAB.NS",
    "LAURUSLABS.NS","LICHSGFIN.NS","MANAPPURAM.NS","MOTHERSON.NS",
    "MPHASIS.NS","MRF.NS","NMDC.NS","OBEROIRLTY.NS","PERSISTENT.NS",
    "PETRONET.NS","POLYCAB.NS","RBLBANK.NS","TATACOMM.NS","TATACHEM.NS",
    "TATAELXSI.NS","TORNTPOWER.NS","TRIDENT.NS","UNIONBANK.NS","VBL.NS",
]
INDEX_MAP = {
    'nifty50':  NIFTY_50,
    'nifty100': NIFTY_100,
    'nifty500': NIFTY_500_SAMPLE,
}



# ════════════════════════════════════════════════════════════
# FILTER 1 — LIQUIDITY PRE-FILTER
# Runs BEFORE indicator calculation. Saves time + removes
# untradeable stocks from watchlist entirely.
# ════════════════════════════════════════════════════════════

LIQUIDITY_PRESETS = {
    'small':         {'min_adv_crores': 0.5,  'min_avg_volume': 25000,  'max_amihud': 0.50, 'min_consistency': 60},
    'medium':        {'min_adv_crores': 2.0,  'min_avg_volume': 75000,  'max_amihud': 0.20, 'min_consistency': 70},
    'large':         {'min_adv_crores': 10.0, 'min_avg_volume': 200000, 'max_amihud': 0.05, 'min_consistency': 80},
    'institutional': {'min_adv_crores': 50.0, 'min_avg_volume': 500000, 'max_amihud': 0.01, 'min_consistency': 90},
}


def check_liquidity(df, preset='medium'):
    """
    Three-measure liquidity check.

    Measure 1 — Average Daily Value (ADV):
        Rupees traded per day on average (Close x Volume, 20-day rolling).
        Your trade should be < 1% of ADV. Rs 1 lakh trade needs Rs 1 crore ADV.

    Measure 2 — Amihud Illiquidity Ratio:
        Price impact per crore of volume traded.
        Low ratio = price barely moves per unit of volume = liquid.
        High ratio = even small orders move the price = illiquid trap.
        Formula: avg(|daily return| / daily rupee volume in crores)

    Measure 3 — Volume Consistency:
        % of recent days where volume was above a meaningful minimum.
        Catches the block-deal trap: one 5-crore block deal inflates
        the 20-day average even if the stock barely trades on other days.

    Returns:
        dict: passes (bool), adv_crores, amihud, consistency, grade, reasons
    """
    cfg     = LIQUIDITY_PRESETS.get(preset, LIQUIDITY_PRESETS['medium'])
    reasons = []
    passes  = True

    if len(df) < 20:
        return {'passes': False, 'adv_crores': 0, 'adv_shares': 0,
                'amihud': 999, 'consistency': 0, 'grade': 'F',
                'reasons': ['Insufficient data']}

    # ── ADV ──
    daily_val  = df['Close'] * df['Volume']
    adv_rupees = daily_val.rolling(20, min_periods=20).mean()
    adv_crores = round(adv_rupees.iloc[-1] / 1e7, 2) if not pd.isna(adv_rupees.iloc[-1]) else 0
    adv_shares = int(df['Volume'].rolling(20, min_periods=20).mean().iloc[-1]) if not pd.isna(df['Volume'].rolling(20).mean().iloc[-1]) else 0

    if adv_crores < cfg['min_adv_crores']:
        passes = False
        reasons.append(f"ADV Rs{adv_crores:.1f}Cr < min Rs{cfg['min_adv_crores']}Cr")
    if adv_shares < cfg['min_avg_volume']:
        passes = False
        reasons.append(f"Avg vol {adv_shares:,} < min {cfg['min_avg_volume']:,} shares")

    # ── Amihud ──
    abs_ret   = (df['Close'] / df['Close'].shift(1) - 1).abs()
    rvol_cr   = (df['Close'] * df['Volume'] / 1e7).replace(0, np.nan)
    daily_ami = abs_ret / rvol_cr
    p99       = daily_ami.quantile(0.99)
    amihud    = round(daily_ami.clip(upper=p99).rolling(20, min_periods=20).mean().iloc[-1], 4)
    if pd.isna(amihud): amihud = 999.0

    if amihud > cfg['max_amihud']:
        passes = False
        reasons.append(f"Amihud {amihud:.3f} > max {cfg['max_amihud']}")

    # ── Consistency ──
    period    = min(60, len(df))
    min_v     = max(cfg['min_avg_volume'] // 5, 5000)
    recent    = df['Volume'].iloc[-period:]
    cons_pct  = round((recent >= min_v).sum() / len(recent) * 100, 1)
    zero_days = int((recent == 0).sum())

    if cons_pct < cfg['min_consistency']:
        passes = False
        reasons.append(f"Consistency {cons_pct}% < min {cfg['min_consistency']}%")
    if zero_days > 3:
        passes = False
        reasons.append(f"{zero_days} zero-volume days in 60d")

    # ── Grade ──
    adv_r  = adv_crores / max(cfg['min_adv_crores'], 0.01)
    ami_r  = cfg['max_amihud'] / max(amihud, 0.001)
    comp   = adv_r * 0.5 + ami_r * 0.3 + (cons_pct / 100) * 0.2
    grade  = 'A' if comp >= 5 else 'B' if comp >= 2 else 'C' if comp >= 1 else 'D' if comp >= 0.5 else 'F'

    return {
        'passes':      passes,
        'adv_crores':  adv_crores,
        'adv_shares':  adv_shares,
        'amihud':      amihud,
        'consistency': cons_pct,
        'zero_days':   zero_days,
        'grade':       grade,
        'reasons':     reasons,
    }


# ════════════════════════════════════════════════════════════
# FILTER 2 — FUNDAMENTAL QUALITY GATE
# Removes structurally broken stocks regardless of technicals.
# Uses yfinance.info — free, no API key needed.
# ════════════════════════════════════════════════════════════

def check_fundamentals(ticker):
    """
    Four fundamental filters to remove structural traps.

    PE Ratio:
        Stocks with PE > 200 are either wildly speculative or
        earnings are near-zero (denominator problem). Avoid.
        PE < 0 means the company is loss-making. Flag it.

    Promoter Holding:
        In Indian markets, promoter holding < 25% is a warning.
        Low promoter holding means the people who built the company
        don't trust it enough to hold significant stake.
        Holding < 10% is a serious red flag.

    Debt-to-Equity:
        D/E > 2.0 means debt is 2x equity — highly leveraged.
        A technical breakout in an over-leveraged company often
        fails because rising interest costs erode earnings.
        Exception: banks and NBFCs naturally have high D/E.

    Revenue Growth:
        Negative revenue growth (shrinking business) + bullish
        technicals = technical pattern in a fundamentally declining
        stock. These fail more often than they succeed.

    Returns:
        dict: passes (bool), reasons (list), fundamental data dict
    """
    try:
        info    = yf.Ticker(ticker).info
        reasons = []
        passes  = True
        data    = {}

        # PE Ratio
        pe = info.get('trailingPE', None)
        data['PE'] = round(pe, 1) if pe else 'N/A'
        if pe is not None:
            if pe < 0:
                passes = False
                reasons.append(f"PE={round(pe,1)} (loss-making company)")
            elif pe > 200:
                passes = False
                reasons.append(f"PE={round(pe,1)} > 200 (wildly overvalued or near-zero earnings)")

        # Promoter / Insider Holding
        promoter = info.get('heldPercentInsiders', None)
        if promoter is not None:
            promoter_pct = round(promoter * 100, 1)
            data['Promoter%'] = promoter_pct
            if promoter_pct < 10:
                passes = False
                reasons.append(f"Promoter holding {promoter_pct}% < 10% (serious red flag)")
            elif promoter_pct < 25:
                # Warn but don't fail — many good companies have lower promoter holding
                reasons.append(f"Promoter holding {promoter_pct}% < 25% (watch)")
        else:
            data['Promoter%'] = 'N/A'

        # Debt to Equity
        de = info.get('debtToEquity', None)
        data['D/E'] = round(de / 100, 2) if de is not None else 'N/A'
        # yfinance returns D/E as percentage (150 = 1.5x), so divide by 100
        if de is not None:
            de_ratio = de / 100
            sector = info.get('sector', '').lower()
            # Banks and financial companies naturally have high D/E — exempt them
            is_financial = any(s in sector for s in ['financial', 'bank', 'insurance'])
            if not is_financial and de_ratio > 2.0:
                passes = False
                reasons.append(f"D/E={round(de_ratio,1)} > 2.0 (over-leveraged)")

        # Revenue Growth (year-over-year)
        rev_growth = info.get('revenueGrowth', None)
        data['RevGrowth%'] = round(rev_growth * 100, 1) if rev_growth is not None else 'N/A'
        if rev_growth is not None and rev_growth < -0.15:
            # Only fail if revenue is shrinking more than 15% — mild declines are ok
            passes = False
            reasons.append(f"Revenue growth {round(rev_growth*100,1)}% < -15% (shrinking business)")

        return {
            'passes':  passes,
            'reasons': reasons,
            'data':    data,
        }

    except Exception:
        # If we can't get fundamental data, don't fail the stock — just pass through
        return {'passes': True, 'reasons': ['Fundamental data unavailable — skipped'], 'data': {}}


# ════════════════════════════════════════════════════════════
# FILTER 5 — MARKET REGIME DETECTION
# Runs once before the full scan. Determines whether the market
# is Bull / Bear / Sideways and adjusts qualifying thresholds.
# ════════════════════════════════════════════════════════════

def detect_market_regime():
    """
    Detects the current market regime using Nifty 50.

    Three signals used together:
        1. Nifty 50 vs its own SMA 50 and SMA 200
           (is the index itself in an uptrend or downtrend?)
        2. % of Nifty 50 stocks above their SMA 50
           (market breadth — is the move broad or narrow?)
        3. Nifty 50's own RSI
           (momentum of the index)

    Regime definitions:
        BULL: Index above SMA 200, >60% stocks above SMA 50, RSI > 50
        BEAR: Index below SMA 200, <40% stocks above SMA 50, RSI < 45
        SIDEWAYS: Everything in between

    Why regime matters for the screener:
        Bull regime  → set qualify threshold at score >= 18 (many stocks qualify, be selective)
        Sideways     → threshold >= 20 (be more selective, fewer false breakouts)
        Bear regime  → threshold >= 24 (only the very strongest survive)

    Returns:
        dict with regime ('BULL'/'BEAR'/'SIDEWAYS'), breadth_pct, nifty_rsi, details
    """
    print("\n  Detecting market regime...")
    try:
        # Download Nifty 50 index
        nifty = yf.download("^NSEI", period="1y", auto_adjust=True, progress=False)
        if isinstance(nifty.columns, pd.MultiIndex):
            nifty.columns = nifty.columns.get_level_values(0)
        nifty.dropna(inplace=True)

        if len(nifty) < 60:
            return {'regime': 'SIDEWAYS', 'breadth_pct': 50, 'nifty_rsi': 50,
                    'qualify_score': 18, 'details': 'Insufficient Nifty data'}

        nifty_close  = nifty['Close']
        nifty_sma50  = calc_sma(nifty_close, 50).iloc[-1]
        nifty_sma200 = calc_sma(nifty_close, 200).iloc[-1]
        nifty_rsi    = round(calc_rsi(nifty_close, 14).iloc[-1], 1)
        nifty_now    = round(nifty_close.iloc[-1], 0)

        above_sma50  = nifty_now > nifty_sma50
        above_sma200 = nifty_now > nifty_sma200

        # Breadth: download all Nifty 50 stocks and check % above SMA 50
        breadth_df = yf.download(NIFTY_50, period="3mo", auto_adjust=True, progress=False)['Close']
        if isinstance(breadth_df.columns, pd.MultiIndex):
            breadth_df.columns = breadth_df.columns.get_level_values(0)

        above_count = 0
        valid_count = 0
        for col in breadth_df.columns:
            series = breadth_df[col].dropna()
            if len(series) >= 50:
                sma50_val = series.rolling(50).mean().iloc[-1]
                if not pd.isna(sma50_val):
                    valid_count += 1
                    if series.iloc[-1] > sma50_val:
                        above_count += 1

        breadth_pct = round(above_count / max(valid_count, 1) * 100, 1)

        # Determine regime
        bull_signals = sum([
            above_sma200,
            above_sma50,
            breadth_pct > 60,
            nifty_rsi > 50,
        ])

        bear_signals = sum([
            not above_sma200,
            not above_sma50,
            breadth_pct < 40,
            nifty_rsi < 45,
        ])

        if bull_signals >= 3:
            regime         = 'BULL'
            qualify_score  = 18   # Many stocks look good — be selective
            regime_advice  = 'Good conditions for swing trades. Score >= 18 to qualify.'
        elif bear_signals >= 3:
            regime         = 'BEAR'
            qualify_score  = 24   # Only the very strongest setups
            regime_advice  = 'High risk environment. Only score >= 24 qualifies. Reduce size.'
        else:
            regime         = 'SIDEWAYS'
            qualify_score  = 20   # Moderate selectivity
            regime_advice  = 'Mixed signals. Score >= 20 to qualify. Wait for clarity.'

        details = (f"Nifty={nifty_now:.0f} | "
                   f"{'Above' if above_sma200 else 'Below'} SMA200 | "
                   f"{'Above' if above_sma50 else 'Below'} SMA50 | "
                   f"Breadth={breadth_pct}% | RSI={nifty_rsi}")

        print(f"  Regime: {regime} | {details}")
        print(f"  Qualify threshold: score >= {qualify_score}")

        return {
            'regime':        regime,
            'breadth_pct':   breadth_pct,
            'nifty_rsi':     nifty_rsi,
            'qualify_score': qualify_score,
            'regime_advice': regime_advice,
            'details':       details,
        }

    except Exception as e:
        print(f"  Regime detection failed ({e}) — using SIDEWAYS default")
        return {'regime': 'SIDEWAYS', 'breadth_pct': 50, 'nifty_rsi': 50,
                'qualify_score': 20, 'regime_advice': 'Defaulting to SIDEWAYS.',
                'details': 'Detection failed'}


# ════════════════════════════════════════════════════════════
# FILTER 4 — RELATIVE STRENGTH vs NIFTY
# Downloaded once, reused for all stocks.
# ════════════════════════════════════════════════════════════

def download_nifty_returns():
    """
    Downloads Nifty 50 closing prices once.
    Used to calculate each stock's RS rating during scoring.
    Returns close price Series, or None if download fails.
    """
    try:
        nifty = yf.download("^NSEI", period="1y", auto_adjust=True, progress=False)
        if isinstance(nifty.columns, pd.MultiIndex):
            nifty.columns = nifty.columns.get_level_values(0)
        nifty.dropna(inplace=True)
        return nifty['Close']
    except Exception:
        return None


def calc_rs_rating(stock_close, nifty_close):
    """
    Relative Strength Rating vs Nifty 50.

    Measures how much a stock outperforms or underperforms
    the Nifty 50 index over the last 3 months (63 trading days).

    Formula:
        Stock 3-month return  = (Close / Close[63d ago] - 1) x 100
        Nifty 3-month return  = (Nifty / Nifty[63d ago] - 1) x 100
        RS Score              = Stock return - Nifty return

    Interpretation:
        RS > +10% : Stock significantly outperforming Nifty — leader
        RS 0-10%  : Mild outperformance — in line with market
        RS < 0    : Underperforming — avoid (money rotating elsewhere)
        RS < -10% : Significantly lagging — likely in distribution

    Bonus scoring:
        RS > +10% → +3 bonus points (clear leader)
        RS > +5%  → +2 bonus points (modest outperformer)
        RS > 0%   → +1 bonus point  (at least keeping pace)
        RS <= 0   → 0 bonus points  (no leadership premium)

    Parameters:
        stock_close (Series): Stock daily closing prices
        nifty_close (Series): Nifty 50 daily closing prices

    Returns:
        dict with rs_score, bonus_pts, label
    """
    try:
        # Align stock and Nifty to the same dates
        common_dates = stock_close.index.intersection(nifty_close.index)
        if len(common_dates) < 63:
            return {'rs_score': 0, 'bonus_pts': 0, 'label': 'N/A'}

        s_close  = stock_close[common_dates]
        n_close  = nifty_close[common_dates]

        # 3-month (63-day) returns
        s_return = (s_close.iloc[-1] / s_close.iloc[-63] - 1) * 100
        n_return = (n_close.iloc[-1] / n_close.iloc[-63] - 1) * 100

        rs_score = round(s_return - n_return, 2)

        if rs_score > 10:
            bonus_pts = 3
            label     = f"RS+{rs_score:.1f}% — market leader"
        elif rs_score > 5:
            bonus_pts = 2
            label     = f"RS+{rs_score:.1f}% — outperformer"
        elif rs_score > 0:
            bonus_pts = 1
            label     = f"RS+{rs_score:.1f}% — mild outperformer"
        else:
            bonus_pts = 0
            label     = f"RS{rs_score:.1f}% — lagging Nifty"

        return {'rs_score': rs_score, 'bonus_pts': bonus_pts, 'label': label}

    except Exception:
        return {'rs_score': 0, 'bonus_pts': 0, 'label': 'N/A'}



# ════════════════════════════════════════════════════════════
# DATA DOWNLOAD + ALL INDICATORS
# Identical to v2, plus weekly data for Filter 6 (MTF)
# ════════════════════════════════════════════════════════════

def download_and_calculate(ticker, period="1y"):
    """
    Downloads daily OHLCV and calculates all 20 indicators (same as v2).
    Additionally downloads weekly data for multi-timeframe gate (Filter 6).

    Returns:
        tuple: (df_daily, df_weekly) or (None, None) if download fails
        df_weekly contains: weekly Close, SMA_20w, RSI_14w, MACD weekly
    """
    try:
        # ── Daily data ──
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if len(df) < 210:
            return None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.dropna(subset=['Open','High','Low','Close','Volume'], inplace=True)
        if len(df) < 210:
            return None, None

        # Daily indicators (unchanged from v2)
        df['SMA_20']  = calc_sma(df['Close'], 20)
        df['SMA_50']  = calc_sma(df['Close'], 50)
        df['SMA_200'] = calc_sma(df['Close'], 200)
        df['EMA_9']   = calc_ema(df['Close'], 9)
        df['EMA_20']  = calc_ema(df['Close'], 20)

        ribbon = calc_ema_ribbon(df['Close'], [9, 21, 34, 55, 89, 144])
        for p, vals in ribbon.items():
            df[f'EMA_{p}'] = vals

        df['RSI']                            = calc_rsi(df['Close'], 14)
        df['Stoch_K'], df['Stoch_D']         = calc_stochastic(df, 14, 3, 3)
        df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calc_macd(df['Close'])
        df['ATR']                            = calc_atr(df, 14)

        (df['BB_Mid'], df['BB_Up'], df['BB_Lo'],
         df['PctB'],   df['BW'])             = calc_bollinger(df['Close'])
        (df['KC_Mid'], df['KC_Up'], df['KC_Lo']) = calc_keltner(df)
        (df['DC_Up'],  df['DC_Mid'], df['DC_Lo']) = calc_donchian(df, 20)

        df['Squeeze']  = (df['BB_Up'] - df['BB_Lo']) < (df['KC_Up'] - df['KC_Lo'])
        df['ADX'], df['DI_Plus'], df['DI_Minus'] = calc_adx(df, 14)
        df['Supertrend'], df['ST_Dir']            = calc_supertrend(df, period=7, multiplier=3.0)

        df['VMA']       = calc_sma(df['Volume'].astype(float), 20)
        df['Vol_Ratio'] = df['Volume'] / df['VMA']
        df['OBV']       = calc_obv(df['Close'], df['Volume'])
        df['MFI']       = calc_mfi(df, 14)

        df['MACD_Cross_Up'] = (
            (df['MACD'] > df['MACD_Signal']) &
            (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
        )

        # Extension indicators
        df['Ich_Tenkan'], df['Ich_Kijun'], _, _, _ = calc_ichimoku(df)
        df['Ich_Cloud_A'] = ((df['Ich_Tenkan'] + df['Ich_Kijun']) / 2).shift(26)
        df['Ich_Cloud_B'] = (
            (df['High'].rolling(52).max() + df['Low'].rolling(52).min()) / 2
        ).shift(26)
        df['PSAR'], df['PSAR_Trend'] = calc_parabolic_sar(df)
        df['Williams_R']             = calc_williams_r(df, 14)
        df['CMF']                    = calc_cmf(df, 20)
        df['Aroon_Up'], df['Aroon_Dn'], df['Aroon_Osc'] = calc_aroon(df, 25)
        df['HMA_21']    = calc_hma(df['Close'], 21)
        df['Force_Idx'] = calc_force_index(df, 13)

        # ── FILTER 6: Weekly data for MTF gate ──
        dfw = yf.download(ticker, period="2y", interval="1wk",
                          auto_adjust=True, progress=False)
        if isinstance(dfw.columns, pd.MultiIndex):
            dfw.columns = dfw.columns.get_level_values(0)
        dfw.dropna(subset=['Close'], inplace=True)

        weekly_ok = False
        if len(dfw) >= 26:
            dfw['SMA_20w']  = calc_sma(dfw['Close'], 20)
            dfw['SMA_10w']  = calc_sma(dfw['Close'], 10)
            dfw['RSI_14w']  = calc_rsi(dfw['Close'], 14)
            (dfw['MACD_w'], dfw['Signal_w'], _) = calc_macd(dfw['Close'])
            weekly_ok = True

        return df, (dfw if weekly_ok else None)

    except Exception:
        return None, None


# ════════════════════════════════════════════════════════════
# FILTER 6 — WEEKLY MTF GATE
# Checks weekly trend before allowing daily signals to score.
# ════════════════════════════════════════════════════════════

def check_weekly_gate(dfw):
    """
    Weekly timeframe confirmation gate (Multi-Timeframe = MTF).

    The core insight:
        A daily oversold RSI reading in a weekly uptrend = buy opportunity.
        The same daily oversold RSI in a weekly downtrend = falling knife.
        Weekly trend alignment roughly triples the win rate of daily signals.

    Three weekly checks:
        1. Price above weekly SMA 20 (medium-term uptrend)
        2. Weekly RSI above 45 (not in a downward spiral)
        3. Weekly MACD positive or rising (weekly momentum not collapsed)

    Gate logic:
        All 3 pass → STRONG gate: full scoring applies, +2 bonus pts
        2 of 3 pass → MODERATE gate: full scoring applies
        1 of 3 pass → WEAK gate: score capped at 50% of max
        0 pass      → BLOCKED: skip daily scoring entirely

    Returns:
        dict with gate_level ('STRONG'/'MODERATE'/'WEAK'/'BLOCKED'),
        bonus_pts, weekly_rsi, weekly_trend, cap_score
    """
    if dfw is None or len(dfw) < 10:
        # No weekly data — allow scoring but no bonus
        return {'gate_level': 'MODERATE', 'bonus_pts': 0,
                'weekly_rsi': 50, 'weekly_trend': 'Unknown',
                'cap_score': None, 'details': 'Weekly data unavailable'}

    last_w = dfw.iloc[-1]
    close_w     = last_w['Close']
    sma20w      = last_w['SMA_20w']
    rsi_w       = last_w['RSI_14w']
    macd_w      = last_w['MACD_w']
    signal_w    = last_w['Signal_w']

    if pd.isna(sma20w) or pd.isna(rsi_w):
        return {'gate_level': 'MODERATE', 'bonus_pts': 0,
                'weekly_rsi': 50, 'weekly_trend': 'Unknown',
                'cap_score': None, 'details': 'Insufficient weekly indicator data'}

    # Weekly checks
    above_sma20w  = close_w > sma20w
    rsi_ok        = rsi_w > 45
    macd_ok       = (not pd.isna(macd_w) and not pd.isna(signal_w) and
                     (macd_w > signal_w or macd_w > dfw['MACD_w'].iloc[-2]))

    passes = sum([above_sma20w, rsi_ok, macd_ok])

    weekly_trend = 'Uptrend' if above_sma20w else 'Downtrend'

    if passes == 3:
        gate_level = 'STRONG'
        bonus_pts  = 2
        cap_score  = None
        detail     = f"Weekly: {weekly_trend} | RSI_w={round(rsi_w,1)} | MACD_w bullish"
    elif passes == 2:
        gate_level = 'MODERATE'
        bonus_pts  = 0
        cap_score  = None
        detail     = f"Weekly: {weekly_trend} | RSI_w={round(rsi_w,1)} | {passes}/3 checks pass"
    elif passes == 1:
        gate_level = 'WEAK'
        bonus_pts  = 0
        cap_score  = 15   # Daily score capped — weekly trend weak
        detail     = f"Weekly: {weekly_trend} | RSI_w={round(rsi_w,1)} | Only {passes}/3 pass"
    else:
        gate_level = 'BLOCKED'
        bonus_pts  = 0
        cap_score  = 0    # No score at all — weekly trend fully bearish
        detail     = f"Weekly downtrend confirmed. Daily signals unreliable."

    return {
        'gate_level':  gate_level,
        'bonus_pts':   bonus_pts,
        'weekly_rsi':  round(rsi_w, 1),
        'weekly_trend': weekly_trend,
        'cap_score':   cap_score,
        'details':     detail,
    }


# ════════════════════════════════════════════════════════════
# FILTER 3 — WEIGHTED SCORING ENGINE
# Replaces the equal 1-point-per-condition system from v2.
# Each condition now carries weight proportional to its
# historical reliability as a buy signal.
# ════════════════════════════════════════════════════════════

# Weights for each of the 20 conditions
# Higher weight = condition is more reliable / more rare
# The old system gave 1 point each (max 20)
# New system max ≈ 35 weighted points
WEIGHTS = {
    # Original 8 conditions
    'sma200'       : 1,   # Basic filter — necessary but not sufficient
    'golden_cross' : 2,   # Strong long-term alignment
    'rsi_sweet'    : 1,   # Context signal
    'macd_cross'   : 2,   # Timing signal — meaningful crossover
    'bb_setup'     : 2,   # Volatility setup — squeeze is powerful
    'high_volume'  : 1,   # Confirmation
    'obv_rising'   : 1,   # Volume trend confirmation
    'candle_pat'   : 1,   # Timing precision — minor weight

    # New 5 conditions (v2 upgrade)
    'adx_strong'   : 2,   # Trend strength confirmed — important filter
    'supertrend'   : 3,   # Most reliable single signal on NSE
    'donchian_brk' : 2,   # Breakout with volume — strong momentum
    'stoch_oversold': 1,  # Faster than RSI — context
    'bb_kc_squeeze': 2,   # True squeeze — rare and explosive

    # Extension indicators (v2 upgrade)
    'ichimoku'     : 2,   # Multi-component system — strong when confirmed
    'psar_bull'    : 2,   # Clear trend signal — stops flipping
    'williams_r'   : 1,   # Faster stochastic — context
    'cmf_accum'    : 2,   # Institutional accumulation signal
    'aroon_trend'  : 2,   # Early trend detection
    'hma_rising'   : 1,   # Low-lag trend filter
    'force_idx'    : 1,   # Volume × price momentum
}

MAX_WEIGHTED_SCORE = sum(WEIGHTS.values())   # 35

# Human-readable metadata for each of the 20 scoring conditions.
# Used by the browser UI Scoring Customizer (stock.html).
CONDITIONS_META = [
    {'key': 'sma200',        'label': 'Above SMA 200',          'category': 'Trend',     'desc': 'Price above 200-day moving average — long-term uptrend intact'},
    {'key': 'golden_cross',  'label': 'Golden Cross Zone',       'category': 'Trend',     'desc': 'SMA50 above SMA200 — long-term bullish alignment confirmed'},
    {'key': 'rsi_sweet',     'label': 'RSI Sweet Spot',          'category': 'Momentum',  'desc': 'RSI 30–55 — momentum building, not yet overbought'},
    {'key': 'macd_cross',    'label': 'MACD Bullish Cross',      'category': 'Momentum',  'desc': 'MACD crossed above signal line within the last 3 days'},
    {'key': 'bb_setup',      'label': 'BB Squeeze / Near Low',   'category': 'Volatility','desc': 'Bollinger Band squeeze or price near lower band — setup forming'},
    {'key': 'high_volume',   'label': 'High Volume Surge',        'category': 'Volume',    'desc': 'Volume ≥1.5× 20-day average — institutional participation'},
    {'key': 'obv_rising',    'label': 'OBV Rising (10d)',         'category': 'Volume',    'desc': 'On-Balance Volume trending up over 10 days — buyers in control'},
    {'key': 'candle_pat',    'label': 'Candlestick Pattern',      'category': 'Pattern',   'desc': 'Hammer or bullish engulfing candle within the last 3 days'},
    {'key': 'adx_strong',    'label': 'ADX > 25 (Strong Trend)', 'category': 'Trend',     'desc': 'ADX above 25 — confirms a strong directional trend is active'},
    {'key': 'supertrend',    'label': 'Supertrend Bullish',       'category': 'Trend',     'desc': 'Supertrend indicator is bullish — most reliable signal on NSE'},
    {'key': 'donchian_brk',  'label': 'Donchian Breakout',        'category': 'Breakout',  'desc': 'Price breaks 20-day high with volume ≥1.3× — momentum breakout'},
    {'key': 'stoch_oversold','label': 'Stochastic Oversold',      'category': 'Momentum',  'desc': 'Stoch %K < 35 and rising — early oversold reversal signal'},
    {'key': 'bb_kc_squeeze', 'label': 'BB+KC True Squeeze',       'category': 'Volatility','desc': 'Bollinger Band inside Keltner Channel — big move imminent'},
    {'key': 'ichimoku',      'label': 'Ichimoku Bullish',         'category': 'Trend',     'desc': 'Price above cloud and Tenkan ≥ Kijun — multi-component bullish'},
    {'key': 'psar_bull',     'label': 'PSAR Bullish',             'category': 'Trend',     'desc': 'Parabolic SAR flipped bullish — clear trend direction signal'},
    {'key': 'williams_r',    'label': 'Williams %R Recovering',   'category': 'Momentum',  'desc': 'Williams %R < -60 and rising — oversold recovery in progress'},
    {'key': 'cmf_accum',     'label': 'CMF Accumulation',         'category': 'Volume',    'desc': 'Chaikin Money Flow > 0.05 — institutional accumulation signal'},
    {'key': 'aroon_trend',   'label': 'Aroon Trend Signal',       'category': 'Trend',     'desc': 'Aroon Up > 70 and above Aroon Down — early trend detection'},
    {'key': 'hma_rising',    'label': 'HMA (21) Rising',          'category': 'Trend',     'desc': 'Hull Moving Average rising over 3 days — low-lag trend filter'},
    {'key': 'force_idx',     'label': 'Force Index Positive',     'category': 'Volume',    'desc': 'Force Index > 0 — volume × price momentum is positive'},
]


def score_stock(df, ticker, nifty_close=None, liq_result=None, custom_weights=None):
    """
    Weighted scoring engine — scores a stock across all 20 conditions
    with condition-specific weights, then adds:
        - Relative Strength bonus (0-3 pts) from Filter 4
        - Weekly MTF gate (blocks/caps/bonus) from Filter 6

    All 20 conditions are identical to v2 — only the point values changed.

    Parameters:
        df (DataFrame): Daily OHLCV + all indicator columns
        ticker (str): Stock symbol
        nifty_close (Series): Nifty close prices for RS calculation
        liq_result (dict): Pre-computed liquidity result (for grade display)
        custom_weights (dict|None): Per-key weight overrides. Keys with weight=0
                                    are effectively disabled. If None, uses WEIGHTS.

    Returns:
        dict with weighted_score, bonus_pts, total_score, signals, etc.
    """
    if len(df) < 210:
        return None

    # Merge default weights with any user overrides (weight=0 disables that condition)
    _w = {**WEIGHTS, **(custom_weights or {})}

    last  = df.iloc[-1]
    prev  = df.iloc[-2]

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

    ich_tenkan  = last['Ich_Tenkan']
    ich_kijun   = last['Ich_Kijun']
    ich_cloud_a = last['Ich_Cloud_A']
    ich_cloud_b = last['Ich_Cloud_B']
    psar_trend  = last['PSAR_Trend']
    williams_r  = last['Williams_R']
    williams_rp = prev['Williams_R']
    cmf         = last['CMF']
    aroon_up    = last['Aroon_Up']
    aroon_dn    = last['Aroon_Dn']
    hma_now     = last['HMA_21']
    hma_prev3   = df['HMA_21'].iloc[-4]
    force_idx   = last['Force_Idx']

    if any(pd.isna(v) for v in [sma50, sma200, rsi, pctb, vol_ratio]):
        return None

    score    = 0
    signals  = []
    cond_map = {}   # tracks which of the 20 conditions triggered

    # ── 20 scoring conditions with weights ────────────────

    if close > sma200 and _w.get('sma200', 0) > 0:
        cond_map['sma200'] = True
        score += _w['sma200']
        signals.append(f"Above SMA200 (Rs{round(sma200,1)})")

    if sma50 > sma200 and _w.get('golden_cross', 0) > 0:
        cond_map['golden_cross'] = True
        score += _w['golden_cross']
        signals.append("Golden Cross zone")

    if 30 <= rsi <= 55 and _w.get('rsi_sweet', 0) > 0:
        cond_map['rsi_sweet'] = True
        score += _w['rsi_sweet']
        signals.append(f"RSI sweet spot ({round(rsi,1)})")
    elif rsi < 30:
        signals.append(f"RSI oversold ({round(rsi,1)})")

    macd_cross = False
    for lb in range(1, 4):
        if len(df) > lb + 1:
            m_now  = df['MACD'].iloc[-lb];  m_prev = df['MACD'].iloc[-lb-1]
            s_now  = df['MACD_Signal'].iloc[-lb]; s_prev = df['MACD_Signal'].iloc[-lb-1]
            if not any(pd.isna(v) for v in [m_now, m_prev, s_now, s_prev]):
                if m_prev < s_prev and m_now > s_now:
                    macd_cross = True
                    day_str = f"{lb-1}d ago" if lb > 1 else "today"
                    signals.append(f"MACD bullish cross ({day_str})")
                    break
    if macd_cross and _w.get('macd_cross', 0) > 0:
        cond_map['macd_cross'] = True
        score += _w['macd_cross']

    bw_min = df['BW'].iloc[-50:].min() if len(df) >= 50 else df['BW'].min()
    if _w.get('bb_setup', 0) > 0:
        if bw <= bw_min * 1.05:
            cond_map['bb_setup'] = True
            score += _w['bb_setup']
            signals.append(f"BB Squeeze (BW={round(bw,1)}%)")
        elif pctb < 0.15:
            cond_map['bb_setup'] = True
            score += _w['bb_setup']
            signals.append(f"Near lower BB (%B={round(pctb,2)})")

    if not pd.isna(vol_ratio) and vol_ratio >= 1.5 and _w.get('high_volume', 0) > 0:
        cond_map['high_volume'] = True
        score += _w['high_volume']
        signals.append(f"High volume ({round(vol_ratio,1)}x)")

    obv_series = df['OBV'].iloc[-11:]
    if len(obv_series) >= 11 and obv_series.iloc[-1] > obv_series.iloc[0] and _w.get('obv_rising', 0) > 0:
        cond_map['obv_rising'] = True
        score += _w['obv_rising']
        signals.append("OBV rising (10d)")

    pattern_found = False
    for lb in [1, 2, 3]:
        if len(df) >= lb and is_hammer(df.iloc[-lb]):
            signals.append(f"Hammer ({lb}d ago)")
            pattern_found = True; break
    if not pattern_found:
        for lb in [1, 2, 3]:
            if len(df) >= lb + 1 and is_bullish_engulfing(df.iloc[-lb-1], df.iloc[-lb]):
                signals.append(f"Bullish engulfing ({lb}d ago)")
                pattern_found = True; break
    if pattern_found and _w.get('candle_pat', 0) > 0:
        cond_map['candle_pat'] = True
        score += _w['candle_pat']

    if not pd.isna(adx) and adx > 25 and _w.get('adx_strong', 0) > 0:
        cond_map['adx_strong'] = True
        score += _w['adx_strong']
        di_p = round(last['DI_Plus'], 1); di_m = round(last['DI_Minus'], 1)
        signals.append(f"ADX={round(adx,1)} > 25 ({'bull' if di_p > di_m else 'bear'} trend)")

    if not pd.isna(st_dir) and st_dir == 1 and _w.get('supertrend', 0) > 0:
        cond_map['supertrend'] = True
        score += _w['supertrend']
        signals.append(f"Supertrend bullish (Rs{round(last['Supertrend'],1)})")

    donchian_break = False
    for lb in [1, 2]:
        if len(df) >= lb:
            c_row = df.iloc[-lb]
            if (c_row['Close'] > c_row['DC_Up'] and
                    not pd.isna(c_row['Vol_Ratio']) and c_row['Vol_Ratio'] >= 1.3):
                signals.append(f"Donchian break ({lb}d ago, {round(c_row['Vol_Ratio'],1)}x)")
                donchian_break = True; break
    if donchian_break and _w.get('donchian_brk', 0) > 0:
        cond_map['donchian_brk'] = True
        score += _w['donchian_brk']

    if (not pd.isna(stoch_k) and not pd.isna(stoch_k_p) and
            stoch_k < 35 and stoch_k > stoch_k_p and _w.get('stoch_oversold', 0) > 0):
        cond_map['stoch_oversold'] = True
        score += _w['stoch_oversold']
        signals.append(f"Stoch oversold+rising (%K={round(stoch_k,1)})")

    if squeeze and _w.get('bb_kc_squeeze', 0) > 0:
        cond_map['bb_kc_squeeze'] = True
        score += _w['bb_kc_squeeze']
        signals.append("BB+KC Squeeze — big move pending")

    if not any(pd.isna(v) for v in [ich_cloud_a, ich_cloud_b, ich_tenkan, ich_kijun]) and _w.get('ichimoku', 0) > 0:
        cloud_top = max(ich_cloud_a, ich_cloud_b)
        if close > cloud_top and ich_tenkan >= ich_kijun:
            cond_map['ichimoku'] = True
            score += _w['ichimoku']
            signals.append("Ichimoku bullish (above cloud, TK>=KJ)")

    if not pd.isna(psar_trend) and psar_trend == 1 and _w.get('psar_bull', 0) > 0:
        cond_map['psar_bull'] = True
        score += _w['psar_bull']
        signals.append(f"PSAR bullish (stop Rs{round(last['PSAR'],1)})")

    if (not pd.isna(williams_r) and not pd.isna(williams_rp) and
            williams_r < -60 and williams_r > williams_rp and _w.get('williams_r', 0) > 0):
        cond_map['williams_r'] = True
        score += _w['williams_r']
        signals.append(f"Williams %R recovering ({round(williams_r,0):.0f})")

    if not pd.isna(cmf) and cmf > 0.05 and _w.get('cmf_accum', 0) > 0:
        cond_map['cmf_accum'] = True
        score += _w['cmf_accum']
        signals.append(f"CMF={round(cmf,2)} — smart money accumulating")

    if (not pd.isna(aroon_up) and not pd.isna(aroon_dn) and
            aroon_up > 70 and aroon_up > aroon_dn and _w.get('aroon_trend', 0) > 0):
        cond_map['aroon_trend'] = True
        score += _w['aroon_trend']
        signals.append(f"Aroon Up={round(aroon_up,0):.0f} > Down (trend forming)")

    if (not pd.isna(hma_now) and not pd.isna(hma_prev3) and hma_now > hma_prev3 and _w.get('hma_rising', 0) > 0):
        cond_map['hma_rising'] = True
        score += _w['hma_rising']
        signals.append("HMA(21) rising — trend confirmed")

    if not pd.isna(force_idx) and force_idx > 0 and _w.get('force_idx', 0) > 0:
        cond_map['force_idx'] = True
        score += _w['force_idx']
        fi_str = f"{round(force_idx/1e6,1)}M" if abs(force_idx) >= 1e6 else f"{round(force_idx,0):.0f}"
        signals.append(f"Force Index positive ({fi_str})")

    # ── RS bonus (Filter 4) ────────────────────────────────
    rs = calc_rs_rating(df['Close'], nifty_close) if nifty_close is not None else {'rs_score': 0, 'bonus_pts': 0, 'label': 'N/A'}
    if rs['bonus_pts'] > 0:
        signals.append(rs['label'])

    # ── Build per-condition breakdown for the UI ───────────
    conditions_list = [
        {
            'key':            c['key'],
            'label':          c['label'],
            'category':       c['category'],
            'desc':           c['desc'],
            'default_weight': WEIGHTS[c['key']],          # original weight (for reference)
            'actual_weight':  _w.get(c['key'], 0),        # user-adjusted weight used this run
            'triggered':      cond_map.get(c['key'], False),
            'points':         _w.get(c['key'], 0) if cond_map.get(c['key'], False) else 0,
        }
        for c in CONDITIONS_META
    ]

    # ── Additional metadata ────────────────────────────────
    high_52w      = df['High'].iloc[-252:].max() if len(df) >= 252 else df['High'].max()
    pct_from_high = (close - high_52w) / high_52w * 100
    one_mo_ago    = df['Close'].iloc[-22] if len(df) >= 22 else df['Close'].iloc[0]
    pct_1m        = (close - one_mo_ago) / one_mo_ago * 100

    if not any(pd.isna(v) for v in [ich_cloud_a, ich_cloud_b]):
        ct = max(ich_cloud_a, ich_cloud_b); cb = min(ich_cloud_a, ich_cloud_b)
        ich_status = 'Above' if close > ct else ('Below' if close < cb else 'In')
    else:
        ich_status = '—'

    return {
        'Ticker'        : ticker.replace('.NS', ''),
        'W_Score'       : score,                        # weighted indicator score
        'RS_Bonus'      : rs['bonus_pts'],              # RS bonus pts (0-3)
        'RS_Score'      : rs['rs_score'],               # raw RS vs Nifty
        'Conditions'    : conditions_list,              # per-condition breakdown for UI
        'Close'         : close,
        'RSI'           : round(rsi, 1),
        'ADX'           : round(adx, 1) if not pd.isna(adx) else 0,
        'ST_Dir'        : int(st_dir) if not pd.isna(st_dir) else 0,
        'Stoch_K'       : round(stoch_k, 1) if not pd.isna(stoch_k) else 0,
        'Vol_Ratio'     : round(vol_ratio, 2),
        '1M_Chg%'       : round(pct_1m, 1),
        'From52wHigh%'  : round(pct_from_high, 1),
        'Signals'       : ' | '.join(signals) if signals else 'No signals',
        'Ich_Cloud'     : ich_status,
        'PSAR_Dir'      : int(psar_trend) if not pd.isna(psar_trend) else 0,
        'CMF'           : round(cmf, 3) if not pd.isna(cmf) else 0,
        'Liq_Grade'     : liq_result['grade'] if liq_result else '?',
        'ADV_Crores'    : liq_result['adv_crores'] if liq_result else 0,
    }



# ════════════════════════════════════════════════════════════
# SCREENER LOOP — ALL 6 FILTERS IN ORDER
# ════════════════════════════════════════════════════════════

def run_screener(tickers, index_name="Nifty 50", top_n=15,
                 liq_preset='medium', use_fundamentals=True,
                 regime=None, nifty_close=None):
    """
    Main scan loop — all 6 filters applied in optimal order:

        Order of filters (fastest rejections first):
        1. LIQUIDITY  — check ADV / Amihud / consistency
                         Reject fast: no point scoring illiquid stocks
        2. FUNDAMENTALS — check PE, promoter, D/E, revenue
                         Reject structural traps before indicator work
        3. DOWNLOAD + INDICATORS — now only for stocks that passed
        4. WEEKLY MTF GATE — check weekly trend alignment
                         Block or cap daily score if weekly disagrees
        5. WEIGHTED SCORE — run all 20 conditions with weights
        6. RS BONUS — add relative strength vs Nifty bonus

    Regime thresholds from Filter 5 determine which stocks make
    the final watchlist.
    """
    qualify_score = regime['qualify_score'] if regime else 18
    regime_name   = regime['regime']        if regime else 'UNKNOWN'

    print(f"\n{'='*68}")
    print(f"  NIFTY SCREENER v3.0 — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Index: {index_name} | Stocks: {len(tickers)} | Regime: {regime_name}")
    print(f"  Liquidity: {liq_preset} | Qualify score: >= {qualify_score}/35+")
    print(f"{'='*68}\n")

    results      = []
    failed       = []
    illiquid     = []
    fund_failed  = []
    mtf_blocked  = []

    for idx, ticker in enumerate(tickers):
        pct = int((idx + 1) / len(tickers) * 30)
        bar = '█' * pct + '░' * (30 - pct)
        print(f"\r  [{bar}] {idx+1}/{len(tickers)} — {ticker:<20}", end='', flush=True)

        # ── Quick download for pre-filters (3mo, faster) ──
        try:
            df_quick = yf.download(ticker, period="3mo", auto_adjust=True, progress=False)
            if isinstance(df_quick.columns, pd.MultiIndex):
                df_quick.columns = df_quick.columns.get_level_values(0)
            df_quick.dropna(inplace=True)
        except Exception:
            failed.append(ticker)
            continue

        if len(df_quick) < 20:
            failed.append(ticker)
            continue

        # ══ FILTER 1: LIQUIDITY ══════════════════════════
        liq = check_liquidity(df_quick, preset=liq_preset)
        if not liq['passes']:
            illiquid.append({
                'Ticker' : ticker.replace('.NS', ''),
                'ADV_Cr' : liq['adv_crores'],
                'Grade'  : liq['grade'],
                'Reason' : liq['reasons'][0] if liq['reasons'] else 'Failed',
            })
            continue   # Skip all further work on this stock

        # ══ FILTER 2: FUNDAMENTALS ═══════════════════════
        if use_fundamentals:
            fund = check_fundamentals(ticker)
            if not fund['passes']:
                fund_failed.append({
                    'Ticker' : ticker.replace('.NS', ''),
                    'Reason' : fund['reasons'][0] if fund['reasons'] else 'Failed',
                    'Data'   : fund['data'],
                })
                continue   # Skip structurally broken stocks

        # ══ DOWNLOAD FULL DATA + ALL INDICATORS ══════════
        df_daily, df_weekly = download_and_calculate(ticker, period="1y")
        if df_daily is None:
            failed.append(ticker)
            continue

        # ══ FILTER 6: WEEKLY MTF GATE ════════════════════
        mtf = check_weekly_gate(df_weekly)
        if mtf['gate_level'] == 'BLOCKED':
            mtf_blocked.append({
                'Ticker'  : ticker.replace('.NS', ''),
                'Details' : mtf['details'],
            })
            continue   # Weekly trend fully bearish — skip

        # ══ FILTER 3+4: WEIGHTED SCORE + RS BONUS ════════
        result = score_stock(df_daily, ticker,
                             nifty_close=nifty_close,
                             liq_result=liq)
        if result is None:
            failed.append(ticker)
            continue

        # Apply weekly gate cap if needed (WEAK gate)
        w_score = result['W_Score']
        if mtf['cap_score'] is not None:
            w_score = min(w_score, mtf['cap_score'])

        # Add MTF bonus (STRONG gate) and RS bonus
        total_score = w_score + mtf['bonus_pts'] + result['RS_Bonus']

        result['W_Score']      = w_score
        result['MTF_Bonus']    = mtf['bonus_pts']
        result['Total_Score']  = total_score
        result['Weekly_Gate']  = mtf['gate_level']
        result['Weekly_RSI']   = mtf['weekly_rsi']
        result['Weekly_Trend'] = mtf['weekly_trend']

        # ══ FILTER 5: REGIME THRESHOLD ════════════════════
        # Only add to watchlist if total score meets regime threshold
        result['Qualifies'] = total_score >= qualify_score
        results.append(result)

        time.sleep(0.12)

    print(f"\n")

    # Summary of filter rejections
    print(f"  ── Scan Summary ──")
    print(f"  Scanned total      : {len(tickers)}")
    print(f"  Illiquid (skip)    : {len(illiquid)}")
    print(f"  Fund. failed (skip): {len(fund_failed)}")
    print(f"  MTF blocked (skip) : {len(mtf_blocked)}")
    print(f"  Download failed    : {len(failed)}")
    print(f"  Scored             : {len(results)}")
    print(f"  Qualify (>={qualify_score}) : {sum(1 for r in results if r['Qualifies'])}")

    if not results:
        print("  No results.")
        return pd.DataFrame(), illiquid, fund_failed

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(
        by=['Qualifies', 'Total_Score', 'RS_Score'],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    return results_df, illiquid, fund_failed


# ════════════════════════════════════════════════════════════
# OUTPUT FUNCTIONS
# ════════════════════════════════════════════════════════════

def print_watchlist(results_df, top_n=15, qualify_score=18):
    """Prints formatted watchlist with weighted + bonus scores."""

    qualified = results_df[results_df['Qualifies']].head(top_n)
    others    = results_df[~results_df['Qualifies']].head(5)

    print(f"\n{'='*105}")
    print(f"  TOP STOCKS — WATCHLIST  (Weighted max ~35 + RS bonus + MTF bonus)")
    print(f"  Qualify threshold: Total score >= {qualify_score}")
    print(f"{'='*105}")
    print(f"  {'#':<3} {'Ticker':<12} {'W.Score':>8} {'RS':>4} {'MTF':>4} {'Total':>6} "
          f"{'Gate':<8} {'Close':>8} {'RSI':>5} {'ADX':>5} {'Liq':>4}  Signals")
    print(f"  {'-'*103}")

    def print_row(rank, row, prefix=''):
        st = "UP" if row['ST_Dir'] == 1 else "DN"
        rs_str  = f"+{row['RS_Bonus']}" if row['RS_Bonus'] > 0 else "0"
        mtf_str = f"+{row['MTF_Bonus']}" if row['MTF_Bonus'] > 0 else "0"
        print(
            f"  {prefix}{rank:<3} {row['Ticker']:<12} "
            f"{row['W_Score']:>6}pt  {rs_str:>3}  {mtf_str:>3}  "
            f"{row['Total_Score']:>5}pt  "
            f"{row.get('Weekly_Gate','?'):<8}  "
            f"Rs{row['Close']:>7.1f}  {row['RSI']:>4.1f}  {row['ADX']:>4.1f}  "
            f"[{row.get('Liq_Grade','?')}]"
        )
        print(f"       {str(row['Signals'])[:92]}")
        print()

    if len(qualified) == 0:
        print(f"  No stocks meet the qualify threshold of {qualify_score}.")
        print(f"  Consider using --no-fundamentals or changing --preset")
    else:
        for rank, (_, row) in enumerate(qualified.iterrows(), 1):
            print_row(rank, row)

    if len(others) > 0:
        print(f"  ── Just below threshold (showing top {len(others)}) ──")
        for rank, (_, row) in enumerate(others.iterrows(), 1):
            print_row(rank, row, prefix='~')

    print(f"{'='*105}")


def print_market_summary(results_df, regime, illiquid, fund_failed):
    """Comprehensive market summary including all filter stats."""

    total      = len(results_df)
    qualified  = results_df['Qualifies'].sum() if total > 0 else 0
    avg_rsi    = results_df['RSI'].mean() if total > 0 else 50
    avg_adx    = results_df['ADX'].mean() if total > 0 else 0
    pct_st_up  = (results_df['ST_Dir'] == 1).mean() * 100 if total > 0 else 0
    pct_adv    = (results_df['1M_Chg%'] > 0).mean() * 100 if total > 0 else 0
    pct_above  = (results_df['From52wHigh%'] > -10).mean() * 100 if total > 0 else 0

    # Score distribution
    strong   = (results_df['Total_Score'] >= 25).sum() if total > 0 else 0
    moderate = ((results_df['Total_Score'] >= 18) & (results_df['Total_Score'] < 25)).sum() if total > 0 else 0
    weak     = (results_df['Total_Score'] < 18).sum() if total > 0 else 0

    print(f"\n  ── Market Summary (v3) ──")
    print(f"  Regime              : {regime['regime']}  |  {regime['details']}")
    print(f"  Qualify threshold   : >= {regime['qualify_score']} total score")
    print(f"  Stocks scored       : {total}")
    print(f"  Qualify for watch   : {qualified}")
    print(f"  Strong (25+)        : {strong}  ({round(strong/max(total,1)*100,1)}%)")
    print(f"  Moderate (18-24)    : {moderate}  ({round(moderate/max(total,1)*100,1)}%)")
    print(f"  Weak (<18)          : {weak}  ({round(weak/max(total,1)*100,1)}%)")
    print(f"  Avg RSI             : {round(avg_rsi,1)}")
    print(f"  Avg ADX             : {round(avg_adx,1)}")
    print(f"  Supertrend UP       : {round(pct_st_up,1)}%")
    print(f"  Up in last month    : {round(pct_adv,1)}%")
    print(f"  Within 10% of high  : {round(pct_above,1)}%")
    print(f"\n  ── Filter Impact ──")
    print(f"  Illiquid removed    : {len(illiquid)}")
    print(f"  Fundamental removed : {len(fund_failed)}")
    if len(illiquid) > 0:
        print(f"  Sample illiquid     : " + ", ".join([s['Ticker'] for s in illiquid[:5]]))
    if len(fund_failed) > 0:
        print(f"  Sample fund. fail   : " + ", ".join([s['Ticker'] for s in fund_failed[:5]]))

    print(f"\n  Regime advice: {regime['regime_advice']}")


def save_results(results_df, index_name):
    """Saves full results to CSV with all new columns."""
    cols = ['Ticker', 'W_Score', 'RS_Bonus', 'MTF_Bonus', 'Total_Score',
            'Qualifies', 'Weekly_Gate', 'Liq_Grade', 'ADV_Crores',
            'Close', 'RSI', 'ADX', 'ST_Dir', 'Vol_Ratio',
            '1M_Chg%', 'From52wHigh%', 'CMF', 'Ich_Cloud', 'Signals']
    available = [c for c in cols if c in results_df.columns]
    filename  = f"screener_v3_{index_name}_{datetime.now().strftime('%Y%m%d')}.csv"
    results_df[available].to_csv(filename, index=False)
    print(f"\n  Results saved: {filename}")


def plot_results(results_df, top_n=15, regime=None):
    """Enhanced 3-panel chart: score distribution, RS analysis, top picks."""

    if results_df.empty:
        return

    fig = plt.figure(figsize=(16, 10))
    gs  = gridspec.GridSpec(2, 2, hspace=0.4, wspace=0.35)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, :])

    qualify_score = regime['qualify_score'] if regime else 18

    # Panel 1: Total score distribution
    scores      = results_df['Total_Score']
    score_range = range(int(scores.min()), int(scores.max()) + 2)
    counts      = [len(results_df[results_df['Total_Score'] == s]) for s in score_range]
    bar_colors  = ['#E24B4A' if s < 18 else '#EF9F27' if s < 25 else '#1D9E75' for s in score_range]

    ax1.bar(list(score_range), counts, color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.5)
    ax1.axvline(x=qualify_score - 0.5, color='#1D9E75', linewidth=2,
                linestyle='--', label=f'Qualify >= {qualify_score}')
    ax1.set_title('Total Score Distribution (Weighted + RS + MTF)', fontsize=10)
    ax1.set_xlabel('Total Score', fontsize=9)
    ax1.set_ylabel('Stocks', fontsize=9)
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.2, axis='y')

    # Panel 2: RS Score vs Indicator Score scatter
    if 'RS_Score' in results_df.columns and 'W_Score' in results_df.columns:
        colors_sc = ['#1D9E75' if q else '#E24B4A' for q in results_df['Qualifies']]
        ax2.scatter(results_df['RS_Score'], results_df['W_Score'],
                    c=colors_sc, alpha=0.7, s=50, edgecolors='none')
        ax2.axvline(x=0, color='#888780', linewidth=0.8, linestyle='--')
        ax2.set_title('Relative Strength vs Indicator Score', fontsize=10)
        ax2.set_xlabel('RS vs Nifty (3-month %)', fontsize=9)
        ax2.set_ylabel('Weighted Indicator Score', fontsize=9)
        ax2.grid(True, alpha=0.2)
        # Label top stocks
        top5 = results_df.head(5)
        for _, row in top5.iterrows():
            ax2.annotate(row['Ticker'], (row['RS_Score'], row['W_Score']),
                        fontsize=7, alpha=0.8, xytext=(3, 3), textcoords='offset points')

    # Panel 3: Top N stocks horizontal bar (colour by gate level)
    top = results_df.head(top_n).copy()
    gate_colors = {
        'STRONG': '#1D9E75', 'MODERATE': '#378ADD',
        'WEAK': '#EF9F27', 'BLOCKED': '#E24B4A', '?': '#888780'
    }
    bar_cols = [gate_colors.get(g, '#888780') for g in top.get('Weekly_Gate', ['?']*len(top))]

    y_pos = range(len(top))
    ax3.barh(y_pos, top['Total_Score'], color=bar_cols, alpha=0.85,
             edgecolor='white', linewidth=0.5, height=0.6)

    for i, row in enumerate(top.itertuples()):
        lbl = f"W:{row.W_Score}+RS:{row.RS_Bonus}+MTF:{row.MTF_Bonus} | RS_vs_Nifty={row.RS_Score:.1f}%"
        ax3.text(row.Total_Score + 0.2, i, lbl, va='center', fontsize=7.5)

    ax3.set_yticks(y_pos)
    ax3.set_yticklabels(top['Ticker'].values, fontsize=9)
    ax3.set_xlabel('Total Score (Indicator + RS + MTF)', fontsize=10)
    ax3.set_title(f'Top {top_n} Stocks — Score Breakdown', fontsize=10)
    ax3.set_xlim(0, results_df['Total_Score'].max() * 1.3 + 5)
    ax3.axvline(x=qualify_score, color='#1D9E75', linewidth=1.5, linestyle='--', alpha=0.7)
    ax3.grid(True, alpha=0.2, axis='x')
    ax3.invert_yaxis()

    # Gate colour legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#1D9E75', alpha=0.85, label='Weekly STRONG gate'),
        Patch(facecolor='#378ADD', alpha=0.85, label='Weekly MODERATE gate'),
        Patch(facecolor='#EF9F27', alpha=0.85, label='Weekly WEAK gate'),
    ]
    ax3.legend(handles=legend_elements, fontsize=8, loc='lower right')

    regime_name = regime['regime'] if regime else 'UNKNOWN'
    plt.suptitle(f"Screener v3.0 — {datetime.now().strftime('%d %B %Y')} | Regime: {regime_name}",
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    fname = f"screener_v3_chart_{datetime.now().strftime('%Y%m%d')}.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"  Chart saved: {fname}")
    plt.show()


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
    """
    Usage:
        python screener_v3.py                            # Nifty 50, medium liquidity
        python screener_v3.py --index nifty100           # Nifty 100
        python screener_v3.py --index nifty500           # Full sample
        python screener_v3.py --ticker RELIANCE          # Single stock
        python screener_v3.py --preset large             # Large trader liquidity
        python screener_v3.py --preset small             # Small retail trader
        python screener_v3.py --no-fundamentals          # Skip fundamental check
        python screener_v3.py --index nifty100 --preset large --no-fundamentals
    """
    args              = sys.argv[1:]
    index_name        = 'nifty50'
    single_ticker     = None
    liq_preset        = 'medium'
    use_fundamentals  = True

    if '--index' in args:
        i = args.index('--index')
        if i + 1 < len(args): index_name = args[i+1].lower()

    if '--ticker' in args:
        i = args.index('--ticker')
        if i + 1 < len(args):
            t = args[i+1]
            single_ticker = t if t.endswith('.NS') else t.upper() + '.NS'

    if '--preset' in args:
        i = args.index('--preset')
        if i + 1 < len(args): liq_preset = args[i+1].lower()

    if '--no-fundamentals' in args:
        use_fundamentals = False

    # Select tickers
    if single_ticker:
        tickers = [single_ticker]
        label   = single_ticker.replace('.NS', '')
    else:
        tickers = INDEX_MAP.get(index_name, NIFTY_50)
        label   = index_name.upper()

    # ── Step 1: Market Regime Detection (Filter 5) ────────
    regime = detect_market_regime()

    # ── Step 2: Download Nifty returns once (for RS in Filter 4) ─
    print("\n  Downloading Nifty 50 for Relative Strength calculation...")
    nifty_close = download_nifty_returns()
    if nifty_close is not None:
        print(f"  Nifty data ready — {len(nifty_close)} trading days")
    else:
        print("  Nifty download failed — RS bonus will not be calculated")

    # ── Step 3: Run the full scan with all 6 filters ──────
    results_df, illiquid, fund_failed = run_screener(
        tickers,
        index_name      = label,
        top_n           = 15,
        liq_preset      = liq_preset,
        use_fundamentals= use_fundamentals,
        regime          = regime,
        nifty_close     = nifty_close,
    )

    if results_df.empty:
        print("\n  No results after all filters. Done.\n")
        return

    # ── Step 4: Output ────────────────────────────────────
    print_watchlist(results_df, top_n=15, qualify_score=regime['qualify_score'])
    print_market_summary(results_df, regime, illiquid, fund_failed)
    save_results(results_df, index_name)
    plot_results(results_df, top_n=15, regime=regime)

    print(f"\n  Screener v3 complete.\n")


if __name__ == "__main__":
    main()
    