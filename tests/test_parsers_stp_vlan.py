"""Unit tests for STP / trunk parsers."""

from __future__ import annotations

from ospf_engine.parsers import interfaces_trunk, spanning_tree


def _tags(evidence) -> set[str]:
    return {e.tag for e in evidence}


def test_trunk_native_vlan_extraction():
    text = """\
Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      1
Fa0/2       on           802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1-1005
Fa0/2       1-1005
"""
    ev, facts = interfaces_trunk.parse(text, source="x", device="SW1")
    # Per-router parser must emit no evidence (correlator does cross-device work).
    assert ev == []
    assert len(facts.trunks) == 2
    assert all(t.native_vlan == 1 for t in facts.trunks)


def test_trunk_does_not_emit_vlan_allowed_noise():
    """The legacy parser emitted WEAK vlan_allowed_list on every header line.
    The new one must be silent so noise doesn't leak into reasoning."""
    text = """\
Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      10
"""
    ev, _facts = interfaces_trunk.parse(text, source="x", device="SW2")
    assert "vlan_allowed_list" not in _tags(ev)


def test_stp_priorities_equal_means_this_bridge_is_root():
    """When Root priority == Bridge priority, the local bridge IS root.
    The legacy parser falsely emitted stp_unexpected_root in this case."""
    text = """\
VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    32769
             Address     0090.2B6A.AAAA

  Bridge ID  Priority    32769
             Address     0090.2B6A.AAAA

Interface        Role Sts Cost      Prio.Nbr Type
Fa0/1            Desg FWD 19        128.1    P2p
"""
    ev, facts = spanning_tree.parse(text, source="x", device="SW1")
    assert "stp_not_root" not in _tags(ev)
    assert facts.stp_vlans[0].is_root is True


def test_stp_blocking_port_emits_strong():
    text = """\
VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    0
             Address     00FF.AAAA.AAAA

  Bridge ID  Priority    32769
             Address     0090.2B6A.BBBB

Interface        Role Sts Cost      Prio.Nbr Type
Fa0/1            Root FWD 19        128.1    P2p
Fa0/2            Desg BLK 19        128.2    P2p
"""
    ev, facts = spanning_tree.parse(text, source="x", device="SW1")
    assert "stp_port_blocking" in _tags(ev)
    assert "stp_not_root" in _tags(ev)
    assert facts.stp_vlans[0].is_root is False
    assert "Fa0/2" in facts.stp_vlans[0].blocked_ports


def test_stp_low_root_priority_with_blocking_is_a_signal():
    """SW1 sees root priority 0 but is itself priority 32769 - someone forced root."""
    text = """\
VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    0
             Address     0090.2B6A.AAAA
  Bridge ID  Priority    32769
             Address     00D0.BC45.BBBB
Interface        Role Sts Cost      Prio.Nbr Type
Fa0/1            Root FWD 19        128.1    P2p
"""
    _ev, facts = spanning_tree.parse(text, source="x", device="SW1")
    assert facts.stp_vlans[0].root_priority == 0
    assert facts.stp_vlans[0].bridge_priority == 32769
    assert facts.stp_vlans[0].is_root is False
