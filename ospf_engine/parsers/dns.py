"""Parser for endpoint DNS test output (``nslookup`` / ``host``)."""

from __future__ import annotations

import re

from ospf_engine.models import Evidence, EvidenceLevel, TopologyFacts
from ospf_engine.models.topology import ParsedDnsResult


_QUERY_RE = re.compile(r"(?:Name|Address|Server)\s*:\s*(?P<val>[\S]+)", re.IGNORECASE)
_NSLOOKUP_HEADER_RE = re.compile(
    r"(?:^|\n)\s*[\w\.\-]*[>#]?\s*nslookup\s+(?P<host>\S+)",
    re.IGNORECASE,
)
_FAIL_RE = re.compile(
    r"can'?t\s+find|server\s+(?:can'?t\s+find|failed)|"
    r"non[-\s]?existent\s+domain|REFUSED|"
    r"(?:DNS\s+)?[Rr]equest\s+(?:to\s+server\s+)?timed\s+out|server\s+unreachable",
    re.IGNORECASE,
)
_PING_BY_IP_OK_RE = re.compile(
    r"Reply\s+from\s+\d+\.\d+\.\d+\.\d+|bytes\s+from\s+\d+\.\d+\.\d+\.\d+",
    re.IGNORECASE,
)
_PING_BY_NAME_FAIL_RE = re.compile(
    r"ping(?:ing)?\s+(?P<name>[A-Za-z][\w\.-]+).*(?:could\s+not\s+find|unknown\s+host|"
    r"bad\s+address|name\s+or\s+service\s+not\s+known)",
    re.IGNORECASE | re.DOTALL,
)


def parse(text: str, source: str, device: str) -> tuple[list[Evidence], TopologyFacts]:
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    nslookup_m = _NSLOOKUP_HEADER_RE.search(text)
    queried_host = nslookup_m.group("host") if nslookup_m else None

    failed = bool(_FAIL_RE.search(text))
    name_fail = _PING_BY_NAME_FAIL_RE.search(text)
    if name_fail and not queried_host:
        queried_host = name_fail.group("name")
        failed = True

    ip_ok = bool(_PING_BY_IP_OK_RE.search(text))

    if failed and queried_host:
        facts.dns_results.append(
            ParsedDnsResult(
                source=device,
                host=queried_host,
                resolved=False,
                server_reachable=ip_ok,
            )
        )
        # When *this single file* contains both a successful ping by IP and a failed
        # nslookup, we can immediately conclude an isolated DNS failure (CONFIG). When
        # the L3 evidence lives in a separate file (typical for the benchmark), the
        # correlator does the same join across files.
        if ip_ok:
            evidence.append(
                Evidence(
                    tag="dns_failure_isolated",
                    level=EvidenceLevel.CONFIG,
                    source=source,
                    detail=(
                        f"On {device}: DNS lookup for '{queried_host}' failed but the host can "
                        "reach destinations by IP. The network path is healthy - the DNS server "
                        "itself is unreachable, misconfigured, or the client points at a wrong "
                        "DNS server."
                    ),
                    devices=(device,),
                )
            )
        else:
            evidence.append(
                Evidence(
                    tag="dns_query_failed",
                    level=EvidenceLevel.STRONG,
                    source=source,
                    detail=(
                        f"On {device}: nslookup for '{queried_host}' failed. If the host can "
                        "reach the network by IP, this is a DNS-only fault; otherwise it is a "
                        "consequence of broken connectivity."
                    ),
                    devices=(device,),
                )
            )

    return evidence, facts
