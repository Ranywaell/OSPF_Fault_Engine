"""Build a dependency-aware ordered fix path.

If fault X declares ``fix_dependencies = (Y,)`` in the knowledge base, Y must
be repaired before X. The planner topologically sorts the kept faults so the
operator fixes prerequisites first.
"""

from __future__ import annotations

from ospf_engine.models import ScoredFault
from ospf_engine.models.analysis import FixStep
from ospf_engine.reasoning.knowledge_base import FAULT_CATALOG


def _sort_by_dependencies(faults: list[ScoredFault]) -> list[ScoredFault]:
    """Stable topological sort - keeps original order on ties (which is by confidence)."""
    name_to_fault = {f.name: f for f in faults}
    ordered: list[ScoredFault] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def _visit(name: str) -> None:
        if name in visited or name not in name_to_fault:
            return
        if name in visiting:
            # Cycle - bail out to avoid infinite recursion. Keep insertion order.
            return
        visiting.add(name)
        kb = FAULT_CATALOG.get(name)
        if kb is not None:
            for dep in kb.fix_dependencies:
                _visit(dep)
        visiting.discard(name)
        visited.add(name)
        ordered.append(name_to_fault[name])

    for f in faults:
        _visit(f.name)
    return ordered


def build_fix_path(faults: list[ScoredFault]) -> list[FixStep]:
    ordered = _sort_by_dependencies(faults)
    steps: list[FixStep] = []
    for i, fault in enumerate(ordered, start=1):
        steps.append(
            FixStep(
                step=i,
                fault=fault.name,
                classification=fault.classification,
                confidence=fault.confidence,
                fix=fault.fix,
                verify=fault.verify,
            )
        )
    return steps
