"""Benchmark scenarios. Each scenario carries simulated CLI outputs and the
ground-truth fault names the engine should identify."""

from ospf_engine.scenarios.registry import ALL_SCENARIOS, Scenario, scenario

__all__ = ["ALL_SCENARIOS", "Scenario", "scenario"]
