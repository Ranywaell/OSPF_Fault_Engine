"""Parser for ``show ip route``."""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts


_OSPF_ROUTE_RE = re.compile(r"^\s*O(?:\s+IA|\s+E1|\s+E2|\s+N1|\s+N2)?\s", re.MULTILINE)
_OSPF_INTER_AREA_RE = re.compile(r"^\s*O\s+IA\s", re.MULTILINE)


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    has_ospf = bool(_OSPF_ROUTE_RE.search(text))
    has_ia = bool(_OSPF_INTER_AREA_RE.search(text))

    if not has_ospf:
        evidence.append(
            Evidence(
                tag="ospf_no_routes",
                level=EvidenceLevel.WEAK,
                source=source,
                detail=(
                    f"On {device}: no OSPF-learned routes (O / O IA) in the routing table. "
                    "This is a *consequence* of adjacency failure, not a root cause."
                ),
                devices=(device,),
            )
        )
    elif not has_ia:
        evidence.append(
            Evidence(
                tag="ospf_no_interarea_routes",
                level=EvidenceLevel.WEAK,
                source=source,
                detail=(
                    f"On {device}: intra-area OSPF routes are present but no inter-area (O IA) "
                    "routes. Possible ABR misconfiguration or area mismatch on a transit link."
                ),
                devices=(device,),
            )
        )

    return evidence, TopologyFacts()
