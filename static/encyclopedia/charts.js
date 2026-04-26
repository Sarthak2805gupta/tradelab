// charts.js — Chart generation for each indicator modal
// Uses Chart.js 4.x

Chart.defaults.color = '#a0a8c0';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'DM Sans', sans-serif";
Chart.defaults.font.size = 11;

// ── Colour palette ──────────────────────────────────────────
const C = {
  green:  '#3dd68c', blue:  '#60a5fa', amber: '#f59e0b',
  purple: '#a78bfa', red:   '#f87171', teal:  '#34d399',
  orange: '#fb923c', pink:  '#e879f9', sky:   '#38bdf8',
  muted:  '#606880', grid:  'rgba(255,255,255,0.05)',
};

// ── Shared chart options ────────────────────────────────────
function baseOpts(yLabel='', xLabel='Day') {
  return {
    responsive: true, maintainAspectRatio: false,
    animation: { duration: 600, easing: 'easeOutQuart' },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#1f2435', borderColor: 'rgba(255,255,255,0.12)', borderWidth: 1, padding: 8, titleFont: { size: 11 }, bodyFont: { size: 11 } },
    },
    scales: {
      x: { grid: { color: C.grid }, ticks: { maxTicksLimit: 8 }, title: { display: !!xLabel, text: xLabel, font: { size: 10 }, color: C.muted } },
      y: { grid: { color: C.grid }, title: { display: !!yLabel, text: yLabel, font: { size: 10 }, color: C.muted } },
    },
  };
}

// ── Generate simulated price data ──────────────────────────
function genPrice(n=60, start=1000, trend=0.003, noise=0.015, seed=42) {
  let r = seed, price = start, data = [];
  for (let i=0; i<n; i++) {
    r = (r * 1664525 + 1013904223) & 0xffffffff;
    const rnd = ((r >>> 0) / 0xffffffff) - 0.5;
    price *= (1 + trend + noise * rnd);
    data.push(Math.round(price * 100) / 100);
  }
  return data;
}

// ── SMA calculation ────────────────────────────────────────
function sma(data, period) {
  return data.map((_, i) => {
    if (i < period-1) return null;
    return data.slice(i-period+1, i+1).reduce((a,b) => a+b, 0) / period;
  });
}

// ── EMA calculation ────────────────────────────────────────
function ema(data, period) {
  const k = 2/(period+1);
  let result = [];
  data.forEach((v, i) => {
    if (i === 0) { result.push(v); return; }
    result.push(v * k + result[i-1] * (1-k));
  });
  return result;
}

// ── RSI calculation ────────────────────────────────────────
function calcRSI(prices, period=14) {
  const result = [];
  for (let i=0; i<prices.length; i++) {
    if (i < period) { result.push(null); continue; }
    let gains=0, losses=0;
    for (let j=i-period+1; j<=i; j++) {
      const d = prices[j] - prices[j-1];
      if (d > 0) gains += d; else losses -= d;
    }
    const rs = gains/losses || 0;
    result.push(100 - 100/(1+rs));
  }
  return result;
}

// ── MACD calculation ───────────────────────────────────────
function calcMACD(prices) {
  const fast = ema(prices, 12), slow = ema(prices, 26);
  const line = fast.map((f,i) => f - slow[i]);
  const signal = ema(line, 9);
  const hist = line.map((l,i) => l - signal[i]);
  return { line, signal, hist };
}

// ── Bollinger Bands ────────────────────────────────────────
function calcBB(prices, period=20) {
  const mid = sma(prices, period);
  const upper = [], lower = [], bandwidth = [];
  prices.forEach((_, i) => {
    if (i < period-1) { upper.push(null); lower.push(null); bandwidth.push(null); return; }
    const slice = prices.slice(i-period+1, i+1);
    const mean = mid[i];
    const std = Math.sqrt(slice.reduce((s,v) => s+(v-mean)**2, 0)/period);
    upper.push(mean + 2*std);
    lower.push(mean - 2*std);
    bandwidth.push(((mean + 2*std) - (mean - 2*std)) / mean * 100);
  });
  return { mid, upper, lower, bandwidth };
}

// ── Labels ─────────────────────────────────────────────────
function dayLabels(n) { return Array.from({length:n}, (_,i) => `Day ${i+1}`); }

// ══════════════════════════════════════════════════════════
// CHART RENDERERS — one per indicator ID
// ══════════════════════════════════════════════════════════

const CHART_RENDERERS = {

  sma_ema: (container) => {
    const prices = genPrice(60, 2600, 0.004, 0.012, 1);
    const labels = dayLabels(60);
    const s20 = sma(prices, 20), s50 = sma(prices, 50);
    const e20 = ema(prices, 20);

    const html = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Price + SMA 20, 50 and EMA 20</div>
          <div class="chart-wrap"><canvas id="c-sma1"></canvas></div>
          <div class="chart-note">EMA responds faster to price changes than SMA</div>
        </div>
        <div class="chart-container">
          <div class="chart-title">Lag comparison — SMA vs EMA on same period</div>
          <div class="chart-wrap"><canvas id="c-sma2"></canvas></div>
          <div class="chart-note">EMA turns earlier than SMA when price reverses</div>
        </div>
      </div>`;
    container.innerHTML = html;

    new Chart(document.getElementById('c-sma1'), {
      type:'line', data:{ labels,
        datasets:[
          { label:'Price',  data:prices, borderColor:C.teal, borderWidth:1.5, pointRadius:0, tension:0.2 },
          { label:'SMA 20', data:s20,   borderColor:C.blue, borderWidth:1.5, pointRadius:0, borderDash:[4,2] },
          { label:'SMA 50', data:s50,   borderColor:C.orange, borderWidth:1.5, pointRadius:0, borderDash:[6,3] },
          { label:'EMA 20', data:e20,   borderColor:C.green, borderWidth:1.5, pointRadius:0 },
        ]},
      options:{ ...baseOpts('Price (₹)'), plugins:{ legend:{ display:true, position:'top', labels:{ boxWidth:12, font:{size:10} }} } }
    });

    const gapSMA = prices.map((p, i) => s20[i] ? Math.abs(p - s20[i]) : null);
    const gapEMA = prices.map((p, i) => Math.abs(p - e20[i]));
    new Chart(document.getElementById('c-sma2'), {
      type:'line', data:{ labels,
        datasets:[
          { label:'|Price − SMA20|', data:gapSMA, borderColor:C.blue, borderWidth:1.5, pointRadius:0, fill:true, backgroundColor:'rgba(96,165,250,0.1)' },
          { label:'|Price − EMA20|', data:gapEMA, borderColor:C.green, borderWidth:1.5, pointRadius:0, fill:true, backgroundColor:'rgba(61,214,140,0.1)' },
        ]},
      options:{ ...baseOpts('Distance from price'), plugins:{ legend:{ display:true, position:'top', labels:{ boxWidth:12, font:{size:10} }} } }
    });
  },

  supertrend: (container) => {
    const prices = genPrice(60, 1600, 0.003, 0.014, 7);
    const labels = dayLabels(60);
    const atr = prices.map((_, i) => {
      if (i === 0) return 20;
      return Math.abs(prices[i] - prices[i-1]) * 7 + 15;
    });
    const stLine = prices.map((p, i) => {
      const dir = p > (prices[i-1] || p) ? 1 : -1;
      return dir === 1 ? p - 3*atr[i] : p + 3*atr[i];
    });
    const bullish = stLine.map((s, i) => prices[i] > s ? s : null);
    const bearish = stLine.map((s, i) => prices[i] <= s ? s : null);

    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Supertrend — green line below price (uptrend), red line above price (downtrend)</div>
        <div class="chart-wrap tall"><canvas id="c-st1"></canvas></div>
        <div class="chart-note">When line flips sides → buy or sell signal. Line = your trailing stop loss.</div>
      </div>`;

    new Chart(document.getElementById('c-st1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:2, pointRadius:0, tension:0.2 },
        { label:'Supertrend (bull)', data:bullish, borderColor:C.green, borderWidth:2, pointRadius:0, spanGaps:false },
        { label:'Supertrend (bear)', data:bearish, borderColor:C.red, borderWidth:2, pointRadius:0, spanGaps:false },
      ]},
      options:{ ...baseOpts('Price (₹)'), plugins:{ legend:{ display:true, position:'top', labels:{ boxWidth:12, font:{size:10} }} } }
    });
  },

  rsi: (container) => {
    const prices = genPrice(80, 1000, 0.002, 0.018, 3);
    const labels = dayLabels(80);
    const rsiData = calcRSI(prices);

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Price movement</div>
          <div class="chart-wrap"><canvas id="c-rsi1"></canvas></div>
        </div>
        <div class="chart-container">
          <div class="chart-title">RSI (14) — overbought/oversold zones</div>
          <div class="chart-wrap"><canvas id="c-rsi2"></canvas></div>
          <div class="chart-note">RSI below 30 = oversold. Above 70 = overbought. Divergence = early reversal warning.</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-rsi1'), {
      type:'line', data:{ labels, datasets:[{ data:prices, borderColor:C.blue, borderWidth:1.5, pointRadius:0, tension:0.2 }] },
      options: baseOpts('Price')
    });

    new Chart(document.getElementById('c-rsi2'), {
      type:'line', data:{ labels, datasets:[
        { data:rsiData, borderColor:C.purple, borderWidth:2, pointRadius:0, tension:0.3, fill:'origin', backgroundColor:'rgba(167,139,250,0.07)' },
        { data:Array(80).fill(70), borderColor:C.red, borderWidth:1, borderDash:[4,3], pointRadius:0 },
        { data:Array(80).fill(30), borderColor:C.green, borderWidth:1, borderDash:[4,3], pointRadius:0 },
      ]},
      options:{ ...baseOpts('RSI'), scales:{ ...baseOpts().scales, y:{ ...baseOpts().scales.y, min:0, max:100 } } }
    });
  },

  macd: (container) => {
    const prices = genPrice(80, 2600, 0.003, 0.013, 5);
    const labels = dayLabels(80);
    const { line, signal, hist } = calcMACD(prices);
    const histColors = hist.map(h => h >= 0 ? 'rgba(61,214,140,0.6)' : 'rgba(248,113,113,0.6)');

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Price</div>
          <div class="chart-wrap"><canvas id="c-macd1"></canvas></div>
        </div>
        <div class="chart-container">
          <div class="chart-title">MACD Line, Signal Line, Histogram</div>
          <div class="chart-wrap"><canvas id="c-macd2"></canvas></div>
          <div class="chart-note">Histogram growing = momentum accelerating. Shrinking = fading.</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-macd1'), {
      type:'line', data:{ labels, datasets:[{ data:prices, borderColor:C.teal, borderWidth:1.5, pointRadius:0 }]},
      options: baseOpts('Price (₹)')
    });

    new Chart(document.getElementById('c-macd2'), {
      type:'bar', data:{ labels, datasets:[
        { type:'line', label:'MACD', data:line, borderColor:C.blue, borderWidth:2, pointRadius:0, tension:0.3 },
        { type:'line', label:'Signal', data:signal, borderColor:C.orange, borderWidth:1.5, pointRadius:0, tension:0.3, borderDash:[4,2] },
        { type:'bar', label:'Histogram', data:hist, backgroundColor:histColors, barThickness:2 },
      ]},
      options:{ ...baseOpts('MACD'), plugins:{ legend:{ display:true, position:'top', labels:{ boxWidth:12, font:{size:10} }} } }
    });
  },

  bollinger: (container) => {
    const prices = genPrice(60, 3400, 0.001, 0.016, 9);
    const labels = dayLabels(60);
    const bb = calcBB(prices);

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Price with Bollinger Bands (SMA20 ± 2σ)</div>
          <div class="chart-wrap"><canvas id="c-bb1"></canvas></div>
        </div>
        <div class="chart-container">
          <div class="chart-title">Bandwidth (%) — squeeze when narrow</div>
          <div class="chart-wrap"><canvas id="c-bb2"></canvas></div>
          <div class="chart-note">When bandwidth hits multi-month lows → squeeze → big move coming</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-bb1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Upper', data:bb.upper, borderColor:'rgba(96,165,250,0.5)', borderWidth:1, pointRadius:0, fill:'+2', backgroundColor:'rgba(96,165,250,0.05)' },
        { label:'Mid',   data:bb.mid,   borderColor:C.blue, borderWidth:1.5, borderDash:[4,2], pointRadius:0 },
        { label:'Lower', data:bb.lower, borderColor:'rgba(96,165,250,0.5)', borderWidth:1, pointRadius:0 },
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:2, pointRadius:0 },
      ]},
      options:{ ...baseOpts('Price'), plugins:{ legend:{ display:false } } }
    });

    new Chart(document.getElementById('c-bb2'), {
      type:'line', data:{ labels, datasets:[
        { data:bb.bandwidth, borderColor:C.amber, borderWidth:2, pointRadius:0, fill:true, backgroundColor:'rgba(245,158,11,0.1)' }
      ]},
      options: baseOpts('Bandwidth %')
    });
  },

  stochastic: (container) => {
    const prices = genPrice(80, 1180, 0.002, 0.018, 11);
    const labels = dayLabels(80);
    const n = 14;
    const pctK = prices.map((p, i) => {
      if (i < n) return null;
      const hi = Math.max(...prices.slice(i-n, i));
      const lo = Math.min(...prices.slice(i-n, i));
      return (p - lo) / (hi - lo) * 100;
    });
    const pctD = sma(pctK.map(v => v||0), 3);

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Price</div>
          <div class="chart-wrap"><canvas id="c-sto1"></canvas></div>
        </div>
        <div class="chart-container">
          <div class="chart-title">Stochastic %K and %D</div>
          <div class="chart-wrap"><canvas id="c-sto2"></canvas></div>
          <div class="chart-note">Buy when %K crosses above %D below 20. Sell when crosses below %D above 80.</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-sto1'), {
      type:'line', data:{ labels, datasets:[{ data:prices, borderColor:C.blue, borderWidth:1.5, pointRadius:0 }]},
      options: baseOpts('Price')
    });

    new Chart(document.getElementById('c-sto2'), {
      type:'line', data:{ labels, datasets:[
        { label:'%K', data:pctK, borderColor:C.blue, borderWidth:2, pointRadius:0 },
        { label:'%D', data:pctD, borderColor:C.orange, borderWidth:1.5, borderDash:[4,2], pointRadius:0 },
        { data:Array(80).fill(80), borderColor:'rgba(248,113,113,0.4)', borderWidth:1, pointRadius:0 },
        { data:Array(80).fill(20), borderColor:'rgba(61,214,140,0.4)', borderWidth:1, pointRadius:0 },
      ]},
      options:{ ...baseOpts('Stochastic'), scales:{ ...baseOpts().scales, y:{ ...baseOpts().scales.y, min:0, max:100 } }, plugins:{ legend:{ display:true, position:'top', labels:{ boxWidth:10, font:{size:10}, filter:(i)=>i.dataIndex<2 } } } }
    });
  },

  atr: (container) => {
    const prices = genPrice(60, 485, 0.002, 0.018, 13);
    const labels = dayLabels(60);
    const trueRanges = prices.map((p, i) => i===0 ? 0 : Math.abs(p - prices[i-1]) + Math.random()*5);
    const atrData = trueRanges.map((_, i) => {
      if (i < 14) return null;
      return trueRanges.slice(i-14, i).reduce((a,b) => a+b, 0) / 14;
    });

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Stock price — WIPRO.NS example</div>
          <div class="chart-wrap"><canvas id="c-atr1"></canvas></div>
          <div class="chart-note">ATR-based stop: Entry − 2×ATR = your stop loss level</div>
        </div>
        <div class="chart-container">
          <div class="chart-title">ATR (14) — daily volatility in rupees</div>
          <div class="chart-wrap"><canvas id="c-atr2"></canvas></div>
          <div class="chart-note">ATR expands during volatile moves, contracts during quiet periods</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-atr1'), {
      type:'line', data:{ labels, datasets:[{ data:prices, borderColor:C.teal, borderWidth:1.5, pointRadius:0 }]},
      options: baseOpts('Price (₹)')
    });
    new Chart(document.getElementById('c-atr2'), {
      type:'line', data:{ labels, datasets:[{ data:atrData, borderColor:C.amber, borderWidth:2, pointRadius:0, fill:true, backgroundColor:'rgba(245,158,11,0.1)' }]},
      options: baseOpts('ATR (₹)')
    });
  },

  candlestick: (container) => {
    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Common reversal patterns — visual guide</div>
        <svg viewBox="0 0 680 220" width="100%" style="margin-top:8px">
          <defs>
            <marker id="arr2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto">
              <path d="M2 1L8 5L2 9" fill="none" stroke="#60a5fa" stroke-width="1.5"/>
            </marker>
          </defs>
          <!-- Background grid lines -->
          <line x1="20" y1="40" x2="660" y2="40" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
          <line x1="20" y1="110" x2="660" y2="110" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
          <line x1="20" y1="180" x2="660" y2="180" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>

          <!-- HAMMER -->
          <text x="80" y="20" text-anchor="middle" fill="#fbbf24" font-size="12" font-weight="500">Hammer</text>
          <text x="80" y="205" text-anchor="middle" fill="#3dd68c" font-size="10">(Bullish)</text>
          <!-- wick -->
          <line x1="80" y1="70" x2="80" y2="165" stroke="#e2e5f0" stroke-width="1.5"/>
          <!-- body (small, at top) -->
          <rect x="68" y="70" width="24" height="18" fill="#3dd68c" stroke="#3dd68c"/>
          <!-- upper wick (tiny) -->
          <line x1="80" y1="62" x2="80" y2="70" stroke="#e2e5f0" stroke-width="1.5"/>

          <!-- SHOOTING STAR -->
          <text x="180" y="20" text-anchor="middle" fill="#fbbf24" font-size="12" font-weight="500">Shooting Star</text>
          <text x="180" y="205" text-anchor="middle" fill="#f87171" font-size="10">(Bearish)</text>
          <line x1="180" y1="75" x2="180" y2="48" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="168" y="130" width="24" height="14" fill="#f87171" stroke="#f87171"/>
          <line x1="180" y1="75" x2="180" y2="144" stroke="#e2e5f0" stroke-width="1.5"/>

          <!-- BULLISH ENGULFING -->
          <text x="290" y="20" text-anchor="middle" fill="#fbbf24" font-size="12" font-weight="500">Bullish Engulfing</text>
          <text x="290" y="205" text-anchor="middle" fill="#3dd68c" font-size="10">(Bullish)</text>
          <!-- Day 1: small red -->
          <line x1="272" y1="100" x2="272" y2="155" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="262" y="110" width="20" height="28" fill="#f87171" stroke="#f87171"/>
          <!-- Day 2: large green (engulfs day 1) -->
          <line x1="300" y1="95" x2="300" y2="165" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="288" y="100" width="24" height="48" fill="#3dd68c" stroke="#3dd68c"/>

          <!-- DOJI -->
          <text x="420" y="20" text-anchor="middle" fill="#fbbf24" font-size="12" font-weight="500">Doji</text>
          <text x="420" y="205" text-anchor="middle" fill="#a0a8c0" font-size="10">(Indecision)</text>
          <line x1="420" y1="65" x2="420" y2="165" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="408" y="108" width="24" height="4" fill="#e2e5f0" stroke="#e2e5f0"/>

          <!-- MORNING STAR -->
          <text x="575" y="20" text-anchor="middle" fill="#fbbf24" font-size="12" font-weight="500">Morning Star</text>
          <text x="575" y="205" text-anchor="middle" fill="#3dd68c" font-size="10">(Bullish 3-bar)</text>
          <!-- Day 1: large red -->
          <line x1="540" y1="80" x2="540" y2="160" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="530" y="90" width="20" height="55" fill="#f87171" stroke="#f87171"/>
          <!-- Day 2: doji/small -->
          <line x1="565" y1="148" x2="565" y2="172" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="557" y="157" width="16" height="6" fill="#e2e5f0" stroke="#e2e5f0"/>
          <!-- Day 3: large green -->
          <line x1="592" y1="75" x2="592" y2="152" stroke="#e2e5f0" stroke-width="1.5"/>
          <rect x="582" y="85" width="20" height="52" fill="#3dd68c" stroke="#3dd68c"/>

          <!-- Labels -->
          <text x="80" y="190" text-anchor="middle" fill="#606880" font-size="9">Long lower wick</text>
          <text x="180" y="190" text-anchor="middle" fill="#606880" font-size="9">Long upper wick</text>
          <text x="290" y="190" text-anchor="middle" fill="#606880" font-size="9">Green engulfs red</text>
          <text x="420" y="190" text-anchor="middle" fill="#606880" font-size="9">Open ≈ Close</text>
          <text x="575" y="190" text-anchor="middle" fill="#606880" font-size="9">3-candle reversal</text>
        </svg>
        <div class="chart-note">All patterns confirmed with volume + appearing at key S/R levels = high probability setups</div>
      </div>`;
  },

  liquidity: (container) => {
    const presets = ['Small (≤50k)', 'Medium (50k-2L)', 'Large (2L-10L)', 'Institutional (10L+)'];
    const adv = [0.5, 2.0, 10.0, 50.0];
    const amihud = [0.50, 0.20, 0.05, 0.01];

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Minimum ADV requirement by trade size preset</div>
          <div class="chart-wrap"><canvas id="c-liq1"></canvas></div>
          <div class="chart-note">Larger trade → higher minimum ADV needed for safe execution</div>
        </div>
        <div class="chart-container">
          <div class="chart-title">Amihud illiquidity ratio interpretation</div>
          <div class="chart-wrap"><canvas id="c-liq2"></canvas></div>
          <div class="chart-note">Lower Amihud ratio = more liquid. Nifty 50 large caps ≈ 0.0003</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-liq1'), {
      type:'bar',
      data:{ labels:presets, datasets:[{ label:'Min ADV (Crores)', data:adv, backgroundColor:[C.green, C.blue, C.amber, C.red], borderRadius:4 }]},
      options:{ ...baseOpts('Min ADV (Rs Crore)'), plugins:{ legend:{display:false} } }
    });

    const stocks = ['HDFC Bank','Reliance','Nifty100 avg','Nifty500 mid','Nifty500 small'];
    const ratios = [0.0003, 0.0008, 0.08, 0.28, 0.65];
    const bColors = ratios.map(r => r < 0.05 ? C.green : r < 0.25 ? C.blue : r < 0.5 ? C.amber : C.red);
    new Chart(document.getElementById('c-liq2'), {
      type:'bar',
      data:{ labels:stocks, datasets:[{ data:ratios, backgroundColor:bColors, borderRadius:4 }]},
      options:{ ...baseOpts('Amihud Ratio (lower=liquid)'), plugins:{ legend:{display:false} }, scales:{ ...baseOpts().scales, y:{ type:'logarithmic', grid:{ color:C.grid }, title:{ display:true, text:'Amihud (log scale)' } } } }
    });
  },

  fundamental: (container) => {
    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Fundamental filter thresholds — when a stock is rejected</div>
        <div style="margin-top:12px">
          ${[
            ['PE Ratio', '< 0 (losses) or > 200 (extreme)', '#f87171', 85],
            ['Promoter Holding %', '< 10% → reject | < 25% → warn', '#f59e0b', 60],
            ['Debt/Equity', '> 2.0 (non-financial stocks)', '#a78bfa', 70],
            ['Revenue Growth', '< -15% YoY (shrinking business)', '#f87171', 55],
          ].map(([label, desc, color, pct]) => `
            <div class="score-bar-wrap">
              <div class="score-bar-label" style="font-size:12px">${label}</div>
              <div class="score-bar-track" style="flex:1"><div class="score-bar-fill" style="width:${pct}%;background:${color}"></div></div>
              <div style="font-size:11px;color:var(--tx3);min-width:200px;padding-left:8px">${desc}</div>
            </div>
          `).join('')}
        </div>
        <div class="chart-note" style="margin-top:16px">Data fetched free via yfinance.info — no API key required</div>
      </div>`;
  },

  weighted_scoring: (container) => {
    const conditions = [
      ['Supertrend flip',   3, '#3dd68c'],
      ['Golden Cross',      2, '#60a5fa'],
      ['MACD cross',        2, '#60a5fa'],
      ['ADX > 25',          2, '#60a5fa'],
      ['Ichimoku bullish',  2, '#60a5fa'],
      ['PSAR bullish',      2, '#60a5fa'],
      ['BB/KC Squeeze',     2, '#60a5fa'],
      ['Donchian break',    2, '#60a5fa'],
      ['CMF accumulation',  2, '#60a5fa'],
      ['Aroon Up > 70',     2, '#60a5fa'],
      ['SMA 200 above',     1, '#a0a8c0'],
      ['RSI 30-55',         1, '#a0a8c0'],
      ['High volume',       1, '#a0a8c0'],
      ['OBV rising',        1, '#a0a8c0'],
      ['Candle pattern',    1, '#a0a8c0'],
    ];
    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Weight assigned to each scoring condition</div>
        <div class="chart-wrap tall"><canvas id="c-ws1"></canvas></div>
        <div class="chart-note">3pts = high reliability | 2pts = moderate | 1pt = context/confirmation</div>
      </div>`;

    new Chart(document.getElementById('c-ws1'), {
      type:'bar',
      data:{ labels:conditions.map(c=>c[0]), datasets:[{ data:conditions.map(c=>c[1]), backgroundColor:conditions.map(c=>c[2]), borderRadius:4 }]},
      options:{ ...baseOpts('Points assigned'), indexAxis:'y', plugins:{ legend:{display:false} }, scales:{ x:{ max:4, grid:{color:C.grid} }, y:{ grid:{display:false}, ticks:{font:{size:11}} } } }
    });
  },

  rs_rating: (container) => {
    const stocks = ['TITAN','ICICI','BAJFIN','HDFC','INFY','WIPRO','HCLT','SBIN','UPL','COAL'];
    const rs = [14.2, 11.8, 8.4, 5.1, 2.3, -0.8, -3.4, -6.1, -9.2, -14.7];
    const bColors = rs.map(v => v > 10 ? C.green : v > 5 ? C.teal : v > 0 ? C.blue : v > -5 ? C.amber : C.red);

    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Relative Strength vs Nifty 50 (3-month, illustrative)</div>
        <div class="chart-wrap tall"><canvas id="c-rs1"></canvas></div>
        <div class="chart-note">Green = outperforming Nifty (leaders). Red = underperforming (laggards). Only trade leaders in bull markets.</div>
      </div>`;

    new Chart(document.getElementById('c-rs1'), {
      type:'bar',
      data:{ labels:stocks, datasets:[{ data:rs, backgroundColor:bColors, borderRadius:4 }]},
      options:{ ...baseOpts('RS Score (% vs Nifty)'), plugins:{ legend:{display:false} },
        scales:{ ...baseOpts().scales, y:{ ...baseOpts().scales.y,
          grid:{ color:C.grid, drawBorder:false },
          ticks:{ callback:v => v+'%' }
        }}
      }
    });
  },

  market_regime: (container) => {
    const labels = Array.from({length:24},(_,i)=>`Month ${i+1}`);
    const breadth = [72,68,74,80,65,58,52,44,38,30,25,22,28,35,40,48,55,62,68,74,70,66,72,78];
    const rsi = [62,58,64,70,55,48,44,38,32,28,25,24,30,38,44,50,56,62,66,70,64,60,62,68];
    const threshold = Array(24).fill(60);
    const thresholdRsi = Array(24).fill(50);
    const regime = breadth.map((b,i) => b>60 && rsi[i]>50 ? 3 : b<40 && rsi[i]<45 ? 1 : 2);
    const regColors = regime.map(r => r===3 ? 'rgba(61,214,140,0.5)' : r===1 ? 'rgba(248,113,113,0.5)' : 'rgba(245,158,11,0.5)');

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Nifty 50 breadth — % stocks above SMA 50</div>
          <div class="chart-wrap"><canvas id="c-reg1"></canvas></div>
          <div class="chart-note">&gt;60% = bull breadth | &lt;40% = bear breadth</div>
        </div>
        <div class="chart-container">
          <div class="chart-title">Detected regime over time</div>
          <div class="chart-wrap"><canvas id="c-reg2"></canvas></div>
          <div class="chart-note">Green=BULL (qualify≥18) | Amber=SIDEWAYS (≥20) | Red=BEAR (≥24)</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-reg1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Breadth %', data:breadth, borderColor:C.teal, borderWidth:2, pointRadius:0, fill:true, backgroundColor:'rgba(52,211,153,0.08)' },
        { label:'Bull threshold', data:threshold, borderColor:C.green, borderWidth:1, borderDash:[4,3], pointRadius:0 },
      ]},
      options:{ ...baseOpts('% stocks above SMA50'), scales:{ ...baseOpts().scales, y:{ ...baseOpts().scales.y, min:0, max:100 } }, plugins:{ legend:{ display:true, position:'top', labels:{boxWidth:10,font:{size:10}} } } }
    });

    new Chart(document.getElementById('c-reg2'), {
      type:'bar', data:{ labels, datasets:[{ data:regime, backgroundColor:regColors, borderRadius:2 }]},
      options:{ ...baseOpts('Regime (3=BULL, 2=SIDE, 1=BEAR)'), plugins:{ legend:{display:false} },
        scales:{ ...baseOpts().scales, y:{ min:0, max:4, grid:{color:C.grid}, ticks:{ callback:v=>({1:'BEAR',2:'SIDE',3:'BULL'})[v]||'' } } }
      }
    });
  },

  mtf_gate: (container) => {
    const labels = dayLabels(50);
    const wClose = genPrice(50, 1600, 0.002, 0.020, 22);
    const wSMA20 = sma(wClose, 20);
    const wRSI = calcRSI(wClose);
    const gateColor = wClose.map((p,i) => {
      const aboveSMA = p > (wSMA20[i] || 0);
      const rsiOk = (wRSI[i] || 50) > 45;
      const passes = (aboveSMA?1:0) + (rsiOk?1:0);
      return passes===2 ? 'rgba(61,214,140,0.5)' : passes===1 ? 'rgba(245,158,11,0.5)' : 'rgba(248,113,113,0.5)';
    });

    container.innerHTML = `
      <div class="chart-row">
        <div class="chart-container">
          <div class="chart-title">Weekly price vs SMA 20 (weekly)</div>
          <div class="chart-wrap"><canvas id="c-mtf1"></canvas></div>
          <div class="chart-note">Price above weekly SMA20 = one of three gate conditions passing</div>
        </div>
        <div class="chart-container">
          <div class="chart-title">Weekly RSI — gate condition 2</div>
          <div class="chart-wrap"><canvas id="c-mtf2"></canvas></div>
          <div class="chart-note">Weekly RSI &gt; 45 = passing. Below = weakening weekly trend.</div>
        </div>
      </div>`;

    new Chart(document.getElementById('c-mtf1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Weekly Close', data:wClose, borderColor:C.blue, borderWidth:2, pointRadius:0 },
        { label:'Weekly SMA20', data:wSMA20, borderColor:C.orange, borderWidth:1.5, borderDash:[4,2], pointRadius:0 },
      ]},
      options:{ ...baseOpts('Price (weekly)'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,font:{size:10}}}} }
    });

    new Chart(document.getElementById('c-mtf2'), {
      type:'line', data:{ labels, datasets:[
        { data:wRSI, borderColor:C.purple, borderWidth:2, pointRadius:0, fill:true, backgroundColor:'rgba(167,139,250,0.07)' },
        { data:Array(50).fill(45), borderColor:C.amber, borderWidth:1, borderDash:[4,3], pointRadius:0 },
      ]},
      options:{ ...baseOpts('Weekly RSI'), scales:{...baseOpts().scales, y:{...baseOpts().scales.y,min:0,max:100}} }
    });
  },

  triple_confirm: (container) => {
    const n = 80;
    const prices = genPrice(n, 2600, 0.004, 0.014, 33);
    const labels = dayLabels(n);
    const s200 = sma(prices, 60); // use 60 as proxy for 200
    const rsiData = calcRSI(prices);
    const { line:macdL, signal:macdS } = calcMACD(prices);
    const entryDays = [], exitDays = [];
    let inTrade = false, entryPrice = 0;

    prices.forEach((p, i) => {
      if (i < 30) return;
      const aboveSMA = p > (s200[i]||0);
      const rsiOk = rsiData[i] > 30 && rsiData[i] < 55;
      const macdX = i > 0 && macdL[i-1] < macdS[i-1] && macdL[i] > macdS[i];
      if (!inTrade && aboveSMA && rsiOk && macdX) {
        inTrade = true; entryPrice = p; entryDays.push(i);
      } else if (inTrade && (p < (s200[i]||0) || p > entryPrice*1.1)) {
        inTrade = false; exitDays.push(i);
      }
    });

    const entryMarkers = prices.map((_,i) => entryDays.includes(i) ? prices[i] : null);
    const exitMarkers  = prices.map((_,i) => exitDays.includes(i)  ? prices[i] : null);

    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Triple Confirmation — entry/exit signals (simulated)</div>
        <div class="chart-wrap tall"><canvas id="c-tc1"></canvas></div>
        <div class="chart-note">▲ = Buy signal (above SMA + RSI 30-55 + MACD cross). ▼ = Sell (SMA broken or +10% profit)</div>
      </div>`;

    new Chart(document.getElementById('c-tc1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:1.5, pointRadius:0, tension:0.2 },
        { label:'SMA', data:s200, borderColor:C.blue, borderWidth:1, borderDash:[4,2], pointRadius:0 },
        { label:'Buy',  data:entryMarkers, type:'scatter', pointStyle:'triangle', pointRadius:10, backgroundColor:C.green, showLine:false },
        { label:'Sell', data:exitMarkers, type:'scatter', pointStyle:'triangle', pointRadius:10, rotation:180, backgroundColor:C.red, showLine:false },
      ]},
      options:{ ...baseOpts('Price (₹)'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,font:{size:10}}}} }
    });
  },

  supertrend_strategy: (container) => {
    const n = 80;
    const prices = genPrice(n, 1600, 0.003, 0.016, 44);
    const labels = dayLabels(n);
    const entryMarkers = [], exitMarkers = [];
    let inTrade = false, entryP = 0, stDir = -1;
    prices.forEach((p, i) => {
      if (i < 10) return;
      const atr = 25 + Math.random()*8;
      const newDir = p > prices[i-1] ? 1 : -1;
      if (!inTrade && stDir === -1 && newDir === 1) {
        inTrade = true; entryP = p; stDir = 1;
        entryMarkers[i] = p;
      } else if (inTrade && newDir === -1) {
        inTrade = false; stDir = -1;
        exitMarkers[i] = p;
      }
      stDir = newDir;
    });

    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Supertrend Strategy — trend-following trades</div>
        <div class="chart-wrap tall"><canvas id="c-sts1"></canvas></div>
        <div class="chart-note">Green ▲ = Supertrend flipped bullish → BUY. Red ▼ = Supertrend flipped bearish → SELL. Ride the trend until it reverses.</div>
      </div>`;

    const em = prices.map((_,i) => entryMarkers[i]||null);
    const xm = prices.map((_,i) => exitMarkers[i]||null);

    new Chart(document.getElementById('c-sts1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:1.5, pointRadius:0 },
        { label:'Buy',  data:em, type:'scatter', pointStyle:'triangle', pointRadius:10, backgroundColor:C.green, showLine:false },
        { label:'Sell', data:xm, type:'scatter', pointStyle:'triangle', pointRadius:10, rotation:180, backgroundColor:C.red, showLine:false },
      ]},
      options:{ ...baseOpts('Price (₹)'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,font:{size:10}}}} }
    });
  },

  donchian_strategy: (container) => {
    const n = 70;
    const prices = genPrice(n, 800, 0.004, 0.020, 55);
    const labels = dayLabels(n);
    const dcUpper = prices.map((_, i) => i < 20 ? null : Math.max(...prices.slice(i-20, i)));
    const dcLower = prices.map((_, i) => i < 20 ? null : Math.min(...prices.slice(i-20, i)));
    const entries = prices.map((p,i) => (i>20 && dcUpper[i] && p > dcUpper[i-1]) ? p : null);
    const exits   = prices.map((p,i) => (i>20 && dcLower[i] && p < dcLower[i-1]) ? p : null);

    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Donchian Breakout — buy new 20-day highs with volume</div>
        <div class="chart-wrap tall"><canvas id="c-ds1"></canvas></div>
        <div class="chart-note">Price breaking above upper channel + high volume = breakout buy. Exit when price breaks below lower channel.</div>
      </div>`;

    new Chart(document.getElementById('c-ds1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Upper', data:dcUpper, borderColor:'rgba(96,165,250,0.4)', borderWidth:1, pointRadius:0, fill:'+1', backgroundColor:'rgba(96,165,250,0.05)' },
        { label:'Lower', data:dcLower, borderColor:'rgba(96,165,250,0.4)', borderWidth:1, pointRadius:0 },
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:2, pointRadius:0 },
        { label:'Buy',   data:entries, type:'scatter', pointStyle:'triangle', pointRadius:10, backgroundColor:C.green, showLine:false },
        { label:'Exit',  data:exits,   type:'scatter', pointStyle:'triangle', pointRadius:10, rotation:180, backgroundColor:C.red, showLine:false },
      ]},
      options:{ ...baseOpts('Price (₹)'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,font:{size:10},filter:i=>i.dataIndex>1}}} }
    });
  },

  mean_reversion: (container) => {
    const n = 70;
    const prices = genPrice(n, 6800, 0.001, 0.025, 66);
    const labels = dayLabels(n);
    const bb = calcBB(prices);
    const rsiData = calcRSI(prices);
    const s200 = sma(prices, 50);
    const entries = prices.map((p,i) => {
      const rOk = rsiData[i] && rsiData[i] < 35;
      const bOk = bb.lower[i] && p < bb.lower[i] * 1.01;
      const sOk = s200[i] && p > s200[i];
      return (rOk && bOk && sOk) ? p : null;
    });

    container.innerHTML = `
      <div class="chart-container">
        <div class="chart-title">Mean Reversion — buy oversold pullbacks in uptrend</div>
        <div class="chart-wrap tall"><canvas id="c-mr1"></canvas></div>
        <div class="chart-note">▲ = RSI&lt;35 + near lower BB + above SMA200. Wait for price to bounce back to mean.</div>
      </div>`;

    new Chart(document.getElementById('c-mr1'), {
      type:'line', data:{ labels, datasets:[
        { label:'BB Upper', data:bb.upper, borderColor:'rgba(96,165,250,0.3)', borderWidth:1, pointRadius:0 },
        { label:'BB Lower', data:bb.lower, borderColor:'rgba(96,165,250,0.3)', borderWidth:1, pointRadius:0, fill:'-1', backgroundColor:'rgba(61,214,140,0.04)' },
        { label:'SMA proxy', data:s200, borderColor:C.blue, borderWidth:1, borderDash:[4,2], pointRadius:0 },
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:2, pointRadius:0 },
        { label:'Buy signal', data:entries, type:'scatter', pointStyle:'triangle', pointRadius:10, backgroundColor:C.green, showLine:false },
      ]},
      options:{ ...baseOpts('Price (₹)'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,font:{size:10},filter:i=>i.dataIndex>2}}} }
    });
  },

  // Fallback for charts without specific renderers
  ichimoku: (container) => { container.innerHTML = '<div class="chart-container"><div class="chart-title">Ichimoku Cloud components</div><svg viewBox="0 0 600 180" width="100%"><rect x="0" y="60" width="600" height="80" fill="rgba(61,214,140,0.08)" rx="4"/><line x1="0" y1="60" x2="600" y2="60" stroke="#3dd68c" stroke-width="1.5" stroke-dasharray="4,2"/><line x1="0" y1="140" x2="600" y2="88" stroke="#f87171" stroke-width="1.5" stroke-dasharray="4,2"/><text x="20" y="52" fill="#3dd68c" font-size="11">Senkou Span A (green cloud top)</text><text x="20" y="154" fill="#f87171" font-size="11">Senkou Span B (red cloud bottom)</text><text x="300" y="104" fill="#a0a8c0" font-size="12" text-anchor="middle">KUMO (Cloud) — future S/R</text><line x1="0" y1="80" x2="600" y2="70" stroke="#60a5fa" stroke-width="2"/><text x="20" y="75" fill="#60a5fa" font-size="10">Tenkan-sen (fast)</text><line x1="0" y1="100" x2="600" y2="90" stroke="#fb923c" stroke-width="2"/><text x="20" y="107" fill="#fb923c" font-size="10">Kijun-sen (base line — most important)</text></svg><div class="chart-note">Price above green cloud + Tenkan &gt; Kijun = maximum bullish alignment</div></div>'; },

  parabolic_sar: (container) => {
    const prices = genPrice(50, 789, 0.003, 0.015, 77);
    const labels = dayLabels(50);
    const sar = prices.map((p, i) => i === 0 ? p - 25 : p > prices[i-1] ? Math.min(prices[i-1]-18, p-22) : p + 22);
    const bull = sar.map((s,i) => s < prices[i] ? s : null);
    const bear = sar.map((s,i) => s >= prices[i] ? s : null);
    container.innerHTML = `<div class="chart-container"><div class="chart-title">Parabolic SAR — dots below = uptrend, dots above = downtrend</div><div class="chart-wrap"><canvas id="c-psar1"></canvas></div><div class="chart-note">When dots flip sides → trend has reversed → act on next bar's open</div></div>`;
    new Chart(document.getElementById('c-psar1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:2, pointRadius:0 },
        { label:'SAR (bull)', data:bull, type:'scatter', pointRadius:4, backgroundColor:C.green, showLine:false },
        { label:'SAR (bear)', data:bear, type:'scatter', pointRadius:4, backgroundColor:C.red, showLine:false },
      ]},
      options:{ ...baseOpts('Price'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,font:{size:10}}}} }
    });
  },

  dema_tema: (container) => {
    const prices = genPrice(60, 1000, 0.003, 0.016, 88);
    const labels = dayLabels(60);
    const e1 = ema(prices, 20), e2 = ema(e1, 20), e3 = ema(e2, 20);
    const demaData = e1.map((v,i) => 2*v - e2[i]);
    const temaData = e1.map((v,i) => 3*v - 3*e2[i] + e3[i]);
    const s20 = sma(prices, 20);
    container.innerHTML = `<div class="chart-container"><div class="chart-title">SMA vs EMA vs DEMA vs TEMA — lag comparison (same 20-period)</div><div class="chart-wrap tall"><canvas id="c-dt1"></canvas></div><div class="chart-note">All use period=20. TEMA turns first when trend changes. SMA turns last.</div></div>`;
    new Chart(document.getElementById('c-dt1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:'rgba(255,255,255,0.3)', borderWidth:1, pointRadius:0 },
        { label:'SMA 20', data:s20, borderColor:C.muted, borderWidth:1.5, borderDash:[6,3], pointRadius:0 },
        { label:'EMA 20', data:e1, borderColor:C.blue, borderWidth:1.5, pointRadius:0 },
        { label:'DEMA 20', data:demaData, borderColor:C.green, borderWidth:1.5, pointRadius:0 },
        { label:'TEMA 20', data:temaData, borderColor:C.orange, borderWidth:2, pointRadius:0 },
      ]},
      options:{ ...baseOpts('Price'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:12,font:{size:10}}}} }
    });
  },

  hma: (container) => {
    const prices = genPrice(60, 3200, 0.003, 0.016, 99);
    const labels = dayLabels(60);
    const e20 = ema(prices, 20);
    const e10 = ema(prices, 10);
    const raw = e10.map((f,i) => 2*f - e20[i]);
    const hmaData = ema(raw, 4);
    container.innerHTML = `<div class="chart-container"><div class="chart-title">HMA vs EMA — HMA turns sharply, EMA curves gradually</div><div class="chart-wrap"><canvas id="c-hma1"></canvas></div><div class="chart-note">HMA's sharp decisive turns make trend changes unmistakable</div></div>`;
    new Chart(document.getElementById('c-hma1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:'rgba(255,255,255,0.2)', borderWidth:1, pointRadius:0 },
        { label:'EMA 20', data:e20, borderColor:C.blue, borderWidth:1.5, borderDash:[4,2], pointRadius:0 },
        { label:'HMA 20', data:hmaData, borderColor:C.green, borderWidth:2.5, pointRadius:0 },
      ]},
      options:{ ...baseOpts('Price'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:12,font:{size:10}}}} }
    });
  },

  alligator: (container) => {
    const prices = genPrice(70, 9800, 0.002, 0.014, 111);
    const labels = dayLabels(70);
    const jaw = ema(prices, 13).map((v,i,a) => a[Math.min(i+8, a.length-1)]);
    const teeth = ema(prices, 8).map((v,i,a) => a[Math.min(i+5, a.length-1)]);
    const lips = ema(prices, 5).map((v,i,a) => a[Math.min(i+3, a.length-1)]);
    container.innerHTML = `<div class="chart-container"><div class="chart-title">Williams Alligator — Jaw(13,8), Teeth(8,5), Lips(5,3)</div><div class="chart-wrap"><canvas id="c-al1"></canvas></div><div class="chart-note">Lines fanned apart = Alligator eating (trade). Lines tangled = sleeping (wait).</div></div>`;
    new Chart(document.getElementById('c-al1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:'rgba(255,255,255,0.3)', borderWidth:1, pointRadius:0 },
        { label:'Jaw (blue)', data:jaw, borderColor:C.blue, borderWidth:1.5, pointRadius:0 },
        { label:'Teeth (red)', data:teeth, borderColor:C.red, borderWidth:1.5, pointRadius:0 },
        { label:'Lips (green)', data:lips, borderColor:C.green, borderWidth:1.5, pointRadius:0 },
      ]},
      options:{ ...baseOpts('Price'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:12,font:{size:10}}}} }
    });
  },

  vwma: (container) => {
    const prices = genPrice(50, 1600, 0.003, 0.014, 122);
    const labels = dayLabels(50);
    const vol = prices.map((_,i) => 500000 + Math.random()*2000000 + (i%7===0 ? 5000000 : 0));
    const s20 = sma(prices, 20);
    const vwmaData = prices.map((_,i) => {
      if (i < 19) return null;
      const pSlice = prices.slice(i-19, i+1), vSlice = vol.slice(i-19, i+1);
      const pv = pSlice.reduce((s,p,j) => s+p*vSlice[j], 0);
      const v = vSlice.reduce((s,v) => s+v, 0);
      return pv/v;
    });
    container.innerHTML = `<div class="chart-container"><div class="chart-title">VWMA vs SMA — high-volume days pull VWMA toward actual trading price</div><div class="chart-wrap"><canvas id="c-vm1"></canvas></div><div class="chart-note">VWMA above SMA = high-volume days had higher prices (bullish institutional activity)</div></div>`;
    new Chart(document.getElementById('c-vm1'), {
      type:'line', data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:C.teal, borderWidth:1, pointRadius:0 },
        { label:'SMA 20', data:s20, borderColor:C.muted, borderWidth:1.5, borderDash:[4,2], pointRadius:0 },
        { label:'VWMA 20', data:vwmaData, borderColor:C.amber, borderWidth:2, pointRadius:0 },
      ]},
      options:{ ...baseOpts('Price'), plugins:{legend:{display:true,position:'top',labels:{boxWidth:12,font:{size:10}}}} }
    });
  },

};

// ── Mini chart renderer for card thumbnails ─────────────────
function renderMiniChart(canvas, chartId, cat) {
  const catColors = {
    trend:'#3dd68c', momentum:'#60a5fa', volatility:'#f59e0b',
    volume:'#a78bfa', strength:'#f87171', patterns:'#fbbf24',
    filters:'#e879f9', strategies:'#38bdf8', breadth:'#34d399',
  };
  const color = catColors[cat] || '#60a5fa';
  const data = Array.from({length:20}, (_,i) => {
    const seed = chartId.split('').reduce((a,c) => a+c.charCodeAt(0),0) + i*13;
    return 50 + 20*Math.sin(i*0.4 + seed*0.1) + (seed%7)*3;
  });

  new Chart(canvas, {
    type:'line',
    data:{ labels:Array(20).fill(''), datasets:[{
      data, borderColor:color, borderWidth:1.5, pointRadius:0,
      tension:0.4, fill:true, backgroundColor:color+'15',
    }]},
    options:{
      responsive:true, maintainAspectRatio:false, animation:false,
      plugins:{ legend:{display:false}, tooltip:{enabled:false} },
      scales:{ x:{display:false}, y:{display:false} },
    }
  });
}
