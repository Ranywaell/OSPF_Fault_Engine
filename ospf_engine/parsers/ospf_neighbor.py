"""Parser for ``show ip ospf neighbor`` (and ``... detail``)."""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, ParsedNeighbor, TopologyFacts
from ospf_engine.utils.text import iter_nonempty_lines

# Standard 6-column layout:
#   Neighbor ID     Pri   State      Dead Time   Address       Interface
#   2.2.2.2         1     FULL/DR    00:00:35    10.0.1.2      GigabitEthernet0/0
_NEIGHBOR_RE = re.compile(
    r"^(?P<nbr>\d+\.\d+\.\d+\.\d+)\s+"
    r"(?P<pri>\d+)\s+"
    r"(?P<state>[A-Za-z2/\-]+)\s+"
    r"(?:[\d:]+\s+)?"  # dead time (optional in some outputs)
    r"(?P<addr>\d+\.\d+\.\d+\.\d+)\s+"
    r"(?P<iface>\S+)"
)


def _classify_state(state: str) -> tuple[str, EvidenceLevel, str] | None:
    """Map an OSPF neighbor state to (tag, level, explanation)."""
    s = state.upper()
    if "FULL" in s:
        return None  # adjacency healthy on this side
    if "INIT" in s or "ATTEMPT" in s:
        return (
            "ospf_adjacency_failure",
            EvidenceLevel.WEAK,
            f"Neighbor stuck in {state}. Hellos are being received but adjacency cannot "
            "complete. Possible causes: ACL blocking OSPF, area mismatch, authentication "
            "mismatch, network-type mismatch, or timer mismatch.",
        )
    if "EXSTART" in s or "EXCHANGE" in s:
        return (
            "ospf_exstart_stuck",
            EvidenceLevel.STRONG,
            f"Neighbor stuck in {state}. Hellos succeeded but DBD exchange is failing. "
            "Classic symptom of an MTU mismatch on the link, but can also indicate a "
            "duplicate router-ID or authentication mismatch.",
        )
    if "2WAY" in s or "DROTHER" in s:
        return (
            "ospf_2way_unexpected",
            EvidenceLevel.WEAK,
            f"Neighbor in {state}. On a multi-access network this is normal between two "
            "non-DR/BDR routers; on a point-to-point link it indicates a network-type mismatch.",
        )
    return None


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()
    found_any = False

    for line in iter_nonempty_lines(text):
        m = _NEIGHBOR_RE.match(line)
        if not m:
            continue
        found_any = True
        nbr = m.group("nbr")
        state = m.group("state")
        iface = m.group("iface")
        addr = m.group("addr")

        facts.neighbors.append(
            ParsedNeighbor(
                device=device, neighbor_id=nbr, state=state, interface=iface, address=addr
            )
        )

        classified = _classify_state(state)
        if classified is None:
            continue
        tag, level, explanation = classified
        evidence.append(
            Evidence(
                tag=tag,
                level=level,
                source=source,
                detail=f"On {device}: neighbor {nbr} via {iface} - {explanation}",
                devices=(device,),
            )
        )

    if not found_any:
        # Empty neighbor table is itself a (weak) symptom only if other text
        # confirms OSPF is enabled. We always emit it; the suppressor will
        # remove it once a CONFIG cause is identified.
        evidence.append(
            Evidence(
                tag="ospf_no_neighbor",
                level=EvidenceLevel.WEAK,
                source=source,
                detail=(
                    f"On {device}: 'show ip ospf neighbor' returns no entries. "
                    "Either OSPF hellos are not being exchanged, the interface is passive, "
                    "or the link is down."
                ),
                devices=(device,),
            )
        )

    return evidence, facts
