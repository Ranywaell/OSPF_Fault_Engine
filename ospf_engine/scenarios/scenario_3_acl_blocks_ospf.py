"""Scenario 3 - ACL on R1's link to R2 denies OSPF multicast inbound."""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import F_HELLOS_BLOCKED_ACL
from ospf_engine.scenarios.registry import scenario


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
R1#
"""

_R1_ACCESS_LISTS = """\
R1#show access-lists
Extended IP access list BLOCK_OSPF
    10 deny ospf any host 224.0.0.5 (342 matches)
    20 deny ospf any host 224.0.0.6 (128 matches)
    30 permit ip any any (1204 matches)
R1#
"""

_R1_IP_INTERFACE = """\
R1#show ip interface gigabitEthernet 0/0
GigabitEthernet0/0 is up, line protocol is up
  Internet address is 10.0.1.1/30
  Broadcast address is 255.255.255.255
  MTU is 1500
  Helper address is not set
  Outgoing access list is not set
  Inbound  access list is BLOCK_OSPF
  Proxy ARP is enabled
R1#
"""

_R1_LOG = """\
R1#show logging
*Mar  1 00:00:45.001: %SEC-6-IPACCESSLOGP: list BLOCK_OSPF denied ospf 10.0.1.2(0) -> 224.0.0.5(0), 1 packet
*Mar  1 00:01:15.002: %OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 on GigabitEthernet0/0 from LOADING to DOWN, Neighbor Down: Dead timer expired
*Mar  1 00:01:55.003: %SEC-6-IPACCESSLOGP: list BLOCK_OSPF denied ospf 10.0.1.2(0) -> 224.0.0.5(0), 38 packets
R1#
"""


SCENARIO = scenario(
    name="Scenario 3 - OSPF Hellos Blocked by ACL",
    description=(
        "Inbound ACL on R1 Gi0/0 denies OSPF multicast (224.0.0.5/6). Hellos are dropped "
        "and adjacency cannot form."
    ),
    files={
        "R1_ospf_neighbor.txt": _R1_OSPF_NEIGHBOR,
        "R1_ospf_interface.txt": _R1_OSPF_INTERFACE,
        "R1_access_lists.txt": _R1_ACCESS_LISTS,
        "R1_ip_interface_g00.txt": _R1_IP_INTERFACE,
        "R1_logging.txt": _R1_LOG,
    },
    ground_truth=(F_HELLOS_BLOCKED_ACL,),
)
