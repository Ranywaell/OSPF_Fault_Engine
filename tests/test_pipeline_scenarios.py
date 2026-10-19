"""End-to-end tests: every scenario must produce the expected top fault and
hit the F1 threshold."""

from __future__ import annotations

import pytest

from ospf_engine import analyze, parse_files
from ospf_engine.reporting.accuracy import check_accuracy
from ospf_engine.scenarios import ALL_SCENARIOS


_F1_THRESHOLD = 0.90  # per-scenario floor


@pytest.mark.parametrize("scenario_name", list(ALL_SCENARIOS.keys()))
def test_scenario_top_fault_is_correct(scenario_name: str) -> None:
    scenario = ALL_SCENARIOS[scenario_name]
    parse_result = parse_files(scenario.files)
    analysis = analyze(parse_result)
    assert analysis.top_fault is not None, f"{scenario_name}: no fault detected"
    assert analysis.top_fault.name == scenario.expected_top, (
        f"{scenario_name}: expected top {scenario.expected_top!r}, "
        f"got {analysis.top_fault.name!r}"
    )


@pytest.mark.parametrize("scenario_name", list(ALL_SCENARIOS.keys()))
def test_scenario_f1_above_threshold(scenario_name: str) -> None:
    scenario = ALL_SCENARIOS[scenario_name]
    parse_result = parse_files(scenario.files)
    analysis = analyze(parse_result)
    accuracy = check_accuracy(analysis, scenario.ground_truth)
    assert accuracy.f1 >= _F1_THRESHOLD, (
        f"{scenario_name}: F1={accuracy.f1:.2f} below threshold {_F1_THRESHOLD}; "
        f"FP={accuracy.false_positives}, FN={accuracy.false_negatives}"
    )


def test_average_f1_across_all_scenarios() -> None:
    total = 0.0
    n = 0
    for scenario in ALL_SCENARIOS.values():
        parse_result = parse_files(scenario.files)
        analysis = analyze(parse_result)
        total += check_accuracy(analysis, scenario.ground_truth).f1
        n += 1
    avg = total / n
    assert avg >= 0.92, f"Average F1 {avg:.2f} below 0.92"


def test_scenario_3_does_not_surface_area_or_timer_mismatch():
    """Regression test for the legacy 'side-effect bleed' bug."""
    scenario = ALL_SCENARIOS["Scenario 3 - OSPF Hellos Blocked by ACL"]
    parse_result = parse_files(scenario.files)
    analysis = analyze(parse_result)
    detected_names = {f.name for f in analysis.ranked_faults}
    assert "OSPF Area Mismatch" not in detected_names
    assert "OSPF Timer Mismatch" not in detected_names


def test_scenario_2_correctly_picks_timer_not_area():
    """Regression test for legacy bug: benchmark.py wrongly picked Area Mismatch."""
    scenario = ALL_SCENARIOS["Scenario 2 - OSPF Timer Mismatch"]
    parse_result = parse_files(scenario.files)
    analysis = analyze(parse_result)
    assert analysis.top_fault is not None
    assert analysis.top_fault.name == "OSPF Timer Mismatch"
    assert analysis.top_fault.confidence >= 0.85
