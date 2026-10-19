"""Second round of regression tests for external-mixed-topology gaps.

The first external test (see ``test_external_gaps.py``) covered prompt /
filename / Cisco column-dash bugs.  The next round of external uploads
exposed four more gaps that this module locks in:

1. ``==================== DEVICE: R1 ====================`` style banners
   - the dispatcher used to capture ``DEVICE`` (or fall back to
   ``UNKNOWN``) instead of the real hostname after the colon.

2. Generic CLI-keyword filenames (``IPCONFIG.txt``, ``PING.txt``,
   ``SYSLOG.txt``, ``DEVICE.txt``) - none of these are device names.

3. Trunk *allowed-VLAN* inconsistency between two switches
   (``Allowed VLANs: 1,20`` on one side, ``1,10,20`` on the other).
   Native-VLAN mismatch is already detected; missing-VLAN-on-trunk used
   to be silently dropped.

4. STP ``BLK`` ports and wrong-root scenarios in a single combined
   dump using DEVICE banners (i.e. issues 1 + 4 stacked).

These tests fail before the patch and pass after.
"""

from __future__ import annotations

from ospf_engine import analyze, parse_files
from ospf_engine.models import EvidenceLevel
from ospf_engine.parsers.dispatcher import parse_file
from ospf_engine.reasoning.knowledge_base import (
    F_AREA_MISMATCH,
    F_NATIVE_VLAN_MISMATCH,
    F_STP_WRONG_ROOT,
    F_TIMER_MISMATCH,
)
from ospf_engine.utils.text import (
    extract_device_from_filename,
)


# ---------------------------------------------------------------------------
# 1) ``DEVICE: R1`` decorated banners
# ---------------------------------------------------------------------------


_DEVICE_BANNER_DUMP = """\
==================== DEVICE: R1 ====================
R1#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5

==================== DEVICE: R2 ====================
R2#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.2/30, Area 1
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 5, Dead 20, Wait 20, Retransmit 5

==================== DEVICE: S1 ====================
S1#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1,10,20

==================== DEVICE: S2 ====================
S2#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      99

Port        Vlans allowed on trunk
Fa0/1       1,20

S2#show spanning-tree

VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    1
             Address     0001.4264.1234
             Cost        19

  Bridge ID  Priority    32769 (priority 32768 sys-id-ext 1)

Interface           Role Sts Cost      Prio.Nbr Type
------------------- ---- --- --------- -------- --------------------------------
Fa0/1               Root FWD 19        128.1    P2p
Fa0/2               Altn BLK 19        128.2    P2p
"""


def test_device_banner_extracts_real_hostname_not_keyword() -> None:
    """``==== DEVICE: R1 ====`` must yield R1, never DEVICE."""
    pr = parse_files({"combined.txt": _DEVICE_BANNER_DUMP})
    iface_devices = {iface.device for iface in pr.facts.interfaces}
    trunk_devices = {t.device for t in pr.facts.trunks}
    stp_devices = {s.device for s in pr.facts.stp_vlans}

    assert {"R1", "R2"}.issubset(iface_devices), (
        f"Expected R1 and R2 from DEVICE banners, got {iface_devices}."
    )
    assert {"S1", "S2"}.issubset(trunk_devices), (
        f"Expected S1 and S2 from DEVICE banners, got {trunk_devices}."
    )
    assert "S2" in stp_devices, f"Expected S2 in STP facts, got {stp_devices}."

    bad_tokens = {
        "DEVICE", "UNKNOWN", "SHOW", "INTERFACE", "INTERFACES",
        "VLAN", "OSPF", "SPANNING",
    }
    leaked = (iface_devices | trunk_devices | stp_devices) & bad_tokens
    assert not leaked, (
        f"Generic CLI tokens leaked as device names: {leaked}."
    )


def test_device_banner_dump_detects_area_mismatch_at_config() -> None:
    pr = parse_files({"combined.txt": _DEVICE_BANNER_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_AREA_MISMATCH in fault_names
    area = next(f for f in analysis.ranked_faults if f.name == F_AREA_MISMATCH)
    assert area.best_evidence_level == EvidenceLevel.CONFIG


def test_device_banner_dump_detects_timer_mismatch_at_config() -> None:
    pr = parse_files({"combined.txt": _DEVICE_BANNER_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_TIMER_MISMATCH in fault_names
    timer = next(f for f in analysis.ranked_faults if f.name == F_TIMER_MISMATCH)
    assert timer.best_evidence_level == EvidenceLevel.CONFIG


def test_device_banner_dump_detects_native_vlan_at_config() -> None:
    pr = parse_files({"combined.txt": _DEVICE_BANNER_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_NATIVE_VLAN_MISMATCH in fault_names
    nvm = next(
        f for f in analysis.ranked_faults if f.name == F_NATIVE_VLAN_MISMATCH
    )
    assert nvm.best_evidence_level == EvidenceLevel.CONFIG


def test_device_banner_dump_detects_stp_anomaly() -> None:
    pr = parse_files({"combined.txt": _DEVICE_BANNER_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    # Either wrong-root (priority 1 elected) OR a blocked-port symptom must
    # surface; the user reported neither was being detected.
    assert F_STP_WRONG_ROOT in fault_names, (
        f"Expected STP wrong-root from priority-1 root anomaly. "
        f"Got {fault_names}."
    )


# ---------------------------------------------------------------------------
# 2) Filename rejection: generic CLI keywords are NOT device names
# ---------------------------------------------------------------------------


def test_filename_cli_keyword_rejected_as_device() -> None:
    """Filenames named after the show-command must not become device IDs."""
    for name in (
        "IPCONFIG.txt", "ipconfig.txt",
        "PING.txt", "ping.txt",
        "SYSLOG.txt", "syslog.txt",
        "DEVICE.txt", "device.txt",
        "SHOW.txt",
        "INTERFACES.txt", "interfaces.txt",
        "TRUNK.txt", "trunk.txt",
        "VLAN.txt", "vlan.txt",
        "ROUTE.txt", "route.txt",
        "SPANNING.txt", "spanning.txt",
        "DHCP.txt", "dhcp.txt",
        "OUTPUT.txt", "output.txt",
    ):
        assert extract_device_from_filename(name) is None, (
            f"{name!r} must not be treated as a device name."
        )


# ---------------------------------------------------------------------------
# 3) Trunk allowed-VLAN inconsistency
# ---------------------------------------------------------------------------


_S1_TRUNK_ALLOWED_FULL = """\
S1#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/24      on               802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/24      1,10,20,30
"""

_S2_TRUNK_ALLOWED_PARTIAL = """\
S2#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/24      on               802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/24      1,20
"""


def test_trunk_allowed_vlan_inconsistency_surfaces_finding() -> None:
    """Two switches whose trunks have *different* allowed-VLAN lists must
    raise a Native-VLAN-Mismatch-family finding so the operator sees it.

    Native vlans are equal here (both 1) but VLAN 10 and 30 are missing
    from one side.  Without this detection the engine silently dropped
    the misconfiguration."""
    pr = parse_files({
        "s1_trunk.txt": _S1_TRUNK_ALLOWED_FULL,
        "s2_trunk.txt": _S2_TRUNK_ALLOWED_PARTIAL,
    })

    # The correlator must produce some kind of trunk-inconsistency evidence.
    tags = {ev.tag for ev in analyze(pr).evidence}
    assert "trunk_allowed_vlan_mismatch" in tags, (
        "Allowed-VLAN inconsistency between trunks must produce a "
        f"'trunk_allowed_vlan_mismatch' evidence tag. Got tags={sorted(tags)}."
    )


# ---------------------------------------------------------------------------
# 4) STP wrong-root + blocking inside a SINGLE combined DEVICE-banner dump
# ---------------------------------------------------------------------------


def test_stp_blocking_evidence_emitted_in_device_banner_dump() -> None:
    """The Fa0/2 BLK row inside the S2 chunk of a DEVICE-banner combined
    dump must produce ``stp_port_blocking`` evidence on S2."""
    pr = parse_files({"combined.txt": _DEVICE_BANNER_DUMP})
    blocking_ev = [ev for ev in pr.evidence if ev.tag == "stp_port_blocking"]
    assert blocking_ev, (
        "Expected stp_port_blocking evidence from the BLK row in the "
        "S2 spanning-tree chunk."
    )
    devices = {d for ev in blocking_ev for d in ev.devices}
    assert "S2" in devices, (
        f"stp_port_blocking must be attributed to S2, got devices={devices}."
    )


# ---------------------------------------------------------------------------
# Sanity: parse_file alone (single chunk) still works for DEVICE banners
# ---------------------------------------------------------------------------


def test_single_chunk_with_device_banner_keeps_real_hostname() -> None:
    text = """\
==================== DEVICE: SW42 ====================
SW42#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      99
"""
    _ev, facts = parse_file("paste.txt", text)
    assert len(facts.trunks) == 1
    assert facts.trunks[0].device == "SW42", (
        f"Single chunk with DEVICE banner must yield SW42, "
        f"got {facts.trunks[0].device}."
    )


# ---------------------------------------------------------------------------
# Worst-case external dump: DEVICE banners are the ONLY device marker.
# No inner Cisco prompts (e.g. user pasted output without re-typing the
# `RouterX#show ...` line). The banner alone must drive device attribution.
# ---------------------------------------------------------------------------


_DEVICE_BANNER_NO_PROMPTS_DUMP = """\
==================== DEVICE: R1 ====================
show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5

==================== DEVICE: R2 ====================
show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.2/30, Area 1
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5

==================== DEVICE: S1 ====================
show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1-1005

==================== DEVICE: S2 ====================
show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      99

show spanning-tree

VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    1
             Address     0001.4264.1234

  Bridge ID  Priority    32769 (priority 32768 sys-id-ext 1)

Interface           Role Sts Cost      Prio.Nbr Type
------------------- ---- --- --------- -------- --------------------------------
Fa0/1               Root FWD 19        128.1    P2p
Fa0/2               Altn BLK 19        128.2    P2p
"""


def test_device_banner_alone_drives_attribution_when_no_inner_prompts() -> None:
    """``DEVICE: NAME`` is the *only* marker; no R1#/R2# prompt re-echo.

    Before the fix this collapsed every chunk to the banner-token
    ``DEVICE`` (a CLI keyword leak) or to ``UNKNOWN``, so cross-device
    comparison silently degraded.
    """
    pr = parse_files({"combined.txt": _DEVICE_BANNER_NO_PROMPTS_DUMP})

    iface_devices = {iface.device for iface in pr.facts.interfaces}
    trunk_devices = {t.device for t in pr.facts.trunks}
    stp_devices = {s.device for s in pr.facts.stp_vlans}

    assert {"R1", "R2"}.issubset(iface_devices), (
        f"Expected R1+R2 from DEVICE banners alone, got {iface_devices}."
    )
    assert {"S1", "S2"}.issubset(trunk_devices), (
        f"Expected S1+S2 from DEVICE banners alone, got {trunk_devices}."
    )
    assert "S2" in stp_devices, f"Expected S2 in STP facts, got {stp_devices}."
    assert "DEVICE" not in iface_devices | trunk_devices | stp_devices
    assert "UNKNOWN" not in iface_devices | trunk_devices | stp_devices


def test_device_banner_alone_still_detects_area_mismatch_at_config() -> None:
    pr = parse_files({"combined.txt": _DEVICE_BANNER_NO_PROMPTS_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_AREA_MISMATCH in fault_names
    area = next(f for f in analysis.ranked_faults if f.name == F_AREA_MISMATCH)
    assert area.best_evidence_level == EvidenceLevel.CONFIG, (
        f"Area Mismatch must be CONFIG-level, got {area.best_evidence_level}."
    )
