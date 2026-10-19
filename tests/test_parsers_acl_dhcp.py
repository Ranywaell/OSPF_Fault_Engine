"""Unit tests for ACL, ip-interface, DHCP parsers."""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel
from ospf_engine.parsers import access_lists, dhcp, ip_interface


def _tags(evidence) -> set[str]:
    return {e.tag for e in evidence}


def test_acl_deny_ospf_multicast_emits_strong():
    text = """\
Extended IP access list BLOCK_OSPF
    10 deny ospf any host 224.0.0.5 (342 matches)
    20 deny ospf any host 224.0.0.6 (128 matches)
    30 permit ip any any (1204 matches)
"""
    ev, facts = access_lists.parse(text, source="x", device="R1")
    assert any(e.tag == "acl_blocks_ospf" and e.level == EvidenceLevel.STRONG for e in ev)
    assert len(facts.acls) == 1
    assert facts.acls[0].name == "BLOCK_OSPF"
    assert facts.acls[0].has_deny_ospf_multicast is True


def test_acl_deny_with_hits_emits_weak():
    text = """\
Extended IP access list MAYBE_WRONG
    10 permit tcp 192.168.1.0 0.0.0.255 any eq 80 (0 matches)
    20 deny ip any any (892 matches)
"""
    ev, facts = access_lists.parse(text, source="x", device="R1")
    assert "acl_deny_with_hits" in _tags(ev)
    assert facts.acls[0].has_deny_with_hits is True


def test_acl_zero_hits_emits_no_evidence_beyond_hits():
    text = """\
Extended IP access list CLEAN
    10 permit tcp any any (0 matches)
    20 deny ip any any (0 matches)
"""
    ev, _facts = access_lists.parse(text, source="x", device="R1")
    assert "acl_blocks_ospf" not in _tags(ev)
    assert "acl_deny_with_hits" not in _tags(ev)


def test_ip_interface_inbound_acl_recorded():
    text = """\
GigabitEthernet0/0 is up, line protocol is up
  Internet address is 10.0.1.1/30
  MTU is 1500
  Helper address is not set
  Outgoing access list is not set
  Inbound  access list is BLOCK_OSPF
"""
    ev, facts = ip_interface.parse(text, source="x", device="R1")
    assert "acl_applied_inbound" in _tags(ev)
    assert "dhcp_helper_missing" in _tags(ev)
    assert any(
        a.acl_name == "BLOCK_OSPF" and a.direction == "in" for a in facts.acl_applications
    )
    assert any(h.helper_ip is None for h in facts.helper_addresses)


def test_ip_interface_outbound_acl_recorded():
    text = """\
GigabitEthernet0/1 is up, line protocol is up
  Internet address is 192.168.1.1/24
  MTU is 1500
  Helper address is not set
  Outgoing access list is WRONG_DIR
  Inbound  access list is not set
"""
    ev, facts = ip_interface.parse(text, source="x", device="R1")
    assert "acl_applied_outbound" in _tags(ev)
    assert any(
        a.acl_name == "WRONG_DIR" and a.direction == "out" for a in facts.acl_applications
    )


def test_ip_interface_helper_set_recorded_silently():
    text = """\
GigabitEthernet0/1 is up, line protocol is up
  Internet address is 192.168.1.1/24
  MTU is 1500
  Helper address is 192.168.4.10
  Outgoing access list is not set
  Inbound  access list is not set
"""
    ev, facts = ip_interface.parse(text, source="x", device="R1")
    # No 'missing helper' evidence should be raised.
    assert "dhcp_helper_missing" not in _tags(ev)
    assert any(h.helper_ip == "192.168.4.10" for h in facts.helper_addresses)


def test_dhcp_binding_empty_emits_strong():
    text = """\
Bindings from all pools not associated with VRF:
IP address       Client-ID/              Lease expiration        Type
                 Hardware address

"""
    ev, facts = dhcp.parse(text, source="x", device="R1")
    assert "dhcp_no_bindings" in _tags(ev)
    assert all(b.has_bindings is False for b in facts.dhcp_bindings)


def test_dhcp_binding_with_entries_does_not_emit_no_bindings():
    text = """\
Bindings from all pools not associated with VRF:
IP address       Client-ID/              Lease expiration        Type
                 Hardware address
192.168.1.50     0100.D0AB.1234          Mar 02 2026 10:00 AM    Automatic
"""
    ev, facts = dhcp.parse(text, source="x", device="R1")
    assert "dhcp_no_bindings" not in _tags(ev)
    assert facts.dhcp_bindings[0].has_bindings is True
