# ============================================================
# UPGRADED BACKTESTER — v2.0
# Now tests 6 strategies (was 4 in v1)
# ============================================================
#
# WHAT'S NEW vs backtester.py (v1):
#   All indicator functions imported from complete_indicators.py
#   instead of being duplicated here.
#
#   2 new strategies added:
#     Strategy 5 — Supertrend         (most popular in India)
#     Strategy 6 — Donchian Breakout  (momentum breakout)
#
#   All 6 strategies now compared in one run.
#
# REQUIRES:
#   complete_indicators.py in the same folder
#
# HOW TO RUN:
#   python backtester_v2.py                   → RELIANCE.NS, 3y
#   python backtester_v2.py TATAMOTORS        → any ticker, 3y
#   python backtester_v2.py SBIN 5y           → with custom period
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import sys
import os
import warnings

warnings.filterwarnings('ignore')

# ── Allow importing advanced_indicators.py from project root ──
_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if _root not in sys.path:
    sys.path.insert(0, _root)

# ── Import all indicators from our complete library ──────────
from complete_indicators import (
    calc_sma, calc_ema, calc_rsi, calc_macd,
    calc_bollinger, calc_atr, calc_adx,
    calc_supertrend, calc_donchian, calc_keltner,
    calc_stochastic,
)

# ── Import extension indicators (same folder) ─────────────────
from indicators_extension import (
    calc_ichimoku,
    calc_parabolic_sar,
    calc_aroon,
)

# ── Import advanced indicators (project root) ─────────────────
from indicators.advanced_indicators import (
    calc_hma,
)


# ════════════════════════════════════════════════════════════
# SECTION 1 — DATA DOWNLOAD + ALL INDICATORS
# ════════════════════════════════════════════════════════════

def get_data_with_indicators(ticker, period="3y"):
    """
    Downloads OHLCV data and calculates every indicator
    needed by all 6 strategies.

    Parameters:
        ticker (str): e.g. "RELIANCE.NS"
        period (str): "3y" or "5y" recommended for meaningful backtest

    Returns:
        df (DataFrame) with all indicator columns
    """
    print(f"\nDownloading {ticker} ({period}) ...")
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    df.dropna(inplace=True)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    print(f"Got {len(df)} trading days | {df.index[0].date()} to {df.index[-1].date()}")

    print("Calculating indicators...")

    # Trend
    df['SMA_20']  = calc_sma(df['Close'], 20)
    df['SMA_50']  = calc_sma(df['Close'], 50)
    df['SMA_200'] = calc_sma(df['Close'], 200)
    df['EMA_9']   = calc_ema(df['Close'], 9)
    df['EMA_20']  = calc_ema(df['Close'], 20)

    # Momentum
    df['RSI']  = calc_rsi(df['Close'], 14)
    df['MACD'], df['Signal'], df['Histogram'] = calc_macd(df['Close'])
    df['Stoch_K'], df['Stoch_D'] = calc_stochastic(df, 14, 3, 3)

    # Volatility & Bands
    df['ATR'] = calc_atr(df, 14)
    (df['BB_Mid'], df['BB_Up'], df['BB_Lo'],
     df['PctB'],  df['BW'])    = calc_bollinger(df['Close'])
    (df['KC_Mid'], df['KC_Up'], df['KC_Lo']) = calc_keltner(df)
    (df['DC_Up'],  df['DC_Mid'], df['DC_Lo']) = calc_donchian(df, 20)

    # Trend strength
    df['ADX'], df['DI_Plus'], df['DI_Minus'] = calc_adx(df, 14)

    # Supertrend
    df['Supertrend'], df['ST_Dir'] = calc_supertrend(df, period=7, multiplier=3.0)

    # MACD crossover flags
    df['MACD_Cross_Up'] = (
        (df['MACD'] > df['Signal']) &
        (df['MACD'].shift(1) <= df['Signal'].shift(1))
    )
    df['MACD_Cross_Down'] = (
        (df['MACD'] < df['Signal']) &
        (df['MACD'].shift(1) >= df['Signal'].shift(1))
    )

    # Golden/Death Cross flags
    df['Golden_Cross'] = (
        (df['SMA_50'] > df['SMA_200']) &
        (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1))
    )
    df['Death_Cross'] = (
        (df['SMA_50'] < df['SMA_200']) &
        (df['SMA_50'].shift(1) >= df['SMA_200'].shift(1))
    )

    # Volume
    df['VMA']       = calc_sma(df['Volume'].astype(float), 20)
    df['Vol_Ratio'] = df['Volume'] / df['VMA']

    # ── Extension + advanced indicators ─────────────────────

    # Ichimoku (9/26/52) — current cloud at bar i uses data from i-26
    df['Ich_Tenkan'], df['Ich_Kijun'], _, _, _ = calc_ichimoku(df)
    df['Ich_Cloud_A'] = ((df['Ich_Tenkan'] + df['Ich_Kijun']) / 2).shift(26)
    df['Ich_Cloud_B'] = (
        (df['High'].rolling(52).max() + df['Low'].rolling(52).min()) / 2
    ).shift(26)

    # Parabolic SAR
    df['PSAR'], df['PSAR_Trend'] = calc_parabolic_sar(df)

    # Aroon (trend emergence detector)
    df['Aroon_Up'], df['Aroon_Dn'], _ = calc_aroon(df, 25)

    # Hull Moving Average (low-lag trend filter)
    df['HMA_21'] = calc_hma(df['Close'], 21)

    return df


# ════════════════════════════════════════════════════════════
# SECTION 2 — THE 9 STRATEGIES
# (Original 6 unchanged + 3 new from extension indicators)
# ════════════════════════════════════════════════════════════

def strategy_triple_confirmation(df, i):
    """
    Strategy 1 — Triple Confirmation (unchanged from v1)

    BUY: Price > SMA200 + SMA50 > SMA200 + RSI 30–55 + MACD cross + Volume ok
    SELL: Price drops below SMA50
    """
    if i < 200: return False, False
    row = df.iloc[i]
    buy = (row['Close'] > row['SMA_200'] and
           row['SMA_50'] > row['SMA_200'] and
           30 <= row['RSI'] <= 55 and
           bool(row['MACD_Cross_Up']) and
           row['Vol_Ratio'] >= 1.0)
    sell = row['Close'] < row['SMA_50'] and df.iloc[i-1]['Close'] >= df.iloc[i-1]['SMA_50']
    return buy, sell


def strategy_mean_reversion(df, i):
    """
    Strategy 2 — Mean Reversion (unchanged from v1)

    BUY: RSI < 35 + near lower BB + high volume + above SMA200
    SELL: RSI > 60
    """
    if i < 200: return False, False
    row = df.iloc[i]
    buy = (row['RSI'] < 35 and
           row['PctB'] < 0.1 and
           row['Vol_Ratio'] >= 1.5 and
           row['Close'] > row['SMA_200'])
    sell = row['RSI'] > 60
    return buy, sell


def strategy_macd_momentum(df, i):
    """
    Strategy 3 — MACD Momentum (unchanged from v1)

    BUY: MACD bullish cross below zero + growing histogram + volume
    SELL: MACD bearish cross
    """
    if i < 60: return False, False
    row  = df.iloc[i]
    prev = df.iloc[i-1]
    buy = (bool(row['MACD_Cross_Up']) and
           row['MACD'] < 0 and
           row['Histogram'] > 0 and
           row['Histogram'] > prev['Histogram'] and
           row['Vol_Ratio'] >= 1.2 and
           row['RSI'] < 60)
    sell = bool(row['MACD_Cross_Down'])
    return buy, sell


def strategy_golden_cross(df, i):
    """
    Strategy 4 — Golden Cross (unchanged from v1)

    BUY: SMA50 crosses above SMA200 + RSI not overbought
    SELL: Death Cross
    """
    if i < 210: return False, False
    row = df.iloc[i]
    buy  = bool(row['Golden_Cross']) and row['RSI'] < 70 and row['Vol_Ratio'] >= 1.0
    sell = bool(row['Death_Cross'])
    return buy, sell


def strategy_supertrend(df, i):
    """
    Strategy 5 — Supertrend (NEW)

    The most popular intraday strategy in India.
    Clean, objective signals — no ambiguity.

    BUY conditions (ALL must be true):
        1. Supertrend direction flips from -1 to +1
           (trend just turned bullish)
        2. ADX > 20  — the new trend has real strength
        3. Volume ≥ 1.0x average — some participation

    SELL conditions:
        Supertrend direction flips from +1 to -1
        (trend just turned bearish)

    Why this strategy is so popular:
        Supertrend gives a single unambiguous line.
        Price above the line = hold/buy.
        Price below the line = exit/avoid.
        No interpretation needed — it's either bullish or bearish.
        Indian retail traders love this for its simplicity and clarity.

    Parameters:
        df (DataFrame): Must have ST_Dir, ADX, Vol_Ratio
        i (int): Current row index

    Returns:
        buy_signal (bool), sell_signal (bool)
    """
    # Need at least 20 rows for Supertrend to stabilise
    if i < 20:
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i-1]

    st_now  = row['ST_Dir']
    st_prev = prev['ST_Dir']
    adx     = row['ADX']
    vol     = row['Vol_Ratio']

    # Skip if any required value is NaN
    if any(pd.isna(v) for v in [st_now, st_prev, adx, vol]):
        return False, False

    # BUY: ST just flipped to bullish with trend strength confirmation
    buy = (st_prev == -1 and
           st_now  == 1 and
           adx > 20 and
           vol >= 1.0)

    # SELL: ST just flipped to bearish
    sell = (st_prev == 1 and st_now == -1)

    return buy, sell


def strategy_donchian_breakout(df, i):
    """
    Strategy 6 — Donchian Channel Breakout (NEW)

    Fundamentally different from all other strategies here.
    This is a MOMENTUM/BREAKOUT strategy, not a mean-reversion
    or trend-following strategy.

    The other strategies buy during pullbacks or at trend starts.
    This strategy buys when price is making NEW HIGHS — the
    complete opposite philosophy.

    Logic: A stock hitting a 20-day high is showing unusual strength.
    The breakout attracts momentum buyers. We join them.

    BUY conditions (ALL must be true):
        1. Close > 20-day Donchian Upper Band
           (price just hit a 20-day high)
        2. Volume ≥ 1.5x average
           (real buying, not random noise)
        3. ADX > 18
           (some trend is developing)
        4. Close > SMA 50
           (price is in a reasonable uptrend)

    SELL conditions:
        Price closes below 20-day Donchian Lower Band
        (20-day low = the trend has fully reversed)
        OR price falls below SMA 50 (trend broken)

    Note: This strategy will have a LOWER WIN RATE than the others
    because breakouts fail ~40% of the time (false breakouts).
    But the winning trades are larger — the risk/reward compensates.

    Parameters:
        df (DataFrame): Must have DC_Up, DC_Lo, Vol_Ratio, ADX, SMA_50
        i (int): Current row index

    Returns:
        buy_signal (bool), sell_signal (bool)
    """
    # Need at least 50 rows for Donchian and SMA to be reliable
    if i < 50:
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i-1]

    close     = row['Close']
    dc_up     = row['DC_Up']
    dc_lo     = row['DC_Lo']
    vol_ratio = row['Vol_Ratio']
    adx       = row['ADX']
    sma50     = row['SMA_50']

    if any(pd.isna(v) for v in [dc_up, dc_lo, vol_ratio, adx, sma50]):
        return False, False

    # BUY: fresh 20-day high on high volume with trend developing
    buy = (close > dc_up and
           vol_ratio >= 1.5 and
           adx > 18 and
           close > sma50)

    # SELL: 20-day low (trend fully reversed) OR SMA50 broken
    sell = (close < dc_lo or
            (close < sma50 and prev['Close'] >= prev['SMA_50']))

    return buy, sell


def strategy_ichimoku(df, i):
    """
    Strategy 7 — Ichimoku Cloud (NEW)

    The complete Japanese trend system — trend, momentum, support,
    and resistance in a single framework. Extremely popular in Asia.

    Uses CURRENT cloud (calculated from data 26 bars ago, already
    stored in Ich_Cloud_A/B) so there is no look-ahead bias.

    BUY conditions (ALL must be true):
        1. Price above the cloud (above max of Cloud_A, Cloud_B)
           → Primary trend is bullish
        2. Tenkan-sen crosses above Kijun-sen (TK cross)
           → Short-term momentum turned bullish
        3. ADX > 18  — the trend has some real strength
        4. Volume ≥ 1.0x average — participation confirmed

    SELL conditions (EITHER):
        Tenkan-sen crosses below Kijun-sen (TK cross bearish)
        OR price closes below the cloud bottom
        → Trend has reversed

    Why this works in Indian markets:
        Ichimoku gives unambiguous, mechanical signals.
        Institutions in Asia have used it for decades —
        levels become self-fulfilling as many traders watch the same lines.

    Parameters:
        df (DataFrame): Must have Ich_Tenkan, Ich_Kijun,
                        Ich_Cloud_A, Ich_Cloud_B, ADX, Vol_Ratio
        i (int): Current row index
    """
    if i < 60:
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i - 1]

    close       = row['Close']
    cloud_a     = row['Ich_Cloud_A']
    cloud_b     = row['Ich_Cloud_B']
    tenkan      = row['Ich_Tenkan']
    kijun       = row['Ich_Kijun']
    tenkan_prev = prev['Ich_Tenkan']
    kijun_prev  = prev['Ich_Kijun']
    adx         = row['ADX']
    vol_ratio   = row['Vol_Ratio']

    if any(pd.isna(v) for v in [cloud_a, cloud_b, tenkan, kijun,
                                  tenkan_prev, kijun_prev]):
        return False, False

    cloud_top = max(cloud_a, cloud_b)
    cloud_bot = min(cloud_a, cloud_b)

    # BUY: TK bullish cross above the cloud
    tk_cross_up = tenkan_prev <= kijun_prev and tenkan > kijun
    buy = (tk_cross_up and
           close > cloud_top and
           not pd.isna(adx) and adx > 18 and
           not pd.isna(vol_ratio) and vol_ratio >= 1.0)

    # SELL: TK bearish cross OR price breaks below cloud
    tk_cross_dn = tenkan_prev >= kijun_prev and tenkan < kijun
    sell = tk_cross_dn or close < cloud_bot

    return buy, sell


def strategy_parabolic_sar(df, i):
    """
    Strategy 8 — Parabolic SAR + ADX Filter (NEW)

    Parabolic SAR gives a simple, unambiguous signal: dot below
    price = uptrend. Dot above price = downtrend.

    The SAR alone generates too many false signals in choppy markets.
    The ADX filter ensures we only trade when a real trend exists.

    BUY conditions (ALL must be true):
        1. PSAR just flipped bullish (+1 from -1)
           → Trend just reversed to uptrend
        2. ADX > 20  — real trend strength confirmed
        3. Price > SMA 50  — medium-term trend is also up
        4. Volume ≥ 1.0x average

    SELL condition:
        PSAR flips bearish (-1 from +1) — trend reversed

    Pairing with Supertrend:
        Both SAR and Supertrend bullish → extremely high conviction.
        Use the strategies side-by-side to compare.

    Parameters:
        df (DataFrame): Must have PSAR_Trend, ADX, SMA_50, Vol_Ratio
        i (int): Current row index
    """
    if i < 30:
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i - 1]

    psar_now  = row['PSAR_Trend']
    psar_prev = prev['PSAR_Trend']
    adx       = row['ADX']
    close     = row['Close']
    sma50     = row['SMA_50']
    vol_ratio = row['Vol_Ratio']

    if any(pd.isna(v) for v in [psar_now, psar_prev]):
        return False, False

    # BUY: SAR just flipped bullish with trend + position confirmation
    buy = (psar_prev == -1 and
           psar_now == 1 and
           not pd.isna(adx) and adx > 20 and
           not pd.isna(sma50) and close > sma50 and
           not pd.isna(vol_ratio) and vol_ratio >= 1.0)

    # SELL: SAR just flipped bearish
    sell = psar_prev == 1 and psar_now == -1

    return buy, sell


def strategy_hma_momentum(df, i):
    """
    Strategy 9 — Hull MA Momentum (NEW)

    The Hull Moving Average (HMA) has almost zero lag, making it
    the best MA for catching trend changes early.

    This strategy uses price crossing the HMA as the primary signal.
    Unlike SMA/EMA crossovers, HMA crossovers tend to be timely
    rather than late.

    BUY conditions (ALL must be true):
        1. Price crosses ABOVE HMA(21)
           (was below on the previous bar, now above)
           → Low-lag confirmation that trend turned bullish
        2. Volume ≥ 1.2x average — real participation
        3. ADX > 18  — some directional strength exists

    SELL condition:
        Price crosses BELOW HMA(21) — trend reversed

    HMA vs EMA crossovers:
        EMA(21) crossovers lag by ~10 days.
        HMA(21) crossovers lag by ~2-3 days.
        The earlier signal means better entries and less drawdown.

    Parameters:
        df (DataFrame): Must have HMA_21, Vol_Ratio, ADX
        i (int): Current row index
    """
    if i < 30:
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i - 1]

    close      = row['Close']
    hma        = row['HMA_21']
    hma_prev   = prev['HMA_21']
    close_prev = prev['Close']
    vol_ratio  = row['Vol_Ratio']
    adx        = row['ADX']

    if any(pd.isna(v) for v in [hma, hma_prev, vol_ratio]):
        return False, False

    # BUY: price crossed above HMA (was below, now above)
    buy = (close_prev < hma_prev and
           close > hma and
           not pd.isna(vol_ratio) and vol_ratio >= 1.2 and
           not pd.isna(adx) and adx > 18)

    # SELL: price crossed below HMA (was above, now below)
    sell = close_prev > hma_prev and close < hma

    return buy, sell


# ════════════════════════════════════════════════════════════
# SECTION 3 — BACKTESTING ENGINE (unchanged from v1)
# ════════════════════════════════════════════════════════════

def run_backtest(df, strategy_func, strategy_name,
                 capital=100000,
                 stop_loss_pct=0.05,
                 take_profit_pct=0.10,
                 max_hold_days=20):
    """
    Core backtesting engine — identical to v1.
    Simulates every trade day by day.

    Entry at next day's OPEN (can't trade at today's close).
    Exit rules (whichever hits first):
        - Stop loss   : -5% from entry
        - Take profit : +10% from entry
        - Time stop   : 20 trading days
        - Strategy exit signal
    """
    trades       = []
    equity_curve = []
    in_trade     = False
    entry_price  = 0
    entry_date   = None
    entry_idx    = 0
    stop_loss_px = 0
    take_profit_px = 0
    current_equity = capital

    for i in range(len(df) - 1):
        row       = df.iloc[i]
        next_open = df['Open'].iloc[i + 1]

        if in_trade:
            equity_curve.append(current_equity * (row['Close'] / entry_price))
        else:
            equity_curve.append(current_equity)

        if in_trade:
            days_held = i - entry_idx
            _, sell_signal = strategy_func(df, i)
            exit_reason = None
            exit_price  = None

            if next_open <= stop_loss_px:
                exit_reason = 'Stop Loss'
                exit_price  = next_open
            elif next_open >= take_profit_px:
                exit_reason = 'Take Profit'
                exit_price  = next_open
            elif days_held >= max_hold_days:
                exit_reason = 'Time Stop'
                exit_price  = next_open
            elif sell_signal:
                exit_reason = 'Strategy Exit'
                exit_price  = next_open

            if exit_reason:
                pnl_pct = (exit_price - entry_price) / entry_price
                pnl_rs  = current_equity * pnl_pct
                current_equity += pnl_rs
                trades.append({
                    'Entry Date' : str(entry_date),
                    'Exit Date'  : str(df.index[i+1].date()),
                    'Entry Price': round(entry_price, 2),
                    'Exit Price' : round(exit_price, 2),
                    'PnL %'      : round(pnl_pct * 100, 2),
                    'PnL ₹'      : round(pnl_rs, 2),
                    'Days Held'  : days_held,
                    'Exit Reason': exit_reason,
                    'Win'        : pnl_pct > 0
                })
                in_trade = False
        else:
            buy_signal, _ = strategy_func(df, i)
            if buy_signal:
                in_trade       = True
                entry_price    = next_open
                entry_date     = df.index[i+1].date()
                entry_idx      = i + 1
                stop_loss_px   = entry_price * (1 - stop_loss_pct)
                take_profit_px = entry_price * (1 + take_profit_pct)

    equity_curve.append(current_equity)
    return trades, equity_curve


# ════════════════════════════════════════════════════════════
# SECTION 4 — PERFORMANCE METRICS (unchanged from v1)
# ════════════════════════════════════════════════════════════

def calculate_metrics(trades, equity_curve, capital, strategy_name):
    """Calculates all performance metrics from the trade log."""

    if not trades:
        return {
            'Strategy': strategy_name, 'Trades': 0,
            'Return %': 0, 'Win Rate %': 0, 'Avg Win %': 0,
            'Avg Loss %': 0, 'Risk/Reward': 0, 'Profit Factor': 0,
            'Max Drawdown %': 0, 'Sharpe Ratio': 0, 'Final Capital': capital
        }

    wins   = [t for t in trades if t['Win']]
    losses = [t for t in trades if not t['Win']]

    final_equity  = equity_curve[-1]
    total_return  = (final_equity - capital) / capital * 100
    win_rate      = len(wins) / len(trades) * 100
    avg_win       = np.mean([t['PnL %'] for t in wins])   if wins   else 0
    avg_loss      = np.mean([abs(t['PnL %']) for t in losses]) if losses else 0
    rr_ratio      = avg_win / avg_loss if avg_loss > 0 else float('inf')
    gross_profit  = sum(t['PnL ₹'] for t in wins)
    gross_loss    = abs(sum(t['PnL ₹'] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Max drawdown
    peak   = equity_curve[0]
    max_dd = 0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (annualised)
    eq_series     = pd.Series(equity_curve)
    daily_returns = eq_series.pct_change().dropna()
    std_ret       = daily_returns.std()
    sharpe        = (daily_returns.mean() / std_ret * np.sqrt(252)) if std_ret > 0 else 0

    return {
        'Strategy'       : strategy_name,
        'Trades'         : len(trades),
        'Return %'       : round(total_return, 2),
        'Win Rate %'     : round(win_rate, 2),
        'Avg Win %'      : round(avg_win, 2),
        'Avg Loss %'     : round(avg_loss, 2),
        'Risk/Reward'    : round(rr_ratio, 2),
        'Profit Factor'  : round(profit_factor, 2),
        'Max Drawdown %' : round(max_dd, 2),
        'Sharpe Ratio'   : round(sharpe, 2),
        'Final Capital'  : round(final_equity, 2)
    }


# ════════════════════════════════════════════════════════════
# SECTION 5 — CHART (extended for 9 strategies)
# ════════════════════════════════════════════════════════════

def plot_results(equity_curves, metrics_list, ticker, capital):
    """Results dashboard for all 6 strategies."""

    fig = plt.figure(figsize=(16, 12))
    gs  = gridspec.GridSpec(2, 2, hspace=0.4, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, :])   # Full-width equity curves
    ax2 = fig.add_subplot(gs[1, 0])   # Return bar chart
    ax3 = fig.add_subplot(gs[1, 1])   # Win rate + profit factor

    # Colours for 6 strategies
    colors = ['#1D9E75', '#378ADD', '#EF9F27', '#7F77DD', '#E24B4A', '#D4537E',
              '#2EC4B6', '#FF9F1C', '#CBFF8C']
    names  = list(equity_curves.keys())

    # Panel 1: Equity curves (normalised to 100)
    for idx, (name, curve) in enumerate(equity_curves.items()):
        norm = [v / capital * 100 for v in curve]
        ax1.plot(range(len(norm)), norm,
                 color=colors[idx], linewidth=2, label=name)

    ax1.axhline(y=100, color='#888780', linewidth=1,
                linestyle='--', alpha=0.6, label='Start (100)')
    ax1.set_title(f'{ticker} — All 6 Strategy Equity Curves', fontsize=13)
    ax1.set_ylabel('Portfolio Value (start = 100)', fontsize=10)
    ax1.set_xlabel('Trading Days', fontsize=10)
    ax1.legend(fontsize=9, loc='upper left')
    ax1.grid(True, alpha=0.2)

    # Panel 2: Return % comparison
    short_names = [m['Strategy'][:16] for m in metrics_list]
    returns     = [m['Return %'] for m in metrics_list]
    bar_colors  = [colors[i] for i in range(len(returns))]

    bars = ax2.bar(short_names, returns, color=bar_colors, alpha=0.85, width=0.6)
    for bar, val in zip(bars, returns):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + (0.3 if val >= 0 else -1.5),
                 f'{val}%', ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax2.axhline(y=0, color='#444441', linewidth=0.8)
    ax2.set_title('Total Return by Strategy', fontsize=11)
    ax2.set_ylabel('Return %', fontsize=10)
    ax2.grid(True, alpha=0.2, axis='y')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=20, ha='right', fontsize=8)

    # Panel 3: Win rate vs profit factor
    x_pos      = np.arange(len(short_names))
    width      = 0.35
    win_rates  = [m['Win Rate %'] for m in metrics_list]
    pf_scaled  = [min(m['Profit Factor'] * 20, 100) for m in metrics_list]

    ax3.bar(x_pos - width/2, win_rates, width, color='#378ADD',
            alpha=0.8, label='Win Rate %')
    ax3.bar(x_pos + width/2, pf_scaled, width, color='#EF9F27',
            alpha=0.8, label='Profit Factor × 20')
    ax3.axhline(y=50, color='#888780', linewidth=1, linestyle='--', alpha=0.5)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(short_names, rotation=20, ha='right', fontsize=8)
    ax3.set_title('Win Rate vs Profit Factor', fontsize=11)
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.2, axis='y')

    plt.suptitle(f'{ticker} — Backtesting v2 (9 Strategies)',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()

    fname = f"{ticker.replace('.','_')}_backtest_v2.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"\nChart saved: {fname}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 6 — MAIN
# ════════════════════════════════════════════════════════════

def main():
    """
    Usage:
        python backtester_v2.py                  → RELIANCE.NS, 3y
        python backtester_v2.py TATAMOTORS        → any ticker
        python backtester_v2.py SBIN 5y           → with period
    """
    args   = sys.argv[1:]
    ticker_input = args[0] if args else "RELIANCE"
    period       = args[1] if len(args) > 1 else "3y"

    if not ticker_input.endswith('.NS'):
        ticker = ticker_input.upper() + '.NS'
    else:
        ticker = ticker_input.upper()

    capital         = 100000
    stop_loss_pct   = 0.05
    take_profit_pct = 0.10
    max_hold_days   = 20

    # Download + calculate all indicators once
    df = get_data_with_indicators(ticker, period)

    # All 9 strategies
    strategies = [
        (strategy_triple_confirmation, "Triple Confirmation"),
        (strategy_mean_reversion,      "Mean Reversion"),
        (strategy_macd_momentum,       "MACD Momentum"),
        (strategy_golden_cross,        "Golden Cross"),
        (strategy_supertrend,          "Supertrend"),
        (strategy_donchian_breakout,   "Donchian Breakout"),
        (strategy_ichimoku,            "Ichimoku"),           # NEW
        (strategy_parabolic_sar,       "Parabolic SAR"),      # NEW
        (strategy_hma_momentum,        "HMA Momentum"),       # NEW
    ]

    all_metrics       = []
    all_equity_curves = {}
    all_trades        = {}

    print("\nRunning backtests...")

    for func, name in strategies:
        print(f"  Testing: {name}...")
        trades, equity = run_backtest(
            df, func, name,
            capital=capital,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days
        )
        metrics = calculate_metrics(trades, equity, capital, name)
        all_metrics.append(metrics)
        all_equity_curves[name] = equity
        all_trades[name]        = trades

    # Print results table
    print(f"\n{'='*92}")
    print(f"  BACKTESTING v2 (9 strategies) — {ticker}  |  Capital: ₹{capital:,}  |  SL:{stop_loss_pct*100}%  TP:{take_profit_pct*100}%")
    print(f"{'='*92}")
    print(f"  {'Strategy':<22} {'Trades':>7} {'Return':>9} {'Win%':>7} {'AvgW':>7} "
          f"{'AvgL':>7} {'R:R':>6} {'PF':>6} {'MaxDD':>8} {'Sharpe':>8}")
    print(f"  {'-'*90}")

    best_ret    = max(all_metrics, key=lambda m: m['Return %'])
    best_sharpe = max(all_metrics, key=lambda m: m['Sharpe Ratio'])

    for m in all_metrics:
        marker = " <-- best return" if m['Strategy'] == best_ret['Strategy'] else ""
        print(
            f"  {m['Strategy']:<22} {m['Trades']:>7} "
            f"{m['Return %']:>8.1f}% {m['Win Rate %']:>6.1f}% "
            f"{m['Avg Win %']:>6.1f}% {m['Avg Loss %']:>6.1f}% "
            f"{m['Risk/Reward']:>6.2f} {m['Profit Factor']:>6.2f} "
            f"{m['Max Drawdown %']:>7.1f}% {m['Sharpe Ratio']:>8.2f}"
            f"{marker}"
        )

    print(f"\n  Best Sharpe : {best_sharpe['Strategy']} ({best_sharpe['Sharpe Ratio']})")

    # Trade log for the best strategy
    best_name   = best_ret['Strategy']
    best_trades = all_trades[best_name]

    print(f"\n{'='*92}")
    print(f"  TRADE LOG — {best_name} (last 15 trades)")
    print(f"{'='*92}")
    print(f"  {'Entry':<13} {'Exit':<13} {'Entry ₹':>9} {'Exit ₹':>9} "
          f"{'PnL%':>7} {'PnL ₹':>10} {'Days':>5}  Exit Reason")
    print(f"  {'-'*90}")

    for t in best_trades[-15:]:
        sign = "+" if t['PnL %'] >= 0 else ""
        print(
            f"  {t['Entry Date']:<13} {t['Exit Date']:<13} "
            f"₹{t['Entry Price']:>8.2f} ₹{t['Exit Price']:>8.2f} "
            f"{sign}{t['PnL %']:>6.2f}% ₹{t['PnL ₹']:>9.0f} "
            f"{t['Days Held']:>5}d  {t['Exit Reason']}"
        )

    best_m = all_metrics[[m['Strategy'] for m in all_metrics].index(best_name)]
    print(f"\n  Starting: ₹{capital:,}  →  Final: ₹{int(best_m['Final Capital']):,}  "
          f"(Net: ₹{int(best_m['Final Capital']-capital):,})")
    print(f"\n  Past performance does not guarantee future results.")
    print(f"{'='*92}\n")

    plot_results(all_equity_curves, all_metrics, ticker, capital)


if __name__ == "__main__":
    main()