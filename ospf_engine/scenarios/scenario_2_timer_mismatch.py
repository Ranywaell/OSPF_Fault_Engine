"""Scenario 2 - OSPF hello/dead timer mismatch on R2<->R3 link."""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import F_TIMER_MISMATCH
from ospf_engine.scenarios.registry import scenario


_R2_OSPF_INTERFACE = """\
R2#show ip ospf interface
GigabitEthernet0/1 is up, line protocol is up
  Internet Address 10.0.2.1/30, Area 0
  Process ID 1, Router ID 2.2.2.2, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  Neighbor Count is 0, Adjacent neighbor count is 0
R2#
"""

_R3_OSPF_INTERFACE = """\
R3#show ip ospf interface
GigabitEthernet0/0 is up, line protocol is up
  Internet Address 10.0.2.2/30, Area 0
  Process ID 1, Router ID 3.3.3.3, Network Type BROADCAST, Cost: 1
  Timer intervals configured, Hello 20, Dead 80, Wait 80, Retransmit 5
  Neighbor Count is 0, Adjacent neighbor count is 0
R3#
"""

_R2_OSPF_NEIGHBOR = """\
R2#show ip ospf neighbor

Neighbor ID     Pri   State           Dead Time   Address         Interface

R2#
"""

_R2_LOG = """\
R2#show logging
*Mar  1 00:03:22.111: %OSPF-5-ADJCHG: Process 1, Nbr 3.3.3.3 on GigabitEthernet0/1 from FULL to DOWN, Neighbor Down: Dead timer expired
*Mar  1 00:04:02.222: %OSPF-5-ADJCHG: Process 1, Nbr 3.3.3.3 on GigabitEthernet0/1 from INIT to DOWN, Neighbor Down: Dead timer expired
R2#
"""


SCENARIO = scenario(
    name="Scenario 2 - OSPF Timer Mismatch",
    description=(
        "R2 (hello 10 / dead 40) vs R3 (hello 20 / dead 80) on the same link. "
        "Neighbor flaps and the dead timer expires."
    ),
    files={
        "R2_ospf_interface.txt": _R2_OSPF_INTERFACE,
        "R3_ospf_interface.txt": _R3_OSPF_INTERFACE,
        "R2_ospf_neighbor.txt": _R2_OSPF_NEIGHBOR,
        "R2_logging.txt": _R2_LOG,
    },
    ground_truth=(F_TIMER_MISMATCH,),
)
