"""Parser for ``show ip dhcp binding``."""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts
from ospf_engine.models.topology import ParsedDhcpBinding


_BINDING_LINE_RE = re.compile(
    r"^\s*\d+\.\d+\.\d+\.\d+\s+\S+\s+\S+", re.MULTILINE
)


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    has_bindings = bool(_BINDING_LINE_RE.search(text))
    facts.dhcp_bindings.append(
        ParsedDhcpBinding(device=device, has_bindings=has_bindings)
    )

    if not has_bindings:
        evidence.append(
            Evidence(
                tag="dhcp_no_bindings",
                level=EvidenceLevel.STRONG,
                source=source,
                detail=(
                    f"On {device}: DHCP binding table is empty. No client has been issued an "
                    "address. Check ip helper-address on the relay interface, the DHCP pool on "
                    "the server, and L2 reachability between client and server."
                ),
                devices=(device,),
            )
        )

    return evidence, facts
