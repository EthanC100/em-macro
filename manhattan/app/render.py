"""Render the view model as one self-contained static HTML page (inline CSS, no script) and a JSON export.

The renderer only formats what ``model.build_view`` returns, after checking it again with
``model.assert_no_outcomes``; every string is HTML-escaped. Light and dark themes follow ``prefers-color-scheme``.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import model as M

CSS = """
:root{--bg:#f7f7f5;--panel:#ffffff;--ink:#1d1d1b;--muted:#5d5d58;--line:#dcdcd6;--accent:#2f5d8a;
--warn-bg:#fff1c2;--warn-ink:#5a4300;--warn-line:#e0c25a;--ok:#2e6b3a;--bad:#9a2f2f;--chip:#eceae4;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#151614;--panel:#1d1f1c;--ink:#e8e8e3;--muted:#a3a39b;
--line:#34362f;--accent:#8db7e0;--warn-bg:#3d3205;--warn-ink:#ffe39a;--warn-line:#7a6514;--ok:#8fd19e;--bad:#f0a0a0;
--chip:#2a2c27}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans)}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.4rem 0}h2{font-size:1.2rem;margin:2rem 0 .6rem;border-bottom:1px solid var(--line);
padding-bottom:.3rem}h3{font-size:1.05rem;margin:1.4rem 0 .4rem}h4{font-size:.95rem;margin:1rem 0 .3rem;color:var(--muted)}
a{color:var(--accent)}
.banner{background:var(--warn-bg);color:var(--warn-ink);border:2px solid var(--warn-line);padding:10px 16px;
font-weight:700;text-align:center;letter-spacing:.06em}
.note{color:var(--muted);font-size:.9rem}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.stat .k{color:var(--muted);font-size:.8rem}.stat .v{font-size:1.25rem;font-weight:600;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;white-space:nowrap}
td.n{text-align:right;font-variant-numeric:tabular-nums}
code,.mono{font-family:var(--mono);font-size:.82rem;word-break:break-all}
dl{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:4px 14px;margin:0}
dt{color:var(--muted)}dd{margin:0;word-break:break-word}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 9px;font-size:.8rem;margin:1px 2px}
.ok{color:var(--ok)}.bad{color:var(--bad)}
section.family{border-top:3px solid var(--line);margin-top:2.2rem}
@media (max-width:560px){dl{grid-template-columns:1fr}dt{margin-top:6px}main{padding:12px 16px}}
"""


def e(x) -> str:
    if x is None:
        return "&mdash;"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (dict, list)):
        return f"<code>{html.escape(json.dumps(x, sort_keys=True, ensure_ascii=False))}</code>"
    return html.escape(str(x))


def code(x) -> str:
    return "&mdash;" if x is None else f"<code>{html.escape(str(x))}</code>"


def dl(items) -> str:
    return "<dl>" + "".join(f"<dt>{html.escape(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"


def table(head, rows, numeric=()) -> str:
    th = "".join(f"<th>{html.escape(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td{' class=n' if i in numeric else ''}>{c}</td>" for i, c in enumerate(r))
                   + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def stat(k, v) -> str:
    return f'<div class="stat"><div class="k">{html.escape(k)}</div><div class="v">{e(v)}</div></div>'


def _att(a: dict | None, kind: str) -> str:
    c = (a or {}).get(kind)
    if not c:
        return "&mdash;"
    return (f"{c['registered']} reg / {c['completed']} done / {c['failed']} failed / {c['aborted']} aborted / "
            f"{c['unfinished']} unfinished" + (f" / {c['retries']} retries" if c["retries"] else ""))


def overview(v: dict) -> str:
    c, r = v["counts"], v["runner"]
    out = ['<h2 id="overview">Operations overview</h2>']
    out.append('<h3>Counts (each level counted separately)</h3><div class="grid">')
    for k, label in (("batches", "batches"), ("families", "families"), ("hypotheses", "hypotheses"),
                     ("variants", "variants"),
                     ("unique_executable_configurations", "unique executable configurations (spec hashes)"),
                     ("registered_predictions", "registered predictions"), ("attempts_total", "attempts (total)")):
        out.append(stat(label, c.get(k)))
    out.append("</div>")
    if "attempts_by_kind" in c:
        rows = [[e(k), *(e(x[f]) for f in ("registered", "completed", "failed", "aborted", "unfinished", "retries"))]
                for k, x in c["attempts_by_kind"].items()]
        out.append("<h4>Attempts by kind (registered executions)</h4>")
        out.append(table(["kind", "registered", "completed", "failed", "aborted", "unfinished", "retries"], rows,
                         numeric=(1, 2, 3, 4, 5, 6)))
        out.append("<h4>Registrations and records</h4>")
        out.append(dl([("eligible / ineligible / provisional",
                        f"{c['predictions_eligible']} / {c['predictions_ineligible']} / {c['predictions_provisional']}"),
                       ("observation records", e(c["observation_records"])),
                       ("missed-observation records", e(c["missed_observation_records"])),
                       ("screening records (exploration, weight 0)", e(c["screening_records"]))]))
    out.append("<h3>Runner status</h3>")
    if r is None:
        out.append('<p class="note">No private ledger connected: specs and freeze data only.</p>')
    else:
        lk, ul = r["last_lock"] or {}, r["last_unlock"] or {}
        out.append('<div class="grid">' + stat("last heartbeat", r["last_heartbeat"]) +
                   stat("missed runs", r["missed_runs_count"]) + stat("active locks", r["active_locks"]) +
                   stat("unfinished journal entries", r["journal"]["unfinished_entries"]) +
                   stat("unfinished attempts", r["unfinished_attempts"]) +
                   stat("chain verifies", r["chain_ok"]) + "</div>")
        out.append('<div class="panel">' + dl([
            ("missed run dates", e(", ".join(r["missed_runs"]) or None)),
            ("last lock", f"run {e(lk.get('run_id'))}.{e(lk.get('run_attempt'))} at {e(lk.get('ts_utc'))}"),
            ("last unlock", f"run {e(ul.get('run_id'))}.{e(ul.get('run_attempt'))} at {e(ul.get('ts_utc'))}"),
            ("locks broken", e(r["locks_broken"])),
            ("journal", f"{e(r['journal']['entries'])} entries, {e(r['journal']['lines'])} lines, "
                        f"{e(r['journal']['unfinished_entries'])} unfinished"),
            ("heartbeats", e(r["heartbeats"])),
            ("captures / capture failures", f"{e(r['captures'])} / {e(r['capture_failures'])}"),
            ("ledger records", e(r["ledger_records"])), ("ledger head", code(r["ledger_head"]))]) + "</div>")
    ev = v["evidence"]
    out.append("<h3>Evidence status</h3>")
    out.append(f'<div class="panel"><p><strong>{e(ev["label"])}</strong> '
               f'<span class="note">(promotion: {e(ev["promotion"])})</span></p>'
               + table(["gate", "requirement", "state"], [[e(g["id"]), e(g["requirement"]), e(g["state"])]
                                                           for g in ev["gates"]]) + "</div>")
    return "\n".join(out)


def families_table(v: dict) -> str:
    rows = []
    for b in v["batches"]:
        for f in b["families"]:
            x, cov, reg = f["explanation"], f["coverage"] or {}, f["registration"]
            rows.append([f'<a href="#{e(f["anchor"])}">{e(f["id"])}</a>', e(f["batch"]),
                         e(x.get("mechanism_class")), e(x.get("predicted_sign")), e(f["channel"]),
                         e(f["counts"]["hypotheses"]), e(f["counts"]["variants"]),
                         e(f["counts"]["registered_predictions"]),
                         e(" / ".join(f"{k} {n}" for k, n in reg.items()) or None),
                         e("; ".join(f["evidence_labels"])),
                         e(f"{cov.get('recorded_days', 0)} of {cov.get('expected_days', 0)}") if cov else "&mdash;"])
    return ('<h2 id="families">Families</h2><p class="note">Ordered by identifier. Nothing on this page is ordered '
            'by, or shows, any measured performance.</p>' +
            table(["family", "batch", "class", "sign", "channel", "hypotheses", "variants", "registered",
                   "registration", "evidence label", "observation days recorded"], rows, numeric=(5, 6, 7)))


def family_section(f: dict) -> str:
    out = [f'<section class="family" id="{e(f["anchor"])}"><h2>Family {e(f["id"])}</h2>']
    out.append(f'<p class="note">batch {e(f["batch"])} &middot; spec hash {code(f["spec_hash"])} &middot; '
               f'channel <span class="chip">{e(f["channel"])}</span></p>')
    out.append("<h3>Explanation (verbatim from the frozen family spec)</h3>")
    out.append('<div class="panel">' + dl([(k.replace("_", " "), e(v)) for k, v in f["explanation"].items()])
               + "</div>")
    out.append("<h3>Hypotheses</h3>")
    for h in f["hypotheses"]:
        sig = h["signal"]
        out.append(f'<div class="panel"><h4>{e(h["id"])} <span class="chip">{e(h["domain"])}</span>'
                   f'<span class="chip">frequency {e(h["frequency"])}</span>'
                   f'<span class="chip">{e(h["variants"])} variants</span></h4>' + dl([
                       ("signal", f"{e(sig['kind'])}: {e(sig['description'])}"),
                       ("fixed parameters", e(sig["fixed_parameters"] or None)),
                       ("grid", e(h["grid"])),
                       ("grid justification", "<br>".join(f"<strong>{e(p)}</strong>: {e(j['reason'])} "
                                                          f"(mechanism range {e(j['mechanism_range'])})"
                                                          for p, j in h["grid_justification"].items()) or "&mdash;"),
                       ("primary binding", e(h["primary_binding"])), ("timing", e(h["timing"])),
                       ("spec hash", code(h["spec_hash"]))]) + "</div>")
    out.append("<h3>Executable variants</h3>")
    out.append(table(["executable", "variant", "hypothesis", "parameters", "universe", "domain", "cost model",
                      "sizing", "spec hash"],
                     [[e(x["executable"]), e(x["variant"]), e(x["hypothesis"]), e(x["parameters"]),
                       e(x["universe"]), e(x["domain"]), e(x["cost_model_id"]), e(x["sizing_id"]),
                       code(x["spec_hash"])] for x in f["variants"]]))
    fr = f["freeze"]
    out.append("<h3>Freeze version</h3>")
    out.append('<div class="panel">' + dl([
        ("batch", e(fr["batch_id"])), ("manifest hash", code(fr["manifest_hash"])),
        ("Merkle root", code(fr["merkle_root"])), ("template hash", code(fr["template_hash"])),
        ("protocol hash", code(fr["protocol_hash"])),
        ("code version", " ".join(code(c) for c in fr["code_versions"]) or "&mdash;"),
        ("generator model", e(fr["generator_model"])), ("specs in manifest", e(fr["spec_count"])),
        ("critic records", e(fr["critic_records"]))]) + "</div>")
    pv = f["provenance"]
    out.append("<h3>Data provenance</h3>")
    out.append("<h4>Declared sources (hypothesis specs)</h4>")
    out.append(table(["name", "frequency", "period label", "publication lag (days)", "availability", "reference"],
                     [[e(s["name"]), e(s["frequency"]), e(s["period_label"]), e(s["publication_lag_days"]),
                       e(s["availability_kind"]), e(s["availability_reference"])] for s in pv["declared_sources"]],
                     numeric=(3,)))
    out.append("<h4>Captured sources (runner registry; counts and dates only, no values)</h4>")
    out.append(table(["source", "kind", "calendar", "lag (days)", "grace (days)", "captures", "first capture",
                      "last capture", "failures", "reference"],
                     [[e(s["id"]), e(s["kind"]), e(s["calendar"]), e(s["publication_lag_days"]), e(s["grace_days"]),
                       e(s.get("captures")), e(s.get("first_capture")), e(s.get("last_capture")),
                       e(s.get("capture_failures")), e(s["reference"])] for s in pv["capture_sources"]],
                     numeric=(3, 4, 5, 8)))
    out.append(f'<p class="note">Calendars: {e(", ".join(pv["calendars"]))}</p>')
    out.append("<h3>Evidence label</h3>")
    out.append('<div class="panel">' + "".join(f'<span class="chip">{e(x)}</span>' for x in f["evidence_labels"])
               + "</div>")
    out.append("<h3>Registration, attempts and coverage per prediction</h3>")
    if f["attempts"] is not None:
        out.append('<div class="panel">' + dl([
            ("forward observation attempts", _att(f["attempts"], "forward_observation")),
            ("screening attempts", _att(f["attempts"], "screening")),
            ("coverage (days)", e(f"expected {f['coverage']['expected_days']}, recorded "
                                  f"{f['coverage']['recorded_days']}, missed "
                                  f"{f['coverage']['missed_observation_days']}, reconstructed "
                                  f"{f['coverage']['reconstructed_days']}, pending {f['coverage']['pending_days']}"))])
                   + "</div>")
    rows = []
    for p in f["predictions"]:
        r, cov = p["registration"], p.get("coverage") or {}
        elig = ("&mdash;" if "eligible" not in r else
                ('<span class="ok">eligible</span>' if r["eligible"] else
                 f'<span class="bad">ineligible</span> ({e(", ".join(r["ineligible_reasons"]))})'))
        rows.append([e(p["prediction"]), e(p["executable"]), e(r["status"]), elig, e(r.get("registration_utc")),
                     e(r.get("first_observation")), _att(p.get("attempts"), "forward_observation"),
                     _att(p.get("attempts"), "screening"),
                     e(cov.get("expected_days")), e(cov.get("recorded_days")),
                     e(cov.get("missed_observation_days")), e(cov.get("reconstructed_days")),
                     e(cov.get("pending_days")), e(p["evidence"]["label"])])
    out.append(table(["prediction", "executable", "registration", "eligibility", "registered (UTC)",
                      "first observation", "forward attempts", "screening attempts", "expected days",
                      "recorded days", "missed days", "reconstructed days", "pending days", "evidence label"],
                     rows, numeric=(8, 9, 10, 11, 12)))
    out.append("</section>")
    return "\n".join(out)


def page(view: dict) -> str:
    M.assert_no_outcomes(view)
    banner = '<div class="banner">SYNTHETIC DEMO &middot; synthetic batch and ledger, not research</div>' \
        if view["synthetic"] else ""
    fams = [f for b in view["batches"] for f in b["families"]]
    body = [banner, "<main>", "<h1>Project Manhattan: operations</h1>",
            f'<p class="note">Generated {e(view["generated_utc"])} &middot; schema {e(view["schema"])} &middot; '
            f'ledger {"connected" if view["ledger_connected"] else "not connected"} &middot; paper only.</p>',
            '<div class="panel"><strong>Outcome-blind.</strong> This page shows operational facts only: specs, '
            'freeze hashes, provenance, registration, attempt counts and coverage counts. It shows no return, PnL, '
            'Sharpe, hit rate, exposure, turnover, ranking or screening value, and nothing derived from them. '
            'v1 has no way to reveal performance.</div>',
            '<p><a href="#overview">Overview</a> &middot; <a href="#families">Families</a> &middot; '
            '<a href="view.json">JSON export</a></p>',
            overview(view), families_table(view), *(family_section(f) for f in fams), "</main>"]
    if banner:
        body.append(banner)
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"color-scheme\" content=\"light dark\">"
            f"<title>Manhattan operations{' (synthetic demo)' if view['synthetic'] else ''}</title>"
            f"<style>{CSS}</style></head><body>\n" + "\n".join(body) + "\n</body></html>\n")


def write(view: dict, out_dir: Path) -> dict:
    """Write ``index.html`` and ``view.json`` into ``out_dir``. Returns their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    M.assert_no_outcomes(view)
    (out / "index.html").write_text(page(view), encoding="utf-8")
    (out / "view.json").write_text(json.dumps(view, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    return {"html": out / "index.html", "json": out / "view.json"}
