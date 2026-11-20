"""Resource, concurrency, retry and budget limits.

The defaults below are the ceiling. A run root may hold ``limits.json`` to make them *tighter* (a smaller cap, a
longer back-off, a larger disk reserve); a value that would loosen a limit is refused, not clipped, so a mistyped or
agent-edited file can never raise a cap. Raising a ceiling is a reviewed code change to this file.

Budget. ``monthly_vcpu_hours`` caps *reserved* vCPU-hours (workers x wall-clock hours of every invocation, whatever
the utilisation: what a rented machine bills). Before an invocation starts, its worst case (workers x its wall-clock
limit) must fit in what is left of the calendar month (UTC); otherwise the job waits and the refusal is journaled.
``price_sgd_per_vcpu_hour`` converts usage into an estimated spend for the status report and for the
``monthly_budget_sgd`` check; it is 0 by default because the default host is hardware already owned (no spending).
Docs: docs/manhattan/orchestra/OPERATIONS.md section 7.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from .journal import full_hash

# fields where a larger value is looser (caps) and where a larger value is tighter (reserves, waits)
CAPS = ("max_running_jobs", "max_total_workers", "max_workers_per_job", "max_memory_mb_per_job",
        "max_wall_minutes_per_invocation", "max_invocations_per_job", "max_consecutive_errors",
        "monthly_vcpu_hours", "monthly_budget_sgd", "max_log_mb_per_invocation")
FLOORS = ("min_free_disk_mb", "backoff_base_s", "backoff_max_s", "price_sgd_per_vcpu_hour")
FLAGS_TIGHT_WHEN_TRUE = ("require_clean_tree",)
FIXED = ("launch_grace_s", "cancel_grace_s", "progress_interval_s")
# caps where 0 would mean "off" somewhere downstream: an override must keep them positive
POSITIVE = ("max_running_jobs", "max_total_workers", "max_workers_per_job", "max_memory_mb_per_job",
            "max_wall_minutes_per_invocation", "max_invocations_per_job", "max_consecutive_errors",
            "max_log_mb_per_invocation")


class LimitsError(ValueError):
    pass


def _finite(v) -> bool:
    try:
        return math.isfinite(v) and abs(v) < 1e15        # an integer too large for a float is not a limit either
    except OverflowError:
        return False


@dataclass(frozen=True)
class Limits:
    max_running_jobs: int = 2
    max_total_workers: int = 8                 # also capped at the machine's CPU count at run time
    max_workers_per_job: int = 8
    max_memory_mb_per_job: int = 12_000        # aggregate RSS of the invocation's process group
    max_wall_minutes_per_invocation: float = 360.0
    max_invocations_per_job: int = 50          # a job still unfinished after this many is ``incomplete``
    max_consecutive_errors: int = 3            # a job whose last k invocations errored is ``failed``
    monthly_vcpu_hours: float = 3000.0         # reserved vCPU-hours per calendar month (UTC)
    monthly_budget_sgd: float = 500.0          # estimated spend cap (usage x price)
    price_sgd_per_vcpu_hour: float = 0.0       # 0: owned hardware; set it (tighter only) for a rented machine
    max_log_mb_per_invocation: int = 200       # stdout/stderr of one invocation; larger is cut by the child
    min_free_disk_mb: int = 2048
    backoff_base_s: int = 60
    backoff_max_s: int = 3600
    require_clean_tree: bool = True            # the code paths of a job must match a commit exactly
    launch_grace_s: int = 120
    cancel_grace_s: int = 120
    progress_interval_s: int = 15

    def as_dict(self) -> dict:
        return asdict(self)

    def hash(self) -> str:
        return full_hash(self.as_dict())

    def tighten(self, override: dict) -> "Limits":
        """Apply an override that may only tighten. Unknown keys and loosening values are refused."""
        names = {f.name for f in fields(self)}
        bad = sorted(set(override) - names)
        if bad:
            raise LimitsError(f"unknown limit(s): {bad}")
        errors, new = [], {}
        for k, v in override.items():
            cur = getattr(self, k)
            if k in FIXED:
                errors.append(f"{k} is fixed in code")
                continue
            if isinstance(cur, bool):
                if not isinstance(v, bool):
                    errors.append(f"{k} must be true or false")
                elif k in FLAGS_TIGHT_WHEN_TRUE and cur and not v:
                    errors.append(f"{k} cannot be relaxed")
                else:
                    new[k] = v
            elif not isinstance(v, (int, float)) or isinstance(v, bool) or not _finite(v) or v < 0:
                errors.append(f"{k} must be a finite, non-negative number")
            elif isinstance(cur, int) and v != int(v):
                errors.append(f"{k} must be a whole number (got {v})")
            elif k in POSITIVE and v <= 0:
                errors.append(f"{k} must be positive (0 would disable the limit, not tighten it)")
            elif k in CAPS and v > cur:
                errors.append(f"{k}={v} would raise the ceiling {cur}")
            elif k in FLOORS and v < cur:
                errors.append(f"{k}={v} would lower the floor {cur}")
            else:
                new[k] = type(cur)(v) if not isinstance(cur, bool) else v
                continue
            # an error was recorded for this key: nothing of it is applied
        if errors:
            raise LimitsError("; ".join(errors))
        out = replace(self, **new)
        if out.backoff_max_s < out.backoff_base_s:
            raise LimitsError("backoff_max_s is below backoff_base_s")
        return out


DEFAULT = Limits()


def load(root: Path, base: Limits = DEFAULT) -> Limits:
    p = Path(root) / "limits.json"
    if not p.exists():
        return base
    try:
        override = json.loads(p.read_text(encoding="utf-8"),
                              parse_constant=lambda c: (_ for _ in ()).throw(LimitsError(f"{p}: {c} is not a limit")))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        raise LimitsError(f"{p} is not readable JSON: {type(e).__name__}") from e
    if not isinstance(override, dict):
        raise LimitsError(f"{p} must hold an object")
    return base.tighten(override)


def backoff_seconds(limits: Limits, consecutive: int) -> int:
    """Exponential back-off before a retry: base x 2^(k-1), capped."""
    k = max(1, consecutive)
    return int(min(limits.backoff_max_s, limits.backoff_base_s * 2 ** (k - 1)))
