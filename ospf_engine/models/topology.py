"""Structured topology facts extracted by parsers.

The parsers produce *both* ``Evidence`` (operator-readable observations) and
these typed facts. The cross-device correlator then joins facts on subnet,
link, and trunk to detect mismatches that no single-router parser can see.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class ParsedInterface:
    """One OSPF-enabled interface as seen on a single device."""

    device: str
    ifname: str
    ip: str | None = None
    prefix_len: int | None = None
    area: str | None = None
    hello: int | None = None
    dead: int | None = None
    network_type: str | None = None
    mtu: int | None = None
    state: str | None = None
    process_id: str | None = None
    router_id: str | None = None
    passive: bool = False

    @property
    def subnet(self) -> str | None:
        """Return the canonical subnet (e.g. '10.0.1.0/30') for link correlation."""
        if not self.ip or self.prefix_len is None:
            return None
        try:
            net = ipaddress.ip_network(f"{self.ip}/{self.prefix_len}", strict=False)
        except ValueError:
            return None
        return str(net)


@dataclass(slots=True)
class ParsedNeighbor:
    device: str
    neighbor_id: str
    state: str
    interface: str
    address: str | None = None


@dataclass(slots=True)
class ParsedAcl:
    """A parsed ACL definition."""

    device: str
    name: str
    rules: list[str] = field(default_factory=list)
    has_deny_ospf: bool = False
    has_deny_ospf_multicast: bool = False
    has_deny_with_hits: bool = False


@dataclass(slots=True)
class ParsedAclApplication:
    """Where an ACL is applied (interface + direction)."""

    device: str
    interface: str
    acl_name: str
    direction: str  # 'in' or 'out'


@dataclass(slots=True)
class ParsedHelperAddress:
    device: str
    interface: str
    helper_ip: str | None  # None means 'not set'


@dataclass(slots=True)
class ParsedTrunk:
    """One trunk port observation."""

    device: str
    port: str
    encapsulation: str | None = None
    status: str | None = None
    native_vlan: int | None = None
    allowed_vlans: str | None = None


@dataclass(slots=True)
class ParsedStpVlan:
    """STP info for one VLAN on one switch."""

    device: str
    vlan: int
    is_root: bool
    root_priority: int | None = None
    bridge_priority: int | None = None
    blocked_ports: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedDhcpBinding:
    device: str
    has_bindings: bool


@dataclass(slots=True)
class ParsedDnsResult:
    """Result of an `nslookup` / `host` from an endpoint."""

    source: str
    host: str | None
    resolved: bool
    server_reachable: bool


@dataclass(slots=True)
class TopologyFacts:
    """Aggregated structured facts across all parsed files. Consumed by the correlator."""

    interfaces: list[ParsedInterface] = field(default_factory=list)
    neighbors: list[ParsedNeighbor] = field(default_factory=list)
    acls: list[ParsedAcl] = field(default_factory=list)
    acl_applications: list[ParsedAclApplication] = field(default_factory=list)
    helper_addresses: list[ParsedHelperAddress] = field(default_factory=list)
    trunks: list[ParsedTrunk] = field(default_factory=list)
    stp_vlans: list[ParsedStpVlan] = field(default_factory=list)
    dhcp_bindings: list[ParsedDhcpBinding] = field(default_factory=list)
    dns_results: list[ParsedDnsResult] = field(default_factory=list)
    endpoint_ping_ok: list[str] = field(default_factory=list)
    """Devices observed to have at least one successful ping by IP."""

    def merge(self, other: "TopologyFacts") -> "TopologyFacts":
        return TopologyFacts(
            interfaces=self.interfaces + other.interfaces,
            neighbors=self.neighbors + other.neighbors,
            acls=self.acls + other.acls,
            acl_applications=self.acl_applications + other.acl_applications,
            helper_addresses=self.helper_addresses + other.helper_addresses,
            trunks=self.trunks + other.trunks,
            stp_vlans=self.stp_vlans + other.stp_vlans,
            dhcp_bindings=self.dhcp_bindings + other.dhcp_bindings,
            dns_results=self.dns_results + other.dns_results,
            endpoint_ping_ok=self.endpoint_ping_ok + other.endpoint_ping_ok,
        )
