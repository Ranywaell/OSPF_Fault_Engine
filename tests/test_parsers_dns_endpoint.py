"""Unit tests for DNS / endpoint / syslog parsers."""

from __future__ import annotations

from ospf_engine.models import EvidenceLevel
from ospf_engine.parsers import dns, endpoint, syslog


def _tags(evidence) -> set[str]:
    return {e.tag for e in evidence}


def test_endpoint_no_dhcp_address():
    text = """\
PC1> ipconfig
IP Address. . . . . : 0.0.0.0
Subnet Mask . . . . : 0.0.0.0
"""
    ev, _facts = endpoint.parse(text, source="x", device="PC1")
    assert "dhcp_client_no_address" in _tags(ev)


def test_endpoint_request_timed_out_is_weak():
    text = "Request timed out.\n"
    ev, _facts = endpoint.parse(text, source="x", device="PC1")
    assert "endpoint_unreachable" in _tags(ev)
    assert all(e.level == EvidenceLevel.WEAK for e in ev)


def test_dns_isolated_failure_emits_config():
    text = """\
PC1> ping 192.168.4.20
Reply from 192.168.4.20: bytes=32 time=2ms
PC1> nslookup web.lab.local
Server: 192.168.4.10
*** 192.168.4.10 can't find web.lab.local: Server failed
"""
    ev, facts = dns.parse(text, source="x", device="PC1")
    assert "dns_failure_isolated" in _tags(ev)
    assert any(
        e.level == EvidenceLevel.CONFIG and e.tag == "dns_failure_isolated" for e in ev
    )
    assert facts.dns_results
    assert facts.dns_results[0].resolved is False
    assert facts.dns_results[0].server_reachable is True


def test_dns_query_failed_emits_strong_when_no_l3_in_same_file():
    """Without ping-by-IP success in the same file the parser only emits STRONG;
    cross-file CONFIG promotion is the correlator's job."""
    text = """\
PC1> nslookup web.lab.local
*** Request to server timed out
"""
    ev, facts = dns.parse(text, source="x", device="PC1")
    assert "dns_query_failed" in _tags(ev)
    assert any(e.level == EvidenceLevel.STRONG for e in ev if e.tag == "dns_query_failed")
    assert facts.dns_results
    assert facts.dns_results[0].server_reachable is False


def test_syslog_native_vlan_mismatch_strong():
    text = (
        "*Mar  1 00:02:11.500: %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch "
        "discovered on FastEthernet0/1 (1), with SW2 FastEthernet0/1 (10)."
    )
    ev, _facts = syslog.parse(text, source="x", device="SW1")
    assert "syslog_native_vlan_mismatch" in _tags(ev)


def test_syslog_ospf_mtu_mismatched_hello_parameters():
    text = (
        "*Mar  1 00:05:10.111: %OSPF-4-ERRRCV: Received invalid packet: "
        "Mismatched hello parameters from 10.0.3.2 (ID 4.4.4.4)"
    )
    ev, _facts = syslog.parse(text, source="x", device="R3")
    assert "syslog_ospf_mismatch" in _tags(ev)


def test_syslog_adjchg_down_only_weak():
    """An ADJCHG to DOWN is a consequence, not a cause - must be WEAK."""
    text = (
        "*Mar  1 00:01:04.123: %OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 on "
        "GigabitEthernet0/0 from FULL to DOWN, Neighbor Down: Dead timer expired"
    )
    ev, _facts = syslog.parse(text, source="x", device="R1")
    assert any(
        e.tag == "syslog_ospf_adjacency_down" and e.level == EvidenceLevel.WEAK for e in ev
    )
