"""First Light: the data-access cap for Manhattan's first end-to-end exploration experiment (S17 remediation plan).

Dormant. Nothing in ``manhattan/`` outside this package imports it, it reads no real data, and it enables nothing.
See ``cap.py`` and docs/manhattan/audit/S17_NEXT_PRS.md (PR-3). ``harness.py`` (with ``synthetic.py``,
``anchor_stub.py`` and ``report.py``) is the end-to-end SYNTHETIC reproducibility harness: it reads
``config/manhattan.yaml`` only to refuse to run while a protected switch is on, and writes only under its
``--out`` directory.
"""
