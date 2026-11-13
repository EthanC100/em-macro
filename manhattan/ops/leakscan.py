"""Search public output channels for performance values (criterion O-05).

Given the floats a run recorded privately (returns, summaries, wealth: anything that is performance) and the
channels a run could have written to in public, report every place where one of those values appears.

**Matching.** A value can be printed in many ways (``repr``, ``%.6f``, ``%.4g``, as a percentage, in basis
points). Instead of listing renderings, every decimal token in the scanned text is parsed and compared with every
value at three scales (1, 100, 10,000): the token matches when it equals the value rounded or truncated to the
token's own precision. Tokens with fewer than ``min_sig`` significant digits are ignored, because short numbers
("0.5", "1.25") occur everywhere and identify nothing. Integers are ignored (the public health record holds counts).

**Channels.** ``scan_tree`` (files of a directory), ``scan_git`` (every object reachable from any ref, the reflog
and stashes included: commits, trees and blobs, so deleted files and old versions are searched too), and
``scan_text`` for captured logs, step summaries and issue bodies.
"""
from __future__ import annotations

import math
import re
import subprocess
from bisect import bisect_left
from pathlib import Path

SCALES = (1.0, 100.0, 10_000.0)
_TOKEN = re.compile(r"(?<![0-9A-Za-z_.])[-+]?(?:\d+\.\d*|\.\d+|\d+(?=[eE]))(?:[eE][-+]?\d+)?(?![0-9A-Za-z_])")


def _sig_and_ulp(tok: str) -> tuple[int, float]:
    t = tok.lstrip("+-")
    mant, _, exp = t.lower().partition("e")
    e = int(exp) if exp else 0
    intpart, _, frac = mant.partition(".")
    digits = (intpart + frac).lstrip("0")
    return len(digits), 10.0 ** (e - len(frac))


class Needles:
    """The values to look for, sorted for fast range queries."""

    def __init__(self, values, min_sig: int = 5):
        vals = set()
        for v in values:
            try:
                x = abs(float(v))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(x) or x == 0.0:
                continue
            for s in SCALES:
                vals.add(x * s)
        self.values = sorted(vals)
        self.min_sig = min_sig

    def __len__(self):
        return len(self.values)

    def match(self, tok: str) -> float | None:
        sig, ulp = _sig_and_ulp(tok)
        if sig < self.min_sig:
            return None
        try:
            t = abs(float(tok))
        except ValueError:
            return None
        lo = t - ulp * 1.0000001                      # rounded (half an ulp) or truncated (up to one ulp)
        i = bisect_left(self.values, lo)
        if i < len(self.values) and self.values[i] <= t + ulp * 1.0000001:
            return self.values[i]
        return None


def scan_text(text: str, needles: Needles, where: str) -> list[dict]:
    found = []
    for m in _TOKEN.finditer(text):
        hit = needles.match(m.group(0))
        if hit is not None:
            a, b = max(0, m.start() - 40), min(len(text), m.end() + 40)
            found.append({"channel": where, "token": m.group(0), "context": text[a:b].replace("\n", " ")})
    return found


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def scan_tree(root: Path, needles: Needles, where: str, exclude: tuple[Path, ...] = ()) -> list[dict]:
    root = Path(root)
    out = []
    ex = tuple(Path(p).resolve() for p in exclude)
    for p in sorted(root.rglob("*")):
        rp = p.resolve()
        if any(rp == e or e in rp.parents for e in ex):
            continue
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            out += scan_text(_decode(p.read_bytes()), needles, f"{where}:{p.relative_to(root)}")
    return out


def scan_git(repo: Path, needles: Needles, where: str) -> list[dict]:
    """Every object reachable from any ref or reflog entry, decompressed by git itself."""
    repo = Path(repo)
    objs = subprocess.run(["git", "rev-list", "--objects", "--all", "--reflog"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.split()
    shas = sorted({o for o in objs if re.fullmatch(r"[0-9a-f]{40}", o)})
    out = []
    if not shas:
        return out
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=repo, input="\n".join(shas).encode() + b"\n",
                       capture_output=True, check=True).stdout
    pos = 0
    while pos < len(p):
        nl = p.index(b"\n", pos)
        sha, kind, size = p[pos:nl].decode().split()
        size = int(size)
        body = p[nl + 1: nl + 1 + size]
        pos = nl + 1 + size + 1
        if kind == "tree":
            continue                      # a tree holds names and hashes; its names are in the commits' diffs anyway
        out += scan_text(_decode(body), needles, f"{where}:{kind}:{sha[:12]}")
    return out


def scan_channels(channels: dict, needles: Needles) -> list[dict]:
    """``channels`` maps a name to ``("text", str)``, ``("tree", path)``, ``("tree_excluding", (path, excludes))``
    or ``("git", path)``."""
    found = []
    for name, (kind, obj) in channels.items():
        if kind == "text":
            found += scan_text(obj or "", needles, name)
        elif kind == "tree":
            found += scan_tree(obj, needles, name)
        elif kind == "tree_excluding":
            found += scan_tree(obj[0], needles, name, exclude=tuple(obj[1]))
        elif kind == "git":
            found += scan_git(obj, needles, name)
        else:
            raise ValueError(f"unknown channel kind {kind}")
    return found


def performance_values(records: list[dict]) -> list[float]:
    """Every float inside private records' payloads: everything a run measured is treated as performance."""
    out: list[float] = []

    def walk(x):
        if isinstance(x, float):
            out.append(x)
        elif isinstance(x, str):
            try:
                if re.fullmatch(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", x):
                    out.append(float(x))          # canonical JSON stores non-integers as decimal strings
            except ValueError:
                pass
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    for r in records:
        walk(r.get("payload", r))
    return out
