"""Errors of the dormant HTE execution bridge."""
from __future__ import annotations

from manhattan.execution_realism.errors import ExecutionRealismError


class BridgeError(ExecutionRealismError, ValueError):
    """An input the bridge cannot translate faithfully (shape, window, clock, cost mapping)."""


class BridgeDisabled(ExecutionRealismError, PermissionError):
    """The bridge is dormant: it runs on verified synthetic inputs only and is wired into nothing."""
