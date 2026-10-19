"""Parser for ``show access-lists``.

Produces:
  * :class:`ParsedAcl` per access list with flags ``has_deny_ospf`` and
    ``has_deny_ospf_multicast`` for downstream correlation.
  * STRONG evidence if any ACL contains a rule that would drop OSPF hellos.
  * WEAK evidence if a non-OSPF deny rule has non-zero hits (could be the
    user's traffic being filtered the wrong way - the correlator decides).
"""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, ParsedAcl, TopologyFacts
from ospf_engine.utils.text import iter_nonempty_lines

_HEADER_RE = re.compile(
    r"^(?:Standard|Extended)\s+IP\s+access\s+list\s+(?P<name>\S+)", re.IGNORECASE
)
_DENY_OSPF_RE = re.compile(r"\bdeny\s+ospf\b", re.IGNORECASE)
_DENY_MCAST_RE = re.compile(r"\bdeny\s+.*?\b224\.0\.0\.[56]\b", re.IGNORECASE)
_HIT_COUNT_RE = re.compile(r"\((\d+)\s+matches?\)", re.IGNORECASE)


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()
    current: ParsedAcl | None = None

    for line in iter_nonempty_lines(text):
        header = _HEADER_RE.match(line)
        if header:
            if current is not None:
                facts.acls.append(current)
            current = ParsedAcl(device=device, name=header.group("name"))
            continue

        if current is None:
            continue

        # Skip prompt-like lines or section divisions.
        if line.endswith("#") or line.endswith(">"):
            continue

        current.rules.append(line)

        if _DENY_MCAST_RE.search(line):
            current.has_deny_ospf_multicast = True
            evidence.append(
                Evidence(
                    tag="acl_blocks_ospf",
                    level=EvidenceLevel.STRONG,
                    source=source,
                    detail=(
                        f"On {device}, ACL '{current.name}' contains rule that drops OSPF "
                        f"multicast: [{line}]. If this ACL is applied INBOUND on an OSPF-enabled "
                        "interface, hellos cannot be received."
                    ),
                    devices=(device,),
                )
            )
        elif _DENY_OSPF_RE.search(line):
            current.has_deny_ospf = True
            evidence.append(
                Evidence(
                    tag="acl_blocks_ospf",
                    level=EvidenceLevel.STRONG,
                    source=source,
                    detail=(
                        f"On {device}, ACL '{current.name}' contains [{line}]. "
                        "Applied inbound on an OSPF interface this drops OSPF hellos."
                    ),
                    devices=(device,),
                )
            )

        # generic deny with hits (not OSPF)
        if "deny" in line.lower() and "ospf" not in line.lower():
            hit_m = _HIT_COUNT_RE.search(line)
            if hit_m and int(hit_m.group(1)) > 0:
                current.has_deny_with_hits = True
                evidence.append(
                    Evidence(
                        tag="acl_deny_with_hits",
                        level=EvidenceLevel.WEAK,
                        source=source,
                        detail=(
                            f"On {device}, ACL '{current.name}' rule [{line}] has "
                            f"{hit_m.group(1)} hits. Traffic is actively being dropped - check "
                            "whether the interface and direction of this ACL match the intent."
                        ),
                        devices=(device,),
                    )
                )

    if current is not None:
        facts.acls.append(current)

    return evidence, facts
