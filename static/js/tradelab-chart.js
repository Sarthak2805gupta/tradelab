/* TradeLab Chart — a small native canvas candlestick/line/area/bar chart.
   Drop-in compatibility shim for the tiny subset of the lightweight-charts API
   that analysis.html and live.html use.
   Exposes window.LightweightCharts.createChart(el, opts).
*/
(function () {
  "use strict";

  // ─── helpers ──────────────────────────────────────────────
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const dpr = () => window.devicePixelRatio || 1;

  function themeColors() {
    const rs = getComputedStyle(document.documentElement);
    const isLight = document.documentElement.classList.contains("light");
    return {
      ink: rs.getPropertyValue("--sa-ink").trim() || (isLight ? "#0f172a" : "#e6ebf3"),
      muted: rs.getPropertyValue("--sa-muted").trim() || "#8a94a7",
      grid: isLight ? "rgba(15,23,42,0.06)" : "rgba(255,255,255,0.05)",
      border: isLight ? "rgba(15,23,42,0.10)" : "rgba(255,255,255,0.08)",
      up: rs.getPropertyValue("--sa-accent").trim() || "#34d399",
      down: rs.getPropertyValue("--sa-danger").trim() || "#fb7185",
      crosshair: isLight ? "rgba(15,23,42,0.35)" : "rgba(255,255,255,0.25)",
      tooltipBg: isLight ? "rgba(255,255,255,0.95)" : "rgba(15,20,32,0.95)",
    };
  }

  // ─── Series ───────────────────────────────────────────────
  function Series(chart, type, opts) {
    this.chart = chart;
    this.type = type;
    this.opts = opts || {};
    this.data = [];
    this.markers = [];
  }
  Series.prototype.setData = function (data) {
    this.data = (data || []).slice().sort((a, b) => a.time - b.time);
    this.chart._layoutDirty = true;
    this.chart._requestDraw();
  };
  Series.prototype.setMarkers = function (markers) {
    this.markers = markers || [];
    this.chart._requestDraw();
  };
  Series.prototype.update = function (bar) {
    if (!this.data.length || bar.time > this.data[this.data.length - 1].time) {
      this.data.push(bar);
    } else {
      this.data[this.data.length - 1] = bar;
    }
    this.chart._layoutDirty = true;
    this.chart._requestDraw();
  };
  Series.prototype.applyOptions = function (o) { Object.assign(this.opts, o || {}); this.chart._requestDraw(); };

  // ─── Chart ────────────────────────────────────────────────
  function Chart(el, opts) {
    this.el = el;
    this.opts = opts || {};
    this.series = [];
    this.width = opts.width || el.clientWidth || 600;
    this.height = opts.height || 400;
    this._panIdx = 0;           // left-edge offset into data (bars)
    this._barsPerView = null;   // auto
    this._hover = null;
    this._listeners = [];
    this._rangeSyncLocks = false;

    // wrapper
    el.style.position = el.style.position || "relative";
    el.style.overflow = "hidden";
    el.innerHTML = "";

    this.canvas = document.createElement("canvas");
    this.canvas.style.display = "block";
    this.canvas.style.width = "100%";
    this.canvas.style.height = this.height + "px";
    el.appendChild(this.canvas);

    // tooltip
    this.tip = document.createElement("div");
    this.tip.style.cssText =
      "position:absolute;top:8px;left:8px;padding:6px 10px;border-radius:8px;" +
      "font:500 11px/1.5 'JetBrains Mono',monospace;pointer-events:none;display:none;z-index:5;" +
      "white-space:nowrap;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);";
    el.appendChild(this.tip);

    this._resize();
    this._bindEvents();

    const self = this;
    this._ro = new ResizeObserver(() => self._resize());
    this._ro.observe(el);

    this._themeObs = new MutationObserver(() => self._requestDraw());
    this._themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  }

  Chart.prototype._resize = function () {
    this.width = this.el.clientWidth || 600;
    this.canvas.style.height = this.height + "px";
    const d = dpr();
    this.canvas.width = this.width * d;
    this.canvas.height = this.height * d;
    this._layoutDirty = true;
    this._requestDraw();
  };

  Chart.prototype.addCandlestickSeries = function (o) { const s = new Series(this, "candle", o); this.series.push(s); return s; };
  Chart.prototype.addLineSeries       = function (o) { const s = new Series(this, "line",   o); this.series.push(s); return s; };
  Chart.prototype.addAreaSeries       = function (o) { const s = new Series(this, "area",   o); this.series.push(s); return s; };
  Chart.prototype.addBarSeries        = function (o) { const s = new Series(this, "bar",    o); this.series.push(s); return s; };
  Chart.prototype.addHistogramSeries  = function (o) { const s = new Series(this, "hist",   o); this.series.push(s); return s; };
  Chart.prototype.removeSeries = function (s) {
    const i = this.series.indexOf(s);
    if (i >= 0) this.series.splice(i, 1);
    this._requestDraw();
  };
  Chart.prototype.applyOptions = function (o) { Object.assign(this.opts, o || {}); this._requestDraw(); };
  Chart.prototype.resize = function (w, h) { if (h) this.height = h; this._resize(); };
  Chart.prototype.remove = function () {
    this._ro && this._ro.disconnect();
    this._themeObs && this._themeObs.disconnect();
    this.el.innerHTML = "";
  };

  Chart.prototype.timeScale = function () {
    const self = this;
    return {
      fitContent() {
        self._panIdx = 0;
        self._barsPerView = null;
        self._layoutDirty = true;
        self._requestDraw();
      },
      subscribeVisibleLogicalRangeChange(cb) { self._listeners.push(cb); },
      setVisibleLogicalRange(r) {
        if (!r || self._rangeSyncLocks) return;
        self._panIdx = Math.max(0, Math.round(r.from));
        self._barsPerView = Math.max(5, Math.round(r.to - r.from));
        self._layoutDirty = true;
        self._requestDraw();
      },
      scrollToPosition() {},
    };
  };

  // Figure out the total bars across all series (use the first non-empty)
  Chart.prototype._primarySeries = function () {
    for (const s of this.series) if (s.type !== "hist" && s.data.length) return s;
    return this.series.find(s => s.data.length) || null;
  };

  Chart.prototype._computeLayout = function () {
    const p = this._primarySeries();
    const t = themeColors();
    if (!p || !p.data.length) { this._layout = null; return; }

    const data = p.data;
    const total = data.length;
    const bpv = this._barsPerView ? Math.min(this._barsPerView, total) : total;
    const start = clamp(this._panIdx, 0, Math.max(0, total - bpv));
    const end = start + bpv;
    const view = data.slice(start, end);

    // Price extent
    let lo = Infinity, hi = -Infinity;
    for (const b of view) {
      const l = b.low  != null ? b.low  : b.value;
      const h = b.high != null ? b.high : b.value;
      if (l < lo) lo = l;
      if (h > hi) hi = h;
    }
    if (!isFinite(lo) || !isFinite(hi) || lo === hi) { hi = (hi || 1) * 1.02; lo = (lo || 0) * 0.98 || 0; }
    const pad = (hi - lo) * 0.08;
    lo -= pad; hi += pad;

    // Volume extent (from any hist series)
    const histSeries = this.series.find(s => s.type === "hist");
    let vMax = 0;
    if (histSeries && histSeries.data.length) {
      const vs = histSeries.data.slice(start, end);
      for (const v of vs) if (v.value > vMax) vMax = v.value;
    }

    const rightAxisW = 56;
    const bottomAxisH = this.opts.timeScale && this.opts.timeScale.visible === false ? 8 : 24;
    const chartX = 0;
    const chartY = 6;
    const chartW = this.width - rightAxisW;
    const chartH = this.height - bottomAxisH - chartY;
    const barW = chartW / bpv;

    this._layout = {
      theme: t, data, view, start, end, bpv, total,
      lo, hi, vMax, histSeries,
      chartX, chartY, chartW, chartH, rightAxisW, bottomAxisH, barW,
    };
    this._layoutDirty = false;
  };

  Chart.prototype._priceToY = function (p) {
    const L = this._layout;
    return L.chartY + L.chartH - ((p - L.lo) / (L.hi - L.lo)) * L.chartH;
  };
  Chart.prototype._indexToX = function (i) {
    const L = this._layout;
    return L.chartX + (i - L.start + 0.5) * L.barW;
  };
  Chart.prototype._xToIndex = function (x) {
    const L = this._layout;
    return Math.floor((x - L.chartX) / L.barW) + L.start;
  };

  Chart.prototype._requestDraw = function () {
    if (this._raf) return;
    const self = this;
    this._raf = requestAnimationFrame(() => { self._raf = null; self._draw(); });
  };

  Chart.prototype._draw = function () {
    if (this._layoutDirty || !this._layout) this._computeLayout();
    const ctx = this.canvas.getContext("2d");
    const d = dpr();
    ctx.setTransform(d, 0, 0, d, 0, 0);
    ctx.clearRect(0, 0, this.width, this.height);

    if (!this._layout) return;
    const L = this._layout;
    const { theme: t } = L;

    // Horizontal grid + right axis ticks
    const gridLines = 5;
    ctx.strokeStyle = t.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = t.muted;
    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= gridLines; i++) {
      const y = L.chartY + (L.chartH * i) / gridLines;
      ctx.beginPath(); ctx.moveTo(L.chartX, y + 0.5); ctx.lineTo(L.chartX + L.chartW, y + 0.5); ctx.stroke();
      const price = L.hi - ((L.hi - L.lo) * i) / gridLines;
      ctx.fillText("₹" + price.toFixed(2), L.chartX + L.chartW + 6, y);
    }

    // X-axis ticks (IST dates)
    const xTicks = Math.max(3, Math.floor(L.chartW / 90));
    const step = Math.max(1, Math.floor(L.view.length / xTicks));
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let i = 0; i < L.view.length; i += step) {
      const x = this._indexToX(L.start + i);
      const b = L.view[i];
      const d2 = new Date(b.time * 1000);
      const isIntra = L.view.length > 1 && (L.view[1].time - L.view[0].time) < 24 * 3600;
      const label = isIntra
        ? d2.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false })
        : d2.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short" });
      ctx.fillStyle = t.muted;
      ctx.fillText(label, x, L.chartY + L.chartH + 6);
    }

    // Volume histogram (drawn into bottom 18% of chart area, semi-transparent)
    if (L.histSeries && L.vMax > 0) {
      const volH = L.chartH * 0.18;
      const volY0 = L.chartY + L.chartH - volH;
      const vs = L.histSeries.data.slice(L.start, L.end);
      for (let i = 0; i < vs.length; i++) {
        const v = vs[i];
        const x = this._indexToX(L.start + i) - L.barW * 0.4;
        const h = (v.value / L.vMax) * volH;
        ctx.fillStyle = v.color || (v.value > 0 ? "rgba(52,211,153,0.28)" : "rgba(251,113,133,0.28)");
        ctx.fillRect(x, volY0 + (volH - h), L.barW * 0.8, h);
      }
    }

    // Price series
    const primary = this._primarySeries();
    if (primary) this._drawPriceSeries(ctx, primary);

    // Markers
    if (primary && primary.markers && primary.markers.length) this._drawMarkers(ctx, primary);

    // Crosshair + readout
    if (this._hover && this._hover.x >= L.chartX && this._hover.x <= L.chartX + L.chartW) {
      this._drawCrosshair(ctx, primary);
    } else {
      this.tip.style.display = "none";
    }
  };

  Chart.prototype._drawPriceSeries = function (ctx, s) {
    const L = this._layout;
    const t = L.theme;
    const up = s.opts.upColor || s.opts.color || t.up;
    const down = s.opts.downColor || t.down;
    const wickUp = s.opts.wickUpColor || "rgba(52,211,153,0.55)";
    const wickDn = s.opts.wickDownColor || "rgba(251,113,133,0.55)";
    const bars = L.view;
    const self = this;

    if (s.type === "candle") {
      const w = Math.max(1, L.barW * 0.75);
      for (let i = 0; i < bars.length; i++) {
        const b = bars[i];
        const x = self._indexToX(L.start + i);
        const yO = self._priceToY(b.open), yC = self._priceToY(b.close);
        const yH = self._priceToY(b.high), yL = self._priceToY(b.low);
        const isUp = b.close >= b.open;
        ctx.strokeStyle = isUp ? wickUp : wickDn;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x + 0.5, yH); ctx.lineTo(x + 0.5, yL); ctx.stroke();
        ctx.fillStyle = isUp ? up : down;
        const top = Math.min(yO, yC), h = Math.max(1, Math.abs(yC - yO));
        ctx.fillRect(x - w / 2, top, w, h);
      }
    } else if (s.type === "bar") {
      const w = Math.max(1, L.barW * 0.6);
      for (let i = 0; i < bars.length; i++) {
        const b = bars[i];
        const x = self._indexToX(L.start + i);
        const yO = self._priceToY(b.open), yC = self._priceToY(b.close);
        const yH = self._priceToY(b.high), yL = self._priceToY(b.low);
        const isUp = b.close >= b.open;
        ctx.strokeStyle = isUp ? up : down; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(x + 0.5, yH); ctx.lineTo(x + 0.5, yL); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x - w/2, yO); ctx.lineTo(x, yO); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x, yC); ctx.lineTo(x + w/2, yC); ctx.stroke();
      }
    } else if (s.type === "line" || s.type === "area") {
      ctx.strokeStyle = s.opts.lineColor || s.opts.color || up;
      ctx.lineWidth = s.opts.lineWidth || 2;
      ctx.beginPath();
      for (let i = 0; i < bars.length; i++) {
        const b = bars[i];
        const x = self._indexToX(L.start + i);
        const y = self._priceToY(b.close != null ? b.close : b.value);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      if (s.type === "area") {
        const grad = ctx.createLinearGradient(0, L.chartY, 0, L.chartY + L.chartH);
        grad.addColorStop(0, s.opts.topColor || "rgba(52,211,153,0.28)");
        grad.addColorStop(1, s.opts.bottomColor || "rgba(52,211,153,0.01)");
        ctx.save();
        ctx.stroke();
        const lastX = self._indexToX(L.start + bars.length - 1);
        ctx.lineTo(lastX, L.chartY + L.chartH);
        ctx.lineTo(self._indexToX(L.start), L.chartY + L.chartH);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.restore();
      } else {
        ctx.stroke();
      }
    }
  };

  Chart.prototype._drawMarkers = function (ctx, s) {
    const L = this._layout;
    ctx.font = "10px Inter, system-ui, sans-serif";
    for (const m of s.markers) {
      const idx = L.data.findIndex(b => b.time === m.time);
      if (idx < L.start || idx >= L.end) continue;
      const b = L.data[idx];
      const x = this._indexToX(idx);
      const above = m.position === "aboveBar";
      const y = above ? this._priceToY(b.high) - 10 : this._priceToY(b.low) + 10;
      ctx.fillStyle = m.color || L.theme.muted;
      ctx.beginPath();
      if (m.shape === "circle") { ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill(); }
      else if (m.shape === "arrowDown") { ctx.moveTo(x, y + 6); ctx.lineTo(x - 5, y - 2); ctx.lineTo(x + 5, y - 2); ctx.closePath(); ctx.fill(); }
      else if (m.shape === "arrowUp")   { ctx.moveTo(x, y - 6); ctx.lineTo(x - 5, y + 2); ctx.lineTo(x + 5, y + 2); ctx.closePath(); ctx.fill(); }
      if (m.text) {
        ctx.textAlign = "center";
        ctx.textBaseline = above ? "bottom" : "top";
        ctx.fillStyle = L.theme.ink;
        ctx.fillText(m.text, x, above ? y - 6 : y + 8);
      }
    }
  };

  Chart.prototype._drawCrosshair = function (ctx, primary) {
    const L = this._layout;
    const t = L.theme;
    const x = this._hover.x;
    const i = clamp(this._xToIndex(x), L.start, L.end - 1);
    const b = L.data[i]; if (!b) return;
    const cx = this._indexToX(i);

    ctx.save();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = t.crosshair;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx + 0.5, L.chartY); ctx.lineTo(cx + 0.5, L.chartY + L.chartH); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(L.chartX, this._hover.y + 0.5); ctx.lineTo(L.chartX + L.chartW, this._hover.y + 0.5); ctx.stroke();
    ctx.restore();

    // Tooltip
    const tip = this.tip;
    const d2 = new Date(b.time * 1000);
    const intraday = L.view.length > 1 && (L.view[1].time - L.view[0].time) < 24 * 3600;
    const ts = intraday
      ? d2.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })
      : d2.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric" });
    const isUp = (b.close || b.value || 0) >= (b.open || b.value || 0);
    const color = isUp ? t.up : t.down;
    const rows = [];
    if (b.open != null) rows.push(`<span style="color:${t.muted}">O</span> ₹${b.open.toFixed(2)}`);
    if (b.high != null) rows.push(`<span style="color:${t.muted}">H</span> ₹${b.high.toFixed(2)}`);
    if (b.low  != null) rows.push(`<span style="color:${t.muted}">L</span> ₹${b.low.toFixed(2)}`);
    if (b.close != null) rows.push(`<span style="color:${color}">C</span> ₹${b.close.toFixed(2)}`);
    else if (b.value != null) rows.push(`<span style="color:${color}">V</span> ₹${b.value.toFixed(2)}`);

    tip.innerHTML = `<div style="color:${t.muted};margin-bottom:4px">${ts}</div>${rows.join(" &nbsp; ")}`;
    tip.style.background = t.tooltipBg;
    tip.style.color = t.ink;
    tip.style.border = "1px solid " + t.border;
    tip.style.display = "block";
  };

  Chart.prototype._emitRange = function () {
    if (!this._layout || this._rangeSyncLocks) return;
    const r = { from: this._layout.start, to: this._layout.end };
    this._rangeSyncLocks = true;
    for (const cb of this._listeners) { try { cb(r); } catch (e) {} }
    this._rangeSyncLocks = false;
  };

  Chart.prototype._bindEvents = function () {
    const self = this;
    const c = this.canvas;

    c.addEventListener("mousemove", e => {
      const r = c.getBoundingClientRect();
      self._hover = { x: e.clientX - r.left, y: e.clientY - r.top };
      self._requestDraw();
    });
    c.addEventListener("mouseleave", () => { self._hover = null; self._requestDraw(); });

    c.addEventListener("wheel", e => {
      if (!self._layout) return;
      e.preventDefault();
      const L = self._layout;
      const curBpv = self._barsPerView || L.total;
      const factor = e.deltaY > 0 ? 1.1 : 0.9;
      const next = clamp(Math.round(curBpv * factor), 10, L.total);
      self._barsPerView = next;
      self._panIdx = clamp(self._panIdx, 0, L.total - next);
      self._layoutDirty = true;
      self._requestDraw();
      self._emitRange();
    }, { passive: false });

    // Drag to pan
    let dragging = false, lastX = 0;
    c.addEventListener("mousedown", e => { dragging = true; lastX = e.clientX; });
    window.addEventListener("mousemove", e => {
      if (!dragging || !self._layout) return;
      const L = self._layout;
      const dx = e.clientX - lastX;
      lastX = e.clientX;
      const dIdx = -Math.round(dx / L.barW);
      self._panIdx = clamp(self._panIdx + dIdx, 0, L.total - (self._barsPerView || L.total));
      self._layoutDirty = true;
      self._requestDraw();
      self._emitRange();
    });
    window.addEventListener("mouseup", () => { dragging = false; });
  };

  // ─── Public API shim ──────────────────────────────────────
  window.LightweightCharts = window.LightweightCharts || {};
  window.LightweightCharts.createChart = function (el, opts) {
    return new Chart(el, opts || {});
  };
})();
