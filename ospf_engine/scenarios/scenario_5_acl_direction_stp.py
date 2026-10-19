"""Scenario 5 - ACL applied in the wrong direction on R1 LAN
combined with SW2 forced as STP root with priority 0."""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import F_ACL_WRONG_DIRECTION, F_STP_WRONG_ROOT
from ospf_engine.scenarios.registry import scenario


_R1_ACCESS_LISTS = """\
R1#show access-lists
Extended IP access list WRONG_DIR
    10 permit tcp 192.168.1.0 0.0.0.255 any eq 80 (0 matches)
    20 permit tcp 192.168.1.0 0.0.0.255 any eq 443 (0 matches)
    30 deny ip any any (892 matches)
R1#
"""

_R1_IP_INTERFACE = """\
R1#show ip interface gigabitEthernet 0/1
GigabitEthernet0/1 is up, line protocol is up
  Internet address is 192.168.1.1/24
  Broadcast address is 255.255.255.255
  MTU is 1500
  Helper address is not set
  Outgoing access list is WRONG_DIR
  Inbound  access list is not set
R1#
"""

_SW1_SPANNING_TREE = """\
SW1#show spanning-tree

VLAN0001
  Spanning tree enabled protocol ieee
  Root ID    Priority    0
             Address     0090.2B6A.AAAA
             Cost        19
             Port        1 (FastEthernet0/1)
             Hello Time   2 sec  Max Age 20 sec  Forward Delay 15 sec

  Bridge ID  Priority    32769  (priority 32768 sys-id-ext 1)
             Address     00D0.BC45.BBBB
             Hello Time   2 sec  Max Age 20 sec  Forward Delay 15 sec
             Aging Time  20

Interface        Role Sts Cost      Prio.Nbr Type
---------------- ---- --- --------- -------- --------------------------------
Fa0/1            Root FWD 19        128.1    P2p
Fa0/2            Desg BLK 19        128.2    P2p

SW1#
"""

_SW1_LOG = """\
SW1#show logging
*Mar  1 00:04:01.200: %SPANTREE-5-TOPOTRAP: Topology change detected on FastEthernet0/1
*Mar  1 00:04:01.210: %SPANTREE-2-ROOTCHANGE: Root changed for vlan 1
*Mar  1 00:04:05.100: %SPANTREE-5-TOPOTRAP: Topology change detected on FastEthernet0/2
SW1#
"""


SCENARIO = scenario(
    name="Scenario 5 - ACL Direction + STP Root",
    description=(
        "An ACL meant to filter inbound is applied OUTBOUND on R1's LAN interface and is "
        "actively dropping user traffic. Independently, SW2 has been forced to STP priority 0 "
        "and has stolen the root bridge role."
    ),
    files={
        "R1_access_lists.txt": _R1_ACCESS_LISTS,
        "R1_ip_interface_g01.txt": _R1_IP_INTERFACE,
        "SW1_spanning_tree.txt": _SW1_SPANNING_TREE,
        "SW1_logging.txt": _SW1_LOG,
    },
    ground_truth=(F_ACL_WRONG_DIRECTION, F_STP_WRONG_ROOT),
    expected_top_fault=F_ACL_WRONG_DIRECTION,
)
