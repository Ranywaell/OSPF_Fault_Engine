"""Parser for ``show interfaces trunk``."""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, ParsedTrunk, TopologyFacts
from ospf_engine.utils.text import iter_nonempty_lines, safe_int

_TRUNK_HEADER_RE = re.compile(
    r"^Port\s+Mode\s+Encapsulation\s+Status\s+Native\s+vlan", re.IGNORECASE
)
_TRUNK_ROW_RE = re.compile(
    r"^(?P<port>\S+)\s+(?P<mode>\S+)\s+(?P<encap>\S+)\s+(?P<status>\S+)\s+(?P<native>\d+)\s*$",
    re.IGNORECASE,
)
_ALLOWED_HEADER_RE = re.compile(r"^Port\s+Vlans\s+allowed\s+on\s+trunk", re.IGNORECASE)
_ALLOWED_ROW_RE = re.compile(r"^(?P<port>\S+)\s+(?P<vlans>[\d,\-\s]+)\s*$")


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    section: str | None = None  # 'native' | 'allowed' | None
    by_port: dict[str, ParsedTrunk] = {}

    for line in iter_nonempty_lines(text):
        if _TRUNK_HEADER_RE.search(line):
            section = "native"
            continue
        if _ALLOWED_HEADER_RE.search(line):
            section = "allowed"
            continue

        if section == "native":
            m = _TRUNK_ROW_RE.match(line)
            if m:
                port = m.group("port")
                trunk = by_port.setdefault(port, ParsedTrunk(device=device, port=port))
                trunk.encapsulation = m.group("encap")
                trunk.status = m.group("status")
                trunk.native_vlan = safe_int(m.group("native"))
        elif section == "allowed":
            m = _ALLOWED_ROW_RE.match(line)
            if m:
                port = m.group("port")
                trunk = by_port.setdefault(port, ParsedTrunk(device=device, port=port))
                trunk.allowed_vlans = m.group("vlans").strip()

    facts.trunks.extend(by_port.values())
    # No per-device evidence emitted here - the correlator compares ports across switches.
    return evidence, facts
