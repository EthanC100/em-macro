"""Manhattan ops: the generator isolation kit (O-11, O-12). Every probe is injected: no network is touched."""
import subprocess
from pathlib import Path

import pytest

from manhattan.ops import isolation_kit as K

ROOT = Path(__file__).resolve().parents[1]


def clean(tmp_path, **kw):
    repo = tmp_path / "manhattan-blind"
    repo.mkdir()
    for n in ("README.md", "PROMPT_v2.md", "isolation_kit.py"):
        (repo / n).write_text("x\n")
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    g("add", "-A")
    g("-c", "user.name=t", "-c", "user.email=t@e.invalid", "commit", "-qm", "template")
    for d in ("home", "outside", "tmpd"):
        (tmp_path / d).mkdir()

    def no_dns(h):
        raise OSError("no network")

    args = dict(repo=repo, home=tmp_path / "home", env={"GIT_CONFIG_NOSYSTEM": "1", "PATH": "/usr/bin:/bin"},
                outside_roots=(str(tmp_path / "outside"),), tmp_dirs=(str(tmp_path / "tmpd"),),
                declared_tools=["Read", "Write"], net_probe=lambda h, p: False, git_probe=lambda u: False,
                resolve=no_dns, which=lambda n: None)
    args.update(kw)
    return K.Ctx(**args)


def status(res):
    return {c["channel"]: c["status"] for c in res["channels"]}


def test_clean_sandbox_passes(tmp_path):
    res = K.run(clean(tmp_path))
    assert res["verdict"] == "PASS", K.report(res)
    assert len(res["channels"]) == 8 and K.report(res).splitlines()[-1] == "PASS"


def test_undeclared_tools_are_incomplete_not_pass(tmp_path):
    res = K.run(clean(tmp_path, declared_tools=None))
    assert res["verdict"] == "INCOMPLETE" and status(res)["tools_and_mcp"] == "INCOMPLETE"


def open_network(t):
    return {"net_probe": lambda h, p: h == "github.com"}


def open_clone(t):
    return {"git_probe": lambda u: "em-macro-data" in u}


def open_outside(t):
    (t / "outside/em-macro/.git").mkdir(parents=True)
    return {}


def open_leftover(t):
    (t / "manhattan-blind/data").mkdir()
    (t / "manhattan-blind/data/results.csv").write_text("x")
    return {}


def open_credentials(t):
    return {"env": {"GIT_CONFIG_NOSYSTEM": "1", "GITHUB_TOKEN": "secret-value-never-printed"}}


def open_tools(t):
    return {"declared_tools": ["Read", "WebFetch", "mcp__github__get_file_contents"]}


def open_context(t):
    p = t / "home/.claude/projects/-x"
    p.mkdir(parents=True)
    (p / "s.jsonl").write_text("{}")
    return {}


def open_indirect(t):
    (t / "home/.bash_history").write_text("git clone https://github.com/EthanC100/em-macro\n")
    return {}


@pytest.mark.parametrize("opener, channel", [
    (open_network, "network"), (open_clone, "clone_access"), (open_outside, "files_outside_repo"),
    (open_leftover, "leftover_artifacts"), (open_credentials, "credentials"), (open_tools, "tools_and_mcp"),
    (open_context, "inherited_context"), (open_indirect, "indirect_channels")])
def test_each_open_channel_fails(tmp_path, opener, channel):
    base = clean(tmp_path)
    kw = opener(tmp_path)
    c = K.Ctx(**{**{f: getattr(base, f) for f in ("repo", "home", "env", "outside_roots", "tmp_dirs", "declared_tools",
                                                    "net_probe", "git_probe", "resolve", "which")}, **kw})
    res = K.run(c)
    assert res["verdict"] == "FAIL" and status(res)[channel] == "FAIL", K.report(res)
    assert "secret-value-never-printed" not in K.report(res)


def test_claude_md_in_the_repository_and_temp_files_fail(tmp_path):
    c = clean(tmp_path)
    (c.repo / "CLAUDE.md").write_text("rules")
    (tmp_path / "tmpd/leftover.json").write_text("{}")
    s = status(K.run(c))
    assert s["inherited_context"] == "FAIL" and s["indirect_channels"] == "FAIL"


def test_a_remote_other_than_the_generator_repository_fails(tmp_path):
    c = clean(tmp_path)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/EthanC100/em-macro"], cwd=c.repo, check=True)
    assert status(K.run(c))["indirect_channels"] == "FAIL"
    c.allowed_remote = "manhattan-blind"
    subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/EthanC100/manhattan-blind"], cwd=c.repo,
                   check=True)
    assert status(K.run(c))["indirect_channels"] == "PASS"


def test_the_kit_uses_the_standard_library_only():
    src = (ROOT / "manhattan/ops/isolation_kit.py").read_text()
    imports = {l.split()[1].split(".")[0] for l in src.splitlines() if l.startswith(("import ", "from "))}
    assert imports <= {"__future__", "argparse", "fnmatch", "json", "os", "re", "shutil", "socket", "subprocess", "sys",
                       "dataclasses", "pathlib"}
