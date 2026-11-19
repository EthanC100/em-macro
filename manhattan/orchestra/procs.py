"""Portable process and host facts: Linux reads /proc; macOS (the iMac, the default host) uses ``ps``, ``mount``,
``sysctl`` and ``ioreg``. Every function fails safe: an unknown answer never kills a process or approves a root.

    machine_id()            a stable machine identifier (not the hostname, which macOS changes with the network)
    boot_id()               changes at every boot: a process recorded under another boot cannot be alive
    group(pgid)             [(pid, rss_bytes, cmdline)] of the processes in a process group
    fs_type(path)           the file-system type of the mount holding ``path`` (None if unknown)
"""
from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

PROC = Path("/proc")


def _cmd(*args: str, timeout: float = 10.0) -> str | None:
    try:
        p = subprocess.run(list(args), capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def machine_id() -> str:
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            v = Path(p).read_text().strip()
            if v:
                return v
        except OSError:
            pass
    out = _cmd("ioreg", "-rd1", "-c", "IOPlatformExpertDevice")
    if out:
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                return line.split("=", 1)[1].strip().strip('"')
    return "host:" + socket.gethostname()


def boot_id() -> str:
    try:
        return (PROC / "sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        pass
    out = _cmd("sysctl", "-n", "kern.boottime")
    return ("boottime:" + out.strip()) if out else "unknown"


def group(pgid: int, *, use_proc: bool | None = None) -> list[tuple[int, int, str]]:
    use_proc = PROC.is_dir() and (PROC / "self" / "stat").exists() if use_proc is None else use_proc
    out = []
    if use_proc:
        page = os.sysconf("SC_PAGE_SIZE")
        try:
            entries = os.listdir(PROC)
        except OSError:
            return out
        for e in entries:
            if not e.isdigit():
                continue
            try:
                s = (PROC / e / "stat").read_text()
                rest = s[s.rfind(")") + 2:].split()
                if int(rest[2]) != pgid:                       # field 5: pgrp
                    continue
                cmd = (PROC / e / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
                out.append((int(e), int(rest[21]) * page, cmd))  # field 24: rss in pages
            except (OSError, IndexError, ValueError):
                continue
        return out
    txt = _cmd("ps", "-A", "-o", "pid=,pgid=,rss=,command=")
    if txt is None:
        return out
    for line in txt.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            pid, pg, rss_kb = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if pg == pgid:
            out.append((pid, rss_kb * 1024, parts[3]))
    return out


def fs_type(path: Path) -> str | None:
    p = str(Path(path))
    best, typ = "", None
    try:
        lines = [(l.split()[1].replace("\\040", " "), l.split()[2]) for l in (PROC / "mounts").read_text().splitlines()
                 if len(l.split()) >= 3]
    except OSError:
        txt = _cmd("mount")                                     # macOS: "dev on /path (type, options)"
        if txt is None:
            return None
        lines = []
        for l in txt.splitlines():
            if " on " in l and "(" in l:
                mnt = l.split(" on ", 1)[1].rsplit(" (", 1)
                lines.append((mnt[0], mnt[1].split(",", 1)[0].strip(")")))
    for mnt, t in lines:
        if (p == mnt or p.startswith(mnt.rstrip("/") + "/")) and len(mnt) >= len(best):
            best, typ = mnt, t
    return typ
