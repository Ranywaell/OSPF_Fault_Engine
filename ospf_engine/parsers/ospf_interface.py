"""Parser for ``show ip ospf interface``.

This parser produces *structured* :class:`ParsedInterface` facts so the
cross-device correlator can compare both ends of every link. It deliberately
does **not** emit per-router 'multiple areas' or 'multiple hellos' evidence -
that is a job for the correlator, which has visibility into the peer.
"""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, ParsedInterface, TopologyFacts
from ospf_engine.utils.text import safe_int

_BLOCK_HEADER_RE = re.compile(
    r"^(?P<ifname>\S+)\s+is\s+(?P<state>up|down|administratively\s+down).*?(?:line\s+protocol\s+is\s+(?P<lp>up|down))?",
    re.IGNORECASE,
)
_ADDR_AREA_RE = re.compile(
    r"Internet\s+Address\s+(?P<ip>\d+\.\d+\.\d+\.\d+)/(?P<plen>\d+),\s*Area\s+(?P<area>[\w\.]+)",
    re.IGNORECASE,
)
_PROCESS_RE = re.compile(
    r"Process\s+ID\s+(?P<pid>[\w\.\-]+),\s*Router\s+ID\s+(?P<rid>[\d\.]+),\s*"
    r"Network\s+Type\s+(?P<nt>[A-Z\-_]+)",
    re.IGNORECASE,
)
_TIMER_RE = re.compile(
    r"Hello\s+(?P<hello>\d+),\s*Dead\s+(?P<dead>\d+)", re.IGNORECASE
)
_MTU_RE = re.compile(r"\bMTU\s+(?P<mtu>\d+)\b", re.IGNORECASE)
_PASSIVE_RE = re.compile(r"passive\s+interface", re.IGNORECASE)
_STATE_RE = re.compile(r"State\s+(?P<state>[A-Z]+)", re.IGNORECASE)


def _split_blocks(text: str) -> list[str]:
    """Split the output into one block per interface."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _BLOCK_HEADER_RE.match(line.strip()):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks if any(line.strip() for line in b)]


def _parse_block(block: str, device: str) -> ParsedInterface | None:
    header_m = _BLOCK_HEADER_RE.match(block.strip())
    if not header_m:
        return None
    ifname = header_m.group("ifname")

    addr_m = _ADDR_AREA_RE.search(block)
    proc_m = _PROCESS_RE.search(block)
    timer_m = _TIMER_RE.search(block)
    mtu_m = _MTU_RE.search(block)
    state_m = _STATE_RE.search(block)
    passive = bool(_PASSIVE_RE.search(block))

    return ParsedInterface(
        device=device,
        ifname=ifname,
        ip=addr_m.group("ip") if addr_m else None,
        prefix_len=safe_int(addr_m.group("plen")) if addr_m else None,
        area=addr_m.group("area") if addr_m else None,
        hello=safe_int(timer_m.group("hello")) if timer_m else None,
        dead=safe_int(timer_m.group("dead")) if timer_m else None,
        network_type=proc_m.group("nt").upper() if proc_m else None,
        mtu=safe_int(mtu_m.group("mtu")) if mtu_m else None,
        state=state_m.group("state") if state_m else None,
        process_id=proc_m.group("pid") if proc_m else None,
        router_id=proc_m.group("rid") if proc_m else None,
        passive=passive,
    )


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    for block in _split_blocks(text):
        parsed = _parse_block(block, device)
        if parsed is None:
            continue
        facts.interfaces.append(parsed)

        if parsed.passive:
            evidence.append(
                Evidence(
                    tag="ospf_passive_interface",
                    level=EvidenceLevel.WEAK,
                    source=source,
                    detail=(
                        f"On {device}: {parsed.ifname} is configured as passive. "
                        "OSPF will not send or process hellos on a passive interface."
                    ),
                    devices=(device,),
                )
            )

    return evidence, facts
