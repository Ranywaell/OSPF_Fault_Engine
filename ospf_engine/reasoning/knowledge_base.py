"""Static fault knowledge base.

This is a typed, in-memory, read-only catalog. It replaces the previous
SQLite-backed ``engine/db.py`` - eight static facts do not need a database.

Each entry encodes:
  * ``cause``           - the *why* in plain network-engineer language
  * ``verify``          - safe, read-only commands that prove or disprove this fault
  * ``fix``             - the safe corrective configuration (NEVER applied automatically)
  * ``fix_dependencies`` - faults that must be repaired BEFORE this one (used by the
    fix-planner so an operator removes the L2 native-VLAN issue before chasing the
    L3 OSPF flapping it caused, etc.)
"""

from __future__ import annotations

from ospf_engine.models import Fault, FaultCategory


# Canonical fault names - reuse these constants everywhere to avoid string typos.
F_AREA_MISMATCH = "OSPF Area Mismatch"
F_TIMER_MISMATCH = "OSPF Timer Mismatch"
F_HELLOS_BLOCKED_ACL = "OSPF Hellos Blocked by ACL"
F_NETWORK_TYPE_MISMATCH = "OSPF Network Type Mismatch"
F_MTU_MISMATCH = "OSPF MTU Mismatch"
F_DUPLICATE_ROUTER_ID = "OSPF Duplicate Router-ID"
F_ACL_WRONG_DIRECTION = "ACL Wrong Direction"
F_NATIVE_VLAN_MISMATCH = "Native VLAN Mismatch"
F_STP_WRONG_ROOT = "STP Topology Change / Wrong Root"
F_DHCP_HELPER_MISSING = "Missing DHCP Helper Address"
F_DHCP_SERVER_UNREACHABLE = "DHCP Server Unreachable"
F_DNS_FAILURE = "DNS Resolution Failure"


_FAULTS: list[Fault] = [
    Fault(
        name=F_AREA_MISMATCH,
        category=FaultCategory.OSPF,
        cause=(
            "The OSPF area ID configured on one end of a link does not match the area on "
            "the other end. OSPF requires both ends of a link to agree on the area number; "
            "if they disagree, hellos are received but the adjacency state machine cannot "
            "progress past INIT - no LSAs are exchanged and no routes are learned."
        ),
        verify=(
            "show ip ospf interface",
            "show ip ospf neighbor",
            "show running-config | section router ospf",
        ),
        fix=(
            "Align the area ID on both ends. On whichever side is wrong:\n"
            "  Rx(config)# router ospf 1\n"
            "  Rx(config-router)# no network <subnet> <wildcard> area <wrong_area>\n"
            "  Rx(config-router)# network <subnet> <wildcard> area <correct_area>"
        ),
    ),
    Fault(
        name=F_TIMER_MISMATCH,
        category=FaultCategory.OSPF,
        cause=(
            "The OSPF Hello and/or Dead intervals differ between two peers on the same "
            "link. IOS requires identical timers for adjacency to form; mismatched timers "
            "cause the dead timer to expire and the neighbor to be declared down."
        ),
        verify=(
            "show ip ospf interface <interface>",
            "show ip ospf neighbor detail",
        ),
        fix=(
            "Restore matching timers (defaults: hello 10, dead 40 on broadcast):\n"
            "  Rx(config-if)# ip ospf hello-interval 10\n"
            "  Rx(config-if)# ip ospf dead-interval 40"
        ),
    ),
    Fault(
        name=F_HELLOS_BLOCKED_ACL,
        category=FaultCategory.OSPF,
        cause=(
            "An inbound ACL on an OSPF-enabled interface is denying OSPF hello packets "
            "(IP protocol 89 to 224.0.0.5 / 224.0.0.6). Without hellos no neighbor is "
            "ever discovered, so adjacency cannot form and the routing table stays empty "
            "for OSPF-learned destinations."
        ),
        verify=(
            "show access-lists",
            "show ip interface <interface>",
            "show ip ospf neighbor",
        ),
        fix=(
            "Permit OSPF before any deny, or remove the offending ACL from the interface:\n"
            "  Rx(config)# ip access-list extended <NAME>\n"
            "  Rx(config-ext-nacl)# 5 permit ospf any host 224.0.0.5\n"
            "  Rx(config-ext-nacl)# 6 permit ospf any host 224.0.0.6\n"
            "  Rx(config-ext-nacl)# 7 permit ospf any any\n"
            "OR remove the ACL application:\n"
            "  Rx(config-if)# no ip access-group <NAME> in"
        ),
    ),
    Fault(
        name=F_NETWORK_TYPE_MISMATCH,
        category=FaultCategory.OSPF,
        cause=(
            "OSPF network type differs on each end of a link (e.g. broadcast vs. "
            "point-to-point). DR/BDR election and adjacency progression cannot complete; "
            "neighbors stick at 2WAY."
        ),
        verify=(
            "show ip ospf interface",
            "show ip ospf neighbor detail",
        ),
        fix=(
            "Set both ends to the same network type:\n"
            "  Rx(config-if)# ip ospf network point-to-point"
        ),
    ),
    Fault(
        name=F_MTU_MISMATCH,
        category=FaultCategory.OSPF,
        cause=(
            "MTU differs across the link. Hellos succeed (small) but the DBD exchange "
            "fails because oversized packets are dropped. Adjacency hangs in EXSTART/"
            "EXCHANGE."
        ),
        verify=(
            "show ip ospf interface <interface>",
            "show interface <interface> | include MTU",
            "show ip ospf neighbor detail",
        ),
        fix=(
            "Either match MTU on both ends or tell OSPF to ignore the mismatch:\n"
            "  Rx(config-if)# mtu 1500\n"
            "OR (only as a workaround):\n"
            "  Rx(config-if)# ip ospf mtu-ignore"
        ),
    ),
    Fault(
        name=F_DUPLICATE_ROUTER_ID,
        category=FaultCategory.OSPF,
        cause=(
            "Two routers in the same OSPF domain are using the same router-ID. The "
            "duplicate ID prevents adjacencies from going FULL and corrupts the LSDB."
        ),
        verify=(
            "show ip ospf",
            "show ip ospf neighbor detail",
        ),
        fix=(
            "Set unique router-IDs:\n"
            "  Rx(config)# router ospf 1\n"
            "  Rx(config-router)# router-id <unique-id>\n"
            "  Rx# clear ip ospf process"
        ),
    ),
    Fault(
        name=F_ACL_WRONG_DIRECTION,
        category=FaultCategory.ACL,
        cause=(
            "An ACL is applied in the wrong direction (e.g. outbound on the LAN-facing "
            "interface when the intent was to filter ingress). Legitimate user traffic is "
            "being filtered at the wrong point in the forwarding path."
        ),
        verify=(
            "show ip interface <interface>",
            "show access-lists",
            "show running-config interface <interface>",
        ),
        fix=(
            "Re-apply the ACL in the correct direction:\n"
            "  Rx(config-if)# no ip access-group <NAME> out\n"
            "  Rx(config-if)# ip access-group <NAME> in"
        ),
    ),
    Fault(
        name=F_NATIVE_VLAN_MISMATCH,
        category=FaultCategory.STP_VLAN,
        cause=(
            "Two ends of an 802.1Q trunk are configured with different native VLANs. "
            "Untagged frames are placed in the wrong VLAN on the receiving switch, BPDUs "
            "leak between VLANs, and STP topology changes / loops can result."
        ),
        verify=(
            "show interfaces trunk",
            "show running-config interface <trunk>",
            "show spanning-tree",
        ),
        fix=(
            "Set the native VLAN identically on both ends of the trunk:\n"
            "  SW1(config-if)# switchport trunk native vlan 1\n"
            "  SW2(config-if)# switchport trunk native vlan 1"
        ),
        fix_dependencies=(),
    ),
    Fault(
        name=F_STP_WRONG_ROOT,
        category=FaultCategory.STP_VLAN,
        cause=(
            "An unintended switch has been elected STP root because its bridge ID is "
            "lower than the switch you intended to be root. Forwarding paths become "
            "suboptimal, and a topology change can transiently black-hole traffic."
        ),
        verify=(
            "show spanning-tree",
            "show spanning-tree root",
            "show spanning-tree detail",
        ),
        fix=(
            "Force the correct switch to be root with a deterministic priority:\n"
            "  CoreSW(config)# spanning-tree vlan 1 root primary\n"
            "or:\n"
            "  CoreSW(config)# spanning-tree vlan 1 priority 4096"
        ),
        # Native VLAN mismatch causes STP topology changes - fix L2 first.
        fix_dependencies=(F_NATIVE_VLAN_MISMATCH,),
    ),
    Fault(
        name=F_DHCP_HELPER_MISSING,
        category=FaultCategory.DHCP,
        cause=(
            "The router interface that separates DHCP clients from the DHCP server is "
            "missing 'ip helper-address'. DHCP Discover broadcasts cannot cross the "
            "router so clients never receive an address."
        ),
        verify=(
            "show ip interface <client-facing-interface>",
            "show running-config interface <client-facing-interface>",
            "show ip dhcp binding",
        ),
        fix=(
            "Add the helper on the client-facing interface (use the DHCP server's IP):\n"
            "  Rx(config-if)# ip helper-address <dhcp-server-ip>"
        ),
    ),
    Fault(
        name=F_DHCP_SERVER_UNREACHABLE,
        category=FaultCategory.DHCP,
        cause=(
            "The helper-address is correctly configured but the DHCP server is "
            "unreachable (no route, blocked by ACL, or the server itself is down)."
        ),
        verify=(
            "ping <dhcp-server-ip>",
            "show ip route <dhcp-server-ip>",
            "show access-lists",
        ),
        fix=(
            "Restore L3 reachability to the DHCP server (routing or ACL fix), or bring "
            "the DHCP server service back online."
        ),
    ),
    Fault(
        name=F_DNS_FAILURE,
        category=FaultCategory.DNS,
        cause=(
            "Hosts can reach destinations by IP but cannot resolve names. Either the "
            "configured DNS server is unreachable, the wrong server is configured on "
            "clients, or the DNS service itself is failing. This is a DNS-only failure - "
            "the underlying network path is healthy."
        ),
        verify=(
            "nslookup <hostname>",
            "ping <dns-server-ip>",
            "ipconfig /all  (Windows) or cat /etc/resolv.conf  (Linux)",
        ),
        fix=(
            "Point clients at a reachable DNS server, or bring the DNS server back online. "
            "Verify DHCP option 6 (DNS server) on the relay/server."
        ),
    ),
]


FAULT_CATALOG: dict[str, Fault] = {f.name: f for f in _FAULTS}


def get_fault(name: str) -> Fault | None:
    return FAULT_CATALOG.get(name)
