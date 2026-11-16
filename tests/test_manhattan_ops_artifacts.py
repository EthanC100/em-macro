import hashlib

import pytest

from manhattan.ops.artifacts import verify


def fixture(root):
    (root / "synthetic.bin").write_bytes(b"synthetic fixture")
    return {"schema_version": 1, "files": [{"path": "synthetic.bin", "bytes": 17,
            "sha256": hashlib.sha256(b"synthetic fixture").hexdigest()}]}


def test_original_and_backup_then_same_length_tampering(tmp_path):
    doc = fixture(tmp_path)
    assert verify(tmp_path, doc) == {"status": "ok", "verified": 1, "missing": 0, "mismatched": 0}
    (tmp_path / "synthetic.bin").write_bytes(b"SYNTHETIC fixture")
    assert verify(tmp_path, doc)["mismatched"] == 1
    (tmp_path / "synthetic.bin").unlink()
    assert verify(tmp_path, doc)["missing"] == 1


@pytest.mark.parametrize("path", ["../escape", "/absolute", "a/../b", "a//b", "./b", "a\\b", ""])
def test_path_traversal_and_noncanonical_paths_refused(tmp_path, path):
    doc = fixture(tmp_path)
    doc["files"][0]["path"] = path
    with pytest.raises(ValueError):
        verify(tmp_path, doc)


def test_symlinks_and_duplicate_entries_refused(tmp_path):
    doc = fixture(tmp_path)
    doc["files"].append(doc["files"][0].copy())
    with pytest.raises(ValueError):
        verify(tmp_path, doc)
    doc["files"].pop()
    (tmp_path / "link").symlink_to(tmp_path / "synthetic.bin")
    doc["files"][0]["path"] = "link"
    with pytest.raises(ValueError):
        verify(tmp_path, doc)


def test_oversized_manifest_rejected_before_reading(tmp_path):
    doc = fixture(tmp_path)
    doc["files"][0]["bytes"] = 1_000_000_001
    with pytest.raises(ValueError):
        verify(tmp_path, doc)


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_schema_version_has_an_exact_integer_type(tmp_path, version):
    doc = fixture(tmp_path)
    doc["schema_version"] = version
    with pytest.raises(ValueError):
        verify(tmp_path, doc)
