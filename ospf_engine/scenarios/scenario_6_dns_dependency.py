"""Scenario 6 - DNS dependency failure.

The user reports 'I can't reach the website by name'. The PC has a DHCP-issued
address, can ping the web server's IP, but nslookup fails. This is a
classic DNS-only failure - L3 reachability is fine, DNS service is broken.
"""

from __future__ import annotations

from ospf_engine.reasoning.knowledge_base import F_DNS_FAILURE
from ospf_engine.scenarios.registry import scenario


_PC_IPCONFIG = """\
PC1> ipconfig /all

Windows IP Configuration

  Physical Address. . . . . . . . . : 00-D0-AB-12-34-56
  IP Address. . . . . . . . . . . . : 192.168.1.50
  Subnet Mask . . . . . . . . . . . : 255.255.255.0
  Default Gateway . . . . . . . . . : 192.168.1.1
  DNS Servers . . . . . . . . . . . : 192.168.4.10
"""

_PC_PING_BY_IP = """\
PC1> ping 192.168.4.20

Pinging 192.168.4.20 with 32 bytes of data:
Reply from 192.168.4.20: bytes=32 time=4ms TTL=63
Reply from 192.168.4.20: bytes=32 time=3ms TTL=63
Reply from 192.168.4.20: bytes=32 time=4ms TTL=63
Reply from 192.168.4.20: bytes=32 time=3ms TTL=63

Ping statistics for 192.168.4.20:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
"""

_PC_NSLOOKUP = """\
PC1> nslookup web.lab.local
Server:  192.168.4.10
Address: 192.168.4.10

*** 192.168.4.10 can't find web.lab.local: Server failed
"""

_R1_OSPF_NEIGHBOR = """\
R1#show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
2.2.2.2          1   FULL/DR         00:00:35    10.0.1.2        GigabitEthernet0/0
4.4.4.4          1   FULL/BDR        00:00:31    10.0.3.2        GigabitEthernet0/2
R1#
"""

_R1_ROUTE = """\
R1#show ip route
Codes: C - connected, O - OSPF, IA - OSPF inter area
Gateway of last resort is not set

C    10.0.1.0/30 is directly connected, GigabitEthernet0/0
C    192.168.1.0/24 is directly connected, GigabitEthernet0/1
O IA 192.168.4.0/24 [110/3] via 10.0.1.2, 00:10:22, GigabitEthernet0/0
R1#
"""


SCENARIO = scenario(
    name="Scenario 6 - DNS Dependency Failure",
    description=(
        "PC has a valid IP, can ping the server by IP, but nslookup fails. Underlying "
        "routing/OSPF are healthy. This is a DNS-only fault."
    ),
    files={
        "PC1_ipconfig.txt": _PC_IPCONFIG,
        "PC1_ping_by_ip.txt": _PC_PING_BY_IP,
        "PC1_nslookup.txt": _PC_NSLOOKUP,
        "R1_ospf_neighbor.txt": _R1_OSPF_NEIGHBOR,
        "R1_ip_route.txt": _R1_ROUTE,
    },
    ground_truth=(F_DNS_FAILURE,),
)
