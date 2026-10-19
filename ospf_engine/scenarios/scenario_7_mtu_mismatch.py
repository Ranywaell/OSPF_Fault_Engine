"""Scenario 7 - OSPF MTU mismatch.

Hellos succeed but DBD exchange fails because one side has MTU 1500 and the
other 1400. Adjacency hangs in EXSTART/EXCHANGE - a classic MTU symptom.
"""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import F_MTU_MISMATCH
from ospf_engine.scenarios.registry import scenario


_R3_OSPF_NEIGHBOR = """\
R3#show ip ospf neighbor

Neighbor ID     Pri   State           Dead Time   Address         Interface
4.4.4.4          1   EXSTART/DR      00:00:35    10.0.3.2        GigabitEthernet0/1
R3#
"""

_R3_OSPF_INTERFACE = """\
R3#show ip ospf interface gigabitEthernet 0/1
GigabitEthernet0/1 is up, line protocol is up
  Internet Address 10.0.3.1/30, Area 0
  Process ID 1, Router ID 3.3.3.3, Network Type BROADCAST, Cost: 1
  MTU 1500
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  Neighbor Count is 1, Adjacent neighbor count is 0
R3#
"""

_R4_OSPF_INTERFACE = """\
R4#show ip ospf interface gigabitEthernet 0/0
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.3.2/30, Area 0
  Process ID 1, Router ID 4.4.4.4, Network Type BROADCAST, Cost: 1
  MTU 1400
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  Neighbor Count is 1, Adjacent neighbor count is 0
R4#
"""

_R3_LOG = """\
R3#show logging
*Mar  1 00:05:10.111: %OSPF-4-ERRRCV: Received invalid packet: Mismatched hello parameters from 10.0.3.2 (ID 4.4.4.4) on GigabitEthernet0/1
*Mar  1 00:05:25.222: %OSPF-5-ADJCHG: Process 1, Nbr 4.4.4.4 on GigabitEthernet0/1 from EXCHANGE to DOWN, Neighbor Down: Too many retransmissions
R3#
"""


SCENARIO = scenario(
    name="Scenario 7 - OSPF MTU Mismatch",
    description=(
        "R3 (MTU 1500) and R4 (MTU 1400) on the same /30. Hellos succeed but DBD packets "
        "are dropped - adjacency hangs in EXSTART/EXCHANGE."
    ),
    files={
        "R3_ospf_neighbor.txt": _R3_OSPF_NEIGHBOR,
        "R3_ospf_interface.txt": _R3_OSPF_INTERFACE,
        "R4_ospf_interface.txt": _R4_OSPF_INTERFACE,
        "R3_logging.txt": _R3_LOG,
    },
    ground_truth=(F_MTU_MISMATCH,),
)
