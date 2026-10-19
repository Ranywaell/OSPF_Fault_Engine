"""Parser for endpoint output (PC ipconfig / ping)."""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts


_NO_ADDRESS_RE = re.compile(r"IP\s+Address.*0\.0\.0\.0", re.IGNORECASE)
_REQUEST_TIMEOUT_RE = re.compile(
    r"Request\s+timed\s+out|Destination.*unreachable", re.IGNORECASE
)
_DHCP_NO_REPLY_RE = re.compile(
    r"DHCP\s+(?:request|discover).*(?:no\s+reply|timeout|fail)", re.IGNORECASE
)
_PING_REPLY_OK_RE = re.compile(
    r"Reply\s+from\s+\d+\.\d+\.\d+\.\d+|bytes\s+from\s+\d+\.\d+\.\d+\.\d+",
    re.IGNORECASE,
)


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    # Successful ping by IP - record as a fact for the correlator (no evidence emitted;
    # a successful ping is not a fault, but it lets us prove L3 reachability).
    if _PING_REPLY_OK_RE.search(text):
        facts.endpoint_ping_ok.append(device)

    if _NO_ADDRESS_RE.search(text):
        evidence.append(
            Evidence(
                tag="dhcp_client_no_address",
                level=EvidenceLevel.STRONG,
                source=source,
                detail=(
                    f"On {device} (endpoint): host has IP 0.0.0.0. DHCP did not return an "
                    "address. Check ip helper-address on the relay interface, the DHCP pool, "
                    "and L2 reachability between client and server."
                ),
                devices=(device,),
            )
        )

    if _DHCP_NO_REPLY_RE.search(text):
        evidence.append(
            Evidence(
                tag="dhcp_client_no_reply",
                level=EvidenceLevel.STRONG,
                source=source,
                detail=f"On {device} (endpoint): DHCP request was sent but no reply received.",
                devices=(device,),
            )
        )

    if _REQUEST_TIMEOUT_RE.search(text) and not _PING_REPLY_OK_RE.search(text):
        evidence.append(
            Evidence(
                tag="endpoint_unreachable",
                level=EvidenceLevel.WEAK,
                source=source,
                detail=(
                    f"On {device} (endpoint): ping failed. Connectivity is broken; this is a "
                    "symptom only - inspect routing, ACLs, and helper addresses."
                ),
                devices=(device,),
            )
        )

    return evidence, facts
