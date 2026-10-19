"""Accuracy metrics for the benchmark.

Compares an :class:`AnalysisResult` against a ground-truth tuple of canonical
fault names. The previous implementation counted *every* ranked fault as a
detection (including weak, suppressed alternatives), which inflated false
positives. The new metric only counts faults that the engine actually
surfaced as ROOT_CAUSE / LIKELY_ROOT_CAUSE / CONTRIBUTING_FACTOR.
"""

from __future__ import annotations

from dataclasses import dataclass

from ospf_engine.models import AnalysisResult
from ospf_engine.models.analysis import (
    CLASSIFICATION_CONTRIBUTING,
    CLASSIFICATION_LIKELY_ROOT,
    CLASSIFICATION_ROOT_CAUSE,
)


_DETECTION_CLASSIFICATIONS = {
    CLASSIFICATION_ROOT_CAUSE,
    CLASSIFICATION_LIKELY_ROOT,
    CLASSIFICATION_CONTRIBUTING,
}


@dataclass(slots=True)
class AccuracyMetrics:
    true_positives: list[str]
    false_positives: list[str]
    false_negatives: list[str]
    precision: float
    recall: float
    f1: float

    def to_dict(self) -> dict:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 2),
            "recall": round(self.recall, 2),
            "f1": round(self.f1, 2),
        }


def check_accuracy(
    analysis: AnalysisResult, ground_truth: tuple[str, ...]
) -> AccuracyMetrics:
    """Compute precision / recall / F1 against ground-truth fault names."""
    detected = {
        f.name
        for f in analysis.ranked_faults
        if f.classification in _DETECTION_CLASSIFICATIONS
    }
    truth = set(ground_truth)

    tp = sorted(detected & truth)
    fp = sorted(detected - truth)
    fn = sorted(truth - detected)

    precision = len(tp) / len(detected) if detected else 0.0
    recall = len(tp) / len(truth) if truth else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )

    return AccuracyMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 2),
        recall=round(recall, 2),
        f1=round(f1, 2),
    )
