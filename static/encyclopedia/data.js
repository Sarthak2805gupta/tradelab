
// ============================================================
// data.js — Complete encyclopedia data
// All indicators, filters, strategies, and patterns
// ============================================================

const CATEGORIES = [
  { id:'trend',      label:'Trend Indicators',     color:'#3dd68c', desc:'Direction of price movement' },
  { id:'momentum',   label:'Momentum Indicators',  color:'#60a5fa', desc:'Speed and strength of moves' },
  { id:'volatility', label:'Volatility & Bands',   color:'#f59e0b', desc:'Range and risk measures' },
  { id:'volume',     label:'Volume Indicators',    color:'#a78bfa', desc:'Participation and conviction' },
  { id:'strength',   label:'Trend Strength',       color:'#f87171', desc:'How strong is the current trend?' },
  { id:'patterns',   label:'Candlestick Patterns', color:'#fbbf24', desc:'Price action reversal signals' },
  { id:'filters',    label:'Screener Filters',     color:'#e879f9', desc:'v3 screener improvements' },
  { id:'strategies', label:'Trading Strategies',   color:'#38bdf8', desc:'Complete entry/exit systems' },
  { id:'breadth',    label:'Market Breadth',       color:'#34d399', desc:'Overall market health' },
  { id:'glossary',   label:'Glossary',             color:'#94a3b8', desc:'Plain-English definitions of common stock-market terms' },
];

const ITEMS = [

// ══════════════════════════════════════════════════════════
// TREND INDICATORS
// ══════════════════════════════════════════════════════════
{
  id:'sma-ema', cat:'trend', tag:'built', name:'SMA & EMA',
  short:'Foundation of all trend analysis',
  creator:'SMA: Charles Dow era | EMA: Gerald Appel 1970s',
  python:'complete_indicators.py → calc_sma(), calc_ema()',
  purpose:`The Simple Moving Average (SMA) averages the last N closing prices equally — every day counts the same. The Exponential Moving Average (EMA) gives more weight to recent prices using a smoothing factor, making it react faster to new price moves.

<b>Why they matter:</b> Price above its SMA/EMA = uptrend. Price below = downtrend. The 200-day SMA is the most-watched level by institutional traders globally. Nifty 50 stocks below their SMA 200 are in a long-term downtrend — avoid buying them.

<b>The Golden Cross and Death Cross</b> are the most famous signals in all of technical analysis. When the 50-day SMA crosses above the 200-day SMA, it is a Golden Cross — historically bullish. When it crosses below, it is a Death Cross — bearish.`,
  formula:`SMA(N) = (C₁ + C₂ + ... + Cₙ) / N\n  Every bar has equal weight.\n\nEMA smoothing factor: k = 2 / (N + 1)\nEMA today = Close × k + EMA yesterday × (1 − k)\n  Recent bars have more weight, older bars decay.\n\nKey periods used in practice:\n  SMA/EMA 9   → 2-week trend (fast)\n  SMA/EMA 20  → 1-month trend\n  SMA/EMA 50  → 2.5-month trend\n  SMA/EMA 200 → 1-year trend (most important)`,
  signals:[
    {t:'buy',  s:'Price closes above SMA 200 after being below → long-term trend turned bullish'},
    {t:'buy',  s:'SMA 50 crosses above SMA 200 (Golden Cross) → major bull market signal'},
    {t:'buy',  s:'Price pulls back to SMA 20 in uptrend with volume declining → buy the dip'},
    {t:'sell', s:'SMA 50 crosses below SMA 200 (Death Cross) → major bear market signal'},
    {t:'sell', s:'Price closes below SMA 200 → exit long positions'},
    {t:'note', s:'EMA reacts faster than SMA — better for entries. SMA better for major S/R levels.'},
  ],
  tip:'The SMA 200 is not just a level — it is a psychological magnet. When Nifty approaches it from below, institutional buyers emerge. When it breaks above, massive short covering follows.',
  combos:['ADX','RSI','MACD','Volume'],
  chart:'sma_ema',
  example:`Example — RELIANCE.NS (Jan–Mar 2024):
  Jan 15: Price = ₹2,840 | SMA50 = ₹2,801 | SMA200 = ₹2,634
  Status: Price above both → confirmed uptrend
  Action: Hold long, use SMA50 as trailing stop reference
  
  Feb 3: SMA50 (₹2,855) crosses above SMA200 (₹2,720) → Golden Cross
  Result: Trend confirmed bullish across timeframes → Strong buy`,
},

{
  id:'supertrend', cat:'trend', tag:'built', name:'Supertrend',
  short:'ATR-based trailing stop — most popular in India',
  creator:'Olivier Seban',
  python:'complete_indicators.py → calc_supertrend(df, period=7, multiplier=3)',
  purpose:`Supertrend is the single most used intraday indicator on NSE. It places a dynamic line above or below price that:
<b>1)</b> Tells you trend direction — dot/line below price = uptrend, above price = downtrend
<b>2)</b> Acts as your trailing stop loss — the level where you exit if price reverses
<b>3)</b> Gives a clear buy/sell signal when the line flips sides

The magic is its simplicity: there is no ambiguity. Either the trend is bullish or bearish. When it flips, you act.`,
  formula:`ATR = Wilder's Average True Range over 'period' days\n(ATR measures the stock's daily volatility including gaps)\n\nBasic Upper = (High + Low)/2 + multiplier × ATR\nBasic Lower = (High + Low)/2 − multiplier × ATR\n\nFinal bands ratchet to prevent whipsaws:\n  In uptrend: Final Lower only rises, never drops\n  In downtrend: Final Upper only falls, never rises\n\nNSE standard settings:\n  Daily charts:    period=7, multiplier=3\n  15-min charts:   period=7, multiplier=3\n  5-min charts:    period=10, multiplier=3`,
  signals:[
    {t:'buy',  s:'Line flips from above to below price (direction −1→+1) → BUY signal'},
    {t:'sell', s:'Line flips from below to above price (direction +1→−1) → SELL / EXIT'},
    {t:'note', s:'The Supertrend level IS your stop loss while in the trade. When it rises, your stop rises.'},
    {t:'watch',s:'ADX > 20 at signal time → new trend has real strength. ADX < 20 → may be choppy whipsaw.'},
    {t:'buy',  s:'Supertrend flip + MACD bullish cross on same day → exceptional confluence signal'},
  ],
  tip:'Supertrend + Parabolic SAR together: when both agree on direction, the signal is extremely reliable. When they disagree, the trend is unclear — stay flat.',
  combos:['ATR','ADX','Parabolic SAR','MACD','Volume'],
  chart:'supertrend',
  example:`Example — HDFCBANK.NS:
  March 5: Close=₹1,598, ST line=₹1,612 (above price) → SELL mode
  March 12: Close=₹1,641, ST line=₹1,629 (below price) → FLIP TO BUY
  ADX on March 12 = 28.4 → strong trend confirmed
  
  Action: Buy at ₹1,641, Stop loss = ₹1,629 (Supertrend level)
  As stock rises, Supertrend rises with it → trailing stop
  Exit when Supertrend flips back above price`,
},

{
  id:'ema-ribbon', cat:'trend', tag:'built', name:'EMA Ribbon',
  short:'Six EMAs showing trend strength at a glance',
  creator:'Derived from Guppy Multiple Moving Average (GMMA)',
  python:'complete_indicators.py → calc_ema_ribbon(df, [9,21,34,55,89,144])',
  purpose:`Instead of plotting one or two EMAs, the ribbon plots six EMAs simultaneously using Fibonacci periods: 9, 21, 34, 55, 89, 144. The visual pattern tells the complete trend story instantly:

<b>Bull alignment (fan-up):</b> EMA9 > EMA21 > EMA34 > EMA55 > EMA89 > EMA144 — all six ordered from shortest to longest above price. This is a strong, healthy uptrend. The wider the fan, the stronger the trend.

<b>Bear alignment (fan-down):</b> The reverse order. All EMAs below price in descending order.

<b>Tangled:</b> EMAs crossing and bunching together — market is ranging/sideways. Do NOT use trend-following strategies in this phase. This is when most retail traders lose money — they see small bounces and think the trend is starting.`,
  formula:`Six EMAs calculated using standard EMA formula:\nEMA(price, N) for N in [9, 21, 34, 55, 89, 144]\n\nFibonacci numbers used because they create naturally\nspaced intervals that cover all major market cycles:\n  9  → 2 weeks (short cycle)\n  21 → 1 month (monthly cycle)\n  34 → 7 weeks (intermediate)\n  55 → quarter (seasonal)\n  89 → 4 months (medium-term)\n  144 → 7 months (long-term)\n\nBull signal: EMA9 > EMA21 > EMA34 > EMA55 > EMA89 > EMA144\nBear signal: reverse\nChoppy:      no clear order`,
  signals:[
    {t:'buy',  s:'All 6 EMAs achieve perfect bull alignment + price above EMA9 → strong uptrend, BUY'},
    {t:'sell', s:'All 6 EMAs achieve perfect bear alignment + price below EMA9 → strong downtrend, SELL/AVOID'},
    {t:'watch',s:'Ribbon flipping from bear to bull alignment → major trend reversal in progress, prepare entry'},
    {t:'note', s:'Tangled ribbon = ranging market. All trend-following systems will fail here. Wait.'},
    {t:'note', s:'Fan width = trend strength. Narrow fan in one direction = weak trend, likely to reverse soon.'},
  ],
  tip:'Use EMA Ribbon as your market filter. Before entering any trade based on RSI or MACD signals, check the ribbon. If it is tangled, skip the trade entirely — the context is wrong.',
  combos:['ADX','Volume','RSI'],
  chart:'ema_ribbon',
  example:`Example — TATAMOTORS.NS:
  Phase 1 (Nov): Ribbon tangled → No trades. RSI gave 3 buy signals.
    All would have lost money in the choppy ranging market.
  
  Phase 2 (Dec 10): Ribbon achieves full bull alignment
    EMA9(₹812) > EMA21(₹798) > EMA34(₹781) > EMA55(₹762) > EMA89(₹741) > EMA144(₹719)
    Action: BUY at ₹812
  
  Phase 3 (Jan): Ribbon fans out widely → strong trend confirmed
    Stock moves from ₹812 to ₹948 (+16.7%) while ribbon stays bullish`,
},

{
  id:'ichimoku', cat:'trend', tag:'useful', name:'Ichimoku Cloud',
  short:'5-line system: trend, momentum, S/R — all in one glance',
  creator:'Goichi Hosoda (published 1969)',
  python:'indicators_extension.py → calc_ichimoku(df)',
  purpose:`Ichimoku means "one glance equilibrium chart." It is a complete trading system in a single indicator. Five lines provide everything you need:

<b>Tenkan-sen (Conversion, 9-period):</b> Fast trend line — the midpoint of the 9-period high-low range. When price is above Tenkan, short-term momentum is bullish.

<b>Kijun-sen (Base, 26-period):</b> The most important line. Acts as dynamic support in uptrends, resistance in downtrends. Price bouncing off Kijun in an uptrend = add to position.

<b>Kumo (Cloud):</b> The shaded area between Senkou Span A and B. Price above a green (thick) cloud = strong uptrend. Price inside the cloud = indecision. Price below a red cloud = strong downtrend. The cloud also projects 26 periods into the FUTURE — giving you tomorrow's support/resistance today.

<b>Chikou Span:</b> Today's close plotted 26 periods in the past. Confirms the trend by comparing current price to where it was a month ago.`,
  formula:`Tenkan-sen  = (9-period Highest High + 9-period Lowest Low) / 2\nKijun-sen   = (26-period Highest High + 26-period Lowest Low) / 2\n\nSenkou Span A = (Tenkan + Kijun) / 2  →  plotted 26 periods FORWARD\nSenkou Span B = (52-period High + 52-period Low) / 2  →  plotted 26 periods FORWARD\n\nChikou Span = Today's Close  →  plotted 26 periods BACKWARD\n\nCloud (Kumo) = shaded area between Span A and Span B\n  Green cloud: Span A > Span B (bullish sentiment)\n  Red cloud:   Span A < Span B (bearish sentiment)`,
  signals:[
    {t:'buy',  s:'Price above GREEN cloud + Tenkan >= Kijun → maximum bull confirmation (4/4 signals)'},
    {t:'buy',  s:'Tenkan crosses above Kijun (TK Cross) while price is above cloud → strong BUY'},
    {t:'buy',  s:'Price breaks above cloud after being inside/below → major trend change to bullish'},
    {t:'sell', s:'Price breaks below cloud → major trend change to bearish'},
    {t:'sell', s:'Tenkan crosses below Kijun while price is below RED cloud → maximum bear confirmation'},
    {t:'note', s:'Price INSIDE the cloud = indecision. Avoid new positions. Wait for a decisive break.'},
  ],
  tip:'Thick cloud = strong support/resistance coming. Thin cloud = price will slice through it easily. Before entering, look 26 bars ahead to see how thick the cloud is — that tells you how much resistance your trade will face.',
  combos:['Volume','RSI','MACD'],
  chart:'ichimoku',
  example:`Example — INFY.NS:
  Cloud status: Green (Span A > Span B) — bullish sentiment
  Price: ₹1,842 — above cloud top (₹1,798) ✓
  Tenkan: ₹1,856 > Kijun: ₹1,831 ✓
  Chikou: above price from 26 days ago ✓
  All 4 conditions met → Maximum confidence BUY
  
  Future cloud (26 bars ahead): thick green band at ₹1,760-1,780
  → Strong support zone already visible for next month`,
},

{
  id:'parabolic-sar', cat:'trend', tag:'useful', name:'Parabolic SAR',
  short:'Stop-And-Reverse — trailing stop dots that flip with trend',
  creator:'J. Welles Wilder, 1978',
  python:'indicators_extension.py → calc_parabolic_sar(df)',
  purpose:`SAR = Stop And Reverse. It places dots above or below every price bar:
<b>Dot below price</b> = uptrend is active (dot is your stop loss)
<b>Dot above price</b> = downtrend is active (dot is resistance)
When price crosses the dot, exit your current position and reverse direction.

The acceleration factor starts at 0.02 and increases by 0.02 every time price makes a new extreme in the current trend, up to a maximum of 0.20. This means the dot starts far from price (giving the trend room) and gradually tightens as the trend matures (protecting profits).

The word "Parabolic" comes from the curved shape the dots make as they accelerate toward price — it literally looks like a parabola on a chart.`,
  formula:`In uptrend:\nSAR(t) = SAR(t-1) + AF × (EP − SAR(t-1))\n  EP = Extreme Point (highest high in current uptrend)\n  AF = Acceleration Factor (starts 0.02, max 0.20)\n  AF increases 0.02 each time EP makes new high\n\n  SAR cannot be above previous 2 lows (safety rule)\n\nIn downtrend: mirror image with lowest lows\n  SAR cannot be below previous 2 highs\n\nFlip: when price crosses SAR → reverse direction\n  New SAR = old EP (the extreme of the previous trend)`,
  signals:[
    {t:'buy',  s:'Dots flip from above price to below price → uptrend starting, BUY'},
    {t:'sell', s:'Dots flip from below price to above price → downtrend starting, EXIT/SELL'},
    {t:'note', s:'The SAR level = your trailing stop loss. As it rises in uptrend, raise your stop with it.'},
    {t:'watch',s:'Small gap between price and SAR dot = trend is maturing, consider tightening or exiting'},
    {t:'watch',s:'Rapid sequence of flips (dots zigzagging) = ranging market. SAR is unreliable here.'},
  ],
  tip:'Always check ADX before acting on Parabolic SAR. ADX > 20 = trend exists, SAR is reliable. ADX < 20 = choppy sideways market, SAR will generate many false flips. Ignore SAR when ADX is low.',
  combos:['Supertrend','ADX','ATR'],
  chart:'parabolic_sar',
  example:`Example — SBIN.NS:
  Feb 1:  Dots above price → downtrend. SAR at ₹812.
  Feb 14: Close = ₹798 < SAR ₹798... wait, close crosses above SAR
  Feb 15: SAR flips below price at ₹779. AF resets to 0.02.
  
  Trade: BUY at ₹801 (next open after flip)
  Stop = ₹779 (new SAR level below price)
  
  Feb 20: New high = ₹834. EP updates. AF → 0.04. SAR rises to ₹786.
  Feb 28: SAR at ₹812. Stock at ₹842. Gap narrowing.
  Mar 5:  Close ₹831 < SAR ₹835 → dots flip → EXIT at ₹831.
  Trade P&L: ₹801 → ₹831 = +Rs 30/share (+3.7%)`,
},

{
  id:'dema-tema', cat:'trend', tag:'adv', name:'DEMA / TEMA',
  short:'Double & triple EMA — dramatically reduced lag',
  creator:'Patrick Mulloy, 1994',
  python:'advanced_indicators.py → calc_dema(), calc_tema()',
  purpose:`Standard EMA has a lag of roughly N/2 bars — a 20-period EMA lags price by about 10 bars. This matters because by the time the EMA confirms a trend, a significant part of the move has already happened.

<b>DEMA (Double EMA)</b> applies a correction that halves EMA's lag:
  DEMA = 2×EMA1 − EMA2 (where EMA2 = EMA of EMA1)

<b>TEMA (Triple EMA)</b> reduces it further to near-zero:
  TEMA = 3×EMA1 − 3×EMA2 + EMA3

The trade-off: less lag = slightly more noise. TEMA reacts fastest but also has the most false signals. Use it when you need speed — like intraday scalping on 1-minute or 3-minute charts.`,
  formula:`EMA1 = EMA(price, N)\nEMA2 = EMA(EMA1, N)\nDEMA = 2 × EMA1 − EMA2\n\nEMA3 = EMA(EMA2, N)\nTEMA = 3×EMA1 − 3×EMA2 + EMA3\n\nLag comparison for period=20:\n  SMA     → ~10 bars lag\n  EMA     → ~7 bars lag  \n  DEMA    → ~4 bars lag\n  TEMA    → ~1-2 bars lag\n  HMA     → near-zero, smooth`,
  signals:[
    {t:'buy',  s:'TEMA crosses above DEMA → early momentum signal (faster than EMA cross)'},
    {t:'buy',  s:'Price crosses above TEMA → trend confirmation with minimal lag'},
    {t:'sell', s:'TEMA crosses below DEMA → early bearish signal'},
    {t:'note', s:'Use DEMA as a drop-in replacement for EMA in any strategy for faster signals'},
    {t:'note', s:'TEMA is best for 1-5 minute intraday charts. For daily charts, HMA is smoother.'},
  ],
  tip:'Speed ladder: SMA → EMA → DEMA → TEMA → HMA (fastest to slowest lag). More speed = more noise. Match to your timeframe: TEMA for 1-min scalping, EMA for daily swing trading.',
  combos:['HMA','VWMA','EMA Ribbon','ATR'],
  chart:'dema_tema',
  example:`Example — same stock, different MAs at a trend start:
  Day 0: Price turns up. New uptrend beginning.
  Day 2: TEMA crosses above SMA → TEMA signals first
  Day 5: DEMA crosses above SMA → DEMA signals next
  Day 8: Standard EMA crosses above SMA → EMA signals
  Day 12: SMA 20 crosses above SMA 50 → SMA signals last
  
  TEMA entered 10 bars before SMA-based signal.
  On a ₹10 move, TEMA captured ₹8. SMA captured ₹5.`,
},

{
  id:'hma', cat:'trend', tag:'adv', name:'Hull Moving Average (HMA)',
  short:'Smoothest, most responsive MA — best of both worlds',
  creator:'Alan Hull, 2005',
  python:'advanced_indicators.py → calc_hma(df, period=21)',
  purpose:`Alan Hull set out to solve a fundamental problem: every moving average forces you to choose between smoothness (no noise) and responsiveness (no lag). More smoothing = more lag. Less smoothing = more noise. HMA solves both simultaneously.

The secret is using <b>Weighted Moving Averages</b> (WMAs) instead of EMAs, and applying the correction in a two-step process with a WMA(√period) final smooth.

WMA weights bars linearly: today=N, yesterday=N-1, etc. This gives a more aggressive recent-weighting than EMA without the exponential tail that keeps EMA slow.

The result is a moving average that turns sharply and decisively when trend changes — unlike EMA which curves gradually. The direction of HMA is unmistakably clear at all times.`,
  formula:`WMA(n): weights = [1, 2, 3, ..., n] (linear)\n  WMA = Σ(price × weight) / Σ(weights)\n\nStep 1: WMA(period/2)         — fast WMA, responds quickly\nStep 2: WMA(period)           — slow WMA, smoother\nStep 3: Raw = 2×WMA(half) − WMA(full)\n  → removes lag but still noisy\nStep 4: HMA = WMA(√period) of Raw\n  → √period gives minimal smoothing needed\n  → result: smooth AND fast\n\nFor period=21:\n  half = 10, sqrt = ~4.6 → use 5\n  WMA(10), WMA(21), then WMA(5) of correction`,
  signals:[
    {t:'buy',  s:'HMA slope turns upward (HMA today > HMA 3 days ago) → trend has turned bullish'},
    {t:'sell', s:'HMA slope turns downward → trend has turned bearish'},
    {t:'note', s:'HMA direction IS the signal — no crossovers needed. Just watch slope.'},
    {t:'buy',  s:'Price dips to touch HMA from above in uptrend + volume declining → buy the pullback'},
    {t:'watch',s:'HMA flattening → trend losing momentum. Tighten stops.'},
  ],
  tip:'HMA makes sharp, decisive turns unlike EMA which curves gradually. This makes it much easier to read — you know immediately when the trend changes. Use for daily charts where clarity matters more than speed.',
  combos:['Volume','RSI','DEMA'],
  chart:'hma',
  example:`Example — TITAN.NS:
  Comparing EMA(21) vs HMA(21) at trend reversal:
  
  Day 1-5: Price falling. Both EMA and HMA pointing down.
  Day 6:   Price starts to reverse up.
  Day 7:   HMA slope turns positive → BUY signal from HMA
  Day 11:  EMA finally turns positive → BUY signal from EMA
  
  4-day difference. On ₹50 move, HMA captures ₹42. EMA captures ₹28.
  The HMA's sharp turn vs EMA's gradual curve makes the difference.`,
},

{
  id:'alligator', cat:'trend', tag:'adv', name:'Williams Alligator',
  short:'3 offset SMAs — tells you when the market is sleeping',
  creator:'Bill Williams — Trading Chaos (1995)',
  python:'advanced_indicators.py → calc_alligator(df)',
  purpose:`Bill Williams observed that markets spend approximately 70% of time moving sideways (sleeping) and only 30% trending (eating). Most retail traders lose money by trading during the sleeping phase — mistaking choppy price movement for directional trends.

The Alligator uses three Smoothed Moving Averages (SMMA) with different periods and displacements to tell you the market's state:

<b>JAW (Blue, slow):</b> SMMA(13) shifted 8 bars forward — the alligator's teeth
<b>TEETH (Red, medium):</b> SMMA(8) shifted 5 bars forward  
<b>LIPS (Green, fast):</b> SMMA(5) shifted 3 bars forward

<b>Sleeping:</b> Lines tangled together → NO trades
<b>Waking:</b> Lines starting to separate → prepare
<b>Eating:</b> Lines fully ordered and fanning out → strong trend, trade it
<b>Sated:</b> Lines converging again → take profits`,
  formula:`Midprice = (High + Low) / 2\nSMMA uses alpha = 1/period (gentler than EMA)\n\nJaw   = SMMA(Midprice, 13), shifted 8 bars forward\nTeeth = SMMA(Midprice, 8),  shifted 5 bars forward\nLips  = SMMA(Midprice, 5),  shifted 3 bars forward\n\nBull eating: Lips > Teeth > Jaw AND price > Jaw\nBear eating: Lips < Teeth < Jaw AND price < Jaw\nSleeping:    Lines tangled or crossing frequently`,
  signals:[
    {t:'buy',  s:'Lips > Teeth > Jaw + price above all three → Alligator eating upward → BUY'},
    {t:'sell', s:'Lips < Teeth < Jaw + price below all three → Alligator eating downward → SELL'},
    {t:'note', s:'Lines tangled = Alligator sleeping = market ranging. Ignore all trend signals.'},
    {t:'watch',s:'Lines just starting to separate after tangle → Alligator waking → prepare entry'},
    {t:'sell', s:'Lines starting to converge after trend = sated. Take profits, reduce position.'},
  ],
  tip:'The most important use of the Alligator: knowing when NOT to trade. When it is sleeping, every other indicator will give false signals. Patience during the sleeping phase saves more money than any buy signal.',
  combos:['Awesome Oscillator','ADX','MACD'],
  chart:'alligator',
  example:`Example — MARUTI.NS (2-month period):
  
  Weeks 1-3: Jaw, Teeth, Lips all tangled (₹9,800-10,100)
    → Sleeping phase. RSI gave 4 "oversold" readings.
    → All 4 would have been false signals in the range.
  
  Week 4 (Day 22): Lines start to separate. Lips breaks above Teeth.
    → Alligator waking → reduce position size, prepare.
  
  Week 5 (Day 28): Full alignment: Lips(₹10,180) > Teeth(₹10,040) > Jaw(₹9,920)
    → Alligator eating → BUY at ₹10,200
    → Price moves to ₹11,400 over next 3 weeks (+11.7%)`,
},

{
  id:'vwma', cat:'trend', tag:'useful', name:'VWMA',
  short:'Volume Weighted MA — more accurate fair value',
  creator:'Derived from VWAP concept',
  python:'advanced_indicators.py → calc_vwma(df)',
  purpose:`VWMA gives more weight to prices that traded on high-volume days. A day with 10 crore shares traded has 100× more influence than a day with 10 lakh shares. This makes VWMA the most accurate representation of where money actually changed hands.

When VWMA is above SMA, it means the high-volume days (the days institutions were most active) had higher prices — bullish. When VWMA is below SMA, institutions were more active on down days — bearish.

The spread between VWMA and SMA is itself a signal: a widening spread shows one side gaining dominance in the volume-weighted picture.`,
  formula:`VWMA(N) = Σ(Close × Volume, last N days)\n          ─────────────────────────────────\n          Σ(Volume, last N days)\n\nSimple interpretation:\n  If price rises 5% on 1 crore shares but falls 2% on 10k shares,\n  the VWMA moves +4.8% (almost all of the rise) because the big\n  volume day dominates the weighted average.\n\nVWMA > SMA → High-volume days had higher prices → bullish\nVWMA < SMA → High-volume days had lower prices → bearish\nSpread widening → Dominance of one side increasing`,
  signals:[
    {t:'buy',  s:'VWMA above SMA 20 → institutions buying on strong-volume days → bullish'},
    {t:'sell', s:'VWMA below SMA 20 → institutions selling on strong-volume days → bearish'},
    {t:'buy',  s:'Price pulls back to VWMA in uptrend → institutional support level, buy'},
    {t:'note', s:'VWMA vs VWAP: VWAP resets daily (intraday). VWMA is rolling — works on all timeframes.'},
  ],
  tip:'When Nifty 50 is above its VWMA and VWMA is above SMA, the majority of institutional trading has been at higher prices. Smart money is long. This is the cleanest confirmation you have that institutions agree with your bullish thesis.',
  combos:['SMA','OBV','Volume'],
  chart:'vwma',
  example:`Example — HDFCBANK.NS over 20 days:
  
  Week 1: 3 big volume days (each 5 crore+ shares) all down days
  Week 2: 7 low-volume days, mixed moves
  Week 3: 2 huge-volume days (8 crore+ shares) both up days
  
  SMA 20: ₹1,628 (treats all days equally)
  VWMA 20: ₹1,612 (pulled down by week 1's sell-off on high volume)
  
  VWMA < SMA → despite recent price recovery, heavy-volume days
  were bearish → cautious interpretation, wait for confirmation`,
},

// ── MOMENTUM & other indicators ──
{
  id:'rsi', cat:'momentum', tag:'built', name:'RSI',
  short:'Relative Strength Index — overbought/oversold oscillator',
  creator:'J. Welles Wilder, 1978',
  python:'complete_indicators.py → calc_rsi(prices, period=14)',
  purpose:`RSI compares average gains to average losses over 14 periods, expressing momentum as a 0-100 oscillator. It is the most universally used momentum indicator across every market and timeframe.

<b>Why 70/30?</b> Wilder chose these levels because statistically, price closes above 70 on RSI only about 30% of the time — it represents genuine overextension. Below 30 is equally rare on the downside.

<b>The divergence signal</b> is RSI's most powerful output. When price makes a new high but RSI makes a lower high, buying pressure is fading even as price rises. This almost always precedes a reversal. In Indian markets, RSI divergence on weekly charts has preceded every major Nifty correction.

<b>Sweet spot for buys:</b> RSI 30-55 in an uptrend represents a healthy pullback — not oversold panic, not overbought euphoria. This is where the best risk/reward entries occur.`,
  formula:`For each bar:\n  Gain = max(Close − Close[prev], 0)\n  Loss = max(Close[prev] − Close, 0)\n\nWilder's smoothing (NOT simple average):\n  Avg Gain = (Avg Gain[prev] × 13 + Gain) / 14\n  Avg Loss = (Avg Loss[prev] × 13 + Loss) / 14\n\n  RS  = Avg Gain / Avg Loss\n  RSI = 100 − (100 / (1 + RS))\n\nKey levels:\n  RSI = 100 → only up days (impossible sustained)\n  RSI = 70  → overbought threshold\n  RSI = 50  → neutral/balanced\n  RSI = 30  → oversold threshold\n  RSI = 0   → only down days (impossible sustained)`,
  signals:[
    {t:'buy',  s:'RSI exits oversold zone (crosses above 30) → oversold pressure ending, BUY'},
    {t:'buy',  s:'RSI 30-55 in established uptrend → healthy pullback, best risk/reward entry'},
    {t:'sell', s:'RSI exits overbought zone (crosses below 70) → overbought pressure ending, SELL'},
    {t:'buy',  s:'Bullish divergence: price lower low + RSI higher low → reversal imminent, BUY'},
    {t:'sell', s:'Bearish divergence: price higher high + RSI lower high → top forming, SELL'},
    {t:'note', s:'In strong trends, RSI can stay above 70 for weeks. Don\'t short just because RSI is "overbought."'},
  ],
  tip:'RSI divergence on WEEKLY chart = major signal. If Nifty makes a new all-time high but weekly RSI makes a lower high, reduce exposure. This preceded every major correction from 2007-2024.',
  combos:['MACD','Bollinger Bands','Volume','MFI'],
  chart:'rsi',
  example:`Example — Bullish Divergence on BAJFINANCE.NS:
  
  Oct 15: Price = ₹6,840 (new 3-month low) | RSI = 24.2 (oversold)
  Oct 28: Price = ₹6,710 (new low!) | RSI = 31.8 (higher than Oct 15)
  
  Price made new low → bearish
  RSI made HIGHER low → bullish divergence
  RSI also exited oversold zone (crossed above 30 on Oct 29)
  
  Nov 5: BUY at ₹6,890 (confirmation bar closes above Oct 15 high)
  Dec 20: Price = ₹7,640 → +Rs 750/share (+10.9%)`,
},

{
  id:'macd', cat:'momentum', tag:'built', name:'MACD',
  short:'Moving Average Convergence Divergence — trend + momentum',
  creator:'Gerald Appel, 1970s',
  python:'complete_indicators.py → calc_macd(prices, fast=12, slow=26, signal=9)',
  purpose:`MACD measures the relationship between two EMAs to show both trend direction and the acceleration of momentum. It has three components:

<b>MACD Line:</b> EMA(12) − EMA(26). Above zero = bullish trend. Below zero = bearish trend.
<b>Signal Line:</b> EMA(9) of MACD Line. Smoother version used for crossover signals.
<b>Histogram:</b> MACD − Signal. Shows whether momentum is accelerating (bars growing) or decelerating (bars shrinking). This is MACD's most underused and most powerful feature.

<b>The power zone:</b> A bullish MACD crossover that occurs BELOW zero is the strongest possible signal. It means momentum is turning up from an oversold position — you have both reversal (below zero) and confirmation (crossover) simultaneously. Indian traders who only trade this setup have historically high win rates.`,
  formula:`MACD Line  = EMA(12) − EMA(26)\nSignal Line = EMA(9) of MACD Line\nHistogram  = MACD Line − Signal Line\n\nInterpretation of each component:\n  MACD Line above zero → EMA12 > EMA26 → uptrend\n  MACD Line below zero → EMA12 < EMA26 → downtrend\n  Histogram positive & growing → momentum accelerating\n  Histogram positive & shrinking → rally losing steam\n  Histogram negative & shrinking → sell-off exhausting\n  Histogram negative & growing → downtrend accelerating`,
  signals:[
    {t:'buy',  s:'MACD crosses above Signal line while BOTH below zero → power zone BUY signal'},
    {t:'buy',  s:'MACD crosses above zero line → trend officially confirmed bullish'},
    {t:'sell', s:'MACD crosses below Signal line while BOTH above zero → power zone SELL signal'},
    {t:'sell', s:'Histogram shrinking (positive but declining) → momentum fading, prepare to exit'},
    {t:'buy',  s:'Bullish divergence: price lower low + MACD higher low → reversal signal'},
  ],
  tip:'Watch the histogram, not just the crossover. A histogram that starts shrinking BEFORE the crossover happens gives you an early exit signal — you can sell before the official MACD cross occurs.',
  combos:['RSI','SMA 200','ADX','Volume'],
  chart:'macd',
  example:`Example — RELIANCE.NS:
  
  Nov 10: MACD Line = -18.4, Signal = -22.1 (both below zero)
  Nov 10: Histogram = +3.7 and GROWING → early momentum shift
  Nov 14: MACD (-14.2) crosses above Signal (-16.8) → BUY SIGNAL
    Both below zero → power zone signal
  Nov 14: BUY at ₹2,641
  
  Dec 5: MACD = +28.1, Signal = +24.3 (above zero, still bullish)
  Dec 12: Histogram begins shrinking (from +6.2 to +4.1)
    → Early warning: momentum fading
  Dec 18: MACD crosses below Signal → EXIT at ₹2,798
  Trade: ₹2,641 → ₹2,798 = +Rs 157/share (+5.9%) in 34 days`,
},

{
  id:'stochastic', cat:'momentum', tag:'built', name:'Stochastic Oscillator',
  short:'%K and %D — where did close land in the N-day range?',
  creator:'George Lane, 1950s',
  python:'complete_indicators.py → calc_stochastic(df, k_period=14, d_period=3)',
  purpose:`Stochastic measures where the closing price sits within the High-Low range of the last N days. George Lane's key insight: in strong uptrends, prices close near the TOP of their daily range. In downtrends, near the BOTTOM.

<b>%K</b> is the raw stochastic: where is today's close within the N-day range? 100 = at the high, 0 = at the low.
<b>%D</b> is a 3-period smoothing of %K — the signal line.

The critical rule: crossovers in the middle zone (40-60) are unreliable noise. Only act on crossovers in the extreme zones (below 20 or above 80). A %K/%D crossover at %K=15 is a legitimate oversold signal. The same crossover at %K=52 means nothing.`,
  formula:`%K (raw stochastic):\n  = 100 × (Close − Lowest Low in N days)\n         ─────────────────────────────────\n         (Highest High − Lowest Low in N days)\n\nSlow %K = SMA(3) of raw %K (smoother version)\n%D      = SMA(3) of Slow %K  (signal line)\n\nOverbought zone: %K > 80\nOversold zone:   %K < 20\n\n%K = 100 → closed at N-day high\n%K = 0   → closed at N-day low\n%K = 50  → closed at middle of N-day range`,
  signals:[
    {t:'buy',  s:'%K crosses above %D while both below 20 (oversold) → strong BUY'},
    {t:'sell', s:'%K crosses below %D while both above 80 (overbought) → strong SELL'},
    {t:'note', s:'Middle zone crossovers (40-60) = noise. Ignore them completely.'},
    {t:'buy',  s:'%K dips below 20 then rises back above 20 (without %D cross) → early buy alert'},
    {t:'watch',s:'Stochastic stays above 80 for multiple days → sustained momentum, not reversal yet'},
  ],
  tip:'Stochastic vs RSI: Stochastic reacts faster (better for intraday and 3-5 day swings). RSI is smoother (better for weekly swing and position trades). For NSE intraday on 15-min charts, Stochastic is often more reliable than RSI.',
  combos:['RSI','Bollinger Bands','MACD'],
  chart:'stochastic',
  example:`Example — ICICIBANK.NS 15-minute chart:
  
  10:15 AM: %K = 18.4, %D = 22.1 (both near oversold)
  10:30 AM: %K = 22.8, %D = 21.2 → %K crosses ABOVE %D (both ~20)
    → Valid oversold crossover signal
  10:30 AM: BUY at ₹1,182
  
  11:45 AM: %K = 84.2, %D = 78.1 (entering overbought zone)
  12:00 PM: %K = 79.8, %D = 81.4 → %K crosses BELOW %D (both ~80)
    → Valid overbought crossover signal
  12:00 PM: EXIT at ₹1,198
  Trade: ₹1,182 → ₹1,198 = +Rs 16/share (+1.35%) in 90 minutes`,
},

// VOLATILITY
{
  id:'bollinger', cat:'volatility', tag:'built', name:'Bollinger Bands',
  short:'SMA ± 2 standard deviations — statistical price envelope',
  creator:'John Bollinger, 1980s',
  python:'complete_indicators.py → calc_bollinger(prices, period=20, num_std=2)',
  purpose:`Bollinger Bands draw a statistical envelope around price that adapts to volatility. When the stock is volatile, the bands widen. When calm, they narrow. This makes them fundamentally different from fixed-width channels.

<b>%B indicator:</b> Where is price within the bands? %B=1.0 means at the upper band. %B=0.0 means at the lower band. %B=0.5 means at the middle band. You can set alerts when %B goes below 0.05 (extremely oversold) or above 0.95 (extremely overbought).

<b>Bandwidth indicator:</b> How wide are the bands as a % of price? When bandwidth reaches multi-month lows (the Squeeze), the market is coiling for an explosive breakout. Combined with Keltner Channels for the true BB+KC squeeze, this is one of the most powerful setups available.

<b>Band walking:</b> In strong uptrends, price "walks the upper band" — closing near or above the upper band for days or weeks. This is NOT a sell signal. It confirms a strong trend. Only start selling when price can no longer touch the upper band.`,
  formula:`Middle Band = SMA(Close, 20)\nStd Dev     = Rolling standard deviation over 20 days\n\nUpper Band  = Middle + 2 × Std Dev\nLower Band  = Middle − 2 × Std Dev\n\n%B = (Close − Lower) / (Upper − Lower)\n  %B = 1.0 → at upper band (statistically extended)\n  %B = 0.0 → at lower band (statistically depressed)\n  %B = 0.5 → at middle band\n\nBandwidth = (Upper − Lower) / Middle × 100\n  Rising BW → volatility expanding (trend developing)\n  Falling BW → volatility compressing (squeeze forming)`,
  signals:[
    {t:'buy',  s:'%B < 0.05 (at lower band) + RSI < 35 → double oversold signal, strong BUY'},
    {t:'sell', s:'%B > 0.95 (at upper band) + RSI > 65 → double overbought signal, SELL'},
    {t:'watch',s:'Bandwidth at 6-month low (squeeze) → big move coming. Wait for direction.'},
    {t:'buy',  s:'Squeeze releases and price breaks ABOVE upper band → bullish breakout BUY'},
    {t:'note', s:'Price touching upper band in uptrend = confirming strength, NOT a sell signal'},
  ],
  tip:'The Squeeze setup (bandwidth at multi-month lows) combined with Keltner Channels inside Bollinger Bands is the highest quality breakout setup. The longer the squeeze, the more explosive the breakout.',
  combos:['Keltner','RSI','MFI','Volume'],
  chart:'bollinger',
  example:`Example — ASIANPAINT.NS Squeeze Breakout:
  
  Dec 1-20: Bollinger Bands narrowing. BW drops from 8.2% to 3.1%
    (multi-month low in bandwidth)
  Dec 15: BB inside Keltner Channels → True squeeze confirmed
    → Alert: "Big move coming, no position yet"
  
  Dec 22: Price closes above upper BB at ₹3,418
    Volume = 2.3× average → high conviction breakout
  
  Dec 22: BUY at ₹3,420 (next day open)
  Jan 15: Price = ₹3,742 → +Rs 322/share (+9.4%) in 24 days`,
},

{
  id:'atr', cat:'volatility', tag:'built', name:'ATR — Average True Range',
  short:'Measures daily volatility including gaps — stop loss foundation',
  creator:'J. Welles Wilder, 1978',
  python:'complete_indicators.py → calc_atr(df, period=14)',
  purpose:`ATR measures how much a stock ACTUALLY moves each day, including gap moves. It is the foundation of professional stop loss calculation and position sizing.

<b>True Range</b> captures three scenarios:
1. Normal day: High − Low (today's trading range)
2. Gap up: |High − Previous Close| (gap up bigger than today's range)
3. Gap down: |Low − Previous Close| (gap down bigger than today's range)

A stock with ATR=₹35 means on an average day, that stock moves ₹35 from low to high. Your stop loss needs to be at least 1.5-2× ATR from your entry to survive normal daily noise. A stop tighter than 1× ATR will be hit by random price movement even if your direction is correct.

<b>ATR-based position sizing:</b> Risk ₹1,000 per trade. ATR=₹35. Stop = 2×ATR = ₹70. Shares = ₹1,000/₹70 = 14 shares. This keeps your rupee risk constant regardless of stock price.`,
  formula:`True Range for each bar:\n  TR = max(\n    High − Low,           (normal range)\n    |High − Close[prev]|,  (gap up scenario)\n    |Low  − Close[prev]|   (gap down scenario)\n  )\n\nATR = Wilder's smoothing of TR over 14 days:\n  ATR[1] = simple average of first 14 TRs\n  ATR[i] = (ATR[i-1] × 13 + TR[i]) / 14\n\nUsage in practice:\n  Stop loss  = Entry − 2 × ATR  (for long positions)\n  Stop loss  = Entry + 2 × ATR  (for short positions)\n  Position size = Risk ₹ / (2 × ATR)`,
  signals:[
    {t:'note', s:'ATR is NOT directional — it only measures volatility size, not direction'},
    {t:'watch',s:'Stop loss = Entry − 2×ATR keeps you outside normal daily noise'},
    {t:'watch',s:'ATR expanding rapidly → increasing volatility (trend accelerating or panic)'},
    {t:'watch',s:'ATR at multi-month lows → quiet market, potentially coiling for big move'},
    {t:'note', s:'ATR contracts BEFORE big moves (price coiling) then expands DURING the move'},
  ],
  tip:'Never set a stop loss tighter than 1×ATR. If your entry-to-stop distance is less than 1×ATR, you will get stopped out by random noise even when you\'re right about direction. Use 1.5-2×ATR minimum.',
  combos:['Supertrend','Keltner','Parabolic SAR','Position Sizing'],
  chart:'atr',
  example:`Example — Position Sizing with ATR:
  
  Stock: WIPRO.NS, Close = ₹485, ATR(14) = ₹12.4
  
  Your risk per trade: ₹2,000
  Stop loss distance: 2 × ₹12.4 = ₹24.8
  Stop level: ₹485 − ₹24.8 = ₹460.2
  
  Shares to buy: ₹2,000 / ₹24.8 = 80 shares
  Capital required: 80 × ₹485 = ₹38,800
  
  If stopped out at ₹460.2: lose 80 × ₹24.8 = exactly ₹1,984 ≈ ₹2,000
  Risk is controlled regardless of stock price or volatility.`,
},

// CANDLESTICK PATTERNS
{
  id:'candlestick', cat:'patterns', tag:'built', name:'Candlestick Patterns',
  short:'Price action reversal signals from Japanese rice traders',
  creator:'Munehisa Homma, Japan (1700s). Western: Steve Nison (1991)',
  python:'complete_indicators.py → is_hammer(), is_bullish_engulfing(), is_doji()',
  purpose:`Candlestick patterns are the language of price action. Each candle tells a story: who won the battle between buyers and sellers on that day.

<b>Reading a candle:</b>
- Body (thick part) = distance between Open and Close
- Upper wick = how high buyers pushed price (and where sellers took over)
- Lower wick = how low sellers pushed price (and where buyers stepped in)
- Green/White body = Close > Open (buyers won)
- Red/Black body = Close < Open (sellers won)

<b>The key insight:</b> patterns reveal the CHANGE in sentiment. A Hammer means sellers pushed price down all day, but by close, buyers fought back strongly and recovered most of the loss. The long lower wick = sellers tried and failed. This shift in control often marks a bottom.

All 8 patterns in the code are detected automatically by the screener and score 1 point in the scoring system.`,
  formula:`HAMMER (bullish reversal from downtrend):\n  Body < 30% of total range\n  Lower wick ≥ 2× body length\n  Upper wick ≤ 10% of body length\n  Appears at bottom of downtrend\n\nBULLISH ENGULFING:\n  Day 1: Red candle (Close < Open)\n  Day 2: Green candle with larger body\n  Day 2 Open < Day 1 Close\n  Day 2 Close > Day 1 Open\n  → Green completely engulfs the red\n\nDOJI:\n  |Close − Open| / (High − Low) < 10%\n  → Open and Close almost equal (indecision)\n\nMORNING STAR (3-bar reversal):\n  Day 1: Large red candle (downtrend)\n  Day 2: Small body (Doji or Spinning Top) — gap down\n  Day 3: Large green candle closing above Day 1 midpoint`,
  signals:[
    {t:'buy',  s:'Hammer at support level + increasing volume → strong reversal buy signal'},
    {t:'buy',  s:'Bullish Engulfing after 3+ red days → momentum shift, BUY next open'},
    {t:'buy',  s:'Morning Star at Fibonacci 61.8% level → triple confirmation reversal'},
    {t:'sell', s:'Shooting Star at resistance level → sellers took control, exit longs'},
    {t:'sell', s:'Bearish Engulfing after sustained uptrend → distribution starting'},
    {t:'watch',s:'Doji alone = indecision. Need next bar to confirm direction. Do not act on Doji alone.'},
  ],
  tip:'Never trade a candlestick pattern without context. A Hammer at a major support level with rising volume = high quality. A Hammer in the middle of nowhere with no volume = noise. Context is everything.',
  combos:['RSI','Fibonacci Levels','Pivot Points','Volume'],
  chart:'candlestick',
  example:`Patterns at Key Levels — HDFCBANK.NS:
  
  Example 1 — Hammer at Pivot S1:
    Day's Pivot S1 = ₹1,598
    10:30 AM: Hammer candle. Low=₹1,591, Close=₹1,602
    Lower wick = ₹11 (long), Body = ₹4 (small) ✓
    Volume = 2.1× average → conviction ✓
    BUY at ₹1,605 (confirmation next candle close above high)
    
  Example 2 — Bullish Engulfing at SMA 200:
    SMA 200 = ₹1,540
    Nov 5: Red candle, Close = ₹1,537 (below SMA 200)
    Nov 6: Large green candle, Open = ₹1,532, Close = ₹1,561
      Nov 6 body (₹29) completely engulfs Nov 5 body (₹18) ✓
    BUY on Nov 6 close confirmation ✓`,
},

// SCREENER FILTERS
{
  id:'liquidity-filter', cat:'filters', tag:'new', name:'Liquidity Pre-Filter',
  short:'ADV + Amihud + Consistency — is this stock actually tradeable?',
  creator:'v3 screener improvement | screener_v3.py',
  python:'screener_v3.py → check_liquidity(df, preset)',
  purpose:`The liquidity filter is the first check in the v3 screener and the most impactful improvement over v2. It answers the fundamental question: <b>can I actually trade this stock without the market working against me?</b>

Before v3, the screener would happily score a stock with 13/13 indicators aligned even if that stock traded only 2,000 shares per day. If you tried to buy ₹50,000 worth, your single order would represent 20+ days of average volume — you would move the price against yourself just by entering.

<b>Three measures work together:</b>

1. <b>Average Daily Value (ADV):</b> Total rupees traded per day (Close × Volume, 20-day average). Your trade should be < 1% of ADV. Wanting to trade ₹1 lakh? The stock needs ₹1 crore daily ADV minimum.

2. <b>Amihud Illiquidity Ratio:</b> How much does the price move per crore of volume traded? Low ratio = liquid (price barely responds to volume). High ratio = illiquid (even small orders cause slippage). Formula: avg(|daily return| / daily volume in crores).

3. <b>Volume Consistency:</b> Does the stock trade reliably every day? Catches the block-deal trap: one massive 50-crore block deal inflates the 20-day average even if the stock barely trades on 58 other days.`,
  formula:`MEASURE 1 — Average Daily Value (ADV):\n  Daily Value = Close × Volume  (rupees per day)\n  ADV = rolling 20-day mean of Daily Value\n  Convert to crores: ADV_Cr = ADV / 10,000,000\n\n  The 1% rule: trade size < 1% of ADV\n\nMEASURE 2 — Amihud Illiquidity Ratio:\n  |Return| = abs(Close/Close[prev] − 1)\n  Volume_Cr = (Close × Volume) / 10,000,000\n  Daily Amihud = |Return| / Volume_Cr\n  Amihud = rolling 20-day mean (outliers capped at p99)\n\n  Low Amihud (< 0.01) → extremely liquid (Nifty 50 large caps)\n  High Amihud (> 0.50) → illiquid, avoid\n\nMEASURE 3 — Volume Consistency:\n  % of last 60 days where volume > minimum threshold\n  Must be > 70% (stock cannot trade reliably only on some days)`,
  signals:[
    {t:'note', s:'Grade A: ADV > 5× threshold + Amihud low + 100% consistency → perfect liquidity'},
    {t:'note', s:'Grade B: Passes all thresholds comfortably → liquid enough to trade'},
    {t:'watch',s:'Grade C: Barely passes → trade with caution, use limit orders always'},
    {t:'sell', s:'Grade F: Fails any check → stock rejected before indicator scoring begins'},
    {t:'note', s:'Typical rejection rate: 15-25% of Nifty 500 stocks fail liquidity for medium-sized traders'},
  ],
  tip:'The liquidity filter saves time AND money. Calculating 13 indicators on an illiquid stock takes 0.5 seconds of compute time. The liquidity check takes 0.01 seconds. Rejecting early saves both scan time and trading losses.',
  combos:['Fundamental Filter','Market Regime','ATR','Position Sizing'],
  chart:'liquidity',
  example:`Liquidity Preset Comparison for Rs 1,00,000 trade:
  
  Preset      Min ADV      Max Amihud  Min Consistency
  ─────────────────────────────────────────────────────
  Small       Rs 0.5Cr     0.50        60%    (up to Rs 50k)
  Medium      Rs 2.0Cr     0.20        70%    (Rs 50k-2L)
  Large       Rs 10.0Cr    0.05        80%    (Rs 2L-10L)
  Instit.     Rs 50.0Cr    0.01        90%    (Rs 10L+)
  
  Example: TRIDENT.NS (medium preset)
  ADV: Rs 3.2 Cr/day ✓  Amihud: 0.31 (FAIL > 0.20 max)
  Result: REJECTED — too much price impact per rupee traded
  
  Example: HDFCBANK.NS (medium preset)
  ADV: Rs 1,847 Cr/day ✓  Amihud: 0.0003 ✓  Consistency: 100% ✓
  Grade: A | Max safe trade: Rs 18.47 crore`,
},

{
  id:'fundamental-filter', cat:'filters', tag:'new', name:'Fundamental Quality Gate',
  short:'PE, promoter holding, D/E, revenue growth — remove broken companies',
  creator:'v3 screener improvement | screener_v3.py',
  python:'screener_v3.py → check_fundamentals(ticker)',
  purpose:`A technically perfect chart pattern in a fundamentally broken company is a trap. The indicators see a base forming — but the company is reporting losses, promoters are selling, and debt is exploding. The "breakout" fails because there are no real buyers.

The fundamental filter removes these structural traps before any indicator work is done. It uses four data points available free via yfinance.info:

<b>PE Ratio:</b> Price-to-Earnings. PE > 200 usually means earnings are near-zero (denominator problem) or the stock is wildly speculative. PE < 0 means losses.

<b>Promoter Holding:</b> In Indian markets, promoter holding < 25% is a warning sign. The people who built the company don't trust it enough to hold significant stake. Below 10% is serious.

<b>Debt-to-Equity (D/E):</b> D/E > 2.0 means debt is twice equity — overleveraged. Rising interest costs eat earnings. Technical breakouts in overleveraged companies frequently fail. Exception: banks and NBFCs naturally have high D/E.

<b>Revenue Growth:</b> Revenue shrinking > 15% YoY = the business itself is contracting. A technical recovery in a shrinking business has low probability of sustaining.`,
  formula:`PE Ratio check:\n  pe = info.get('trailingPE')\n  FAIL if pe < 0 (loss-making)\n  FAIL if pe > 200 (overvalued or near-zero earnings)\n\nPromoter Holding check:\n  promoter = info.get('heldPercentInsiders') × 100\n  FAIL if promoter < 10% (serious red flag)\n  WARN if promoter < 25% (caution, not fail)\n\nDebt/Equity check:\n  de = info.get('debtToEquity') / 100  (yfinance returns %)\n  Skip check if sector = financial/banking\n  FAIL if de > 2.0 (over-leveraged)\n\nRevenue Growth check:\n  rev = info.get('revenueGrowth')  (decimal: 0.15 = +15%)\n  FAIL if rev < -0.15 (shrinking > 15% YoY)`,
  signals:[
    {t:'note', s:'Passes all 4 → stock has solid fundamentals, proceed to indicator scoring'},
    {t:'watch',s:'PE warning (100-200) → speculative but not rejected, watch position size'},
    {t:'sell', s:'Promoter < 10% → serious red flag, rejected'},
    {t:'sell', s:'D/E > 2.0 (non-financial) → over-leveraged, rejected'},
    {t:'note', s:'~10-15% of Nifty 500 stocks typically fail fundamentals in any given scan'},
  ],
  tip:'Fundamental filter catches the most painful type of loss: technically perfect pattern + fundamentally broken company. The chart sets up beautifully because few people are watching fundamentals. Then a bad earnings result destroys the position.',
  combos:['Liquidity Filter','Market Regime','Relative Strength'],
  chart:'fundamental',
  example:`Fund. Filter in Action:
  
  Stock A — YESBANK.NS (2019):
  Technical: RSI=32, near support, bullish engulfing → score 8/13 (v2)
  Fundamental check: PE = N/A (losses) → REJECTED
  Result of rejection: Stock fell from ₹80 to ₹5 (-94%)
  Filter saved a catastrophic loss.
  
  Stock B — UPL.NS (2023):
  Technical: Supertrend bullish, MACD cross → score 11/13 (v2)
  Fundamental check: D/E = 2.4 (exceeds 2.0 threshold) → REJECTED
  Stock fell 35% over next 6 months on debt concerns.
  
  Both stocks had excellent technicals. Fundamentals told the real story.`,
},

{
  id:'weighted-scoring', cat:'filters', tag:'new', name:'Weighted Scoring System',
  short:'Not all signals are equal — v3 assigns different weights',
  creator:'v3 screener improvement | screener_v3.py',
  python:'screener_v3.py → WEIGHTS dict, score_stock()',
  purpose:`The v1 and v2 screener gave exactly 1 point to every condition, making a Supertrend flip worth the same as a slightly-oversold Stochastic. In reality, these signals have vastly different reliability and rarity.

The weighted system assigns points proportional to each signal's historical reliability on NSE. A Supertrend direction flip gets 3 points because it is rare, reliable, and has a high win rate as a standalone signal. RSI in the 30-55 zone gets 1 point because it is common context information, not a trigger.

<b>The result:</b> A stock with a Supertrend flip + Golden Cross + MACD cross gets 3+2+2=7 points for just these three signals. Under the old system it would get 3/20. Under the new system it gets 7/35+ — a more meaningful separation from stocks that just happen to pass several weak conditions simultaneously.

Max weighted score ≈ 35. Plus 3 RS bonus + 2 MTF bonus = 40 maximum total.`,
  formula:`WEIGHTS = {\n  # Structural / Trend (high reliability)\n  'supertrend'    : 3,  # Rare flip, highly reliable on NSE\n  'golden_cross'  : 2,  # Strong long-term alignment\n  'macd_cross'    : 2,  # Timing signal with evidence\n  'adx_strong'    : 2,  # Confirms trend has real strength\n  'ichimoku'      : 2,  # Multi-component confirmation\n  'psar_bull'     : 2,  # Clear directional signal\n  'bb_setup'      : 2,  # Volatility compression (powerful)\n  'donchian_brk'  : 2,  # Volume-confirmed breakout\n  'cmf_accum'     : 2,  # Institutional accumulation\n  'aroon_trend'   : 2,  # Early trend detection\n  \n  # Context / Supporting (moderate reliability)\n  'sma200'        : 1,  # Necessary filter, not sufficient\n  'rsi_sweet'     : 1,  # Context, not trigger\n  'stoch_oversold': 1,  # Faster RSI, context signal\n  'high_volume'   : 1,  # Confirmation\n  'obv_rising'    : 1,  # Volume trend\n  'candle_pat'    : 1,  # Timing precision\n  'williams_r'    : 1,  # Fast momentum, context\n  'hma_rising'    : 1,  # Low-lag filter\n  'force_idx'     : 1,  # Volume × price momentum\n  'bb_kc_squeeze' : 2,  # True squeeze setup\n}\nMax weighted score ≈ 35\n\nBonus points (on top of weighted score):\n  RS rating bonus: 0-3 (relative strength vs Nifty)\n  MTF bonus: 0-2 (weekly trend aligned)\n  Total maximum: ~40 points`,
  signals:[
    {t:'note', s:'Score 30-40: Exceptional — maximum indicator alignment, very rare (1-3 stocks in Nifty 100)'},
    {t:'note', s:'Score 22-29: Strong — multiple high-weight signals aligned, high watchlist priority'},
    {t:'note', s:'Score 16-21: Moderate — worth watching, fewer high-weight signals'},
    {t:'note', s:'Score < 16: Weak — insufficient alignment, skip unless in BULL regime'},
  ],
  tip:'Weighted scores make the difference between stocks more meaningful. A score of 28 vs 18 tells you something real: the 28-scoring stock has major signals like Supertrend + MACD cross + ADX confirmation, while the 18 might just have many minor signals.',
  combos:['Liquidity Filter','RS Rating','Market Regime','MTF Gate'],
  chart:'weighted_scoring',
  example:`Same stock, old vs new scoring:
  
  Conditions firing for Stock X:
    Supertrend bullish flip  → old: 1pt | new: 3pts
    Golden Cross zone        → old: 1pt | new: 2pts
    MACD bullish cross       → old: 1pt | new: 2pts
    RSI 30-55                → old: 1pt | new: 1pt
    High volume              → old: 1pt | new: 1pt
    OBV rising               → old: 1pt | new: 1pt
  
  Old total: 6/13 (scored same as stock with 6 weak signals)
  New total: 10/35 base (clearly distinguished)
  + RS bonus: +2 (outperforming Nifty by 6%)
  + MTF bonus: +2 (weekly trend STRONG)
  Final: 14/40 — properly reflects signal quality`,
},

{
  id:'rs-rating', cat:'filters', tag:'new', name:'Relative Strength Rating',
  short:'How does this stock compare to Nifty? Leaders break out first.',
  creator:'Based on IBD RS Rating concept | v3 screener',
  python:'screener_v3.py → calc_rs_rating(stock_close, nifty_close)',
  purpose:`Relative Strength (RS) measures how a stock performs compared to the Nifty 50 index. A stock with RS+15% outperformed Nifty by 15% over the last 3 months — it is a market leader.

<b>Why leaders matter:</b> In every bull market, a small number of leading stocks account for the majority of gains. These leaders show strength BEFORE the market rallies — they go up more on up days and fall less on down days. When the market eventually breaks out, these leaders have already been accumulating and they lead the charge.

Finding leaders early using RS rating is how professional fund managers systematically outperform. William O'Neil, founder of Investor's Business Daily, built his entire CANSLIM system around RS rating. He required RS > 80th percentile before buying any stock.

<b>v3 implementation:</b> 3-month return of the stock minus 3-month return of Nifty 50. Positive = outperforming. Negative = underperforming. Added as bonus points to the weighted score.`,
  formula:`Stock 3-month return:\n  S_return = (Close / Close[63 days ago] − 1) × 100\n\nNifty 50 3-month return:\n  N_return = (Nifty / Nifty[63 days ago] − 1) × 100\n\nRS Score = S_return − N_return\n\nBonus point allocation:\n  RS > +10% → +3 bonus points (clear market leader)\n  RS > +5%  → +2 bonus points (outperformer)\n  RS > 0%   → +1 bonus point  (at least keeping pace)\n  RS ≤ 0%   → +0 bonus points (lagging — avoid)\n\nNote: Negative RS stocks are penalized in ranking\neven if they pass all other filters.`,
  signals:[
    {t:'buy',  s:'RS > +10% + strong indicator score → market leader with technicals aligned, highest priority'},
    {t:'buy',  s:'RS > +5% → stock outperforming index, worth prioritizing in watchlist'},
    {t:'watch',s:'RS 0-5% → keeping pace with market, acceptable but not a leader'},
    {t:'sell', s:'RS < 0% → underperforming Nifty. Why buy a laggard when leaders exist?'},
    {t:'note', s:'RS is calculated using Nifty 50 downloaded fresh each scan day'},
  ],
  tip:'In a bull market, focus exclusively on stocks with positive RS. You have 500 stocks to choose from. Only buy the ones already showing leadership. Laggards often stay laggards.',
  combos:['Market Regime','Weighted Scoring','MTF Gate'],
  chart:'rs_rating',
  example:`RS Rating in Bull Market (Q1 2024):
  
  Stock A: TITAN.NS
    Stock 3-month return: +18.4%
    Nifty 3-month return: +7.2%
    RS Score: +11.2% → LEADER → +3 bonus points
  
  Stock B: SUNPHARMA.NS
    Stock 3-month return: +9.1%
    Nifty 3-month return: +7.2%
    RS Score: +1.9% → mild outperformer → +1 bonus point
  
  Stock C: HCLTECH.NS
    Stock 3-month return: +3.8%
    Nifty 3-month return: +7.2%
    RS Score: -3.4% → lagging → +0 bonus points
  
  Same Nifty, same month: leaders vs laggards are clear.
  In the next month, TITAN continued higher. HCLTECH flat.`,
},

{
  id:'market-regime', cat:'filters', tag:'new', name:'Market Regime Detection',
  short:'Bull / Bear / Sideways — adjusts thresholds dynamically',
  creator:'v3 screener improvement | screener_v3.py',
  python:'screener_v3.py → detect_market_regime()',
  purpose:`The same RSI reading of 35 means very different things in a bull market vs a bear market. In a bull market, RSI=35 is a healthy pullback in an uptrend — a buy. In a bear market, RSI=35 might still be falling toward 20. The indicator is the same; the context changes everything.

The v3 screener detects the market regime before scanning any stocks, then automatically adjusts the qualify threshold:
<b>BULL regime:</b> Many stocks look good → raise bar to qualify (18+) so you are selective
<b>BEAR regime:</b> Only strongest survive → raise bar much higher (24+) to avoid value traps
<b>SIDEWAYS:</b> Mixed signals → moderate threshold (20+)

<b>Four signals used to determine regime:</b>
1. Nifty 50 vs SMA 200 (is the index in long-term uptrend?)
2. Nifty 50 vs SMA 50 (is the index in medium-term uptrend?)
3. Breadth: % of Nifty 50 stocks above their SMA 50 (is the move broad or narrow?)
4. Nifty 50 RSI (is index momentum positive?)`,
  formula:`Download Nifty 50 (^NSEI) daily data\n\nSignals:\n  above_sma200 = Nifty > SMA(200)\n  above_sma50  = Nifty > SMA(50)\n  breadth_pct  = % of Nifty 50 stocks above their SMA(50)\n  nifty_rsi    = RSI(14) of Nifty 50 index\n\nBull signals = count of:\n  above_sma200, above_sma50,\n  breadth_pct > 60%, nifty_rsi > 50\n\nBear signals = count of:\n  NOT above_sma200, NOT above_sma50,\n  breadth_pct < 40%, nifty_rsi < 45\n\nRegime determination:\n  bull_signals >= 3 → BULL  → qualify at score >= 18\n  bear_signals >= 3 → BEAR  → qualify at score >= 24\n  else              → SIDEWAYS → qualify at score >= 20`,
  signals:[
    {t:'note', s:'BULL regime: qualify at 18+. Many stocks align → be selective. Reduce position size slightly.'},
    {t:'note', s:'SIDEWAYS: qualify at 20+. Mixed conditions → require stronger confirmation before acting.'},
    {t:'sell', s:'BEAR regime: qualify at 24+. Only exceptional setups survive. Significantly reduce size.'},
    {t:'watch',s:'Regime changes from BULL to SIDEWAYS → early warning. Begin taking profits on existing positions.'},
  ],
  tip:'The regime detection runs once before scanning and takes about 60 seconds. It downloads Nifty and checks breadth for all 50 stocks. This single step saves you from buying aggressively in bear markets.',
  combos:['Liquidity Filter','Fundamental Filter','MTF Gate','Weighted Scoring'],
  chart:'market_regime',
  example:`Market Regime Examples:
  
  Jan 2024 (BULL detected):
    Nifty: 21,853 | Above SMA200 ✓ | Above SMA50 ✓
    Breadth: 72% stocks above SMA50 ✓
    Nifty RSI: 62.4 ✓ | Bull signals = 4/4
    Qualify threshold set: 18 → 11 stocks qualify from Nifty 50
  
  Mar 2020 (BEAR detected):
    Nifty: 7,610 | Below SMA200 ✗ | Below SMA50 ✗
    Breadth: 4% stocks above SMA50 ✗
    Nifty RSI: 22.1 ✗ | Bear signals = 4/4
    Qualify threshold set: 24 → 0 stocks qualify
    Output: "No trades. Market is in BEAR regime. Wait."`,
},

{
  id:'mtf-gate', cat:'filters', tag:'new', name:'Weekly MTF Gate',
  short:'Weekly trend must agree before daily signals score',
  creator:'v3 screener improvement | screener_v3.py',
  python:'screener_v3.py → check_weekly_gate(df_weekly)',
  purpose:`MTF = Multi-TimeFrame. The core insight: a daily oversold RSI signal is 3× more reliable when the weekly trend agrees than when it doesn't.

Think of it this way: the weekly chart shows the "big river" direction. The daily chart shows "small ripples" within that river. Swimming upstream (trading against the weekly trend) is always harder than swimming with it.

In v2, the screener evaluated stocks on daily data only. A bearish weekly trend was invisible to it. This meant stocks in genuine weekly downtrends would pass all daily signal filters — you'd buy a stock whose daily setup looked great but whose larger trend was hostile.

<b>Three weekly checks:</b>
1. Close > Weekly SMA 20 (medium-term weekly uptrend)
2. Weekly RSI > 45 (weekly momentum not in a spiral)
3. Weekly MACD positive or rising (weekly money flow)

<b>Gate outcomes:</b>
STRONG (3/3): Full scoring + 2 bonus points
MODERATE (2/3): Full scoring, no bonus
WEAK (1/3): Daily score capped at 15 (reduce confidence)
BLOCKED (0/3): Skip stock entirely — do not score`,
  formula:`Download weekly OHLCV data (interval="1wk", period="2y")\n\nCalculate on weekly bars:\n  SMA_20w = SMA(weekly Close, 20)\n  RSI_14w = RSI(weekly Close, 14)\n  MACD_w, Signal_w = MACD(weekly Close)\n\nWeekly checks:\n  check1 = Close_w > SMA_20w      (weekly uptrend)\n  check2 = RSI_14w > 45           (weekly momentum ok)\n  check3 = MACD_w > Signal_w      (weekly MACD bullish)\n       OR MACD_w > MACD_w[prev]   (weekly MACD rising)\n\npasses = check1 + check2 + check3 (count of True)\n\nGate:  passes==3 → STRONG (+2 bonus)\n       passes==2 → MODERATE (0 bonus)\n       passes==1 → WEAK (cap daily score at 15)\n       passes==0 → BLOCKED (skip, no score)`,
  signals:[
    {t:'buy',  s:'STRONG gate (weekly fully bullish) → daily signals are most reliable, +2 bonus pts'},
    {t:'buy',  s:'MODERATE gate → proceed normally, signals are reasonably reliable'},
    {t:'watch',s:'WEAK gate → daily signal exists but weekly disagrees. Reduce position size by 50%.'},
    {t:'sell', s:'BLOCKED gate → weekly trend fully bearish. Do not buy even if daily signals look perfect.'},
  ],
  tip:'The BLOCKED gate is the most valuable outcome. It prevents you from buying a stock in a weekly downtrend even when every daily indicator looks bullish. Weekly downtrends kill daily signals consistently.',
  combos:['Market Regime','Weighted Scoring','RS Rating'],
  chart:'mtf_gate',
  example:`MTF Gate Impact:
  
  Stock: BAJFINANCE.NS
  Weekly status: Close ₹6,820 < SMA_20w ₹7,240 (below weekly MA)
                 Weekly RSI = 38.4 (weak momentum)
                 Weekly MACD negative and falling
  Gate: BLOCKED (0/3 weekly checks pass)
  
  Daily signals firing: RSI=31, Hammer candle, near support
    Under v2: would score 8/13 → ENTER TRADE
    Under v3: BLOCKED by weekly gate → NO TRADE
  
  Result: Stock fell another 15% over next 3 weeks.
  The weekly downtrend invalidated all daily signals.
  V3 correctly blocked the trade. V2 would have entered.`,
},

// STRATEGIES
{
  id:'triple-confirmation', cat:'strategies', tag:'built', name:'Triple Confirmation Strategy',
  short:'Price above SMA200 + RSI pullback + MACD cross + Volume',
  creator:'backtester.py / backtester_v2.py — Strategy 1',
  python:'backtester_v2.py → strategy_triple_confirmation()',
  purpose:`Triple Confirmation is the safest, most conservative strategy in the system. It requires multiple independent signals to align before entering, dramatically reducing false positives at the cost of entering later.

<b>The philosophy:</b> Wait for the long-term trend, the momentum indicator, the trigger signal, and volume confirmation all to agree simultaneously. Any one condition in isolation is unreliable. All four together are significantly more reliable.

This strategy is ideal for traders who:
- Prefer fewer but higher-quality trades
- Want to sleep well knowing the position has strong backing
- Are still learning and want to avoid impulsive trades

<b>Backtested performance (typical):</b> ~45-55% win rate with 2:1 average reward-to-risk ratio gives a positive expectancy. Not exciting trade-by-trade, but consistently profitable over time.`,
  formula:`ENTRY conditions (ALL must be true):\n  1. Close > SMA(200)      → long-term uptrend filter\n  2. SMA(50) > SMA(200)    → Golden Cross zone (medium-term)\n  3. RSI between 30-55     → healthy pullback, not overbought\n  4. MACD bullish crossover in last 3 days → momentum trigger\n  5. Volume ≥ 1.0× average → minimum participation\n\nEXIT conditions (first one hit wins):\n  Stop loss: price drops below SMA(50)\n  Take profit: +10% from entry (configurable)\n  Time stop: 20 trading days maximum hold\n  Strategy exit: SMA(50) broken\n\nKey rationale: the SMA(200) filter removes the majority\nof bear market false signals. RSI 30-55 ensures entry\nat the beginning of momentum, not the exhaustion.`,
  signals:[
    {t:'buy',  s:'All 5 conditions met simultaneously → ENTER at next day open'},
    {t:'sell', s:'Close < SMA 50 → trend broken, EXIT at next open'},
    {t:'sell', s:'Price reaches +10% profit target → TAKE PROFIT'},
    {t:'sell', s:'20 trading days elapsed without hitting stop or target → TIME STOP EXIT'},
    {t:'note', s:'Typical trade frequency: 2-4 trades per month per stock universe'},
  ],
  tip:'The MACD crossover below zero is the strongest version of condition 4. When MACD crosses above its signal line while both are negative, you get momentum starting from an oversold position — the highest quality entry.',
  combos:['ADX Filter','Volume','SMA 200'],
  chart:'triple_confirm',
  example:`Backtest Summary (RELIANCE.NS, 3 years, 2021-2024):
  
  Total trades:     47
  Winning trades:   26  (55.3%)
  Losing trades:    21  (44.7%)
  
  Average win:      +7.8%
  Average loss:     -4.2%
  Win/Loss ratio:   1.86:1
  
  Total return:     +62.4%
  Max drawdown:     -18.2%
  Sharpe ratio:     1.42
  Profit factor:    2.17
  
  Best trade:  +10.0% (hit profit target, MACD cross below zero)
  Worst trade: -5.0%  (hit stop loss at SMA 50 break)`,
},

{
  id:'supertrend-strategy', cat:'strategies', tag:'built', name:'Supertrend Strategy',
  short:'Direction flip + ADX confirmation — clean trend-following',
  creator:'backtester_v2.py — Strategy 5',
  python:'backtester_v2.py → strategy_supertrend()',
  purpose:`The Supertrend strategy is the most popular mechanical trend-following system among Indian retail traders. It generates clear, objective signals: when the Supertrend flips bullish, buy. When it flips bearish, sell. No interpretation needed.

The system uses the Supertrend flip as the primary signal with ADX as a confirmation filter. ADX > 20 ensures the flip is happening in a trending environment, not in a choppy sideways market where Supertrend generates frequent false signals.

<b>Why this works on NSE:</b> Indian markets trend strongly when they trend. Supertrend's ATR-based construction naturally adapts to the volatility of each stock. For a highly volatile stock, the band is wider and avoids false flips. For a calm stock, the band is tighter and catches moves earlier.

<b>Position management:</b> The Supertrend line itself acts as a trailing stop during the trade. As the stock rises, the Supertrend line rises with it, automatically protecting profits without any manual intervention.`,
  formula:`ENTRY conditions:\n  1. Supertrend direction flips from -1 to +1\n     (line moves from above price to below price)\n  2. ADX > 20 (trend has real strength)\n  3. Volume ≥ 1.0× average (minimum participation)\n\n  Settings: period=7, multiplier=3 (standard NSE)\n\nEXIT conditions:\n  Primary: Supertrend direction flips from +1 to -1\n           (line moves from below price to above price)\n  Secondary: +10% profit target hit\n  Safety: -5% stop loss from entry\n  Time: 20-day maximum hold\n\nKey advantage: the Supertrend EXIT is a trailing stop\nthat automatically locks in more profit as stock rises`,
  signals:[
    {t:'buy',  s:'Supertrend flips +1 + ADX > 20 → ENTER at next day open'},
    {t:'sell', s:'Supertrend flips -1 → EXIT (trailing stop hit) at next day open'},
    {t:'sell', s:'+10% profit target reached → TAKE PROFIT'},
    {t:'watch',s:'Multiple consecutive quick flips = choppy market. Wait for ADX > 25 before next entry.'},
    {t:'note', s:'Best performance in strongly trending markets (Nifty ADX > 25). Avoid when ADX < 18.'},
  ],
  tip:'Run the Supertrend strategy on daily charts only for positional trades (3-20 days). For intraday, use 15-minute charts with the same settings. Never use 1-minute charts — too much noise.',
  combos:['ADX','Volume','Parabolic SAR'],
  chart:'supertrend_strategy',
  example:`Backtest Summary (HDFCBANK.NS, 3 years):
  
  Total trades:     41
  Winning trades:   24  (58.5%)
  Losing trades:    17  (41.5%)
  
  Average win:      +8.1%
  Average loss:     -3.8%
  Win/Loss ratio:   2.13:1
  
  Total return:     +89.3%
  Max drawdown:     -14.7%
  Sharpe ratio:     1.68
  Profit factor:    2.81
  
  Note: Supertrend strategy typically outperforms Triple
  Confirmation because it catches more of each trend move.
  Triple Confirmation exits earlier (fixed SMA stop).
  Supertrend holds until the trend actually reverses.`,
},

{
  id:'donchian-breakout-strat', cat:'strategies', tag:'built', name:'Donchian Breakout Strategy',
  short:'New N-day high with volume — momentum breakout system',
  creator:'backtester_v2.py — Strategy 6 | Based on Turtle Trading',
  python:'backtester_v2.py → strategy_donchian_breakout()',
  purpose:`The Donchian Breakout strategy is fundamentally different from all other strategies in the system. While the others look for oversold pullbacks or trend continuations, this strategy specifically targets stocks making NEW HIGHS with conviction volume.

The logic: a stock making a 20-day high just hit its highest price in a month. This is unusual — most days, the stock does NOT make new highs. When it does, and when volume confirms the move, breakout momentum often carries price significantly higher.

This is the essence of the legendary Turtle Trading system (Richard Dennis and William Eckhardt, 1983). They proved that a pure price breakout system with no other filters could generate extraordinary returns over decades. The volume requirement in our version further improves on the original.

<b>Warning:</b> This strategy has a LOWER win rate (~45%) than the others. This is normal and expected. The wins are larger because you are catching the beginning of sustained moves. Do not abandon it because it loses more often — the reward-to-risk ratio compensates.`,
  formula:`ENTRY conditions (ALL must be true):\n  1. Close > Donchian Channel Upper (new 20-day high)\n     → Stock just hit its highest price in 1 month\n  2. Volume ≥ 1.5× average\n     → Real buying, not random noise\n  3. ADX > 18\n     → Some trend developing (not purely random)\n  4. Close > SMA(50)\n     → Price in broader uptrend\n\nEXIT conditions:\n  Stop loss: Close < Donchian Lower (20-day low)\n          OR Close < SMA(50) (trend broken)\n  Take profit: +10% from entry\n  Time stop: 20 trading days\n\nKey: volume requirement eliminates ~40% of false breakouts`,
  signals:[
    {t:'buy',  s:'New 20-day high + volume ≥ 1.5× avg + ADX > 18 → BREAKOUT BUY'},
    {t:'sell', s:'New 20-day low → trend fully reversed, EXIT'},
    {t:'sell', s:'Close below SMA 50 → trend broken, EXIT'},
    {t:'note', s:'Win rate ~45% is EXPECTED. Larger winners (+10%) compensate for more losers.'},
    {t:'watch',s:'Gap up breakout + huge volume (3×+) = most powerful signal, very high success rate'},
  ],
  tip:'Never abandon this strategy after 3-4 losses. Breakout strategies inherently have lower win rates. The key metric is profit factor (gross wins / gross losses). Above 1.5 is good. Above 2.0 is excellent.',
  combos:['Volume ROC','ADX','ATR'],
  chart:'donchian_strategy',
  example:`Backtest Summary (TATAMOTORS.NS, 3 years):
  
  Total trades:     38
  Winning trades:   17  (44.7%)
  Losing trades:    21  (55.3%)
  
  Average win:      +9.4%
  Average loss:     -4.1%
  Win/Loss ratio:   2.29:1
  
  Total return:     +71.8%
  Max drawdown:     -22.6%
  Sharpe ratio:     1.31
  Profit factor:    1.85
  
  Despite 55% loss rate, the strategy is profitable because
  winners are 2.29× larger than losers. This is the Turtle
  Trading insight: being right less often but winning more
  per winning trade produces better long-term results.`,
},

{
  id:'mean-reversion', cat:'strategies', tag:'built', name:'Mean Reversion Strategy',
  short:'RSI oversold + lower BB + above SMA200 — buy the dip',
  creator:'backtester.py / backtester_v2.py — Strategy 2',
  python:'backtester_v2.py → strategy_mean_reversion()',
  purpose:`Mean reversion is based on a statistical reality: prices tend to return to their mean after extreme moves. When a stock in a healthy long-term uptrend (above SMA 200) pulls back sharply (RSI < 35, near lower Bollinger Band), it has often moved too far too fast. The rubber band will snap back.

This strategy is the opposite of breakout trading. Instead of buying new highs, you buy extreme weakness in a strong trend. This feels wrong psychologically — you are buying when a stock is falling and sentiment is negative. That psychological discomfort is precisely why the edge exists: most people can't bring themselves to buy in these moments.

<b>Key requirement:</b> The stock MUST be above its SMA 200. This is the most critical filter. Mean reversion in a downtrend is called "catching a falling knife" — extremely dangerous. The SMA 200 filter ensures you are buying weakness in an uptrend, not weakness in a downtrend.`,
  formula:`ENTRY conditions (ALL must be true):\n  1. RSI(14) < 35\n     → Oversold momentum\n  2. %B < 0.10 (price near or below lower Bollinger Band)\n     → Statistically extended low\n  3. Volume ≥ 1.5× average\n     → Capitulation volume (panic selling = opportunity)\n  4. Close > SMA(200)\n     → In long-term uptrend (NOT catching a falling knife)\n\nEXIT conditions:\n  Take profit: RSI rises above 60 (mean restored)\n  Stop loss: -5% from entry\n  Time stop: 20 trading days`,
  signals:[
    {t:'buy',  s:'RSI < 35 + %B < 0.10 + Close > SMA 200 + high vol → double oversold BUY'},
    {t:'sell', s:'RSI rises above 60 → mean restored, take profit'},
    {t:'sell', s:'-5% stop loss hit → SMA 200 may have failed, exit'},
    {t:'note', s:'The highest quality setups have RSI below 25 and %B below 0.0 (below lower band)'},
    {t:'watch',s:'High volume on the oversold day = capitulation (panic selling). This is the optimal entry.'},
  ],
  tip:'The best mean reversion entries come on days when everyone is panicking — news-driven drops, F&O expiry pressure, global sell-offs. These create temporary extreme readings on stocks that are fundamentally strong. Those are your shopping days.',
  combos:['RSI','Bollinger Bands','SMA 200','Volume'],
  chart:'mean_reversion',
  example:`Backtest Summary (BAJFINANCE.NS, 3 years):
  
  Total trades:     29
  Winning trades:   19  (65.5%)
  Losing trades:    10  (34.5%)
  
  Average win:      +6.2%
  Average loss:     -4.8%
  
  Total return:     +58.7%
  Max drawdown:     -16.4%
  Sharpe ratio:     1.55
  Profit factor:    2.31
  
  Mean Reversion has the highest win rate (65.5%) of all
  strategies because it requires extreme statistical conditions
  (double oversold + above SMA200) before triggering.
  Trade frequency is lowest — only 29 trades in 3 years.`,
},

// ── Additional indicators ──
// ── MOMENTUM (remaining) ──
{id:'cci',cat:'momentum',tag:'built',name:'CCI — Commodity Channel Index',short:'Distance from statistical mean — trend & reversal',creator:'Donald Lambert, 1980',python:'complete_indicators.py → calc_cci(df)',
purpose:`CCI measures how far the Typical Price has moved from its statistical average, expressed in units of Mean Deviation. Values beyond ±100 are statistically unusual — price is at an extreme relative to its recent history.\n\n<b>Dual personality:</b> In ranging markets, CCI oscillates between +100 and -100 — use it as an overbought/oversold tool. In trending markets, CCI stays above +100 for extended periods — treat this as trend confirmation, not a sell signal. Knowing which mode the market is in is the key skill.`,
formula:`Typical Price (TP) = (High + Low + Close) / 3\nSMA of TP over N days\nMean Deviation = avg(|TP − SMA_of_TP|) over N days\n\nCCI = (TP − SMA_of_TP) / (0.015 × Mean Deviation)\n\n0.015 chosen so ~70% of readings fall within ±100\n±100 = 1 standard deviation from mean\n±200 = extreme (only ~5% of readings)`,
signals:[{t:'buy',s:'CCI crosses above -100 (exits oversold) → pullback ending, BUY'},{t:'sell',s:'CCI crosses below +100 (exits overbought) → rally ending, SELL'},{t:'buy',s:'CCI > +100 in confirmed uptrend → breakout signal, ride it'},{t:'watch',s:'CCI divergence with price → same reversal warning as RSI divergence'}],
tip:'In strong Nifty bull markets, CCI stays above +100 for weeks. Don\'t short CCI > 100 in a bull market — that\'s a trend confirmation. Only treat it as overbought in sideways/ranging conditions.',
combos:['RSI','MACD','Bollinger Bands'],chart:'rsi',example:`CCI Example — INFY.NS:\n  Range market (Oct): CCI oscillates -150 to +120\n    CCI crosses above -100 → BUY at ₹1,782\n    CCI crosses below +100 → SELL at ₹1,841 (+3.3%)\n\n  Trend market (Nov): CCI rises above +100 and STAYS there\n    Don't sell at +100 → let it ride\n    CCI eventually falls below +100 → EXIT at ₹1,956 (+9.7%)\n  Reading the market mode correctly doubled the profit.`},

{id:'roc-ind',cat:'momentum',tag:'built',name:'ROC — Rate of Change',short:'% price change over N days — pure raw momentum',creator:'Classic technical analysis',python:'complete_indicators.py → calc_roc(prices, period=12)',
purpose:`ROC is the simplest momentum indicator possible: the percentage change from N days ago. No smoothing, no formula complexity. Pure momentum. Everything in technical analysis — MACD, RSI, TRIX — is a sophistication of this one simple idea.\n\n<b>Why use it?</b> Transparency. ROC shows exactly what happened. When ROC is +8%, the stock is 8% higher than it was N days ago. No interpretation needed. Use it to compare momentum across stocks — the stock with ROC +12% has more momentum than the one with +5%.`,
formula:`ROC = (Close[today] − Close[N days ago]) / Close[N days ago] × 100\n\nROC > 0 → price higher than N days ago (positive momentum)\nROC < 0 → price lower than N days ago (negative momentum)\n\nCommon periods:\n  ROC(12) → 12-day (2-3 week) momentum\n  ROC(25) → 1-month momentum\n  ROC(200) → ~1-year momentum (trend)\n\nZero-line crossing → momentum reversal signal`,
signals:[{t:'buy',s:'ROC crosses above zero → momentum turned positive'},{t:'sell',s:'ROC crosses below zero → momentum turned negative'},{t:'watch',s:'ROC at multi-month extreme high → possible exhaustion'},{t:'note',s:'Use ROC to rank stocks by momentum strength: buy the highest ROC, avoid the lowest'}],
tip:'ROC is in % units, making it comparable across stocks. "Which stock has more momentum: HDFC at ₹1,600 or Reliance at ₹2,800?" ROC answers this directly. MACD values are not comparable across different-priced stocks.',
combos:['MACD','PPO','TRIX'],chart:'macd',example:`ROC Momentum Ranking (Nifty 50, 1-month scan):\n  TITAN:     ROC(25) = +14.2% → strongest momentum\n  ICICIBANK: ROC(25) = +9.8%  → strong\n  HDFCBANK:  ROC(25) = +4.1%  → moderate\n  WIPRO:     ROC(25) = -1.2%  → negative momentum\n  UPL:       ROC(25) = -8.4%  → weakest\n\n  Simple rule: buy TITAN and ICICIBANK, avoid WIPRO and UPL.\n  This simple ROC ranking outperforms random stock selection.`},

{id:'williams-r',cat:'momentum',tag:'useful',name:'Williams %R',short:'Inverted Stochastic — faster overbought/oversold',creator:'Larry Williams, 1966',python:'indicators_extension.py → calc_williams_r(df, period=14)',
purpose:`Williams %R is mathematically identical to the Stochastic oscillator but inverted and with no smoothing. Scale runs from 0 to -100: 0 means the close was at the N-day HIGH (overbought), -100 means at the N-day LOW (oversold).\n\nBecause it uses no smoothing, %R reacts 1-2 bars EARLIER than Stochastic. Larry Williams used this indicator to win the 1987 World Trading Championship, turning $10,000 into $1.1 million in 12 months.`,
formula:`%R = (Highest High[N] − Close) / (Highest High[N] − Lowest Low[N]) × −100\n\nScale:\n  0    = close at N-day HIGH (maximum overbought)\n  -100 = close at N-day LOW (maximum oversold)\n  -80  = oversold threshold\n  -20  = overbought threshold\n\n%R = −(100 − Stochastic %K)\nMathematically: same information, no smoothing`,
signals:[{t:'buy',s:'%R rises above -80 (exits oversold zone) → buy signal'},{t:'sell',s:'%R falls below -20 (exits overbought zone) → sell signal'},{t:'buy',s:'Failure swing: %R hits oversold, bounces, fails to make new low → strong BUY'},{t:'note',s:'%R warns 1-2 bars before Stochastic because it has no smoothing layer'}],
tip:'Use %R to spot the setup early, then wait for Stochastic %K/%D crossover to confirm. %R warns you to watch. Stochastic tells you when to act. The combination gives better timing than either alone.',
combos:['Stochastic','RSI','CCI'],chart:'stochastic',example:`%R Timing Advantage vs Stochastic — BAJFINANCE.NS:\n  Day 14: %R = -82.4 (just entered oversold) → ALERT\n           Stochastic %K = 23.1 (not yet crossed %D)\n  Day 15: %R = -74.2 (rising from oversold) → %R BUY signal\n           Stochastic %K = 19.8 / %D = 22.4 (not yet crossed)\n  Day 16: %R = -61.3 (well above -80)\n           Stochastic %K = 24.8 crosses above %D 21.4 → CONFIRM\n\n  %R gave 2-day early warning. Entry at Day 15 (₹6,820)\n  vs Day 16 (₹6,890) = ₹70/share better entry.`},

{id:'trix-ind',cat:'momentum',tag:'adv',name:'TRIX',short:'Triple-smoothed ROC — the ultimate noise filter',creator:'Jack Hutson, 1983',python:'advanced_indicators.py → calc_trix(prices, period=15)',
purpose:`TRIX applies three layers of EMA smoothing before calculating the Rate of Change. Each layer of smoothing removes one level of market noise. By the third layer, only sustained directional momentum survives — all the short-term wiggling is eliminated.\n\n<b>The result:</b> TRIX generates fewer signals than MACD but each one is significantly more reliable. If you are frustrated by MACD's false signals in choppy markets, TRIX is the solution — it simply doesn't fire during choppy conditions.`,
formula:`EMA1 = EMA(price, period)\nEMA2 = EMA(EMA1, period)\nEMA3 = EMA(EMA2, period)\n\nTRIX = (EMA3 − EMA3[yesterday]) / EMA3[yesterday] × 100\nSignal = EMA(9) of TRIX\n\nEach EMA removes one frequency of noise:\n  EMA1 → removes daily noise\n  EMA2 → removes weekly fluctuations\n  EMA3 → only monthly+ trends survive`,
signals:[{t:'buy',s:'TRIX crosses above Signal line → buy signal (reliable)'},{t:'buy',s:'TRIX crosses above zero → major long-term trend turned bullish'},{t:'sell',s:'TRIX crosses below Signal line → sell signal'},{t:'note',s:'TRIX fires 30-50% fewer signals than MACD — each one carries more weight'}],
tip:'TRIX vs MACD: MACD for active swing traders (many signals). TRIX for patient position traders (fewer, higher quality signals). Both can be right for different trading styles.',
combos:['MACD','PPO','Volume'],chart:'macd',example:`TRIX vs MACD False Signal Comparison (3-month sideways market):\n  MACD signals fired:  11 (7 false, 4 true) — 36% win rate\n  TRIX signals fired:   4 (1 false, 3 true) — 75% win rate\n\n  In sideways conditions, TRIX's triple smoothing simply\n  doesn't trigger on the short-term noise that confuses MACD.\n  The one false TRIX signal lost 2.1%. The three true signals\n  gained 4.8%, 6.2%, and 5.4% respectively.`},

// ── VOLATILITY (remaining) ──
{id:'keltner',cat:'volatility',tag:'built',name:'Keltner Channels',short:'EMA ± 2×ATR — the squeeze partner for Bollinger Bands',creator:'Chester Keltner / Linda Bradford Raschke',python:'complete_indicators.py → calc_keltner(df)',
purpose:`Keltner Channels use ATR (actual volatility including gaps) for band width instead of standard deviation. This makes them more stable than Bollinger Bands during volatile spikes.\n\n<b>The primary use in v3 screener:</b> detecting the BB+KC Squeeze. When Bollinger Bands are INSIDE Keltner Channels, both volatility measures agree the market is maximally compressed. This creates the most explosive breakout setups — the market has coiled tightly and the eventual release is powerful.`,
formula:`Middle = EMA(Close, 20)\nUpper  = EMA(20) + 2 × ATR(10)\nLower  = EMA(20) − 2 × ATR(10)\n\nSqueeze detection:\n  BB_width = BB_Upper − BB_Lower\n  KC_width = KC_Upper − KC_Lower\n  Squeeze  = BB_width < KC_width\n  (Both compressed simultaneously = maximum compression)\n\nRelease: BB expands beyond KC → breakout in progress`,
signals:[{t:'watch',s:'BB inside KC (squeeze ON) → coiling for explosive move, no position yet'},{t:'buy',s:'Squeeze releases + price breaks above KC upper → bullish breakout BUY'},{t:'sell',s:'Squeeze releases + price breaks below KC lower → bearish breakdown SELL'},{t:'note',s:'KC alone acts as S/R in trending markets — bounce off KC mid = trend intact'}],
tip:'Squeeze duration matters more than squeeze depth. A 3-week squeeze is far more powerful than a 3-day squeeze. The longer the coil, the bigger the spring. The v3 screener flags the squeeze with 2 weighted points.',
combos:['Bollinger Bands','Volume','ATR'],chart:'bollinger',example:`BB+KC Squeeze Breakout — ASIANPAINT.NS:\n  Dec 1-18: BB bandwidth falls from 7.8% to 2.9%\n  Dec 12:   BB enters inside KC → squeeze confirmed\n             Wait. No position.\n  Dec 19:   Price gaps up. BB expands beyond KC.\n             Volume = 3.1× average\n  BUY at ₹3,421 (next open)\n  Jan 8: Price = ₹3,748 → +9.6% in 20 days\n  The squeeze lasted 18 days → powerful release.`},

{id:'donchian-ch',cat:'volatility',tag:'built',name:'Donchian Channels',short:'N-day highest high / lowest low — pure breakout channel',creator:'Richard Donchian — Father of Trend Following',python:'complete_indicators.py → calc_donchian(df, period=20)',
purpose:`Donchian Channels are the simplest possible channel: the highest high and lowest low over N days. There is no smoothing, no formula complexity. When price touches the upper channel, it just made a new N-day high. That's it.\n\nRichard Donchian used this in the 1960s-70s. The famous Turtle Traders (Richard Dennis, 1983) built an entire trading empire on 20-day and 55-day Donchian breakouts. If price can reach its highest level in 20 days, momentum is strongly in that direction — ride it.`,
formula:`Upper  = max(High, last N days)\nLower  = min(Low,  last N days)\nMiddle = (Upper + Lower) / 2\n\nN = 20 → 1-month breakout (used in screener v3)\nN = 55 → Turtle system entry\nN = 10 → Turtle system exit (faster)\n\nBreakout rule: Close > Upper AND Volume > 1.5× average\n→ Valid momentum breakout (volume confirms the move)`,
signals:[{t:'buy',s:'Close > Donchian Upper + volume > 1.5× avg → breakout BUY'},{t:'sell',s:'Close < Donchian Lower + high volume → breakdown SELL/EXIT'},{t:'note',s:'Middle channel = dynamic S/R: support in uptrend, resistance in downtrend'},{t:'watch',s:'Low-volume breakout → 40% fail rate. ALWAYS require volume confirmation.'}],
tip:'False breakout filter: if price makes a new 20-day high but volume is below average, wait 1-2 days for volume to confirm. Most false breakouts reverse within 48 hours. Real breakouts have instant volume.',
combos:['Volume ROC','ADX','ATR'],chart:'bollinger',example:`Donchian Breakout — TATAMOTORS.NS:\n  20-day high: ₹872 (from 20 days ago)\n  Today: Close = ₹878 → new 20-day high ✓\n  Volume: 4.2 crore shares vs 20-day avg 2.1 crore = 2.0× ✓\n  ADX: 27.4 > 20 ✓\n\n  BUY at ₹880 (next open)\n  Stop: Donchian Lower = ₹821 (-6.7%)\n  Target: +10% = ₹968\n\n  Result (22 days later): ₹944 → hit time stop\n  P&L: +7.3% in 22 days`},

{id:'hv',cat:'volatility',tag:'useful',name:'Historical Volatility',short:'Annualised std dev of log returns — options input',creator:'Statistical finance',python:'advanced_indicators.py → calc_hma (HV not separately named)',
purpose:`Historical Volatility (HV) measures how much a stock has actually moved, expressed as an annualised percentage. HV = 25% means the stock's returns have had a standard deviation equivalent to ±25% per year. One daily standard deviation = 25% / √252 = ±1.57%.\n\n<b>Primary use for options traders:</b> Compare HV to Implied Volatility (IV). If IV >> HV, options are expensive — consider selling options. If IV << HV, options are cheap — consider buying options. This comparison is the foundation of options pricing strategy.`,
formula:`Daily Log Return = ln(Close[today] / Close[yesterday])\n\nHV(N) = StdDev(N daily log returns) × √252 × 100\n\n√252 = annualisation factor (252 trading days/year)\nLog returns used instead of % returns for mathematical\ncorrectness when compounding over many periods.\n\nInterpretation:\n  HV = 15%  → low vol (stable large cap)\n  HV = 25%  → typical NSE large cap\n  HV = 50%  → high vol (small/midcap or event risk)\n  HV = 100%+ → extreme (stressed stock)`,
signals:[{t:'note',s:'HV rising sharply → volatility expanding (trending or panicking)'},{t:'note',s:'HV at multi-month lows → quiet market, likely to explode (pairs with BB squeeze)'},{t:'watch',s:'HV << Implied Vol → options overpriced → consider selling puts/calls'},{t:'watch',s:'HV >> Implied Vol → options cheap → consider buying for upcoming catalyst'}],
tip:'HV and ATR measure different things: ATR measures daily HIGH-LOW range including gaps. HV measures CLOSE-to-CLOSE statistical volatility. Use ATR for stop placement. Use HV for options pricing and academic risk models.',
combos:['ATR','Bollinger Bands','Ulcer Index'],chart:'atr',example:`HV vs ATR — WIPRO.NS:\n  ATR(14) = ₹14.2  (average daily range including gaps)\n  HV(20)  = 28.4%  (annualised close-to-close volatility)\n\n  Daily 1-sigma move from HV: 28.4% / √252 = ±1.79%\n  On ₹485 stock: ±₹8.67 expected daily move (1 sigma)\n\n  ATR says: ₹14.2 range including gaps → use ₹14.2×2 = ₹28.4 stop\n  HV says: 28.4% annual vol → position size = Risk / (28.4%/√252 × Price)\n\n  For Rs 2,000 risk: 2000 / (0.284/√252 × 485) = 26 shares`},

{id:'ulcer',cat:'volatility',tag:'adv',name:'Ulcer Index',short:'Downside-only drawdown risk — the real pain measure',creator:'Peter Martin & Byron McCann, 1987',python:'advanced_indicators.py → calc_ulcer_index()',
purpose:`Standard deviation and ATR treat upside and downside volatility equally. But only downside moves cause actual pain — no investor ever complained that their stock went up too much.\n\nUlcer Index measures ONLY drawdowns from recent peaks — the kind of sustained losses that cause anxiety, panic selling, and sleepless nights. The Martin Ratio (return / Ulcer Index) is the Ulcer-adjusted Sharpe Ratio — it tells you how much return you earned per unit of drawdown stress.`,
formula:`For each day:\n  % Drawdown = (Price − max(Price, last N days)) / max × 100\n  (always ≤ 0 — measures loss from recent peak)\n\nUlcer Index = √(Average of squared % drawdowns over N days)\n\nMartin Ratio = Annualised Return / Avg Ulcer Index\n\nUI interpretation:\n  < 5%  → low stress — comfortable to hold\n  5-10% → moderate — manageable\n  10-20% → high — stressful\n  > 20%  → severe — risk of panic selling`,
signals:[{t:'note',s:'UI < 5% → smooth ride, can hold larger position with confidence'},{t:'note',s:'UI 5-10% → moderate drawdowns, use normal position sizing'},{t:'watch',s:'UI > 15% → uncomfortable drawdowns, reduce position size'},{t:'note',s:'Martin Ratio > 3.0 → excellent return-to-drawdown ratio'}],
tip:'Use Ulcer Index to choose between two similar setups: if both have the same expected return, pick the one with lower UI. You get the same profit with far less psychological suffering — and less chance of panic-selling at the wrong moment.',
combos:['HV','ATR','Sharpe','Max Drawdown'],chart:'atr',example:`Ulcer Index Comparison — Three Stocks, Same Period:\n\n  Stock A (HDFCBANK): Return +18%, UI = 4.2% → Martin = 4.29\n  Stock B (TATASTEEL): Return +22%, UI = 14.8% → Martin = 1.49\n  Stock C (TITAN): Return +20%, UI = 6.1% → Martin = 3.28\n\n  Despite Stock B having highest return, it caused 3× more\n  drawdown stress. Stock A has best Martin Ratio — best\n  return-per-unit-of-pain. Most traders would panic-sell\n  Stock B during its 15% drawdown and miss the recovery.`},

// ── VOLUME (remaining) ──
{id:'obv',cat:'volume',tag:'built',name:'OBV — On Balance Volume',short:'Cumulative buying vs selling pressure since inception',creator:'Joe Granville, 1963',python:'complete_indicators.py → calc_obv()',
purpose:`OBV adds volume on up days and subtracts on down days cumulatively. The absolute value of OBV is meaningless — what matters is its TREND. Rising OBV = more volume on up days = net buying pressure = smart money accumulating.\n\n<b>The legendary signal:</b> OBV divergence. When price is making new highs but OBV is flat or falling, it means the price rises are happening on declining volume — the rally is not supported by real buying. Institutions are SELLING into the retail enthusiasm. This divergence preceded every major market top.`,
formula:`If Close > Close[yesterday]: OBV = OBV[prev] + Volume\nIf Close < Close[yesterday]: OBV = OBV[prev] − Volume\nIf Close = Close[yesterday]: OBV = OBV[prev]\n\nKey: OBV absolute value means nothing.\nWatch the TREND of OBV:\n  OBV 10-day trend rising → net accumulation\n  OBV 10-day trend falling → net distribution\n\nDivergence: OBV direction ≠ Price direction\n  → Major reversal warning (very reliable)`,
signals:[{t:'buy',s:'OBV rising while price also rising → confirmed uptrend, real buying'},{t:'sell',s:'OBV falling while price rising → distribution divergence → sell before crowd'},{t:'buy',s:'OBV making new highs before price does → institutional accumulation, breakout coming'},{t:'watch',s:'OBV 10-day slope = quick daily check of smart money direction'}],
tip:'OBV divergence is one of the most reliable signals in all of technical analysis. If OBV falls while price rises, institutions are selling into retail buying. This ends in a sharp correction. Act before the herd notices.',
combos:['CMF','MFI','Volume MA'],chart:'macd',example:`OBV Divergence Warning — NIFTY 50 (2024 example):\n  Week 1-4: Nifty rises from 21,200 to 22,400 (+5.7%)\n            OBV: rises from 850M to 920M (+8.2%) → CONFIRMS rally\n  Week 5-8: Nifty rises from 22,400 to 23,100 (+3.1%)\n            OBV: FALLS from 920M to 880M (-4.3%) → DIVERGENCE\n\n  Price making new highs, OBV making lower highs.\n  Institutions distributing at the top.\n  4 weeks later: Nifty corrects to 21,800 (-5.6%)\n  OBV warned in advance.`},

{id:'vwap',cat:'volume',tag:'built',name:'VWAP',short:'Volume Weighted Average Price — institutional benchmark',creator:'Institutional trading standard, 1980s',python:'complete_indicators.py → calc_vwap()',
purpose:`VWAP is the average price at which all volume traded during the day. Every institutional fund manager measures execution quality against VWAP: buying below VWAP = good execution (you paid less than average), buying above = poor execution (you overpaid).\n\nThis makes VWAP a self-fulfilling level: because institutions use it as a benchmark, they place more orders near it, making it act as strong intraday support and resistance. On NSE, VWAP is the most watched intraday level — more than any pivot or technical indicator.`,
formula:`Typical Price (TP) = (High + Low + Close) / 3\n\nVWAP = Σ(TP × Volume for each trade) / Σ(Volume)\n\nVWAP resets at 9:15 AM every trading day.\nFor multi-day charts: use Rolling VWAP(20)\n\nBias rule:\n  Price > VWAP → more money traded above average → bullish\n  Price < VWAP → more money traded below average → bearish\n  Price at VWAP → fair value, battle zone`,
signals:[{t:'buy',s:'Price above VWAP → bullish intraday bias, buy dips to VWAP level'},{t:'sell',s:'Price below VWAP → bearish intraday bias, sell rallies to VWAP level'},{t:'buy',s:'Price reclaims VWAP from below → intraday sentiment may have shifted'},{t:'note',s:'Opening price vs VWAP by 10 AM is the most powerful intraday directional signal'}],
tip:'For intraday trading: check price vs VWAP at 9:30 AM (15 min after open). If price is above VWAP and rising, the bias is bullish for the entire day. If below and falling, bearish. This one check guides 80% of intraday decisions.',
combos:['Pivot Points','Supertrend','Volume MA'],chart:'macd',example:`VWAP Intraday Playbook — ICICIBANK.NS:\n\n  9:15 AM open: ₹1,181. VWAP starts at ₹1,181.\n  9:30 AM: Price ₹1,186, VWAP ₹1,183 → Price above VWAP\n    → Bullish bias established. Only take buy setups.\n  10:15 AM: Pullback to VWAP at ₹1,184\n    → Buy dip to VWAP. Entry ₹1,184.\n  1:30 PM: Price ₹1,198, VWAP ₹1,187 → hold\n  3:15 PM: Price ₹1,194, VWAP ₹1,189 → still above, hold to close\n  3:30 PM close: ₹1,192 → P&L: +₹8/share (+0.67%) in one day`},

{id:'mfi-ind',cat:'volume',tag:'built',name:'MFI — Money Flow Index',short:'Volume-weighted RSI — stronger overbought/oversold',creator:'Gene Quong & Avrum Soudack',python:'complete_indicators.py → calc_mfi(df)',
purpose:`MFI is RSI with volume added. Instead of comparing gains and losses by price alone, MFI weights each period by the money (price × volume) that traded. A 2% up move on 10 crore shares carries far more weight than the same 2% move on 10 lakh shares.\n\n<b>The key insight:</b> volume-backed overbought/oversold readings are significantly more reliable than price-only RSI readings. MFI > 80 means not only that price is high, but that massive volume supported the rise — real money drove it there. The exhaustion signal is more meaningful.`,
formula:`Typical Price (TP) = (High + Low + Close) / 3\nRaw Money Flow = TP × Volume\n\nPositive MF = sum of Raw MF on days TP > TP[prev]\nNegative MF = sum of Raw MF on days TP ≤ TP[prev]\n\nMF Ratio = Positive MF / Negative MF\nMFI = 100 − (100 / (1 + MF Ratio))\n\nSame formula as RSI but uses money flow not price\nOverbought: > 80 | Oversold: < 20`,
signals:[{t:'buy',s:'MFI crosses above 20 (exits oversold) → volume-confirmed bounce, BUY'},{t:'sell',s:'MFI crosses below 80 (exits overbought) → volume-confirmed top, SELL'},{t:'buy',s:'Bullish divergence: price lower low + MFI higher low → double confirmation'},{t:'note',s:'MFI > 80 on high volume → stronger sell than RSI > 70 (volume confirms the exhaustion)'}],
tip:'Combine MFI with RSI: if both are simultaneously oversold (MFI < 20 AND RSI < 30), you have volume AND price confirmation — the strongest double oversold signal possible on any chart.',
combos:['RSI','OBV','CMF'],chart:'rsi',example:`MFI vs RSI Signal Quality Comparison:\n\n  Nov 8: RSI = 68 (approaching overbought)\n         MFI = 72 (NOT overbought yet — low volume)\n         → RSI signal is noise. Volume doesn't confirm.\n         → Skip the sell signal.\n\n  Nov 22: RSI = 72 (overbought)\n           MFI = 84 (overbought on HIGH volume)\n           → Both confirm. This is a REAL overbought signal.\n           → Sell ₹2,641. Stock fell to ₹2,498 over next 8 days.\n\n  Nov 8 false signal (MFI filtered out) saved a bad trade.\n  Nov 22 true signal (both confirm) caught a real reversal.`},

{id:'cmf',cat:'volume',tag:'useful',name:'Chaikin Money Flow',short:'Accumulation vs distribution — close position in range',creator:'Marc Chaikin',python:'indicators_extension.py → calc_cmf(df)',
purpose:`CMF measures where the closing price sits within each day's High-Low range, weighted by volume. Close at the High = all volume counts as buying (multiplier = +1). Close at the Low = all volume counts as selling (multiplier = -1). Close in the middle = net zero.\n\nThis is more nuanced than OBV which just asks "was it an up day or down day?" CMF asks "how convincingly did buyers or sellers win today?" A day that closes near the low — even if it closed fractionally higher — shows sellers had control all day.`,
formula:`MF Multiplier = (2×Close − High − Low) / (High − Low)\n  Range: −1 to +1\n  +1 = close at day's HIGH (maximum buying)\n  0  = close at midpoint (neither side)\n  −1 = close at day's LOW (maximum selling)\n\nMF Volume = MF Multiplier × Volume\nCMF(N) = sum(MF Volume, N) / sum(Volume, N)\n\nCMF > 0 → net accumulation\nCMF < 0 → net distribution\nCMF > +0.25 → strong institutional buying`,
signals:[{t:'buy',s:'CMF > 0 and rising → net accumulation, bullish money flow'},{t:'sell',s:'CMF < 0 and falling → net distribution, bearish money flow'},{t:'buy',s:'CMF > +0.25 → strong institutional accumulation → major buy signal'},{t:'sell',s:'CMF divergence (price rising, CMF falling) → distribution, institutions selling'}],
tip:'CMF > 0.25 combined with an RSI pullback to 35-45 is one of the cleanest "institutions buying the dip" setups. The money flow is strongly positive AND price has pulled back — perfect entry condition.',
combos:['OBV','MFI','Force Index'],chart:'macd',example:`CMF Institutional Accumulation Signal — TITAN.NS:\n  Day 1-10: Price ranging ₹3,180-3,220 (sideways)\n            CMF rising from -0.08 to +0.18\n            → Institutions accumulating quietly during the range\n  Day 11: Price breaks out to ₹3,264\n           CMF = +0.27 (strong accumulation confirmed)\n\n  The CMF told the story BEFORE the breakout:\n  smart money was building a position during the sideways phase.\n  By Day 11, the position was ready and price broke out.\n  Entry on CMF > 0.18 breakout: ₹3,225 → exit ₹3,418 (+6%)`},

{id:'force-index',cat:'volume',tag:'adv',name:'Force Index',short:'Price change × volume = raw buying/selling power',creator:'Dr Alexander Elder — Trading for a Living (1993)',python:'advanced_indicators.py → calc_force_index()',
purpose:`Force Index is the simplest volume-price combination possible: multiply the price change direction and magnitude by the volume. This gives the raw power behind each move.\n\nDr Elder uses two versions:\n<b>2-period Force Index (FI2):</b> Very sensitive. Shows the precise moment of maximum buying/selling pressure. Use for entry timing: buy when FI2 dips negative in an uptrend (brief selling moment = opportunity).\n<b>13-period Force Index (FI13):</b> Smoothed. Shows trend of buying/selling pressure. Positive = buyers consistently winning. Negative = sellers winning.`,
formula:`Raw Force = (Close[today] − Close[yesterday]) × Volume\n\nForce Index(N) = EMA(N) of Raw Force\n\n2-period FI → entry timing (very sensitive)\n13-period FI → trend confirmation (smoothed)\n\nPositive FI → buyers winning (upward pressure)\nNegative FI → sellers winning (downward pressure)\n\nElder's rule:\n  FI13 > 0 → only take BUY signals from other indicators\n  FI13 < 0 → only take SELL signals from other indicators`,
signals:[{t:'buy',s:'FI(2) dips below zero in uptrend (FI13 > 0) → brief dip, buy the weakness'},{t:'sell',s:'FI(2) spikes above zero in downtrend (FI13 < 0) → brief bounce, sell the strength'},{t:'buy',s:'FI(13) crosses above zero → buying pressure sustained, uptrend confirmed'},{t:'watch',s:'FI making new highs while price also at highs → acceleration, strong trend'}],
tip:'Elder\'s complete system: check FI(13) for direction (positive = bull side only). Then use FI(2) for timing (buy when FI2 goes negative in a bull market = momentary weakness to exploit).',
combos:['EMA','RSI','OBV'],chart:'macd',example:`Force Index Entry Timing — RELIANCE.NS:\n\n  Context: FI(13) = +48 crore (positive → bull mode)\n  Look for: FI(2) going negative (brief dip to buy)\n\n  Mar 5:  FI(2) = +24Cr (buying pressure, don't buy yet)\n  Mar 8:  FI(2) = -12Cr → GOES NEGATIVE in bull mode → BUY\n           Price = ₹2,821\n  Mar 12: FI(2) = +31Cr (buying pressure returns)\n  Mar 20: FI(13) still positive. FI(2) = -8Cr → add to position\n  Mar 28: FI(13) crosses zero → close position at ₹2,964\n  Total: +5.1% in 23 days with precise entries`},

// ── TREND STRENGTH ──
{id:'adx',cat:'strength',tag:'built',name:'ADX + DI+ / DI−',short:'Trend strength meter — the most important filter in trading',creator:'J. Welles Wilder, 1978',python:'complete_indicators.py → calc_adx(df)',
purpose:`ADX answers the single most important question in technical analysis: <b>Is there a trend worth trading?</b>\n\nADX measures trend STRENGTH — not direction. It rises when any trend (up or down) is gaining strength, and falls when the market is ranging. Combined with the Directional Indicators (+DI and -DI), it tells you both strength and direction.\n\n<b>The critical rule:</b> ADX below 20 = no trend. All trend-following indicators (EMA, MACD, Supertrend) will fail. Every false signal you've ever had from these indicators happened when ADX was below 20. Using ADX as a filter before any trend trade would eliminate most of your trading losses.`,
formula:`+DM = max(High − High[prev], 0)  if > -DM, else 0\n-DM = max(Low[prev] − Low, 0)   if > +DM, else 0\n\n+DI = 100 × Wilder_EMA(+DM, 14) / ATR\n-DI = 100 × Wilder_EMA(-DM, 14) / ATR\n\nDX  = 100 × |+DI − -DI| / (+DI + -DI)\nADX = Wilder_EMA(DX, 14)\n\nADX values:\n  < 20 → No trend. Wait.\n  20-25 → Trend developing. Watch.\n  25-35 → Strong trend. Trade.\n  35-50 → Very strong trend. Ride.\n  > 50  → Extreme trend (rare)`,
signals:[{t:'note',s:'ADX < 20 → No trend. STOP. Do not use EMA, MACD, Supertrend. They will all fail.'},{t:'buy',s:'ADX > 25 AND +DI > -DI → strong uptrend. Act on bullish signals with confidence.'},{t:'sell',s:'ADX > 25 AND -DI > +DI → strong downtrend. Only take bearish setups.'},{t:'buy',s:'+DI crosses above -DI with ADX > 25 → direction just flipped bullish → BUY'},{t:'watch',s:'ADX falling from above 40 → trend exhausting. Start taking partial profits.'}],
tip:'ADX as a filter is the single most powerful improvement you can make to any trading system. Before ANY trade, check ADX. If below 20, skip the trade entirely. This one rule improves most strategies\' win rate by 10-20 percentage points.',
combos:['Supertrend','EMA Ribbon','MACD','Donchian Channels'],chart:'rsi',example:`ADX Filter Impact — SBIN.NS (6-month test):\n\n  All MACD signals: 18 trades, 9 winners (50% win rate)\n  MACD + ADX > 20 filter: 11 trades, 8 winners (73% win rate)\n\n  7 trades eliminated by ADX filter:\n    - 1 was a true winner (missed it)\n    - 6 were losers (avoided them)\n\n  ADX filter removed 6 losers and only missed 1 winner.\n  Win rate improved from 50% to 73%.\n  This is the most powerful single improvement to any system.`},

{id:'aroon',cat:'strength',tag:'useful',name:'Aroon Indicator',short:'How recently was the N-day high/low? Detects trends early.',creator:'Tushar Chande, 1995 — Aroon means "dawn" in Sanskrit',python:'indicators_extension.py → calc_aroon(df)',
purpose:`Aroon detects the BEGINNING of new trends by measuring how recently the stock made its N-period high or low. In a strong uptrend, price regularly makes new highs — Aroon Up stays near 100. In a downtrend, Aroon Down stays near 100.\n\n<b>Speed advantage over ADX:</b> ADX is a smoothed indicator that lags by design. Aroon reacts faster because it simply checks when the last high/low occurred — no smoothing needed. When Aroon Up crosses above Aroon Down, a new uptrend is beginning. This crossover typically occurs BEFORE ADX rises above 20.`,
formula:`Aroon Up   = ((N − bars since N-period High) / N) × 100\nAroon Down = ((N − bars since N-period Low)  / N) × 100\n\nAroon Up = 100 → N-period high was TODAY (maximum bull)\nAroon Up = 0   → N-period high was N bars ago (bull exhausted)\n\nAroon Oscillator = Aroon Up − Aroon Down\n  Range: −100 to +100\n  > 0  → upward bias\n  < 0  → downward bias\n\nUsed in v3 screener: Aroon Up > 70 AND Up > Down = 2pts`,
signals:[{t:'buy',s:'Aroon Up crosses above Aroon Down → new uptrend beginning (faster than ADX signal)'},{t:'sell',s:'Aroon Down crosses above Aroon Up → new downtrend beginning'},{t:'buy',s:'Aroon Up at 100 AND Aroon Down near 0 → very strong uptrend, just made new high'},{t:'watch',s:'Both Aroon lines below 50 → consolidation/ranging market, no clear trend'}],
tip:'Use Aroon to detect trend starts, ADX to confirm trend has strength. Aroon Up crossing Aroon Down = new trend alert. Then wait for ADX to rise above 20 before committing full position size.',
combos:['ADX','Supertrend','EMA Ribbon'],chart:'rsi',example:`Aroon vs ADX Early Detection — MARUTI.NS:\n  Day 1:  Price turns up. New uptrend beginning.\n  Day 3:  Aroon Up crosses above Aroon Down → ALERT\n           ADX still = 16.8 (below 20, not yet triggering)\n  Day 7:  ADX rises to 21.2 → ADX signals trend\n           Aroon gave 4-day head start\n\n  Entry on Aroon signal (Day 3): ₹10,180\n  Entry on ADX signal (Day 7):  ₹10,360\n  Aroon entry was ₹180/share better on a ₹10,000 move.\n  4 days = 1.8% advantage from earlier detection.`},

// ── BREADTH ──
{id:'ad-line',cat:'breadth',tag:'useful',name:'Advance-Decline Line',short:'Are most stocks rising or just a handful of large caps?',creator:'Classic market breadth concept, 1920s Wall Street',python:'advanced_indicators.py → calc_advance_decline()',
purpose:`The A-D Line tracks how many stocks advance vs decline each day, cumulatively. It is the most fundamental measure of whether a market rally has broad participation or is being held up by a few large-cap stocks.\n\n<b>The single most important divergence in all of market analysis:</b> when a market index makes new all-time highs but the A-D Line is falling (or making lower highs), the rally is being driven by only a handful of stocks. When those stocks roll over, the index falls sharply with nowhere to hide.\n\nThis divergence warned months before: the 1929 crash, 1987 crash, 2000 tech bubble, 2008 financial crisis. It is slow but extremely reliable.`,
formula:`A-D Value(day) = Advancing Stocks − Declining Stocks\nA-D Line = Previous A-D Line + A-D Value (cumulative)\n\nFor Nifty 50: check all 50 stocks each day\n  Advancing: Close > Close[yesterday]\n  Declining: Close < Close[yesterday]\n\nHealthy bull market: A-D Line rising with index\nDangerous rally:    A-D Line falling while index rising\nRecovery signal:    A-D Line rising while index still falling`,
signals:[{t:'buy',s:'A-D Line rising with index → broad participation, sustainable rally'},{t:'sell',s:'A-D Line falling while index makes new highs → narrow rally, MAJOR WARNING'},{t:'buy',s:'A-D Line turning up while index still falling → recovery underway, potential bottom'},{t:'watch',s:'A-D Line peaked months before major crashes: 1929, 1987, 2000, 2008'}],
tip:'Check the weekly A-D Line once a week. If Nifty makes a new 52-week high but the A-D Line is below its previous peak, start reducing exposure. This is the early warning of a market top that few notice.',
combos:['McClellan Oscillator','New Highs/Lows'],chart:'macd',example:`A-D Divergence Warning — Illustrative:\n  Month 1: Nifty: 21,000 → 22,000 (+4.8%). A-D: +840 → confirms\n  Month 2: Nifty: 22,000 → 22,800 (+3.6%). A-D: +840 → FLAT\n    → Index rising, A-D not confirming. First warning.\n  Month 3: Nifty: 22,800 → 23,400 (+2.6%). A-D: +840 → FALLING\n    → Divergence confirmed. Only a few stocks driving index.\n  Month 4: Nifty falls 8% in 3 weeks as large caps roll over.\n\n  The A-D Line warned 2 months before the correction.`},

{id:'mcclellan',cat:'breadth',tag:'adv',name:'McClellan Oscillator',short:'Smoothed breadth momentum — short-term market turns',creator:'Sherman & Marian McClellan, 1969',python:'advanced_indicators.py → calc_mcclellan_oscillator()',
purpose:`The McClellan Oscillator is to the A-D Line what MACD is to price: it smooths the Advance-Decline data using two EMAs and shows the short-term momentum of breadth. It oscillates around zero and identifies when the broad market is overbought or oversold.\n\nThe McClellan Summation Index (running total of the oscillator) is the longer-term version — when it falls from above +1000, it has historically preceded significant market corrections in both US and Indian markets.`,
formula:`McClellan = EMA(19) of Daily A-D Value\n           − EMA(39) of Daily A-D Value\n\n(Exactly like MACD, but applied to breadth data\n instead of price data)\n\nZero line: positive = breadth momentum up\n           negative = breadth momentum down\n\nOverbought: > +100 (market breadth extended)\nOversold:   < −100 (market breadth depressed)\n\nSummation Index = cumulative sum of McClellan\n  > +1000 → strong bull participation\n  < −1000 → severe breadth damage`,
signals:[{t:'buy',s:'McClellan < -100 → market-wide oversold → broad rally likely'},{t:'sell',s:'McClellan > +100 → market-wide overbought → broad pullback likely'},{t:'buy',s:'McClellan crosses above zero → short-term breadth momentum turned positive'},{t:'watch',s:'Summation Index turns down from > +1000 → major correction warning signal'}],
tip:'Track the Summation Index monthly. When it reaches above +1000 and then turns down, it has historically been a reliable warning of corrections of 8-15%. Not a day-trading tool — use it for position sizing decisions.',
combos:['A-D Line','New Highs/Lows'],chart:'macd',example:`McClellan Oscillator Oversold Bounce:\n  Week 1: McClellan = -142 (deeply oversold breadth)\n           → Most stocks simultaneously oversold\n           → Historical bounce rate: 78% within 5 days\n  Week 2: McClellan crosses above -100 → BUY signal\n           Nifty rises 3.2% over next week\n\n  Summation Index example:\n  Aug: Summation = +1,240 (extreme bull breadth)\n  Sep: Summation turns down → WARNING\n  Oct: Summation = +680 (falling)\n  Nov: Nifty corrects -11% over 3 weeks\n  Summation warned 6 weeks before correction.`},

{id:'new-highs-lows',cat:'breadth',tag:'useful',name:'New 52-Week Highs/Lows',short:'Are stocks making new extremes? Quality check for any rally.',creator:'Classic market breadth concept',python:'advanced_indicators.py → calc_new_highs_lows()',
purpose:`New 52-week Highs and Lows count how many stocks in the index are making new yearly extremes each day. A genuine bull market has many new highs. A hollow rally has the index rising while fewer and fewer individual stocks are setting new highs.\n\n<b>The NH/NL ratio</b> (New Highs / (New Highs + New Lows)) above 70% signals broad market participation — the rally is real. Below 30% means most stocks are at yearly lows — even if the index holds up, it's on thin ice. When this ratio inverts while the index is near highs, prepare for a sharp drop.`,
formula:`New High: Close today = max(Close, last 252 trading days)\nNew Low:  Close today = min(Close, last 252 trading days)\n\nNH/NL Ratio = New Highs / (New Highs + New Lows) × 100\n\nInterpretation:\n  > 70% → broad bull market, high participation\n  50-70% → moderate participation\n  30-50% → mixed, transitional\n  < 30%  → bear market breadth\n\nKey signal: NH/NL ratio FALLING while index RISING\n→ Narrowing leadership = danger sign`,
signals:[{t:'buy',s:'NH/NL ratio > 70% → strong broad rally, increase exposure'},{t:'sell',s:'NH/NL ratio < 30% and falling → bear breadth, reduce exposure'},{t:'sell',s:'New Lows expanding while index holds near highs → distribution, SELL'},{t:'watch',s:'Monitor weekly: 5 consecutive weeks of declining NH/NL in a bull market = warning'}],
tip:'Count the absolute numbers, not just the ratio. If only 5 of 50 Nifty stocks are at new 52-week highs while the index is at new highs, those 5 stocks are doing ALL the work. When any of them stumble, the index drops instantly with no support underneath.',
combos:['A-D Line','McClellan Oscillator'],chart:'macd',example:`NH/NL Ratio Reading — Nifty 100:\n\n  Bull market peak (Jan 2024):\n    New 52-week Highs: 73 stocks\n    New 52-week Lows:  4 stocks\n    NH/NL Ratio: 73/(73+4) = 94.8% → extremely bullish\n\n  Warning phase (3 months later):\n    New 52-week Highs: 31 stocks\n    New 52-week Lows:  22 stocks\n    NH/NL Ratio: 31/(31+22) = 58.5% → declining despite index holding\n\n  Correction phase (2 months later):\n    Index fell 9%. NH/NL ratio at 58.5% warned in advance.`},

// ── PRICE LEVELS ──
{id:'pivots',cat:'levels',tag:'useful',name:'Classic Pivot Points',short:'Pre-calculated daily S/R from previous day OHLC',creator:'Floor traders, formalized mid-20th century',python:'indicators_extension.py → calc_pivot_points(df)',
purpose:`Classic daily pivots are calculated from the previous day's High, Low, and Close. They give fixed, pre-calculated support and resistance levels that are widely watched by institutional traders and algorithms. On NSE, R1, S1, R2, and S2 levels are extremely respected — many intraday moves stop exactly at these levels.\n\n<b>The self-fulfilling prophecy:</b> Because thousands of traders, algorithms, and institutions watch these exact levels, price genuinely reacts at them. The more people watch a level, the more real it becomes. Pivot points are among the most widely-watched levels in Indian markets.`,
formula:`Pivot Point (PP) = (High[prev] + Low[prev] + Close[prev]) / 3\n\nResistance:\n  R1 = 2 × PP − Low[prev]\n  R2 = PP + (High[prev] − Low[prev])\n  R3 = High[prev] + 2 × (PP − Low[prev])\n\nSupport:\n  S1 = 2 × PP − High[prev]\n  S2 = PP − (High[prev] − Low[prev])\n  S3 = Low[prev] − 2 × (High[prev] − PP)\n\nCalibrate night before market opens.`,
signals:[{t:'buy',s:'Open above PP + early volume → bullish day, target R1 then R2'},{t:'sell',s:'Open below PP + early volume → bearish day, target S1 then S2'},{t:'buy',s:'Price bounces from S1 with volume → strong support holding, add to position'},{t:'watch',s:'Price at R1 or S1 with strong momentum → likely to break through to R2/S2'}],
tip:'Calculate pivots the night before. Know PP, R1, S1, R2, S2 for every stock on your watchlist before 9:15 AM. The first 15 minutes often determines which side of PP the stock spends the entire day.',
combos:['Camarilla Pivots','VWAP','Stochastic'],chart:'bollinger',example:`Pivot Trading — HDFCBANK.NS:\n  Previous day: H=₹1,668, L=₹1,632, C=₹1,659\n  PP  = (1668+1632+1659)/3 = ₹1,653.0\n  R1  = 2×1653 − 1632 = ₹1,674.0\n  R2  = 1653 + (1668-1632) = ₹1,689.0\n  S1  = 2×1653 − 1668 = ₹1,638.0\n  S2  = 1653 − (1668-1632) = ₹1,617.0\n\n  9:30 AM: Open ₹1,655 → above PP → bullish bias\n  10:45 AM: Pullback to ₹1,652 (near PP) + small bounce\n    → Buy ₹1,653, target R1 ₹1,674, stop ₹1,642\n  1:30 PM: ₹1,672 → near R1, take partial profit\n  3:00 PM: Close ₹1,678 → R1 broken, held through = +₹25 (1.5%)`},

{id:'camarilla',cat:'levels',tag:'useful',name:'Camarilla Pivots',short:'Tighter intraday levels for mean reversion scalping',creator:'Nick Scott, 1989',python:'indicators_extension.py → calc_camarilla_pivots(df)',
purpose:`Camarilla pivots are much tighter than classic pivots, all anchored to the PREVIOUS CLOSE rather than the pivot point. This makes them ideal for intraday mean reversion: when price reaches H4 or L4, it is statistically likely to reverse.\n\n<b>The key rule that makes Camarilla unique:</b> if price CLOSES beyond H4 or L4, the mean reversion thesis is invalid and you should trade WITH the breakout instead. A close above H4 turns H4 from resistance into support — it's now a trend day.`,
formula:`Range = Previous High − Previous Low\n\nH4 = Prev Close + Range × (1.1/2)  ← sell zone\nH3 = Prev Close + Range × (1.1/4)  ← resistance\nH1 = Prev Close + Range × (1.1/12)\nL1 = Prev Close − Range × (1.1/12)\nL3 = Prev Close − Range × (1.1/4)  ← support\nL4 = Prev Close − Range × (1.1/2)  ← buy zone\n\nNote: 1.1 multiplier was empirically derived by Nick Scott\nfrom years of floor trading data`,
signals:[{t:'buy',s:'Price hits L4 → buy for mean reversion. Target: L3 or H1. Stop: below L3.'},{t:'sell',s:'Price hits H4 → sell for mean reversion. Target: H3 or L1. Stop: above H3.'},{t:'buy',s:'Price CLOSES above H4 → breakout. Switch from mean reversion to trend mode.'},{t:'sell',s:'Price CLOSES below L4 → breakdown. Trade WITH the move, not against it.'}],
tip:'The CLOSE rule is the most important: never average down at L4 if price closes below it. A close below L4 means the stock wants to trend lower, not mean revert. Camarilla levels are only for mean reversion — not breakouts.',
combos:['Classic Pivots','VWAP','Stochastic'],chart:'bollinger',example:`Camarilla Scalping — BAJAJ-AUTO.NS:\n  Prev: H=₹8,820, L=₹8,680, C=₹8,790\n  Range = ₹140\n  H4 = 8790 + 140×(1.1/2) = ₹8,867  (sell zone)\n  H3 = 8790 + 140×(1.1/4) = ₹8,828\n  L3 = 8790 − 140×(1.1/4) = ₹8,752\n  L4 = 8790 − 140×(1.1/2) = ₹8,713  (buy zone)\n\n  10:30 AM: Price ₹8,718 → hit L4 zone → BUY ₹8,718\n  Stop: ₹8,700 (below L4). Target: L3 ₹8,752 or H1.\n  11:45 AM: Price ₹8,756 (above L3) → exit ₹8,752\n  P&L: +₹34/share (+0.39%) in 75 minutes`},

{id:'fibonacci',cat:'levels',tag:'useful',name:'Fibonacci Retracements & Extensions',short:'Golden ratio levels — where price pauses and reverses',creator:'Applied to markets by R.N. Elliott, early 1900s',python:'indicators_extension.py → auto_fibonacci(df)',
purpose:`Fibonacci levels are based on the Golden Ratio (0.618) — a ratio that appears throughout nature, art, and architecture. Applied to financial markets, they mark where price tends to pause or reverse after a significant move.\n\n<b>Why do they work?</b> Partly mathematics, mostly self-fulfilling. Millions of traders globally watch the same Fibonacci levels. When price approaches 61.8%, buyers and sellers both react to it — creating the very support/resistance it predicts. The more people believe in a level, the more real it becomes.\n\n<b>The 61.8% retracement</b> (Golden Ratio) is the most important. A pullback to 61.8% in an uptrend is considered the deepest valid retracement — below 78.6% suggests the trend may have fully reversed.`,
formula:`Draw from Swing Low (SL) to Swing High (SH) in uptrend:\n  Range = SH − SL\n\nRetracement levels (pullback support):\n  23.6% = SH − Range × 0.236  (shallow pullback)\n  38.2% = SH − Range × 0.382  (moderate pullback)\n  50.0% = SH − Range × 0.500  (not Fibonacci, but watched)\n  61.8% = SH − Range × 0.618  ← Golden Ratio (most important)\n  78.6% = SH − Range × 0.786  (deep pullback)\n\nExtension targets (after breakout above SH):\n  127.2% = SL + Range × 1.272\n  161.8% = SL + Range × 1.618  ← most common target\n  261.8% = SL + Range × 2.618`,
signals:[{t:'buy',s:'Price pulls back to 38.2% or 61.8% + bullish candle pattern → buy the retracement'},{t:'buy',s:'Hammer at 61.8% + RSI oversold + high volume → triple confirmation'},{t:'watch',s:'After pullback, target 127.2% extension, then 161.8%'},{t:'note',s:'Below 78.6% retracement = likely full reversal, not just a pullback'}],
tip:'Most powerful Fibonacci entry: price pulls back to 61.8% AND a bullish candlestick forms (Hammer, Morning Star, Bullish Engulfing) AND RSI is oversold. Three independent signals all pointing to the same level = very high probability bounce.',
combos:['Pivot Points','RSI','Candlestick Patterns'],chart:'bollinger',example:`Fibonacci Trade — TITAN.NS:\n  Swing Low (Nov): ₹3,120\n  Swing High (Jan): ₹3,580\n  Range: ₹460\n\n  Retracement levels:\n  38.2% = ₹3,580 − ₹460×0.382 = ₹3,404\n  61.8% = ₹3,580 − ₹460×0.618 = ₹3,296  ← key level\n  78.6% = ₹3,580 − ₹460×0.786 = ₹3,218\n\n  Feb 10: Price pulls back to ₹3,302 (near 61.8% = ₹3,296)\n           RSI = 34 (oversold) ✓\n           Hammer candle ✓\n  Feb 11: BUY ₹3,310 (confirmation)\n\n  Target 1: Swing High ₹3,580 (+8.2%)\n  Target 2: 127.2% extension ₹3,705 (+11.9%)\n  Target 3: 161.8% extension ₹3,844 (+16.1%)\n  Actual exit: ₹3,698 (+11.7%) in 6 weeks`},

// ── Volume, Volatility, Strength, Breadth, Levels ──
// ── MOMENTUM (remaining) ──

];
