"""Runs every test case through the extractor and writes the scores to results/.

Usage: python evaluate.py
"""

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from extractor import FIELDS, MODEL, extract

ROOT = Path(__file__).parent
RESULTS_DIR = ROOT / "results"
SECONDS_BETWEEN_CALLS = 7  # Stays under the free tier's requests-per-minute limit.

# These can be worded differently and still be right, such as "Bengaluru, India".
LOOSE_FIELDS = (
    "location",
    "highest_education",
    "expected_salary",
    "current_job_title",
    "position_applied",
    "company_applied_to",
    "current_company",
)


def normalise(value):
    return re.sub(r"\s+", " ", str(value)).strip().lower().rstrip("/.")


def values_match(field, expected, actual):
    if expected is None or actual is None:
        return expected is None and actual is None
    if field == "skills":
        return {normalise(s) for s in expected} == {normalise(s) for s in actual}
    if field == "phone":
        return re.sub(r"\D", "", expected) == re.sub(r"\D", "", actual)
    if field == "years_of_experience":
        return float(expected) == float(actual)
    expected, actual = normalise(expected), normalise(actual)
    if field in LOOSE_FIELDS:
        return expected in actual or actual in expected
    return expected == actual


def score_case(case, actual):
    """Compares one result with the expected answer, field by field."""
    expected = case["expected"]
    mismatches = {}
    invented = []
    for field in FIELDS:
        want = expected.get(field)
        got = actual[field]
        if not values_match(field, want, got):
            mismatches[field] = {"expected": want, "actual": got}
            if want is None:
                invented.append(field)
    return {
        "id": case["id"],
        "category": case["category"],
        "description": case["description"],
        "status_correct": actual["input_status"] == expected["input_status"],
        "expected_status": expected["input_status"],
        "actual_status": actual["input_status"],
        "fields_correct": len(FIELDS) - len(mismatches),
        "null_fields_expected": sum(1 for f in FIELDS if expected.get(f) is None),
        "invented_fields": invented,
        "mismatches": mismatches,
        "error": None,
    }


def failed_case(case, error):
    return {
        "id": case["id"],
        "category": case["category"],
        "description": case["description"],
        "status_correct": False,
        "expected_status": case["expected"]["input_status"],
        "actual_status": None,
        "fields_correct": 0,
        "null_fields_expected": sum(1 for f in FIELDS if case["expected"].get(f) is None),
        "invented_fields": [],
        "mismatches": {},
        "error": str(error),
    }


def summarise(rows):
    completed = [row for row in rows if row["error"] is None]
    passed = [
        row for row in completed if row["status_correct"] and not row["mismatches"]
    ]
    total_fields = len(FIELDS) * len(rows)
    nulls = sum(row["null_fields_expected"] for row in rows)
    invented = sum(len(row["invented_fields"]) for row in rows)
    return {
        "cases": len(rows),
        "api_or_schema_failures": len(rows) - len(completed),
        "fully_correct_cases": len(passed),
        "status_accuracy": sum(row["status_correct"] for row in rows) / len(rows),
        "field_accuracy": sum(row["fields_correct"] for row in rows) / total_fields,
        "invented_values": invented,
        "missing_info_accuracy": (nulls - invented) / nulls if nulls else 1.0,
    }


def write_report(summary, by_category, rows):
    lines = [
        "# Evaluation report",
        "",
        f"Model: `{MODEL}`",
        "",
        "| Metric | Result |",
        "| --- | --- |",
        f"| Test cases | {summary['cases']} |",
        f"| Cases fully correct | {summary['fully_correct_cases']} of {summary['cases']} |",
        f"| Status accuracy | {summary['status_accuracy']:.1%} |",
        f"| Field accuracy | {summary['field_accuracy']:.1%} |",
        f"| Missing fields left as null | {summary['missing_info_accuracy']:.1%} |",
        f"| Invented values | {summary['invented_values']} |",
        f"| API or schema failures | {summary['api_or_schema_failures']} |",
        "",
        "## By category",
        "",
        "| Category | Cases | Fully correct | Status accuracy | Field accuracy | Invented values |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for category, s in by_category.items():
        lines.append(
            f"| {category} | {s['cases']} | {s['fully_correct_cases']} "
            f"| {s['status_accuracy']:.1%} | {s['field_accuracy']:.1%} | {s['invented_values']} |"
        )
    lines += ["", "## Cases that were not fully correct", ""]
    failures = [
        r for r in rows if r["error"] or r["mismatches"] or not r["status_correct"]
    ]
    if not failures:
        lines.append("None.")
    for row in failures:
        lines.append(f"### {row['id']}: {row['description']}")
        if row["error"]:
            lines.append(f"- Error: {row['error']}")
        if not row["status_correct"]:
            lines.append(f"- Status: expected `{row['expected_status']}`, got `{row['actual_status']}`")
        for field, m in row["mismatches"].items():
            lines.append(f"- `{field}`: expected `{m['expected']}`, got `{m['actual']}`")
        lines.append("")
    (RESULTS_DIR / "evaluation_report.md").write_text("\n".join(lines) + "\n")


def main():
    cases = json.loads((ROOT / "tests" / "test_cases.json").read_text())
    rows = []
    for number, case in enumerate(cases, start=1):
        print(f"[{number}/{len(cases)}] {case['id']}", flush=True)
        try:
            rows.append(score_case(case, extract(case["input"])))
        except Exception as error:
            print(f"    failed: {error}", file=sys.stderr)
            rows.append(failed_case(case, error))
        if case["input"].strip() and number < len(cases):
            time.sleep(SECONDS_BETWEEN_CALLS)

    summary = summarise(rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    by_category = {name: summarise(group) for name, group in grouped.items()}

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "evaluation_results.json").write_text(
        json.dumps(
            {"model": MODEL, "summary": summary, "by_category": by_category, "cases": rows},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    write_report(summary, by_category, rows)

    print(f"\nFully correct: {summary['fully_correct_cases']} of {summary['cases']}")
    print(f"Field accuracy: {summary['field_accuracy']:.1%}")
    print(f"Invented values: {summary['invented_values']}")
    print("Report: results/evaluation_report.md")


if __name__ == "__main__":
    main()
