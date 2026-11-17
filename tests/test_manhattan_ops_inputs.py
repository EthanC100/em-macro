"""Metadata is untrusted; all fixtures are synthetic and reads stay bounded."""
import json
import os
import subprocess
import sys

import pytest

from manhattan.ops.inputs import read_json


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', '[Infinity]', '[1e9999]',
                               '[' * 65 + '0' + ']' * 65, '[' * 1100 + '0' + ']' * 1100])
def test_ambiguous_nonfinite_and_deep_json_refused(tmp_path, raw):
    path = tmp_path / "input.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        read_json(path)


def test_real_read_bound_even_when_stat_understates_size(tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    path.write_bytes(b'"' + b'x' * 100 + b'"')
    original = os.fstat

    def small(fd):
        values = list(original(fd))
        values[6] = 0
        return os.stat_result(values)

    monkeypatch.setattr(os, "fstat", small)
    with pytest.raises(ValueError):
        read_json(path, max_bytes=50)


def test_exact_byte_bound_and_unicode(tmp_path):
    path = tmp_path / "input.json"
    raw = '{"text":"é"}'.encode()
    path.write_bytes(raw)
    assert read_json(path, max_bytes=len(raw)) == {"text": "é"}
    with pytest.raises(ValueError):
        read_json(path, max_bytes=len(raw) - 1)


@pytest.mark.parametrize("command", ["monitor", "readiness", "artifacts"])
@pytest.mark.parametrize("kind", ["fifo", "symlink", "duplicate", "deep"])
def test_cli_invalid_input_stays_bounded_and_does_not_leak(tmp_path, command, kind):
    path = tmp_path / "private_canary_0.918273645.json"
    if kind == "fifo":
        os.mkfifo(path)
    elif kind == "symlink":
        target = tmp_path / "target"
        target.write_text('{"private_canary_0.918273645":1}')
        path.symlink_to(target)
    elif kind == "duplicate":
        path.write_text('{"private_canary_0.918273645":1,"private_canary_0.918273645":2}')
    else:
        path.write_text('[' * 1100 + '0' + ']' * 1100)
    args = {"monitor": ["integrity", "--approved", str(path)],
            "readiness": [str(path)], "artifacts": ["--root", str(tmp_path), "--manifest", str(path)]}
    result = subprocess.run([sys.executable, "-m", f"manhattan.ops.{command}", *args[command]],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 2 and not result.stderr
    assert json.loads(result.stdout)["status"] in ("invalid_input", "invalid_inventory")
    assert "private_canary" not in result.stdout
