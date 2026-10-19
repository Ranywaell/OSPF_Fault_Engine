"""CET361 OSPF Fault Engine — package root.

Public entrypoints:
    from ospf_engine import analyze, parse_files
    from ospf_engine.scenarios import ALL_SCENARIOS
"""

from __future__ import annotations

from ospf_engine.parsers.dispatcher import parse_files
from ospf_engine.reasoning.pipeline import analyze
from ospf_engine.models.analysis import AnalysisResult, ScoredFault, FixStep
from ospf_engine.models.evidence import Evidence, EvidenceLevel
from ospf_engine.models.fault import Fault, FaultCategory

__version__ = "2.0.0"

__all__ = [
    "analyze",
    "parse_files",
    "AnalysisResult",
    "ScoredFault",
    "FixStep",
    "Evidence",
    "EvidenceLevel",
    "Fault",
    "FaultCategory",
    "__version__",
]
