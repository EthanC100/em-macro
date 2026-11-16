"""Bounded metadata input for offline ops CLIs; never echo input in errors."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("non-finite JSON constant")


def read_bytes(path: str | Path, *, max_bytes: int = 2_000_000) -> bytes:
    """Read at most max_bytes+1 from a regular, non-symlink final component.

    Open nonblocking before fstat, so a FIFO cannot stall the caller. Inspect
    the opened descriptor instead of trusting a separate path-size check. The
    path is caller-authorized; this reader is not a filesystem sandbox.
    """
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("invalid byte bound")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise ValueError("safe metadata reads unsupported")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
            raise ValueError("invalid metadata file")
        chunks, remaining = [], max_bytes + 1
        while remaining:
            block = os.read(descriptor, min(65_536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        raw = b"".join(chunks)
    finally:
        os.close(descriptor)
    if len(raw) > max_bytes:
        raise ValueError("metadata byte bound exceeded")
    return raw


def read_json(path: str | Path, *, max_bytes: int = 2_000_000):
    raw = read_bytes(path, max_bytes=max_bytes)
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
    except RecursionError:
        raise ValueError("JSON nesting bound exceeded") from None
    stack = [(result, 0)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if depth > 64 or nodes > 100_000:
            raise ValueError("JSON structure bound exceeded")
        if isinstance(value, dict):
            stack.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            stack.extend((v, depth + 1) for v in value)
        elif isinstance(value, float) and not (-float("inf") < value < float("inf")):
            raise ValueError("non-finite JSON number")
    return result
