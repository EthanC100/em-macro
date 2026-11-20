"""Portable process and host facts: Linux reads /proc; macOS (the iMac, the default host) uses ``ps``, ``mount``,
``sysctl`` and ``ioreg``. Every function fails safe: an unknown answer never kills a process or approves a root.

    machine_id()            a stable machine identifier (not the hostname, which macOS changes with the network);
                            None when it cannot be read: liveness never depends on it, and None never mismatches
    boot_id()               changes at every boot, and only then (macOS: kern.bootsessionuuid; the boot time's
                            seconds as a fallback, never its local-time text); None when unknown
    group(pgid)             [Proc(pid, rss_bytes, cmdline, start)] of a process group; raises ProcsUnavailable
                            when the process table cannot be read (never an empty "all clear")
    fs_type(path)           the file-system type of the mount holding ``path`` (None if unknown)

The macOS tools live in /usr/sbin and /sbin, which cron's and launchd's default PATH (/usr/bin:/bin) leaves out, so
they are called by absolute path (``TOOLS``) and only by bare name where none of those paths exists.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

PROC = Path("/proc")
TOOLS = {"ioreg": ("/usr/sbin/ioreg",), "sysctl": ("/usr/sbin/sysctl", "/sbin/sysctl"),
         "mount": ("/sbin/mount", "/bin/mount", "/usr/bin/mount"), "ps": ("/bin/ps", "/usr/bin/ps")}


def tool(name: str) -> str:
    for p in TOOLS.get(name, ()):
        if os.access(p, os.X_OK):
            return p
    return name


def _cmd(*args: str, timeout: float = 10.0) -> str | None:
    try:
        p = subprocess.run([tool(args[0]), *args[1:]], capture_output=True, timeout=timeout,
                           env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def machine_id() -> str | None:
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
            if "IOPlatformUUID" in line and "=" in line:
                v = line.split("=", 1)[1].strip().strip('"')
                if v:
                    return v
    return None


def boot_id() -> str | None:
    try:
        v = (PROC / "sys/kernel/random/boot_id").read_text().strip()
        if v:
            return v
    except OSError:
        pass
    out = _cmd("sysctl", "-n", "kern.bootsessionuuid")
    if out and out.strip():
        return "bootsession:" + out.strip()
    out = _cmd("sysctl", "-n", "kern.boottime")          # "{ sec = 1763500000, usec = 12345 } Thu Nov 19 ..."
    m = re.search(r"sec\s*=\s*(\d+)", out or "")
    return ("boottime:" + m.group(1)) if m else None


class Proc(NamedTuple):
    pid: int
    rss: int            # bytes
    cmd: str
    start: str          # process start time: with the pid, it names one process across pid reuse


class ProcsUnavailable(RuntimeError):
    """The process table could not be read (neither /proc nor ps): callers must fail closed, not read "empty"."""


def group(pgid: int, *, use_proc: bool | None = None) -> list[Proc]:
    """Every process whose process group is ``pgid``. Raises ``ProcsUnavailable`` if the table cannot be read."""
    use_proc = PROC.is_dir() and (PROC / "self" / "stat").exists() if use_proc is None else use_proc
    out = []
    if use_proc:
        page = os.sysconf("SC_PAGE_SIZE")
        try:
            entries = os.listdir(PROC)
        except OSError as e:
            raise ProcsUnavailable(f"/proc: {type(e).__name__}") from None
        for e in entries:
            if not e.isdigit():
                continue
            try:
                s = (PROC / e / "stat").read_text()
                rest = s[s.rfind(")") + 2:].split()
                if int(rest[2]) != pgid:                       # field 5: pgrp
                    continue
                cmd = (PROC / e / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
                # field 24: rss in pages; field 22: start time in clock ticks since boot
                out.append(Proc(int(e), int(rest[21]) * page, cmd.rstrip(), "jiffies:" + rest[19]))
            except (OSError, IndexError, ValueError):
                continue
        return out
    # macOS: rss in KiB; lstart is five tokens under LC_ALL=C ("Thu Nov 20 01:02:03 2026")
    txt = _cmd("ps", "-A", "-o", "pid=,pgid=,rss=,lstart=,command=")
    if txt is None:
        raise ProcsUnavailable("ps failed")
    for line in txt.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        try:
            pid, pg, rss_kb = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if pg == pgid:
            out.append(Proc(pid, rss_kb * 1024, parts[8].rstrip(), "lstart:" + " ".join(parts[3:8])))
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
