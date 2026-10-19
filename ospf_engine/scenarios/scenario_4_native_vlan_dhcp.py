"""Scenario 4 - Native VLAN mismatch on the SW1<->SW2 trunk
combined with a missing DHCP helper-address on R1's LAN interface."""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import (
    F_DHCP_HELPER_MISSING,
    F_NATIVE_VLAN_MISMATCH,
)
from ospf_engine.scenarios.registry import scenario


_SW1_TRUNK = """\
SW1#show interfaces trunk

Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      1
Fa0/2       on           802.1q         trunking      1

Port        Vlans allowed on trunk
Fa0/1       1-1005
Fa0/2       1-1005
SW1#
"""

_SW2_TRUNK = """\
SW2#show interfaces trunk

Port        Mode         Encapsulation  Status        Native vlan
Fa0/1       on           802.1q         trunking      10
Fa0/2       on           802.1q         trunking      10

Port        Vlans allowed on trunk
Fa0/1       1-1005
Fa0/2       1-1005
SW2#
"""

_SW1_LOG = """\
SW1#show logging
*Mar  1 00:02:11.500: %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch discovered on FastEthernet0/1 (1), with SW2 FastEthernet0/1 (10).
*Mar  1 00:02:11.510: %SPANTREE-2-RECV_PVST_BPDU: Received PVST BPDU on non trunk FastEthernet0/1 VLAN 10
SW1#
"""

_R1_IP_INTERFACE = """\
R1#show ip interface gigabitEthernet 0/1
GigabitEthernet0/1 is up, line protocol is up
  Internet address is 192.168.1.1/24
  Broadcast address is 255.255.255.255
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


SCENARIO = scenario(
    name="Scenario 4 - Native VLAN + DHCP Relay",
    description=(
        "SW1 native VLAN 1 vs SW2 native VLAN 10 on the inter-switch trunk, AND R1 is "
        "missing 'ip helper-address' on the LAN interface. Both faults are independent."
    ),
    files={
        "SW1_trunk.txt": _SW1_TRUNK,
        "SW2_trunk.txt": _SW2_TRUNK,
        "SW1_logging.txt": _SW1_LOG,
        "R1_ip_interface_g01.txt": _R1_IP_INTERFACE,
        "R1_dhcp_binding.txt": _R1_DHCP_BINDING,
    },
    ground_truth=(F_NATIVE_VLAN_MISMATCH, F_DHCP_HELPER_MISSING),
    expected_top_fault=F_NATIVE_VLAN_MISMATCH,
)
