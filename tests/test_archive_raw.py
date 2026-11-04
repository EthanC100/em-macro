"""em_macro/archive_raw.py: deterministic archives, splitting, and the hash record."""
import tarfile

import pytest

from em_macro import archive_raw as A

DOC = """# x

| trial | asset | bytes | SHA-256 | contents | recorded | status |
|---|---|---|---|---|---|---|

after
"""


@pytest.fixture
def doc(tmp_path, monkeypatch):
    p = tmp_path / "raw_data_archive.md"
    p.write_text(DOC)
    monkeypatch.setattr(A, "DOC", p)
    return p


def _raw(tmp_path):
    src = tmp_path / "econ_test"
    (src / "sub").mkdir(parents=True)
    (src / "a.csv").write_text("x,y\n1,2\n")
    (src / "sub" / "b.json").write_text('{"v": 1}')
    return src


def test_archive_is_deterministic_and_restores_the_files(tmp_path):
    src = _raw(tmp_path)
    a1 = A.make_archive(src, tmp_path / "o1" / "a.tar.gz")
    (src / "a.csv").touch()                                     # new mtime, same content
    a2 = A.make_archive(src, tmp_path / "o2" / "a.tar.gz")
    assert a1.read_bytes() == a2.read_bytes()
    with tarfile.open(a1) as t:
        t.extractall(tmp_path / "x", filter="data")
    assert (tmp_path / "x" / "econ_test" / "sub" / "b.json").read_text() == '{"v": 1}'


def test_split_parts_join_back(tmp_path):
    f = tmp_path / "big.tar.gz"
    f.write_bytes(bytes(range(256)) * 40)                      # 10240 bytes
    parts = A.split(f, part_bytes=4096)
    assert [p.name for p in parts] == ["big.tar.gz.part001", "big.tar.gz.part002", "big.tar.gz.part003"]
    assert all(p.stat().st_size <= 4096 for p in parts) and not f.exists()
    assert b"".join(p.read_bytes() for p in parts) == bytes(range(256)) * 40
    g = tmp_path / "small.tar.gz"
    g.write_bytes(b"x")
    assert A.split(g, part_bytes=4096) == [g] and g.exists()


def test_pack_records_hashes_and_refuses_to_change_them(tmp_path, doc):
    assets = A.pack("T99", _raw(tmp_path), tmp_path / "out")
    rec = A.recorded()
    assert sorted(rec) == sorted(a.name for a in assets)
    for a in assets:
        assert rec[a.name]["sha256"] == A.sha256_file(a) and rec[a.name]["status"] == "pending upload"
    assert doc.read_text().rstrip().endswith("after")              # rows go into the table, not the end
    assert A.check(assets)
    tar = next(a for a in assets if a.name.endswith(".tar.gz"))
    tar.write_bytes(b"tampered")
    assert not A.check([tar])
    with pytest.raises(SystemExit, match="immutable"):
        A.record("T99", tar, "x")
    A.set_status(tar.name, "on release `raw-data-archive`")
    assert A.recorded()[tar.name]["status"] == "on release `raw-data-archive`"


def test_the_repository_record_parses():
    rec = A.recorded()
    t02 = rec["econ_momentum_raw_2026-11-04.tar.gz"]
    assert t02["sha256"] == "9be8876bba5596594a21e7ea7bd76b0dcb7a878018728c9b96a69e8081558f3c"
    assert t02["bytes"] == 16533509 and t02["bytes"] < A.GITHUB_ASSET_LIMIT
