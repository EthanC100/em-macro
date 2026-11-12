"""Q026: promotion check b ignores data/meta.json audit.checked_at (the wall-clock second the audit ran), as it
ignores built_at, so two identical builds a second apart pass; the audit's ok, label and detail still count."""
import json

from nightshift import promote as PR


def meta(**audit):
    a = {"ok": True, "label": "record verified", "detail": "", "checked_at": "2026-11-12T06:40:01+00:00"} | audit
    return {"built_at": "1", "commit": "x", "today": "2026-11-12", "audit": a}


def builds(tmp_path, ma, mb):
    for name, m in (("a", ma), ("b", mb)):
        d = tmp_path / name / "data"
        d.mkdir(parents=True)
        (d / "meta.json").write_text(json.dumps(m))
    return PR.compare_builds(tmp_path / "a", tmp_path / "b")


def test_builds_differing_only_in_audit_checked_at_match(tmp_path):
    assert builds(tmp_path, meta(), meta(checked_at="2026-11-12T06:40:07+00:00")) == []


def test_any_other_audit_change_still_differs(tmp_path):
    for k, v in (("ok", False), ("label", "record BROKEN"), ("detail", "seal 12 does not match")):
        sub = tmp_path / k
        d = builds(sub, meta(), meta(checked_at="2026-11-12T06:40:07+00:00", **{k: v}))
        assert d == [{"file": "data/meta.json", "paths": [f".audit.{k}"]}]
        assert [x["file"] for x in PR.unexplained(d, set())] == ["data/meta.json"]


def test_checked_at_is_ignored_only_in_meta_json(tmp_path):
    for name, t in (("a", "1"), ("b", "2")):
        d = tmp_path / name / "data"
        d.mkdir(parents=True)
        (d / "janus.json").write_text(json.dumps({"watchdog": {"checked_at": t}}))
    assert PR.compare_builds(tmp_path / "a", tmp_path / "b") == [
        {"file": "data/janus.json", "paths": [".watchdog.checked_at"]}]
