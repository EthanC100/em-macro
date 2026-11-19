"""Atomic, hash-verified files.

``write_arrays`` serialises a mapping of numpy arrays to a deterministic byte container, writes them to a temporary file in the same
directory, fsyncs, and renames into place (``os.replace`` is atomic on POSIX). It returns the SHA-256 of the bytes;
the caller records that hash in the attempt log *after* the rename, so a file without a log record is an orphan
(never read as a result) and a log record always names a complete file.

``read_arrays`` refuses a file whose bytes do not match the recorded hash (``CorruptFile``).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .ids import sha256_bytes


class CorruptFile(RuntimeError):
    """A file's bytes do not match the hash recorded for it."""


def atomic_write_bytes(path: Path, data: bytes) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    return sha256_bytes(data)


MAGIC = b"HTEARR1\n"


def arrays_to_bytes(arrays: dict) -> bytes:
    """A deterministic container (``.npz`` embeds zip timestamps, so equal arrays would give unequal bytes):
    magic, an 8-byte header length, a canonical JSON header ``[[name, dtype, shape], ...]`` (names sorted), then
    each array's C-order bytes. Equal arrays give equal bytes, hence equal hashes."""
    names = sorted(arrays)
    parts, header = [], []
    for k in names:
        a = np.ascontiguousarray(arrays[k])
        if a.dtype.hasobject:
            raise TypeError(f"{k}: object arrays are not stored")
        header.append([k, a.dtype.str, list(a.shape)])
        parts.append(a.tobytes())
    h = json.dumps(header, separators=(",", ":")).encode()
    return MAGIC + len(h).to_bytes(8, "little") + h + b"".join(parts)


def bytes_to_arrays(data: bytes) -> dict:
    if not data.startswith(MAGIC):
        raise CorruptFile("not an HTE array file")
    off = len(MAGIC)
    hl = int.from_bytes(data[off:off + 8], "little")
    off += 8
    header = json.loads(data[off:off + hl])
    off += hl
    out = {}
    for name, dt, shape in header:
        dtype = np.dtype(dt)
        n = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
        if off + n > len(data):
            raise CorruptFile("truncated HTE array file")
        out[name] = np.frombuffer(data, dtype=dtype, count=n // dtype.itemsize if dtype.itemsize else 0,
                                  offset=off).reshape(shape).copy()
        off += n
    if off != len(data):
        raise CorruptFile("trailing bytes in HTE array file")
    return out


def write_arrays(path: Path, arrays: dict) -> str:
    return atomic_write_bytes(path, arrays_to_bytes(arrays))


def read_verified(path: Path, sha256: str) -> bytes:
    data = Path(path).read_bytes()
    if sha256_bytes(data) != sha256:
        raise CorruptFile(f"{path}: SHA-256 does not match the recorded hash")
    return data


def read_arrays(path: Path, sha256: str) -> dict:
    return bytes_to_arrays(read_verified(path, sha256))
