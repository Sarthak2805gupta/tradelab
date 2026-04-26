// app.js — Main application logic

// ── Merge all data ──────────────────────────────────────────
const ALL_ITEMS = [
  ...ITEMS,
  ...(typeof ITEMS_PART3 !== "undefined" ? ITEMS_PART3 : []),
  ...(typeof ITEMS_GLOSSARY !== "undefined" ? ITEMS_GLOSSARY : []),
];

// ── Category colour lookup ──────────────────────────────────
const CAT_COLOR = {};
CATEGORIES.forEach(c => CAT_COLOR[c.id] = c.color);

// Tags are internal only — not shown to users

// ── State ───────────────────────────────────────────────────
let activeCat = 'all', activeSearch = '', activeModal = null;
let modalChartInstances = [];

// ── Build navigation sidebar ────────────────────────────────
function buildNav() {
  const navEl = document.getElementById('nav-links');
  const cats = [{ id:'all', label:'All items', color:'#e2e5f0' }, ...CATEGORIES];
  let html = '';
  cats.forEach(cat => {
    const count = cat.id === 'all' ? ALL_ITEMS.length : ALL_ITEMS.filter(i => i.cat === cat.id).length;
    html += `<div class="nav-item ${cat.id==='all'?'active':''}" data-cat="${cat.id}" onclick="setCategory('${cat.id}')">
      <div class="nav-dot" style="background:${cat.color}"></div>
      <span>${cat.label}</span>
      <span class="nav-count">${count}</span>
    </div>`;
  });
  navEl.innerHTML = `<div class="nav-section"><div class="nav-section-title">Browse</div>${html}</div>`;
  document.getElementById('total-count').textContent = ALL_ITEMS.length;
}

// ── Build filter pills ───────────
// Encyclopedia now inherits the site-wide theme from base.html's toggle,
// so no separate theme button is injected here.
function buildPills() {
  document.getElementById('filter-pills').innerHTML = '';
}

// ── Build all sections and cards ────────────────────────────
function buildSections() {
  const container = document.getElementById('sections');
  let html = '';

  CATEGORIES.forEach(cat => {
    const items = ALL_ITEMS.filter(i => i.cat === cat.id);
    if (!items.length) return;

    html += `<div class="section" id="sec-${cat.id}" data-cat="${cat.id}">
      <div class="section-header">
        <div class="section-dot" style="background:${cat.color}"></div>
        <div class="section-title">${cat.label}</div>
        <div class="section-count" id="cnt-${cat.id}">${items.length}</div>
        <div class="section-desc">${cat.desc}</div>
      </div>
      <div class="card-grid" id="grid-${cat.id}">`;

    items.forEach(item => {
      // Escape double/single quotes so they don't break the data-search attribute
      const searchVal = [item.name, item.short||'', item.cat, item.creator||'', item.purpose||'']
        .join(' ').toLowerCase()
        .replace(/"/g, '').replace(/'/g, '');

      html += `<div class="icard" data-id="${item.id}" data-cat="${item.cat}"
                    data-search="${searchVal}"
                    onclick="openModal('${item.id}')"
                    style="--cat-color:${cat.color}">
        <div class="card-top">
          <div class="card-name">${item.name}</div>
        </div>
        <div class="card-desc">${item.short}</div>
        <div class="card-mini-chart"><canvas id="mini-${item.id}" height="45"></canvas></div>
      </div>`;
    });

    html += `</div></div>`;
  });

  container.innerHTML = html;

  // Apply category top-border colour
  document.querySelectorAll('.icard').forEach(card => {
    const color = CAT_COLOR[card.dataset.cat] || '#888';
    card.style.setProperty('--cat-color', color);
  });

  // Render mini charts (deferred so DOM is ready)
  requestAnimationFrame(() => {
    ALL_ITEMS.forEach(item => {
      const canvas = document.getElementById(`mini-${item.id}`);
      if (canvas) renderMiniChart(canvas, item.id, item.cat);
    });
  });
}

// ── Apply category colour to card top border ─────────────────
function applyCardStyles() {
  const style = document.createElement('style');
  CATEGORIES.forEach(cat => {
    style.textContent += `.icard[data-cat="${cat.id}"]::before { background: ${cat.color}; }\n`;
  });
  document.head.appendChild(style);
}

// ── Filter logic ─────────────────────────────────────────────
let activeTag = 'all';

function setCategory(cat) {
  activeCat = cat;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.cat === cat));
  applyFilters();
}

function setTag(tag) {
  activeTag = tag;
  document.querySelectorAll('.fpill').forEach(el => el.classList.toggle('on', el.dataset.tag === tag));
  applyFilters();
}

function applyFilters() {
  const q = activeSearch.toLowerCase().trim();
  let totalVisible = 0;

  CATEGORIES.forEach(cat => {
    const sec = document.getElementById(`sec-${cat.id}`);
    if (!sec) return;

    const cards = sec.querySelectorAll('.icard');
    let secVisible = 0;

    cards.forEach(card => {
      const catMatch    = activeCat === 'all' || card.dataset.cat === activeCat;
      const searchMatch = !q || card.dataset.search.includes(q);
      const visible     = catMatch && searchMatch;
      card.classList.toggle('hidden', !visible);
      if (visible) { secVisible++; totalVisible++; }
    });

    const showSec = secVisible > 0 && (activeCat === 'all' || cat.id === activeCat);
    sec.classList.toggle('hidden', !showSec);

    const cnt = document.getElementById(`cnt-${cat.id}`);
    if (cnt) cnt.textContent = secVisible;
  });

  document.getElementById('empty').style.display = totalVisible === 0 ? 'block' : 'none';
}

// ── Modal ────────────────────────────────────────────────────
function openModal(id) {
  const item = ALL_ITEMS.find(i => i.id === id);
  if (!item) return;

  activeModal = item;
  const color = CAT_COLOR[item.cat] || '#888';
  const cat   = CATEGORIES.find(c => c.id === item.cat);

  // Header — no tag shown to user
  document.getElementById('modal-badge').innerHTML =
    `<div class="modal-badge-dot" style="background:${color}"></div>
     <span style="color:${color}">${cat?.label || ''}</span>`;
  document.getElementById('modal-title').textContent    = item.name;
  document.getElementById('modal-subtitle').textContent = item.creator || '';
  document.getElementById('modal-tags').innerHTML =
    item.python
      ? `<span class="modal-tag" style="font-size:10px;font-family:'DM Mono',monospace">${item.python}</span>`
      : '';

  // Tabs
  const hasPurpose = !!item.purpose;
  const hasFormula = !!item.formula;
  const hasSignals = item.signals && item.signals.length;
  const hasChart   = !!item.chart;
  const hasExample = !!item.example;

  const tabs = [
    { id:'overview', label:'Overview', show: hasPurpose },
    { id:'formula',  label:'Formula',  show: hasFormula },
    { id:'signals',  label:'Signals',  show: hasSignals },
    { id:'chart',    label:'Chart',    show: hasChart   },
    { id:'example',  label:'Example',  show: hasExample },
  ].filter(t => t.show);

  document.getElementById('modal-tabs').innerHTML = tabs.map((t,i) =>
    `<div class="modal-tab ${i===0?'active':''}" data-tab="${t.id}" onclick="switchTab('${t.id}')">${t.label}</div>`
  ).join('');

  // Content panels
  const signals = (item.signals||[]).map(s =>
    `<div class="signal"><div class="sig-tag ${s.t}">${s.t}</div><div class="sig-text">${s.s}</div></div>`
  ).join('');
  const combos = (item.combos||[]).map(c => `<div class="combo-tag">${c}</div>`).join('');

  document.getElementById('modal-content').innerHTML = `
    <div class="tab-panel active" data-panel="overview">
      ${hasPurpose ? `<div class="section-label">What it does</div><div class="desc">${item.purpose}</div>` : ''}
      ${item.tip ? `<div class="section-label" style="margin-top:18px">Pro tip</div><div class="tip-box"><b>Tip:</b> ${item.tip}</div>` : ''}
      ${combos ? `<div class="section-label" style="margin-top:18px">Combine with</div><div class="combos">${combos}</div>` : ''}
    </div>
    <div class="tab-panel" data-panel="formula">
      ${hasFormula ? `<div class="section-label">Formula &amp; calculation</div><div class="formula" style="border-left-color:${color}">${item.formula}</div>` : ''}
    </div>
    <div class="tab-panel" data-panel="signals">
      ${hasSignals ? `<div class="section-label">Trading signals</div><div class="signals">${signals}</div>` : ''}
    </div>
    <div class="tab-panel" data-panel="chart">
      <div id="modal-chart-area"></div>
    </div>
    <div class="tab-panel" data-panel="example">
      ${hasExample ? `<div class="section-label">Real-world example</div><div class="formula" style="border-left-color:${color};font-size:12px">${item.example}</div>` : ''}
    </div>
  `;

  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal').scrollTop = 0;

  if (hasChart && tabs[0]?.id === 'chart') renderModalChart(item);
}

function switchTab(tabId) {
  document.querySelectorAll('.modal-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.panel === tabId));
  if (tabId === 'chart' && activeModal?.chart) {
    setTimeout(() => renderModalChart(activeModal), 50);
  }
}

function renderModalChart(item) {
  const area = document.getElementById('modal-chart-area');
  if (!area) return;
  modalChartInstances.forEach(c => { try { c.destroy(); } catch(e){} });
  modalChartInstances = [];
  const renderer = CHART_RENDERERS[item.chart];
  if (renderer) {
    area.innerHTML = '';
    renderer(area);
    modalChartInstances = Chart.instances ? Object.values(Chart.instances) : [];
  } else {
    area.innerHTML = `<div class="chart-container"><div class="chart-note" style="padding:40px;text-align:center;color:var(--tx3)">Interactive chart coming soon for ${item.name}</div></div>`;
  }
}

function closeModal() {
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
  activeModal = null;
}

// ── Chart.js defaults follow site-wide theme (html.light class) ─────
(function syncChartColors() {
  function apply() {
    const isLight = document.documentElement.classList.contains('light');
    if (typeof Chart !== 'undefined') {
      Chart.defaults.color       = isLight ? '#57606a' : '#a0a8c0';
      Chart.defaults.borderColor = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)';
    }
  }
  apply();
  // Re-apply on theme flips by observing the html class attribute
  new MutationObserver(apply).observe(document.documentElement,
    { attributes: true, attributeFilter: ['class'] });
})();

// ── Search ───────────────────────────────────────────────────
let searchTimer;
document.getElementById('search').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    activeSearch = e.target.value;
    applyFilters();
  }, 150);
});

// ── Keyboard shortcuts ────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if ((e.key === 'f' || e.key === '/') && !e.ctrlKey && !e.metaKey &&
      !document.getElementById('overlay').classList.contains('open')) {
    e.preventDefault();
    document.getElementById('search').focus();
  }
});

// ── Modal close events ────────────────────────────────────────
document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('overlay')) closeModal();
});

// ── Init ──────────────────────────────────────────────────────
// Encyclopedia theme follows the site-wide toggle (html.light), which is
// handled by base.html + the syncChartColors() MutationObserver above.
// Clean up any stale legacy 'theme' localStorage entry left behind by
// the old (removed) encyclopedia-only toggle button.
try { localStorage.removeItem('theme'); } catch (_) {}
document.body.classList.remove('light');

buildNav();
buildPills();
buildSections();
applyCardStyles();
applyFilters();
