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
  // status badges: open, won, lost, passed, failed, under test, and the rest
  const BADGE = {
    open: ['open', 'open'], right: ['won', 'good'], wrong: ['lost', 'bad'], scratched: ['scratched', ''],
    'no trade': ['no trade', ''], yes: ['yes', 'purple'], no: ['no', 'purple'], void: ['void', ''],
    pass: ['passed', 'good'], passed: ['passed', 'good'], fail: ['failed', 'bad'], failed: ['failed', 'bad'],
    pending: ['under test', 'warn'], 'under test': ['under test', 'warn'], live: ['live', 'c-algorithm'],
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
  async function pageHome() {
    const [home, alg] = await Promise.all([load('home'), load('algorithm')]);
    setHead('Home', `Paper P&L to ${fmtMonth(home.last_month)} · positions as of ${fmtMonth(home.rebalance.as_of)}`);
    const live = home.live || {};
    const months = alg.months.filter((m) => m.month >= '2020-01');
    const posRows = home.positions.map((p) => `
      <tr><td>${esc(p.instrument)}</td><td class="wrap">${esc(p.country)}</td><td>${badge(p.side)}</td>
      <td class="num">${fmtPct(p.size_pct_of_capital, 1, true)}</td><td class="num">${fmtPct(p.risk_share_pct, 1)}</td></tr>`).join('');
    const CAT_CLASS = { election: 'c-elections', 'decision horizon': 'c-decisions', 'forecast resolves': 'c-forecasts', 'algorithm rebalance': 'c-algorithm' };
    const cats = home.catalysts.length ? home.catalysts.map((c) => `
      <a class="row-link ${CAT_CLASS[c.kind] || ''}" href="${esc(c.link)}"><div class="row-top"><span class="row-title">${esc(c.label)}</span><span class="muted small">${fmtDate(c.date)}</span></div>
      <div class="row-meta">${pill(c.kind, CAT_CLASS[c.kind] || '')} ${c.country ? esc(c.country) : ''}</div></a>`).join('') : '<p class="empty">Nothing scheduled in the next 30 days.</p>';
    const rep = home.latest_report;
    view.innerHTML = `
      <section class="section">
        <div class="card hero rule">
          <span class="k">${esc(home.account_index_label || ACCOUNT_LABEL)}</span>
          <span class="v">${fmtNum(home.account_index, 1)}</span>
          <span class="s">${fmtUsd(home.account_usd)} · ${fmtPct(home.account_change_pct, 2, true)} since the live start (100 = end of ${fmtMonth(home.account_base_month)}; ${home.usd_switched ? `paper capital ${fmtUsd(home.usd_capital)} from the ${fmtDate(home.usd_switch_rebalance)} rebalance, at index ${fmtNum(home.index_at_switch, 1)}` : `paper capital ${fmtUsd(home.usd_capital)}, raised to US$10,000,000 at the ${fmtDate(home.usd_switch_rebalance)} rebalance`})</span>
          ${home.usd_switch_note ? `<span class="s"><strong>${esc(home.usd_switch_note)}</strong></span>` : ''}
          <span class="s">Latest month ${fmtMonth(home.last_month)} ${fmtPct(home.last_month_net_pct, 2, true)}${home.live.months ? '' : ' (pre-live, not counted)'}</span>
        </div>
        <div class="stats">
          <div class="stat"><span class="k">Live months</span><span class="v">${live.months || 0}</span><span class="s">since the ${fmtDate(home.rebalance.live_since)} rebalance</span></div>
          <div class="stat"><span class="k">Live return</span><span class="v ${signClass(live.total_return_pct)}">${fmtPct(live.total_return_pct, 1, true)}</span><span class="s">net of costs</span></div>
          <div class="stat"><span class="k">Open decisions</span><span class="v">${home.open_decisions.length}</span><span class="s">${home.open_forecasts} open forecasts${isNum(home.live_pnl_pct_total) ? ` · live P&L <b class="${signClass(home.live_pnl_pct_total)}">${fmtPct(home.live_pnl_pct_total, 2, true)}</b>` : ''}</span></div>
          <div class="stat"><span class="k">Last rebalance</span><span class="v sm">${fmtDate(home.rebalance.date)}</span><span class="s">positions as of ${fmtMonth(home.rebalance.as_of)}</span></div>
        </div>
      </section>
      <section class="section">
        <a class="row-link c-evidence" href="#/evidence"><div class="row-top"><span class="row-title" style="color:var(--c-evidence)">Evidence status</span><span class="muted small">${fmtDate(meta.today)}</span></div>
        <div class="row-meta" style="color:var(--fg)">${esc(home.evidence_status)}</div></a>
      </section>
      <section class="section">
        <div class="section-head"><h2>Equity curve</h2><a class="more" href="#/algorithm">Algorithm detail</a></div>
        <div class="card"><div class="chart"><canvas id="c-equity"></canvas></div>
        ${legend([['Backtest 2020 to freeze (left axis)', '--series-backtest'], [`${PRE_LIVE_LABEL} (left axis)`, '--series-prelive'], [`${ACCOUNT_LABEL} (right axis)`, '--series-live']])}
        <p class="chart-note">Left axis: ${esc(historyLabel(home.history_index_base_month))}, figures unchanged. Right axis: ${esc(ACCOUNT_LABEL)}, 100 at the end of ${fmtMonth(home.account_base_month)}.</p></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Open positions</h2><span class="muted small">held through ${fmtMonth(home.rebalance.effective_from)}</span></div>
        <div class="table-wrap"><table><thead><tr><th>Instrument</th><th>Country</th><th>Side</th><th class="num">Size</th><th class="num">Risk share</th></tr></thead><tbody>${posRows}</tbody></table></div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Open decisions</h2><a class="more" href="#/decisions">All decisions</a></div>
        <div class="list">${home.open_decisions.length ? home.open_decisions.map(decisionRow).join('') : '<p class="empty">No open decisions.</p>'}</div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Catalysts, next 30 days</h2><a class="more" href="#/elections">Elections</a></div>
        <div class="list">${cats}</div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Latest report</h2><a class="more" href="#/reports">Archive</a></div>
        ${rep ? reportRow(rep) : '<p class="empty">No reports yet.</p>'}
      </section>`;
    equityChart('c-equity', months, { historyBase: home.history_index_base_month });
  }

  const fmtLevel = (v, unit) => (!isNum(v) ? '—' : (unit === 'bp' ? `${fmtNum(v, 0)}bp` : unit && unit.startsWith('%') ? `${fmtNum(v, 2)}%` : fmtNum(v, Math.abs(v) >= 100 ? 1 : 4)));
  function liveLabel(d) {
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
        <div class="btn-row"><a class="btn primary" href="${esc(meta.issue_forms.decision)}" target="_blank" rel="noopener">Log a decision</a><a class="btn" href="${esc(meta.issue_forms.resolve)}" target="_blank" rel="noopener">Resolve</a></div>
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
        <div class="stat"><span class="k">Live P&L</span><span class="v ${signClass(d.live_pnl_pct)}">${isNum(d.live_pnl_pct) ? fmtPct(d.live_pnl_pct, 2, true) : '—'}</span><span class="s">${isNum(d.mark) ? `mark ${fmtLevel(d.mark, d.mark_unit)}, ${fmtDate(d.mark_date)}${d.mark_frequency === 'monthly' ? ' (monthly)' : ''}` : d.mark_instrument ? 'no mark yet' : d.kind === 'position' ? 'instrument not in the registry' : 'no position'}</span></div>
      </div>`;
    const markNote = d.mark_instrument ? `${esc(d.mark_instrument)}${isNum(d.mark) ? ` = ${fmtLevel(d.mark, d.mark_unit)} on ${fmtDate(d.mark_date)}` : ' (no mark yet)'}${d.mark_frequency === 'monthly' ? ' · <b>marked monthly</b> (no free daily source; see Marks)' : ''}${d.mark_source ? ` · ${esc(d.mark_source)}` : ''}${d.mark_source_url && /^https?:/.test(d.mark_source_url) ? ` · <a href="${esc(d.mark_source_url.split(' ;')[0])}" target="_blank" rel="noopener">source</a>` : ''}${d.mark_note ? ` · <span class="muted">${esc(d.mark_note)}</span>` : ''}${isNum(d.live_pnl_pct) ? '' : d.kind === 'position' && isNum(d.mark) ? ' · P&L needs a numeric entry level' : ''}` : (d.kind === 'position' ? 'instrument not matched in data/ledger/instruments.csv' : '');
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
        ${field('Resolution note', esc(d.resolution_note))}
        ${field('Logged', `${fmtDate(d.logged_at)}${d.issue_url ? ` · <a href="${esc(d.issue_url)}" target="_blank" rel="noopener">issue #${esc(d.issue)}</a>` : ' · seed entry'}`)}
      </section>
      ${d.status === 'open' ? `<div class="btn-row"><a class="btn primary" href="${esc(meta.issue_forms.resolve)}" target="_blank" rel="noopener">Resolve ${esc(d.id)}</a></div>` : ''}`;
  }

  async function pageAlgorithm() {
    const alg = await load('algorithm');
    const months = alg.months;
    const live = alg.live, bt = alg.frozen.test_2020_on || {}, design = alg.frozen.design_2005_2019 || {};
    setHead('Algorithm', `v1.0 systematic macro · paper P&L to ${fmtMonth(months.length ? months[months.length - 1].month : null)} · frozen ${fmtMonth(alg.frozen.freeze_month)}`);
    const cmp = (label, l, b, d, f = (x) => fmtNum(x, 2)) => `<tr><td>${esc(label)}</td><td class="num">${f(l)}</td><td class="num">${f(b)}</td><td class="num">${f(d)}</td></tr>`;
    const pctS = (x) => fmtPct(x, 1, true), pct = (x) => fmtPct(x, 1);
    const liveMonths = months.filter((m) => m.live);
    const liveNote = live.months ? `${live.months} live month${live.months === 1 ? '' : 's'} since the ${fmtDate(alg.rebalance.live_since)} rebalance` : `No live month has closed yet. The first live month is ${fmtMonth(alg.rebalance.live_start_month || nextMonth(alg.frozen.freeze_month))}, booked by the monthly run on the 3rd of the following month.`;
    const preLive = alg.rebalance.pre_live_months || [];
    const preNote = preLive.length ? ` ${preLive.map(fmtMonth).join(', ')}: pre-live (not counted), after the test period and before the first live rebalance.` : '';
    const posRows = alg.positions.map((p) => `
      <tr><td>${esc(p.instrument)}</td><td class="wrap">${esc(p.description)}</td><td>${badge(p.side)}</td>
      <td class="num">${fmtPct(p.size_pct_of_capital, 1, true)}</td><td class="num">${fmtPct(p.risk_share_pct, 1)}</td><td class="num">${fmtPct(p.instrument_vol_pct, 1)}</td>
      <td class="num">${fmtNum(p.carry_z, 2)}</td><td class="num">${fmtNum(p.trend_z, 2)}</td><td class="num">${fmtNum(p.value_z, 2)}</td></tr>`).join('');
    const maxRisk = Math.max(...alg.by_country.map((c) => c.risk_share_pct), 1);
    const countryRows = alg.by_country.map((c) => `<tr><td>${esc(c.country)}</td><td class="wrap small muted">${esc(c.positions.join(', '))}</td><td class="num">${fmtPct(c.risk_share_pct, 1)}</td><td><div class="bar"><i style="width:${(100 * c.risk_share_pct / maxRisk).toFixed(1)}%"></i></div></td><td class="num">${fmtPct(c.gross_pct, 0)}</td></tr>`).join('');
    const sleeveRows = alg.by_sleeve.map((s) => `<tr><td>${esc(s.sleeve)}</td><td class="num">${s.n}</td><td class="num">${fmtPct(s.risk_share_pct, 1)}</td><td class="num">${fmtPct(s.gross_pct, 0)}</td></tr>`).join('');
    const liveRows = liveMonths.length ? liveMonths.map((m) => `<tr><td>${fmtMonth(m.month)}</td><td class="num ${signClass(m.net)}">${fmtPct(m.net * 100, 2, true)}</td><td class="num">${fmtPct(m.model_net * 100, 2, true)}</td><td class="num">${fmtPct((m.override_pnl || 0) * 100, 2, true)}</td><td class="num">${fmtPct(m.carry_basket * 100, 2, true)}</td><td class="num">${fmtPct(m.sp500_tr * 100, 2, true)}</td><td class="num">${fmtNum(m.account_index, 1)}</td></tr>`).join('') : '';
    view.innerHTML = `
      <section class="section">
        <div class="card rule">
          <h2>Live vs the frozen backtest</h2>
          <p class="small muted">${esc(liveNote)}${esc(preNote)} Backtest: 2020-01 to ${fmtMonth(alg.frozen.freeze_month)}, evaluated once at the freeze. Design: 2005 to 2019, in sample.</p>
          <div class="table-wrap"><table><thead><tr><th>Measure</th><th class="num">Live</th><th class="num">Backtest</th><th class="num">Design</th></tr></thead><tbody>
            ${cmp('Months', live.months, bt.months, design.months, (x) => (x == null ? '—' : x))}
            ${cmp('Return, % a year', live.ann_return_pct, bt['ann_return_%'], design['ann_return_%'], pctS)}
            ${cmp('Volatility, % a year', live.ann_vol_pct, bt['ann_vol_%'], design['ann_vol_%'], pct)}
            ${cmp('Sharpe', live.sharpe, bt.sharpe, design.sharpe)}
            ${cmp('Max drawdown', live.max_drawdown_pct, bt['max_drawdown_%'], design['max_drawdown_%'], pct)}
            ${cmp('Hit rate (months up)', live.hit_rate_pct, null, null, pct)}
            ${cmp('S&P 500 correlation', null, bt.corr_sp500, design.corr_sp500)}
            ${cmp('Gross leverage (avg)', null, bt.avg_gross_leverage, design.avg_gross_leverage, (x) => (isNum(x) ? `${fmtNum(x, 1)}×` : '—'))}
          </tbody></table></div>
        </div>
        <div class="stats">
          <div class="stat"><span class="k">Last rebalance</span><span class="v sm">${fmtDate(alg.rebalance.date)}</span><span class="s">positions as of ${fmtMonth(alg.rebalance.as_of)}, held through ${fmtMonth(alg.rebalance.effective_from)}</span></div>
          <div class="stat"><span class="k">Gross leverage</span><span class="v">${isNum(alg.gross_leverage) ? `${fmtNum(alg.gross_leverage, 1)}×` : '—'}</span><span class="s">latest month</span></div>
          <div class="stat"><span class="k">Frozen at</span><span class="v sm mono">${esc(alg.freeze_commit)}</span><span class="s"><a href="${esc(alg.release_url)}" target="_blank" rel="noopener">v1.0-frozen release</a> · <a href="${esc(alg.freeze_doc_url)}" target="_blank" rel="noopener">freeze record</a></span></div>
          <div class="stat"><span class="k">Overrides</span><span class="v">${alg.overrides.length}</span><span class="s">manual overrides logged</span></div>
        </div>
      </section>
      ${liveMonths.length ? `<section class="section"><h2>Live months</h2><div class="table-wrap"><table><thead><tr><th>Month</th><th class="num">Net</th><th class="num">Model</th><th class="num">Override</th><th class="num">Carry basket</th><th class="num">S&P 500</th><th class="num">${esc(ACCOUNT_LABEL)}</th></tr></thead><tbody>${liveRows}</tbody></table></div></section>` : ''}
      <section class="section">
        <h2>Equity: ${esc(ACCOUNT_LABEL)}</h2>
        <div class="card"><div class="chart tall"><canvas id="c-alg-equity"></canvas></div>${legend([['Backtest (left axis)', '--series-backtest'], [`${PRE_LIVE_LABEL} (left axis)`, '--series-prelive'], [`${ACCOUNT_LABEL} (right axis)`, '--series-live']])}
        <p class="chart-note">Left axis: ${esc(historyLabel(alg.frozen.freeze_month))}, figures unchanged. Right axis: ${esc(ACCOUNT_LABEL)}, 100 at the end of ${fmtMonth(alg.rebalance.live_base_month)}; it moves only with live months.</p></div>
      </section>
      <section class="section">
        <h2>Monthly net P&L</h2>
        <div class="card"><div class="chart"><canvas id="c-alg-monthly"></canvas></div>${legend([['Up month', '--series-up'], ['Down month', '--series-down'], [PRE_LIVE_LABEL, '--series-prelive'], ['Live month', '--series-live']])}</div>
      </section>
      <section class="section">
        <h2>Drawdown</h2>
        <div class="card"><div class="chart"><canvas id="c-alg-dd"></canvas></div><p class="chart-note">From the running peak of cumulative net value since Jan 2020. Backtest max drawdown ${fmtPct(bt['max_drawdown_%'], 1)}.</p></div>
      </section>
      <section class="section">
        <h2>Positions by country</h2>
        <div class="table-wrap"><table><thead><tr><th>Country</th><th>Positions</th><th class="num">Risk share</th><th></th><th class="num">Gross</th></tr></thead><tbody>${countryRows}</tbody></table></div>
      </section>
      <section class="section">
        <h2>Positions by sleeve</h2>
        <div class="table-wrap"><table><thead><tr><th>Sleeve</th><th class="num">Positions</th><th class="num">Risk share</th><th class="num">Gross</th></tr></thead><tbody>${sleeveRows}</tbody></table></div>
      </section>
      <section class="section">
        <h2>All positions</h2>
        <div class="table-wrap"><table><thead><tr><th>Instrument</th><th>Description</th><th>Side</th><th class="num">Size</th><th class="num">Risk</th><th class="num">Vol</th><th class="num">Carry z</th><th class="num">Trend z</th><th class="num">Value z</th></tr></thead><tbody>${posRows}</tbody></table></div>
        <p class="small muted">Size is signed notional in % of capital; risk share is the position's share of portfolio risk. Source: results/systematic/positions.csv.</p>
      </section>`;
    equityChart('c-alg-equity', months, { historyBase: alg.frozen.freeze_month });
    monthlyBarChart('c-alg-monthly', months);
    drawdownChart('c-alg-dd', months);
  }
  function nextMonth(m) { if (!m) return null; const [y, mm] = m.split('-').map(Number); return mm === 12 ? `${y + 1}-01` : `${y}-${String(mm + 1).padStart(2, '0')}`; }

  function probTrack(f) {
    const dot = (v, cls, label) => (isNum(v) ? `<i class="dot ${cls}" style="left:${v}%" title="${esc(label)} ${fmtProb(v)}"></i>` : '');
    return `<div class="ptrack" aria-hidden="true">${dot(f.market_prob, 'market', 'Market')}${dot(f.claude_prob, 'claude', 'Claude')}${dot(f.my_prob, 'me', 'Me')}</div>`;
  }

  async function pageForecasts() {
    const fc = await load('forecasts');
    setHead('Forecasts', `${fc.summary.n} calls · ${fc.summary.open} open · ${fc.summary.resolved} resolved`);
    const cum = fc.cumulative;
    const rows = fc.items.slice().reverse().map((f) => `
      <div class="card fcard">
        <div class="row-top"><span class="row-title">${esc(f.question)}</span><span class="mono muted small">${esc(f.id)}</span></div>
        <div class="row-meta"><b>${esc(f.country)}</b> · ${fmtDate(f.date)} · resolves ${fmtDate(f.resolution_date)} ${f.status === 'resolved' ? badge(f.outcome) : badge('open')}</div>
        ${probTrack(f)}
        <div class="probs"><span><i style="background:var(--series-me)"></i>Me <b>${fmtProb(f.my_prob)}</b></span><span><i style="background:var(--series-claude)"></i>Claude <b>${fmtProb(f.claude_prob)}</b></span><span><i style="background:var(--series-market)"></i>Market <b>${fmtProb(f.market_prob)}</b></span></div>
        <div class="row-meta">${esc(f.market_source)}${f.status === 'resolved' ? ` · Brier me ${fmtNum(f.brier_me, 3)} · Claude ${fmtNum(f.brier_claude, 3)} · market ${fmtNum(f.brier_market, 3)}` : ''}${f.result ? ` · ${esc(f.result)}` : ''}</div>
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
      ${older.length ? `<section class="section"><h2>Earlier signal series</h2><div class="table-wrap"><table><thead><tr><th>Country</th><th>Election</th><th>Signal</th><th class="num">Last value</th><th>Last date</th><th class="num">Obs.</th></tr></thead><tbody>${older.map((s) => `<tr><td>${esc(s.country)}</td><td>${fmtDate(s.election_date)}</td><td class="wrap">${esc(s.label)}</td><td class="num">${fmtNum(s.last_value, 1)}</td><td>${fmtDate(s.last)}</td><td class="num">${s.n}</td></tr>`).join('')}</tbody></table></div></section>` : ''}`;
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
    setHead('Screener', 'Built after each monthly rebalance');
    view.innerHTML = '<p class="empty">The screener appears after the next monthly rebalance.</p>';
  }

  async function pageTodo() {
    setHead('To do', 'docs/todo.md');
    view.innerHTML = '<p class="empty">No to-do list yet.</p>';
  }

  async function pageMore() {
    setHead('More', 'Trials, elections, reports, marks, screener, to do and logging');
    const m = meta;
    const src = m.sources;
    view.innerHTML = `
      <section class="section">
        <div class="menu">
          <a href="#/evidence" style="--item:var(--c-evidence)"><span><span class="t">Evidence</span><br><span class="d">Status of every idea the programme has tested</span></span><span class="chev">›</span></a>
          <a href="#/trials" style="--item:var(--c-trials)"><span><span class="t">Trials</span><br><span class="d">The trial ledger with pass/fail</span></span><span class="chev">›</span></a>
          <a href="#/elections" style="--item:var(--c-elections)"><span><span class="t">Elections</span><br><span class="d">Calendar and live signals</span></span><span class="chev">›</span></a>
          <a href="#/reports" style="--item:var(--c-reports)"><span><span class="t">Reports</span><br><span class="d">Archive by date, type and country</span></span><span class="chev">›</span></a>
          <a href="#/screener" style="--item:var(--c-algorithm)"><span><span class="t">Screener</span><br><span class="d">Every country after the monthly rebalance: signals, ranks, positions, catalysts</span></span><span class="chev">›</span></a>
          <a href="#/marks" style="--item:var(--c-decisions)"><span><span class="t">Marks</span><br><span class="d">Daily marks of every instrument and their sources</span></span><span class="chev">›</span></a>
          <a href="#/todo" style="--item:var(--c-more)"><span><span class="t">To do</span><br><span class="d">Technical, automation and algorithm items from docs/todo.md</span></span><span class="chev">›</span></a>
        </div>
      </section>
      <section class="section">
        <h2>Log an entry</h2>
        <p class="small muted">Each button opens a GitHub issue form; the GitHub app on your phone handles it. A workflow checks the entry, writes it to the ledger files and closes the issue with its new id, or comments with what to fix.</p>
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
          <dt>Paper P&L</dt><dd>to ${fmtMonth(src.paper_pnl_last_month)}</dd>
          <dt>Positions</dt><dd>as of ${fmtMonth(src.positions_as_of)}</dd>
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
        <div class="reason">${esc(it.reason)}</div><div class="row-meta">${it.date ? `tested ${fmtDate(it.date)}` : ''}${it.group ? ` · ${esc(it.group)}` : ''}</div></div>`;
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

  // ------------------------------------------------------------------ router
  const routes = {
    home: pageHome, decisions: pageDecisions, algorithm: pageAlgorithm, forecasts: pageForecasts,
    trials: pageTrials, elections: pageElections, reports: pageReports, more: pageMore, evidence: pageEvidence,
    marks: pageMarks, screener: pageScreener, todo: pageTodo,
  };
  const TAB_OF = { trials: 'more', elections: 'more', reports: 'more', evidence: 'more', marks: 'more', screener: 'more', todo: 'more' };

  async function render() {
    const hash = location.hash.replace(/^#\/?/, '');
    const [page, id] = hash.split('/').map(decodeURIComponent);
    const fn = routes[page] || routes.home;
    const key = routes[page] ? page : 'home';
    setTab(TAB_OF[key] || key);
    document.body.dataset.page = key;
    destroyCharts();
    window.scrollTo(0, 0);
    try {
      if (!meta) meta = await load('meta');
      updatedEl.textContent = `Updated ${fmtDateTime(meta.built_at)}`;
      await fn(id);
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
