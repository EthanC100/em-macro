"""Standalone probe run by a fresh lock-only Python, without pytest.

All writes are inside a TemporaryDirectory and all data is synthetic. No batch
is registered, no hypothesis is generated, and no real source is contacted.
"""
from datetime import date, datetime, timedelta, timezone
import importlib.metadata
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # -I excludes ambient PYTHONPATH and user packages


class LockedRunnerProbe(unittest.TestCase):
    def test_lock_only_import_and_synthetic_local_run(self):
        expected = {}
        for line in (ROOT / "requirements-manhattan-runner.lock").read_text().splitlines():
            if line and not line.startswith("#"):
                name, version = line.split()[0].split("==")
                expected[name.lower().replace("_", "-")] = version
        installed = {d.metadata["Name"].lower().replace("_", "-"): d.version
                     for d in importlib.metadata.distributions()}
        installed.pop("pip", None)  # bootstrap tooling supplied by venv, never upgraded
        self.assertEqual(installed, expected)
        for name in ("pytest", "scipy", "pandas"):
            self.assertIsNone(importlib.util.find_spec(name), name)
        self.assertIsNotNone(importlib.util.find_spec("yaml"))       # hash-pinned in the lock (owner decision D-12)

        from manhattan import access as A
        from manhattan.ops import runner as R, data as D, store as ST

        # The authoritative configuration under the lock: safe_load, verified against the checked-out commit and an
        # explicit pin; a mismatched pin fails closed.
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True, timeout=30).stdout.strip()
        probe = R.RunConfig(ledger_dir=ROOT, remote="", batches_dir=ROOT, asof=date(2005, 1, 7), commit=head)
        fence, sha = R.run_fence(probe)
        self.assertEqual(len(sha), 64)
        probe.config_sha256 = sha
        self.assertEqual(R.run_fence(probe), (fence, sha))
        probe.config_sha256 = "f" * 64
        with self.assertRaises(A.AccessError):
            R.run_fence(probe)

        instant = datetime(2005, 1, 7, 23, 0, tzinfo=timezone.utc)

        def clock():
            nonlocal instant
            instant += timedelta(seconds=1)
            return instant

        with tempfile.TemporaryDirectory(prefix="manhattan-locked-probe-") as folder:
            root = Path(folder)
            remote, mirror = root / "remote.git", root / "mirror.git"
            for path in (remote, mirror):
                subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(path)],
                               check=True, timeout=30)
            before = None
            with patch("requests.get", side_effect=AssertionError("no HTTP in synthetic probe")), \
                    patch("socket.create_connection", side_effect=AssertionError("no network in synthetic probe")):
                for attempt in (1, 2):
                    cfg = R.RunConfig(ledger_dir=root / f"run{attempt}/private/ledger", remote=str(remote),
                                      batches_dir=root / "no-batches", asof=date(2005, 1, 7),
                                      private_dir=root / f"run{attempt}/private", sources=("synthetic",),
                                      run_id=f"probe-{attempt}", commit="a" * 40, run_calendar="synthetic",
                                      mirror=str(mirror))
                    health = R.nightly(cfg, {"synthetic": lambda: D.synthetic_csv(cfg.asof)}, clock=clock)
                    self.assertEqual(health["status"], "ok")
                    self.assertTrue(health["mirror_ok"])
                    self.assertEqual(health["predictions_registered"], 0)
                    self.assertEqual(health["observations_total"], 0)
                    self.assertEqual(health["promotion"], "no-adopted-protocol")
                    view = ST.Store(workdir=root / f"view{attempt}", remote=str(remote)).open()
                    self.assertEqual(ST.verify_chain(view.records), [])
                    stable = [r for r in view.records if r["type"] not in ("lock", "unlock")]
                    if before is None:
                        before = stable
                        self.assertEqual(health["captures_new"], 1)
                    else:
                        self.assertEqual(stable, before)
                        self.assertEqual(health["captures_new"], 0)


if __name__ == "__main__":
    unittest.main()
