"""Morning report: "Site and writers on main" (2026-11-17, docs/config_changes.md).

ledger-pages failed on every run from 11 to 17 Nov 2026 and the published site stayed at 11 Nov; the morning report
listed only the night shift's own runs, so nobody was told. The section lists the latest runs on main of ledger-pages
(with the published site's build time) and ledger-daily, and the Janus checks, marks what is failing, stale or late,
and puts it in Needs Ethan. Stubbed API answers and made-up records; no network.
"""
from datetime import date, datetime, timezone

from nightshift import morning as M

NOW = datetime(2026, 11, 16, 22, 50, tzinfo=timezone.utc)      # 06:50 Singapore, 17 Nov
DAY = date(2026, 11, 17)


def run(n, conclusion, started, status="completed"):
    return {"run_number": n, "status": status, "conclusion": conclusion, "run_started_at": started}


def api(pages_runs, daily_runs, built_at="2026-11-16T22:20:00+00:00"):
    def fetch(url):
        if url == M.SITE_META:
            return {"built_at": built_at} if built_at else None
        if "ledger-pages.yml" in url:
            return {"workflow_runs": pages_runs}
        if "ledger-daily.yml" in url:
            return {"workflow_runs": daily_runs}
        raise AssertionError(url)
    return fetch


def janus(check_at="2026-11-16T22:45:00+00:00", review_date="2026-11-16"):
    return [{"type": "run", "session": "daily_review", "date": review_date, "sources_read": [{"title": "a", "url": "https://example.org/a"}],
             "recorded_at": f"{review_date}T23:15:00+00:00"},
            {"type": "check", "recorded_at": check_at, "result": "no change"}]


def test_the_11_17_nov_failure_is_reported_and_needs_ethan():
    pages = [run(498, "failure", "2026-11-17T01:12:00Z"), run(497, "failure", "2026-11-16T22:19:00Z"),
             run(496, None, "2026-11-16T21:00:00Z", status="in_progress"), run(495, "cancelled", "2026-11-16T20:00:00Z"),
             run(299, "failure", "2026-11-11T03:10:00Z"), run(298, "success", "2026-11-11T02:48:00Z")]
    daily = [run(42, "success", "2026-11-16T22:07:00Z")]
    lines, needs = M.status_section(DAY, NOW, (janus(), ""), api(pages, daily, "2026-11-11T02:48:30+00:00"))
    assert lines[0] == ("ledger-pages: FAILING - 3 run(s) in a row (failure, latest #498 17 Nov 01:12Z); last success "
                        "#298 11 Nov 02:48Z (5.8 days ago); published site built 11 Nov 02:48Z (5.8 days ago) STALE")
    assert lines[1] == "ledger-daily: ok - #42 16 Nov 22:07Z succeeded"
    assert lines[2].startswith("Janus checks: last quick check 16 Nov 22:45Z (0 h ago); last daily review 2026-11-16 (ok")
    assert len(needs) == 1 and needs[0].startswith("ledger-pages not healthy =>")


def test_healthy_says_ok_and_needs_nothing():
    lines, needs = M.status_section(DAY, NOW, (janus(), ""), api([run(500, "success", "2026-11-16T22:20:00Z")],
                                                                 [run(42, "success", "2026-11-16T22:07:00Z")]))
    assert lines[0].startswith("ledger-pages: ok - #500") and "STALE" not in lines[0]
    assert needs == []


def test_unreadable_late_and_stale_are_said_never_skipped():
    def down(url):
        return None
    lines, needs = M.status_section(DAY, NOW, (janus(check_at="2026-11-13T15:33:00+00:00", review_date="2026-11-12"),
                                               "main not refreshed (fetch failed)"), down)
    assert lines[0].startswith("ledger-pages: status unknown (GitHub Actions API unreadable); published site: build "
                               "time unreadable")
    assert lines[1] == "ledger-daily: status unknown (GitHub Actions API unreadable)"
    assert lines[2].startswith("[main not refreshed (fetch failed)] Janus checks: last quick check 13 Nov 15:33Z "
                               "(3.3 days ago, LATE: due hourly); last daily review 2026-11-12 (MISSING)"), lines[2]
    assert len(needs) == 3
    # a success that is too old is stale; no success at all among the runs read is said as such
    old = api([run(1, "failure", "2026-11-16T20:00:00Z")], [run(2, "success", "2026-11-14T22:07:00Z")])
    lines, _ = M.status_section(DAY, NOW, (janus(), ""), old)
    assert "no success in the last 1 runs" in lines[0] and "1+ run(s) in a row" in lines[0]
    assert lines[1].startswith("ledger-daily: STALE - no run on main since #2 14 Nov 22:07Z")


def test_report_puts_the_section_on_top_and_failures_in_needs(monkeypatch, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/queue.md").write_text(
        "<!-- queue:start -->\n| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |\n"
        "|---|---|---|---|---|---|---|---|\n<!-- queue:end -->\n", encoding="utf-8")
    cfg = {"run_cap": 12, "safe_mode": {"enabled": False, "run_cap": 4}, "window": {}}
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M.S, "load", lambda *a, **k: {"log": []})
    monkeypatch.setattr(M.C, "load", lambda *a, **k: cfg)
    monkeypatch.setattr(M.C, "now_utc", lambda: NOW)
    for name, val in (("promoted", "no - fixture"), ("merged_into_dev", []), ("v1_rules_state", None),
                      ("v1_rules_section", ["fixture"]), ("lab_section", ["fixture"]), ("janus_section", ["fixture"])):
        monkeypatch.setattr(M, name, lambda *a, _v=val, **k: _v)
    monkeypatch.setattr(M, "janus_records", lambda: (janus(), ""))
    pages = [run(498, "failure", "2026-11-17T01:12:00Z"), run(298, "success", "2026-11-11T02:48:00Z")]
    monkeypatch.setattr(M.G, "_fetch", api(pages, [run(42, "success", "2026-11-16T22:07:00Z")], "2026-11-11T02:48:30Z"))
    text = M.build(DAY, "origin/dev", ["something else => do it"])
    lines = text.splitlines()
    i = lines.index("**Site and writers on main:**")
    assert lines[i - 2].startswith("**Promoted to main:**") and lines[i + 1].startswith("- ledger-pages: FAILING")
    needs = lines[lines.index("**Needs Ethan:**") + 1:]
    assert needs[0].startswith("- ledger-pages not healthy =>") and needs[1] == "- something else => do it"
