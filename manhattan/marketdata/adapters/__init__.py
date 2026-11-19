"""Adapters: vendor raw files -> canonical observations (DESIGN.md section 4).

Every adapter

* parses raw bytes it is given; it never reads a path it was not given and never opens a network connection,
* asks the ``FenceGate`` about each row's instrument and session date **before** converting the row's values,
* takes the retrieval time from its caller (never from the clock) and puts it on every row as ``first_seen_utc``,
* refuses input it cannot map without guessing (unknown market, unknown symbol, a file not in the manifest, a
  manifest hash that does not match),
* refuses to fetch: ``fetch`` raises ``NotAuthorized`` (Norgate is exported on its own server; Databento costs
  money and needs Ethan's decision, ETHAN_ACTIONS item 8).
"""
from .base import Adapter, ParseResult
from .databento import DatabentoStatisticsAdapter
from .fixture import FixtureAdapter
from .norgate import NorgateExportAdapter

__all__ = ["Adapter", "ParseResult", "FixtureAdapter", "NorgateExportAdapter", "DatabentoStatisticsAdapter"]
