"""Parser for ``show logging`` / generic syslog dumps.

Syslog evidence is mostly STRONG when the message identifies a *mechanism*
(e.g. CDP NATIVE_VLAN_MISMATCH) and WEAK when it only reports an *outcome*
(e.g. OSPF ADJCHG DOWN).
"""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts


# (regex, tag, level, explanation_template)
_PATTERNS: list[tuple[re.Pattern[str], str, EvidenceLevel, str]] = [
    (
        re.compile(r"%CDP-\d-NATIVE_VLAN_MISMATCH", re.IGNORECASE),
        "syslog_native_vlan_mismatch",
        # CONFIG: CDP self-reports the conflict by listing both native VLANs
        # ('VLAN 1, with SW2 ... VLAN 99'). That is the same kind of explicit
        # cross-device disagreement the correlator emits at CONFIG.
        EvidenceLevel.CONFIG,
        "Switch CDP detected a native VLAN mismatch on a trunk link "
        "(CDP reports the disagreement explicitly between the two switches).",
    ),
    (
        re.compile(r"%SPANTREE-\d-RECV_PVST_BPDU", re.IGNORECASE),
        "syslog_spantree_pvst_bpdu",
        EvidenceLevel.STRONG,
        "Spanning-tree received PVST BPDUs on a non-trunk port - native VLAN mismatch likely.",
    ),
    (
        re.compile(r"%SPANTREE-\d-(?:TOPOTRAP|TOPOLOGY)", re.IGNORECASE),
        "syslog_stp_topology_change",
        EvidenceLevel.STRONG,
        "STP topology change detected.",
    ),
    (
        re.compile(r"%SPANTREE-\d-ROOTCHANGE", re.IGNORECASE),
        "syslog_stp_root_change",
        EvidenceLevel.STRONG,
        "STP elected a different root bridge.",
    ),
    (
        re.compile(r"%SEC-\d-IPACCESSLOG[A-Z]?", re.IGNORECASE),
        "syslog_acl_deny",
        EvidenceLevel.STRONG,
        "ACL is actively dropping traffic (logged).",
    ),
    (
        re.compile(r"%OSPF-\d-MISMATCH", re.IGNORECASE),
        "syslog_ospf_mismatch",
        EvidenceLevel.STRONG,
        "OSPF logged an explicit parameter mismatch (area, hello/dead, MTU, or auth).",
    ),
    (
        re.compile(r"Mismatched\s+hello\s+parameters", re.IGNORECASE),
        "syslog_ospf_mismatch",
        EvidenceLevel.STRONG,
        "OSPF logged 'Mismatched hello parameters' - timer or MTU mismatch.",
    ),
    (
        re.compile(r"%OSPF-\d-ADJCHG.*\bDOWN\b", re.IGNORECASE),
        "syslog_ospf_adjacency_down",
        EvidenceLevel.WEAK,
        "OSPF adjacency went DOWN. This is a consequence; the cause is elsewhere.",
    ),
    (
        re.compile(r"DHCP.*(?:no\s+reply|timeout)", re.IGNORECASE),
        "syslog_dhcp_no_reply",
        EvidenceLevel.STRONG,
        "DHCP request was not answered - relay or server problem.",
    ),
    (
        re.compile(r"%DUAL-\d-NBRCHANGE.*DOWN", re.IGNORECASE),
        "syslog_eigrp_neighbor_down",
        EvidenceLevel.WEAK,
        "EIGRP neighbor went down - typically a side-effect of L2/L3 instability.",
    ),
    (
        re.compile(r"DNS.*(?:server\s+unreachable|unable\s+to\s+resolve)", re.IGNORECASE),
        "syslog_dns_failure",
        EvidenceLevel.STRONG,
        "DNS server unreachable or name resolution failed.",
    ),
]


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    seen_tags: set[str] = set()

    for pattern, tag, level, explanation in _PATTERNS:
        m = pattern.search(text)
        if not m or tag in seen_tags:
            continue
        seen_tags.add(tag)
        evidence.append(
            Evidence(
                tag=tag,
                level=level,
                source=source,
                detail=f"On {device}: {explanation}",
                devices=(device,),
            )
        )

    return evidence, TopologyFacts()
