#!/usr/bin/env python3
"""Manhattan generator isolation test kit (criteria O-11, O-12). Standard library only: copy this one file into a
candidate blind-generator environment and run it there, from inside the generator's repository:

    python3 isolation_kit.py --declared-tools tools.txt          # tools.txt: the session's tool names, one per line
    python3 isolation_kit.py --json report.json ...

It checks every channel through which a generator could learn Manhattan's results or anything outside its brief,
and prints one line per channel, then a verdict:

    PASS        every forbidden channel is closed                                      (exit 0)
    FAIL        at least one channel is open                                           (exit 1)
    INCOMPLETE  nothing is open, but a channel needs the operator's declaration        (exit 2)

It never prints a secret: environment variables and credential files are reported by name only.

What isolation cannot do: it cannot remove what the model learned in pretraining. A PASS means the generator is
blind to Manhattan's results and repositories, not to market history it has read (docs/manhattan/ops/BLIND_GENERATOR.md).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PASS, FAIL, INCOMPLETE = "PASS", "FAIL", "INCOMPLETE"
OWNER = "EthanC100"
FORBIDDEN_REPOS = ("em-macro", "em-macro-data", "manhattan-ledger")
NET_TARGETS = (("github.com", 443), ("api.github.com", 443), ("raw.githubusercontent.com", 443), ("pypi.org", 443),
               ("fred.stlouisfed.org", 443), ("api.anthropic.com", 443), ("www.google.com", 443), ("1.1.1.1", 53),
               ("8.8.8.8", 53))
SECRET_ENV = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|API_?KEY|PRIVATE_?KEY|^GH_|^GITHUB_|ANTHROPIC|"
                        r"OPENAI|^AWS_|^GOOGLE_|^AZURE_|DATA_REPO|NETRC|SSH_AUTH_SOCK|PROXY)", re.I)
CREDENTIAL_FILES = (".git-credentials", ".netrc", ".config/gh/hosts.yml", ".docker/config.json", ".aws/credentials",
                    ".config/gcloud", ".npmrc", ".pypirc")
SENSITIVE_NAME = re.compile(r"(em[-_]macro|manhattan|ledger|janus|norgate|databento|EthanC100)", re.I)
DEFAULT_ALLOWED_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep")
DEFAULT_REPO_FILES = ("README.md", "PROMPT*.md", "prompt*.md", "schema.json", "isolation_kit.py", ".gitignore",
                      "out/*", "tools.txt")
HOME_OK = (".bashrc", ".profile", ".bash_logout", ".zshrc", ".cache", ".config", ".local", ".gitconfig")
CACHE_DIRS = (".cache/pip", ".npm", ".cargo/registry", ".cache/uv", ".cache/huggingface", ".m2", ".gradle")
HISTORY_FILES = (".bash_history", ".zsh_history", ".python_history", ".node_repl_history", ".lesshst", ".viminfo",
                 ".psql_history", ".sqlite_history")
OUTSIDE_ROOTS = ("/workspace", "/workspaces", "/mnt", "/data", "/srv", "/opt", "/home", "/root", "/Users", "/media",
                 "/var/lib/docker/volumes")


def _tcp(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _git_reachable(url: str, timeout: float) -> bool:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=10"}
    try:
        r = subprocess.run(["git", "ls-remote", "--heads", url], capture_output=True, timeout=timeout, env=env)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@dataclass
class Ctx:
    repo: Path
    home: Path
    env: dict
    outside_roots: tuple = OUTSIDE_ROOTS
    tmp_dirs: tuple = ("/tmp", "/var/tmp")
    declared_tools: list | None = None
    allowed_tools: tuple = DEFAULT_ALLOWED_TOOLS
    allowed_repo_files: tuple = DEFAULT_REPO_FILES
    allowed_remote: str | None = None              # substring the repository's remotes may contain
    net_probe: object = None
    git_probe: object = None
    resolve: object = None
    which: object = None
    timeout: float = 4.0
    max_depth: int = 4
    ignore: tuple = field(default_factory=tuple)   # paths the kit itself created (its own report)

    def __post_init__(self):
        self.repo, self.home = Path(self.repo).resolve(), Path(self.home)
        self.net_probe = self.net_probe or (lambda h, p: _tcp(h, p, self.timeout))
        self.git_probe = self.git_probe or (lambda url: _git_reachable(url, 25.0))
        self.resolve = self.resolve or (lambda h: bool(socket.getaddrinfo(h, 443)))
        self.which = self.which or shutil.which


def _result(channel: str, findings: list, incomplete: list | None = None) -> dict:
    status = FAIL if findings else (INCOMPLETE if incomplete else PASS)
    return {"channel": channel, "status": status, "findings": findings, "needs_declaration": incomplete or []}


def _readable_entries(d: Path, limit: int = 50) -> list[str]:
    try:
        return sorted(p.name for p in d.iterdir())[:limit]
    except OSError:
        return []


def _walk(root: Path, depth: int):
    """(path, is_dir) under root to ``depth`` levels, skipping what cannot be read and not following links."""
    stack = [(root, 0)]
    while stack:
        d, k = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            p = Path(e.path)
            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError:
                continue
            yield p, is_dir
            if is_dir and k + 1 < depth:
                stack.append((p, k + 1))


def _inside(p: Path, root: Path) -> bool:
    try:
        p.resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------- the eight channels

def check_network(c: Ctx) -> dict:
    f = []
    for host, port in NET_TARGETS:
        if c.net_probe(host, port):
            f.append(f"tcp {host}:{port} connects")
    for host in ("github.com", "pypi.org"):
        try:
            if c.resolve(host):
                f.append(f"DNS resolves {host}")
        except OSError:
            pass
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        v = c.env.get(name)
        if v:
            m = re.match(r"^\w+://(?:[^@/]*@)?([^:/]+)(?::(\d+))?", v)
            if m and c.net_probe(m.group(1), int(m.group(2) or 80)):
                f.append(f"proxy in {name} is reachable")
    return _result("network", f)


def check_clone_access(c: Ctx) -> dict:
    f = []
    for repo in FORBIDDEN_REPOS:
        for url in (f"https://github.com/{OWNER}/{repo}", f"https://github.com/{OWNER}/{repo}.git",
                    f"git@github.com:{OWNER}/{repo}.git"):
            if c.git_probe(url):
                f.append(f"git ls-remote succeeds for {url}")
                break
    return _result("clone_access", f)


def check_files_outside(c: Ctx) -> dict:
    f = []
    extra = [n for n in _readable_entries(c.home, 500) if n not in HOME_OK and not n.startswith(".claude")]
    if extra:
        f.append(f"home directory holds {len(extra)} other entr(ies): {', '.join(extra[:10])}")
    for root in map(Path, c.outside_roots):
        if not root.exists() or _inside(root, c.repo):
            continue
        for p, is_dir in _walk(root, c.max_depth):
            if _inside(p, c.repo) or any(_inside(p, Path(i)) for i in c.ignore):
                continue
            if is_dir and p.name == ".git":
                f.append(f"another git repository is readable: {p.parent}")
            elif SENSITIVE_NAME.search(p.name):
                f.append(f"readable path with a sensitive name: {p}")
            if len(f) > 40:
                break
    try:
        mounts = Path("/proc/mounts").read_text().splitlines()
    except OSError:
        mounts = []
    for line in mounts:
        parts = line.split()
        if len(parts) > 2 and SENSITIVE_NAME.search(parts[1]):
            f.append(f"mount with a sensitive name: {parts[1]}")
    return _result("files_outside_repo", f)


def _repo_files(repo: Path) -> list[str]:
    out = []
    for p, is_dir in _walk(repo, 12):
        rel = p.relative_to(repo).as_posix()
        if rel == ".git" or rel.startswith(".git/") or is_dir:
            continue
        out.append(rel)
    return out


def check_leftovers(c: Ctx) -> dict:
    f = []
    for rel in _repo_files(c.repo):
        if not any(fnmatch.fnmatch(rel, pat) for pat in c.allowed_repo_files):
            f.append(f"repository holds an unexpected file: {rel}")
    for name in ("__pycache__", ".pytest_cache", ".ipynb_checkpoints", "results", "data"):
        if any(p.name == name for p, d in _walk(c.repo, 6) if d and ".git" not in p.parts):
            f.append(f"repository holds a {name} directory")
    for rel in (".local/share", ".cache"):
        d = c.home / rel
        names = [n for n in _readable_entries(d) if not any(rel + "/" + n == x for x in CACHE_DIRS)]
        if names and rel == ".local/share":
            f.append(f"~/{rel} holds: {', '.join(names[:10])}")
    return _result("leftover_artifacts", f[:60])


def check_credentials(c: Ctx) -> dict:
    f = [f"environment variable {k} is set" for k in sorted(c.env) if SECRET_ENV.search(k) and c.env.get(k)]
    for rel in CREDENTIAL_FILES:
        if (c.home / rel).exists():
            f.append(f"credential file ~/{rel} exists")
    ssh = c.home / ".ssh"
    for n in _readable_entries(ssh):
        if n.startswith("id_") or n.endswith(".pem") or n == "config":
            f.append(f"~/.ssh/{n} exists")
    git_env = {**c.env, "HOME": str(c.home)}                 # exactly the environment under test (main: os.environ)
    try:
        r = subprocess.run(["git", "config", "--show-origin", "--get-regexp",
                            r"credential\..*|http\..*extraheader|url\..*\.insteadof"],
                           cwd=c.repo, capture_output=True, text=True, env=git_env, timeout=10)
        for line in r.stdout.splitlines():
            origin, _, rest = line.partition("\t")
            key = rest.split()[0] if rest.split() else "?"
            f.append(f"git config sets {key} ({origin.split(':')[0]})")
    except (OSError, subprocess.TimeoutExpired):
        pass
    gh = c.which("gh")
    if gh:
        try:
            r = subprocess.run([gh, "auth", "status"], capture_output=True, env={**c.env, "HOME": str(c.home)},
                               timeout=15)
            if r.returncode == 0:
                f.append("gh is logged in")
        except (OSError, subprocess.TimeoutExpired):
            pass
    return _result("credentials", f)


def check_tools(c: Ctx) -> dict:
    f = []
    for p in (c.home / ".claude.json", c.repo / ".mcp.json", c.home / ".claude/settings.json",
              c.home / ".claude/settings.local.json", c.repo / ".claude/settings.json"):
        try:
            obj = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        servers = obj.get("mcpServers") or {}
        for proj in (obj.get("projects") or {}).values():
            if isinstance(proj, dict):
                servers = {**servers, **(proj.get("mcpServers") or {})}
        if servers:
            f.append(f"MCP servers configured in {p.name}: {', '.join(sorted(servers))}")
        if obj.get("enabledPlugins"):
            f.append(f"plugins enabled in {p.name}")
    incomplete = []
    if c.declared_tools is None:
        incomplete.append("declare the session's tool list with --declared-tools (one name per line)")
    else:
        bad = [t for t in c.declared_tools if t and t not in c.allowed_tools]
        if bad:
            f.append(f"tools beyond the allowed set: {', '.join(sorted(bad))}")
    return _result("tools_and_mcp", f, incomplete)


def check_inherited_context(c: Ctx) -> dict:
    f = []
    d = c.repo
    while True:
        for n in ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", ".claude"):
            if (d / n).exists():
                f.append(f"{d / n} exists")
        if d.parent == d:
            break
        d = d.parent
    claude = c.home / ".claude"
    for rel in ("CLAUDE.md", "agents", "skills", "commands", "plugins", "memory", "todos"):
        p = claude / rel
        if p.is_file() or (p.is_dir() and _readable_entries(p)):
            f.append(f"~/.claude/{rel} is present")
    projects = claude / "projects"
    transcripts = [p for p, d_ in _walk(projects, 3) if not d_ and p.suffix == ".jsonl"] if projects.exists() else []
    if transcripts:
        f.append(f"{len(transcripts)} past-conversation transcript(s) under ~/.claude/projects")
    mem = [p for p, d_ in _walk(projects, 3) if d_ and p.name == "memory"] if projects.exists() else []
    if mem:
        f.append(f"{len(mem)} memory director(ies) under ~/.claude/projects")
    return _result("inherited_context", f)


def check_indirect(c: Ctx) -> dict:
    f = []
    for rel in HISTORY_FILES:
        p = c.home / rel
        if p.exists() and p.stat().st_size > 0:
            f.append(f"shell or tool history ~/{rel} is not empty")
    for t in map(Path, c.tmp_dirs):
        names = [n for n in _readable_entries(t, 500) if not any(_inside(t / n, Path(i)) for i in c.ignore)]
        if names:
            f.append(f"temporary directory {t} holds {len(names)} entr(ies)")
    for rel in CACHE_DIRS:
        root = c.home / rel
        for p, is_dir in _walk(root, 6):
            if SENSITIVE_NAME.search(p.name):
                f.append(f"package cache ~/{rel} holds {p.name}")
                break
    try:
        rem = subprocess.run(["git", "remote", "-v"], cwd=c.repo, capture_output=True, text=True, timeout=10).stdout
        for line in rem.splitlines():
            url = line.split()[1] if len(line.split()) > 1 else ""
            if c.allowed_remote is None or c.allowed_remote not in url:
                f.append(f"repository remote {line.split()[0]} points elsewhere than the generator repository")
        branches = subprocess.run(["git", "for-each-ref", "--format=%(refname)"], cwd=c.repo, capture_output=True,
                                  text=True, timeout=10).stdout.split()
        if len([b for b in branches if b.startswith("refs/heads/")]) > 1:
            f.append("repository has more than one branch")
        if any(b.startswith("refs/stash") for b in branches):
            f.append("repository has a stash")
        hist = subprocess.run(["git", "log", "--all", "--name-only", "--format="], cwd=c.repo, capture_output=True,
                              text=True, timeout=30).stdout.split()
        odd = sorted({h for h in hist if not any(fnmatch.fnmatch(h, pat) for pat in c.allowed_repo_files)})
        if odd:
            f.append(f"repository history holds {len(odd)} unexpected file(s): {', '.join(odd[:5])}")
    except (OSError, subprocess.TimeoutExpired):
        f.append("the repository's git state could not be read")
    return _result("indirect_channels", f)


CHECKS = (check_network, check_clone_access, check_files_outside, check_leftovers, check_credentials, check_tools,
          check_inherited_context, check_indirect)


def run(c: Ctx) -> dict:
    results = [chk(c) for chk in CHECKS]
    if any(r["status"] == FAIL for r in results):
        verdict = FAIL
    elif any(r["status"] == INCOMPLETE for r in results):
        verdict = INCOMPLETE
    else:
        verdict = PASS
    return {"verdict": verdict, "channels": results}


def report(res: dict) -> str:
    lines = ["Manhattan generator isolation kit", ""]
    for r in res["channels"]:
        lines.append(f"[{r['status']:>10}] {r['channel']}")
        for x in r["findings"] + r["needs_declaration"]:
            lines.append(f"             - {x}")
    lines += ["", "Pretraining knowledge cannot be removed by isolation: a PASS means blind to Manhattan's results,",
              "not to market history the model has read.", "", res["verdict"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--home", default=str(Path.home()))
    ap.add_argument("--declared-tools")
    ap.add_argument("--allowed-tools", default=",".join(DEFAULT_ALLOWED_TOOLS))
    ap.add_argument("--allowed-remote", help="substring of the generator repository's own remote URL")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    tools = None
    if a.declared_tools:
        tools = [t.strip() for t in Path(a.declared_tools).read_text().splitlines() if t.strip()]
    c = Ctx(repo=Path(a.repo), home=Path(a.home), env=dict(os.environ), declared_tools=tools,
            allowed_tools=tuple(t for t in a.allowed_tools.split(",") if t), allowed_remote=a.allowed_remote,
            ignore=(a.json,) if a.json else ())
    res = run(c)
    print(report(res))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))
    return {PASS: 0, FAIL: 1, INCOMPLETE: 2}[res["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
