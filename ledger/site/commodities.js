/* Commodities book (ledger/commodities.py, config change C12): the T26 trend shadow at paper size.
   Registers a page on window.LedgerPages; app.js merges it into its router and supplies the shared helpers. */
(function () {
  'use strict';
  const pages = window.LedgerPages = window.LedgerPages || {};

  const monthName = (ym, U) => (ym ? U.fmtMonth(ym) : '—');

  pages.commodities = async function pageCommodities() {
    const U = window.LedgerUI;
    const { esc, fmtDate, fmtNum, fmtPct, isNum, pill, info, setHead, dateChart, legendRow, totalLine, tbillTable,
            totalDataset, signClass, mtdHtml, monthlyBarChart } = U;
    const c = await U.load('commodities');
    const view = U.view;
    const startTxt = c.start ? fmtDate(c.start) : '3 Dec 2026';
    setHead('Commodities', c.live ? `T26 trend shadow at paper size · k = ${fmtNum(c.k, 4)} · live since ${startTxt}`
                                  : (c.status === 'error' ? 'Could not build this book' : `Starts ${startTxt}`));
    const rules = `<ul class="small">
        <li><b>Returns</b> = the T26 shadow's monthly net returns × <b>k = ${fmtNum(c.k, 4)}</b>, fixed once (C12): 10% ÷ the ${fmtPct((c.k_derivation || {}).ann_vol_pct, 2)} annual volatility of the sleeve's 2000-2019 design-period backtest.</li>
        <li>Signals, markets, timing, costs and rules are the shadow's, unchanged. The book only reads the shadow's published output.</li>
        <li>Paper capital US$${fmtNum((c.capital_usd || 0) / 1e6, 0)}m, used only to turn weights into whole contracts. Results are in % of capital, excess of cash; total return adds T-bill interest (display only).</li>
        <li>Outside the Horizons fund, like my decisions. Config change ${esc(c.config_change || 'C12')}.</li></ul>`;
    const noteCard = `<section class="section"><div class="card notice"><b>What it does.</b> ${esc(c.note || '')}
        ${info(`k derivation: ${(c.k_derivation || {}).rule || ''}. Source: ${(c.k_derivation || {}).source || ''}. ${(c.k_derivation || {}).why_not_the_restricted_universe || ''}`)}</div></section>`;
    if (!c.live) {
      view.innerHTML = `${noteCard}
        <section class="section"><div class="card"><div class="row-top"><b>${c.status === 'error' ? 'Not available' : `Starts ${esc(startTxt)}`}</b>${pill('paper', 'warn')}</div>
          <p class="small">${c.status === 'error' ? esc((c.errors || []).join('; ')) : `Positions from the ${esc(startTxt)} settlement, once ledger-daily confirms the shadows' go-live (expected 4 Dec 2026). Until then there is nothing to show.`}</p>
          ${(c.universe || []).length ? `<p class="small muted">Markets (${c.universe.length}): ${esc(c.universe.join(', '))}.</p>` : ''}
          ${rules}</div></section>`;
      return;
    }
    const vol = c.vol || {};
    const months = (c.monthly || []).map((m) => ({ month: m.month, net: m.book_net_pct / 100, live: true }));
    const pos = (c.positions || []).slice().sort((a, b) => (Number(b.risk_share_pct) || 0) - (Number(a.risk_share_pct) || 0));
    const posRows = pos.map((p) => `<tr><td data-label="Market"><b>${esc(p.market)}</b> <span class="muted small">${esc(p.name || '')}</span></td>
        <td data-label="Side">${pill(p.direction, p.direction === 'long' ? 'good' : 'bad')}</td>
        <td data-label="Contract month">${esc(monthName(p.contract_month, U))}</td>
        <td data-label="Contracts" class="num">${p.contracts !== '' && p.contracts != null ? fmtNum(Number(p.contracts), 0) : '—'}</td>
        <td data-label="% of risk" class="num">${p.risk_share_pct !== '' && p.risk_share_pct != null ? fmtPct(Number(p.risk_share_pct), 1) : '—'}</td></tr>`).join('');
    const monRows = (c.monthly || []).slice().reverse().map((m) => `<tr><td>${esc(monthName(m.month, U))}</td>
        <td class="num ${signClass(m.book_net_pct)}"><b>${fmtPct(m.book_net_pct, 2, true)}</b></td><td class="num muted">${fmtPct(m.shadow_net_pct, 2, true)}</td></tr>`).join('');
    view.innerHTML = `${noteCard}
      <section class="section">
        <div class="stats">
          <div class="stat"><span class="k">Index</span><span class="v ${signClass(c.since_start_pct)}">${fmtNum(c.index, 2)}</span><span class="s">since ${esc(startTxt)} ${fmtPct(c.since_start_pct, 2, true)}</span></div>
          <div class="stat"><span class="k">Month to date</span><span class="v">${mtdHtml(c.mtd_pct)}</span><span class="s">excess of cash</span></div>
          <div class="stat"><span class="k">Total return (incl. T-bill)</span><span class="v ${signClass(c.total_since_start_pct)}">${fmtPct(c.total_since_start_pct, 2, true)}</span><span class="s">display only</span></div>
          <div class="stat"><span class="k">Max drawdown</span><span class="v bad">${fmtPct(c.max_drawdown_pct, 2)}</span><span class="s">from the peak</span></div>
        </div>
        <div class="card"><div class="chart"><canvas id="c-com-equity"></canvas></div>
          ${legendRow([['Commodities, excess of cash', '--c-trials'], ['Total return (incl. T-bill)', '--c-trials', true]])}${totalLine(c)}</div>
      </section>
      <section class="section"><div class="section-head"><h2>Positions (${esc(monthName(c.last_rebalance, U))})</h2>${info('Set at the rebalance settlement on the 3rd and held through the month. Contracts = k × the shadow weight × US$100m ÷ each contract\'s value at that settlement, rounded; the returns use the exact weights, so rounding changes nothing reported. % of risk = each position\'s share of the book\'s risk (weight × the sleeve\'s own volatility estimate). No price is published: settlements are licensed.')}</div>
        ${posRows ? `<div class="table-wrap"><table class="stack"><thead><tr><th>Market</th><th>Side</th><th>Contract month</th><th class="num">Contracts</th><th class="num">% of risk</th></tr></thead><tbody>${posRows}</tbody></table></div>` : '<p class="empty">No position this month.</p>'}
      </section>
      <section class="section"><div class="section-head"><h2>Monthly returns</h2>${info('Book = k × the shadow\'s monthly net return at decisive costs, exactly. The current month is month to date.')}</div>
        <div class="card"><div class="chart"><canvas id="c-com-monthly"></canvas></div>
          <div class="table-wrap"><table class="compact"><thead><tr><th>Month</th><th class="num">Book</th><th class="num">Shadow</th></tr></thead><tbody>${monRows}</tbody></table></div>
          ${tbillTable(c)}</div></section>
      <section class="section"><div class="section-head"><h2>Drawdown</h2></div>
        <div class="card"><div class="chart"><canvas id="c-com-dd"></canvas></div></div></section>
      <section class="section"><div class="section-head"><h2>Volatility: realised vs ${fmtPct(c.target_pct || vol.target_pct, 0)} target</h2>${info('Realised volatility of the book\'s daily returns, annualised (√252): since the start, and over the last 3 months (63 trading days). The sleeve aims at 10% with its own 36-month scaler; k was set once on the backtest and is never re-estimated, so realised volatility will drift around the target.')}</div>
        <div class="stats">
          <div class="stat"><span class="k">Since start</span><span class="v">${isNum(vol.since_start_pct) ? fmtPct(vol.since_start_pct, 1) : '—'}</span><span class="s">daily, annualised</span></div>
          <div class="stat"><span class="k">Last 3 months</span><span class="v">${isNum(vol.last_3m_pct) ? fmtPct(vol.last_3m_pct, 1) : '—'}</span><span class="s">63 trading days</span></div>
          <div class="stat"><span class="k">Monthly, since start</span><span class="v">${isNum(vol.monthly_since_start_pct) ? fmtPct(vol.monthly_since_start_pct, 1) : '—'}</span><span class="s">from 6 months</span></div>
          <div class="stat"><span class="k">Target</span><span class="v">${fmtPct(vol.target_pct, 0)}</span><span class="s">annual</span></div>
        </div>
        ${(c.rolling_vol || []).length > 1 ? '<div class="card"><div class="chart"><canvas id="c-com-vol"></canvas></div></div>' : '<p class="small muted">The chart starts after 10 trading days.</p>'}
      </section>
      <section class="section"><div class="card">${rules}
        <p class="small">The shadow's 2031 evaluation is unaffected: it is judged on the shadow's own returns, which this book only reads (pre-registration docs/prereg/T25-T26_live_shadows.md).</p></div></section>`;
    if ((c.series || []).length) {
      dateChart('c-com-equity', [{ label: 'Commodities, excess of cash', data: c.series, color: '--c-trials', fill: true },
        ...totalDataset(c, 'Commodities', '--c-trials')], { fmt: (v) => fmtNum(v, 2) });
    }
    if (months.length) monthlyBarChart('c-com-monthly', months);
    if ((c.drawdown || []).length) dateChart('c-com-dd', [{ label: 'Drawdown, %', data: c.drawdown, color: '--series-down', fill: true }], { fmt: (v) => fmtPct(v, 1) });
    const rv = c.rolling_vol || [];
    if (rv.length > 1) {
      dateChart('c-com-vol', [{ label: 'Realised, last 3 months', data: rv, color: '--c-trials' },
        { label: 'Target', data: rv.map((p) => [p[0], vol.target_pct]), color: '--muted', dash: [5, 4], width: 1.4 }], { fmt: (v) => fmtPct(v, 1) });
    }
  };
})();
