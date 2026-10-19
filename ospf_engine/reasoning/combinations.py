"""Evidence combination rules.

When two specific tags are both present, the *combination* upgrades the
evidence level for a fault to CONFIG. Most CONFIG-level upgrades now happen
via the cross-device correlator, but a few in-device combinations are still
useful (e.g. if the user uploaded ``show access-lists`` AND ``show ip
interface`` for the same interface).

Each rule: (tag_a, tag_b, fault_name, upgrade_to)
"""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel
from ospf_engine.reasoning.knowledge_base import (
    F_ACL_WRONG_DIRECTION,
    F_DHCP_HELPER_MISSING,
    F_HELLOS_BLOCKED_ACL,
    F_NATIVE_VLAN_MISMATCH,
)


COMBINATION_UPGRADES: list[tuple[str, str, str, EvidenceLevel]] = [
    (
        "acl_blocks_ospf",
        "acl_applied_inbound",
        F_HELLOS_BLOCKED_ACL,
        EvidenceLevel.CONFIG,
    ),
    (
        "syslog_acl_deny",
        "acl_blocks_ospf",
        F_HELLOS_BLOCKED_ACL,
        EvidenceLevel.CONFIG,
    ),
    (
        "acl_deny_with_hits",
        "acl_applied_outbound",
        F_ACL_WRONG_DIRECTION,
        EvidenceLevel.CONFIG,
    ),
    (
        "dhcp_no_bindings",
        "dhcp_helper_missing",
        F_DHCP_HELPER_MISSING,
        EvidenceLevel.CONFIG,
    ),
    (
        "dhcp_client_no_address",
        "dhcp_helper_missing",
        F_DHCP_HELPER_MISSING,
        EvidenceLevel.CONFIG,
    ),
    (
        "syslog_native_vlan_mismatch",
        "syslog_spantree_pvst_bpdu",
        F_NATIVE_VLAN_MISMATCH,
        EvidenceLevel.CONFIG,
    ),
]
