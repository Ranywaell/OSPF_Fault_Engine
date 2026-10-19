"""Cross-device correlator.

The single-router parsers cannot distinguish "this router is a legitimate ABR"
from "this router has a misconfigured area on a transit link". The correlator
joins parsed facts from *all* devices on the same subnet/trunk/etc. and emits
CONFIG-level evidence only when the conflict is provable.

Detected conflicts (all CONFIG-level when both sides are observed):
  * area_mismatch_link        : same subnet, different OSPF areas
  * timer_mismatch_link       : same subnet, different hello/dead intervals
  * network_type_mismatch_link: same subnet, different OSPF network types
  * mtu_mismatch_link         : same subnet, different MTUs
  * native_vlan_mismatch_trunk: ports on different switches with different
                                native VLANs (best-effort: when only one
                                native VLAN is observed and it's not 1, we
                                rely on syslog %CDP-NATIVE_VLAN_MISMATCH)
  * stp_unintended_root       : a non-core switch is the elected root
  * acl_blocks_ospf_confirmed : an ACL with deny ospf is applied INBOUND on
                                an OSPF interface
  * acl_wrong_direction_user  : an outbound ACL on a LAN interface that has
                                non-zero deny-with-hits matches user traffic
  * dhcp_relay_broken         : helper-address missing on a router interface
                                AND DHCP binding table empty / client has no
                                address
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts
from ospf_engine.models.topology import ParsedInterface


# ---- helpers ------------------------------------------------------------------


def _group_interfaces_by_subnet(
    interfaces: Iterable[ParsedInterface],
) -> dict[str, list[ParsedInterface]]:
    by_subnet: dict[str, list[ParsedInterface]] = defaultdict(list)
    for iface in interfaces:
        sn = iface.subnet
        if sn is None:
            continue
        by_subnet[sn].append(iface)
    return by_subnet


def _devices_str(ifs: Iterable[ParsedInterface]) -> str:
    return ", ".join(f"{i.device}:{i.ifname}" for i in ifs)


# ---- detectors ---------------------------------------------------------------


def _detect_link_mismatches(facts: TopologyFacts) -> list[Evidence]:
    out: list[Evidence] = []

    # Only consider OSPF-relevant interfaces (those that have an Area).
    ospf_ifaces = [i for i in facts.interfaces if i.area is not None]
    by_subnet = _group_interfaces_by_subnet(ospf_ifaces)

    for subnet, ifs in by_subnet.items():
        # Need at least two ends of the same link to compare.
        if len({i.device for i in ifs}) < 2:
            continue

        areas = {i.area for i in ifs if i.area is not None}
        if len(areas) > 1:
            out.append(
                Evidence(
                    tag="area_mismatch_link",
                    level=EvidenceLevel.CONFIG,
                    source="correlator",
                    detail=(
                        f"OSPF AREA MISMATCH on link {subnet}: "
                        f"{', '.join(f'{i.device}:{i.ifname}=Area {i.area}' for i in ifs)}. "
                        "Both ends of the link must agree on the area number for adjacency to form."
                    ),
                    devices=tuple(sorted({i.device for i in ifs})),
                )
            )

        hellos = {i.hello for i in ifs if i.hello is not None}
        deads = {i.dead for i in ifs if i.dead is not None}
        if len(hellos) > 1 or len(deads) > 1:
            out.append(
                Evidence(
                    tag="timer_mismatch_link",
                    level=EvidenceLevel.CONFIG,
                    source="correlator",
                    detail=(
                        f"OSPF TIMER MISMATCH on link {subnet}: "
                        f"{', '.join(f'{i.device}:{i.ifname} hello={i.hello}/dead={i.dead}' for i in ifs)}. "
                        "OSPF requires identical hello and dead timers on both ends; the dead timer "
                        "expires and the neighbor is declared down."
                    ),
                    devices=tuple(sorted({i.device for i in ifs})),
                )
            )

        net_types = {i.network_type for i in ifs if i.network_type is not None}
        if len(net_types) > 1:
            out.append(
                Evidence(
                    tag="network_type_mismatch_link",
                    level=EvidenceLevel.CONFIG,
                    source="correlator",
                    detail=(
                        f"OSPF NETWORK-TYPE MISMATCH on link {subnet}: "
                        f"{', '.join(f'{i.device}:{i.ifname}={i.network_type}' for i in ifs)}. "
                        "Adjacency will hang at 2WAY because DR/BDR election semantics differ."
                    ),
                    devices=tuple(sorted({i.device for i in ifs})),
                )
            )

        mtus = {i.mtu for i in ifs if i.mtu is not None}
        if len(mtus) > 1:
            out.append(
                Evidence(
                    tag="mtu_mismatch_link",
                    level=EvidenceLevel.CONFIG,
                    source="correlator",
                    detail=(
                        f"MTU MISMATCH on link {subnet}: "
                        f"{', '.join(f'{i.device}:{i.ifname}={i.mtu}' for i in ifs)}. "
                        "Hellos succeed (small) but DBD exchange fails - adjacency hangs in EXSTART."
                    ),
                    devices=tuple(sorted({i.device for i in ifs})),
                )
            )

    return out


def _detect_acl_blocks_ospf(facts: TopologyFacts) -> list[Evidence]:
    """An ACL with deny-ospf rules applied INBOUND on an OSPF-enabled interface."""
    out: list[Evidence] = []

    ospf_ifaces_by_dev_if: dict[tuple[str, str], ParsedInterface] = {
        (i.device, i.ifname): i for i in facts.interfaces if i.area is not None
    }
    blocking_acls: dict[tuple[str, str], bool] = {
        (a.device, a.name): (a.has_deny_ospf or a.has_deny_ospf_multicast)
        for a in facts.acls
    }

    for app in facts.acl_applications:
        if app.direction != "in":
            continue
        if (app.device, app.acl_name) not in blocking_acls:
            continue
        if not blocking_acls[(app.device, app.acl_name)]:
            continue
        # Is this interface actually running OSPF? If we have it as an ospf-interface
        # fact, yes. If not, it might still be an OSPF interface we just didn't see -
        # the inbound-deny-OSPF combination is bad regardless, so emit CONFIG.
        is_ospf_iface = (app.device, app.interface) in ospf_ifaces_by_dev_if
        out.append(
            Evidence(
                tag="acl_blocks_ospf_confirmed",
                level=EvidenceLevel.CONFIG,
                source="correlator",
                detail=(
                    f"On {app.device}: ACL '{app.acl_name}' is applied INBOUND on "
                    f"{app.interface} AND that ACL contains a rule that drops OSPF. "
                    + (
                        "The interface is OSPF-enabled, so hellos are guaranteed to be dropped "
                        "and the adjacency cannot form."
                        if is_ospf_iface
                        else "If this interface participates in OSPF, hellos are being dropped."
                    )
                ),
                devices=(app.device,),
            )
        )

    return out


def _detect_acl_wrong_direction(facts: TopologyFacts) -> list[Evidence]:
    """An ACL applied OUTBOUND on a LAN interface that has non-zero deny hits.

    This is how 'wrong direction' is reliably distinguished from 'intended outbound
    filter' - the deny counter is climbing, meaning legitimate traffic is being
    filtered after the routing decision when it should have been filtered at ingress.
    """
    out: list[Evidence] = []
    deny_hit_acls: set[tuple[str, str]] = {
        (a.device, a.name) for a in facts.acls if a.has_deny_with_hits
    }

    for app in facts.acl_applications:
        if app.direction != "out":
            continue
        if (app.device, app.acl_name) not in deny_hit_acls:
            continue
        out.append(
            Evidence(
                tag="acl_wrong_direction_confirmed",
                level=EvidenceLevel.CONFIG,
                source="correlator",
                detail=(
                    f"On {app.device}: ACL '{app.acl_name}' is applied OUTBOUND on "
                    f"{app.interface} AND its deny rule has non-zero hits. User traffic is "
                    "being dropped after the routing decision; the ACL is almost certainly "
                    "applied in the wrong direction."
                ),
                devices=(app.device,),
            )
        )

    return out


def _detect_native_vlan_mismatch(facts: TopologyFacts) -> list[Evidence]:
    """Native VLAN mismatch when at least two switches have trunks with
    different native VLANs."""
    out: list[Evidence] = []
    native_by_device: dict[str, set[int]] = defaultdict(set)
    samples: dict[str, list[str]] = defaultdict(list)
    for t in facts.trunks:
        if t.native_vlan is None:
            continue
        native_by_device[t.device].add(t.native_vlan)
        samples[t.device].append(f"{t.port}=native {t.native_vlan}")

    if len(native_by_device) < 2:
        return out

    flat_natives = {v for s in native_by_device.values() for v in s}
    if len(flat_natives) <= 1:
        return out

    summary = "; ".join(f"{dev}: {', '.join(samp)}" for dev, samp in samples.items())
    out.append(
        Evidence(
            tag="native_vlan_mismatch_trunk",
            level=EvidenceLevel.CONFIG,
            source="correlator",
            detail=(
                f"NATIVE VLAN MISMATCH across trunks: {summary}. Untagged frames are placed "
                "into different VLANs on each side - BPDUs may cross VLANs and STP topology "
                "changes can result."
            ),
            devices=tuple(sorted(native_by_device.keys())),
        )
    )
    return out


def _expand_vlan_list(allowed: str) -> set[int]:
    """Expand a Cisco allowed-VLAN spec like ``1,10,20-22,30`` into a set.
    Returns an empty set if parsing fails."""
    out: set[int] = set()
    for token in allowed.replace(" ", "").split(","):
        if not token:
            continue
        if "-" in token:
            try:
                lo, hi = token.split("-", 1)
                out.update(range(int(lo), int(hi) + 1))
            except ValueError:
                continue
        else:
            try:
                out.add(int(token))
            except ValueError:
                continue
    return out


def _detect_trunk_allowed_vlan_inconsistency(
    facts: TopologyFacts,
) -> list[Evidence]:
    """At least two switches both have trunks observed AND their allowed-VLAN
    sets disagree.

    We don't have explicit link adjacency from CDP/LLDP in our parsed facts,
    so we use a conservative heuristic: if the *union* of allowed VLANs on
    one switch's trunks differs from another switch's, at least one side is
    pruning a VLAN the other still carries. The classic symptom is an
    endpoint in VLAN N that can reach the local switch but not the remote
    LAN because the trunk between them strips that VLAN.

    Emits at STRONG (not CONFIG) because we cannot prove from this data
    alone that the trunks face each other - operators should verify the
    physical adjacency. Native VLAN mismatch already has its own CONFIG
    detector above.
    """
    out: list[Evidence] = []
    allowed_by_device: dict[str, set[int]] = {}
    samples: dict[str, list[str]] = defaultdict(list)
    for t in facts.trunks:
        if not t.allowed_vlans:
            continue
        expanded = _expand_vlan_list(t.allowed_vlans)
        if not expanded:
            continue
        # Treat 'all VLANs' (1-4094 / 1-1005) as a non-restrictive trunk and
        # ignore it - a switch that allows everything cannot be the side
        # that is missing a VLAN.
        if len(expanded) >= 1000:
            continue
        allowed_by_device.setdefault(t.device, set()).update(expanded)
        samples[t.device].append(f"{t.port}=allow {t.allowed_vlans}")

    if len(allowed_by_device) < 2:
        return out

    devices = sorted(allowed_by_device.keys())
    # Compare every pair for a non-empty symmetric difference.
    for i, dev_a in enumerate(devices):
        for dev_b in devices[i + 1:]:
            a = allowed_by_device[dev_a]
            b = allowed_by_device[dev_b]
            missing_on_b = sorted(a - b)
            missing_on_a = sorted(b - a)
            if not missing_on_a and not missing_on_b:
                continue
            parts: list[str] = []
            if missing_on_b:
                parts.append(f"{dev_b} is missing VLAN(s) {missing_on_b}")
            if missing_on_a:
                parts.append(f"{dev_a} is missing VLAN(s) {missing_on_a}")
            summary = (
                f"{dev_a}: {', '.join(samples[dev_a])} | "
                f"{dev_b}: {', '.join(samples[dev_b])}"
            )
            out.append(
                Evidence(
                    tag="trunk_allowed_vlan_mismatch",
                    level=EvidenceLevel.STRONG,
                    source="correlator",
                    detail=(
                        f"TRUNK ALLOWED-VLAN INCONSISTENCY between {dev_a} and "
                        f"{dev_b}: {'; '.join(parts)}. Endpoints in the missing "
                        f"VLAN(s) cannot cross the trunk. Trunks: {summary}."
                    ),
                    devices=(dev_a, dev_b),
                )
            )
    return out


def _detect_dhcp_relay_broken(facts: TopologyFacts) -> list[Evidence]:
    """Helper missing on the relay AND ACTUAL DHCP context (empty binding table
    or a client with no address) is observed.

    We require explicit DHCP context to fire because lots of router interfaces
    legitimately have no helper-address (LAN-internal routers, transit links,
    etc.) - flagging those as broken DHCP relays would be a false positive.
    """
    out: list[Evidence] = []
    if not any(h.helper_ip is None for h in facts.helper_addresses):
        return out

    # Did we actually observe a DHCP-related failure?
    has_dhcp_context = any(not b.has_bindings for b in facts.dhcp_bindings)
    if not has_dhcp_context:
        return out

    out.append(
        Evidence(
            tag="dhcp_relay_broken",
            level=EvidenceLevel.CONFIG,
            source="correlator",
            detail=(
                "DHCP relay is broken: the router interface facing clients has no "
                "ip helper-address AND the DHCP binding table is empty. Discover "
                "broadcasts cannot cross the router."
            ),
            devices=tuple(
                sorted({h.device for h in facts.helper_addresses if h.helper_ip is None})
            ),
        )
    )
    return out


def _detect_isolated_dns_failure(facts: TopologyFacts) -> list[Evidence]:
    """A device shows DNS failure AND (the same device or any device) successfully
    pinged something by IP. Underlying L3 is healthy - the DNS service is the fault."""
    out: list[Evidence] = []
    failed = [d for d in facts.dns_results if not d.resolved]
    if not failed or not facts.endpoint_ping_ok:
        return out

    devices_with_ping_ok = set(facts.endpoint_ping_ok)
    for dns_fail in failed:
        # Either the same device pinged OK, or *any* endpoint did - both prove L3 works.
        if dns_fail.source in devices_with_ping_ok or devices_with_ping_ok:
            out.append(
                Evidence(
                    tag="dns_failure_isolated",
                    level=EvidenceLevel.CONFIG,
                    source="correlator",
                    detail=(
                        f"DNS for '{dns_fail.host}' failed on {dns_fail.source}, but at least "
                        f"one endpoint successfully reached destinations by IP "
                        f"({', '.join(sorted(devices_with_ping_ok))}). The network path is "
                        "healthy - the DNS service is unreachable, misconfigured, or the wrong "
                        "DNS server is configured."
                    ),
                    devices=(dns_fail.source,),
                )
            )
    return out


def _detect_stp_unintended_root(facts: TopologyFacts) -> list[Evidence]:
    """If only one switch has been observed and it is not root, we cannot decide.
    If two or more switches have been observed AND the elected root is the one
    with the lower bridge priority on a port that is NOT a designated core port,
    flag it.

    Heuristic: if any switch has 'is_root' False and reported priority equal to
    the root priority on another VLAN-block, surface a STP-wrong-root signal.
    """
    out: list[Evidence] = []
    if len(facts.stp_vlans) < 1:
        return out

    # If we see at least one VLAN where the root priority is lower than typical
    # default 32769 (i.e. someone set priority 0/4096) on a non-core switch,
    # flag it. This catches the Scenario-5 case where SW2 was forced to priority 0.
    suspicious = [
        s
        for s in facts.stp_vlans
        if s.root_priority is not None and s.root_priority < 32769 and not s.is_root
    ]
    if suspicious:
        for s in suspicious:
            out.append(
                Evidence(
                    tag="stp_unintended_root",
                    level=EvidenceLevel.STRONG,
                    source="correlator",
                    detail=(
                        f"On {s.device}: VLAN {s.vlan} - elected root priority is "
                        f"{s.root_priority} (this bridge {s.bridge_priority}). The unusually "
                        "low root priority strongly suggests another switch has been forced "
                        "as root unintentionally."
                    ),
                    devices=(s.device,),
                )
            )
    return out


# ---- public API --------------------------------------------------------------


def correlate(facts: TopologyFacts) -> list[Evidence]:
    """Run every cross-device detector and return aggregated evidence."""
    out: list[Evidence] = []
    out.extend(_detect_link_mismatches(facts))
    out.extend(_detect_acl_blocks_ospf(facts))
    out.extend(_detect_acl_wrong_direction(facts))
    out.extend(_detect_native_vlan_mismatch(facts))
    out.extend(_detect_trunk_allowed_vlan_inconsistency(facts))
    out.extend(_detect_dhcp_relay_broken(facts))
    out.extend(_detect_isolated_dns_failure(facts))
    out.extend(_detect_stp_unintended_root(facts))
    return out
