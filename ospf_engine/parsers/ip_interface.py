"""Parser for ``show ip interface [X]``.

Extracts:
  * inbound / outbound ACL applications  -> ParsedAclApplication
  * ip helper-address                    -> ParsedHelperAddress
  * MTU                                  -> noted on already-parsed interfaces
"""

from __future__ import annotations

import re

from ospf_engine.models import (
    Evidence,
    EvidenceLevel,
    ParsedHelperAddress,
    TopologyFacts,
)
from ospf_engine.models.topology import ParsedAclApplication
from ospf_engine.utils.text import safe_int

_INTERFACE_HEADER_RE = re.compile(
    r"^(?P<ifname>\S+)\s+is\s+\S+,\s+line\s+protocol\s+is\s+\S+", re.IGNORECASE
)
_INBOUND_ACL_RE = re.compile(
    r"Inbound\s+access\s+list\s+is\s+(?P<acl>\S+)", re.IGNORECASE
)
_OUTBOUND_ACL_RE = re.compile(
    r"Outgoing\s+access\s+list\s+is\s+(?P<acl>\S+)", re.IGNORECASE
)
_HELPER_NOT_SET_RE = re.compile(r"Helper\s+address\s+is\s+not\s+set", re.IGNORECASE)
_HELPER_SET_RE = re.compile(
    r"Helper\s+address\s+is\s+(?P<ip>\d+\.\d+\.\d+\.\d+)", re.IGNORECASE
)
_MTU_RE = re.compile(r"\bMTU\s+(?:is\s+)?(?P<mtu>\d+)\b", re.IGNORECASE)


def _split_into_interface_blocks(text: str) -> list[tuple[str, str]]:
    """Yield ``(ifname, block_text)`` for each interface section."""
    blocks: list[tuple[str, str]] = []
    current_name: str | None = None
    current: list[str] = []
    for line in text.splitlines():
        m = _INTERFACE_HEADER_RE.match(line.strip())
        if m:
            if current_name is not None:
                blocks.append((current_name, "\n".join(current)))
            current_name = m.group("ifname")
            current = [line]
        else:
            current.append(line)
    if current_name is not None:
        blocks.append((current_name, "\n".join(current)))
    if not blocks and text.strip():
        # Single-interface output without a clear header - treat the whole thing as one block.
        blocks.append(("UNKNOWN", text))
    return blocks


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    for ifname, block in _split_into_interface_blocks(text):
        in_m = _INBOUND_ACL_RE.search(block)
        if in_m and in_m.group("acl").lower() != "not":
            acl = in_m.group("acl")
            facts.acl_applications.append(
                ParsedAclApplication(
                    device=device, interface=ifname, acl_name=acl, direction="in"
                )
            )
            evidence.append(
                Evidence(
                    tag="acl_applied_inbound",
                    level=EvidenceLevel.CONFIG,
                    source=source,
                    detail=(
                        f"On {device}: ACL '{acl}' is applied INBOUND on {ifname}. "
                        "Cross-checked with 'show access-lists', this can confirm whether "
                        "OSPF or user traffic is being filtered at ingress."
                    ),
                    devices=(device,),
                )
            )

        out_m = _OUTBOUND_ACL_RE.search(block)
        if out_m and out_m.group("acl").lower() != "not":
            acl = out_m.group("acl")
            facts.acl_applications.append(
                ParsedAclApplication(
                    device=device, interface=ifname, acl_name=acl, direction="out"
                )
            )
            evidence.append(
                Evidence(
                    tag="acl_applied_outbound",
                    level=EvidenceLevel.CONFIG,
                    source=source,
                    detail=(
                        f"On {device}: ACL '{acl}' is applied OUTBOUND on {ifname}. "
                        "If the intent was to filter ingress traffic, the direction is wrong."
                    ),
                    devices=(device,),
                )
            )

        if _HELPER_NOT_SET_RE.search(block):
            facts.helper_addresses.append(
                ParsedHelperAddress(device=device, interface=ifname, helper_ip=None)
            )
            evidence.append(
                Evidence(
                    tag="dhcp_helper_missing",
                    level=EvidenceLevel.CONFIG,
                    source=source,
                    detail=(
                        f"On {device}: ip helper-address is NOT set on {ifname}. "
                        "DHCP Discover broadcasts from clients on this subnet cannot be relayed "
                        "to the DHCP server."
                    ),
                    devices=(device,),
                )
            )
        else:
            help_m = _HELPER_SET_RE.search(block)
            if help_m:
                facts.helper_addresses.append(
                    ParsedHelperAddress(
                        device=device, interface=ifname, helper_ip=help_m.group("ip")
                    )
                )

        mtu_m = _MTU_RE.search(block)
        if mtu_m:
            mtu_val = safe_int(mtu_m.group("mtu"))
            # Annotate any already-parsed interface fact with the MTU.
            for iface in facts.interfaces:
                if iface.device == device and iface.ifname == ifname and iface.mtu is None:
                    iface.mtu = mtu_val
            # If the interface wasn't seen by ospf parser, store as a stub fact
            # so the correlator can still detect MTU mismatch on plain interfaces.
            from ospf_engine.models import ParsedInterface

            if not any(
                f.device == device and f.ifname == ifname for f in facts.interfaces
            ):
                facts.interfaces.append(
                    ParsedInterface(device=device, ifname=ifname, mtu=mtu_val)
                )

    return evidence, facts
