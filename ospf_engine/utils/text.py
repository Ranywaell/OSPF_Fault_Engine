"""Small text helpers used by every parser."""

from __future__ import annotations

import re
from typing import Iterable, Iterator


# Cisco prompt: 'R1#', 'SW2>', 'R1(config)#', 'R1(config-if)#', 'R1(config-router)#'.
# The hostname is capture group 1; an optional config-mode segment may sit
# between the hostname and the [#>] terminator.
_PROMPT_RE = re.compile(
    r"^(?P<host>[A-Za-z][A-Za-z0-9_\-]{0,30})"
    r"(?:\s*\([\w\-]{1,40}\))?"
    r"\s*[#>]"
)

# Filenames we'll strip when extracting a device hint.
_FILENAME_EXT_RE = re.compile(
    r"\.(?:txt|log|out|cap|cli|cfg|md|json|csv)$", re.IGNORECASE
)

# Filename device hostname: must START the filename, must be a real word
# (letters then optional digits / hyphen-suffix), and must be followed by an
# accepted separator or end-of-string. We split on _ - . space.
_FILENAME_DEVICE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9]{0,15})(?:[_.\s\-]|$)")

# Filename tokens that are clearly NOT a device name (case-insensitive).
# Anything that names a `show`-command, a wrapper keyword, or a common
# label like 'device'/'output' must be rejected so files such as
# 'IPCONFIG.txt' or 'DEVICE.txt' fall through to UNKNOWN instead of
# being treated as a hostname.
_FILENAME_RESERVED = {
    "show", "scenario", "log", "logs", "logging", "syslog",
    "term", "terminal", "config", "configuration", "running", "startup",
    "ipconfig", "ping", "trace", "nslookup", "tracert", "traceroute",
    "device", "hostname", "output", "capture", "dump", "paste",
    "interface", "interfaces", "vlan", "vlans", "trunk", "trunks",
    "spanning", "tree", "stp", "route", "routes", "routing",
    "access", "list", "lists", "acl", "acls", "dhcp", "binding",
    "bindings", "ospf", "eigrp", "bgp", "rip", "verify", "verifying",
    "building", "current",
}

# Hostname tokens we reject from the prompt regex. We only blacklist tokens
# that are CLI command keywords AND can plausibly be followed by '#' or '>'.
# 'Router' and 'Switch' are deliberately NOT here - they are common default
# Cisco hostnames in unconfigured labs.
_PROMPT_RESERVED = {
    "show", "term", "terminal", "config", "press", "building",
}

# Tokens we reject when extracting a device label from a *decorated banner*
# such as ``===== show ip ospf =====`` or ``==== DEVICE: ====``. This list
# is intentionally broader than _PROMPT_RESERVED because a banner header is
# almost never a real hostname - it is usually a section title containing
# the show-command name itself ('show', 'interface', 'spanning', ...).
_BANNER_RESERVED = _FILENAME_RESERVED | _PROMPT_RESERVED

# ``==== DEVICE: R1 ====`` / ``Hostname: R1`` / ``device = R1`` style markers.
# A high-confidence label that pins the device name explicitly. Captured
# token still has to clear _BANNER_RESERVED so 'device' itself can't loop
# back as the hostname.
_EXPLICIT_DEVICE_LABEL_RE = re.compile(
    r"\b(?:device|hostname|host|router|switch)\s*[:=]\s*"
    r"(?P<dev>[A-Za-z][A-Za-z0-9_\-]{0,30})\b",
    re.IGNORECASE,
)


def iter_nonempty_lines(text: str) -> Iterator[str]:
    """Yield stripped, non-empty lines."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            yield stripped


def safe_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def extract_device_from_prompt(text: str) -> str | None:
    """Look for a Cisco prompt like ``R1#``, ``SW2>``, ``R1(config-if)#`` in
    the first 30 non-empty lines of ``text``.

    Returns the hostname uppercased, or None if no acceptable prompt is found.
    """
    for line in list(iter_nonempty_lines(text))[:30]:
        match = _PROMPT_RE.match(line)
        if not match:
            continue
        host = match.group("host")
        if host.lower() in _PROMPT_RESERVED:
            continue
        return host.upper()
    return None


def extract_device_from_explicit_label(text: str) -> str | None:
    """Find an explicit ``DEVICE: R1`` / ``Hostname = SW1`` style label in
    the first 30 non-empty lines of ``text``. Highest-confidence signal -
    used by the dispatcher BEFORE falling back to banner-token guessing.

    Returns the captured hostname uppercased, or None if no label is found
    (or the captured token is itself a reserved keyword).
    """
    for line in list(iter_nonempty_lines(text))[:30]:
        m = _EXPLICIT_DEVICE_LABEL_RE.search(line)
        if not m:
            continue
        candidate = m.group("dev")
        if candidate.lower() in _BANNER_RESERVED:
            continue
        return candidate.upper()
    return None


def extract_device_from_filename(filename: str) -> str | None:
    """Best-effort device extraction from a filename.

    Examples::

        "R1.txt"                 -> "R1"
        "R1"                     -> "R1"
        "R1_ospf_neighbor.txt"   -> "R1"
        "R1-ospf.txt"            -> "R1"
        "R1 ospf neighbor.txt"   -> "R1"
        "sw2_log.txt"            -> "SW2"
        "scenario_3.txt"         -> None  (reserved word)
        "show.txt"               -> None  (reserved word)
        "1.txt"                  -> None  (must start with a letter)
    """
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = _FILENAME_EXT_RE.sub("", base)

    match = _FILENAME_DEVICE_RE.match(base)
    if not match:
        return None
    candidate = match.group(1)
    if candidate.lower() in _FILENAME_RESERVED:
        return None
    return candidate.upper()


def infer_device(filename: str, content: str) -> str:
    """Best-effort device identifier.

    Order of attempts:
      1. Explicit ``DEVICE: NAME`` / ``Hostname: NAME`` label in the
         first lines of the content (highest confidence).
      2. A Cisco prompt (``R1#``, ``SW2>``, ``R1(config-if)#``).
      3. The filename stem (with reserved words rejected).
      4. ``'UNKNOWN'`` fallback.
    """
    return (
        extract_device_from_explicit_label(content)
        or extract_device_from_prompt(content)
        or extract_device_from_filename(filename)
        or "UNKNOWN"
    )


def has_any(text: str, patterns: Iterable[str]) -> bool:
    """Convenience: regex-search a list of patterns case-insensitively."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False
