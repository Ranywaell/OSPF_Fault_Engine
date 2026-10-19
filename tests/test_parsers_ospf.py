"""Unit tests for OSPF parsers."""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel
from ospf_engine.parsers import ospf_interface, ospf_neighbor


def _tags(evidence) -> set[str]:
    return {e.tag for e in evidence}


def test_ospf_neighbor_empty_table_emits_no_neighbor():
    text = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface

"""
    ev, facts = ospf_neighbor.parse(text, source="R1_ospf_neighbor.txt", device="R1")
    assert "ospf_no_neighbor" in _tags(ev)
    assert facts.neighbors == []


def test_ospf_neighbor_full_state_emits_no_evidence():
    text = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2          1   FULL/DR         00:00:35    10.0.1.2        GigabitEthernet0/0
"""
    ev, facts = ospf_neighbor.parse(text, source="R1_ospf_neighbor.txt", device="R1")
    assert ev == []
    assert len(facts.neighbors) == 1
    assert facts.neighbors[0].state.upper().startswith("FULL")


def test_ospf_neighbor_init_state_emits_weak_adjacency_failure():
    text = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2          1   INIT            00:00:30    10.0.1.2        GigabitEthernet0/0
"""
    ev, _facts = ospf_neighbor.parse(text, source="x", device="R1")
    assert "ospf_adjacency_failure" in _tags(ev)
    assert all(e.level == EvidenceLevel.WEAK for e in ev if e.tag == "ospf_adjacency_failure")


def test_ospf_neighbor_exstart_emits_strong():
    text = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface
4.4.4.4          1   EXSTART/DR      00:00:35    10.0.3.2        GigabitEthernet0/1
"""
    ev, _facts = ospf_neighbor.parse(text, source="x", device="R3")
    tags = {(e.tag, e.level) for e in ev}
    assert ("ospf_exstart_stuck", EvidenceLevel.STRONG) in tags


def test_ospf_interface_extracts_subnet_area_and_timers():
    text = """\
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
"""
    _ev, facts = ospf_interface.parse(text, source="x", device="R1")
    assert len(facts.interfaces) == 1
    iface = facts.interfaces[0]
    assert iface.device == "R1"
    assert iface.ifname == "GigabitEthernet0/0"
    assert iface.ip == "10.0.1.1"
    assert iface.prefix_len == 30
    assert iface.area == "0"
    assert iface.hello == 10
    assert iface.dead == 40
    assert iface.network_type == "BROADCAST"
    assert iface.subnet == "10.0.1.0/30"


def test_ospf_interface_does_not_emit_per_router_area_mismatch():
    """Critical: the parser must NOT flag a legitimate ABR with multiple areas."""
    text = """\
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
GigabitEthernet0/1 is up, line protocol is up
  Internet Address 192.168.1.1/24, Area 1
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
"""
    ev, facts = ospf_interface.parse(text, source="x", device="R1")
    # No CONFIG-level area_mismatch on a single-router, multi-area parse.
    assert all(e.tag != "area_mismatch" for e in ev)
    assert all(e.tag != "area_mismatch_link" for e in ev)
    # But facts should record both interfaces.
    assert len(facts.interfaces) == 2
    assert {i.area for i in facts.interfaces} == {"0", "1"}


def test_ospf_interface_passive_emits_weak():
    text = """\
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  This is a passive interface
"""
    ev, _facts = ospf_interface.parse(text, source="x", device="R1")
    assert "ospf_passive_interface" in _tags(ev)
