"""Prices and corporate actions, point in time: raw closes, split adjustment, total returns and delisting returns.

    book = PriceBook(calendar)
    book.add_bar(Bar("S1", day, close=41.2, currency="USD", volume=1.2e6))
    book.add_action(CorporateAction("S1", "split", ex_date=..., known_from=..., ratio=2.0))
    days, r = book.total_returns("S1", start, end, as_of=end, delisting=DelistingPolicy.require())

**Raw prices are the record.** A bar stores the unadjusted close in the security's trading currency. Adjusted
series are computed on demand **as of a date** from the actions known by then: the split-adjusted history seen on
2008-01-02 does not contain a split announced in 2009, so a back-adjusted series cannot leak a later split.

**Total return.** For consecutive sessions ``t−1, t``::

    r_t = ( P_t · k_t + D_t ) / P_{t−1} − 1

where ``k_t`` is the product of split ratios (new shares per old share) with ex-date ``t`` and ``D_t`` the cash
distributions per **post-split** share with ex-date ``t`` (regular and special alike; special dividends are kept
apart in the record because they are not income signals). A distribution in another currency is refused
(``CurrencyError``): conversion must be explicit.

**Gaps.** A session with no bar (missing data) or a suspended bar gives no return for that day; the return from the
last traded close to the next is booked on the day trading resumes and the day is flagged ``multi_session``.
A close-to-close ratio within 1% of a common split ratio (2:1, 3:2, 1:10 ...) with no known split raises
``CorporateActionError``, and so does any move whose absolute log return exceeds ``max_unexplained_move`` (default
1.0, about −63% or +172%) unless it was confirmed against the source (``confirm_move``). A silent missing split
creates a fictitious return of −50% or more.

**Delisting.** After the last trading day the position's final return is the **delisting return** (the value
received for the share: cash merger terms, last OTC price, zero in a bankruptcy). It must come from the data
(``DelistingReturn``) or from an explicit, declared assumption (``DelistingPolicy.assume``) that is flagged in the
output. Dropping the security, the default of many databases, is survivorship bias and is refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from .errors import CorporateActionError, CurrencyError, TemporalError
from .identity import DELISTING_REASONS
from .sessions import MarketCalendar

ACTION_KINDS = ("split", "cash_dividend", "special_dividend", "stock_dividend", "return_of_capital")
BAR_STATUSES = ("traded", "suspended")
# split-like close ratios (new shares per old, forward and reverse) that a missing split would leave in raw closes
COMMON_SPLITS = (1.5, 2.0, 3.0, 4.0, 5.0, 7.0, 8.0, 10.0, 20.0, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 8, 1 / 10, 1 / 20)
SPLIT_TOLERANCE = 0.01


@dataclass(frozen=True)
class Bar:
    security_id: str
    day: date
    close: float                        # raw, unadjusted
    currency: str
    volume: float = 0.0
    status: str = "traded"

    def __post_init__(self):
        if self.status not in BAR_STATUSES:
            raise CorporateActionError(f"{self.security_id} {self.day}: unknown bar status {self.status!r}")
        if self.status == "traded" and not (np.isfinite(self.close) and self.close > 0):
            raise CorporateActionError(f"{self.security_id} {self.day}: a traded close must be positive")
        if self.volume < 0:
            raise CorporateActionError(f"{self.security_id} {self.day}: negative volume")


@dataclass(frozen=True)
class CorporateAction:
    security_id: str
    kind: str
    ex_date: date
    known_from: date                    # first day the action was public (declaration / announcement)
    ratio: float = 1.0                  # split or stock dividend: new shares per old share
    amount: float = 0.0                 # cash per post-split share
    currency: str | None = None

    def __post_init__(self):
        if self.kind not in ACTION_KINDS:
            raise CorporateActionError(f"unknown corporate action {self.kind!r}")
        if self.known_from > self.ex_date:
            raise TemporalError(f"{self.security_id}: an action cannot become public after its ex-date "
                                f"({self.known_from} > {self.ex_date}); record the late capture instead")
        if self.kind in ("split", "stock_dividend") and not (self.ratio > 0 and self.ratio != 1.0):
            raise CorporateActionError(f"{self.security_id}: a split needs a ratio other than 1")
        if self.kind in ("cash_dividend", "special_dividend", "return_of_capital"):
            if not self.amount > 0 or not self.currency:
                raise CorporateActionError(f"{self.security_id}: a cash distribution needs an amount and a currency")


@dataclass(frozen=True)
class DelistingReturn:
    security_id: str
    last_day: date                      # last trading day
    value: float                        # return from the last close to the delisting proceeds
    known_from: date                    # when the proceeds were known (cash terms, final OTC price, liquidation)
    source: str = ""

    def __post_init__(self):
        if not (np.isfinite(self.value) and self.value >= -1.0):
            raise CorporateActionError(f"{self.security_id}: a delisting return is a finite number, at least −100%")


@dataclass(frozen=True)
class DelistingPolicy:
    """What to do when a security stops trading inside the requested span. ``require``: the data must hold a
    delisting return. ``assume``: use a declared value per delisting reason, flagged as assumed."""
    mode: str = "require"
    assumed: dict = field(default_factory=dict)          # reason -> return
    reference: str = ""

    @classmethod
    def require(cls) -> "DelistingPolicy":
        return cls("require")

    @classmethod
    def assume(cls, assumed: dict, reference: str) -> "DelistingPolicy":
        if not assumed or not reference:
            raise CorporateActionError("an assumed delisting return needs values per reason and a reference")
        return cls("assume", dict(assumed), reference)


@dataclass
class ReturnSeries:
    security_id: str
    days: np.ndarray                    # session days with a return (object array of dates)
    returns: np.ndarray
    multi_session: np.ndarray           # bool: return spans a missing or suspended session
    delisting_day: date | None = None
    delisting_assumed: bool = False
    as_of: date | None = None


class PriceBook:
    """Raw bars, corporate actions and delisting returns of many securities, on one calendar."""

    def __init__(self, calendar: MarketCalendar, *, max_unexplained_move: float | None = 1.0):
        self.calendar = calendar
        self.max_unexplained_move = max_unexplained_move
        self._bars: dict[str, dict[date, Bar]] = {}
        self._actions: dict[str, list[CorporateAction]] = {}
        self._delisting: dict[str, DelistingReturn] = {}
        self._currency: dict[str, str] = {}
        self._last_day: dict[str, date] = {}
        self._reasons: dict[str, str] = {}
        self._confirmed: dict[tuple, str] = {}

    # ---- building
    def add_bar(self, bar: Bar) -> None:
        if not self.calendar.is_session(bar.day):
            raise TemporalError(f"{bar.security_id}: {bar.day} is not a session of {self.calendar.name} "
                                "(the market was closed)")
        cur = self._currency.setdefault(bar.security_id, bar.currency)
        if cur != bar.currency:
            raise CurrencyError(f"{bar.security_id}: bars in {cur} and {bar.currency}")
        bars = self._bars.setdefault(bar.security_id, {})
        if bar.day in bars and bars[bar.day] != bar:
            raise CorporateActionError(f"{bar.security_id} {bar.day}: two different bars")
        bars[bar.day] = bar

    def add_bars(self, security_id: str, days, closes, *, currency: str, volumes=None) -> None:
        vols = np.zeros(len(closes)) if volumes is None else volumes
        for d, c, v in zip(days, closes, vols):
            self.add_bar(Bar(security_id, d, float(c), currency, float(v)))

    def add_action(self, a: CorporateAction) -> None:
        if a.currency and a.security_id in self._currency and a.currency != self._currency[a.security_id]:
            raise CurrencyError(f"{a.security_id}: a {a.kind} in {a.currency} on a security priced in "
                                f"{self._currency[a.security_id]}; convert explicitly first")
        self._actions.setdefault(a.security_id, []).append(a)

    def add_delisting_return(self, d: DelistingReturn) -> None:
        if d.security_id in self._delisting and self._delisting[d.security_id] != d:
            raise CorporateActionError(f"{d.security_id}: two delisting returns")
        self._delisting[d.security_id] = d

    # ---- queries
    def securities(self) -> tuple:
        return tuple(sorted(self._bars))

    def currency(self, security_id: str) -> str:
        return self._currency[security_id]

    def bars(self, security_id: str, start: date, end: date) -> list[Bar]:
        b = self._bars.get(security_id, {})
        return [b[d] for d in sorted(b) if start <= d <= end]

    def actions_known(self, security_id: str, as_of: date) -> list[CorporateAction]:
        return sorted((a for a in self._actions.get(security_id, []) if a.known_from <= as_of),
                      key=lambda a: (a.ex_date, a.kind))

    def last_traded(self, security_id: str, as_of: date) -> date | None:
        days = [d for d, b in self._bars.get(security_id, {}).items() if d <= as_of and b.status == "traded"]
        return max(days) if days else None

    def split_adjusted_closes(self, security_id: str, start: date, end: date, *, as_of: date):
        """Closes from ``start`` to ``end`` back-adjusted for splits known by ``as_of`` (only those with ex-date
        ``<= as_of``: a split is not applied before it happens). Returns (days, closes)."""
        if end > as_of:
            raise TemporalError(f"{security_id}: closes up to {end} are not known at {as_of}")
        bars = [b for b in self.bars(security_id, start, end) if b.status == "traded"]
        splits = [a for a in self.actions_known(security_id, as_of)
                  if a.kind in ("split", "stock_dividend") and a.ex_date <= as_of]
        days = np.array([b.day for b in bars], dtype=object)
        closes = np.array([b.close for b in bars], dtype=float)
        for s in splits:
            closes[days < s.ex_date] /= s.ratio
        return days, closes

    def total_returns(self, security_id: str, start: date, end: date, *, as_of: date,
                      delisting: DelistingPolicy | None = None) -> ReturnSeries:
        """Daily total returns for sessions in ``(start, end]`` known at the close of ``as_of`` (see module)."""
        if end > as_of:
            raise TemporalError(f"{security_id}: returns up to {end} are not known at {as_of}")
        delisting = delisting or DelistingPolicy.require()
        allbars = self._bars.get(security_id, {})
        sessions = self.calendar.sessions_between(start, end)
        actions = [a for a in self.actions_known(security_id, as_of) if start < a.ex_date <= end]
        cur = self._currency.get(security_id)
        prev_close, prev_day = None, None
        before = [d for d, b in allbars.items() if d <= start and b.status == "traded"]
        if before:
            prev_day = max(before)
            prev_close = allbars[prev_day].close
        days, rets, multi = [], [], []
        pending_k, pending_d = 1.0, 0.0
        gap = False
        for d in sessions:
            if d == start:
                continue
            for a in actions:
                if a.ex_date == d:
                    if a.currency and cur and a.currency != cur:
                        raise CurrencyError(f"{security_id}: {a.kind} in {a.currency}, priced in {cur}")
                    if a.kind in ("split", "stock_dividend"):
                        pending_k *= a.ratio
                    else:
                        pending_d += a.amount
            bar = allbars.get(d)
            if bar is None or bar.status != "traded":
                gap = True if prev_close is not None else gap
                continue
            if prev_close is not None:
                r = (bar.close * pending_k + pending_d) / prev_close - 1.0
                self._check_move(security_id, d, r, pending_k, as_of)
                days.append(d)
                rets.append(r)
                multi.append(gap)
            prev_close, prev_day = bar.close, d
            pending_k, pending_d, gap = 1.0, 0.0, False
        out = ReturnSeries(security_id, np.array(days, dtype=object), np.array(rets, dtype=float),
                           np.array(multi, dtype=bool), as_of=as_of)
        listed_to = self._listed_to(security_id)
        if listed_to is not None and start <= listed_to < end:
            out = self._append_delisting(out, security_id, listed_to, end, as_of, delisting)
        return out

    def confirm_move(self, security_id: str, day: date, note: str) -> None:
        """Record that an extreme move on ``day`` was checked against the source and is genuine."""
        if not note:
            raise CorporateActionError("a confirmed move needs a note saying how it was checked")
        self._confirmed[(security_id, day)] = note

    def _check_move(self, security_id: str, day: date, r: float, k: float, as_of: date) -> None:
        if (security_id, day) in self._confirmed:
            return
        ratio = 1.0 + r
        if k == 1.0 and any(abs(ratio * s - 1.0) < SPLIT_TOLERANCE for s in COMMON_SPLITS):
            raise CorporateActionError(
                f"{security_id} {day}: close-to-close ratio {ratio:.4f} matches a split and no split is known at "
                f"{as_of}; resolve the corporate action before use")
        if self.max_unexplained_move is not None and abs(np.log(ratio)) > self.max_unexplained_move:
            raise CorporateActionError(
                f"{security_id} {day}: move {r:+.1%} exceeds the unexplained-move limit; confirm it against the "
                "source (confirm_move) or record the missing action")

    def _listed_to(self, security_id: str) -> date | None:
        """The last trading day, when a delisting return is recorded or trading has stopped for good."""
        d = self._delisting.get(security_id)
        return d.last_day if d else self._last_day.get(security_id)

    def mark_delisted(self, security_id: str, last_day: date, reason: str = "unknown") -> None:
        """Declare that ``security_id`` stopped trading after ``last_day``, and why (from the security master)."""
        if security_id in self._last_day and self._last_day[security_id] != last_day:
            raise CorporateActionError(f"{security_id}: two different last trading days")
        self._last_day[security_id] = last_day
        self._reasons[security_id] = reason

    def _append_delisting(self, out: ReturnSeries, security_id: str, last_day: date, end: date, as_of: date,
                          policy: DelistingPolicy) -> ReturnSeries:
        nxt = self.calendar.next_session(last_day)
        if nxt > end:
            return out
        rec = self._delisting.get(security_id)
        if rec is not None and rec.known_from <= as_of:
            value, assumed = rec.value, False
        elif policy.mode == "assume":
            reason = self._reasons.get(security_id, "unknown")
            if reason not in policy.assumed:
                raise CorporateActionError(f"{security_id}: no delisting return and no assumption for reason "
                                           f"{reason!r}")
            value, assumed = float(policy.assumed[reason]), True
        else:
            raise CorporateActionError(f"{security_id}: delisted after {last_day} and no delisting return is known "
                                       f"at {as_of}; dropping it would be survivorship bias")
        out.days = np.append(out.days, np.array([nxt], dtype=object))
        out.returns = np.append(out.returns, value)
        out.multi_session = np.append(out.multi_session, False)
        out.delisting_day, out.delisting_assumed = nxt, assumed
        return out

    def corporate_action_complete(self, security_id: str, start: date, end: date, *, as_of: date) -> bool:
        """True when every close-to-close move in the span is either ordinary or explained by a known action."""
        try:
            self.total_returns(security_id, start, min(end, as_of), as_of=as_of,
                               delisting=DelistingPolicy.assume({r: 0.0 for r in DELISTING_REASONS},
                                                                "completeness check only: value unused"))
        except CorporateActionError:
            return False
        return True

    def dollar_volume(self, security_id: str, end: date, sessions: int) -> np.ndarray:
        """Close × volume of the last ``sessions`` traded bars on or before ``end`` (raw, unadjusted)."""
        b = self._bars.get(security_id, {})
        days = sorted(d for d in b if d <= end and b[d].status == "traded")[-sessions:]
        return np.array([b[d].close * b[d].volume for d in days], dtype=float)
