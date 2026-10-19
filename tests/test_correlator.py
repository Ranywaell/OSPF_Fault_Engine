"""Unit tests for the cross-device correlator."""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel, ParsedInterface, ParsedTrunk, TopologyFacts
from ospf_engine.models.topology import (
    ParsedAcl,
    ParsedAclApplication,
    ParsedDhcpBinding,
    ParsedHelperAddress,
    ParsedStpVlan,
)
from ospf_engine.reasoning.correlator import correlate


def _tag_levels(evidence) -> set[tuple[str, EvidenceLevel]]:
    return {(e.tag, e.level) for e in evidence}


def test_area_mismatch_link_detected_when_two_devices_disagree():
    facts = TopologyFacts(
        interfaces=[
            ParsedInterface(
                device="R1", ifname="Gi0/0", ip="10.0.1.1", prefix_len=30, area="0",
                hello=10, dead=40, network_type="BROADCAST",
            ),
            ParsedInterface(
                device="R2", ifname="Gi0/0", ip="10.0.1.2", prefix_len=30, area="1",
                hello=10, dead=40, network_type="BROADCAST",
            ),
        ]
    )
    ev = correlate(facts)
    assert ("area_mismatch_link", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_legitimate_abr_does_not_trigger_area_mismatch():
    """One router with two different areas on two different links is a legitimate ABR."""
    facts = TopologyFacts(
        interfaces=[
            ParsedInterface(
                device="R1", ifname="Gi0/0", ip="10.0.1.1", prefix_len=30, area="0",
                hello=10, dead=40,
            ),
            ParsedInterface(
                device="R1", ifname="Gi0/1", ip="192.168.1.1", prefix_len=24, area="1",
                hello=10, dead=40,
            ),
        ]
    )
    ev = correlate(facts)
    assert all(e.tag != "area_mismatch_link" for e in ev)


def test_timer_mismatch_link_detected():
    facts = TopologyFacts(
        interfaces=[
            ParsedInterface(
                device="R2", ifname="Gi0/1", ip="10.0.2.1", prefix_len=30, area="0",
                hello=10, dead=40,
            ),
            ParsedInterface(
                device="R3", ifname="Gi0/0", ip="10.0.2.2", prefix_len=30, area="0",
                hello=20, dead=80,
            ),
        ]
    )
    ev = correlate(facts)
    assert ("timer_mismatch_link", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_mtu_mismatch_link_detected():
    facts = TopologyFacts(
        interfaces=[
            ParsedInterface(
                device="R3", ifname="Gi0/1", ip="10.0.3.1", prefix_len=30, area="0",
                hello=10, dead=40, mtu=1500,
            ),
            ParsedInterface(
                device="R4", ifname="Gi0/0", ip="10.0.3.2", prefix_len=30, area="0",
                hello=10, dead=40, mtu=1400,
            ),
        ]
    )
    ev = correlate(facts)
    assert ("mtu_mismatch_link", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_acl_blocks_ospf_confirmed_when_inbound_on_ospf_iface():
    facts = TopologyFacts(
        interfaces=[
            ParsedInterface(
                device="R1", ifname="GigabitEthernet0/0",
                ip="10.0.1.1", prefix_len=30, area="0",
                hello=10, dead=40, network_type="BROADCAST",
            ),
        ],
        acls=[
            ParsedAcl(device="R1", name="BLOCK_OSPF", has_deny_ospf_multicast=True),
        ],
        acl_applications=[
            ParsedAclApplication(
                device="R1", interface="GigabitEthernet0/0",
                acl_name="BLOCK_OSPF", direction="in",
            ),
        ],
    )
    ev = correlate(facts)
    assert ("acl_blocks_ospf_confirmed", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_acl_wrong_direction_confirmed_when_outbound_with_hits():
    facts = TopologyFacts(
        acls=[
            ParsedAcl(device="R1", name="WRONG_DIR", has_deny_with_hits=True),
        ],
        acl_applications=[
            ParsedAclApplication(
                device="R1", interface="Gi0/1",
                acl_name="WRONG_DIR", direction="out",
            ),
        ],
    )
    ev = correlate(facts)
    assert ("acl_wrong_direction_confirmed", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_native_vlan_mismatch_across_switches():
    facts = TopologyFacts(
        trunks=[
            ParsedTrunk(device="SW1", port="Fa0/1", native_vlan=1),
            ParsedTrunk(device="SW2", port="Fa0/1", native_vlan=10),
        ]
    )
    ev = correlate(facts)
    assert ("native_vlan_mismatch_trunk", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_dhcp_relay_broken_when_missing_helper_and_no_bindings():
    facts = TopologyFacts(
        helper_addresses=[
            ParsedHelperAddress(device="R1", interface="Gi0/1", helper_ip=None),
        ],
        dhcp_bindings=[ParsedDhcpBinding(device="R1", has_bindings=False)],
    )
    ev = correlate(facts)
    assert ("dhcp_relay_broken", EvidenceLevel.CONFIG) in _tag_levels(ev)


def test_stp_unintended_root_when_low_priority_and_not_root():
    facts = TopologyFacts(
        stp_vlans=[
            ParsedStpVlan(
                device="SW1", vlan=1, is_root=False,
                root_priority=0, bridge_priority=32769,
            ),
        ]
    )
    ev = correlate(facts)
    assert any(e.tag == "stp_unintended_root" for e in ev)
