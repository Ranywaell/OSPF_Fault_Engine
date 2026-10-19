"""Run the engine across every benchmark scenario and print/save a report.

Usage::

    python run_benchmark.py             # run all, save data/benchmark_report.txt
    python run_benchmark.py --json      # emit JSON
    python run_benchmark.py --threshold 0.9   # exit code != 0 if avg F1 below threshold
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make local imports work when launched from any CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ospf_engine import analyze, parse_files
from ospf_engine.reporting.accuracy import check_accuracy
from ospf_engine.reporting.text_report import generate_text_report
from ospf_engine.scenarios import ALL_SCENARIOS


_REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_REPORT_PATH = os.path.join(_REPORT_DIR, "benchmark_report.txt")
_DIVIDER = "=" * 70


def _run_all() -> tuple[list[str], list[dict], float, int]:
    text_lines: list[str] = []
    json_rows: list[dict] = []
    text_lines.append(_DIVIDER)
    text_lines.append("   OSPF FAULT ENGINE  -  BENCHMARK RESULTS  (CET361)")
    text_lines.append(_DIVIDER)
    text_lines.append("  Accuracy below is measured on the bundled benchmark scenarios only.")
    text_lines.append("")

    total_f1 = 0.0
    correct_top = 0
    n = 0

    for name, scenario in ALL_SCENARIOS.items():
        n += 1
        text_lines.append("-" * 70)
        text_lines.append(f"  {name}")
        text_lines.append(f"  Ground truth : {', '.join(scenario.ground_truth)}")
        text_lines.append(f"  Expected top : {scenario.expected_top}")
        text_lines.append("-" * 70)

        parse_result = parse_files(scenario.files)
        analysis = analyze(parse_result)
        accuracy = check_accuracy(analysis, scenario.ground_truth)

        top_name = analysis.top_fault.name if analysis.top_fault else None
        top_ok = top_name == scenario.expected_top
        if top_ok:
            correct_top += 1
        total_f1 += accuracy.f1

        if analysis.top_fault is not None:
            top = analysis.top_fault
            text_lines.append(
                f"    Detected top : {top.name}  "
                f"({top.best_evidence_level.value}, {int(top.confidence * 100)}%)  "
                f"[{'OK' if top_ok else 'MISMATCH'}]"
            )
        else:
            text_lines.append("    Detected top : (none)  [MISMATCH]")

        text_lines.append(
            f"    Precision    : {int(accuracy.precision * 100)}%   "
            f"Recall: {int(accuracy.recall * 100)}%   F1: {accuracy.f1:.2f}"
        )
        if accuracy.true_positives:
            text_lines.append(f"    Correct      : {', '.join(accuracy.true_positives)}")
        if accuracy.false_positives:
            text_lines.append(f"    False+       : {', '.join(accuracy.false_positives)}")
        if accuracy.false_negatives:
            text_lines.append(f"    Missed       : {', '.join(accuracy.false_negatives)}")
        text_lines.append("")

        json_rows.append(
            {
                "scenario": name,
                "ground_truth": list(scenario.ground_truth),
                "expected_top": scenario.expected_top,
                "detected_top": top_name,
                "top_ok": top_ok,
                "precision": accuracy.precision,
                "recall": accuracy.recall,
                "f1": accuracy.f1,
                "ranked_faults": [f.to_dict() for f in analysis.ranked_faults],
            }
        )

    avg_f1 = total_f1 / n if n else 0.0
    text_lines.append(_DIVIDER)
    text_lines.append("   SUMMARY")
    text_lines.append(_DIVIDER)
    text_lines.append(f"  Scenarios       : {n}")
    text_lines.append(f"  Top-fault OK    : {correct_top}/{n}")
    text_lines.append(f"  Average F1      : {avg_f1:.2f}")
    text_lines.append(_DIVIDER)

    return text_lines, json_rows, avg_f1, correct_top


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CET361 fault-engine benchmark.")
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human-readable text."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum average F1; the process exits non-zero if not met.",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        default=True,
        help="Save the human-readable report to data/benchmark_report.txt (default).",
    )
    parser.add_argument(
        "--save-detailed",
        action="store_true",
        help="Additionally write a per-scenario operator report in data/.",
    )
    args = parser.parse_args()

    text_lines, json_rows, avg_f1, correct_top = _run_all()
    text = "\n".join(text_lines)

    if args.json:
        print(json.dumps({"avg_f1": avg_f1, "correct_top": correct_top, "rows": json_rows}, indent=2))
    else:
        print(text)

    if args.save_report:
        os.makedirs(_REPORT_DIR, exist_ok=True)
        with open(_REPORT_PATH, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"\n  Report saved: {_REPORT_PATH}")

    if args.save_detailed:
        for name, scenario in ALL_SCENARIOS.items():
            pr = parse_files(scenario.files)
            analysis = analyze(pr)
            accuracy = check_accuracy(analysis, scenario.ground_truth)
            report = generate_text_report(analysis, name, accuracy=accuracy)
            slug = name.replace(" ", "_").replace("/", "-")
            path = os.path.join(_REPORT_DIR, f"report_{slug}.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report)

    return 0 if avg_f1 >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
