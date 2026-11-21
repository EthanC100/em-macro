"""Where a cost number comes from: known, estimated or scenario. Every cost component carries one ``Source``.

**Three classes, seven kinds.** The class decides what a result may be called (``realism.assess``):

| class | kinds | meaning | needs |
|---|---|---|---|
| ``known`` | ``recorded`` | measured from recorded quotes, fills or statements over the dates used (the Protocol v3.1 section 10 estimator: median recorded half-spreads and fees) | reference, ``valid_from``, ``valid_to`` |
| | ``published_schedule`` | a fee schedule or contract specification in force on the dates used | reference, ``valid_from``, ``valid_to`` |
| ``estimated`` | ``literature_estimate`` | a published study's figure for a similar instrument and period (as in ``results/cost_audit/cost_estimates.csv``) | reference |
| | ``model_estimate`` | the output of a stated model, e.g. square-root impact with an assumed coefficient | reference |
| | ``extrapolated`` | a ``known`` number used outside the dates it is known for (set by ``for_window``, never by hand) | reference |
| ``scenario`` | ``scenario`` | a sensitivity or stress value, e.g. a 2x multiple of another source | reference |
| | ``synthetic`` | made up for a test; describes no market | nothing |

**Refused labels.** ``calibrated``, ``realistic``, ``actual``, ``measured`` and ``live``: no number in this package is
calibrated against fills, so no label may suggest it (PR #85 refuses ``calibrated`` for the same reason).

**Known for which dates.** A ``known`` source is known only for ``[valid_from, valid_to]``. ``for_window(start, end)``
returns the source unchanged when the evaluation window lies inside that range, and an ``extrapolated`` source
(class ``estimated``) when it does not: a 2026 fee schedule applied to 2008 trades is an estimate, not a known cost.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .errors import ProvenanceError

CLASS_OF = {
    "recorded": "known", "published_schedule": "known",
    "literature_estimate": "estimated", "model_estimate": "estimated", "extrapolated": "estimated",
    "scenario": "scenario", "synthetic": "scenario",
}
KINDS = tuple(CLASS_OF)
CLASSES = ("known", "estimated", "scenario")         # strongest first
REFUSED = ("calibrated", "realistic", "actual", "measured", "live")


@dataclass(frozen=True)
class Source:
    kind: str
    reference: str = ""                 # citation, file and row, or how the value was derived
    valid_from: date | None = None      # for ``known`` kinds: the dates the number is known for
    valid_to: date | None = None

    def __post_init__(self):
        if self.kind in REFUSED:
            raise ProvenanceError(f"cost provenance {self.kind!r} is refused: nothing in this package is calibrated "
                                  f"against fills; use one of {KINDS}")
        if self.kind not in CLASS_OF:
            raise ProvenanceError(f"cost provenance must be one of {KINDS}, not {self.kind!r}")
        if not isinstance(self.reference, str):
            raise ProvenanceError("reference is text")
        if self.kind != "synthetic" and not self.reference.strip():
            raise ProvenanceError(f"a {self.kind!r} cost needs a reference saying where it comes from")
        if self.cls == "known":
            if not (isinstance(self.valid_from, date) and isinstance(self.valid_to, date)):
                raise ProvenanceError(f"a {self.kind!r} cost is known only for stated dates: give valid_from and "
                                      "valid_to")
            if self.valid_to < self.valid_from:
                raise ProvenanceError("valid_to is before valid_from")

    @property
    def cls(self) -> str:
        return CLASS_OF[self.kind]

    def for_window(self, start: date, end: date) -> "Source":
        """This source as it applies to an evaluation window: a ``known`` source outside its dates becomes
        ``extrapolated``."""
        if self.cls != "known" or (self.valid_from <= start and end <= self.valid_to):
            return self
        return Source("extrapolated", f"{self.kind} for {self.valid_from}..{self.valid_to} used for {start}..{end}: "
                                      f"{self.reference}")

    def as_dict(self) -> dict:
        return {"kind": self.kind, "class": self.cls, "reference": self.reference,
                "valid_from": self.valid_from.isoformat() if self.valid_from else None,
                "valid_to": self.valid_to.isoformat() if self.valid_to else None}


SYNTHETIC = Source("synthetic")


def weakest(classes) -> str:
    """The weakest of a collection of classes (``scenario`` < ``estimated`` < ``known``)."""
    classes = set(classes)
    for c in reversed(CLASSES):
        if c in classes:
            return c
    raise ProvenanceError("no cost sources given")
