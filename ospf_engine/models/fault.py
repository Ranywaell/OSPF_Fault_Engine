"""Fault catalog model — a single network-fault definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FaultCategory(str, Enum):
    OSPF = "OSPF"
    ACL = "ACL"
    STP_VLAN = "STP/VLAN"
    DHCP = "DHCP"
    DNS = "DNS"
    LINK = "Link/Physical"


@dataclass(slots=True, frozen=True)
class Fault:
    """A canonical fault definition: cause, verification commands, safe fix."""

    name: str
    category: FaultCategory
    cause: str
    verify: tuple[str, ...]
    fix: str
    fix_dependencies: tuple[str, ...] = field(default_factory=tuple)
    """Names of faults that must be resolved BEFORE this one (used by fix_planner)."""
