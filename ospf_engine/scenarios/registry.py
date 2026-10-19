"""Scenario registry.

Each scenario module exposes a top-level ``SCENARIO`` of type :class:`Scenario`.
The registry simply imports them and exposes a name-keyed dict that the UI and
the benchmark CLI consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Scenario:
    """A pre-built test scenario with simulated device outputs and ground truth."""

    name: str
    description: str
    files: dict[str, str]
    ground_truth: tuple[str, ...]
    """Canonical fault names (matching FAULT_CATALOG keys) that should be detected."""

    expected_top_fault: str | None = None
    """Optional: which fault must rank #1 (defaults to ground_truth[0])."""

    @property
    def expected_top(self) -> str:
        return self.expected_top_fault or self.ground_truth[0]


def scenario(**kwargs) -> Scenario:
    """Convenience constructor for scenario modules."""
    return Scenario(**kwargs)


# Importing the scenario modules registers them.
from ospf_engine.scenarios import (  # noqa: E402
    scenario_1_area_mismatch,
    scenario_2_timer_mismatch,
    scenario_3_acl_blocks_ospf,
    scenario_4_native_vlan_dhcp,
    scenario_5_acl_direction_stp,
    scenario_6_dns_dependency,
    scenario_7_mtu_mismatch,
    scenario_8_multi_fault_demo,
)


_SCENARIOS: list[Scenario] = [
    scenario_1_area_mismatch.SCENARIO,
    scenario_2_timer_mismatch.SCENARIO,
    scenario_3_acl_blocks_ospf.SCENARIO,
    scenario_4_native_vlan_dhcp.SCENARIO,
    scenario_5_acl_direction_stp.SCENARIO,
    scenario_6_dns_dependency.SCENARIO,
    scenario_7_mtu_mismatch.SCENARIO,
    scenario_8_multi_fault_demo.SCENARIO,
]


ALL_SCENARIOS: dict[str, Scenario] = {s.name: s for s in _SCENARIOS}
