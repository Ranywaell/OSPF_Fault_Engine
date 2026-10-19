"""Mapping from evidence tags to candidate fault names.

A single piece of evidence can contribute to multiple candidate faults; the
*contribution level* clamps how strongly the evidence vote actually counts
toward each. WEAK evidence on a generic symptom contributes WEAK to every
candidate that could plausibly cause it; CONFIG evidence from the correlator
contributes CONFIG to exactly one fault.
"""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel
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


# Each entry: tag -> list of (fault_name, contribution_level)
TAG_TO_FAULT: dict[str, list[tuple[str, EvidenceLevel]]] = {
    # --- Generic OSPF symptom signals (WEAK contribution to many candidates) ---
    "ospf_no_neighbor": [
        (F_AREA_MISMATCH, EvidenceLevel.WEAK),
        (F_TIMER_MISMATCH, EvidenceLevel.WEAK),
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.WEAK),
        (F_NETWORK_TYPE_MISMATCH, EvidenceLevel.WEAK),
    ],
    "ospf_adjacency_failure": [
        (F_AREA_MISMATCH, EvidenceLevel.WEAK),
        (F_TIMER_MISMATCH, EvidenceLevel.WEAK),
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.WEAK),
        (F_NETWORK_TYPE_MISMATCH, EvidenceLevel.WEAK),
    ],
    "ospf_2way_unexpected": [
        (F_NETWORK_TYPE_MISMATCH, EvidenceLevel.STRONG),
    ],
    "ospf_exstart_stuck": [
        (F_MTU_MISMATCH, EvidenceLevel.STRONG),
        (F_DUPLICATE_ROUTER_ID, EvidenceLevel.WEAK),
    ],
    "ospf_no_routes": [
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.WEAK),
        (F_AREA_MISMATCH, EvidenceLevel.WEAK),
    ],
    "ospf_no_interarea_routes": [
        (F_AREA_MISMATCH, EvidenceLevel.WEAK),
    ],
    "ospf_passive_interface": [
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.WEAK),
    ],

    # --- Cross-device CONFIG signals from the correlator ---
    "area_mismatch_link": [
        (F_AREA_MISMATCH, EvidenceLevel.CONFIG),
    ],
    "timer_mismatch_link": [
        (F_TIMER_MISMATCH, EvidenceLevel.CONFIG),
    ],
    "network_type_mismatch_link": [
        (F_NETWORK_TYPE_MISMATCH, EvidenceLevel.CONFIG),
    ],
    "mtu_mismatch_link": [
        (F_MTU_MISMATCH, EvidenceLevel.CONFIG),
    ],

    # --- ACL signals ---
    "acl_blocks_ospf": [
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.STRONG),
    ],
    "acl_applied_inbound": [
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.WEAK),
    ],
    "acl_applied_outbound": [
        (F_ACL_WRONG_DIRECTION, EvidenceLevel.STRONG),
    ],
    "acl_blocks_ospf_confirmed": [
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.CONFIG),
    ],
    "acl_wrong_direction_confirmed": [
        (F_ACL_WRONG_DIRECTION, EvidenceLevel.CONFIG),
    ],
    "acl_deny_with_hits": [
        (F_ACL_WRONG_DIRECTION, EvidenceLevel.WEAK),
    ],

    # --- DHCP signals ---
    # NOTE: 'dhcp_helper_missing' from a single 'show ip interface' is only WEAK on
    # its own - lots of router interfaces legitimately have no helper-address. It
    # only confirms a fault when combined with empty DHCP bindings or a no-address
    # client (handled by COMBINATION_UPGRADES and the correlator's 'dhcp_relay_broken').
    "dhcp_helper_missing": [
        (F_DHCP_HELPER_MISSING, EvidenceLevel.WEAK),
    ],
    "dhcp_no_bindings": [
        (F_DHCP_HELPER_MISSING, EvidenceLevel.STRONG),
        (F_DHCP_SERVER_UNREACHABLE, EvidenceLevel.WEAK),
    ],
    "dhcp_client_no_address": [
        (F_DHCP_HELPER_MISSING, EvidenceLevel.STRONG),
        (F_DHCP_SERVER_UNREACHABLE, EvidenceLevel.WEAK),
    ],
    "dhcp_client_no_reply": [
        (F_DHCP_HELPER_MISSING, EvidenceLevel.STRONG),
        (F_DHCP_SERVER_UNREACHABLE, EvidenceLevel.STRONG),
    ],
    "dhcp_relay_broken": [
        (F_DHCP_HELPER_MISSING, EvidenceLevel.CONFIG),
    ],

    # --- STP / VLAN signals ---
    "native_vlan_mismatch_trunk": [
        (F_NATIVE_VLAN_MISMATCH, EvidenceLevel.CONFIG),
    ],
    # Allowed-VLAN list disagreement between two switches' trunks. We cannot
    # prove the two trunks face each other from the parsed facts alone, so
    # the contribution is STRONG (operator should verify the adjacency).
    "trunk_allowed_vlan_mismatch": [
        (F_NATIVE_VLAN_MISMATCH, EvidenceLevel.STRONG),
    ],
    "stp_port_blocking": [
        (F_NATIVE_VLAN_MISMATCH, EvidenceLevel.WEAK),
        (F_STP_WRONG_ROOT, EvidenceLevel.WEAK),
    ],
    "stp_not_root": [
        (F_STP_WRONG_ROOT, EvidenceLevel.WEAK),
    ],
    "stp_unintended_root": [
        (F_STP_WRONG_ROOT, EvidenceLevel.STRONG),
    ],

    # --- Syslog signals ---
    # CDP reports both ends' native VLANs in the same log line, so this is a
    # CONFIG-quality cross-device conflict on its own (not just STRONG).
    "syslog_native_vlan_mismatch": [
        (F_NATIVE_VLAN_MISMATCH, EvidenceLevel.CONFIG),
    ],
    "syslog_spantree_pvst_bpdu": [
        (F_NATIVE_VLAN_MISMATCH, EvidenceLevel.STRONG),
    ],
    "syslog_stp_topology_change": [
        (F_STP_WRONG_ROOT, EvidenceLevel.STRONG),
        (F_NATIVE_VLAN_MISMATCH, EvidenceLevel.WEAK),
    ],
    "syslog_stp_root_change": [
        (F_STP_WRONG_ROOT, EvidenceLevel.STRONG),
    ],
    # A %SEC-IPACCESSLOG entry proves "an ACL is dropping packets" but it does NOT
    # prove the ACL direction is wrong - both the OSPF-blocked and wrong-direction
    # cases would log this. Map only to F_HELLOS_BLOCKED_ACL; F_ACL_WRONG_DIRECTION
    # gets its own evidence path via 'acl_applied_outbound' + 'acl_deny_with_hits'.
    "syslog_acl_deny": [
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.STRONG),
    ],
    "syslog_ospf_mismatch": [
        (F_AREA_MISMATCH, EvidenceLevel.STRONG),
        (F_TIMER_MISMATCH, EvidenceLevel.STRONG),
        (F_MTU_MISMATCH, EvidenceLevel.STRONG),
    ],
    "syslog_ospf_adjacency_down": [
        (F_AREA_MISMATCH, EvidenceLevel.WEAK),
        (F_TIMER_MISMATCH, EvidenceLevel.WEAK),
        (F_HELLOS_BLOCKED_ACL, EvidenceLevel.WEAK),
    ],
    "syslog_dhcp_no_reply": [
        (F_DHCP_HELPER_MISSING, EvidenceLevel.STRONG),
        (F_DHCP_SERVER_UNREACHABLE, EvidenceLevel.STRONG),
    ],
    "syslog_dns_failure": [
        (F_DNS_FAILURE, EvidenceLevel.STRONG),
    ],

    # --- DNS / endpoint ---
    "dns_failure_isolated": [
        (F_DNS_FAILURE, EvidenceLevel.CONFIG),
    ],
    "dns_query_failed": [
        # On its own, only STRONG: the DNS lookup failed but we don't yet know whether
        # the underlying L3 is healthy (the correlator promotes to CONFIG when it is).
        (F_DNS_FAILURE, EvidenceLevel.STRONG),
    ],
    "endpoint_unreachable": [
        # Pure connectivity failure; only weakly contributes to any candidate.
    ],
}
