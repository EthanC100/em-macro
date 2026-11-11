/* Ledger app: a hash-routed single page that renders the JSON written by ledger/build.py. */
(function () {
  'use strict';

  const DATA = {};
  const charts = [];
  const filters = { decisions: { country: '', status: '', outcome: '' }, reports: { type: '', country: '' },
                    elections: { country: '' } };
  let meta = null;

  // ------------------------------------------------------------------ helpers
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtDate(s) {
    if (!s) return '—';
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    if (!m) return s;
    return `${parseInt(m[3], 10)} ${MONTHS[parseInt(m[2], 10) - 1]} ${m[1]}`;
  }
  function fmtDateTime(s) {
    if (!s) return '—';
    const d = new Date(s);
    if (isNaN(d)) return s;
    const hh = String(d.getUTCHours()).padStart(2, '0'), mm = String(d.getUTCMinutes()).padStart(2, '0');
    return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${hh}:${mm} UTC`;
  }
  function fmtMonth(s) {
    if (!s) return '—';
    const m = /^(\d{4})-(\d{2})/.exec(s);
    return m ? `${MONTHS[parseInt(m[2], 10) - 1]} ${m[1]}` : s;
  }
  const isNum = (x) => typeof x === 'number' && isFinite(x);
  function fmtNum(x, nd = 1) { return isNum(x) ? x.toLocaleString('en-GB', { minimumFractionDigits: nd, maximumFractionDigits: nd }) : '—'; }
  function fmtPct(x, nd = 1, sign = false) {
    if (!isNum(x)) return '—';
    const s = fmtNum(Math.abs(x), nd);
    return (x < 0 ? '−' : (sign && x > 0 ? '+' : '')) + s + '%';
  }
  function fmtProb(x) { return isNum(x) ? `${fmtNum(x, 0)}%` : '—'; }
  const signClass = (x) => (!isNum(x) || x === 0) ? '' : (x > 0 ? 'good' : 'bad');
  function pill(text, cls = '') { return `<span class="pill ${esc(cls)}">${esc(text)}</span>`; }
  // escape, then turn bare URLs into links (used for resolution notes that carry source links)
  function linkify(s) {
    return esc(s).replace(/https?:\/\/[^\s;,)"'&lt;&gt;]+/g, (u) => `<a href="${u}" target="_blank" rel="noopener">${u.replace(/^https?:\/\//, '').slice(0, 40)}${u.length > 48 ? '…' : ''}</a>`);
  }
  // status badges: open, won, lost, passed, failed, under test, and the rest
  const BADGE = {
    open: ['open', 'open'], right: ['won', 'good'], wrong: ['lost', 'bad'], scratched: ['scratched', ''],
    'no trade': ['no trade', ''], yes: ['yes', 'purple'], no: ['no', 'purple'], void: ['void', ''],
    pass: ['passed', 'good'], passed: ['passed', 'good'], fail: ['failed', 'bad'], failed: ['failed', 'bad'],
    pending: ['under test', 'warn'], 'under test': ['under test', 'warn'], live: ['live', 'c-algorithm'],
    inconclusive: ['inconclusive', ''],
    resolved: ['resolved', 'purple'], long: ['long', 'good'], short: ['short', 'bad'],
    Buy: ['Buy', 'good'], Sell: ['Sell', 'bad'], 'No trade': ['No trade', ''],
  };
  function badge(value) { const b = BADGE[value] || [value, '']; return pill(b[0], b[1]); }
  function daysLabel(n) {
    if (!isNum(n)) return '';
    if (n === 0) return 'today';
    if (n < 0) return `${-n} day${n === -1 ? '' : 's'} ago`;
    return `in ${n} day${n === 1 ? '' : 's'}`;
  }
  const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  function withAlpha(hex, a) {
    const m = /^#([0-9a-f]{6})$/i.exec(hex);
    if (!m) return hex;
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }

  async function load(name) {
    if (DATA[name]) return DATA[name];
    const res = await fetch(`data/${name}.json`, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`Could not load ${name}.json (${res.status})`);
    DATA[name] = await res.json();
    return DATA[name];
  }

  const view = document.getElementById('view');
  const titleEl = document.getElementById('page-title');
  const subEl = document.getElementById('page-sub');
  const updatedEl = document.getElementById('updated');

  function setHead(title, sub) {
    titleEl.textContent = title;
    subEl.textContent = sub || '';
    document.title = title === 'Home' ? 'Ledger' : `${title} · Ledger`;
  }
  function setTab(tab) {
    document.querySelectorAll('.tabbar a').forEach((a) => {
      if (a.dataset.tab === tab) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
  }
  function destroyCharts() { while (charts.length) { try { charts.pop().destroy(); } catch (e) { /* ignore */ } } }
  function toast(msg, action, onAction) {
    const t = document.getElementById('toast');
    t.innerHTML = `<span>${esc(msg)}</span>${action ? `<button type="button" id="toast-action">${esc(action)}</button>` : ''}`;
    t.hidden = false;
    if (action) document.getElementById('toast-action').onclick = () => { t.hidden = true; onAction && onAction(); };
    else setTimeout(() => { t.hidden = true; }, 3500);
  }

  // ------------------------------------------------------------------ charts
  function chartDefaults() {
    const fg2 = cssVar('--fg-2'), grid = cssVar('--grid');
    Chart.defaults.color = fg2;
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.font.size = 11;
    Chart.defaults.borderColor = grid;
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.backgroundColor = cssVar('--surface-2');
    Chart.defaults.plugins.tooltip.titleColor = cssVar('--fg');
    Chart.defaults.plugins.tooltip.bodyColor = cssVar('--fg');
    Chart.defaults.plugins.tooltip.borderColor = cssVar('--line');
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.animation = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? false : { duration: 300 };
  }
  function mkChart(id, config) {
    const c = document.getElementById(id);
    if (!c || typeof Chart === 'undefined') return null;
    chartDefaults();
    const ch = new Chart(c.getContext('2d'), config);
    charts.push(ch);
    return ch;
  }
  const monthTick = (labels) => (v, i) => { const l = labels[i]; return (l && l.endsWith('-01')) || i === 0 ? l.slice(0, 4) : ''; };

  const PRE_LIVE_LABEL = 'Pre-live (not counted)';
  const ACCOUNT_LABEL = 'Account index (start = 100, live from Nov 2026)';
  const historyLabel = (base) => `History index (${fmtMonth(base)} = 100, not counted)`;
  const fmtUsd = (x) => (isNum(x) ? `US$${Math.round(x).toLocaleString('en-US')}` : '—');
  const phaseSuffix = (m) => (!m ? '' : m.live ? ' (live)' : m.pre_live ? ' (pre-live, not counted)' : '');

  function equityChart(id, months, opts = {}) {
    const histBase = opts.historyBase;
    const labels = months.map((m) => m.month);
    const isBt = (m) => !m.live && !m.pre_live;
    const bt = months.map((m) => (isBt(m) ? m.account_value : null));
    // join the pre-live series to the last backtest point, and the live series to the last earlier point
    const lastBt = months.map(isBt).lastIndexOf(true);
    const pre = months.map((m, i) => (m.pre_live || (i === lastBt && months.some((x) => x.pre_live)) ? m.account_value : null));
    // live account index on its own (right) axis: 100 at the end of the last pre-live month
    const live = months.map((m) => (isNum(m.account_index) ? m.account_index : null));
    const cBt = cssVar('--series-backtest'), cLive = cssVar('--series-live'), cPre = cssVar('--series-prelive');
    return mkChart(id, {
      type: 'line',
      data: { labels, datasets: [
        { label: `Backtest (test, evaluated once), ${historyLabel(histBase)}`, yAxisID: 'yh', data: bt, borderColor: cBt, backgroundColor: withAlpha(cBt, 0.12), fill: true, borderWidth: 1.6, pointRadius: 0, tension: 0.1, spanGaps: false },
        { label: `${PRE_LIVE_LABEL}, ${historyLabel(histBase)}`, yAxisID: 'yh', data: pre, borderColor: cPre, backgroundColor: withAlpha(cPre, 0.12), fill: true, borderWidth: 1.6, borderDash: [4, 3], pointRadius: (ctx) => (months[ctx.dataIndex] && months[ctx.dataIndex].pre_live ? 3 : 0), pointBackgroundColor: cPre, tension: 0.1, spanGaps: false },
        { label: ACCOUNT_LABEL, yAxisID: 'y', data: live, borderColor: cLive, backgroundColor: withAlpha(cLive, 0.18), fill: false, borderWidth: 2.2, pointRadius: (ctx) => (isNum(live[ctx.dataIndex]) && (ctx.dataIndex === labels.length - 1 || live.filter(isNum).length < 3) ? 3.5 : 0), pointBackgroundColor: cLive, tension: 0.1, spanGaps: false },
      ] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: { x: { grid: { display: false }, ticks: { autoSkip: false, maxRotation: 0, callback: monthTick(labels) } },
                  yh: { position: 'left', grid: { color: cssVar('--grid') }, ticks: { callback: (v) => fmtNum(v, 0) }, title: { display: true, text: historyLabel(histBase) } },
                  y: { position: 'right', grid: { display: false }, ticks: { color: cLive, callback: (v) => fmtNum(v, 1) }, title: { display: true, text: ACCOUNT_LABEL, color: cLive } } },
        plugins: { tooltip: { callbacks: { title: (it) => fmtMonth(it[0].label) + phaseSuffix(months[it[0].dataIndex]), label: (it) => `${it.dataset.label}: ${fmtNum(it.parsed.y, 1)}` } } } },
    });
  }

  function monthlyBarChart(id, months) {
    const labels = months.map((m) => m.month);
    const good = cssVar('--series-up'), bad = cssVar('--series-down'), live = cssVar('--series-live'), pre = cssVar('--series-prelive');
    return mkChart(id, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Net monthly return', data: months.map((m) => (isNum(m.net) ? m.net * 100 : null)),
        backgroundColor: months.map((m) => (m.live ? live : m.pre_live ? pre : withAlpha(m.net >= 0 ? good : bad, 0.75))),
        borderRadius: 2, maxBarThickness: 14 }] },
      options: { maintainAspectRatio: false,
        scales: { x: { grid: { display: false }, ticks: { autoSkip: false, maxRotation: 0, callback: monthTick(labels) } },
                  y: { grid: { color: cssVar('--grid') }, ticks: { callback: (v) => `${v}%` } } },
        plugins: { tooltip: { callbacks: { title: (it) => fmtMonth(it[0].label) + phaseSuffix(months[it[0].dataIndex]), label: (it) => fmtPct(it.parsed.y, 2, true) } } } },
    });
  }

  function drawdownChart(id, months) {
    const labels = months.map((m) => m.month);
    const bad = cssVar('--series-down');
    return mkChart(id, {
      type: 'line',
      data: { labels, datasets: [{ label: 'Drawdown', data: months.map((m) => m.drawdown_pct), borderColor: bad, backgroundColor: withAlpha(bad, 0.18), fill: true, borderWidth: 1.6, pointRadius: 0, tension: 0 }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: { x: { grid: { display: false }, ticks: { autoSkip: false, maxRotation: 0, callback: monthTick(labels) } },
                  y: { max: 0, grid: { color: cssVar('--grid') }, ticks: { callback: (v) => `${v}%` } } },
        plugins: { tooltip: { callbacks: { title: (it) => fmtMonth(it[0].label) + phaseSuffix(months[it[0].dataIndex]), label: (it) => fmtPct(it.parsed.y, 1) } } } },
    });
  }

  function calibrationChart(id, calib) {
    const sets = [['me', 'Me', cssVar('--series-me')], ['claude', 'Claude', cssVar('--series-claude')], ['market', 'Market', cssVar('--series-market')]];
    const datasets = sets.map(([k, label, color]) => ({
      type: 'scatter', label, data: (calib[k] || []).filter((b) => isNum(b.observed)).map((b) => ({ x: b.mean_forecast, y: b.observed, n: b.n })),
      backgroundColor: color, borderColor: cssVar('--surface'), borderWidth: 1.5, pointRadius: 6, pointHoverRadius: 8,
    }));
    datasets.push({ type: 'line', label: 'Perfect calibration', data: [{ x: 0, y: 0 }, { x: 100, y: 100 }], borderColor: cssVar('--muted'), borderDash: [4, 4], borderWidth: 1, pointRadius: 0 });
    return mkChart(id, {
      data: { datasets },
      options: { maintainAspectRatio: false,
        scales: { x: { min: 0, max: 100, title: { display: true, text: 'Forecast probability (%)' }, grid: { color: cssVar('--grid') }, ticks: { stepSize: 20 } },
                  y: { min: 0, max: 100, title: { display: true, text: 'Observed frequency (%)' }, grid: { color: cssVar('--grid') }, ticks: { stepSize: 20 } } },
        plugins: { tooltip: { callbacks: { label: (it) => `${it.dataset.label}: forecast ${fmtNum(it.parsed.x, 0)}%, observed ${fmtNum(it.parsed.y, 0)}% (n ${it.raw.n})` } } } },
    });
  }

  function brierChart(id, cum) {
    const labels = cum.ids;
    const sets = [['me', 'Me', cssVar('--series-me')], ['claude', 'Claude', cssVar('--series-claude')], ['market', 'Market', cssVar('--series-market')]];
    return mkChart(id, {
      type: 'line',
      data: { labels, datasets: sets.map(([k, label, color]) => ({ label, data: cum[k].running, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 3, tension: 0.1, spanGaps: true })) },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: { x: { grid: { display: false } }, y: { min: 0, suggestedMax: 0.5, grid: { color: cssVar('--grid') }, title: { display: true, text: 'Cumulative Brier (lower is better)' } } },
        plugins: { tooltip: { callbacks: { label: (it) => `${it.dataset.label}: ${fmtNum(it.parsed.y, 3)}` } } } },
    });
  }

  function sparkChart(id, series, color) {
    return mkChart(id, {
      type: 'line',
      data: { labels: series.map((p) => p[0]), datasets: [{ data: series.map((p) => p[1]), borderColor: color, backgroundColor: withAlpha(color, 0.15), fill: true, borderWidth: 1.6, pointRadius: 0, tension: 0.15 }] },
      options: { maintainAspectRatio: false, scales: { x: { display: false }, y: { grid: { color: cssVar('--grid') }, ticks: { maxTicksLimit: 4 } } },
        plugins: { tooltip: { callbacks: { title: (it) => fmtDate(it[0].label), label: (it) => fmtNum(it.parsed.y, 1) } } } },
    });
  }

  function legend(items) {
    return `<div class="legend">${items.map(([label, v]) => `<span><i style="background:${cssVar(v)}"></i>${esc(label)}</span>`).join('')}</div>`;
  }

  // ------------------------------------------------------------------ pages
  const fmtLevel = (v, unit) => (!isNum(v) ? '—' : (unit === 'bp' ? `${fmtNum(v, Number.isInteger(Math.round(v * 10) / 10) ? 0 : 1)}bp` : unit && unit.startsWith('%') ? `${fmtNum(v, 2)}%` : fmtNum(v, Math.abs(v) >= 100 ? 1 : 4)));
  // futures / options (ledger/derivs.py): P&L in % only (settlements are licensed); options are a model estimate
  const valuationText = (d) => (d.valuation === 'entry' ? 'at entry' : d.valuation || 'settlement');
  function derivLive(d) {
    const v = d.derivative;
    return `${isNum(d.live_pnl_pct) ? `<b class="${signClass(d.live_pnl_pct)}">live P&L ${fmtPct(d.live_pnl_pct, 2, true)}</b>` : 'no settlement yet'} · ${pill(valuationText(d), d.valuation === 'model estimate' ? 'warn' : '')}${d.mark_date ? ` ${fmtDate(d.mark_date)}` : ''}${v && v.proxy === 'yes' ? ` ${pill('proxy', 'warn')}` : ''}`;
  }
  function liveLabel(d) {
    if (d.status === 'open' && d.derivative) return ` · ${derivLive(d)}`;
    if (d.status !== 'open' || !d.mark_instrument) return '';
    if (!isNum(d.mark)) return ' · no mark yet';
    const when = `${fmtDate(d.mark_date)}${d.mark_frequency === 'monthly' ? ', monthly' : ''}`;
    return isNum(d.live_pnl_pct) ? ` · <b class="${signClass(d.live_pnl_pct)}">live P&L ${fmtPct(d.live_pnl_pct, 2, true)}</b> at ${fmtLevel(d.mark, d.mark_unit)} (${when})`
      : ` · mark ${fmtLevel(d.mark, d.mark_unit)} (${when})`;
  }
  function decisionRow(d) {
    const score = d.status === 'resolved' ? ` · Brier ${fmtNum(d.brier, 3)}${isNum(d.pnl_pct) ? ` · P&L ${fmtPct(d.pnl_pct, 2, true)}` : ''}${d.auto_resolved ? ' · auto' : ''}` : (isNum(d.days_to_horizon) ? ` · horizon ${daysLabel(d.days_to_horizon)}` : '') + liveLabel(d);
    return `<a class="row-link c-decisions" href="#/decisions/${esc(d.id)}">
      <div class="row-top"><span class="row-title">${esc(d.instrument)} ${badge(d.action)}</span><span class="mono muted small">${esc(d.id)}</span></div>
      <div class="row-meta"><b>${esc(d.country)}</b> · ${fmtDate(d.date)} · ${fmtPct(d.size_pct, 1)} at risk · p ${fmtProb(d.probability)} ${d.status === 'resolved' ? badge(d.outcome) : badge('open')}${score}</div></a>`;
  }

  async function pageDecisions(id) {
    const dec = await load('decisions');
    if (id) return decisionDetail(dec, id);
    const f = filters.decisions;
    setHead('Decisions', `${dec.summary.n} logged · ${dec.summary.open} open · ${dec.summary.resolved} resolved`);
    const items = dec.items.filter((d) => (!f.country || d.country === f.country) && (!f.status || d.status === f.status) && (!f.outcome || d.outcome === f.outcome));
    const OUT_LABEL = { right: 'won', wrong: 'lost' };
    const sel = (name, label, opts, cur) => `<select id="f-${name}" aria-label="${esc(label)}"><option value="">${esc(label)}: all</option>${opts.map((o) => `<option value="${esc(o)}" ${o === cur ? 'selected' : ''}>${esc(OUT_LABEL[o] || o)}</option>`).join('')}</select>`;
    view.innerHTML = `
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Resolved</span><span class="v">${dec.summary.resolved}</span><span class="s">${dec.summary.right} won · ${dec.summary.wrong} lost</span></div>
          <div class="stat"><span class="k">Brier (mine)</span><span class="v">${fmtNum(dec.summary.brier, 3)}</span><span class="s">${dec.summary.brier_n ? `over ${dec.summary.brier_n} resolved` : 'none resolved yet'}</span></div>
          <div class="stat"><span class="k">P&L logged</span><span class="v ${signClass(dec.summary.pnl_pct_total)}">${fmtPct(dec.summary.pnl_pct_total, 2, true)}</span><span class="s">% of account, resolved positions</span></div>
          <div class="stat"><span class="k">Open</span><span class="v">${dec.summary.open}</span><span class="s">of ${dec.summary.n}</span></div>
        </div>
      </section>
      <section class="section">
        <div class="filters">${sel('country', 'Country', dec.summary.countries, f.country)}${sel('status', 'Status', ['open', 'resolved'], f.status)}${sel('outcome', 'Outcome', dec.summary.outcomes, f.outcome)}</div>
        <div class="list">${items.length ? items.map(decisionRow).join('') : '<p class="empty">No decisions match these filters.</p>'}</div>
        <div class="btn-row">${clerkButton(meta)}<a class="btn" href="${esc(meta.issue_forms.resolve)}" target="_blank" rel="noopener">Resolve</a></div>
      </section>`;
    ['country', 'status', 'outcome'].forEach((k) => { document.getElementById(`f-${k}`).onchange = (e) => { f[k] = e.target.value; pageDecisions(); }; });
  }

  function field(k, v, cls = '') { return `<div class="field"><span class="k">${esc(k)}</span><span class="v ${cls}">${v == null || v === '' ? '<span class="muted">—</span>' : v}</span></div>`; }

  function decisionDetail(dec, id) {
    const d = dec.items.find((x) => x.id === id);
    if (!d) { setHead('Decision', ''); view.innerHTML = `<p class="empty">No decision with id ${esc(id)}.</p><a class="back" href="#/decisions">← Decisions</a>`; return; }
    setHead(`${d.id} · ${d.instrument}`, `${d.country} · ${fmtDate(d.date)} · ${d.status}${d.outcome ? ` (${d.outcome})` : ''}`);
    const kelly = isNum(d.kelly_cap_pct) ? `${fmtPct(d.kelly_cap_pct, 2)} of account (half of quarter-Kelly at ${fmtProb(d.probability)}, even odds)` : '—';
    const scoreBlock = d.status === 'resolved' ? `
      <div class="stats">
        <div class="stat"><span class="k">Outcome</span><span class="v sm">${badge(d.outcome)}</span><span class="s">resolved ${fmtDate(d.resolved_date)}</span></div>
        <div class="stat"><span class="k">Brier (mine)</span><span class="v">${fmtNum(d.brier, 3)}</span><span class="s">p ${fmtProb(d.probability)} → ${d.outcome01 === 1 ? 'right' : d.outcome01 === 0 ? 'wrong' : 'n/a'}</span></div>
        <div class="stat"><span class="k">Brier (Claude)</span><span class="v">${fmtNum(d.brier_claude, 3)}</span><span class="s">${isNum(d.claude_probability) ? `p ${fmtProb(d.claude_probability)}` : 'no Claude probability'}</span></div>
        <div class="stat"><span class="k">P&L</span><span class="v ${signClass(d.pnl_pct)}">${fmtPct(d.pnl_pct, 2, true)}</span><span class="s">${isNum(d.exit_price) ? `exit ${fmtNum(d.exit_price, 2)}` : 'not computable'}</span></div>
      </div>` : `
      <div class="stats">
        <div class="stat"><span class="k">Status</span><span class="v sm">${badge('open')}</span><span class="s">horizon ${fmtDate(d.horizon)} (${daysLabel(d.days_to_horizon)})</span></div>
        <div class="stat"><span class="k">My probability</span><span class="v">${fmtProb(d.probability)}</span><span class="s">${isNum(d.claude_probability) ? `Claude ${fmtProb(d.claude_probability)}` : 'that the view is right'}</span></div>
        <div class="stat"><span class="k">At risk</span><span class="v">${fmtPct(d.size_pct, 2)}</span><span class="s">of account (cap 2%) · ${d.position_type === 'event' ? 'event bet' : 'continuous'}</span></div>
        <div class="stat"><span class="k">Live P&L</span><span class="v ${signClass(d.live_pnl_pct)}">${isNum(d.live_pnl_pct) ? fmtPct(d.live_pnl_pct, 2, true) : '—'}</span><span class="s">${d.derivative ? `${esc(valuationText(d))}${d.mark_date ? `, ${fmtDate(d.mark_date)}` : ''}` : isNum(d.mark) ? `mark ${fmtLevel(d.mark, d.mark_unit)}, ${fmtDate(d.mark_date)}${d.mark_frequency === 'monthly' ? ' (monthly)' : ''}` : d.mark_instrument ? 'no mark yet' : d.kind === 'position' ? 'instrument not in the registry' : 'no position'}</span></div>
      </div>`;
    const dv = d.derivative;
    const derivNote = dv ? `${esc(dv.structure)} on ${esc(dv.product)} ${esc(dv.contract_month)} (${esc(dv.exchange)}${dv.legs ? `: ${esc(dv.legs.split('|').join(', '))}` : ''}${dv.option_expiry ? `, expiry ${fmtDate(dv.option_expiry)}` : ''}) · marked at the ${esc(dv.mark_source)}${dv.proxy === 'yes' ? ' <b>(proxy)</b>' : ''}${dv.structure !== 'future' ? ` · <b>model estimate</b>: Black-76 with implied vol ${esc(dv.iv_entry_pct)}% at entry (${esc(dv.iv_source)}); intrinsic value from expiry · ${isNum(Number(dv.risk_per_unit)) && dv.risk_per_unit !== '' ? `maximum loss ${esc(dv.risk_per_unit)} per unit (the premium)` : 'maximum loss: the premium, priced at the entry-day settlement (kept private: licensed)'}` : ''} · <span class="muted">settlement prices are licensed and kept privately; only P&L in % is published</span>` : '';
    const markNote = dv ? derivNote : d.mark_instrument ? `${esc(d.mark_instrument)}${isNum(d.mark) ? ` = ${fmtLevel(d.mark, d.mark_unit)} on ${fmtDate(d.mark_date)}` : ' (no mark yet)'}${d.mark_frequency === 'monthly' ? ' · <b>marked monthly</b> (no free daily source; see Marks)' : ''}${d.mark_source ? ` · ${esc(d.mark_source)}` : ''}${d.mark_source_url && /^https?:/.test(d.mark_source_url) ? ` · <a href="${esc(d.mark_source_url.split(' ;')[0])}" target="_blank" rel="noopener">source</a>` : ''}${d.mark_note ? ` · <span class="muted">${esc(d.mark_note)}</span>` : ''}${!isNum(d.live_pnl_pct) && d.kind === 'position' && isNum(d.mark) && !isNum(d.entry_level) ? ' · P&L needs a numeric entry level' : ''}` : (d.kind === 'position' ? 'instrument not matched in data/ledger/instruments.csv' : '');
    view.innerHTML = `
      <a class="back" href="#/decisions">← Decisions</a>
      ${scoreBlock}
      <section class="card rule record">
        <h2>Decision record</h2>
        ${field('Date', fmtDate(d.date))}${field('Country', esc(d.country))}${field('Instrument', esc(d.instrument))}
        ${field('Action', badge(d.action))}
        ${field('Size (% of account at risk)', fmtPct(d.size_pct, 2))}
        ${field('Probability my view is right', fmtProb(d.probability) + (isNum(d.claude_probability) ? ` <span class="muted">(Claude ${fmtProb(d.claude_probability)})</span>` : ''))}
        ${field('Horizon', fmtDate(d.horizon))}
        ${field('Entry trigger', esc(d.entry_trigger))}
        ${field('Stop / exit if wrong', esc(d.stop) + (isNum(d.stop_level) ? ` <span class="muted">(level ${fmtNum(d.stop_level, 2)})</span>` : ''))}
        ${field('Thesis', esc(d.thesis))}
        ${field('Key factors', esc(d.key_factors))}
        ${field('What would change my mind', esc(d.change_mind))}
        ${field('How this differs from market consensus', esc(d.vs_consensus))}
      </section>
      <section class="card record">
        <h2>Sizing and resolution</h2>
        ${field('Event-bet sizing rule', esc(kelly))}
        ${field('Entry level (for P&L)', isNum(d.entry_level) ? fmtNum(d.entry_level, 4) : '<span class="muted">not recorded; P&L needs entry, stop and exit levels or a P&L entered at resolution</span>')}
        ${d.status === 'open' ? field('Live mark', markNote || '<span class="muted">—</span>') : ''}
        ${field('Exit price / result', isNum(d.exit_price) ? fmtNum(d.exit_price, 4) : esc(d.exit_price || ''))}
        ${field('Resolution note', linkify(d.resolution_note || '') + (d.auto_resolved ? ` ${pill('auto-resolved', 'purple')}` : ''))}
        ${field('Logged', `${fmtDate(d.logged_at)}${d.issue_url ? ` · <a href="${esc(d.issue_url)}" target="_blank" rel="noopener">issue #${esc(d.issue)}</a>` : ' · seed entry'}`)}
      </section>
      ${d.status === 'open' ? `<div class="btn-row"><a class="btn primary" href="${esc(meta.issue_forms.resolve)}" target="_blank" rel="noopener">Resolve ${esc(d.id)}</a></div>` : ''}`;
  }

  function capacitySection(c, label) {
    if (!c || !c.rows) return '';
    const rows = c.rows.map((r) => `<tr class="${r.flags.length ? 'flag' : ''}"><td>${esc(r.instrument)}</td><td class="num">${fmtUsd(r.notional_usd)}</td>
      <td class="num">${r.adv_usd ? fmtUsd(r.adv_usd) : '—'}</td><td class="num ${r.flags.includes('adv') ? 'bad' : ''}">${fmtPct(r.pct_adv, 1)}</td>
      <td class="num ${r.flags.includes('limit') ? 'bad' : ''}">${isNum(r.pct_limit) ? fmtPct(r.pct_limit, 0) : '—'}</td><td class="num">${fmtNum(r.impact_bp_full, 1)}bp</td>
      <td class="wrap small">${esc(r.adv_status || '')}</td></tr>`).join('');
    return `<section class="section"><h2>Capacity, ${esc(label)} at ${fmtUsd(c.capital_usd)}</h2>
      <p class="small">${c.flagged.length ? `<b class="bad">Flagged: ${esc(c.flagged.join(', '))}</b>` : 'No position above 10% of ADV or near a position limit.'}</p>
      <div class="table-wrap"><table><thead><tr><th>Instrument</th><th class="num">Notional</th><th class="num">ADV</th><th class="num">% ADV</th><th class="num">% limit</th><th class="num">Impact</th><th>ADV source</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="small muted">${esc(c.method)} ${esc(c.impact_note || '')}</p></section>`;
  }

  function nextMonth(m) { if (!m) return null; const [y, mm] = m.split('-').map(Number); return mm === 12 ? `${y + 1}-01` : `${y}-${String(mm + 1).padStart(2, '0')}`; }

  function probTrack(f) {
    const dot = (v, cls, label) => (isNum(v) ? `<i class="dot ${cls}" style="left:${v}%" title="${esc(label)} ${fmtProb(v)}"></i>` : '');
    return `<div class="ptrack" aria-hidden="true">${dot(f.market_prob, 'market', 'Market')}${dot(f.claude_prob, 'claude', 'Claude')}${dot(f.my_prob, 'me', 'Me')}</div>`;
  }

  async function pageForecasts() {
    const fc = await load('forecasts');
    setHead('Forecasts', `${fc.summary.n} calls · ${fc.summary.open} open · ${fc.summary.resolved} resolved · scored by Brier only`);
    const cum = fc.cumulative;
    const rows = fc.items.slice().reverse().map((f) => `
      <div class="card fcard">
        <div class="row-top"><span class="row-title">${esc(f.question)}</span><span class="mono muted small">${esc(f.id)}</span></div>
        <div class="row-meta"><b>${esc(f.country)}</b> · ${fmtDate(f.date)} · resolves ${fmtDate(f.resolution_date)} ${f.status === 'resolved' ? badge(f.outcome) : badge('open')}</div>
        ${probTrack(f)}
        <div class="probs"><span><i style="background:var(--series-me)"></i>Me <b>${fmtProb(f.my_prob)}</b></span><span><i style="background:var(--series-claude)"></i>Claude <b>${fmtProb(f.claude_prob)}</b></span><span><i style="background:var(--series-market)"></i>Market <b>${fmtProb(f.market_prob)}</b></span></div>
        <div class="row-meta">${esc(f.market_source)}${f.resolution_source ? ` · resolves by <b>${esc(f.resolution_source)}</b>` : ''}${f.status === 'resolved' ? ` · Brier me ${fmtNum(f.brier_me, 3)} · Claude ${fmtNum(f.brier_claude, 3)} · market ${fmtNum(f.brier_market, 3)}${f.auto_resolved ? ` ${pill('auto-resolved', 'purple')}` : ''}` : ''}${f.result ? ` · ${linkify(f.result)}` : ''}</div>
      </div>`).join('');
    const hasResolved = fc.summary.resolved > 0;
    view.innerHTML = `
      <style>
        .ptrack { position: relative; height: 10px; margin: 10px 0 6px; border-radius: 5px; background: linear-gradient(90deg, var(--surface-2), var(--line)); }
        .ptrack::before { content: ""; position: absolute; left: 50%; top: -3px; bottom: -3px; width: 1px; background: var(--muted); }
        .ptrack .dot { position: absolute; top: -3px; width: 16px; height: 16px; margin-left: -8px; border-radius: 50%; border: 2px solid var(--surface); }
        .dot.me { background: var(--series-me); z-index: 3; } .dot.claude { background: var(--series-claude); z-index: 2; } .dot.market { background: var(--series-market); }
        .probs { display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.86rem; color: var(--fg-2); } .probs i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 4px; } .probs b { color: var(--fg); }
        .fcard { display: grid; gap: 4px; border-left: 5px solid var(--c-forecasts); }
      </style>
      <section class="section"><div class="card notice"><b>Forecasts are scored by Brier only.</b> They are not positions: they never enter any book's P&L and never appear on the Home charts.</div></section>
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Brier, me</span><span class="v">${fmtNum(cum.me.mean, 3)}</span><span class="s">${cum.me.n} resolved</span></div>
          <div class="stat"><span class="k">Brier, Claude</span><span class="v">${fmtNum(cum.claude_vs.claude, 3)}</span><span class="s">${cum.claude_vs.n} with a Claude call</span></div>
          <div class="stat"><span class="k">Brier, market</span><span class="v">${fmtNum(cum.market.mean, 3)}</span><span class="s">${cum.market.n} resolved</span></div>
          <div class="stat"><span class="k">Open</span><span class="v">${fc.summary.open}</span><span class="s">of ${fc.summary.n} calls</span></div>
        </div>
        <p class="small muted">Brier score = (probability − outcome)², averaged over resolved calls; 0 is perfect, 0.25 is a coin flip. All three are scored on the same resolved questions. Where Claude gave no number, the Claude column uses only the calls it did price, with my and the market's scores on that same subset: me ${fmtNum(cum.claude_vs.me, 3)}, market ${fmtNum(cum.claude_vs.market, 3)}.</p>
      </section>
      <section class="section">
        <h2>Calibration</h2>
        <div class="card"><div class="chart"><canvas id="c-calib"></canvas></div>${legend([['Me', '--series-me'], ['Claude', '--series-claude'], ['Market', '--series-market']])}
        <p class="chart-note">${hasResolved ? 'Each point is a 20-point probability bin: mean stated probability against how often those calls came true.' : 'Points appear as calls resolve: each is a 20-point probability bin, mean stated probability against how often those calls came true. Nothing has resolved yet.'}</p></div>
      </section>
      <section class="section">
        <h2>Cumulative Brier</h2>
        <div class="card">${hasResolved ? '<div class="chart"><canvas id="c-brier"></canvas></div>' + legend([['Me', '--series-me'], ['Claude', '--series-claude'], ['Market', '--series-market']]) : '<p class="empty">Running scores appear after the first call resolves.</p>'}</div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Calls</h2><span class="muted small">newest first</span></div>
        <div class="list">${rows || '<p class="empty">No forecasts yet.</p>'}</div>
        <div class="btn-row"><a class="btn primary" href="${esc(meta.issue_forms.forecast)}" target="_blank" rel="noopener">Log a forecast</a><a class="btn" href="${esc(meta.issue_forms.resolve)}" target="_blank" rel="noopener">Resolve</a></div>
      </section>`;
    calibrationChart('c-calib', fc.calibration);
    if (hasResolved) brierChart('c-brier', cum);
  }

  async function pageTrials() {
    const tr = await load('trials');
    setHead('Trials', `${tr.summary.n} trials · ${tr.summary.pass} pass · ${tr.summary.fail} fail · trials.csv updated ${fmtDate(tr.updated)}`);
    const rows = tr.items.map((t) => `
      <details class="card" style="border-left:5px solid ${t.status === 'pass' ? 'var(--good)' : t.status === 'fail' ? 'var(--bad)' : 'var(--warn-fill)'}">
        <summary style="cursor:pointer;min-height:44px;display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span class="mono" style="color:var(--c-trials);font-weight:700">${esc(t.trial_id)}</span>${badge(t.status)}<span class="row-title" style="flex:1 1 200px;min-width:0">${esc(t.name)}</span><span class="muted small">${fmtDate(t.date_tested)}</span></summary>
        <dl class="kv" style="margin-top:10px">
          <dt>Hypothesis</dt><dd>${esc(t.hypothesis)}</dd>
          <dt>Result</dt><dd>${esc(t.result)}</dd>
          <dt>Decision</dt><dd>${esc(t.decision)}</dd>
          <dt>Design sample</dt><dd>${esc(t.design_sample)}</dd>
          <dt>Test sample</dt><dd>${esc(t.test_sample)}</dd>
          <dt>Test type</dt><dd>${esc(t.test_type)}</dd>
          <dt>Group</dt><dd>${esc(t.trial_group)} · ${t.counted ? 'counted in the spec’s N = 7' : 'not counted in N = 7'}</dd>
          <dt>Code</dt><dd>${esc(t.repo)} · <span class="mono">${esc(t.code_ref)}</span></dd>
          <dt>Source</dt><dd>${esc(t.source)}</dd>
          ${t.notes ? `<dt>Notes</dt><dd>${esc(t.notes)}</dd>` : ''}
        </dl>
      </details>`).join('');
    view.innerHTML = `
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Passed</span><span class="v good">${tr.summary.pass}</span><span class="s">kept or frozen</span></div>
          <div class="stat"><span class="k">Failed</span><span class="v bad">${tr.summary.fail}</span><span class="s">rejected, null or not adopted</span></div>
          <div class="stat"><span class="k">Under test</span><span class="v warn">${tr.summary.pending}</span><span class="s">not yet run</span></div>
          <div class="stat"><span class="k">Counted (N = 7)</span><span class="v">${tr.summary.counted_n7}</span><span class="s">in the spec's multiple-testing count</span></div>
        </div>
      </section>
      <section class="section"><div class="list">${rows}</div><p class="small muted">Tap a trial to read the full ledger row. Source: trials.csv.</p></section>`;
  }

  async function pageElections() {
    const el = await load('elections');
    const f = filters.elections;
    setHead('Elections', `${el.upcoming.length} upcoming · ${el.n_past} past · ${el.signals.filter((s) => s.active).length} live signals`);
    const up = el.upcoming.length ? el.upcoming.map((e) => `
      <div class="card rule"><div class="row-top"><span class="row-title">${esc(e.event)}</span><span class="muted small">${fmtDate(e.date)}</span></div>
      <div class="row-meta"><b>${esc(e.country)}</b> · ${esc(e.type || '')}${e.round ? ` · round ${esc(e.round)}` : ''}${e.cand_a ? ` · ${esc(e.cand_a)} vs ${esc(e.cand_b)}` : ''}${isNum(e.poll_margin_pp) ? ` · poll margin ${fmtNum(e.poll_margin_pp, 1)}pp` : ''}${isNum(e.odds_prob_favourite) ? ` · odds ${fmtProb(e.odds_prob_favourite * 100)} ${esc(e.odds_favourite || '')}` : ''}</div>
      ${e.notes ? `<div class="row-meta">${esc(e.notes)}</div>` : ''}</div>`).join('') : '<p class="empty">No upcoming election in the calendar.</p>';
    const active = el.signals.filter((s) => s.active);
    const sig = active.length ? active.map((s, i) => `
      <div class="card"><div class="row-top"><span class="row-title">${esc(s.country)} · ${esc(s.label)}</span><span class="row-title">${fmtNum(s.last_value, 1)}</span></div>
      <div class="row-meta">election ${fmtDate(s.election_date)} · last ${fmtDate(s.last)} · ${s.n} observations</div>
      <div class="chart" style="height:120px;margin-top:6px"><canvas id="c-sig-${i}"></canvas></div></div>`).join('') : '<p class="empty">No signal within 120 days of a vote.</p>';
    const past = el.past.filter((e) => !f.country || e.country === f.country);
    const pastRows = past.map((e) => `<tr><td>${fmtDate(e.date)}</td><td>${esc(e.country)}</td><td class="wrap">${esc(e.event)}${e.round && e.round !== '1' ? ` (round ${esc(e.round)})` : ''}</td><td class="num">${fmtNum(e.poll_margin_pp, 1)}</td><td class="num">${fmtNum(e.actual_margin_pp, 1)}</td><td class="num ${isNum(e.actual_margin_pp) && isNum(e.poll_margin_pp) ? signClass(e.actual_margin_pp - e.poll_margin_pp) : ''}">${isNum(e.actual_margin_pp) && isNum(e.poll_margin_pp) ? fmtNum(e.actual_margin_pp - e.poll_margin_pp, 1) : '—'}</td><td class="wrap">${esc(e.winner)}</td><td class="num">${isNum(e.odds_prob_favourite) ? fmtProb(e.odds_prob_favourite * 100) : '—'}</td></tr>`).join('');
    const older = el.signals.filter((s) => !s.active);
    view.innerHTML = `
      <section class="section"><h2>Calendar</h2><div class="list">${up}</div></section>
      <section class="section"><h2>Live signals</h2><div class="list">${sig}</div><p class="small muted">Polls are the leading candidate's two-party margin from the poll-of-polls; odds are the favourite's prediction-market win probability. Source: ${esc(el.sources.join(', '))}.</p></section>
      <section class="section">
        <div class="section-head"><h2>Past elections</h2><span class="muted small">${el.n_past} in the study</span></div>
        <div class="filters"><select id="f-ecountry" aria-label="Country"><option value="">Country: all</option>${el.countries.map((c) => `<option value="${esc(c)}" ${c === f.country ? 'selected' : ''}>${esc(c)}</option>`).join('')}</select></div>
        <div class="table-wrap"><table><thead><tr><th>Vote</th><th>Country</th><th>Election</th><th class="num">Poll margin</th><th class="num">Actual</th><th class="num">Surprise</th><th>Winner</th><th class="num">Odds fav.</th></tr></thead><tbody>${pastRows || '<tr><td colspan="8" class="muted">No elections for this filter.</td></tr>'}</tbody></table></div>
        <p class="small muted">Margins in percentage points for the leading candidate (cand_a); surprise = actual − final poll. Showing the latest ${el.past.length}.</p>
      </section>
      ${older.length ? `<section class="section"><h2>Earlier signal series</h2><div class="table-wrap"><table class="compact"><thead><tr><th>Country</th><th>Election</th><th>Signal</th><th class="num">Last value</th><th>Last date</th><th class="num">Obs.</th></tr></thead><tbody>${older.map((s) => `<tr><td>${esc(s.country)}</td><td>${fmtDate(s.election_date)}</td><td class="wrap">${esc(s.label)}</td><td class="num">${fmtNum(s.last_value, 1)}</td><td>${fmtDate(s.last)}</td><td class="num">${s.n}</td></tr>`).join('')}</tbody></table></div></section>` : ''}`;
    document.getElementById('f-ecountry').onchange = (e) => { f.country = e.target.value; pageElections(); };
    active.forEach((s, i) => sparkChart(`c-sig-${i}`, s.series, cssVar(s.kind === 'odds' ? '--series-claude' : '--series-me')));
  }

  function reportRow(r) {
    return `<a class="row-link c-reports" href="#/reports/${esc(r.id)}"><div class="row-top"><span class="row-title">${esc(r.title)}</span><span class="muted small">${fmtDate(r.date)}</span></div>
      <div class="row-meta">${pill(r.type, 'c-reports')} <b>${esc(r.country)}</b> · ${r.format.toUpperCase()}${r.words ? ` · ${r.words.toLocaleString('en-GB')} words` : ''}</div></a>`;
  }

  async function pageReports(id) {
    const rp = await load('reports');
    if (id) return reportDetail(rp, id);
    const f = filters.reports;
    setHead('Reports', `${rp.items.length} in the archive`);
    const items = rp.items.filter((r) => (!f.type || r.type === f.type) && (!f.country || r.country === f.country));
    const sel = (name, label, opts, cur) => `<select id="f-r${name}" aria-label="${esc(label)}"><option value="">${esc(label)}: all</option>${opts.map((o) => `<option value="${esc(o)}" ${o === cur ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
    view.innerHTML = `
      <section class="section">
        <div class="filters">${sel('type', 'Type', rp.types, f.type)}${sel('country', 'Country', rp.countries, f.country)}</div>
        <div class="list">${items.length ? items.map(reportRow).join('') : '<p class="empty">No reports match these filters.</p>'}</div>
        <div class="btn-row"><a class="btn primary" href="${esc(meta.issue_forms.report)}" target="_blank" rel="noopener">Add a report</a></div>
      </section>`;
    ['type', 'country'].forEach((k) => { document.getElementById(`f-r${k}`).onchange = (e) => { f[k] = e.target.value; pageReports(); }; });
  }

  async function reportDetail(rp, id) {
    const r = rp.items.find((x) => x.id === id);
    if (!r) { setHead('Report', ''); view.innerHTML = `<p class="empty">No report with id ${esc(id)}.</p><a class="back" href="#/reports">← Reports</a>`; return; }
    setHead(r.title, `${r.type} · ${r.country} · ${fmtDate(r.date)}`);
    const head = `<a class="back" href="#/reports">← Reports</a><div class="row-meta">${pill(r.type, 'c-reports')} <b>${esc(r.country)}</b> · ${fmtDate(r.date)} · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">source file</a>${r.issue_url ? ` · <a href="${esc(r.issue_url)}" target="_blank" rel="noopener">issue</a>` : ''}</div>`;
    if (r.format === 'pdf') {
      view.innerHTML = `${head}<iframe class="pdf-frame" src="${esc(r.file)}" title="${esc(r.title)}"></iframe><div class="btn-row"><a class="btn" href="${esc(r.file)}" target="_blank" rel="noopener">Open the PDF</a></div>`;
      return;
    }
    view.innerHTML = `${head}<article class="card prose" id="report-body"><p class="muted">Loading…</p></article>`;
    try {
      const res = await fetch(r.file, { cache: 'no-cache' });
      const md = await res.text();
      const html = (typeof marked !== 'undefined') ? marked.parse(md, { gfm: true }) : `<pre>${esc(md)}</pre>`;
      document.getElementById('report-body').innerHTML = html;
      document.querySelectorAll('#report-body a[href^="http"]').forEach((a) => { a.target = '_blank'; a.rel = 'noopener'; });
    } catch (e) {
      document.getElementById('report-body').innerHTML = `<p class="bad">Could not load the report (${esc(e.message)}). It may not be cached for offline use yet.</p>`;
    }
  }

  async function pageMarks() {
    const mk = await load('marks');
    const s = mk.summary;
    setHead('Marks', `${s.marked} of ${s.n} instruments marked · ${s.daily} daily · ${s.monthly} monthly · last fetch ${fmtDateTime(s.last_fetch)}`);
    const freqPill = (i) => (i.frequency === 'monthly' ? pill('monthly', 'warn') : i.frequency === 'daily' ? pill('daily', 'good') : pill(i.frequency || 'none', ''));
    const rows = mk.items.map((i) => `<tr><td><span class="mono">${esc(i.instrument)}</span>${i.book === 'leg' ? ' <span class="muted small">leg</span>' : ''}</td><td class="wrap">${esc(i.country)}</td>
      <td class="num">${isNum(i.value) ? fmtLevel(i.value, i.unit) : '—'}</td><td>${fmtDate(i.date)}${i.stale ? ` ${pill('stale', 'bad')}` : ''}</td><td>${freqPill(i)}</td>
      <td class="wrap small">${esc(i.source)}${i.source_url && /^https?:/.test(i.source_url) ? ` · <a href="${esc(i.source_url.split(' ;')[0])}" target="_blank" rel="noopener">link</a>` : ''}${i.note ? `<br><span class="muted">${esc(i.note)}</span>` : ''}</td></tr>`).join('');
    const monthly = mk.items.filter((i) => i.registry_frequency === 'monthly');
    view.innerHTML = `
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Marked</span><span class="v">${s.marked}</span><span class="s">of ${s.n} registry rows</span></div>
          <div class="stat"><span class="k">Daily</span><span class="v good">${s.daily}</span><span class="s">free official daily source</span></div>
          <div class="stat"><span class="k">Monthly</span><span class="v warn">${s.monthly}</span><span class="s">no free daily source</span></div>
          <div class="stat"><span class="k">Stale</span><span class="v ${s.stale ? 'bad' : ''}">${s.stale}</span><span class="s">daily mark older than 7 days</span></div>
        </div>
        <p class="small muted">Every open decision is marked to market each morning by the <span class="mono">ledger-daily</span> workflow from <span class="mono">${esc(mk.registry)}</span>; marks are kept in <span class="mono">${esc(mk.marks_file)}</span> (${mk.n_rows} rows). A mark carries the source's own observation date. ${monthly.length ? `<b>Marked monthly, not daily:</b> ${monthly.map((i) => i.instrument).join(', ')} (no reachable free daily source; the table says why).` : ''}</p>
      </section>
      <section class="section">
        <h2>Latest marks</h2>
        <div class="table-wrap"><table><thead><tr><th>Instrument</th><th>Country</th><th class="num">Mark</th><th>Date</th><th>Freq.</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></div>
      </section>`;
  }

  async function pageScreener() {
    const sc = await load('screener');
    if (!sc.available) { setHead('Screener', 'Built after each monthly rebalance'); view.innerHTML = '<p class="empty">The screener appears after the next monthly rebalance.</p>'; return; }
    setHead('Screener', `After the ${fmtMonth(sc.as_of)} rebalance · generated ${fmtDate(sc.generated)} · ${sc.rows.length} instruments`);
    const rk = (r) => (isNum(r) ? r : '—');
    const table = (book) => {
      const rows = sc.rows.filter((r) => r.book === book).sort((a, b) => (a.rank_composite == null) - (b.rank_composite == null) || (a.rank_composite || 0) - (b.rank_composite || 0));
      return `<div class="table-wrap"><table class="compact"><thead><tr><th>Country</th><th>Instr.</th><th class="num">Carry</th><th class="num">Real</th><th class="num">Value</th><th class="num">Trend</th><th class="num">Rk C</th><th class="num">Rk V</th><th class="num">Rk T</th><th class="num">Rk comp.</th><th>Position</th><th class="num">Month</th><th>Election</th><th>Rating</th></tr></thead><tbody>${rows.map((r) => `
        <tr><td class="wrap">${esc(r.country)}</td><td><span class="mono">${esc(r.instrument)}</span>${r.stale || !r.data_month ? ` <span class="muted small" title="latest data ${esc(r.data_month || 'none')}">*${esc(r.data_month ? fmtMonth(r.data_month) : 'no data')}</span>` : ''}</td>
        <td class="num">${fmtNum(r.carry, 2)}</td><td class="num">${fmtNum(r.real_carry, 2)}</td><td class="num">${fmtNum(r.value, book === 'fx' ? 3 : 0)}</td><td class="num">${fmtNum(r.trend, 2)}</td>
        <td class="num">${rk(r.rank_carry)}</td><td class="num">${rk(r.rank_value)}</td><td class="num">${rk(r.rank_trend)}</td><td class="num"><b>${rk(r.rank_composite)}</b></td>
        <td>${r.position !== 'none' ? `${badge(r.position)} ${fmtPct(r.size_pct_of_capital, 1, true)}` : '—'}</td>
        <td class="num ${signClass(r.month_return_pct)}">${fmtPct(r.month_return_pct, 2, true)}${r.move_2sd ? ` ${pill(`>${sc.sigma}σ`, 'bad')}` : ''}</td>
        <td class="wrap small">${esc(r.next_election || '—')}</td><td class="wrap small">${esc(r.rating_reviews || '—')}</td></tr>`).join('')}</tbody></table></div>`;
    };
    const held = sc.rows.filter((r) => r.position !== 'none');
    view.innerHTML = `
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Positions</span><span class="v">${held.length}</span><span class="s">of ${sc.rows.length} instruments held</span></div>
          <div class="stat"><span class="k">Big moves</span><span class="v ${sc.moves.length ? 'bad' : ''}">${sc.moves.length}</span><span class="s">beyond ${sc.sigma}σ in the month${sc.moves.length ? `: ${sc.moves.join(', ')}` : ''}</span></div>
          <div class="stat"><span class="k">Without data</span><span class="v ${sc.stale.length ? 'warn' : ''}">${sc.stale.length}</span><span class="s">stale or missing for ${fmtMonth(sc.as_of)}</span></div>
          <div class="stat"><span class="k">Report</span><span class="v sm">${sc.report ? `<a href="#/reports/${esc(sc.report)}">open</a>` : '—'}</span><span class="s">filed under Reports (type screener)</span></div>
        </div>
        <p class="small muted">Carry, value and trend are the algorithm's own signals for ${fmtMonth(sc.as_of)}; ranks are within each book (1 = highest) among instruments with data. Real carry: FX, the real policy-rate differential against the US; EM bonds, the real 10-year yield; spreads, the spread. * marks an instrument whose latest data are older than ${fmtMonth(sc.as_of)} (shown at that month, unranked). Elections and rating reviews: next 12 months from the Ledger calendars.</p>
      </section>
      <section class="section"><h2>Currencies (vs USD)</h2>${table('fx')}</section>
      <section class="section"><h2>Bonds (10y; spreads over the Bund)</h2>${table('bond')}</section>
      <section class="section"><h2>By country</h2><div class="list">${sc.countries.map((c) => `<div class="card"><div class="row-top"><span class="row-title">${esc(c.country)}</span><span class="muted small">${esc(c.instruments.join(', '))}</span></div><div class="row-meta">${c.positions.length ? `<b>${esc(c.positions.join(', '))}</b>` : 'no position'}${c.moves.length ? ` · ${pill(`${c.moves.join(', ')} > ${sc.sigma}σ`, 'bad')}` : ''}${c.next_election ? ` · election ${esc(c.next_election)}` : ''}${c.rating_reviews ? ` · rating ${esc(c.rating_reviews)}` : ''}</div></div>`).join('')}</div></section>`;
  }

  async function pageTodo() {
    const td = await load('todo');
    setHead('To do', `${td.done} of ${td.n} done · docs/todo.md updated ${fmtDate(td.updated)}`);
    if (!td.sections.length) { view.innerHTML = '<p class="empty">No to-do list yet (docs/todo.md is missing).</p>'; return; }
    const SEC_COLOR = { Technical: 'var(--c-trials)', Automation: 'var(--c-algorithm)', Algorithm: 'var(--c-evidence)' };
    const item = (i) => `<li class="todo-item ${i.done ? 'done' : ''}"><span class="box" aria-hidden="true">${i.done ? '✓' : ''}</span><span class="txt">${esc(i.text)}${i.note ? `<br><span class="muted small">${esc(i.note)}</span>` : ''}</span></li>`;
    view.innerHTML = `
      <style>
        .todo-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
        .todo-item { display: flex; gap: 10px; align-items: flex-start; padding: 8px 10px; border-radius: 10px; background: var(--surface); border: 1px solid var(--line); }
        .todo-item .box { flex: 0 0 22px; height: 22px; border-radius: 6px; border: 2px solid var(--g, var(--page)); display: grid; place-items: center; font-weight: 700; color: var(--on-accent); margin-top: 1px; }
        .todo-item.done .box { background: var(--good); border-color: var(--good); }
        .todo-item.done .txt { color: var(--muted); text-decoration: line-through; }
        .todo-item.done .txt .muted { text-decoration: none; }
      </style>
      <section class="section">
        <div class="stats">${td.sections.map((s) => `<div class="stat" style="--page:${SEC_COLOR[s.title] || 'var(--page)'}"><span class="k">${esc(s.title)}</span><span class="v">${s.done}<span class="muted" style="font-size:1rem">/${s.n}</span></span><span class="s">done</span></div>`).join('')}</div>
        ${td.intro ? `<p class="small muted">${esc(td.intro)} <a href="${esc(td.source_url)}" target="_blank" rel="noopener">Edit on GitHub</a>.</p>` : ''}
      </section>
      ${td.sections.map((s) => `<section class="section ev-group" style="--g:${SEC_COLOR[s.title] || 'var(--page)'}"><div class="section-head"><h2>${esc(s.title)}</h2><span class="muted small">${s.done} of ${s.n}</span></div><ul class="todo-list">${s.items.map(item).join('')}</ul></section>`).join('')}`;
  }

  async function pageMore() {
    setHead('More', 'Forecasts, calendar, risk, post-mortems, reports, trials and logging');
    const m = meta;
    const src = m.sources;
    view.innerHTML = `
      <section class="section">
        <div class="menu">
          <a href="#/forecasts" style="--item:var(--c-forecasts)"><span><span class="t">Forecasts</span><br><span class="d">Scored by Brier only; never in any P&L</span></span><span class="chev">›</span></a>
          <a href="#/calendar" style="--item:var(--c-home)"><span><span class="t">Calendar</span><br><span class="d">Catalysts, horizons, rebalances and Janus review days</span></span><span class="chev">›</span></a>
          <a href="#/risk" style="--item:var(--c-trials)"><span><span class="t">Risk and stress tests</span><br><span class="d">2008, March 2020 and 2022 replays; P&L attribution</span></span><span class="chev">›</span></a>
          <a href="#/postmortems" style="--item:var(--c-more)"><span><span class="t">Post-mortems</span><br><span class="d">Every closed position: thesis right? skill or luck?</span></span><span class="chev">›</span></a>
          <a href="#/evidence" style="--item:var(--c-evidence)"><span><span class="t">Evidence</span><br><span class="d">Status of every idea the programme has tested</span></span><span class="chev">›</span></a>
          <a href="#/trials" style="--item:var(--c-trials)"><span><span class="t">Trials</span><br><span class="d">The trial ledger with pass/fail</span></span><span class="chev">›</span></a>
          <a href="#/elections" style="--item:var(--c-elections)"><span><span class="t">Elections</span><br><span class="d">Calendar and live signals</span></span><span class="chev">›</span></a>
          <a href="#/reports" style="--item:var(--c-reports)"><span><span class="t">Reports</span><br><span class="d">Archive by date, type and country</span></span><span class="chev">›</span></a>
          <a href="#/screener" style="--item:var(--c-algorithm)"><span><span class="t">Screener</span><br><span class="d">Every country after the monthly rebalance: signals, ranks, positions, catalysts</span></span><span class="chev">›</span></a>
          <a href="#/marks" style="--item:var(--c-decisions)"><span><span class="t">Marks</span><br><span class="d">Daily marks of every instrument and their sources</span></span><span class="chev">›</span></a>
          <a href="#/lab" style="--item:var(--c-trials)"><span><span class="t">Lab - experimental</span><br><span class="d">Night-shift paper sleeves; a separate book, never in any other P&L</span></span><span class="chev">›</span></a>
          <a href="#/todo" style="--item:var(--c-more)"><span><span class="t">To do</span><br><span class="d">Technical, automation and algorithm items from docs/todo.md</span></span><span class="chev">›</span></a>
        </div>
      </section>
      <section class="section">
        <h2>Log an entry</h2>
        <div class="btn-row">${clerkButton(m)}</div>
        <p class="small muted">Backup: each link below opens a GitHub issue form; a workflow runs the same checks as the clerk, writes the entry and closes the issue with its new id, or comments with what to fix.</p>
        <div class="menu">
          <a href="${esc(m.issue_forms.decision)}" target="_blank" rel="noopener" style="--item:var(--c-decisions)"><span><span class="t">Decision record</span><br><span class="d">Trade or no-trade, with size, probability, stop and thesis</span></span><span class="chev">↗</span></a>
          <a href="${esc(m.issue_forms.forecast)}" target="_blank" rel="noopener" style="--item:var(--c-forecasts)"><span><span class="t">Forecast</span><br><span class="d">A question with my, the market's and Claude's probability</span></span><span class="chev">↗</span></a>
          <a href="${esc(m.issue_forms.resolve)}" target="_blank" rel="noopener" style="--item:var(--c-algorithm)"><span><span class="t">Resolve</span><br><span class="d">Close a decision or forecast with its outcome</span></span><span class="chev">↗</span></a>
          <a href="${esc(m.issue_forms.report)}" target="_blank" rel="noopener" style="--item:var(--c-reports)"><span><span class="t">Report</span><br><span class="d">Briefing, review, notebook or research, as text or a file</span></span><span class="chev">↗</span></a>
        </div>
      </section>
      <section class="section">
        <h2>About this build</h2>
        <div class="card"><dl class="kv">
          <dt>Built</dt><dd>${fmtDateTime(m.built_at)}</dd>
          <dt>Commit</dt><dd class="mono">${esc(m.commit || '—')}</dd>
          <dt>Algorithm positions</dt><dd>set ${fmtDate((src.positions_set || {})['v1.0'])} (v1.0)${(src.positions_set || {})['v1.1'] ? `, ${fmtDate(src.positions_set['v1.1'])} (v1.1)` : ''}</dd>
          <dt>Latest mark</dt><dd>${fmtDate(src.latest_mark)}${src.latest_fetch ? ` (fetched ${fmtDateTime(src.latest_fetch)})` : ''}</dd>
          <dt>Record</dt><dd>${m.audit ? `${m.audit.ok ? '<span class="good">verified</span>' : '<span class="bad">FAILED</span>'}: ${esc(m.audit.detail)}` : '—'}</dd>
          <dt>Decisions file</dt><dd>${fmtDate(src.decisions_updated)}</dd>
          <dt>Forecasts file</dt><dd>${fmtDate(src.forecasts_updated)}</dd>
          <dt>Marks</dt><dd>${src.marks_last_fetch ? `fetched ${fmtDateTime(src.marks_last_fetch)}` : 'none yet'}</dd>
          <dt>Trials file</dt><dd>${fmtDate(src.trials_updated)}</dd>
          <dt>Elections</dt><dd>${esc((src.elections || []).join(', '))}</dd>
          <dt>Repository</dt><dd><a href="${esc(m.repo_url)}" target="_blank" rel="noopener">${esc(m.repo_url.replace('https://', ''))}</a></dd>
        </dl></div>
        <p class="small muted">Install on an iPhone: open this page in Safari, tap Share, then "Add to Home Screen". The app then opens full screen and keeps working offline from the last build. Data refreshes on every push to main and once a day.</p>
        <div class="btn-row"><button class="btn" type="button" id="btn-refresh">Check for a new build</button></div>
      </section>`;
    document.getElementById('btn-refresh').onclick = async () => {
      try {
        const reg = await navigator.serviceWorker?.getRegistration();
        if (reg) { await reg.update(); toast('Checked for updates'); } else { location.reload(); }
      } catch (e) { location.reload(); }
    };
  }

  async function pageEvidence() {
    const ev = await load('evidence');
    setHead('Evidence', `Every idea the programme has tested · as of ${fmtDate(ev.as_of)}`);
    const G_COLOR = { live: 'var(--c-algorithm)', prospective: 'var(--warn)', passed: 'var(--good)', failed: 'var(--bad)' };
    const progress = (pct, left, right) => `<div class="progress"><div class="bar ${pct >= 100 ? 'good' : 'warn'}"><i style="width:${Math.max(0, Math.min(100, pct || 0)).toFixed(1)}%"></i></div><div class="lbl"><span>${esc(left)}</span><span>${esc(right)}</span></div></div>`;
    const item = (g, it) => {
      if (g === 'live' && it.under_test) return `
        <div class="card ev-item"><div class="row-top"><span class="row-title"><span class="mono" style="color:var(--g)">${esc(it.id)}</span> <a href="${esc(it.link)}">${esc(it.name)}</a></span><span>${badge('live')} ${badge('under test')}</span></div>
        <div class="stats">
          <div class="stat"><span class="k">Live months</span><span class="v">${it.live_months}</span><span class="s">${it.live_months ? 'since' : 'from'} ${fmtDate(it.live_since)}</span></div>
          <div class="stat"><span class="k">Live Sharpe</span><span class="v">${fmtNum(it.live_sharpe, 2)}</span><span class="s">backtest ${fmtNum(it.backtest_sharpe, 2)}</span></div>
          <div class="stat"><span class="k">Live drawdown</span><span class="v ${signClass(it.live_max_drawdown_pct)}">${fmtPct(it.live_max_drawdown_pct, 1)}</span><span class="s">backtest ${fmtPct(it.backtest_max_drawdown_pct, 1)}</span></div>
          <div class="stat"><span class="k">Live return</span><span class="v ${signClass(it.live_return_pct)}">${fmtPct(it.live_return_pct, 1, true)}</span><span class="s">v1.0 same months ${fmtPct(it.v1_0_same_window_return_pct, 1, true)}</span></div>
        </div>
        <div class="reason">${esc(it.reason)}</div></div>`;
      if (g === 'live') return `
        <div class="card ev-item"><div class="row-top"><span class="row-title"><a href="${esc(it.link)}">${esc(it.name)}</a></span>${badge('live')}</div>
        <div class="stats">
          <div class="stat"><span class="k">Live months</span><span class="v">${it.live_months}</span><span class="s">since ${fmtDate(it.live_since)}</span></div>
          <div class="stat"><span class="k">Live Sharpe</span><span class="v">${fmtNum(it.live_sharpe, 2)}</span><span class="s">backtest ${fmtNum(it.backtest_sharpe, 2)}</span></div>
          <div class="stat"><span class="k">Live drawdown</span><span class="v ${signClass(it.live_max_drawdown_pct)}">${fmtPct(it.live_max_drawdown_pct, 1)}</span><span class="s">backtest ${fmtPct(it.backtest_max_drawdown_pct, 1)}</span></div>
          <div class="stat"><span class="k">Live return</span><span class="v ${signClass(it.live_return_pct)}">${fmtPct(it.live_return_pct, 1, true)}</span><span class="s">net of costs, to ${fmtMonth(it.last_month)}</span></div>
        </div>
        ${progress(it.progress_pct, `Track record: ${it.live_months} of ${it.months_needed} months`, `${fmtNum(it.progress_pct, 0)}% of ${ev.min_track_record.years} years (${ev.min_track_record.confidence} confidence)`)}
        <div class="reason">${esc(it.reason)}</div></div>`;
      if (g === 'prospective') return `
        <div class="card ev-item"><div class="row-top"><span class="row-title"><a href="${esc(it.link)}">${esc(it.name)}</a></span>${badge('under test')}</div>
        ${isNum(it.threshold) ? progress(it.progress_pct, `${it.scored} of ${it.threshold} elections scored`, `${fmtNum(it.progress_pct, 0)}%`) : ''}
        <div class="reason">${esc(it.reason)}</div><div class="row-meta">source ${esc(it.source)}</div></div>`;
      return `
        <div class="card ev-item"><div class="row-top"><span class="row-title"><span class="mono" style="color:var(--g)">${esc(it.id)}</span> <a href="${esc(it.link)}">${esc(it.name)}</a></span>${badge(it.status)}</div>
        <div class="reason">${esc(it.reason)}</div><div class="row-meta">${it.date ? `tested ${fmtDate(it.date)}` : ''}${it.group ? ` · ${esc(it.group)}` : ''}${it.live_as ? ` · live as <a href="#/algorithm">${esc(it.live_as)}</a>` : ''}</div></div>`;
    };
    const EMPTY = { live: 'Nothing live.', prospective: 'Nothing under prospective test.', passed: 'None yet: no discretionary idea has passed a pre-registered test.', failed: 'None.' };
    view.innerHTML = `
      <section class="section">
        <div class="card ev-status"><span class="k">Overall status</span><span class="v">${esc(ev.overall)}</span><span class="s">Computed on every build from ${esc(ev.sources.join(', '))}. Minimum track record for ${ev.min_track_record.confidence} confidence in v1.0's Sharpe: about ${ev.min_track_record.years} years (${ev.min_track_record.months} months).</span></div>
      </section>
      ${ev.groups.map((g) => `
      <section class="section ev-group" style="--g:${G_COLOR[g.key]}">
        <div class="section-head"><h2>${esc(g.title)}</h2><span class="muted small">${g.items.length}</span></div>
        <div class="list">${g.items.length ? g.items.map((it) => item(g.key, it)).join('') : `<p class="empty">${EMPTY[g.key]}</p>`}</div>
      </section>`).join('')}`;
  }

  // ================================================================== v2: three books
  const BOOK = {
    me: { name: 'Me', cls: 'b-me', v: '--book-me', link: '#/me', kind: 'My decisions' },
    algorithm: { name: 'Algorithm', cls: 'b-algorithm', v: '--book-algo', link: '#/algorithm', kind: 'Mechanical rules, not AI' },
    janus: { name: 'Janus', cls: 'b-janus', v: '--book-janus', link: '#/janus', kind: 'AI book (experiment)' },
    fund: { name: 'Fund', cls: 'b-fund', v: '--book-fund', link: '#/fund', kind: 'Horizons fund: v1.1 + Janus, by risk' },
  };
  const bookOf = (b) => BOOK[String(b || '').split(' ')[0]] || { name: b, cls: 'b-none', v: '--muted', link: '#/home', kind: '' };
  const JANUS_ICON = '<svg class="janus-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M16 4c-3.6 0-6.2 2.3-7 5.6L6 13.2l2.6 1.1-.4 2.3 1.4 1-.6 2.8c-.3 1.6.9 3.1 2.5 3.1H14v3.5h4V23.5h2.5c1.6 0 2.8-1.5 2.5-3.1l-.6-2.8 1.4-1-.4-2.3 2.6-1.1-3-3.6C22.2 6.3 19.6 4 16 4Z" fill="currentColor"/><path d="M16 5v22" stroke="var(--surface)" stroke-width="1.6"/><circle cx="12.4" cy="11.6" r="1.1" fill="var(--surface)"/><circle cx="19.6" cy="11.6" r="1.1" fill="var(--surface)"/></svg>';
  const bookIcon = (b) => (b === 'janus' ? JANUS_ICON : `<span class="book-dot" style="background:var(${bookOf(b).v})"></span>`);
  const bookPill = (b, text) => `<span class="pill bk ${bookOf(b).cls}">${b === 'janus' ? JANUS_ICON : ''}${esc(text || bookOf(b).name)}</span>`;
  const pts = (x) => (isNum(x) ? `${x > 0 ? '+' : x < 0 ? '−' : ''}${fmtNum(Math.abs(x), 2)}` : '—');
  // "Log a decision": instructions for the Ledger clerk (docs/ledger/clerk.md); the GitHub forms stay as a backup
  const CLERK_TEMPLATE = ['DECISION RECORD', 'Date: ', 'Country: ', 'Instrument: ', 'Action: Buy / Sell / No trade', 'Size: ',
    'Probability: ', 'Horizon: ', 'Entry trigger: ', 'Stop / exit if wrong: ', 'Thesis: ', 'Key factors: ',
    'What would change my mind: ', 'How this differs from market consensus: '].join('\n');
  function clerkButton(m) {
    return `<details class="clerk"><summary class="btn primary">Log a decision</summary>
      <div class="clerk-body card">
        <ol class="small">
          <li>Open a Claude Code session on <b>em-macro</b>.</li>
          <li>Say <b>“Log this with the Ledger clerk”</b> and paste the <code>DECISION RECORD</code>, <code>FORECAST</code> or <code>RESOLVE</code> block.</li>
          <li>The session follows <code>docs/ledger/clerk.md</code>: it shows you the Risk Manager result, then logs the entry (sealed in the audit chain) and gives you the new id, or lists every problem to fix.</li>
        </ol>
        <div class="btn-row"><button type="button" class="btn" data-copy-clerk>Copy a blank DECISION RECORD</button></div>
        <p class="small muted">Backup: <a href="${esc(m.issue_forms.decision)}" target="_blank" rel="noopener">GitHub decision form</a> · <a href="${esc(m.issue_forms.quick)}" target="_blank" rel="noopener">GitHub paste form</a></p>
      </div></details>`;
  }
  document.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-copy-clerk]');
    if (!b) return;
    try { await navigator.clipboard.writeText(CLERK_TEMPLATE); b.textContent = 'Copied'; } catch (err) { b.textContent = 'Copy failed: select the text in docs/ledger/clerk.md'; }
  });
  let infoSeq = 0;
  function info(text, label = 'About this') {
    if (!text) return '';
    const id = `info-${++infoSeq}`;
    return `<button type="button" class="info-btn" aria-expanded="false" aria-controls="${id}" title="${esc(label)}">i<span class="sr">${esc(label)}</span></button><div class="info-text" id="${id}" hidden>${esc(text)}</div>`;
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.info-btn');
    if (!b) return;
    const t = document.getElementById(b.getAttribute('aria-controls'));
    if (!t) return;
    const open = b.getAttribute('aria-expanded') === 'true';
    b.setAttribute('aria-expanded', String(!open));
    t.hidden = open;
  });
  // explanatory paragraphs of the older pages collapse behind an info button; every table gets labels so it
  // can turn into stacked cards on a phone
  function polish(root) {
    root.querySelectorAll('p.small.muted, p.chart-note, p.note').forEach((p) => {
      if (p.dataset.kept || p.closest('.info-text') || (p.textContent || '').trim().length < 90) return;
      const id = `info-${++infoSeq}`;
      const btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'info-btn'; btn.textContent = 'i';
      btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', id); btn.title = 'About this';
      const box = document.createElement('div');
      box.className = 'info-text'; box.id = id; box.hidden = true; box.innerHTML = p.innerHTML;
      p.replaceWith(btn); btn.after(box);
    });
    root.querySelectorAll('table').forEach((t) => {
      const heads = [...t.querySelectorAll('thead th')].map((th) => th.textContent.trim());
      if (!t.classList.contains('compact')) t.classList.add('stack');
      t.querySelectorAll('tbody tr').forEach((tr) => [...tr.children].forEach((td, i) => { if (heads[i] && !td.dataset.label) td.dataset.label = heads[i]; }));
    });
  }

  function gauge(used, limit, label) {
    const f = isNum(used) && isNum(limit) && limit > 0 ? Math.max(0, Math.min(1, used / limit)) : 0;
    const a = Math.PI * (1 - f), x = 50 + 40 * Math.cos(a), y = 50 - 40 * Math.sin(a);
    const cls = f >= 0.9 ? 'bad' : f >= 0.7 ? 'warn' : 'good';
    return `<div class="gauge" role="img" aria-label="${esc(label)}: ${fmtNum(used, 2)} of ${fmtNum(limit, 1)}">
      <svg viewBox="0 0 100 56"><path d="M10 50 A40 40 0 0 1 90 50" class="g-track"/>${f > 0 ? `<path d="M10 50 A40 40 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}" class="g-fill ${cls}"/>` : ''}</svg>
      <span class="g-v">${fmtNum(used, 1)}<small> / ${fmtNum(limit, 0)}</small></span><span class="g-k">${esc(label)}</span></div>`;
  }

  // a dated line chart: datasets [{label, data: [[date, value]], color, dash, fill, width}]; tap or hover shows the
  // date and every value on that date
  function dateChart(id, datasets, opts = {}) {
    const labels = [...new Set(datasets.flatMap((d) => d.data.map((p) => p[0])))].sort();
    const fmtV = opts.fmt || ((v) => fmtNum(v, 2));
    return mkChart(id, {
      type: 'line',
      data: { labels, datasets: datasets.map((d) => {
        const m = new Map(d.data.map((p) => [p[0], p[1]]));
        const c = d.color.startsWith('--') ? cssVar(d.color) : d.color;
        return { label: d.label, data: labels.map((l) => (m.has(l) ? m.get(l) : null)), borderColor: c, backgroundColor: withAlpha(c, 0.12),
          fill: !!d.fill, borderDash: d.dash || [], borderWidth: d.width || 2, pointRadius: (ctx) => (labels.length < 25 && ctx.raw != null ? 2.5 : 0),
          pointHitRadius: 12, pointBackgroundColor: c, tension: 0.15, spanGaps: true };
      }) },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        events: ['mousemove', 'mouseout', 'click', 'touchstart', 'touchmove'],
        scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 6, callback: (v, i) => fmtDate(labels[i]).replace(/ \d{4}$/, '') } },
                  y: { grid: { color: cssVar('--grid') }, ticks: { maxTicksLimit: 5, callback: (v) => fmtV(v) }, title: { display: !!opts.yLabel, text: opts.yLabel || '' } } },
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: (it) => fmtDate(it[0].label), label: (it) => `${it.dataset.label}: ${fmtV(it.parsed.y)}` } } } },
    });
  }
  function sparkline(id, data, colorVar) {
    const c = cssVar(colorVar);
    return mkChart(id, {
      type: 'line',
      data: { labels: data.map((p) => p[0]), datasets: [{ data: data.map((p) => p[1]), borderColor: c, backgroundColor: withAlpha(c, 0.14), fill: true, borderWidth: 1.8, pointRadius: 0, pointHitRadius: 10, tension: 0.2 }] },
      options: { maintainAspectRatio: false, events: ['mousemove', 'mouseout', 'click', 'touchstart', 'touchmove'],
        scales: { x: { display: false }, y: { display: false } }, interaction: { mode: 'index', intersect: false },
        plugins: { tooltip: { displayColors: false, callbacks: { title: (it) => fmtDate(it[0].label), label: (it) => `index ${fmtNum(it.parsed.y, 2)}` } } } },
    });
  }
  const legendRow = (items) => `<div class="legend">${items.map(([l, v, dash]) => `<span><i class="${dash ? 'dash' : ''}" style="--c:var(${v})"></i>${esc(l)}</span>`).join('')}</div>`;
  const mtdHtml = (x, est) => `<span class="${signClass(x)}">${isNum(x) ? fmtPct(x, 2, true) : '—'}</span>${est ? '<span class="est">estimate</span>' : ''}`;
  function positionsHead(set, mark) { return `Positions set ${fmtDate(set)} · latest mark ${fmtDate(mark)}`; }

  async function homeHead() {
    const b = await load('books');
    const v = b.algorithm.versions[0];
    setHead('Home', positionsHead(v.positions_set || (meta.sources.positions_set || {})['v1.0'], b.latest_mark));
    return b;
  }

  // ------------------------------------------------------------------ collateral interest (display only)
  // total return = excess return + 3-month T-bill interest on the full account value (ledger/books.py TBILL_NOTE)
  const TOTAL_LABEL = 'total return (incl. T-bill)';
  const EXCESS_LABEL = 'excess of cash';
  function totalLine(o) {
    if (!o || !(o.total_series || []).length) return '';
    return `<div class="vs-cash tbill"><span>Excess of cash ${fmtPct(o.excess_since_start_pct, 2, true)}</span><span>T-bill interest ${fmtPct((o.total_since_start_pct || 0) - (o.excess_since_start_pct || 0), 2, true)}</span><span><b>Total return (incl. T-bill) ${fmtPct(o.total_since_start_pct, 2, true)}</b></span></div>`;
  }
  function tbillTable(o, title = 'Monthly, with T-bill interest') {
    const rows = (o && o.monthly_tbill) || [];
    if (!rows.length) return '';
    return `<details class="collapsible tbill-months"><summary><h3>${esc(title)}</h3>${info(o.tbill_note)}</summary>
      <div class="table-wrap"><table class="compact"><thead><tr><th>Month</th><th class="num">Excess</th><th class="num">T-bill</th><th class="num">Total</th></tr></thead>
      <tbody>${rows.slice().reverse().map((r) => `<tr><td>${fmtMonth(r.month)}</td><td class="num ${signClass(r.excess_pct)}">${fmtPct(r.excess_pct, 2, true)}</td><td class="num">${fmtPct(r.tbill_pct, 2, true)}</td><td class="num ${signClass(r.total_pct)}"><b>${fmtPct(r.total_pct, 2, true)}</b></td></tr>`).join('')}</tbody></table></div>
      <p class="small">Excess = excess of cash, the book's recorded P&L and the basis of every evaluation. T-bill = interest at the 3-month US T-bill rate on the full account value. Total = total return (incl. T-bill), display only.</p></details>`;
  }
  const totalDataset = (o, label, color) => ((o && (o.total_series || []).length > 1)
    ? [{ label: `${label}, ${TOTAL_LABEL}`, data: o.total_series, color, dash: [5, 4], width: 1.5 }] : []);
  const withNote = (text, o) => `${text} Solid line: ${EXCESS_LABEL} (the recorded P&L, used for every evaluation). Dashed line: ${TOTAL_LABEL}. ${(o && o.tbill_note) || ''}`;

  // ------------------------------------------------------------------ Horizons fund (ledger/fund.py, read only)
  const FUND_NAMES = { 'algorithm v1.1': 'Algorithm v1.1', janus: 'Janus', me: 'Me' };
  const fundMix = (fd) => Object.entries(fd.allocation.weights).map(([k, w]) => `${esc(FUND_NAMES[k] || k)} ${fmtPct(100 * w, 0)}`).join(' · ');
  function fundSection(fd) {
    const a = fd.allocation, jr = a.janus_rule;
    const bars = Object.keys(a.weights).map((k) => `<div class="bar-row"><span class="bl">${esc(FUND_NAMES[k] || k)}<br><span class="muted small">risk share ${fmtPct(100 * a.risk_shares[k], 0)}${isNum(a.vol[k].ann_vol_pct) ? ` · vol ${fmtPct(a.vol[k].ann_vol_pct, 1)}` : ''}</span></span><span class="bt"><i class="w" style="width:${(100 * a.weights[k]).toFixed(1)}%"></i></span><span class="bv">${fmtPct(100 * a.weights[k], 1)}</span></div>`).join('');
    const corr = fd.correlation;
    const corrRows = corr.pairs.map((p) => `<tr><td>${esc(FUND_NAMES[p.a])} / ${esc(FUND_NAMES[p.b])}</td><td class="num">${isNum(p.corr) ? fmtNum(p.corr, 2) : '<span class="muted">—</span>'}</td><td class="num">${p.months}</td></tr>`).join('');
    return `<section class="section">
        <div class="section-head"><h2>Performance and allocation</h2></div>
        <div class="card b-fund">
          ${fd.live ? `<div class="stats"><div class="stat"><span class="k">Since ${fmtDate(fd.live_start)}</span><span class="v ${signClass(fd.since_start_pct)}">${fmtPct(fd.since_start_pct, 2, true)}</span><span class="s">index ${fmtNum(fd.index, 2)}</span></div><div class="stat"><span class="k">Month to date</span><span class="v">${mtdHtml(fd.mtd_pct)}</span><span class="s">excess of cash, combined by risk</span></div><div class="stat"><span class="k">Total return (incl. T-bill)</span><span class="v ${signClass(fd.total_since_start_pct)}">${fmtPct(fd.total_since_start_pct, 2, true)}</span><span class="s">MTD ${fmtPct(fd.total_mtd_pct, 2, true)} · display only</span></div></div>
          <div class="chart"><canvas id="c-fund"></canvas></div>${legendRow([['Fund, excess of cash', '--book-fund'], ['Fund, total return (incl. T-bill)', '--book-fund', true]])}${tbillTable(fd)}` : `<p class="empty">Not started: ${esc(fd.status)}${fd.live_start ? ` (index 100 on ${fmtDate(fd.live_start)})` : ''}. The fund starts at 100 on the first date every member is live.</p>`}
          <h3>Allocation${a.from ? ` from ${fmtDate(a.from)}` : ' (the rule today)'}</h3>
          <div class="bars alloc">${bars}</div>
          <p class="small">Weights: ${esc(a.basis)}. Janus's risk share: ${fmtPct(100 * jr.share, 0)}, ${esc(jr.reason)}; drawdown ${fmtPct(jr.drawdown_pct, 1)}. The rule: <a href="${esc(meta.repo_url)}/blob/main/docs/fund/allocation.md" target="_blank" rel="noopener">docs/fund/allocation.md</a>. My decisions (Me) are outside the fund; no fund figure is written into any book.</p>
          <h3>Correlation between the books</h3>
          ${corr.enough ? '' : `<p class="small muted">Shown once two books share ${corr.min_months} completed months (${esc(corr.basis)}).</p>`}
          <div class="table-wrap"><table class="compact corr"><thead><tr><th>Books</th><th class="num">Correlation</th><th class="num">Months</th></tr></thead><tbody>${corrRows}</tbody></table></div>
        </div>
      </section>`;
  }

  async function pageFund() {
    const [b, fd] = await Promise.all([load('books'), load('fund')]);
    setHead('Horizons fund', fd.live ? `Live since ${fmtDate(fd.live_start)} · Algorithm v1.1 + Janus, combined by risk` : `Not started · ${fd.status}`);
    const v11 = b.algorithm.versions[1];
    const hist = (fd.history || []).slice().reverse();
    const histRows = hist.map((h) => `<tr><td>${fmtDate(h.from)}</td>${Object.keys(h.weights).map((k) => `<td class="num">${fmtPct(100 * h.weights[k], 1)}</td>`).join('')}<td class="num">${fmtPct(100 * h.janus_rule.share, 0)}</td><td>${h.basis.startsWith('risk') ? 'risk' : 'capital'}</td></tr>`).join('');
    view.innerHTML = `
      <section class="section"><div class="card b-fund notice"><b>A combined view, read only.</b> Built from the published indices of Algorithm v1.1 (starting risk share 80%) and Janus (20%) on every build. The books keep their own records; no fund figure is written into any of them, and my decisions (Me) are outside the fund. ${info(`${fd.note} ${fd.tbill_note || ""} The allocation rule, weights, volatilities and correlations use excess returns only.`)}</div></section>
      ${fundSection(fd)}
      ${fd.live ? `<section class="section"><div class="section-head"><h2>The fund and its members</h2>${info('Each line is that book\'s own excess-of-cash index, rebased to 100 on the fund\'s start; the fund is their risk-weighted combination. Weights and correlations use excess returns only.')}</div>
        <div class="card"><div class="chart"><canvas id="c-fund-members"></canvas></div>${legendRow([['Fund', '--book-fund'], ['Algorithm v1.1', '--book-algo'], ['Janus', '--book-janus']])}</div></section>` : ''}
      <section class="section"><div class="section-head"><h2>Allocation history</h2>${info('Weights set at each month start. Share = Janus\'s risk share under the rule. Basis: capital = the risk shares themselves (fewer than 6 months of data); risk = risk share ÷ trailing volatility.')}</div>
        <div class="card">${histRows ? `<div class="table-wrap"><table class="compact"><thead><tr><th>From</th>${Object.keys(fd.allocation.weights).map((k) => `<th class="num">${k === 'janus' ? 'Janus' : 'v1.1'}</th>`).join('')}<th class="num">Share</th><th>Basis</th></tr></thead><tbody>${histRows}</tbody></table></div>` : '<p class="empty">No allocation has been applied yet: the fund has not started.</p>'}</div></section>
      <section class="section"><div class="section-head"><h2>Janus's share: the rule</h2></div>
        <div class="card"><ul class="small">
          <li><b>20%</b> at the start, and until Janus has at least 30 resolved calls (now ${fd.allocation.janus_rule.calls_with_market_probability}).</li>
          <li>Then, on those calls: <b>30%</b> if its net P&L after costs is positive and its Brier score is better than the market's; <b>10%</b> if its net P&L is negative or its Brier score is worse than the market's (an exact tie stays at 20%). Now: Brier ${isNum(fd.allocation.janus_rule.brier_janus) ? fmtNum(fd.allocation.janus_rule.brier_janus, 3) : '—'} vs market ${isNum(fd.allocation.janus_rule.brier_market) ? fmtNum(fd.allocation.janus_rule.brier_market, 3) : '—'}. Every call records the market's probability, 50 where no market price exists.</li>
          <li><b>5%</b> while Janus's drawdown exceeds 10%, overriding the others (now ${fmtPct(fd.allocation.janus_rule.drawdown_pct, 1)}).</li>
          <li>Evaluated at each month start on data to the previous month end. The algorithm takes the rest.</li></ul>
          <p class="small"><a href="${esc(meta.repo_url)}/blob/main/docs/fund/allocation.md" target="_blank" rel="noopener">docs/fund/allocation.md</a> · config change C04, amended 7 November 2026 (before the fund starts and before any Janus call resolved)</p></div></section>`;
    if (fd.series.length) {
      dateChart('c-fund', [{ label: 'Fund, excess of cash', data: fd.series, color: '--book-fund', fill: true }, ...totalDataset(fd, 'Fund', '--book-fund')], { fmt: (v) => fmtNum(v, 2) });
      const rebase = (ser) => { const base = ser.find((p) => p[0] >= fd.live_start) || ser[0]; return ser.filter((p) => p[0] >= fd.live_start).map((p) => [p[0], 100 * p[1] / base[1]]); };
      dateChart('c-fund-members', [
        { label: 'Fund', data: fd.series, color: '--book-fund', width: 2.6 },
        { label: 'Algorithm v1.1', data: rebase(v11.series || []), color: '--book-algo' },
        { label: 'Janus', data: rebase(b.janus.series || []), color: '--book-janus' },
      ], { fmt: (v) => fmtNum(v, 2) });
    }
  }

  // ------------------------------------------------------------------ Home: the cockpit
  // ------------------------------------------------------------------ D004: v1.0 cut and stop rules (ledger/v1_rules.py, flags only)
  const V1_STATUS = { triggered: 'bad', 'in force': 'warn', watch: 'warn', error: 'warn', ok: 'good', passed: 'good', superseded: '' };
  function v1RulesFlags(vr) {
    if (!vr || !(vr.flags || []).length) return '';
    return `<section class="section"><div class="card notice"><b class="bad">v1.0 rules (D004): ${vr.flags.length} flag${vr.flags.length > 1 ? 's' : ''} at the ${esc(vr.as_of || '')} month-end.</b>
      <ul class="small">${vr.flags.map((f) => `<li>${esc(f)}</li>`).join('')}</ul>
      <p class="small muted">Flags only: the monitor never changes exposure. Ethan acts at the next rebalance. <a href="#/algorithm">Details</a></p></div></section>`;
  }
  function v1RulesSection(vr) {
    if (!vr) return '';
    const head = `<div class="section-head"><h2>v1.0 cut and stop rules (D004)</h2>${info('Pre-committed in decision D004 (11 Nov 2026). Measured on the official month-end v1.0 index from the 1 Nov 2026 live start. A monitor evaluates them after each official monthly run and raises flags; it never changes exposure and never touches frozen v1.0 code, configs or tags. Ethan acts on the flags. Rules and definitions: docs/ledger/v1_rules.md.')}</div>`;
    if (!vr.available) return `<section class="section">${head}<div class="card"><p class="empty">${esc(vr.note || 'No evaluation yet.')}</p></div></section>`;
    const rows = (vr.rules || []).map((r) => `<tr><td>${r.rule}. ${esc(r.name)}</td><td>${pill(r.status, V1_STATUS[r.status] || '')}</td><td class="wrap small">${esc(r.detail)}${r.action ? ` <b>→ ${esc(r.action)}</b>` : ''}</td></tr>`).join('');
    return `<section class="section">${head}<div class="card">
      <div class="stats">
        <div class="stat"><span class="k">Index (official)</span><span class="v">${fmtNum(vr.index, 2)}</span><span class="s">${esc(vr.as_of)} month-end · peak ${fmtNum(vr.peak, 2)}</span></div>
        <div class="stat"><span class="k">From live peak</span><span class="v ${signClass(vr.drawdown_pct)}">${fmtPct(vr.drawdown_pct, 2, true)}</span><span class="s">halve at −20% · stop at −27%</span></div>
        <div class="stat"><span class="k">Live Sharpe</span><span class="v">${isNum(vr.sharpe) ? fmtNum(vr.sharpe, 2) : '—'}</span><span class="s">after costs · ${vr.live_months} of 24 months</span></div>
        <div class="stat"><span class="k">Book carry</span><span class="v">${isNum(vr.carry_spread_pp) ? fmtNum(vr.carry_spread_pp, 2) : '—'}pp</span><span class="s">a year at constant risk · review below ${isNum(vr.carry_threshold_pp) ? fmtNum(vr.carry_threshold_pp, 2) : '—'}pp twice</span></div>
      </div>
      <div class="table-wrap"><table class="compact"><thead><tr><th>Rule</th><th>Status</th><th>Detail</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${(vr.managed_fx || []).length ? `<p class="small">Rule 4 is superseded by ${esc(vr.rule4_superseded_by || 'D005')}. Managed list: ${vr.managed_fx.map((m) => `<b>${esc(m.currency)}</b> (${esc(m.imf_classification)}, listed ${fmtDate(m.date)}${m.held ? ', held' : ''})`).join('; ')}.</p>` : ''}
      <p class="small muted">Evaluated ${fmtDateTime(vr.evaluated_at)}. ${esc(vr.note || '')}</p></div></section>`;
  }
  // ------------------------------------------------------------------ D005: volatility floor for managed currencies (em_macro/d005.py)
  function d005Section(d) {
    if (!d) return '';
    const head = `<div class="section-head"><h2>Volatility floor (D005)</h2>${info('Decision D005 supersedes D004 rule 4. For each currency on the managed list (IMF de facto classification: crawl-like, stabilised, crawling peg or conventional peg), its volatility estimate is floored at the median volatility of v1.0\'s emerging-market currencies that month, that leg\'s inverse-volatility weight is recomputed, and the whole book is rescaled to v1.0\'s 10% volatility target. Applied after v1.0 computes its positions and before they are booked, from the 3 December 2026 rebalance. Frozen v1.0 code, configs and tags are unchanged. The booked line includes D005; the unadjusted line is v1.0 without it. Rules: docs/ledger/d005_vol_floor.md.')}</div>`;
    const managed = (d.managed || []).map((m) => `<li><b>${esc(m.currency)}</b>: ${esc(m.imf_classification)} (IMF de facto), listed ${fmtDate(m.date)}<br><span class="small muted">${esc(m.source)}</span></li>`).join('');
    const sgn = (x) => (isNum(x) ? `${x > 0 ? '+' : ''}${fmtNum(x, 1)}` : '—');
    const cur = (d.current || []).map((p) => `<tr><td>${esc(p.instrument)} <span class="muted small">${esc(p.side)}</span>${p.floored ? `<br>${pill('floored', 'warn')}` : ''}</td>
      <td class="num">${fmtNum(p.instrument_vol_pct, 1)}${p.floored ? `<br><b>${fmtNum(p.vol_used_pct, 1)}</b>` : ''}</td>
      <td class="num">${sgn(p.v10_size_pct_of_capital)}</td><td class="num"><b>${sgn(p.d005_size_pct_of_capital)}</b></td></tr>`).join('');
    const last = (d.comparison || []).slice(-1)[0];
    return `<section class="section">${head}<div class="card">
      ${last ? `<div class="stats">
        <div class="stat"><span class="k">Booked (with D005)</span><span class="v">${fmtNum(last.booked_index, 2)}</span><span class="s">${fmtMonth(last.month)} month-end</span></div>
        <div class="stat"><span class="k">v1.0 unadjusted</span><span class="v">${fmtNum(last.unadjusted_index, 2)}</span><span class="s">comparison line, not booked</span></div>
        <div class="stat"><span class="k">Effect of D005</span><span class="v ${signClass(d.live_effect_pct)}">${fmtPct(d.live_effect_pct, 2, true)}</span><span class="s">booked / unadjusted − 1</span></div>
      </div>` : ''}
      ${cur ? `<h3 class="sub">Book as of ${fmtMonth(d.as_of)} (floor ${fmtNum(d.vol_floor_pct, 2)}%)</h3>
      <div class="table-wrap"><table class="compact"><thead><tr><th>Instrument</th><th class="num">Vol %</th><th class="num">v1.0 %</th><th class="num">D005 %</th></tr></thead><tbody>${cur}</tbody></table></div>
      <p class="small muted">Sizes in % of capital. Vol: v1.0's estimate, then the floored value used (median EM-currency volatility).</p>`
        : `<p class="small">First applied at the ${fmtDate(d.first_rebalance)} rebalance (positions as of ${fmtMonth(d.first_as_of)}). Until then v1.0 is booked unchanged.</p>`}
      <h3 class="sub">Managed list</h3>
      ${managed ? `<ul>${managed}</ul>` : '<p class="empty">Empty.</p>'}
    </div></section>`;
  }

  async function pageHome() {
    const [b, jn, ch, fd, vr] = await Promise.all([homeHead(), load('janus'), load('changes'), load('fund'), load('v1_rules').catch(() => null)]);
    const v10 = b.algorithm.versions[0], v11 = b.algorithm.versions[1];
    const TOT_MTD = { me: b.me.total_mtd_pct, algorithm: v10.total_mtd_pct, janus: b.janus.total_mtd_pct, fund: fd.live ? fd.total_mtd_pct : null };
    const card = (id, title, sub, mtd, est, open, gauge_, extra, openLabel = 'Open positions') => `
      <a class="card book-card ${bookOf(id).cls}" href="${bookOf(id).link}">
        <div class="bc-head"><span class="bc-name">${bookIcon(id)}${esc(title)}</span><span class="bc-kind">${esc(sub)}</span></div>
        <div class="bc-body"><div class="bc-spark"><canvas id="spark-${id}"></canvas></div>
          <div class="bc-stats"><span class="k">MTD, excess of cash</span><span class="v">${mtdHtml(mtd, est)}</span>
          <span class="k">MTD, total incl. T-bill</span><span class="v sm ${signClass(TOT_MTD[id])}">${isNum(TOT_MTD[id]) ? fmtPct(TOT_MTD[id], 2, true) : '—'}</span>
          <span class="k">${esc(openLabel)}</span><span class="v sm">${open}</span></div>${gauge_}</div>${extra || ''}</a>`;
    const items = (ch.items || []);
    const changed = items.length ? items.map((it) => `<li class="chg ${bookOf(it.book).cls}">${it.book in BOOK ? bookPill(it.book) : pill(it.book)} ${it.link ? `<a href="${esc(it.link)}">${esc(it.text)}</a>` : esc(it.text)}</li>`).join('')
      : '<li class="muted">Nothing new since the previous update.</li>';
    const ex = b.exposures;
    const cols = ['me', 'algorithm v1.0', 'algorithm v1.1', 'janus'];
    const exRows = (rows) => rows.map((r) => `<tr class="${r.shared ? 'flag' : ''}"><td><b>${esc(r.key)}</b>${r.shared ? ` <span class="pill warn">${r.opposed ? 'held by 2+ books, opposite' : 'held by 2+ books'}</span>` : ''}</td>
      ${cols.map((c) => `<td class="num ${bookOf(c).cls}-t">${isNum(r.books[c]) ? fmtNum(r.books[c], r.books[c] && Math.abs(r.books[c]) < 10 ? 2 : 1) : '—'}</td>`).join('')}</tr>`).join('');
    const cmp = b.comparison;
    view.innerHTML = `${v1RulesFlags(vr)}
      <section class="section cockpit">
        ${card('me', 'Me', 'my decisions', b.me.mtd_pct, false, b.me.open_count, gauge(b.me.risk_used_pct, b.me.risk_limit_pct, '% at risk'))}
        ${card('algorithm', 'Algorithm', 'mechanical rules, not AI', v10.mtd_pct, true, `${v10.n_positions} (v1.0) · ${v11.n_positions} (v1.1)`, gauge(v10.gross_leverage, v10.leverage_cap, 'gross leverage, x'),
          `<div class="bc-foot">v1.0 live since ${fmtDate(v10.live_start)}; v1.1 live from the ${fmtDate('2026-12-03')} rebalance${isNum(v11.pre_live_estimate_pct) ? ` (pre-live estimate ${fmtPct(v11.pre_live_estimate_pct, 2, true)}, not counted)` : ''}</div>`)}
        ${card('janus', 'Janus', 'AI book (experiment)', b.janus.mtd_pct, false, `${b.janus.open_count} of ${jn.max_open}`, gauge(b.janus.risk_used_pct, b.janus.risk_limit_pct, '% at risk'),
          `<div class="bc-foot">${jn.last_check ? `Last checked ${fmtDateTime(jn.last_check.time)} · ${esc(jn.last_check.result || '')}` : 'Not checked yet'} · fills at the next official daily mark</div>`)}
        ${card('fund', 'Fund', 'Horizons: v1.1 + Janus, by risk', fd.live ? fd.mtd_pct : null, false, fundMix(fd), '',
          `<div class="bc-foot">${fd.live ? `Live since ${fmtDate(fd.live_start)} · ${esc(fd.allocation.basis.split(' (')[0])}` : `Starts ${fd.live_start ? fmtDate(fd.live_start) : 'when every member is live'}`} · my decisions are outside the fund</div>`, 'Weights')}
      </section>
      <section class="section">
        <div class="card changes"><div class="section-head"><h2>What changed</h2><span class="muted small">${ch.since ? `since ${fmtDateTime(ch.since)}` : ''}</span></div>
        <ul class="chg-list">${changed}</ul></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Three books, the fund and cash</h2>${info(cmp.note + ' The fund starts at 100 on its own live start. Forecasts are not books: they are scored by Brier only and appear only on the Forecasts page.')}</div>
        <div class="card"><div class="chart"><canvas id="c-compare"></canvas></div>
        ${legendRow([['Me', '--book-me'], ['Algorithm v1.0', '--book-algo'], ['Janus', '--book-janus'], ['Fund', '--book-fund'], ['Cash (3m T-bill)', '--muted', true]])}
        <div class="vs-cash">${Object.entries(cmp.vs_cash).map(([k, v]) => `<span class="${bookOf(k).cls}-t">${esc(bookOf(k).name)} ${fmtPct(v.book_pct, 2, true)} excess of cash vs cash ${fmtPct(v.cash_pct, 2, true)}${isNum(v.total_pct) ? ` · total return (incl. T-bill) ${fmtPct(v.total_pct, 2, true)}` : ''}</span>`).join('')}</div></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Combined risk</h2><a class="more" href="#/risk">Risk and stress tests</a></div>
        <div class="card">${info(ex.note)}
          <h3>By country</h3>
          <div class="table-wrap"><table class="compact"><thead><tr><th>Country</th><th class="num">Me</th><th class="num">v1.0</th><th class="num">v1.1</th><th class="num">Janus</th></tr></thead><tbody>${exRows(ex.by_country) || '<tr><td colspan="5" class="muted">No positions.</td></tr>'}</tbody></table></div>
          <h3>By currency (FX positions)</h3>
          <div class="table-wrap"><table class="compact"><thead><tr><th>Currency</th><th class="num">Me</th><th class="num">v1.0</th><th class="num">v1.1</th><th class="num">Janus</th></tr></thead><tbody>${exRows(ex.by_currency) || '<tr><td colspan="5" class="muted">No FX positions.</td></tr>'}</tbody></table></div>
        </div>
      </section>
      <section class="section">
        <div class="menu">
          <a href="#/calendar" style="--item:var(--c-home)"><span><span class="t">Calendar</span><br><span class="d">Catalysts, horizons, rebalances, Janus review days</span></span><span class="chev">›</span></a>
          <a href="#/forecasts" style="--item:var(--c-forecasts)"><span><span class="t">Forecasts</span><br><span class="d">Scored by Brier only; never in any P&L</span></span><span class="chev">›</span></a>
        </div>
      </section>`;
    sparkline('spark-me', b.me.series, '--book-me');
    sparkline('spark-algorithm', v10.series, '--book-algo');
    sparkline('spark-janus', b.janus.series.length ? b.janus.series : [[meta.today, 100]], '--book-janus');
    sparkline('spark-fund', fd.series.length ? fd.series : [[meta.today, 100]], '--book-fund');
    dateChart('c-compare', [
      { label: 'Me', data: b.me.series, color: '--book-me' },
      { label: 'Algorithm v1.0', data: v10.series, color: '--book-algo' },
      ...(v11.series.length ? [{ label: 'Algorithm v1.1', data: v11.series, color: '--book-algo', dash: [2, 2], width: 1.5 }] : []),
      { label: 'Janus', data: b.janus.series, color: '--book-janus' },
      ...(fd.series.length ? [{ label: 'Fund', data: fd.series, color: '--book-fund', width: 2.4 }] : []),
      { label: 'Cash', data: cmp.cash, color: '--muted', dash: [5, 4], width: 1.4 },
    ], { fmt: (v) => fmtNum(v, 1) });
  }

  // ------------------------------------------------------------------ Me
  function posRow(book, p, title, meta_, pnl, href) {
    return `<a class="row-link pos ${bookOf(book).cls}" href="${esc(href)}"><div class="row-top"><span class="row-title">${title}</span><span class="row-pnl ${signClass(pnl)}">${isNum(pnl) ? fmtPct(pnl, 2, true) : ''}</span></div><div class="row-meta">${meta_}</div></a>`;
  }
  async function pageMe() {
    const [b, dec] = await Promise.all([load('books'), load('decisions')]);
    const me = b.me;
    setHead('Me', `My decisions · latest mark ${fmtDate(b.latest_mark)}`);
    const open = me.positions.filter((p) => p.status === 'open');
    const resolved = me.positions.filter((p) => p.status === 'resolved');
    const flag = (p) => (p.mark_flag ? ` ${pill(p.mark_frequency === 'monthly' ? 'monthly mark' : 'stale mark', 'warn')}` : '');
    const row = (p) => posRow('me', p, `${esc(p.instrument)} ${badge(p.action)}`,
      `<b>${esc(p.id)}</b>${(p.corrections || []).length ? ` ${pill('corrected', 'warn')}` : ''} · ${esc(p.country)} · ${p.action === 'No trade' ? 'no position' : `${fmtPct(p.size_pct, 1)} at risk`} · p ${fmtProb(p.probability)}${p.derivative && p.status === 'open' ? ` · ${pill(valuationText(p), p.valuation === 'model estimate' ? 'warn' : '')}${p.derivative.proxy === 'yes' ? ` ${pill('proxy', 'warn')}` : ''}` : isNum(p.mark) ? ` · mark ${fmtLevel(p.mark, p.mark_unit)} (${fmtDate(p.mark_date)}, ${esc(p.mark_frequency)})` : ''}${flag(p)}${p.status === 'resolved' ? ` · ${badge(p.outcome)}` : ` · horizon ${fmtDate(p.horizon)}`}`,
      p.status === 'resolved' ? p.pnl_pct : p.live_pnl_pct, `#/position/me/${p.id}`);
    const live = me.series.length ? me.series[me.series.length - 1][1] - 100 : null;
    view.innerHTML = `
      <section class="section">
        <div class="stats b-me-stats">
          <div class="stat"><span class="k">Live P&L</span><span class="v ${signClass(live)}">${fmtPct(live, 2, true)}</span><span class="s">% of account since ${fmtDate(me.live_start)}</span></div>
          <div class="stat"><span class="k">Month to date</span><span class="v">${mtdHtml(me.mtd_pct)}</span><span class="s">open and closed</span></div>
          <div class="stat"><span class="k">Brier</span><span class="v">${fmtNum(me.brier, 3)}</span><span class="s">${me.brier_n ? `${me.brier_n} resolved` : 'none resolved yet'}</span></div>
          <div class="stat">${gauge(me.risk_used_pct, me.risk_limit_pct, '% at risk')}</div>
        </div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Account, from my first decision</h2>${info(withNote('Index = 100 + live P&L in % of my account. Open positions are marked at first-hand daily marks dated on or after the decision; a monthly or stale mark is shown but never prices or closes a position.', me))}</div>
        <div class="card"><div class="chart"><canvas id="c-me"></canvas></div>${legendRow([['Me, excess of cash', '--book-me'], ['Me, total return (incl. T-bill)', '--book-me', true]])}${totalLine(me)}${tbillTable(me)}</div>
      </section>
      <section class="section"><div class="section-head"><h2>Open</h2><span class="muted small">${open.length}</span></div>
        <div class="list">${open.map(row).join('') || '<p class="empty">No open decisions.</p>'}</div></section>
      <section class="section"><div class="section-head"><h2>Resolved</h2><span class="muted small">${resolved.length}</span></div>
        <div class="list">${resolved.map(row).join('') || '<p class="empty">Nothing resolved yet.</p>'}</div></section>
      ${attributionSection('me', me.attribution, 'Live P&L of open positions, % of account')}
      <section class="section"><div class="btn-row">${clerkButton(meta)}<a class="btn" href="${esc(meta.issue_forms.resolve)}" target="_blank" rel="noopener">Resolve</a></div></section>`;
    dateChart('c-me', [{ label: 'Me, excess of cash', data: me.series, color: '--book-me', fill: true }, ...totalDataset(me, 'Me', '--book-me')], { fmt: (v) => fmtNum(v, 2) });
  }

  function attributionSection(book, att, note) {
    if (!att) return '';
    const block = (title, rows) => (rows && rows.length ? `<h3>${esc(title)}</h3><div class="bars">${rows.map((r) => {
      const max = Math.max(...rows.map((x) => Math.abs(x.pnl_pct)), 0.0001);
      return `<div class="bar-row"><span class="bl">${esc(r.key)}</span><span class="bt"><i class="${r.pnl_pct >= 0 ? 'up' : 'down'}" style="width:${(50 * Math.abs(r.pnl_pct) / max).toFixed(1)}%"></i></span><span class="bv ${signClass(r.pnl_pct)}">${fmtPct(r.pnl_pct, 2, true)}</span></div>`;
    }).join('')}</div>` : '');
    const body = block('By country', att.country) + block('By asset class', att.asset_class) + block('By signal (approximate)', att.signal) + block('Booked live months, by book', att.official_books);
    return body ? `<section class="section"><div class="section-head"><h2>P&L attribution</h2>${info(note)}</div><div class="card ${bookOf(book).cls}">${body}</div></section>` : '';
  }

  // ------------------------------------------------------------------ Algorithm
  async function pageAlgorithm() {
    const [b, alg, vr] = await Promise.all([load('books'), load('algorithm'), load('v1_rules').catch(() => null)]);
    const [v10, v11] = b.algorithm.versions;
    setHead('Algorithm', positionsHead(v10.positions_set, b.latest_mark));
    const verBlock = (v, cap, positions) => {
      const est = v.estimate || {};
      const rows = (est.positions || []).map((p) => `<tr><td><a href="#/position/algorithm/${esc(v.id)}:${esc(p.instrument)}">${esc(p.instrument)}</a></td><td class="wrap">${esc(p.country)}</td><td>${badge(p.side)}</td>
        <td class="num">${fmtPct(p.size_pct, 1, true)}</td><td class="num">${isNum(p.mark) ? fmtLevel(p.mark, p.unit) : '—'} <span class="muted small">${fmtDate(p.mark_date).replace(/ \d{4}$/, '')}</span></td>
        <td class="num ${signClass(p.mtd_pct)}">${fmtPct(p.mtd_pct, 2, true)}${p.carried ? ` ${pill('carried', 'warn')}` : ''}</td></tr>`).join('');
      const liveTxt = v.is_live ? `live since ${fmtDate(v.live_start)} (index 100)` : `live from the ${fmtDate('2026-12-03')} rebalance; this month is pre-live (not counted)`;
      return `
      <section class="section ver">
        <div class="section-head"><h2>${esc(v.label)}</h2>${bookPill('algorithm', 'mechanical rules')}</div>
        <div class="stats">
          <div class="stat"><span class="k">Index</span><span class="v">${fmtNum(v.index, 2)}</span><span class="s">${esc(liveTxt)}</span></div>
          <div class="stat"><span class="k">Month to date</span><span class="v">${mtdHtml(v.is_live ? v.mtd_pct : v.pre_live_estimate_pct, true)}</span><span class="s">${v.is_live ? 'estimate, month to date' : 'pre-live estimate, not counted'}</span></div>
          <div class="stat"><span class="k">With impact (MTD)</span><span class="v ${signClass(v.mtd_pct)}">${v.is_live && isNum(v.mtd_pct) ? fmtPct(v.mtd_pct - (v.mtd_impact_pct || 0), 2, true) : '—'}</span><span class="s">minus ${fmtPct(v.mtd_impact_pct, 3)} square-root impact</span></div>
          <div class="stat">${gauge(v.gross_leverage, v.leverage_cap, 'gross leverage, x')}</div>
        </div>
        ${v.series.length ? `<div class="card"><div class="chart"><canvas id="c-${v.id.replace('.', '')}"></canvas></div>
          ${legendRow([['Official monthly P&L, then estimate (excess of cash)', '--book-algo'], ['Estimated P&L with impact', '--book-algo-2', true], ...((v.unadjusted_series || []).length ? [['v1.0 unadjusted (without D005), official month-ends', '--muted', true]] : []), ['Total return (incl. T-bill)', '--book-algo', true]])}
          ${totalLine(v)}${tbillTable(v)}
          ${info(`${withNote('', v)} ${(est.note || '')} The official P&L keeps the frozen cost model; the dashed line subtracts the square-root market-impact estimate of each rebalance's trades at that month's paper capital (US$100,000 to Nov 2026, US$500,000,000 from Dec 2026).`)}</div>` : `<div class="card"><p class="empty">${esc(liveTxt)}. The chart starts at 100 then.</p></div>`}
        <h3 class="sub">Positions (effective ${fmtMonth(v.effective_from)}, set ${fmtDate(v.positions_set)})</h3>
        <div class="table-wrap"><table><thead><tr><th>Instrument</th><th>Country</th><th>Side</th><th class="num">Size</th><th class="num">Mark</th><th class="num">MTD</th></tr></thead><tbody>${rows}</tbody></table></div>
        ${est.carried && est.carried.length ? `<p class="small"><span class="pill warn">carried</span> no free daily source or no current mark, carried at the last mark: ${esc(est.carried.join(', '))}</p>` : ''}
        ${capacitySection(cap, v.id)}
        ${attributionSection('algorithm', v.attribution, 'Estimate, month to date, by country, asset class and signal. Signal split: each position\'s P&L is shared between carry, trend and value in proportion to the z-scores that point the same way as the position (approximate). Booked months are split by the official FX and bond books.')}
      </section>`;
    };
    const live = alg.live, bt = alg.frozen.test_2020_on || {};
    const months = alg.months;
    const sh = alg.shadows || { items: [] };
    const gl = sh.go_live;
    const evalTxt = gl && gl.first_evaluation ? `evaluated on ${fmtDate(gl.first_evaluation.date)} (and, if inconclusive, on ${fmtDate(gl.second_evaluation.date)}); nothing before then is a result` : 'evaluation dates are fixed at go-live; nothing before them is a result';
    const shadowBlock = (it) => {
      const pos = (it.positions || []).map((p) => `<tr><td>${esc(p.market)}</td><td>${badge(p.direction)}</td><td>${esc(p.contract)}</td><td class="num">${fmtNum(p.held_weight, 3)}</td></tr>`).join('');
      const drops = Object.entries(it.dropped || {}).map(([m, d]) => `${esc(m)} (from ${fmtMonth(d.from_month)})`).join(', ');
      const miss = Object.entries(it.missing || {}).map(([m, l]) => `${fmtMonth(m)}: ${esc(l.join(', '))}`).join('; ');
      if (!it.live) {
        return `<div class="card"><div class="row-top"><b>${esc(it.id)} · ${esc(it.name)}</b>${pill('not live yet', 'warn')}</div>
          <p class="small">${gl ? `Go-live planned at the ${fmtMonth(gl.M1)} rebalance, after the pre-live checks at that rebalance.` : 'Goes live at the first rebalance after the pre-live checks (planned: 3 December 2026).'}${it.universe && it.universe.length ? ` Universe: ${esc(it.universe.join(', '))} (N = ${it.N}; predicted Sharpe ${fmtNum(it.sr_pred, 3)}).` : ''}</p></div>`;
      }
      return `<div class="card">
        <div class="row-top"><b>${esc(it.id)} · ${esc(it.name)}</b>${pill('zero size, paper', 'warn')}</div>
        <div class="stats">
          <div class="stat"><span class="k">Index</span><span class="v">${fmtNum(it.index, 2)}</span><span class="s">net, decisive costs; ${it.index_as_of ? fmtDate(it.index_as_of) : '—'}</span></div>
          <div class="stat"><span class="k">Months live</span><span class="v">${it.months_live || 0}</span><span class="s">of ${it.months_in_first_window}</span></div>
          <div class="stat"><span class="k">Last rebalance</span><span class="v">${it.last_rebalance ? fmtMonth(it.last_rebalance) : '—'}</span><span class="s">${isNum(it.active_markets) ? `${it.active_markets} active of ${it.N}` : ''}</span></div>
        </div>
        ${(it.series || []).length > 1 ? `<div class="chart"><canvas id="c-shadow-${esc(it.id)}"></canvas></div>` : ''}
        <h3 class="sub">Held weights (${it.last_rebalance ? fmtMonth(it.last_rebalance) : '—'})</h3>
        ${pos ? `<div class="table-wrap"><table><thead><tr><th>Market</th><th>Side</th><th>Contract</th><th class="num">Weight</th></tr></thead><tbody>${pos}</tbody></table></div>` : '<p class="empty">No position this month.</p>'}
        <p class="small muted">${miss ? `Missing markets: ${miss}. ` : ''}${drops ? `Dropped: ${drops}. ` : ''}${(it.months_with_fewer_than_6 || []).length ? `Months with fewer than 6 active markets: ${esc(it.months_with_fewer_than_6.map(fmtMonth).join(', '))}.` : ''}</p>
      </div>`;
    };
    const shadowsHtml = `
      <section class="section">
        <div class="section-head"><h2>Shadows</h2>${info(`Pre-registered zero-size live shadows of the T21 basis-momentum (T25) and T22 diversified trend (T26) commodity sleeves, run on Databento final settlements with the trial code unchanged. Weights are fractions of a notional sleeve at its 10% volatility target; the index is net of decisive costs (2× the cost model). No price is published. Rules: ${sh.prereg}.`)}</div>
        <div class="card notice"><b>Zero size, paper.</b> ${esc((sh.label || '').replace(/^zero size, paper; /, '').replace(/^./, (c) => c.toUpperCase()))}. ${esc(evalTxt.replace(/^./, (c) => c.toUpperCase()))}.</div>
        ${sh.items.map(shadowBlock).join('')}
      </section>`;
    view.innerHTML = `
      <section class="section"><div class="card b-algorithm notice"><b>Mechanical rules, not AI.</b> v1.0 is the frozen control (carry, trend and value; FX and bonds); v1.1 is v1.0 plus the pre-registered T18 turnover rule. Both run on the same inputs every month on the 3rd; neither reads my decisions or Janus. ${info('Live records: v1.0 from the November 2026 positions (index 100 at the end of October 2026), v1.1 from the 3 December 2026 rebalance. Paper capital US$500,000,000 from that rebalance (C03); results are in % of capital. Positions are set by the monthly run; daily figures for the month in progress are estimates, replaced by the official figure on the 3rd.')}</div></section>
      ${v1RulesFlags(vr)}
      ${verBlock(v10, alg.capacity)}
      ${v1RulesSection(vr)}
      ${d005Section(alg.d005)}
      ${verBlock(v11, alg.v11 && alg.v11.capacity)}
      ${shadowsHtml}
      <section class="section">
        <details class="collapsible"><summary><h2>Backtest (not counted)</h2><span class="muted small">2020-01 to the freeze, evaluated once; pre-live months</span></summary>
          <div class="stats">
            <div class="stat"><span class="k">Sharpe 2020+</span><span class="v">${fmtNum(bt.sharpe, 2)}</span><span class="s">test, evaluated once</span></div>
            <div class="stat"><span class="k">Ann. return</span><span class="v">${fmtPct(bt.ann_return_pct, 1, true)}</span><span class="s">2020-01 to ${fmtMonth(alg.frozen.freeze_month)}</span></div>
            <div class="stat"><span class="k">Max drawdown</span><span class="v bad">${fmtPct(bt.max_drawdown_pct, 1)}</span><span class="s">test period</span></div>
            <div class="stat"><span class="k">Live months</span><span class="v">${live.months || 0}</span><span class="s">booked</span></div>
          </div>
          <div class="card"><div class="chart"><canvas id="c-alg-equity"></canvas></div>
            ${legend([['Backtest (left axis)', '--series-backtest'], [PRE_LIVE_LABEL, '--series-prelive'], [ACCOUNT_LABEL, '--series-live']])}</div>
          <div class="card"><div class="chart"><canvas id="c-alg-monthly"></canvas></div></div>
          <div class="card"><div class="chart"><canvas id="c-alg-dd"></canvas></div></div>
          <p class="small muted">Backtest figures come from results/systematic/test/ (frozen; reproduced byte for byte by em_macro.verify_v1). They are not part of any live record.</p>
        </details>
      </section>
      <section class="section"><div class="menu"><a href="#/screener" style="--item:var(--c-algorithm)"><span><span class="t">Screener</span><br><span class="d">Signals, ranks and catalysts after the rebalance</span></span><span class="chev">›</span></a>
      <a href="#/risk" style="--item:var(--c-algorithm)"><span><span class="t">Stress tests</span><br><span class="d">Current positions through 2008, March 2020 and 2022</span></span><span class="chev">›</span></a></div></section>`;
    for (const v of [v10, v11]) {
      if (!v.series.length) continue;
      dateChart(`c-${v.id.replace('.', '')}`, [
        { label: `${v.id} (official, then estimate)`, data: v.series.map((p) => [p[0], p[1]]), color: '--book-algo', fill: true },
        { label: `${v.id} with impact`, data: v.impact_series, color: '--book-algo-2', dash: [5, 4], width: 1.6 },
        ...((v.unadjusted_series || []).length ? [{ label: `${v.id} unadjusted (without D005)`, data: v.unadjusted_series, color: '--muted', dash: [2, 3], width: 1.4 }] : []),
        ...totalDataset(v, v.id, '--book-algo'),
      ], { fmt: (x) => fmtNum(x, 2) });
    }
    for (const it of sh.items) {
      if (it.live && (it.series || []).length > 1) {
        dateChart(`c-shadow-${it.id}`, [{ label: `${it.id} (net, decisive costs)`, data: it.series, color: '--book-algo-2', fill: false }], { fmt: (x) => fmtNum(x, 2) });
      }
    }
    const details = view.querySelector('details.collapsible');
    let drawn = false;
    details.addEventListener('toggle', () => {
      if (!details.open || drawn) return;
      drawn = true;
      equityChart('c-alg-equity', months, { historyBase: alg.frozen.freeze_month });
      monthlyBarChart('c-alg-monthly', months);
      drawdownChart('c-alg-dd', months);
    });
  }

  // ------------------------------------------------------------------ Janus
  async function pageJanus() {
    const [b, jn] = await Promise.all([load('books'), load('janus')]);
    setHead('Janus', jn.start ? `AI paper book since ${fmtDate(jn.start.date)} · latest mark ${fmtDate(b.latest_mark)}` : 'AI paper book · not started');
    const eq = jn.equity || [];
    const idx = eq.length ? eq[eq.length - 1][1] : 100;
    const oppHtml = (o) => (o ? `<details class="opp"><summary>The Opposition</summary><p>${esc(o.case_against)}</p>${(o.key_risks || []).length ? `<ul>${o.key_risks.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}${o.what_proves_it_wrong ? `<p><b>What would prove Janus wrong:</b> ${esc(o.what_proves_it_wrong)}</p>` : ''}${isNum(o.probability_view_wrong) ? `<p class="small">Opposition's probability that Janus is wrong: ${fmtProb(o.probability_view_wrong)}</p>` : ''}</details>` : '');
    const posCard = (p) => `
      <div class="card pos-card b-janus">
        <div class="row-top"><a class="row-title" href="#/position/janus/${esc(p.id)}">${esc(p.id)} ${badge(p.direction)} ${esc(p.instrument)}</a><span class="row-pnl ${signClass(p.net_pnl_pct)}">${isNum(p.net_pnl_pct) ? fmtPct(p.net_pnl_pct, 2, true) : (p.status === 'pending' ? pill('awaiting entry', 'warn') : '')}</span></div>
        <div class="row-meta">${fmtPct(p.risk_pct, 2)} at risk · stop ${fmtLevel(p.stop, p.unit)} · horizon ${fmtDate(p.horizon)} · p ${fmtProb(p.probability)}${p.fill ? (p.fill.entry_private ? ` · filled ${fmtDate(p.fill.entry_date)}${p.contract ? ` (${esc(p.contract.code)})` : ''}` : ` · entry ${fmtLevel(p.fill.entry_level, p.unit)} (${fmtDate(p.fill.entry_date)})`) : (p.contract ? ` · ${esc(p.contract.code)}` : '')}${p.option ? ` · ${esc(p.option.structure)} ${esc(p.option.legs.split('|').join(', '))}, expiry ${fmtDate(p.option.expiry)}` : ''}${p.valuation === 'model estimate' ? ` ${pill('model estimate', 'warn')}` : ''}${p.proxy ? ` ${pill('proxy', 'warn')}` : ''}${p.estimate ? ` ${pill('spot-proxy estimate', 'warn')}` : ''}${p.close ? ` · ${badge(p.close.outcome)} ${esc(p.close.reason)}` : ''}</div>
        <p class="thesis">${esc(p.thesis)}</p>
        <p class="small"><b>Would change its mind:</b> ${esc(p.change_mind)}</p>
        ${oppHtml(p.opposition)}
      </div>`;
    const counter = jn.calls_needed ? Math.min(100, 100 * jn.n_closed / jn.calls_needed) : 0;
    view.innerHTML = `
      <section class="section"><div class="card b-janus notice"><span class="janus-head">${JANUS_ICON}<b>Janus is an experiment in AI judgement.</b></span> Its results do not feed the algorithm, and no edge is claimed. Paper account of US$500,000,000, reported in % (index 100 at its start). Janus works in Claude Code sessions: a quick check every 30 minutes (at :15 and :45) and a full review after the US close; The Opposition argues against every new position. Every rule is enforced in code and the record is append-only.</div></section>
      <section class="section"><div class="card b-janus last-check">
        <div class="row-top"><b>Last checked ${jn.last_check ? fmtDateTime(jn.last_check.time) : '—'}</b>${jn.last_check ? `<span class="muted small">${esc(String(jn.last_check.session || '').replace('_', ' '))}</span>` : ''}</div>
        ${jn.last_check ? `<div class="row-meta">${esc(jn.last_check.result || '')}${jn.last_check.positions ? ` · positions: ${esc(jn.last_check.positions.join(', ') || 'none open')}` : ''}</div>` : ''}
        <p class="fill-rule"><b>Trades fill at the next official daily mark</b>, the first daily mark dated on or after the decision, not at the price when Janus decides.</p></div></section>
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Index</span><span class="v ${signClass(idx - 100)}">${fmtNum(idx, 2)}</span><span class="s">month to date ${isNum(b.janus.mtd_pct) ? fmtPct(b.janus.mtd_pct, 2, true) : '—'}</span></div>
          <div class="stat"><span class="k">Hit rate</span><span class="v">${isNum(jn.hit_rate) ? fmtPct(jn.hit_rate, 0) : '—'}</span><span class="s">${jn.n_right} of ${jn.n_closed} closed</span></div>
          <div class="stat"><span class="k">Brier</span><span class="v">${fmtNum(jn.brier, 3)}</span><span class="s">stated probability vs outcome</span></div>
          <div class="stat">${gauge(jn.risk_used_pct, jn.risk_limit_pct, '% at risk')}</div>
        </div>
        <div class="card"><div class="row-top"><b>Resolved calls: ${jn.n_closed} of ${jn.calls_needed || '—'} needed</b>${info(jn.significance_method)}</div><div class="progress"><i style="width:${counter.toFixed(1)}%"></i></div></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Equity</h2>${info(withNote((jn.benchmark && jn.benchmark.method) || '', b.janus))}</div>
        <div class="card">${eq.length ? '<div class="chart"><canvas id="c-janus"></canvas></div>' : '<p class="empty">The equity curve starts with the first run.</p>'}
          <div class="vs-cash"><span>Janus ${isNum(jn.benchmark.janus_pnl_pct) ? fmtPct(jn.benchmark.janus_pnl_pct, 2, true) : '—'}</span><span>Equal-weight benchmark of the same instruments ${isNum(jn.benchmark.pnl_pct) ? fmtPct(jn.benchmark.pnl_pct, 2, true) : '—'}</span>${b.comparison.vs_cash.janus ? `<span>Cash ${fmtPct(b.comparison.vs_cash.janus.cash_pct, 2, true)}</span>` : ''}</div>
          ${eq.length ? legendRow([['Janus, excess of cash', '--book-janus'], ['Janus, total return (incl. T-bill)', '--book-janus', true]]) : ''}${totalLine(b.janus)}${tbillTable(b.janus)}</div>
      </section>
      <section class="section"><div class="section-head"><h2>Open positions</h2><span class="muted small">${jn.n_open} of ${jn.max_open}</span></div>
        ${jn.open.map(posCard).join('') || '<p class="empty">No open positions.</p>'}</section>
      <section class="section"><div class="section-head"><h2>Closed positions</h2><span class="muted small">${jn.n_closed}</span></div>
        ${jn.closed.map(posCard).join('') || '<p class="empty">None closed yet.</p>'}</section>
      <section class="section"><div class="section-head"><h2>No-trade records</h2></div>
        ${(jn.no_trades || []).slice().reverse().map((n) => `<div class="card b-janus"><div class="row-meta">${fmtDate(n.date)} · ${esc(n.model || '')}</div><p>${esc(n.reasoning)}</p></div>`).join('') || '<p class="empty">None.</p>'}</section>
      <section class="section"><div class="section-head"><h2>Sessions</h2><span class="muted small">reviews and quick checks</span></div>
        ${(jn.runs || []).slice().reverse().slice(0, 15).map((r) => `<div class="card b-janus"><div class="row-meta">${fmtDateTime(r.decided_at)} · ${esc((r.session || 'weekly run (API)').replace('_', ' '))} · ${esc(r.model || '')} · ${r.n_new} new · ${r.n_reviews} reviews${r.session_url ? ` · <a href="${esc(r.session_url)}" target="_blank" rel="noopener">session</a>` : ''}</div>${r.market_summary ? `<p>${esc(r.market_summary)}</p>` : ''}</div>`).join('') || '<p class="empty">No session yet.</p>'}
        ${(jn.checks || []).length ? `<h3 class="sub">Recent quick checks</h3><ul class="plain checks">${jn.checks.slice().reverse().slice(0, 12).map((c) => `<li><span class="mono small">${fmtDateTime(c.time)}</span> · ${esc(c.result)}${c.positions && c.positions.length ? ` <span class="muted small">(${esc(c.positions.join(', '))})</span>` : ''}</li>`).join('')}</ul>` : ''}</section>
      <section class="section"><div class="section-head"><h2>Universe and data</h2>${info('Rates and FX: free public daily marks. Futures (NYMEX energy, COMEX gold, silver and copper, CBOT corn, soybeans and wheat) by contract month, marked at final exchange settlements from Databento; the settlements are licensed and kept privately, so only P&L in % is shown. ICE Brent is held and marked as NYMEX BZ (proxy). Options only as defined-risk structures, valued with Black-76 (model estimate). Never Norgate.')}</div>
        <div class="table-wrap"><table><thead><tr><th>Code</th><th>Market</th><th>Daily source</th></tr></thead><tbody>${jn.universe.map((u) => `<tr><td><b>${esc(u.instrument)}</b>${u.estimate ? ` ${pill('estimate', 'warn')}` : ''}</td><td class="wrap">${esc(u.name)}</td><td class="wrap small">${esc(u.source)} ${esc(u.source_id)}</td></tr>`).join('')}</tbody></table></div>
        <h3 class="sub">Dropped</h3><ul class="plain">${jn.dropped.map((d) => `<li><b>${esc(d.market)}</b>: ${esc(d.reason)}</li>`).join('')}</ul>
        <p class="small">Record chain: ${jn.chain.ok ? `<span class="good">verified</span> (${jn.chain.n} records)` : `<span class="bad">FAILED: ${esc(jn.chain.error)}</span>`}</p></section>`;
    if (eq.length) dateChart('c-janus', [{ label: 'Janus, excess of cash', data: eq, color: '--book-janus', fill: true }, ...totalDataset(b.janus, 'Janus', '--book-janus')], { fmt: (v) => fmtNum(v, 2) });
  }

  // ------------------------------------------------------------------ position detail (any book)
  async function pagePosition(arg) {
    const [book, ...rest] = String(arg || '').split('/');
    const id = rest.join('/');
    const [b, jn, pmAll] = await Promise.all([load('books'), load('janus'), load('postmortems')]);
    let p, title, rows = [], hist = [], unit, thesis = '', opp = null, entry = null, stop = null, sub = '';
    const pm = (pmAll.items || []).find((x) => x.book === book && x.id === id);
    if (book === 'me') {
      p = b.me.positions.find((x) => x.id === id);
      if (!p) throw new Error(`No decision ${id}`);
      title = `${p.id} · ${p.instrument}`; unit = p.mark_unit || p.unit; hist = p.mark_history || []; thesis = p.thesis;
      entry = p.entry_level; stop = p.stop; sub = `Me · ${p.action} · ${p.status}`;
      rows = [['Action', badge(p.action)], ['Size', `${fmtPct(p.size_pct, 2)} of account at risk`], ['Probability', fmtProb(p.probability)],
        ['Entry', (isNum(entry) ? `${fmtLevel(entry, unit)} (${fmtDate(p.date)})` : (p.entry_text ? esc(p.entry_text) : '—')) + ((p.corrections || []).some((c) => c.field === 'entry_level') ? ` ${pill('corrected', 'warn')}` : '')], ['Stop', isNum(stop) ? fmtLevel(stop, unit) : '—'],
        ['Mark', isNum(p.mark) ? `${fmtLevel(p.mark, unit)} (${fmtDate(p.mark_date)}, ${esc(p.mark_frequency)})${p.mark_flag ? ` ${pill(p.mark_flag, 'warn')}` : ''}` : '—'],
        ['P&L', p.status === 'resolved' ? fmtPct(p.pnl_pct, 2, true) : `<span class="${signClass(p.live_pnl_pct)}">${fmtPct(p.live_pnl_pct, 2, true)}</span> of account`],
        ['Distance to stop', isNum(p.stop_distance) ? fmtLevel(Math.abs(p.stop_distance), unit) : '—'], ['Horizon', fmtDate(p.horizon)],
        ['Would change my mind', esc(p.change_mind || '')], ['Source', p.mark_source_url ? `<a href="${esc(p.mark_source_url.split(' ;')[0])}" target="_blank" rel="noopener">${esc(p.mark_source || 'source')}</a>` : '—']];
    } else if (book === 'janus') {
      p = jn.positions.find((x) => x.id === id);
      if (!p) throw new Error(`No Janus position ${id}`);
      title = `${p.id} · ${p.direction} ${p.instrument}`; unit = p.unit; hist = (p.mark_history || []).map((x) => [x[0], x[1]]);
      thesis = p.thesis; opp = p.opposition; entry = p.fill && p.fill.entry_level; stop = p.stop; sub = `Janus · ${p.status} · ${p.model}`;
      rows = [['Market', esc(p.name)], ['Size', `${fmtPct(p.risk_pct, 2)} of account at risk${p.requested_risk_pct !== p.risk_pct ? ` (asked ${fmtPct(p.requested_risk_pct, 2)})` : ''}`],
        ['Notional', p.fill ? `${fmtUsd(p.fill.notional_usd)}${p.fill.contracts ? ` · ${p.fill.contracts} contracts ${esc((p.fill.contract || {}).code || '')}` : ''}` : 'at the entry mark'],
        ['Probability its view is right', fmtProb(p.probability)], ['Entry', p.fill ? `${fmtLevel(entry, unit)} (${fmtDate(p.fill.entry_date)})` : 'next available daily mark'],
        ['Stop', `${fmtLevel(stop, unit)}${p.initial_stop !== p.stop ? ` (initial ${fmtLevel(p.initial_stop, unit)})` : ''}`],
        ['Mark', isNum(p.mark) ? `${fmtLevel(p.mark, unit)} (${fmtDate(p.mark_date)})` : '—'],
        ['P&L', isNum(p.net_pnl_pct) ? `<span class="${signClass(p.net_pnl_pct)}">${fmtPct(p.net_pnl_pct, 3, true)}</span> net (${fmtPct(p.gross_pnl_pct, 3, true)} gross)` : '—'],
        ['Distance to stop', isNum(p.distance_to_stop_pct_account) ? `${fmtPct(p.distance_to_stop_pct_account, 2)} of account` : '—'], ['Horizon', fmtDate(p.horizon)],
        ['Capacity', p.fill ? `${fmtPct(p.fill.capacity.pct_adv, 2)} of ADV${isNum(p.fill.capacity.pct_limit) ? ` · ${fmtPct(p.fill.capacity.pct_limit, 0)} of the position limit` : ''}${p.fill.capacity_note ? ` · ${esc(p.fill.capacity_note)}` : ''}` : '—'],
        ['Costs', p.fill ? `${fmtPct(p.fill.cost_pct, 3)} of account at entry (cost model + impact)` : '—'],
        ['Would change its mind', esc(p.change_mind)], ['Decided', `${fmtDateTime(p.decided_at)} by ${esc(p.model)}`],
        ['Sources cited', (p.sources || []).map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.url)}</a>`).join('<br>') || '—'],
        ['Sources read', `${(p.sources_read || []).length} pages returned by web search`]];
      if (p.fill && p.fill.roll_rule) rows.push(['Roll rule', esc(p.fill.roll_rule)]);
    } else if (book === 'algorithm') {
      const [vid, inst] = id.split(':');
      const v = b.algorithm.versions.find((x) => x.id === vid);
      p = v && (v.estimate.positions || []).find((x) => x.instrument === inst);
      if (!p) throw new Error(`No ${vid} position in ${inst}`);
      title = `${vid} · ${p.instrument}`; unit = p.unit; hist = (p.mark_history || []).map((x) => [x[0], x[1]]);
      sub = `Algorithm · mechanical rules · effective ${fmtMonth(v.effective_from)}`;
      thesis = `${p.description || ''}. Rule-based: carry z ${fmtNum(p.carry_z, 2)}, trend z ${fmtNum(p.trend_z, 2)}, value z ${fmtNum(p.value_z, 2)}; sized for equal risk (vol ${fmtNum(p.instrument_vol_pct, 1)}%).`;
      rows = [['Side', badge(p.side)], ['Size', `${fmtPct(p.size_pct, 2, true)} of capital`], ['Month start mark', `${fmtLevel(p.base_mark, unit)} (${fmtDate(p.base_date)})`],
        ['Mark', `${fmtLevel(p.mark, unit)} (${fmtDate(p.mark_date)}, ${esc(p.frequency)})${p.carried ? ` ${pill('carried', 'warn')}` : ''}`],
        ['P&L', `<span class="${signClass(p.mtd_pct)}">${fmtPct(p.mtd_pct, 3, true)}</span> of capital, estimate, month to date`],
        ['Stop', 'none (monthly rebalance)'], ['Risk share', fmtPct(p.risk_share_pct, 1)]];
    } else throw new Error('Unknown book');
    const corr = (book === 'me' && p.corrections) || [];
    const FIELD = { entry_level: 'Entry level', entry_underlying: 'Underlying at entry', entry_premium: 'Entry premium', risk_per_unit: 'Maximum loss per unit', quantity: 'Quantity (spreads)' };
    const corrHtml = corr.length ? `<section class="section"><h2>Corrections</h2>${corr.map((c) => `
      <div class="card correction"><div class="row-top"><b>${esc(c.correction_id)} · ${esc(FIELD[c.field] || c.field)}</b><span class="muted small">${fmtDateTime(c.sealed_at)}</span></div>
        <dl class="kv"><dt>Was</dt><dd>${esc(c.old_value)}</dd><dt>Now</dt><dd>${esc(c.new_value)}</dd><dt>Reason</dt><dd>${esc(c.reason)}</dd>
        <dt>Record</dt><dd class="small">appended to the audit chain (seal ${c.seq}, hash <span class="mono">${esc(String(c.hash).slice(0, 12))}…</span>); every other field unchanged</dd></dl></div>`).join('')}</section>` : '';
    setHead(title, sub);
    document.body.dataset.page = book === 'algorithm' ? 'algorithm' : book;
    view.innerHTML = `
      <section class="section"><div class="card ${bookOf(book).cls}">${bookPill(book)}<dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl></div></section>
      <section class="section"><h2>Mark history</h2><div class="card">${hist.length ? '<div class="chart"><canvas id="c-pos"></canvas></div>' : '<p class="empty">No marks yet.</p>'}
        ${legendRow([['Mark', bookOf(book).v], ...(isNum(entry) ? [['Entry', '--muted', true]] : []), ...(isNum(stop) ? [['Stop', '--bad', true]] : [])])}</div></section>
      ${corrHtml}
      ${thesis ? `<section class="section"><h2>${book === 'algorithm' ? 'Why the rules hold it' : 'Thesis'}</h2><div class="card"><p>${esc(thesis)}</p></div></section>` : ''}
      ${opp ? `<section class="section"><h2>The Opposition</h2><div class="card b-janus"><p>${esc(opp.case_against)}</p>${(opp.key_risks || []).length ? `<ul>${opp.key_risks.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}${opp.what_proves_it_wrong ? `<p><b>What would prove Janus wrong:</b> ${esc(opp.what_proves_it_wrong)}</p>` : ''}</div></section>` : ''}
      <section class="section"><h2>Post-mortem</h2>${pm ? postmortemCard(pm) : '<p class="empty">Written automatically when the position closes.</p>'}</section>`;
    if (hist.length) {
      const ds = [{ label: 'Mark', data: hist.map((x) => [x[0], x[1]]), color: bookOf(book).v, width: 2.2 }];
      if (isNum(entry)) ds.push({ label: 'Entry', data: hist.map((x) => [x[0], entry]), color: '--muted', dash: [4, 3], width: 1.2 });
      if (isNum(stop)) ds.push({ label: 'Stop', data: hist.map((x) => [x[0], stop]), color: '--bad', dash: [4, 3], width: 1.2 });
      dateChart('c-pos', ds, { fmt: (v) => fmtLevel(v, unit) });
    }
  }
  function postmortemCard(x) {
    const p = x.postmortem || {};
    return `<div class="card ${bookOf(x.book).cls}"><div class="row-top">${bookPill(x.book)} <a href="#/position/${esc(x.book)}/${esc(x.id)}">${esc(x.id)}</a><span class="muted small">${fmtDate(x.generated_at)}</span></div>
      <div class="row-meta">Thesis right: <b>${esc(p.thesis_right || '—')}</b> · ${esc(p.skill_or_luck || '—')}</div>
      ${p.what_happened ? `<p>${esc(p.what_happened)}</p>` : ''}<p>${esc(p.assessment || '')}</p>${p.do_differently ? `<p><b>Do differently:</b> ${esc(p.do_differently)}</p>` : ''}<p class="small">${esc(x.model || '')}</p></div>`;
  }
  async function pagePostmortems() {
    const pm = await load('postmortems');
    setHead('Post-mortems', 'Every closed position in every book, written automatically');
    view.innerHTML = `<section class="section">${(pm.items || []).map(postmortemCard).join('') || '<p class="empty">No position has closed yet. A post-mortem (was the thesis right, skill or luck, what to do differently) is written by the daily run for each one.</p>'}</section>`;
  }

  // ------------------------------------------------------------------ calendar
  async function pageCalendar() {
    const cal = await load('calendar');
    setHead('Calendar', `Next 180 days from ${fmtDate(cal.from)}`);
    const byMonth = {};
    cal.items.forEach((c) => { (byMonth[c.date.slice(0, 7)] = byMonth[c.date.slice(0, 7)] || []).push(c); });
    const chip = (c) => (c.book in BOOK ? bookPill(c.book, c.kind) : pill(c.kind, c.book === 'all' ? 'purple' : ''));
    view.innerHTML = `<section class="section">${legendRow([['Me', '--book-me'], ['Algorithm', '--book-algo'], ['Janus', '--book-janus'], ['Catalysts', '--muted']])}</section>` +
      Object.entries(byMonth).map(([m, items]) => `<section class="section"><h2>${fmtMonth(m)}</h2><div class="list">${items.map((c) =>
        `<a class="row-link cal ${c.book in BOOK ? bookOf(c.book).cls : 'b-none'}" href="${esc(c.link || '#/calendar')}"><div class="row-top"><span class="row-title">${esc(c.label)}</span><span class="muted small">${fmtDate(c.date)}</span></div><div class="row-meta">${chip(c)} ${esc(c.country || '')}</div></a>`).join('')}</div></section>`).join('');
  }

  // ------------------------------------------------------------------ risk: exposures, stress tests, attribution
  async function pageRisk() {
    const [b, st] = await Promise.all([load('books'), load('stress')]);
    setHead('Risk', `Combined exposure and stress tests · latest mark ${fmtDate(b.latest_mark)}`);
    const books_ = ['me', 'algorithm v1.0', 'algorithm v1.1', 'janus'];
    const scen = (st.scenarios || []).map((s) => `
      <div class="card"><div class="row-top"><b>${esc(s.name)}</b><span class="muted small">${fmtDate(s.start)} to ${fmtDate(s.end)}</span></div>
        <div class="bars">${books_.map((k) => `<div class="bar-row"><span class="bl ${bookOf(k).cls}-t">${esc(k === 'me' ? 'Me' : k === 'janus' ? 'Janus' : k.replace('algorithm ', 'Algorithm '))}</span><span class="bt"><i class="${(s.by_book[k] || 0) >= 0 ? 'up' : 'down'}" style="width:${Math.min(50, Math.abs(s.by_book[k] || 0)).toFixed(1)}%"></i></span><span class="bv ${signClass(s.by_book[k])}">${k in s.by_book ? fmtPct(s.by_book[k], 1, true) : '—'}</span></div>`).join('')}</div>
        <details><summary class="small">Positions (${s.positions.length}) and instruments without history (${s.missing.length})</summary>
          <div class="table-wrap"><table><thead><tr><th>Book</th><th>Position</th><th>Move</th><th class="num">P&L</th></tr></thead><tbody>${s.positions.map((r) => `<tr><td>${bookPill(r.book, r.book)}</td><td>${esc(r.instrument)}</td><td class="wrap small">${esc(r.move)}${r.monthly ? ' (monthly averages)' : ''}</td><td class="num ${signClass(r.pnl_pct)}">${fmtPct(r.pnl_pct, 2, true)}</td></tr>`).join('')}</tbody></table></div>
          ${s.missing.length ? `<p class="small"><b>No history (listed, not guessed):</b> ${s.missing.map((m) => `${esc(m.book)} ${esc(m.instrument)}`).join(', ')}</p>` : ''}</details></div>`).join('');
    view.innerHTML = `
      <section class="section"><div class="section-head"><h2>Stress tests</h2>${info(`${st.method || ''} Each book in % of its own capital. Positions are held unchanged through the whole episode; the algorithm would have rebalanced monthly, so long episodes overstate it.`)}</div>${scen || '<p class="empty">Not computed yet.</p>'}</section>
      ${attributionSection('me', b.me.attribution, 'Me: live P&L of open positions by country and asset class, % of account.')}
      ${attributionSection('algorithm', b.algorithm.versions[0].attribution, 'Algorithm v1.0: estimate, month to date.')}
      ${attributionSection('janus', b.janus.attribution, 'Janus: net P&L by country and asset class, % of account.')}`;
  }

  async function pageLab() {
    const lab = await load('lab');
    setHead(lab.label || 'Lab - experimental', 'A separate paper book: never mixed into Me, the algorithm, Janus, the shadows or the fund');
    const sl = lab.sleeves || [];
    const row = (s) => `<tr><td>${esc(s.id)}</td><td class="wrap">${esc(s.title)}</td><td>${esc(s.instrument)} ${esc(s.direction)}</td><td class="num">${fmtPct(s.risk_pct, 2)}</td><td>${esc(s.status)}</td><td>${esc(s.retire_on)}</td><td class="num ${signClass(s.pnl_pct)}">${fmtPct(s.pnl_pct, 2, true)}</td></tr>`;
    view.innerHTML = `
      <section class="section"><div class="card"><p class="small">${esc(lab.note || '')}</p>
        <p class="small muted">At risk ${fmtPct(lab.risk_used_pct || 0, 2)} of ${fmtPct((lab.limits || {}).total_pct || 5, 1)} (${fmtPct((lab.limits || {}).per_sleeve_pct || 0.5, 1)} per sleeve).</p></div></section>
      <section class="section"><h2>Lab account (start = 100)</h2>${(lab.series || []).length ? '<div class="chart"><canvas id="lab-chart"></canvas></div>' : '<p class="empty">No sleeve has filled yet.</p>'}</section>
      <section class="section"><h2>Sleeves</h2>${sl.length ? `<div class="table-wrap"><table><thead><tr><th>Id</th><th>Idea</th><th>Position</th><th class="num">Risk</th><th>Status</th><th>Retires</th><th class="num">P&L</th></tr></thead><tbody>${sl.map(row).join('')}</tbody></table></div>` : '<p class="empty">No sleeve launched yet.</p>'}
        ${(lab.proposed || []).length ? `<p class="small muted">Not launched: ${(lab.proposed || []).map(esc).join(', ')}</p>` : ''}
        ${(lab.errors || []).length ? `<p class="small bad">${(lab.errors || []).map(esc).join('<br>')}</p>` : ''}</section>`;
    if ((lab.series || []).length) {
      mkChart('lab-chart', { type: 'line', data: { labels: lab.series.map((p) => p[0]),
        datasets: [{ label: 'Lab - experimental', data: lab.series.map((p) => p[1]), borderColor: cssVar('--c-trials'), pointRadius: 0, borderWidth: 2 }] },
        options: { responsive: true, maintainAspectRatio: false } });
    }
  }

  // ------------------------------------------------------------------ router
  const routes = {
    home: pageHome, me: pageMe, decisions: (id) => (id ? pageDecisions(id) : pageMe()), algorithm: pageAlgorithm,
    janus: pageJanus, fund: pageFund, position: pagePosition, calendar: pageCalendar, risk: pageRisk, postmortems: pagePostmortems,
    forecasts: pageForecasts, trials: pageTrials, elections: pageElections, reports: pageReports, more: pageMore,
    evidence: pageEvidence, marks: pageMarks, screener: pageScreener, todo: pageTodo, lab: pageLab,
  };
  const TAB_OF = { decisions: 'me', position: '', trials: 'more', elections: 'more', reports: 'more', evidence: 'more',
                   marks: 'more', screener: 'algorithm', todo: 'more', lab: 'more', forecasts: 'more', calendar: 'more', risk: 'more',
                   postmortems: 'more' };

  async function render() {
    const hash = location.hash.replace(/^#\/?/, '');
    const parts = hash.split('/').map(decodeURIComponent);
    const page = parts[0];
    const id = page === 'position' ? parts.slice(1).join('/') : parts[1];
    const fn = routes[page] || routes.home;
    const key = routes[page] ? page : 'home';
    setTab(key in TAB_OF ? TAB_OF[key] : key);
    document.body.dataset.page = key;
    destroyCharts();
    window.scrollTo(0, 0);
    try {
      if (!meta) meta = await load('meta');
      updatedEl.textContent = `Updated ${fmtDateTime(meta.built_at)}`;
      const au = document.getElementById('audit');
      if (au && meta.audit) {
        au.hidden = false;
        au.className = `audit ${meta.audit.ok ? 'ok' : 'fail'}`;
        au.textContent = meta.audit.ok ? '✓ record verified' : '✗ record check failed';
        au.title = meta.audit.detail || '';
      }
      await fn(id);
      polish(view);
    } catch (e) {
      view.innerHTML = `<div class="card"><p class="bad">Could not load this page: ${esc(e.message)}</p><p class="muted small">If you are offline, the last build may not have been cached yet. Open the app once with a connection.</p></div>`;
    }
  }
  window.addEventListener('hashchange', render);

  // ------------------------------------------------------------------ theme
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('ledger.theme', t); } catch (e) { /* ignore */ }
    const mc = document.querySelector('meta[name="theme-color"]');
    if (mc) mc.setAttribute('content', t === 'dark' ? '#121633' : '#ffffff');
  }
  document.getElementById('theme-toggle').onclick = () => {
    const cur = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(cur === 'dark' ? 'light' : 'dark');
    render();
  };
  applyTheme(document.documentElement.getAttribute('data-theme') || 'light');

  // ------------------------------------------------------------------ service worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      try {
        const reg = await navigator.serviceWorker.register('sw.js');
        reg.addEventListener('updatefound', () => {
          const nw = reg.installing;
          if (!nw) return;
          nw.addEventListener('statechange', () => {
            if (nw.state === 'installed' && navigator.serviceWorker.controller) {
              toast('A new build is ready', 'Reload', () => location.reload());
            }
          });
        });
      } catch (e) { /* offline support unavailable */ }
    });
  }

  render();
})();
