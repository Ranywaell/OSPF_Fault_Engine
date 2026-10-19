"""Tests for the parser dispatcher: filename routing, content sniffing,
combined-output handling."""

from __future__ import annotations

from ospf_engine.parsers import parse_file, parse_files


def test_dispatch_by_filename_routes_to_ospf_neighbor():
    content = """\
Neighbor ID     Pri   State           Dead Time   Address         Interface

"""
    ev, facts = parse_file("R1_ospf_neighbor.txt", content)
    tags = {e.tag for e in ev}
    assert "ospf_no_neighbor" in tags


def test_dispatch_by_content_when_filename_uninformative():
    content = """\
Extended IP access list BLOCK_OSPF
    10 deny ospf any host 224.0.0.5 (10 matches)
    20 permit ip any any
"""
    ev, _facts = parse_file("dump.txt", content)
    tags = {e.tag for e in ev}
    assert "acl_blocks_ospf" in tags


def test_combined_output_is_split_and_routed():
    """A single file with multiple sections must be parsed by section."""
    content = """\
R1#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
R1#

R1#show access-lists
Extended IP access list BLOCK_OSPF
    10 deny ospf any host 224.0.0.5 (10 matches)
    20 permit ip any any
R1#
"""
    ev, facts = parse_file("R1_combined.txt", content)
    tags = {e.tag for e in ev}
    assert "acl_blocks_ospf" in tags
    assert any(i.area == "0" for i in facts.interfaces)


def test_parse_files_aggregates_evidence_across_files():
    files = {
        "R1_ospf_interface.txt": """\
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
""",
        "R2_ospf_interface.txt": """\
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.2/30, Area 1
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
""",
    }
    pr = parse_files(files)
    assert len(pr.facts.interfaces) == 2
    devices = {i.device for i in pr.facts.interfaces}
    assert devices == {"R1", "R2"}
