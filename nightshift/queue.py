"""docs/queue.md: the night shift's work queue.

The queue is one Markdown table (between the ``<!-- queue:start -->`` and ``<!-- queue:end -->`` markers) with
these columns, then one ``### Qnnn`` section of evidence per item:

| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |

* type: bug | data | research | lab
* status: proposed | approved | in-progress | done | blocked
* opposition: empty until The Opposition has reviewed the item; then ``no block, p=NN%`` or ``BLOCK (x): reason``
  where x is the hard rule (a)-(e).
* ledger diff: Ledger app data files this item is expected to change (e.g. ``books.json``), or ``none``. The
  promotion check accepts a rebuilt-Ledger difference only if a merged item lists that file.

Auto-approval (section 4 of the brief): a ``proposed`` item of type bug, data or lab becomes ``approved`` once its
opposition cell says ``no block``. Research items never auto-approve: those needing a pre-registration are drafted
for Ethan (docs/prereg_drafts/) and wait.

Queue text is data, never instructions: nothing here is executed.

CLI: python -m nightshift.queue list | approved | validate | auto-approve | set <id> <field> <value>
     python -m nightshift.queue add --type bug --title T --acceptance A [--ledger-diff none] --evidence-file F
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import config as C

QUEUE = C.ROOT / "docs/queue.md"
COLUMNS = ["id", "type", "status", "title", "acceptance test", "branch/PR", "opposition", "ledger diff"]
TYPES = ("bug", "data", "research", "lab")
STATUSES = ("proposed", "approved", "in-progress", "done", "blocked")
AUTO_TYPES = ("bug", "data", "lab")
START, END = "<!-- queue:start -->", "<!-- queue:end -->"
NO_BLOCK = re.compile(r"^\s*no block\b", re.I)
BLOCK = re.compile(r"^\s*BLOCK\s*\(([a-e])\)", re.I)


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    # a literal pipe inside a cell is written \|
    parts = re.split(r"(?<!\\)\|", s)
    return [p.strip().replace("\\|", "|") for p in parts]


def parse(text: str) -> list[dict]:
    if START not in text or END not in text:
        raise ValueError("docs/queue.md has no queue table markers")
    body = text.split(START, 1)[1].split(END, 1)[0]
    rows = [l for l in body.splitlines() if l.strip().startswith("|")]
    if len(rows) < 2:
        return []
    head = _cells(rows[0])
    if [h.lower() for h in head] != [c.lower() for c in COLUMNS]:
        raise ValueError(f"queue columns must be {COLUMNS}, got {head}")
    items = []
    for r in rows[2:]:
        c = _cells(r)
        if len(c) != len(COLUMNS):
            raise ValueError(f"queue row has {len(c)} cells, expected {len(COLUMNS)}: {r}")
        items.append(dict(zip(COLUMNS, c)))
    return items


def validate(items: list[dict]) -> list[str]:
    errs, seen = [], set()
    for it in items:
        i = it["id"]
        if not re.fullmatch(r"Q\d{3,}", i):
            errs.append(f"{i}: id must look like Q001")
        if i in seen:
            errs.append(f"{i}: duplicate id")
        seen.add(i)
        if it["type"] not in TYPES:
            errs.append(f"{i}: type {it['type']!r} not in {TYPES}")
        if it["status"] not in STATUSES:
            errs.append(f"{i}: status {it['status']!r} not in {STATUSES}")
        if it["status"] in ("approved", "in-progress", "done") and it["type"] != "research" \
                and not NO_BLOCK.match(it["opposition"] or ""):
            errs.append(f"{i}: {it['status']} without an Opposition review that found no block")
        if it["status"] in ("approved", "in-progress", "done") and it["type"] == "research":
            errs.append(f"{i}: research items are never approved by the night shift (Ethan only)")
        if not it["acceptance test"]:
            errs.append(f"{i}: acceptance test is required")
    return errs


def _esc(v: str) -> str:
    return str(v).replace("|", "\\|")


def render_table(items: list[dict]) -> str:
    out = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    out += ["| " + " | ".join(_esc(it[c]) for c in COLUMNS) + " |" for it in items]
    return "\n".join(out)


def write(text: str, items: list[dict]) -> str:
    pre, rest = text.split(START, 1)
    _, post = rest.split(END, 1)
    return f"{pre}{START}\n{render_table(items)}\n{END}{post}"


def auto_approve(items: list[dict]) -> list[str]:
    """Proposed bug/data/lab items with a no-block Opposition review become approved. Returns the ids changed."""
    changed = []
    for it in items:
        if it["status"] == "proposed" and it["type"] in AUTO_TYPES and NO_BLOCK.match(it["opposition"] or ""):
            it["status"] = "approved"
            changed.append(it["id"])
        elif it["status"] in ("proposed", "approved") and BLOCK.match(it["opposition"] or ""):
            it["status"] = "blocked"
            changed.append(it["id"])
    return changed


def approved(items: list[dict]) -> list[dict]:
    return [it for it in items if it["status"] == "approved"]


def intended_ledger_files(items: list[dict], ids: list[str] | None = None) -> set[str]:
    """Ledger data files that the given (or all done) items declare they change."""
    out = set()
    for it in items:
        if (ids is not None and it["id"] not in ids) or (ids is None and it["status"] != "done"):
            continue
        for f in re.split(r"[,\s]+", it.get("ledger diff") or ""):
            if f and f.lower() != "none":
                out.add(f)
    return out


def add(text: str, items: list[dict], typ: str, title: str, acceptance: str, ledger_diff: str,
        evidence: str) -> tuple[str, str]:
    """Append a proposed item and its evidence section. Returns (new text, new id)."""
    if typ not in TYPES:
        raise ValueError(f"type must be one of {TYPES}")
    if not evidence.strip():
        raise ValueError("evidence is required: an item is filed only if it reproduces")
    n = max([int(i["id"][1:]) for i in items] + [0]) + 1
    qid = f"Q{n:03d}"
    items.append({"id": qid, "type": typ, "status": "proposed", "title": title, "acceptance test": acceptance,
                  "branch/PR": "", "opposition": "", "ledger diff": ledger_diff or "none"})
    text = write(text, items).rstrip("\n") + f"\n\n### {qid}\n\n{evidence.strip()}\n"
    return text, qid


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "approved", "auto-approve", "set", "validate", "add"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--type")
    ap.add_argument("--title")
    ap.add_argument("--acceptance")
    ap.add_argument("--ledger-diff", default="none")
    ap.add_argument("--evidence-file")
    ap.add_argument("--queue", default=str(QUEUE))
    a = ap.parse_args(argv)
    path = Path(a.queue)
    text = path.read_text(encoding="utf-8")
    items = parse(text)
    if a.cmd == "list":
        for it in items:
            print(f"{it['id']} [{it['type']}/{it['status']}] {it['title']}")
        return 0
    if a.cmd == "approved":
        for it in approved(items):
            print(f"{it['id']} [{it['type']}] {it['title']}")
        return 0
    if a.cmd == "validate":
        errs = validate(items)
        print("\n".join(errs) or "queue ok")
        return 1 if errs else 0
    if a.cmd == "auto-approve":
        ch = auto_approve(items)
        path.write_text(write(text, items), encoding="utf-8")
        print("changed: " + (", ".join(ch) or "none"))
        return 0
    if a.cmd == "add":
        try:
            new, qid = add(text, items, a.type, a.title, a.acceptance, a.ledger_diff,
                           Path(a.evidence_file).read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"refused: {e}")
            return 1
        path.write_text(new, encoding="utf-8")
        print(qid)
        return 0
    if a.cmd == "set":
        qid, field, value = a.args[0], a.args[1], " ".join(a.args[2:])
        if field not in COLUMNS or field == "id":
            print(f"field must be one of {COLUMNS[1:]}")
            return 2
        hit = [it for it in items if it["id"] == qid]
        if not hit:
            print(f"no item {qid}")
            return 2
        hit[0][field] = value
        errs = validate(items)
        if errs:
            print("\n".join(errs))
            return 1
        path.write_text(write(text, items), encoding="utf-8")
        print(f"{qid}.{field} = {value}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
