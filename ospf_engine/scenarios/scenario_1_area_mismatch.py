"""Scenario 1 - OSPF Area Mismatch on R1<->R2 link."""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import F_AREA_MISMATCH
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
  Neighbor Count is 0, Adjacent neighbor count is 0
GigabitEthernet0/1 is up, line protocol is up
  Internet Address 192.168.1.1/24, Area 0
  Process ID 1, Router ID 1.1.1.1, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
R1#
"""

_R2_OSPF_INTERFACE = """\
R2#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.1.2/30, Area 1
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  Neighbor Count is 0, Adjacent neighbor count is 0
R2#
"""

_R1_LOG = """\
R1#show logging
*Mar  1 00:01:04.123: %OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 on GigabitEthernet0/0 from LOADING to DOWN, Neighbor Down: Dead timer expired
*Mar  1 00:01:44.456: %OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 on GigabitEthernet0/0 from INIT to DOWN, Neighbor Down: Dead timer expired
R1#
"""

_R1_ROUTE = """\
R1#show ip route
Codes: C - connected, S - static, I - IGRP, R - RIP, M - mobile, B - BGP
       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area

Gateway of last resort is not set

C    10.0.1.0/30 is directly connected, GigabitEthernet0/0
C    192.168.1.0/24 is directly connected, GigabitEthernet0/1
R1#
"""


SCENARIO = scenario(
    name="Scenario 1 - OSPF Area Mismatch",
    description="R1 (Area 0) and R2 (Area 1) on the same /30 link. Adjacency never forms.",
    files={
        "R1_ospf_neighbor.txt": _R1_OSPF_NEIGHBOR,
        "R1_ospf_interface.txt": _R1_OSPF_INTERFACE,
        "R2_ospf_interface.txt": _R2_OSPF_INTERFACE,
        "R1_logging.txt": _R1_LOG,
        "R1_ip_route.txt": _R1_ROUTE,
    },
    ground_truth=(F_AREA_MISMATCH,),
)
