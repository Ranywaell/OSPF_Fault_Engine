"""Filename + content based parser dispatcher.

The dispatcher decides which parser(s) to run on each input string. It handles
three input shapes:

1. A single-command file (e.g. ``R1_ospf_interface.txt``) -> route by filename
   keyword, fall back to content sniffing.
2. A combined dump where one file contains many ``show`` outputs separated by
   ``-----`` or ``=====`` style banners, or by Cisco's prompt + command echo.
3. An unknown blob -> sniff every parser's signature on the content and run
   whatever matches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ospf_engine.models import Evidence, TopologyFacts
from ospf_engine.parsers import (
    access_lists,
    dhcp,
    dns,
    endpoint,
    interfaces_trunk,
    ip_interface,
    ip_route,
    ospf_interface,
    ospf_neighbor,
    spanning_tree,
    syslog,
)
from ospf_engine.parsers.base import ParserFn
from ospf_engine.utils.text import (
    extract_device_from_explicit_label,
    extract_device_from_prompt,
    infer_device,
    _BANNER_RESERVED,
    _EXPLICIT_DEVICE_LABEL_RE,
    _PROMPT_RE,
    _PROMPT_RESERVED,
)


@dataclass
class ParseResult:
    """Aggregate of all parsing across the input set."""

    evidence: list[Evidence] = field(default_factory=list)
    facts: TopologyFacts = field(default_factory=TopologyFacts)
    file_results: list[dict] = field(default_factory=list)


# (filename keyword, parser, content-signature regex)
# Ordering matters: more specific filenames first.
_PARSER_ROUTES: list[tuple[str, ParserFn, re.Pattern[str]]] = [
    (
        "ospf_neighbor",
        ospf_neighbor.parse,
        re.compile(r"show\s+ip\s+ospf\s+neighbor", re.IGNORECASE),
    ),
    (
        "ospf_interface",
        ospf_interface.parse,
        re.compile(
            r"show\s+ip\s+ospf\s+interface|Network\s+Type\s+\w+,\s*Cost",
            re.IGNORECASE,
        ),
    ),
    (
        "access_list",
        access_lists.parse,
        re.compile(
            r"show\s+access[-\s]?list|(?:Standard|Extended)\s+IP\s+access\s+list",
            re.IGNORECASE,
        ),
    ),
    (
        "ip_interface",
        ip_interface.parse,
        re.compile(
            r"show\s+ip\s+interface|"
            r"Inbound\s+access\s+list\s+is|"
            r"Outgoing\s+access\s+list\s+is|"
            r"Helper\s+address\s+is",
            re.IGNORECASE,
        ),
    ),
    (
        "trunk",
        interfaces_trunk.parse,
        re.compile(r"show\s+interfaces\s+trunk|Native\s+vlan", re.IGNORECASE),
    ),
    (
        "spanning_tree",
        spanning_tree.parse,
        re.compile(
            r"show\s+spanning[-\s]?tree|Spanning\s+tree\s+enabled",
            re.IGNORECASE,
        ),
    ),
    (
        "ip_route",
        ip_route.parse,
        re.compile(
            r"show\s+ip\s+route|Codes:\s+C\s+-\s+connected|"
            r"Gateway\s+of\s+last\s+resort",
            re.IGNORECASE,
        ),
    ),
    (
        "dhcp",
        dhcp.parse,
        re.compile(r"show\s+ip\s+dhcp\s+binding|Bindings\s+from\s+all\s+pools", re.IGNORECASE),
    ),
    (
        "syslog",
        syslog.parse,
        re.compile(r"show\s+logging|%[A-Z]+-\d-[A-Z_]+", re.IGNORECASE),
    ),
    (
        "log",
        syslog.parse,
        re.compile(r"%[A-Z]+-\d-[A-Z_]+", re.IGNORECASE),
    ),
    (
        "nslookup",
        dns.parse,
        re.compile(r"nslookup|DNS\s+request|server\s+can'?t\s+find", re.IGNORECASE),
    ),
    (
        "dns",
        dns.parse,
        re.compile(r"nslookup|DNS\s+request|server\s+can'?t\s+find", re.IGNORECASE),
    ),
    (
        "ipconfig",
        endpoint.parse,
        re.compile(r"ipconfig|IP\s+Address.*0\.0\.0\.0|Reply\s+from\s+\d", re.IGNORECASE),
    ),
    (
        "ping",
        endpoint.parse,
        re.compile(r"^Pinging|^PING|Reply\s+from|Request\s+timed\s+out", re.IGNORECASE),
    ),
]


# ---- combined-output handling -------------------------------------------------

# A "banner" delimits one show-command output from the next inside a
# combined-dump file. Two recognised shapes:
#
#   1. Decorated banner: '===== show ip ospf neighbor =====' / '----- R1 -----'.
#      We require at least one *word* character between the markers so a
#      Cisco column-header line like '------- ---- --- -------' (dashes
#      separated only by whitespace) does NOT match. That false-positive
#      used to split 'show spanning-tree' output and lose the
#      blocked-port table.
#
#   2. A Cisco prompt followed by a 'show' command:
#        'R1#show ip ospf interface' / 'R1(config-if)#show ip ospf neighbor'.
#      The optional '(config-...)' segment is supported so config-mode dumps
#      are still routed correctly.
_BANNER_RE = re.compile(
    r"""(?P<banner>
        (?:^|\n)
        (?:
            # Decorated banner with at least one alphanumeric word between
            # the marker pairs (excludes Cisco column-separator lines).
            [-=#]{3,}[\ \t]*[A-Za-z0-9][\w \-\./:]*[\ \t]*[-=#]{3,}
          |
            # Cisco prompt (with optional config-mode parens) + show command.
            [\w\.\-]+(?:\([\w\-]{1,40}\))?[#>]\s*show\s+\S.*
        )
    )""",
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Inner-chunk separator: a bare ``show <cmd>`` line at the start of a line.
# Some external dumps look like::
#
#     ==================== DEVICE: S2 ====================
#     show interfaces trunk
#     ...
#     show spanning-tree
#     ...
#
# i.e. the device label is set once with a decorated banner and every
# show command inside that section is just typed without re-echoing the
# Cisco prompt. Without this second-level split, ``_route_by_content``
# would only match the first ``show`` signature and silently drop the
# rest of the section's data.
_INNER_SHOW_RE = re.compile(
    r"^[ \t]*show\s+\S[\w \-\./:]{0,80}$",
    re.IGNORECASE | re.MULTILINE,
)


def _is_combined(text: str) -> bool:
    """Heuristic: more than one banner-style separator -> treat as combined dump."""
    matches = _BANNER_RE.findall(text)
    return len(matches) >= 2


def _route_by_filename(filename: str) -> ParserFn | None:
    name = filename.lower().replace("-", "_").replace(" ", "_")
    for keyword, fn, _sig in _PARSER_ROUTES:
        if keyword in name:
            return fn
    return None


def _route_by_content(text: str) -> ParserFn | None:
    head = text[:2000]
    for _kw, fn, sig in _PARSER_ROUTES:
        if sig.search(head):
            return fn
    return None


def _split_combined(text: str) -> list[tuple[str, str]]:
    """Yield ``(banner, body)`` chunks from a combined-output blob."""
    parts: list[tuple[str, str]] = []
    matches = list(_BANNER_RE.finditer(text))
    if not matches:
        return [("", text)]
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        if body.strip():
            parts.append((m.group("banner").strip(), body))
    return parts


def _split_inner_shows(body: str) -> list[str]:
    """Split a chunk body on bare ``show <cmd>`` lines.

    Returns sub-bodies in source order. If the body has 0 or 1 inner
    ``show`` separators we just return ``[body]`` so the caller behaves
    exactly as before.
    """
    matches = list(_INNER_SHOW_RE.finditer(body))
    if len(matches) < 2:
        return [body]
    pieces: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sub = body[start:end]
        if sub.strip():
            pieces.append(sub)
    return pieces or [body]


# Decorated banner with embedded device label, e.g. '===== R1 show ip ospf ====='
# or '----- R2 -----'. Captures the first device-like token after the marker run.
_BANNER_DEVICE_RE = re.compile(
    r"[-=#]{2,}\s*(?P<dev>[A-Za-z][A-Za-z0-9_\-]{0,15})\b"
)


def _device_from_chunk(banner: str, body: str, fallback: str) -> str:
    """Best-effort device id for one banner+body chunk inside a combined dump.

    Order of attempts (highest confidence first):
      1. Explicit ``DEVICE: NAME`` / ``Hostname: NAME`` label in the
         banner OR the first lines of the body (added for external dumps
         that mark each section with ``==== DEVICE: R1 ====`` and DON'T
         re-echo a Cisco prompt).
      2. Cisco prompt at the start of the banner (``R1#show ...``,
         ``R1(config-if)#show ...``).
      3. Decorated banner with the device name embedded
         (``===== R1 show ip ospf =====`` -> ``R1``).
      4. A Cisco prompt anywhere in the body (rare - bodies are usually
         output, not prompts).
      5. The file-level fallback device.

    All candidates are clamped against ``_BANNER_RESERVED`` so generic CLI
    keywords (``DEVICE``, ``SHOW``, ``INTERFACE``, ``VLAN``, ...) never
    leak through as a hostname.
    """
    if banner:
        b = banner.strip()
        # 1a) Explicit DEVICE: / Hostname: label in the banner itself.
        explicit = _EXPLICIT_DEVICE_LABEL_RE.search(b)
        if explicit:
            cand = explicit.group("dev")
            if cand.lower() not in _BANNER_RESERVED:
                return cand.upper()
        # 2) Cisco prompt at the start (after stripping any leading markers).
        cleaned = b.lstrip("-=# \t")
        m = _PROMPT_RE.match(cleaned)
        if m:
            host = m.group("host")
            if host.lower() not in _PROMPT_RESERVED:
                return host.upper()
        # 3) Decorated banner with embedded device token. Use the broader
        #    _BANNER_RESERVED set so 'DEVICE', 'SHOW', etc. never win here.
        decorated = _BANNER_DEVICE_RE.search(b)
        if decorated:
            cand = decorated.group("dev")
            if cand.lower() not in _BANNER_RESERVED:
                return cand.upper()

    # 1b) Explicit DEVICE: / Hostname: label in the first lines of the body
    #     (some dumps put the banner on its own line and the ``DEVICE: R1``
    #     marker just below it, without a re-echoed prompt).
    body_explicit = extract_device_from_explicit_label(body)
    if body_explicit:
        return body_explicit

    # 4) Last-ditch: prompt inside the body.
    body_dev = extract_device_from_prompt(body)
    if body_dev:
        return body_dev

    return fallback


def parse_file(filename: str, content: str) -> tuple[list[Evidence], TopologyFacts]:
    """Parse a single uploaded file.

    For combined-dump files (multiple ``show`` outputs in one file), each
    chunk is parsed with its *own* inferred device - extracted from the
    chunk banner ('R1#show ip ospf interface' -> R1, 'S2#show...' -> S2).
    Without per-chunk inference, every chunk would inherit the file-level
    device (the first prompt found) and cross-device correlation would
    collapse to a single device, missing real link-level mismatches.
    """
    file_level_device = infer_device(filename, content)
    evidence: list[Evidence] = []
    facts = TopologyFacts()

    if _is_combined(content):
        for banner, body in _split_combined(content):
            chunk_device = _device_from_chunk(banner, body, fallback=file_level_device)
            # If the chunk body itself contains multiple bare ``show <cmd>``
            # commands, split it again so each show output gets routed to
            # its own parser - while keeping the chunk's device attribution.
            for sub in _split_inner_shows(body):
                fn = _route_by_content(banner) or _route_by_content(sub)
                if fn is None:
                    continue
                ev, fc = fn(sub, filename, chunk_device)
                evidence.extend(ev)
                facts = facts.merge(fc)
        return evidence, facts

    fn = _route_by_filename(filename) or _route_by_content(content)
    if fn is None:
        return evidence, facts
    ev, fc = fn(content, filename, file_level_device)
    return ev + evidence, facts.merge(fc)


def parse_files(files: dict[str, str]) -> ParseResult:
    """Parse a dict of ``{filename: content}`` and aggregate results."""
    result = ParseResult()
    seen: set[tuple[str, str, str]] = set()

    for fname, content in files.items():
        evidence, facts = parse_file(fname, content)
        unique_evidence: list[Evidence] = []
        for ev in evidence:
            key = (ev.tag, ev.level.value, ev.detail[:80])
            if key in seen:
                continue
            seen.add(key)
            unique_evidence.append(ev)

        result.evidence.extend(unique_evidence)
        result.facts = result.facts.merge(facts)
        result.file_results.append(
            {
                "filename": fname,
                "evidence_count": len(unique_evidence),
                "evidence": [e.to_dict() for e in unique_evidence],
            }
        )

    return result
