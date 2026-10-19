"""Regression tests for the four gaps surfaced by an external custom test:

1. OSPF Area Mismatch is missed (or downgraded) when device names overlap
   because filename / prompt parsing failed.
2. Native VLAN Mismatch is missed when only one switch is captured but
   syslog reports the mismatch.
3. STP blocking / wrong-root anomaly is missed when device parsing fails.
4. Device-name parsing returns 'UNKNOWN' for common filename / prompt
   shapes (`R1.txt`, `R1`, `R1(config)#show ...`).

These tests describe behaviour that *must* hold; the fixes in this commit
make them pass.
"""

from __future__ import annotations

from ospf_engine import analyze, parse_files
from ospf_engine.models import EvidenceLevel
from ospf_engine.parsers.dispatcher import parse_file
from ospf_engine.reasoning.knowledge_base import (
    F_AREA_MISMATCH,
    F_NATIVE_VLAN_MISMATCH,
    F_STP_WRONG_ROOT,
)
from ospf_engine.utils.text import (
    extract_device_from_filename,
    extract_device_from_prompt,
    infer_device,
)


# ---------------------------------------------------------------------------
# 4) Device-name parsing
# ---------------------------------------------------------------------------


def test_filename_with_no_underscore_extracts_device() -> None:
    assert extract_device_from_filename("R1.txt") == "R1"
    assert extract_device_from_filename("r1.txt") == "R1"
    assert extract_device_from_filename("SW1.txt") == "SW1"
    assert extract_device_from_filename("R1") == "R1"


def test_filename_with_hyphen_separator_extracts_device() -> None:
    assert extract_device_from_filename("R1-ospf.txt") == "R1"
    assert extract_device_from_filename("SW1-trunk.log") == "SW1"


def test_filename_with_space_separator_extracts_device() -> None:
    assert extract_device_from_filename("R1 ospf neighbor.txt") == "R1"


def test_prompt_in_config_mode_extracts_device() -> None:
    text = "R1(config-if)#ip ospf area 0\nR1(config-if)#exit\n"
    assert extract_device_from_prompt(text) == "R1"

    text2 = "SW2(config)#show running-config interface fa0/1\n"
    assert extract_device_from_prompt(text2) == "SW2"


def test_infer_device_falls_back_through_layers() -> None:
    # Filename-only signal: no prompt in body.
    assert infer_device("R1.txt", "Neighbor ID  Pri  State\n") == "R1"
    # Prompt-only signal: filename is opaque.
    assert (
        infer_device("paste.txt", "R1#show ip ospf neighbor\nNeighbor ID Pri\n")
        == "R1"
    )


# ---------------------------------------------------------------------------
# 1) OSPF Area Mismatch must be CONFIG when both routers are observed
# ---------------------------------------------------------------------------


_R1_OSPF_INTERFACE_AREA0 = """\
R1#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
"""

_R2_OSPF_INTERFACE_AREA1 = """\
R2#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.2/30, Area 1
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
"""


def test_area_mismatch_with_bare_filenames_is_config() -> None:
    """Filenames have no underscore: 'R1.txt' / 'R2.txt'.

    Before the fix, both files inferred device='UNKNOWN', so the correlator
    saw only one device on the link and did not emit area_mismatch_link.
    """
    files = {
        "R1.txt": _R1_OSPF_INTERFACE_AREA0,
        "R2.txt": _R2_OSPF_INTERFACE_AREA1,
    }
    pr = parse_files(files)

    devices = {iface.device for iface in pr.facts.interfaces}
    assert devices == {"R1", "R2"}, (
        f"Expected per-router devices, got {devices}. "
        "Device-name parsing regressed."
    )

    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_AREA_MISMATCH in fault_names, (
        f"Expected '{F_AREA_MISMATCH}' to be ranked. Got {fault_names}."
    )

    area = next(f for f in analysis.ranked_faults if f.name == F_AREA_MISMATCH)
    assert area.best_evidence_level == EvidenceLevel.CONFIG, (
        f"Expected CONFIG for Area Mismatch, got {area.best_evidence_level}."
    )


def test_area_mismatch_is_not_in_ruled_out() -> None:
    files = {
        "R1.txt": _R1_OSPF_INTERFACE_AREA0,
        "R2.txt": _R2_OSPF_INTERFACE_AREA1,
    }
    analysis = analyze(parse_files(files))
    suppressed = {c.name for c in analysis.considered_and_ruled_out}
    assert F_AREA_MISMATCH not in suppressed, (
        "Confirmed (CONFIG-level) Area Mismatch must never be suppressed."
    )


# ---------------------------------------------------------------------------
# 2) Native VLAN Mismatch when only one switch + CDP syslog are captured
# ---------------------------------------------------------------------------


_SW1_TRUNK_NATIVE_1 = """\
SW1#show interfaces trunk

Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      1
Fa0/24      on           802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1-1005
"""

_SW1_LOG_CDP_MISMATCH = """\
SW1#show logging
*Mar  1 00:02:11.500: %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch \
discovered on FastEthernet0/1 (1), with SW2 FastEthernet0/1 (99).
*Mar  1 00:02:11.510: %SPANTREE-2-RECV_PVST_BPDU: Received PVST BPDU on \
non trunk FastEthernet0/1 VLAN 99
"""


def test_native_vlan_mismatch_detected_with_one_switch_plus_syslog() -> None:
    files = {
        "SW1_trunk.txt": _SW1_TRUNK_NATIVE_1,
        "SW1_logging.txt": _SW1_LOG_CDP_MISMATCH,
    }
    analysis = analyze(parse_files(files))

    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_NATIVE_VLAN_MISMATCH in fault_names, (
        f"Native VLAN Mismatch must be ranked when CDP syslog reports it. "
        f"Got {fault_names}."
    )

    nvm = next(
        f for f in analysis.ranked_faults if f.name == F_NATIVE_VLAN_MISMATCH
    )
    assert nvm.best_evidence_level.order >= EvidenceLevel.STRONG.order


# ---------------------------------------------------------------------------
# 3) STP blocking / wrong-root anomaly
# ---------------------------------------------------------------------------


_SW1_STP_PRIORITY_0 = """\
SW1#show spanning-tree

VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    1
             Address     0001.4264.1234
             This bridge is the root
             Hello Time  2 sec  Max Age 20 sec  Forward Delay 15 sec

  Bridge ID  Priority    1   (priority 0 sys-id-ext 1)
             Address     0001.4264.1234

Interface           Role Sts Cost      Prio.Nbr Type
------------------- ---- --- --------- -------- --------------------------------
Fa0/1               Desg FWD 19        128.1    P2p
Fa0/24              Desg FWD 19        128.24   P2p
"""

_SW2_STP_NORMAL_BLOCKED = """\
SW2#show spanning-tree

VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    1
             Address     0001.4264.1234
             Cost        19
             Port        1 (FastEthernet0/1)

  Bridge ID  Priority    32769 (priority 32768 sys-id-ext 1)
             Address     0002.96A2.5678

Interface           Role Sts Cost      Prio.Nbr Type
------------------- ---- --- --------- -------- --------------------------------
Fa0/1               Root FWD 19        128.1    P2p
Fa0/2               Altn BLK 19        128.2    P2p
Fa0/24              Desg FWD 19        128.24   P2p
"""


def test_stp_wrong_root_detected_with_overlapping_filenames() -> None:
    """Filename has no underscore. Without the device-parsing fix both
    switches are 'UNKNOWN' and the STP correlator collapses them."""
    files = {
        "SW1.txt": _SW1_STP_PRIORITY_0,
        "SW2.txt": _SW2_STP_NORMAL_BLOCKED,
    }
    pr = parse_files(files)
    devices = {s.device for s in pr.facts.stp_vlans}
    assert devices == {"SW1", "SW2"}, (
        f"Per-switch device names must be preserved. Got {devices}."
    )

    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_STP_WRONG_ROOT in fault_names, (
        f"STP wrong-root must surface (priority 1 is suspicious). "
        f"Got {fault_names}."
    )


def test_blocking_port_evidence_extracted() -> None:
    files = {"SW2.txt": _SW2_STP_NORMAL_BLOCKED}
    _ev, facts = parse_file("SW2.txt", _SW2_STP_NORMAL_BLOCKED)
    blocked_ports = [b for s in facts.stp_vlans for b in s.blocked_ports]
    assert "Fa0/2" in blocked_ports, (
        f"Blocked port 'Fa0/2' must be extracted from SW2 output. "
        f"Got {blocked_ports}."
    )


# ---------------------------------------------------------------------------
# Dispatcher: Cisco column-separator dashes must NOT be treated as a banner.
# ---------------------------------------------------------------------------


def test_dispatcher_does_not_split_on_cisco_column_dashes() -> None:
    """The line '------- ---- --- ---------' inside `show spanning-tree` is a
    column header, NOT a banner separator. It must not split the output."""
    from ospf_engine.parsers.dispatcher import _is_combined

    text = (
        "SW2#show spanning-tree\n"
        "\n"
        "VLAN0001\n"
        "  Spanning tree enabled protocol ieee\n"
        "\n"
        "Interface           Role Sts Cost      Prio.Nbr Type\n"
        "------------------- ---- --- --------- -------- "
        "--------------------------------\n"
        "Fa0/2               Altn BLK 19        128.2    P2p\n"
    )
    assert _is_combined(text) is False, (
        "Cisco column-header dashes triggered combined-dump splitting."
    )


def test_dispatcher_still_splits_on_real_banners() -> None:
    """Genuine '===== show ... =====' banners must still trigger splitting."""
    from ospf_engine.parsers.dispatcher import _is_combined

    text = (
        "===== R1 show ip ospf neighbor =====\n"
        "Neighbor ID  Pri State\n"
        "===== R1 show ip ospf interface =====\n"
        "GigabitEthernet0/0 is up, line protocol is up\n"
    )
    assert _is_combined(text) is True


def test_dispatcher_accepts_config_mode_prompt_banner() -> None:
    """'R1(config-if)#show ip ospf interface' is a valid banner."""
    from ospf_engine.parsers.dispatcher import _is_combined

    text = (
        "R1#show ip ospf neighbor\n"
        "Neighbor ID  Pri State\n"
        "R1(config-if)#show ip ospf interface\n"
        "GigabitEthernet0/0 is up, line protocol is up\n"
    )
    assert _is_combined(text) is True


# ---------------------------------------------------------------------------
# THE big external-mixed-topology gap: a single file containing show output
# from many devices (R1, R2, S1, S2, PC1) interleaved with their prompts.
# Every chunk must be tagged with its *own* device, NOT the first device in
# the file.
# ---------------------------------------------------------------------------


_MIXED_TOPOLOGY_DUMP = """\
R1#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5

R2#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.2/30, Area 1
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5

S1#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1-1005

S2#show interfaces trunk

Port        Mode             Encapsulation  Status        Native vlan
Fa0/1       on               802.1q         trunking      99

Port        Vlans allowed on trunk
Fa0/1       1-1005

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

PC1>ipconfig

   IP Address......................: 0.0.0.0
   Subnet Mask.....................: 0.0.0.0
   Default Gateway.................: 0.0.0.0
"""


def test_mixed_topology_per_chunk_device_inference() -> None:
    """Every chunk inside a combined dump must be tagged with its own device.

    Before the fix, every chunk inherited the file-level device (R1), so
    R2's area-1 interface, S1/S2's trunks, S2's STP and PC1's ipconfig all
    got tagged 'R1' - which collapses cross-device correlation.
    """
    pr = parse_files({"mixed_topology.txt": _MIXED_TOPOLOGY_DUMP})

    iface_devices = {iface.device for iface in pr.facts.interfaces}
    assert {"R1", "R2"}.issubset(iface_devices), (
        f"Expected per-router devices on parsed interfaces. Got {iface_devices}."
    )

    trunk_devices = {t.device for t in pr.facts.trunks}
    assert {"S1", "S2"}.issubset(trunk_devices), (
        f"Expected S1 and S2 trunks. Got {trunk_devices}."
    )

    stp_devices = {s.device for s in pr.facts.stp_vlans}
    assert "S2" in stp_devices, (
        f"Expected S2 in STP facts. Got {stp_devices}."
    )

    # Devices must NOT collapse to UNKNOWN.
    assert "UNKNOWN" not in iface_devices | trunk_devices | stp_devices, (
        "No chunk should remain tagged UNKNOWN after per-chunk inference."
    )


def test_mixed_topology_detects_area_mismatch_at_config() -> None:
    """With per-chunk device inference, Area 0 vs Area 1 on 10.0.1.0/30 must
    surface as CONFIG-level Area Mismatch."""
    pr = parse_files({"mixed_topology.txt": _MIXED_TOPOLOGY_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_AREA_MISMATCH in fault_names, (
        f"Area Mismatch must be detected. Got {fault_names}."
    )
    area = next(f for f in analysis.ranked_faults if f.name == F_AREA_MISMATCH)
    assert area.best_evidence_level == EvidenceLevel.CONFIG


def test_mixed_topology_detects_native_vlan_at_config() -> None:
    """S1 (native 1) and S2 (native 99) on the same trunk port must surface
    as CONFIG-level Native VLAN Mismatch from the cross-switch correlator
    (no syslog needed)."""
    pr = parse_files({"mixed_topology.txt": _MIXED_TOPOLOGY_DUMP})
    analysis = analyze(pr)
    fault_names = {f.name for f in analysis.ranked_faults}
    assert F_NATIVE_VLAN_MISMATCH in fault_names
    nvm = next(
        f for f in analysis.ranked_faults if f.name == F_NATIVE_VLAN_MISMATCH
    )
    assert nvm.best_evidence_level == EvidenceLevel.CONFIG


def test_mixed_topology_no_prompt_no_underscore_filename() -> None:
    """Worst-case shape: no Cisco prompt in the first 30 lines AND a filename
    that doesn't carry the device. Per-chunk inference still picks each
    chunk's device from its own banner."""
    no_prompt_header = (
        "Building configuration...\n"
        "\n"
        "Current configuration : 1234 bytes\n"
        "\n"
    )
    pr = parse_files(
        {"topology dump.txt": no_prompt_header + _MIXED_TOPOLOGY_DUMP}
    )
    iface_devices = {iface.device for iface in pr.facts.interfaces}
    assert "R1" in iface_devices and "R2" in iface_devices, (
        f"Per-chunk device inference must still find R1 and R2. "
        f"Got {iface_devices}."
    )


def test_default_hostname_router_and_switch_are_accepted() -> None:
    """Default Cisco hostnames (Router#, Switch#) must NOT be rejected by
    the prompt parser - they're valid device names in unconfigured labs."""
    from ospf_engine.utils.text import extract_device_from_prompt

    assert extract_device_from_prompt("Router#show ip ospf neighbor\n") == "ROUTER"
    assert extract_device_from_prompt("Switch#show vlan brief\n") == "SWITCH"
    assert extract_device_from_prompt("Switch>enable\n") == "SWITCH"
