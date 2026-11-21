"""The executable evaluation identity with the execution assumptions in it.

HTE binds its timing convention into every evaluation as one string (``evaluation_spec["execution"] =
"same_close_fill_next_day_return/v1"``). The bridge replaces that string with the full execution block:
timing (lag, label), the decision clock, the vol-scaling rule and its parameters, sizing (capital, rounding),
the missing-price and liquidity policies, the contract map's digest, the cost model's content id and every cost
source as it applies to the window, the shock scenario and the adapter version. Any change of an assumption is
a different ``spec_hash``; the same assumptions always give the same one.

Data identity stays separate, as PR #85 design section 16 item 6 requires: the HTE ``data_hash`` of the source
panel **and** the adapter's ``market_digest`` (``SettlementPanel.digest()``) of the panel built from it.
"""
from __future__ import annotations

import hashlib
import json

BRIDGE_VERSION = "hte-execution-bridge/1"
ADAPTER_VERSION = "execution_realism/0.1"
HTE_SAME_CLOSE = "same_close_fill_next_day_return/v1"


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def sha(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def executable_spec(hte_spec: dict | None, execution: dict) -> dict:
    """HTE's evaluation spec with its execution string replaced by the bridge's execution block. A spec whose
    execution is not HTE's known same-close convention is refused (an unknown HTE version)."""
    base = dict(hte_spec or {})
    old = base.pop("execution", HTE_SAME_CLOSE)
    if old != HTE_SAME_CLOSE:
        raise ValueError(f"unexpected HTE execution convention {old!r}")
    base["execution"] = {"replaces": HTE_SAME_CLOSE, **execution}
    base["bridge"] = BRIDGE_VERSION
    return base


def executable_identity(spec: dict, *, data_hash: str, market_digest: str, result_hash: str | None = None) -> dict:
    spec_hash = sha(spec)
    out = {"spec_hash": spec_hash, "execution_hash": sha(spec["execution"]), "data_hash": data_hash,
           "market_digest": market_digest,
           "executable": sha({"spec_hash": spec_hash, "bridge": BRIDGE_VERSION, "adapter": ADAPTER_VERSION})}
    if result_hash is not None:
        out["result_hash"] = result_hash
    return out
