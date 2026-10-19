"""Scenario 8 - Multi-fault demo (the brief's headline scenario).

Four independent faults are injected simultaneously across the topology. The
engine must:

1. Identify all four as CONFIG-level root causes (not just symptoms).
2. Distinguish them from side-effects: an empty OSPF neighbor table, missing
   OSPF routes, an empty DHCP binding table, a PC with no L3 reachability,
   etc., are all *consequences* and must NOT appear in the ranked output as
   competing root causes.
3. Produce a dependency-ordered fix path: L2 (native VLAN) before L3 (DHCP /
   OSPF / DNS) where possible.

Injected faults:

    A. ACL on R1 inbound denies OSPF multicast.
       -> Hellos blocked, R1<->R2 adjacency fails, no OSPF routes on R1.
    B. SW1 / SW2 native-VLAN mismatch on the inter-switch trunk.
       -> CDP logs the mismatch, STP receives PVST BPDUs cross-VLAN.
    C. R1 LAN interface is missing 'ip helper-address'.
       -> Empty DHCP bindings, PC1 cannot get an address.
    D. PC1 can reach the server by IP but nslookup fails (DNS service down).
       -> Isolated DNS failure, L3 is healthy.

The engine is expected to surface exactly these four as ROOT_CAUSE and to
suppress 'Area Mismatch', 'Timer Mismatch', 'OSPF Hellos Blocked by ACL'
side-effects of the same ACL signal, 'DHCP Server Unreachable' (a weak
alternative to the helper-missing finding), etc.
"""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import (
    F_DHCP_HELPER_MISSING,
    F_DNS_FAILURE,
    F_HELLOS_BLOCKED_ACL,
    F_NATIVE_VLAN_MISMATCH,
)
from ospf_engine.scenarios.registry import scenario


# ---- A: ACL blocks OSPF on R1 -----------------------------------------------

_R1_OSPF_NEIGHBOR = """\
R1#show ip ospf neighbor

Neighbor ID     Pri   State           Dead Time   Address         Interface

R1#
"""

_R1_OSPF_INTERFACE = """\
R1#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.1/30, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  Neighbor Count is 0, Adjacent neighbor count is 0
GigabitEthernet0/1 is up, line protocol is up
  Internet Address 192.168.1.1/24, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
R1#
"""

_R1_ACCESS_LISTS = """\
R1#show access-lists
Extended IP access list BLOCK_OSPF
    10 deny ospf any host 224.0.0.5 (412 matches)
    20 deny ospf any host 224.0.0.6 (167 matches)
    30 permit ip any any (3201 matches)
R1#
"""

_R1_IP_INTERFACE_G00 = """\
R1#show ip interface gigabitEthernet 0/0
GigabitEthernet0/0 is up, line protocol is up
  Internet address is 10.0.1.1/30
  MTU is 1500
  Helper address is not set
  Outgoing access list is not set
  Inbound  access list is BLOCK_OSPF
R1#
"""

# ---- B: native VLAN mismatch on SW1<->SW2 trunk -----------------------------

_SW1_TRUNK = """\
SW1#show interfaces trunk

Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      1
Fa0/24      on           802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1-1005
SW1#
"""

_SW2_TRUNK = """\
SW2#show interfaces trunk

Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      99
Fa0/24      on           802.1q         trunking      99

Port        Vlans allowed on trunk
Fa0/1       1-1005
SW2#
"""

_SW1_LOG = """\
SW1#show logging
*Mar  1 00:02:11.500: %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch discovered on FastEthernet0/1 (1), with SW2 FastEthernet0/1 (99).
*Mar  1 00:02:11.510: %SPANTREE-2-RECV_PVST_BPDU: Received PVST BPDU on non trunk FastEthernet0/1 VLAN 99
SW1#
"""

# ---- C: R1 LAN missing DHCP helper-address ----------------------------------

_R1_IP_INTERFACE_G01 = """\
R1#show ip interface gigabitEthernet 0/1
GigabitEthernet0/1 is up, line protocol is up
  Internet address is 192.168.1.1/24
  MTU is 1500
  Helper address is not set
  Outgoing access list is not set
  Inbound  access list is not set
R1#
"""

_R1_DHCP_BINDING = """\
R1#show ip dhcp binding
Bindings from all pools not associated with VRF:
IP address       Client-ID/              Lease expiration        Type
                 Hardware address

R1#
"""

# ---- D: PC1 isolated DNS failure -------------------------------------------

_PC1_PING = """\
PC1> ping 192.168.4.20

Pinging 192.168.4.20 with 32 bytes of data:
Reply from 192.168.4.20: bytes=32 time=4ms TTL=63
Reply from 192.168.4.20: bytes=32 time=3ms TTL=63
"""

_PC1_NSLOOKUP = """\
PC1> nslookup intranet.lab.local
Server:  192.168.4.10
Address: 192.168.4.10

*** 192.168.4.10 can't find intranet.lab.local: Server failed
"""

# ---- Combined R1 logging for the timeline -----------------------------------

_R1_LOG = """\
R1#show logging
*Mar  1 00:00:45.001: %SEC-6-IPACCESSLOGP: list BLOCK_OSPF denied ospf 10.0.1.2(0) -> 224.0.0.5(0), 1 packet
*Mar  1 00:01:15.002: %OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 on GigabitEthernet0/0 from LOADING to DOWN, Neighbor Down: Dead timer expired
*Mar  1 00:02:11.500: %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch discovered on FastEthernet0/1 (1), with SW2 FastEthernet0/1 (99).
*Mar  1 00:03:55.901: %SEC-6-IPACCESSLOGP: list BLOCK_OSPF denied ospf 10.0.1.2(0) -> 224.0.0.5(0), 38 packets
R1#
"""


SCENARIO = scenario(
    name="Scenario 8 - Multi-Fault Demo (4 hidden faults)",
    description=(
        "Demo scenario with FOUR independent faults injected at once: "
        "(A) inbound ACL on R1 Gi0/0 denies OSPF multicast, "
        "(B) native VLAN mismatch (1 vs 99) on the SW1<->SW2 trunk, "
        "(C) R1 LAN interface is missing 'ip helper-address', "
        "(D) PC1 can ping the server by IP but nslookup fails (isolated DNS). "
        "The engine must surface all four as ROOT_CAUSE and suppress the "
        "secondary OSPF / DHCP-server / connectivity symptoms they produce."
    ),
    files={
        "R1_ospf_neighbor.txt": _R1_OSPF_NEIGHBOR,
        "R1_ospf_interface.txt": _R1_OSPF_INTERFACE,
        "R1_access_lists.txt": _R1_ACCESS_LISTS,
        "R1_ip_interface_g00.txt": _R1_IP_INTERFACE_G00,
        "R1_ip_interface_g01.txt": _R1_IP_INTERFACE_G01,
        "R1_dhcp_binding.txt": _R1_DHCP_BINDING,
        "R1_logging.txt": _R1_LOG,
        "SW1_trunk.txt": _SW1_TRUNK,
        "SW2_trunk.txt": _SW2_TRUNK,
        "SW1_logging.txt": _SW1_LOG,
        "PC1_ping_by_ip.txt": _PC1_PING,
        "PC1_nslookup.txt": _PC1_NSLOOKUP,
    },
    ground_truth=(
        F_HELLOS_BLOCKED_ACL,
        F_NATIVE_VLAN_MISMATCH,
        F_DHCP_HELPER_MISSING,
        F_DNS_FAILURE,
    ),
    # Any of the four CONFIG findings is a valid 'top' - we pin the ACL one
    # because it has the strongest combined evidence (correlator + combination).
    expected_top_fault=F_HELLOS_BLOCKED_ACL,
)
