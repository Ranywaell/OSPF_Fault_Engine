"""Typed domain models. No I/O, no logic — just data shapes."""

from ospf_engine.models.analysis import AnalysisResult, ConsideredFault, FixStep, ScoredFault
from ospf_engine.models.evidence import Evidence, EvidenceLevel
from ospf_engine.models.fault import Fault, FaultCategory
from ospf_engine.models.topology import (
    ParsedAcl,
    ParsedAclApplication,
    ParsedDhcpBinding,
    ParsedDnsResult,
    ParsedHelperAddress,
    ParsedInterface,
    ParsedNeighbor,
    ParsedStpVlan,
    ParsedTrunk,
    TopologyFacts,
)

__all__ = [
    "AnalysisResult",
    "ConsideredFault",
    "Evidence",
    "EvidenceLevel",
    "Fault",
    "FaultCategory",
    "FixStep",
    "ParsedAcl",
    "ParsedAclApplication",
    "ParsedDhcpBinding",
    "ParsedDnsResult",
    "ParsedHelperAddress",
    "ParsedInterface",
    "ParsedNeighbor",
    "ParsedStpVlan",
    "ParsedTrunk",
    "ScoredFault",
    "TopologyFacts",
]
