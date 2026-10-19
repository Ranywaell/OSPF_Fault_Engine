"""Result models returned by the reasoning pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ospf_engine.models.evidence import Evidence, EvidenceLevel


CLASSIFICATION_ROOT_CAUSE = "ROOT_CAUSE"
CLASSIFICATION_LIKELY_ROOT = "LIKELY_ROOT_CAUSE"
CLASSIFICATION_CONTRIBUTING = "CONTRIBUTING_FACTOR"
CLASSIFICATION_SIDE_EFFECT = "SIDE_EFFECT"
CLASSIFICATION_POSSIBLE = "POSSIBLE_CAUSE"


@dataclass(slots=True)
class ScoredFault:
    """A fault that the reasoner considers plausible, with confidence + evidence."""

    name: str
    category: str
    cause: str
    verify: tuple[str, ...]
    fix: str

    confidence: float
    """0.0-1.0 confidence. Tier-driven (see reasoning/scorer.py)."""

    best_evidence_level: EvidenceLevel
    classification: str  # one of CLASSIFICATION_*
    label: str  # short human label: 'Confirmed Cause', 'Likely Cause', 'Possible Cause'

    supporting_evidence: list[Evidence] = field(default_factory=list)
    evidence_summary: dict[str, int] = field(default_factory=dict)
    """Counts of evidence by level: {'CONFIG': 1, 'STRONG': 2, ...}"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "cause": self.cause,
            "verify": list(self.verify),
            "fix": self.fix,
            "confidence": round(self.confidence, 2),
            "best_evidence_level": self.best_evidence_level.value,
            "classification": self.classification,
            "label": self.label,
            "supporting_evidence": [e.to_dict() for e in self.supporting_evidence],
            "evidence_summary": dict(self.evidence_summary),
        }


@dataclass(slots=True)
class ConsideredFault:
    """A fault the reasoner explicitly considered and ruled out (or suppressed)."""

    name: str
    reason: str


@dataclass(slots=True)
class FixStep:
    step: int
    fault: str
    classification: str
    confidence: float
    fix: str
    verify: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "fault": self.fault,
            "classification": self.classification,
            "confidence": round(self.confidence, 2),
            "fix": self.fix,
            "verify": list(self.verify),
        }


@dataclass(slots=True)
class AnalysisResult:
    """The full output of `pipeline.analyze`."""

    evidence: list[Evidence] = field(default_factory=list)
    ranked_faults: list[ScoredFault] = field(default_factory=list)
    fix_path: list[FixStep] = field(default_factory=list)
    considered_and_ruled_out: list[ConsideredFault] = field(default_factory=list)
    uncertain: bool = False
    verification_note: str | None = None
    diagnosis_chain: list[str] = field(default_factory=list)
    """Ordered narrative explaining how the engine reached its conclusion."""

    @property
    def top_fault(self) -> ScoredFault | None:
        return self.ranked_faults[0] if self.ranked_faults else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": [e.to_dict() for e in self.evidence],
            "ranked_faults": [f.to_dict() for f in self.ranked_faults],
            "fix_path": [s.to_dict() for s in self.fix_path],
            "considered_and_ruled_out": [
                {"name": c.name, "reason": c.reason} for c in self.considered_and_ruled_out
            ],
            "uncertain": self.uncertain,
            "verification_note": self.verification_note,
            "diagnosis_chain": list(self.diagnosis_chain),
        }
