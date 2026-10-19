"""Reasoning layer: pure functions, no I/O.

Public entrypoint is `pipeline.analyze`.
"""

from ospf_engine.reasoning.knowledge_base import FAULT_CATALOG, get_fault
from ospf_engine.reasoning.pipeline import analyze

__all__ = ["FAULT_CATALOG", "analyze", "get_fault"]
