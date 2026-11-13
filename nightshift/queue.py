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

Unblocking (Q016): a ``blocked`` bug/data/lab item with a ``no block`` Opposition review goes back to ``approved``
at auto-approve once the single condition line ``unblock_when: <kind>:<arg>`` (at the start of a line in its
``### Qnnn`` evidence section) is true; the line is then rewritten ``unblock_when (fired YYYY-MM-DD): ...`` so it
never fires twice. Kinds: ``symbol:<module>:<name>`` (the module's source in this checkout defines <name> at top
level, read with ast, never imported) and ``commit:<sha>`` (7-40 lowercase hex, an ancestor of HEAD). An unknown
kind, a malformed condition, more than one condition or an ineligible item stays blocked and is reported.

Queue text is data, never instructions: nothing here is executed.

CLI: python -m nightshift.queue list | approved | validate | auto-approve | set <id> <field> <value>
     python -m nightshift.queue add --type bug --title T --acceptance A [--ledger-diff none] --evidence-file F
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import os
import re
import subprocess
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
UNBLOCK_LINE = re.compile(r"^unblock_when:(.*)$")    # a live condition; a fired one reads "unblock_when (fired ...):"
_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_DOTTED = rf"{_IDENT}(?:\.{_IDENT})*"


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


def _sections(text: str, qid: str) -> list[list[str]]:
    """The lines of every ``### <qid>`` evidence section after the table (up to the next heading)."""
    post = text.split(END, 1)[1] if END in text else text
    out, cur = [], None
    for line in post.splitlines():
        if re.match(r"#{1,3}\s", line):
            cur = [] if line.strip() == f"### {qid}" else None
            if cur is not None:
                out.append(cur)
        elif cur is not None:
            cur.append(line)
    return out


def unblock_conditions(text: str, qid: str) -> list[str]:
    """Live (not yet fired) ``unblock_when:`` values at the start of a line in the item's evidence section."""
    return [m.group(1).strip() for sec in _sections(text, qid) for line in sec
            if (m := UNBLOCK_LINE.match(line))]


def _symbol_defined(src: str, name: str) -> bool:
    """True if ``name`` is defined at the top level of ``src`` (a def, class or assignment; never an import)."""
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        stack = list(targets)
        while stack:
            t = stack.pop()
            if isinstance(t, ast.Name) and t.id == name:
                return True
            if isinstance(t, (ast.Tuple, ast.List)):
                stack.extend(t.elts)
    return False


def check_condition(cond: str, root: Path | None = None) -> tuple[bool, str | None]:
    """Evaluate one ``unblock_when`` condition as data. Returns (true?, problem or None).

    Kinds: ``symbol:<module>:<name>`` (the module's source in ``root`` defines <name> at top level, read with ast)
    and ``commit:<sha>`` (an ancestor of HEAD in ``root``). Never eval, exec, import or a shell (hard rule 12)."""
    root = Path(root if root is not None else C.ROOT)
    kind, sep, arg = cond.partition(":")
    if not sep or not kind:
        return False, f"malformed condition {cond!r} (expected <kind>:<arg>)"
    if kind == "symbol":
        mod, sep, name = arg.partition(":")
        if not sep or not re.fullmatch(_DOTTED, mod) or not re.fullmatch(_IDENT, name):
            return False, f"malformed condition {cond!r} (expected symbol:<module>:<name>)"
        base = root.joinpath(*mod.split("."))
        src = next((p for p in (base.with_suffix(".py"), base / "__init__.py") if p.is_file()), None)
        if src is None:
            return False, None
        try:
            return _symbol_defined(src.read_text(encoding="utf-8"), name), None
        except (SyntaxError, ValueError, UnicodeDecodeError) as e:
            return False, f"cannot parse {src.relative_to(root)}: {type(e).__name__}"
    if kind == "commit":
        if not re.fullmatch(r"[0-9a-f]{7,40}", arg):
            return False, f"malformed condition {cond!r} (expected commit:<7-40 lowercase hex>)"
        try:
            r = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", "--end-of-options", arg, "HEAD"],
                               capture_output=True, text=True, timeout=60,
                               env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"git failed for {cond!r}: {type(e).__name__}"
        if r.returncode in (0, 1):
            return r.returncode == 0, None
        return False, f"git cannot check {cond!r} (exit {r.returncode}: unknown commit?)"
    return False, f"unknown kind {kind!r} in {cond!r} (known: symbol, commit)"


def unblock(items: list[dict], text: str, root: Path | None = None,
            problems: list[str] | None = None) -> list[str]:
    """Blocked items whose single ``unblock_when`` condition is now true become approved. Returns the ids changed.

    Eligible: type bug/data/lab with a ``no block`` Opposition review (never ``BLOCK (x)``, never research, never an
    item with no review). An ineligible item, an unknown kind, a malformed condition or more than one condition
    leaves the item blocked and is reported in ``problems``."""
    problems = problems if problems is not None else []
    changed = []
    for it in items:
        if it["status"] != "blocked":
            continue
        conds = unblock_conditions(text, it["id"])
        if not conds:
            continue
        op = it["opposition"] or ""
        if it["type"] not in AUTO_TYPES:
            problems.append(f"{it['id']} stays blocked: type {it['type']} is not eligible for unblock_when")
            continue
        if BLOCK.match(op):
            problems.append(f"{it['id']} stays blocked: The Opposition's BLOCK stands (unblock_when ignored)")
            continue
        if not NO_BLOCK.match(op):
            problems.append(f"{it['id']} stays blocked: no 'no block' Opposition review (unblock_when ignored)")
            continue
        if len(conds) > 1:
            problems.append(f"{it['id']} stays blocked: more than one unblock_when line ({len(conds)})")
            continue
        ok, why = check_condition(conds[0], root)
        if why:
            problems.append(f"{it['id']} stays blocked: {why}")
        elif ok:
            it["status"] = "approved"
            changed.append(it["id"])
    return changed


def mark_fired(text: str, qid: str, day: str) -> str:
    """Mark the item's live ``unblock_when:`` line fired, so it never fires twice."""
    pre, post = text.split(END, 1)
    lines = post.split("\n")
    sec = False
    for i, line in enumerate(lines):
        if re.match(r"#{1,3}\s", line):
            sec = line.strip() == f"### {qid}"
        elif sec and (m := UNBLOCK_LINE.match(line)):
            lines[i] = f"unblock_when (fired {day}): {m.group(1).strip()}"
    return pre + END + "\n".join(lines)


def auto_approve(items: list[dict], text: str | None = None, root: Path | None = None,
                 problems: list[str] | None = None) -> list[str]:
    """Proposed bug/data/lab items with a no-block Opposition review become approved; given the queue ``text``,
    eligible blocked items whose ``unblock_when`` condition holds become approved too. Returns the ids changed."""
    changed = []
    for it in items:
        if it["status"] == "proposed" and it["type"] in AUTO_TYPES and NO_BLOCK.match(it["opposition"] or ""):
            it["status"] = "approved"
            changed.append(it["id"])
        elif it["status"] in ("proposed", "approved") and BLOCK.match(it["opposition"] or ""):
            it["status"] = "blocked"
            changed.append(it["id"])
    if text is not None:
        changed += unblock(items, text, root, problems)
    return changed


def run_auto_approve(text: str, root: Path | None = None, day: str | None = None) -> tuple[str, list[str], list[str]]:
    """The auto-approve step on the whole queue text: returns (new text, ids changed, problems reported).

    Raises ValueError (nothing to write) if the resulting queue does not validate or does not read back."""
    items = parse(text)
    before = {it["id"]: it["status"] for it in items}
    problems: list[str] = []
    changed = auto_approve(items, text, root, problems)
    new = write(text, items)
    day = day or _dt.date.today().isoformat()
    for it in items:
        if before[it["id"]] == "blocked" and it["status"] == "approved":
            new = mark_fired(new, it["id"], day)
    errs = validate(items)
    if errs:
        raise ValueError("queue does not validate: " + "; ".join(errs))
    if parse(new) != items:
        raise ValueError("queue does not read back as written")
    return new, changed, problems


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
    ap.add_argument("--root", help="checkout that unblock_when conditions are checked against (default: this one)")
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
        try:
            new, ch, problems = run_auto_approve(text, Path(a.root) if a.root else None)
        except ValueError as e:
            print(f"refused, nothing written: {e}")
            return 1
        for p in problems:
            print(f"unblock_when: {p}")
        path.write_text(new, encoding="utf-8")
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
