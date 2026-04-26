# ============================================================
# COMPLETE BACKTESTING ENGINE
# 4 Trading Strategies on Indian Stocks (NSE)
# ============================================================
# Strategies implemented:
#   1. Triple Confirmation  — SMA200 trend + RSI pullback + MACD timing
#   2. Mean Reversion       — RSI oversold + Bollinger lower band + Volume
#   3. MACD Momentum        — MACD bullish cross below zero + Volume
#   4. Golden Cross         — SMA50 crosses SMA200 + RSI filter
#
# For each strategy, the backtester calculates:
#   - Total Return (%)
#   - Win Rate (%)
#   - Average Win / Average Loss
#   - Risk/Reward Ratio
#   - Maximum Drawdown (%)
#   - Sharpe Ratio
#   - Profit Factor
#   - Number of Trades
#
# Exit rules (same for all strategies):
#   - Stop Loss : -5% from entry price
#   - Take Profit: +10% from entry price
#   - Time Stop : 20 trading days maximum hold
#
# INSTALL:
#   pip install yfinance pandas matplotlib numpy
# ============================================================


import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from datetime import datetime


# ════════════════════════════════════════════════════════════
# SECTION 1 — INDICATOR CALCULATIONS
# (All from previous phases, collected here for the engine)
# ════════════════════════════════════════════════════════════

def calc_sma(series, period):
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def calc_ema(series, period):
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(prices, period=14):
    """RSI using Wilder's smoothing method."""
    delta  = prices.diff(1)
    gains  = delta.clip(lower=0)
    losses = delta.clip(upper=0).abs()

    ag = gains.rolling(window=period, min_periods=period).mean()
    al = losses.rolling(window=period, min_periods=period).mean()

    ag_list = ag.tolist()
    al_list = al.tolist()
    g_list  = gains.tolist()
    l_list  = losses.tolist()

    for i in range(period, len(ag_list)):
        if pd.isna(ag_list[i - 1]):
            continue
        ag_list[i] = (ag_list[i-1] * (period-1) + g_list[i]) / period
        al_list[i] = (al_list[i-1] * (period-1) + l_list[i]) / period

    ag = pd.Series(ag_list, index=prices.index)
    al = pd.Series(al_list, index=prices.index)

    rs  = ag / al.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100).round(2)


def calc_macd(prices, fast=12, slow=26, signal=9):
    """MACD Line, Signal Line, Histogram."""
    ema_fast    = calc_ema(prices, fast)
    ema_slow    = calc_ema(prices, slow)
    macd_line   = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(prices, period=20, num_std=2):
    """Bollinger Bands: middle, upper, lower, %B, bandwidth."""
    middle = prices.rolling(window=period, min_periods=period).mean()
    std    = prices.rolling(window=period, min_periods=period).std(ddof=0)
    upper  = middle + num_std * std
    lower  = middle - num_std * std
    pct_b  = (prices - lower) / (upper - lower).replace(0, float('nan'))
    bw     = (upper - lower) / middle * 100
    return middle, upper, lower, pct_b, bw


def calc_volume_ma(volume, period=20):
    """20-day moving average of volume."""
    return volume.rolling(window=period, min_periods=period).mean()


def prepare_indicators(df):
    """
    Calculates ALL indicators needed by all 4 strategies.
    Adds them as new columns to the dataframe.

    This function is called once before the backtesting loop.
    Every strategy reads from these pre-calculated columns.

    Parameters:
        df (DataFrame): Raw OHLCV data

    Returns:
        df (DataFrame): Same dataframe with all indicator columns added
    """

    # ── Trend indicators ──
    df['SMA_20']  = calc_sma(df['Close'], 20)
    df['SMA_50']  = calc_sma(df['Close'], 50)
    df['SMA_200'] = calc_sma(df['Close'], 200)

    # ── Momentum ──
    df['RSI'] = calc_rsi(df['Close'], 14)

    # ── MACD ──
    df['MACD'], df['Signal'], df['Histogram'] = calc_macd(df['Close'])

    # ── MACD crossover flags ──
    # True on days where MACD crosses above Signal
    df['MACD_Cross_Up'] = (
        (df['MACD'] > df['Signal']) &
        (df['MACD'].shift(1) <= df['Signal'].shift(1))
    )
    # True on days where MACD crosses below Signal
    df['MACD_Cross_Down'] = (
        (df['MACD'] < df['Signal']) &
        (df['MACD'].shift(1) >= df['Signal'].shift(1))
    )

    # ── Bollinger Bands ──
    df['BB_Mid'], df['BB_Up'], df['BB_Lo'], df['PctB'], df['BW'] = calc_bollinger(df['Close'])

    # ── Volume ──
    df['VMA']       = calc_volume_ma(df['Volume'], 20)
    df['Vol_Ratio'] = df['Volume'] / df['VMA']

    # ── Golden/Death Cross flags ──
    # True on the day SMA_50 crosses above SMA_200
    df['Golden_Cross'] = (
        (df['SMA_50'] > df['SMA_200']) &
        (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1))
    )
    df['Death_Cross'] = (
        (df['SMA_50'] < df['SMA_200']) &
        (df['SMA_50'].shift(1) >= df['SMA_200'].shift(1))
    )

    return df


# ════════════════════════════════════════════════════════════
# SECTION 2 — FOUR STRATEGY SIGNAL GENERATORS
# Each function returns True/False for buy and sell on each day
# ════════════════════════════════════════════════════════════

def strategy_triple_confirmation(df, i):
    """
    Strategy 1 — Triple Confirmation Trend Following

    Philosophy:
        Only trade IN the direction of the major trend (SMA 200).
        Wait for price to pull back slightly (RSI in 30–50 range).
        Enter precisely when MACD gives a bullish crossover.
        This way we avoid buying at the top of a move.

    BUY conditions (ALL must be true):
        1. Price is ABOVE SMA 200         → we are in a long-term uptrend
        2. SMA 50 is ABOVE SMA 200        → medium-term also bullish
        3. RSI is between 30 and 55       → recent pullback (not overbought)
        4. MACD bullish crossover today   → momentum just turned up
        5. Volume at least 1.0x average   → there is some participation

    SELL conditions (any is enough):
        Handled by global stop loss / take profit / time stop
        OR: Price falls BELOW SMA 50      → trend is weakening

    Parameters:
        df (DataFrame): Full data with all indicators
        i (int): Current row index

    Returns:
        buy_signal (bool), sell_signal (bool)
    """

    # We need SMA_200 and other indicators to be calculated
    # So we skip the first 200 rows
    if i < 200:
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i - 1]

    # ── BUY conditions ──
    trend_up    = row['Close'] > row['SMA_200']          # Major trend is up
    ma_aligned  = row['SMA_50'] > row['SMA_200']         # Medium-term also up
    rsi_pullbk  = 30 <= row['RSI'] <= 55                 # RSI in sweet spot
    macd_cross  = bool(row['MACD_Cross_Up'])             # MACD just crossed up
    vol_ok      = row['Vol_Ratio'] >= 1.0                # At least average volume

    buy = trend_up and ma_aligned and rsi_pullbk and macd_cross and vol_ok

    # ── SELL condition (trend break) ──
    # Exit if price closes below SMA 50 (medium-term trend broken)
    sell = row['Close'] < row['SMA_50'] and prev['Close'] >= prev['SMA_50']

    return buy, sell


def strategy_mean_reversion(df, i):
    """
    Strategy 2 — Mean Reversion (RSI + Bollinger Bands + Volume)

    Philosophy:
        In a ranging or mildly trending market, prices tend to
        revert to their mean. When a stock is BOTH RSI-oversold
        AND touching the lower Bollinger Band, it is under extreme
        downward pressure from a statistical standpoint.
        Volume confirmation ensures real capitulation, not just drift.

    BUY conditions (ALL must be true):
        1. RSI < 35                  → momentum is oversold
        2. %B < 0.1                  → price at or near lower Bollinger Band
        3. Volume > 1.5x average     → real panic selling (capitulation)
        4. Price above SMA 200       → still in overall uptrend (filter bad markets)

    SELL conditions:
        RSI rises above 60           → momentum has recovered (mean restored)
        OR global stop/profit/time stop

    Parameters:
        df (DataFrame): Full data with all indicators
        i (int): Current row index

    Returns:
        buy_signal (bool), sell_signal (bool)
    """

    if i < 200:
        return False, False

    row = df.iloc[i]

    # ── BUY conditions ──
    rsi_os   = row['RSI'] < 35           # Oversold
    bb_lo    = row['PctB'] < 0.1         # At lower Bollinger Band
    high_vol = row['Vol_Ratio'] >= 1.5   # High volume (panic / capitulation)
    uptrend  = row['Close'] > row['SMA_200']   # Don't buy in bear markets

    buy = rsi_os and bb_lo and high_vol and uptrend

    # ── SELL condition ──
    # Exit when RSI recovers to 60 (mean restored)
    sell = row['RSI'] > 60

    return buy, sell


def strategy_macd_momentum(df, i):
    """
    Strategy 3 — MACD Momentum with Volume Confirmation

    Philosophy:
        The strongest MACD buy signal occurs when MACD crosses
        the Signal line while BOTH lines are BELOW zero.
        This means: the stock was in a downtrend, but momentum
        is now turning up from oversold levels — a powerful setup.
        Volume must confirm the move.

    BUY conditions (ALL must be true):
        1. MACD bullish crossover today   → momentum turned up
        2. MACD line is below zero        → crossover happening from oversold
        3. Histogram is positive and > histogram yesterday  → growing momentum
        4. Volume > 1.2x average          → volume confirming the move
        5. RSI < 60                       → not already overbought

    SELL conditions:
        MACD bearish crossover            → momentum has turned back down
        OR global stop/profit/time stop

    Parameters:
        df (DataFrame): Full data with all indicators
        i (int): Current row index

    Returns:
        buy_signal (bool), sell_signal (bool)
    """

    if i < 60:   # Need 26 days for MACD + some history
        return False, False

    row  = df.iloc[i]
    prev = df.iloc[i - 1]

    # ── BUY conditions ──
    macd_cross   = bool(row['MACD_Cross_Up'])        # Fresh bullish crossover
    below_zero   = row['MACD'] < 0                   # Still in negative territory (power zone)
    hist_growing = row['Histogram'] > 0 and row['Histogram'] > prev['Histogram']  # Momentum accelerating
    vol_ok       = row['Vol_Ratio'] >= 1.2            # Volume confirming
    not_ob       = row['RSI'] < 60                    # Not overbought yet

    buy = macd_cross and below_zero and hist_growing and vol_ok and not_ob

    # ── SELL condition ──
    sell = bool(row['MACD_Cross_Down'])   # Exit on any bearish MACD crossover

    return buy, sell


def strategy_golden_cross(df, i):
    """
    Strategy 4 — Golden Cross with RSI Filter

    Philosophy:
        The Golden Cross (SMA50 crossing above SMA200) is one of
        the most well-known bullish signals. It signals that a stock
        has transitioned from a bear phase to a bull phase in the
        medium-to-long term. It's a slow strategy — few trades,
        but each held for weeks to months.
        RSI filter prevents buying into an immediately overbought cross.

    BUY conditions (ALL must be true):
        1. Golden Cross occurs today      → SMA50 just crossed SMA200
        2. RSI < 70                       → not immediately overbought
        3. Volume > 1.0x average          → cross has volume backing

    SELL conditions:
        Death Cross occurs                → trend has reversed
        OR global stop/profit/time stop

    Parameters:
        df (DataFrame): Full data with all indicators
        i (int): Current row index

    Returns:
        buy_signal (bool), sell_signal (bool)
    """

    if i < 210:   # Need 200 days for SMA200 + buffer
        return False, False

    row = df.iloc[i]

    # ── BUY conditions ──
    golden = bool(row['Golden_Cross'])    # Fresh Golden Cross
    rsi_ok = row['RSI'] < 70             # Not overbought
    vol_ok = row['Vol_Ratio'] >= 1.0     # Some volume

    buy = golden and rsi_ok and vol_ok

    # ── SELL condition ──
    sell = bool(row['Death_Cross'])       # Exit on Death Cross

    return buy, sell


# ════════════════════════════════════════════════════════════
# SECTION 3 — THE BACKTESTING ENGINE
# ════════════════════════════════════════════════════════════

def run_backtest(df, strategy_func, strategy_name,
                 capital=100000,
                 stop_loss_pct=0.05,
                 take_profit_pct=0.10,
                 max_hold_days=20):
    """
    Core backtesting engine — simulates every trade day by day.

    How it works:
    ─────────────────────────────────────────────────────────
    We loop through each day in the historical data.
    On each day we either:
        A) Check for a BUY signal (if we have no open trade)
        B) Check exit conditions (if we have an open trade)

    Entry:  We enter at tomorrow's OPEN price (not today's close)
            because in reality you can't buy at today's close —
            the market is closed. You see the signal, place the
            order overnight, and it fills tomorrow at open.

    Exit:   Same logic — exits happen at the next day's open.

    Stop Loss:  If tomorrow's open is below stop_loss_price,
                we exit at tomorrow's open (gap-down scenario).

    Take Profit: If tomorrow's open is above take_profit_price,
                 we exit at tomorrow's open (gap-up scenario).

    Time Stop:  If we've held for max_hold_days with no exit signal,
                we exit at tomorrow's open (prevents stuck trades).
    ─────────────────────────────────────────────────────────

    Parameters:
        df (DataFrame): Full data with all indicators calculated
        strategy_func (function): One of the 4 strategy functions above
        strategy_name (str): Label for the results
        capital (float): Starting capital in rupees
        stop_loss_pct (float): e.g. 0.05 = 5% stop loss below entry
        take_profit_pct (float): e.g. 0.10 = 10% take profit above entry
        max_hold_days (int): Maximum days to hold a position

    Returns:
        trades (list): Every trade with full details
        equity_curve (list): Portfolio value on each day
    """

    trades       = []        # Log of all completed trades
    equity_curve = []        # Portfolio value over time

    # Track current position state
    in_trade      = False    # Are we currently holding a position?
    entry_price   = 0        # Price we entered the trade at
    entry_date    = None     # Date we entered
    entry_idx     = 0        # Row index when we entered
    stop_loss_px  = 0        # Our stop loss price level
    take_profit_px= 0        # Our take profit price level
    current_equity= capital  # Start with full capital

    for i in range(len(df) - 1):   # -1 because we need tomorrow's open
        row        = df.iloc[i]
        next_open  = df['Open'].iloc[i + 1]   # Tomorrow's opening price
        date       = df.index[i].date()

        # Record today's equity value
        if in_trade:
            # Mark-to-market: value based on today's close
            position_value = current_equity * (row['Close'] / entry_price)
            equity_curve.append(position_value)
        else:
            equity_curve.append(current_equity)

        if in_trade:
            # ── Check exit conditions ──
            days_held = i - entry_idx

            # Get the strategy's own sell signal
            _, sell_signal = strategy_func(df, i)

            # Calculate how much we've gained/lost
            pnl_pct = (next_open - entry_price) / entry_price

            # Determine exit reason
            exit_reason = None

            if next_open <= stop_loss_px:
                # Stop loss hit — exit at next open (which may be below stop)
                exit_reason = 'Stop Loss'
                exit_price  = next_open

            elif next_open >= take_profit_px:
                # Take profit hit
                exit_reason = 'Take Profit'
                exit_price  = next_open

            elif days_held >= max_hold_days:
                # Time stop — too long in the trade with no resolution
                exit_reason = 'Time Stop'
                exit_price  = next_open

            elif sell_signal:
                # Strategy's own sell signal
                exit_reason = 'Strategy Exit'
                exit_price  = next_open

            if exit_reason:
                # Calculate actual P&L
                actual_pnl_pct  = (exit_price - entry_price) / entry_price
                actual_pnl_rs   = current_equity * actual_pnl_pct

                # Update equity
                current_equity = current_equity + actual_pnl_rs

                # Record the trade
                trades.append({
                    'Entry Date'  : str(entry_date),
                    'Exit Date'   : str(df.index[i + 1].date()),
                    'Entry Price' : round(entry_price, 2),
                    'Exit Price'  : round(exit_price, 2),
                    'PnL %'       : round(actual_pnl_pct * 100, 2),
                    'PnL ₹'       : round(actual_pnl_rs, 2),
                    'Days Held'   : days_held,
                    'Exit Reason' : exit_reason,
                    'Win'         : actual_pnl_pct > 0
                })

                # Reset position state
                in_trade = False

        else:
            # ── Check for BUY signal ──
            buy_signal, _ = strategy_func(df, i)

            if buy_signal:
                # Enter at tomorrow's open
                in_trade       = True
                entry_price    = next_open
                entry_date     = df.index[i + 1].date()
                entry_idx      = i + 1

                # Set stop loss and take profit levels
                stop_loss_px   = entry_price * (1 - stop_loss_pct)
                take_profit_px = entry_price * (1 + take_profit_pct)

    # Append final equity value
    equity_curve.append(current_equity)

    return trades, equity_curve


# ════════════════════════════════════════════════════════════
# SECTION 4 — PERFORMANCE METRICS
# ════════════════════════════════════════════════════════════

def calculate_metrics(trades, equity_curve, capital, strategy_name):
    """
    Calculates all performance metrics from the trade log.

    Metrics explained:
    ─────────────────────────────────────────────────────────
    Total Return:    How much did the portfolio grow overall?
                     = (Final Value - Initial Capital) / Initial Capital × 100

    Win Rate:        What % of trades were profitable?
                     = Winning trades / Total trades × 100

    Avg Win:         Average profit on winning trades (%)
    Avg Loss:        Average loss on losing trades (%)

    Risk/Reward:     How much do we win vs lose on average?
                     = Avg Win / Avg Loss
                     A ratio of 2.0 means we win twice what we lose.

    Profit Factor:   Gross profit / Gross loss
                     > 1.5 is generally good, > 2.0 is excellent.

    Max Drawdown:    Worst peak-to-trough loss in equity curve (%)
                     = How much did we lose from our highest point?
                     Lower is better. > 20% is concerning.

    Sharpe Ratio:    Return per unit of risk (annualised)
                     = (Mean daily return / Std of daily return) × √252
                     > 1.0 is good, > 2.0 is excellent.
    ─────────────────────────────────────────────────────────

    Parameters:
        trades (list): All trade dicts from run_backtest()
        equity_curve (list): Daily portfolio values
        capital (float): Starting capital
        strategy_name (str): For labelling results

    Returns:
        dict: All performance metrics
    """

    # If no trades happened, return empty metrics
    if not trades:
        return {
            'Strategy': strategy_name, 'Trades': 0,
            'Return %': 0, 'Win Rate %': 0, 'Avg Win %': 0,
            'Avg Loss %': 0, 'Risk/Reward': 0, 'Profit Factor': 0,
            'Max Drawdown %': 0, 'Sharpe Ratio': 0
        }

    # ── Basic counts ──
    n_trades  = len(trades)
    wins      = [t for t in trades if t['Win']]
    losses    = [t for t in trades if not t['Win']]
    n_wins    = len(wins)
    n_losses  = len(losses)

    # ── Return ──
    final_equity = equity_curve[-1]
    total_return = (final_equity - capital) / capital * 100

    # ── Win rate ──
    win_rate = n_wins / n_trades * 100

    # ── Average win and loss ──
    avg_win  = np.mean([t['PnL %'] for t in wins])  if wins   else 0
    avg_loss = np.mean([abs(t['PnL %']) for t in losses]) if losses else 0

    # ── Risk/Reward ratio ──
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

    # ── Profit Factor ──
    gross_profit = sum(t['PnL ₹'] for t in wins)
    gross_loss   = abs(sum(t['PnL ₹'] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # ── Maximum Drawdown ──
    # Walk through the equity curve and find the worst peak-to-trough decline
    peak        = equity_curve[0]
    max_dd      = 0
    for value in equity_curve:
        if value > peak:
            peak = value   # New all-time high
        drawdown = (peak - value) / peak * 100
        if drawdown > max_dd:
            max_dd = drawdown   # Worst drawdown so far

    # ── Sharpe Ratio ──
    # Convert equity curve to daily returns
    eq_series     = pd.Series(equity_curve)
    daily_returns = eq_series.pct_change().dropna()
    mean_return   = daily_returns.mean()
    std_return    = daily_returns.std()

    # Annualise: 252 trading days in a year
    # Risk-free rate assumed 0 for simplicity (or use 6% for India)
    sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0

    return {
        'Strategy'      : strategy_name,
        'Trades'        : n_trades,
        'Return %'      : round(total_return, 2),
        'Win Rate %'    : round(win_rate, 2),
        'Avg Win %'     : round(avg_win, 2),
        'Avg Loss %'    : round(avg_loss, 2),
        'Risk/Reward'   : round(rr_ratio, 2),
        'Profit Factor' : round(profit_factor, 2),
        'Max Drawdown %': round(max_dd, 2),
        'Sharpe Ratio'  : round(sharpe, 2),
        'Final Capital' : round(final_equity, 2)
    }


# ════════════════════════════════════════════════════════════
# SECTION 5 — CHARTING
# ════════════════════════════════════════════════════════════

def plot_results(equity_curves, metrics_list, trades_dict, ticker, capital):
    """
    Creates a comprehensive results dashboard:
        Panel 1: Equity curves of all 4 strategies vs buy-and-hold
        Panel 2: Drawdown curves
        Panel 3: Win rate and profit factor bar chart
        Panel 4: Trade distribution (wins vs losses histogram)

    Parameters:
        equity_curves (dict): {strategy_name: [daily values]}
        metrics_list (list): All metrics dicts from calculate_metrics()
        trades_dict (dict): {strategy_name: [trade list]}
        ticker (str): Stock symbol
        capital (float): Starting capital
    """

    fig = plt.figure(figsize=(16, 12))
    gs  = gridspec.GridSpec(2, 2, hspace=0.4, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, :])   # Top full width: equity curves
    ax2 = fig.add_subplot(gs[1, 0])   # Bottom left: bar comparison
    ax3 = fig.add_subplot(gs[1, 1])   # Bottom right: win rate comparison

    colors = ['#1D9E75', '#378ADD', '#EF9F27', '#7F77DD']
    strategy_names = list(equity_curves.keys())

    # ── Panel 1: Equity Curves ──
    x = range(len(list(equity_curves.values())[0]))

    for idx, (name, curve) in enumerate(equity_curves.items()):
        # Normalise to 100 for easy comparison
        normalised = [v / capital * 100 for v in curve]
        ax1.plot(x, normalised,
                 color=colors[idx], linewidth=2, label=name)

    # Buy and hold benchmark
    ax1.axhline(y=100, color='#888780', linewidth=1,
                linestyle='--', alpha=0.7, label='Starting point (100)')

    ax1.set_title(f'{ticker} — Strategy Equity Curves (normalised to 100)',
                  fontsize=13, pad=10)
    ax1.set_ylabel('Portfolio Value (start = 100)', fontsize=10)
    ax1.set_xlabel('Trading Days', fontsize=10)
    ax1.legend(fontsize=9, loc='upper left')
    ax1.grid(True, alpha=0.25)

    # ── Panel 2: Return % Comparison ──
    names   = [m['Strategy'][:18] for m in metrics_list]
    returns = [m['Return %'] for m in metrics_list]
    bar_colors = ['#1D9E75' if r >= 0 else '#E24B4A' for r in returns]

    bars = ax2.bar(names, returns, color=bar_colors, alpha=0.85, width=0.5)

    # Add value labels on bars
    for bar, val in zip(bars, returns):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + (0.5 if val >= 0 else -1.5),
                 f'{val}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax2.axhline(y=0, color='#444441', linewidth=0.8)
    ax2.set_title('Total Return by Strategy', fontsize=11)
    ax2.set_ylabel('Return %', fontsize=10)
    ax2.grid(True, alpha=0.2, axis='y')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=15, ha='right', fontsize=8)

    # ── Panel 3: Win Rate vs Profit Factor ──
    x_pos      = np.arange(len(names))
    width      = 0.35
    win_rates  = [m['Win Rate %'] for m in metrics_list]
    pf_scaled  = [min(m['Profit Factor'] * 20, 100) for m in metrics_list]  # Scale to 0-100

    bars1 = ax3.bar(x_pos - width/2, win_rates, width, color='#378ADD',
                    alpha=0.8, label='Win Rate %')
    bars2 = ax3.bar(x_pos + width/2, pf_scaled, width, color='#EF9F27',
                    alpha=0.8, label='Profit Factor × 20')

    ax3.axhline(y=50, color='#888780', linewidth=1, linestyle='--', alpha=0.5)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(names, rotation=15, ha='right', fontsize=8)
    ax3.set_title('Win Rate % vs Profit Factor', fontsize=11)
    ax3.set_ylabel('Value', fontsize=10)
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.2, axis='y')

    plt.suptitle(f'{ticker} — Backtesting Results Summary',
                 fontsize=14, fontweight='bold', y=1.01)

    filename = f"{ticker.replace('.', '_')}_backtest_results.png"
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\nChart saved as: {filename}")
    plt.show()


# ════════════════════════════════════════════════════════════
# SECTION 6 — MAIN PROGRAM
# ════════════════════════════════════════════════════════════

def main():
    """
    Full backtesting pipeline:
        1. Download 3 years of data (more data = more reliable backtest)
        2. Calculate all indicators
        3. Run all 4 strategies
        4. Calculate metrics for each
        5. Print comparison table
        6. Plot equity curves
        7. Print trade log for the best strategy
    """

    # ── Configuration ──
    ticker  = "RELIANCE.NS"   # Change to any NSE stock
    period  = "3y"            # 3 years = enough trades to be statistically meaningful
    capital = 100000          # Starting capital: ₹1,00,000

    # Risk parameters (same for all strategies)
    stop_loss_pct    = 0.05   # 5% stop loss
    take_profit_pct  = 0.10   # 10% take profit
    max_hold_days    = 20     # Max 20 trading days per trade (~1 month)

    # ── Download Data ──
    print(f"\nDownloading {ticker} — 3 years of daily data...")
    df = yf.download(ticker, period=period, auto_adjust=True)
    df.dropna(inplace=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    print(f"Got {len(df)} trading days | {df.index[0].date()} to {df.index[-1].date()}")

    # ── Calculate All Indicators ──
    print("\nCalculating indicators...")
    df = prepare_indicators(df)

    # ── Define All 4 Strategies ──
    strategies = [
        (strategy_triple_confirmation, "Triple Confirmation"),
        (strategy_mean_reversion,      "Mean Reversion"),
        (strategy_macd_momentum,       "MACD Momentum"),
        (strategy_golden_cross,        "Golden Cross"),
    ]

    # ── Run Backtests ──
    all_metrics      = []
    all_equity_curves = {}
    all_trades        = {}

    print("\nRunning backtests...")

    for strat_func, strat_name in strategies:
        print(f"  Testing: {strat_name}...")

        trades, equity_curve = run_backtest(
            df, strat_func, strat_name,
            capital        = capital,
            stop_loss_pct  = stop_loss_pct,
            take_profit_pct= take_profit_pct,
            max_hold_days  = max_hold_days
        )

        metrics = calculate_metrics(trades, equity_curve, capital, strat_name)

        all_metrics.append(metrics)
        all_equity_curves[strat_name] = equity_curve
        all_trades[strat_name]        = trades

    # ── Print Comparison Table ──
    print(f"\n{'='*90}")
    print(f"  BACKTEST RESULTS — {ticker}  |  Capital: ₹{capital:,}  |  SL: {stop_loss_pct*100}%  TP: {take_profit_pct*100}%")
    print(f"{'='*90}")
    print(f"  {'Strategy':<22} {'Trades':>7} {'Return':>9} {'Win%':>7} {'AvgW':>7} {'AvgL':>7} {'R:R':>6} {'PF':>6} {'MaxDD':>8} {'Sharpe':>8}")
    print(f"  {'-'*88}")

    best_return   = max(all_metrics, key=lambda m: m['Return %'])
    best_sharpe   = max(all_metrics, key=lambda m: m['Sharpe Ratio'])
    best_winrate  = max(all_metrics, key=lambda m: m['Win Rate %'])

    for m in all_metrics:
        # Mark best strategy with an arrow
        marker = " <-- Best return" if m['Strategy'] == best_return['Strategy'] else ""
        print(
            f"  {m['Strategy']:<22} "
            f"{m['Trades']:>7} "
            f"{m['Return %']:>8.1f}% "
            f"{m['Win Rate %']:>6.1f}% "
            f"{m['Avg Win %']:>6.1f}% "
            f"{m['Avg Loss %']:>6.1f}% "
            f"{m['Risk/Reward']:>6.2f} "
            f"{m['Profit Factor']:>6.2f} "
            f"{m['Max Drawdown %']:>7.1f}% "
            f"{m['Sharpe Ratio']:>8.2f}"
            f"{marker}"
        )

    print(f"\n  Best Sharpe Ratio : {best_sharpe['Strategy']} ({best_sharpe['Sharpe Ratio']})")
    print(f"  Best Win Rate     : {best_winrate['Strategy']} ({best_winrate['Win Rate %']}%)")

    # ── Print Trade Log for Best Strategy ──
    best_name   = best_return['Strategy']
    best_trades = all_trades[best_name]

    print(f"\n{'='*90}")
    print(f"  TRADE LOG — {best_name}  (last 15 trades)")
    print(f"{'='*90}")
    print(f"  {'Entry Date':<13} {'Exit Date':<13} {'Entry ₹':>9} {'Exit ₹':>9} {'PnL%':>7} {'PnL ₹':>10} {'Days':>5} {'Exit Reason'}")
    print(f"  {'-'*88}")

    for t in best_trades[-15:]:
        sign = "+" if t['PnL %'] >= 0 else ""
        print(
            f"  {t['Entry Date']:<13} {t['Exit Date']:<13} "
            f"₹{t['Entry Price']:>8.2f} ₹{t['Exit Price']:>8.2f} "
            f"{sign}{t['PnL %']:>6.2f}% "
            f"₹{t['PnL ₹']:>9.0f} "
            f"{t['Days Held']:>5}d "
            f"{t['Exit Reason']}"
        )

    final = all_metrics[[m['Strategy'] for m in all_metrics].index(best_name)]['Final Capital']
    print(f"\n  Starting capital : ₹{capital:,}")
    print(f"  Final capital    : ₹{int(final):,}")
    print(f"  Net profit       : ₹{int(final-capital):,}")

    print(f"\n  IMPORTANT: Past performance does not guarantee future results.")
    print(f"  Always paper trade a strategy for at least 1 month before using real money.")
    print(f"{'='*90}\n")

    # ── Plot Results ──
    plot_results(all_equity_curves, all_metrics, all_trades, ticker, capital)


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    main()