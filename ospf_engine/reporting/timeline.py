"""Syslog -> timeline events -> Graphviz DOT.

The timeline is intentionally simple: it parses Cisco-style timestamps,
classifies severity, and renders a left-to-right chain of nodes. The earliest
event matching the diagnosed root fault is highlighted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ospf_engine.reasoning.knowledge_base import (
    F_ACL_WRONG_DIRECTION,
    F_AREA_MISMATCH,
    F_DHCP_HELPER_MISSING,
    F_DNS_FAILURE,
    F_HELLOS_BLOCKED_ACL,
    F_MTU_MISMATCH,
    F_NATIVE_VLAN_MISMATCH,
    F_STP_WRONG_ROOT,
    F_TIMER_MISMATCH,
)


_TS_PATTERN = re.compile(
    r"\*?(?P<ts>\w+\s+\d+\s+[\d:\.]+):\s+(?P<fac>%[\w\-]+):\s+(?P<msg>.*)",
    re.IGNORECASE,
)
_PLAIN_PATTERN = re.compile(r"(?P<fac>%[\w\-]+):\s+(?P<msg>.*)", re.IGNORECASE)


@dataclass(slots=True)
class TimelineEvent:
    index: int
    timestamp: str
    facility: str
    message: str
    severity: str  # 'high' | 'medium' | 'low'
    is_root: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "facility": self.facility,
            "message": self.message,
            "severity": self.severity,
            "is_root": self.is_root,
        }


@dataclass(slots=True)
class Timeline:
    events: list[TimelineEvent] = field(default_factory=list)
    dot_source: str = ""
    root_event: TimelineEvent | None = None


# fault -> keywords whose first occurrence we mark as the root event
_ROOT_KEYWORDS: dict[str, tuple[str, ...]] = {
    F_AREA_MISMATCH: ("ADJCHG",),
    F_TIMER_MISMATCH: ("dead timer", "ADJCHG"),
    F_HELLOS_BLOCKED_ACL: ("denied", "IPACCESSLOG"),
    F_ACL_WRONG_DIRECTION: ("denied", "IPACCESSLOG"),
    F_NATIVE_VLAN_MISMATCH: ("NATIVE_VLAN_MISMATCH",),
    F_DHCP_HELPER_MISSING: ("DHCP",),
    F_STP_WRONG_ROOT: ("ROOTCHANGE", "TOPOTRAP", "TOPOLOGY"),
    F_MTU_MISMATCH: ("Mismatched hello parameters", "ERRRCV", "EXCHANGE"),
    F_DNS_FAILURE: ("DNS",),
}


def _severity_for(facility: str, message: str) -> str:
    fac = facility.upper()
    msg = message.upper()
    if "OSPF" in fac and "ADJCHG" in msg:
        return "high"
    if "SEC" in fac and "DENIED" in msg:
        return "high"
    if "CDP" in fac and "NATIVE" in msg:
        return "high"
    if "SPANTREE" in fac and ("TOPO" in msg or "ROOT" in msg or "BLOCK" in msg):
        return "high"
    if "DHCP" in fac:
        return "medium"
    return "low"


def _parse_log_lines(log_text: str) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for i, raw in enumerate(log_text.splitlines()):
        line = raw.strip()
        if not line:
            continue
        m = _TS_PATTERN.search(line)
        if m:
            ts = m.group("ts").strip()
            fac = m.group("fac")
            msg = m.group("msg").strip()
        else:
            m2 = _PLAIN_PATTERN.search(line)
            if not m2:
                continue
            ts = f"t+{i:03d}"
            fac = m2.group("fac")
            msg = m2.group("msg").strip()

        events.append(
            TimelineEvent(
                index=len(events),
                timestamp=ts,
                facility=fac,
                message=msg[:120],
                severity=_severity_for(fac, msg),
            )
        )
    return events


def _mark_root(events: list[TimelineEvent], root_fault: str) -> TimelineEvent | None:
    keywords = _ROOT_KEYWORDS.get(root_fault, ())
    for ev in events:
        for kw in keywords:
            if kw.lower() in ev.message.lower() or kw.lower() in ev.facility.lower():
                ev.is_root = True
                return ev
    return None


def _render_dot(events: list[TimelineEvent], title: str) -> str:
    color_map = {"high": "#E24B4A", "medium": "#BA7517", "low": "#1D9E75"}
    shape_map = {"high": "box", "medium": "ellipse", "low": "ellipse"}

    out = [
        "digraph FaultTimeline {",
        f'  label="{title}";',
        '  labelloc="t";',
        '  rankdir=LR;',
        '  bgcolor="#0E1117";',
        '  node [fontname="Courier", fontsize=10, fontcolor="white"];',
        '  edge [color="#888888"];',
        "",
    ]
    for ev in events:
        color = "#C04828" if ev.is_root else color_map.get(ev.severity, "#888")
        shape = "doubleoctagon" if ev.is_root else shape_map.get(ev.severity, "ellipse")
        label = f"{ev.timestamp}\\n{ev.message[:55]}"
        if ev.is_root:
            label += "\\n[ROOT EVENT]"
        label = label.replace('"', '\\"')
        out.append(
            f'  n{ev.index} [label="{label}", shape={shape}, style=filled, '
            f'fillcolor="{color}"];'
        )
    for i in range(len(events) - 1):
        out.append(f"  n{i} -> n{i+1};")
    out.append("}")
    return "\n".join(out)


def build_timeline(log_text: str, root_fault_name: str = "") -> Timeline:
    """Build the full timeline from raw syslog text."""
    events = _parse_log_lines(log_text)
    root_event = _mark_root(events, root_fault_name) if root_fault_name and events else None
    title = f"Fault Timeline - {root_fault_name or 'Unknown'}"
    dot = _render_dot(events, title)
    return Timeline(events=events, dot_source=dot, root_event=root_event)
