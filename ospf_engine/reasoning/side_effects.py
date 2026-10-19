"""Causal explanation graph: which faults *explain* which other symptoms.

If fault X is confirmed AND fault Y has only WEAK evidence AND X explains Y's
symptoms, then Y is suppressed (moved to "considered and ruled out") rather
than printed as a competing root cause.
"""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import (
    F_ACL_WRONG_DIRECTION,
    F_AREA_MISMATCH,
    F_DHCP_HELPER_MISSING,
    F_DHCP_SERVER_UNREACHABLE,
    F_DNS_FAILURE,
    F_DUPLICATE_ROUTER_ID,
    F_HELLOS_BLOCKED_ACL,
    F_MTU_MISMATCH,
    F_NATIVE_VLAN_MISMATCH,
    F_NETWORK_TYPE_MISMATCH,
    F_STP_WRONG_ROOT,
    F_TIMER_MISMATCH,
)


# fault_name -> set of faults whose WEAK symptoms this fault fully explains
EXPLAINS: dict[str, set[str]] = {
    F_HELLOS_BLOCKED_ACL: {
        F_AREA_MISMATCH,
        F_TIMER_MISMATCH,
        F_NETWORK_TYPE_MISMATCH,
        F_MTU_MISMATCH,
    },
    F_AREA_MISMATCH: {
        F_TIMER_MISMATCH,
        F_NETWORK_TYPE_MISMATCH,
    },
    F_TIMER_MISMATCH: {
        F_AREA_MISMATCH,
        F_NETWORK_TYPE_MISMATCH,
    },
    F_NETWORK_TYPE_MISMATCH: {
        F_AREA_MISMATCH,
        F_TIMER_MISMATCH,
    },
    F_MTU_MISMATCH: {
        F_DUPLICATE_ROUTER_ID,
        # The same syslog 'Mismatched hello parameters' message that confirms MTU
        # could also have meant area / timer / network-type. When MTU is the
        # CONFIG-confirmed cause, the others are alternatives we can rule out.
        F_AREA_MISMATCH,
        F_TIMER_MISMATCH,
        F_NETWORK_TYPE_MISMATCH,
    },
    F_NATIVE_VLAN_MISMATCH: {
        F_STP_WRONG_ROOT,
    },
    F_DHCP_HELPER_MISSING: {
        F_DHCP_SERVER_UNREACHABLE,
        F_DNS_FAILURE,  # PC with no IP can't reach DNS either
    },
    F_ACL_WRONG_DIRECTION: {
        F_DNS_FAILURE,  # if a wrong-direction ACL is dropping LAN traffic, DNS will look broken
    },
}
