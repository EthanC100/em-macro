"""Offline operational checks. No network, credentials, issue writes or dispatches.

Inputs are bounded Actions API snapshots and an independently approved workflow
digest baseline. Outputs contain fixed status words and counts only; never API
titles, exception messages, logs or research results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from .inputs import read_bytes, read_json

WORKFLOW = ".github/workflows/manhattan-ops-runner.yml"
MAX_RUNS = 1000
MAX_BYTES = 2_000_000
MAX_WORKFLOW_BYTES = 8_000_000
MAX_WORKFLOW_FILES = 1000


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def watchdog(runs: list[dict], *, now: datetime, activated: datetime | None = None,
             enabled: bool = False, grace_minutes: int = 720,
             runtime_minutes: int = 75) -> dict:
    """Check weekday 23:41 UTC slots since owner activation (at most 31 days).

    Successes are associated by creation time, so rerunning an old run cannot
    satisfy a new slot. A delayed start may satisfy its slot up to the next
    slot. Grace delays the alert, not the requirement for a successful run.
    Every overdue slot is checked, including gaps followed by a later success.
    The owner must explicitly enable checks; no schedule is inferred or enabled.
    """
    if not enabled:
        return {"status": "disabled", "missed": 0, "failed": 0, "pending": 0}
    if now.tzinfo is None or activated is None or activated.tzinfo is None:
        raise ValueError("explicit activation and aware clock required")
    now, activated = now.astimezone(timezone.utc), activated.astimezone(timezone.utc)
    if activated > now or now - activated > timedelta(days=31):
        raise ValueError("activation outside bounded monitoring window")
    if not 0 <= grace_minutes <= 2880 or not 1 <= runtime_minutes <= 1440:
        raise ValueError("invalid deadline")
    if not isinstance(runs, list) or len(runs) > MAX_RUNS:
        raise ValueError("invalid or truncated run snapshot")
    selected = []
    for r in runs:
        if r.get("path") != WORKFLOW or r.get("head_branch") != "main" \
                or r.get("event") not in ("schedule", "workflow_dispatch"):
            continue
        created = utc(r["created_at"])
        updated = utc(r["updated_at"])
        if updated < created or created > now or updated > now:
            raise ValueError("inconsistent run timestamps")
        if r["status"] not in ("queued", "in_progress", "completed", "waiting", "requested", "pending"):
            raise ValueError("unknown Actions status")
        selected.append((created, r["status"], r.get("conclusion")))
    slots = []
    day = activated.date()
    while day <= now.date():
        due = datetime.combine(day, time(23, 41), timezone.utc)
        if day.weekday() < 5 and activated <= due <= now:
            slots.append(due)
        day += timedelta(days=1)
    missed = failed = pending = 0
    for i, due in enumerate(slots):
        end = slots[i + 1] if i + 1 < len(slots) else now + timedelta(microseconds=1)
        candidates = [(created, status, conclusion) for created, status, conclusion in selected
                      if due <= created < end]
        if any(status == "completed" and conclusion == "success" for _, status, conclusion in candidates):
            continue
        if now <= due + timedelta(minutes=grace_minutes):
            pending += 1
        elif any(status != "completed" and now <= min(created + timedelta(minutes=runtime_minutes),
                                                      due + timedelta(minutes=grace_minutes + runtime_minutes))
                 for created, status, _ in candidates):
            pending += 1
        elif candidates:
            failed += 1
        else:
            missed += 1
    return {"status": "alert" if missed or failed else "pending" if pending else "ok",
            "missed": missed, "failed": failed, "pending": pending}


def workflow_digests(root: Path) -> dict[str, str]:
    """Hash only workflow files. Refuse symlinks, oversized files and directories."""
    directory = root / ".github/workflows"
    if (root / ".github").is_symlink() or directory.is_symlink() or not directory.is_dir():
        raise ValueError("invalid workflow directory")
    result, total = {}, 0
    for index, path in enumerate(directory.iterdir()):
        if index >= MAX_WORKFLOW_FILES:
            raise ValueError("workflow entry bound exceeded")
        if path.suffix not in (".yml", ".yaml"):
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError("invalid workflow file")
        raw = read_bytes(path, max_bytes=min(MAX_BYTES, MAX_WORKFLOW_BYTES - total))
        total += len(raw)
        result[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
    if not result:
        raise ValueError("empty workflow tree")
    return result


def integrity(current: dict, approved: dict) -> dict:
    """Compare with an owner-trusted digest set; report additions/deletions too.

    Never generate trust from commit messages, authors or a baseline changed in
    the same PR. This function does not verify GitHub review authenticity.
    """
    for snapshot in (current, approved):
        if not isinstance(snapshot, dict) or not snapshot or len(snapshot) > 1000:
            raise ValueError("invalid baseline")
        for path, digest in snapshot.items():
            if not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", path) \
                    or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid digest entry")
    added = len(current.keys() - approved.keys())
    removed = len(approved.keys() - current.keys())
    changed = sum(current[p] != approved[p] for p in current.keys() & approved.keys())
    return {"status": "review_required" if added or removed or changed else "ok",
            "added": added, "removed": removed, "changed": changed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    watch = sub.add_parser("watchdog")
    watch.add_argument("--runs", required=True, help="JSON array; collect all pages, max 1000 runs")
    watch.add_argument("--now", required=True)
    watch.add_argument("--activated")
    watch.add_argument("--enabled", action="store_true")
    watch.add_argument("--grace-minutes", type=int, default=720)
    check = sub.add_parser("integrity")
    check.add_argument("--root", type=Path, default=Path.cwd())
    check.add_argument("--approved", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "watchdog":
            result = watchdog(read_json(args.runs), now=utc(args.now),
                              activated=utc(args.activated) if args.activated else None,
                              enabled=args.enabled, grace_minutes=args.grace_minutes)
        else:
            result = integrity(workflow_digests(args.root), read_json(args.approved))
    except (ValueError, KeyError, TypeError, OSError, AttributeError):
        # Do not echo malformed input or exception text to any public channel.
        print('{"status":"invalid_input"}')
        return 2
    print(json.dumps(result, sort_keys=True))
    return int(result["status"] not in ("ok", "disabled", "pending"))


if __name__ == "__main__":
    raise SystemExit(main())
