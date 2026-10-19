"""Parser for ``show spanning-tree``.

Detects whether *this* switch believes itself to be the root, and any blocking
ports. Cross-switch root-election anomalies are detected by the correlator.
"""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts
from ospf_engine.models.topology import ParsedStpVlan
from ospf_engine.utils.text import safe_int

_VLAN_HEADER_RE = re.compile(r"^VLAN(?P<vlan>\d+)", re.IGNORECASE | re.MULTILINE)
_THIS_BRIDGE_IS_ROOT_RE = re.compile(r"This bridge is the root", re.IGNORECASE)
_ROOT_PRI_RE = re.compile(
    r"Root\s+ID\s+Priority\s+(?P<pri>\d+)", re.IGNORECASE
)
_BRIDGE_PRI_RE = re.compile(
    r"Bridge\s+ID\s+Priority\s+(?P<pri>\d+)", re.IGNORECASE
)
_BLOCKING_PORT_RE = re.compile(
    r"^(?P<port>\S+)\s+\S+\s+BLK\b", re.IGNORECASE | re.MULTILINE
)


def _split_vlan_blocks(text: str) -> list[tuple[int, str]]:
    matches = list(_VLAN_HEADER_RE.finditer(text))
    if not matches:
        return []
    blocks: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        vlan = safe_int(m.group("vlan"))
        if vlan is not None:
            blocks.append((vlan, text[start:end]))
    return blocks


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    blocks = _split_vlan_blocks(text)
    if not blocks:
        # Fall back to treating the whole output as VLAN 1 if no header.
        blocks = [(1, text)]

    for vlan, block in blocks:
        is_root = bool(_THIS_BRIDGE_IS_ROOT_RE.search(block))
        root_pri = _ROOT_PRI_RE.search(block)
        br_pri = _BRIDGE_PRI_RE.search(block)
        rp = safe_int(root_pri.group("pri")) if root_pri else None
        bp = safe_int(br_pri.group("pri")) if br_pri else None

        # If we have both numbers and they differ, the local bridge isn't root.
        if rp is not None and bp is not None and rp != bp:
            is_root = False
        # If priorities are *equal*, this bridge IS the root - regardless of
        # whether the literal "This bridge is the root" line appeared.
        if rp is not None and bp is not None and rp == bp:
            is_root = True

        blocked = _BLOCKING_PORT_RE.findall(block)

        facts.stp_vlans.append(
            ParsedStpVlan(
                device=device,
                vlan=vlan,
                is_root=is_root,
                root_priority=rp,
                bridge_priority=bp,
                blocked_ports=blocked,
            )
        )

        if blocked:
            evidence.append(
                Evidence(
                    tag="stp_port_blocking",
                    level=EvidenceLevel.STRONG,
                    source=source,
                    detail=(
                        f"On {device}: VLAN {vlan} - port(s) {', '.join(blocked)} are in "
                        "BLOCKING state. This may be correct loop prevention OR a symptom of "
                        "a native VLAN mismatch / unexpected root."
                    ),
                    devices=(device,),
                )
            )

        if not is_root and rp is not None and bp is not None and bp != rp:
            evidence.append(
                Evidence(
                    tag="stp_not_root",
                    level=EvidenceLevel.WEAK,
                    source=source,
                    detail=(
                        f"On {device}: VLAN {vlan} - root priority {rp}, this bridge "
                        f"priority {bp}. This switch is NOT the root bridge. The correlator "
                        "will flag whether the elected root is the intended one."
                    ),
                    devices=(device,),
                )
            )

    return evidence, facts
