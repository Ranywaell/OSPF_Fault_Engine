"""Evidence model.

Every piece of data extracted from a CLI output is wrapped in an `Evidence`
object tagged with one of three levels:

* WEAK   - symptom only (INIT state, neighbor down, missing routes).
           Proves something is wrong, NOT what caused it.
* STRONG - a direct observation of a fault mechanism (deny ospf in ACL,
           empty DHCP table, blocking port). Strongly suggests a cause.
* CONFIG - an explicit configuration conflict was confirmed (Area 0 vs
           Area 1 on the same link, hello 10 vs 20 across peers, ACL
           applied to interface AND ACL contains deny ospf).

The reasoner caps confidence based on the highest evidence level so the
engine never claims "Confirmed Cause" without CONFIG-level proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvidenceLevel(str, Enum):
    WEAK = "WEAK"
    STRONG = "STRONG"
    CONFIG = "CONFIG"

    @property
    def order(self) -> int:
        return _LEVEL_ORDER[self]


_LEVEL_ORDER: dict[EvidenceLevel, int] = {
    EvidenceLevel.WEAK: 0,
    EvidenceLevel.STRONG: 1,
    EvidenceLevel.CONFIG: 2,
}


def best_level(levels: list[EvidenceLevel]) -> EvidenceLevel:
    """Return the highest-confidence level from a list."""
    if not levels:
        return EvidenceLevel.WEAK
    return max(levels, key=lambda lvl: lvl.order)


@dataclass(slots=True)
class Evidence:
    """A single piece of observational evidence extracted from device output."""

    tag: str
    """Short canonical identifier, e.g. 'area_mismatch_link', 'acl_blocks_ospf'."""

    level: EvidenceLevel
    """Confidence tier of this observation."""

    source: str
    """Where this evidence came from, e.g. 'R1_ospf_interface.txt'."""

    detail: str
    """Human-readable explanation an operator can read."""

    devices: tuple[str, ...] = field(default_factory=tuple)
    """Device IDs this evidence relates to (e.g. ('R1', 'R2') for cross-device)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "level": self.level.value,
            "source": self.source,
            "detail": self.detail,
            "devices": list(self.devices),
        }
