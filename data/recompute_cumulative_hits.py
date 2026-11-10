"""Recompute cumulative hits from saved predictions, using only the standard library.

Place this script beside later_predictions.csv and, optionally, cumulative_hits.csv:
    python recompute_cumulative_hits.py
Or supply --predictions, --expected and --output paths.
Equal-score groups use their exact expected hit count. No fitting or random draws.
"""

import argparse
import csv
import json
import math
from pathlib import Path

METHODS = (
    ("constant", "constant"),
    ("logit", "logistic_proposal"),
    ("part", "part_only"),
    ("rf", "forest"),
)
FIELDS = (
    "method", "source_method", "k", "hits", "tie_min", "tie_max", "cutoff",
    "above_n", "above_cas", "tie_n", "tie_cas", "tie_selected",
)
TOLERANCE = 1e-12


def read_csv(path, required):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: no data rows")
    return rows


def cumulative_rows(predictions):
    ids = [row["REPORT_NUMBER"] for row in predictions]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("REPORT_NUMBER must be nonempty and unique")
    if any(row["cas"] not in ("0", "1") for row in predictions):
        raise ValueError("cas must contain only 0 or 1")
    labels = [int(row["cas"]) for row in predictions]
    output = []
    for method, source in METHODS:
        groups = {}
        for row, label in zip(predictions, labels):
            score = float(row["score_" + source])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError(f"Invalid probability for {row['REPORT_NUMBER']}: {score}")
            groups.setdefault(score, []).append(label)
        output.append(dict(zip(FIELDS, (method, source, 0, 0.0, 0, 0, "", 0, 0, 0, 0, 0))))
        above_n = above_cas = 0
        for score in sorted(groups, reverse=True):
            n, cases = len(groups[score]), sum(groups[score])
            for slots in range(1, n + 1):
                output.append(dict(zip(FIELDS, (
                    method, source, above_n + slots,
                    above_cas + slots * cases / n,
                    above_cas + max(0, slots - (n - cases)),
                    above_cas + min(slots, cases), score,
                    above_n, above_cas, n, cases, slots,
                ))))
            above_n += n
            above_cas += cases
    return output


def compare_rows(actual, expected_path):
    expected = read_csv(expected_path, FIELDS)
    reference = {(row["method"], int(row["k"])): row for row in expected}
    if len(reference) != len(expected):
        raise ValueError(f"{expected_path}: duplicate method/k rows")
    actual_keys = {(row["method"], row["k"]) for row in actual}
    missing = sorted(actual_keys - reference.keys())
    extra = sorted(reference.keys() - actual_keys)
    errors = {field: 0.0 for field in FIELDS[2:]}
    mismatches = []
    compared = 0
    for row in actual:
        key = row["method"], row["k"]
        if key not in reference:
            continue
        compared += 1
        target = reference[key]
        if row["source_method"] != target["source_method"]:
            mismatches.append([*key, "source_method"])
        for field in errors:
            a, b = row[field], target[field]
            if field == "cutoff" and (a == "" or b == ""):
                if a != b:
                    mismatches.append([*key, field])
                continue
            a, b = float(a), float(b)
            if not math.isfinite(a) or not math.isfinite(b):
                raise ValueError(f"{expected_path}: non-finite {field} at {key}")
            difference = abs(a - b)
            errors[field] = max(errors[field], difference)
            if difference > TOLERANCE:
                mismatches.append([*key, field])
    return {
        "path": str(expected_path.resolve()), "matched": not (missing or extra or mismatches),
        "rows_compared": compared, "missing_rows": missing, "extra_rows": extra,
        "mismatched_cells": len(mismatches), "first_mismatches": mismatches[:10],
        "absolute_tolerance": TOLERANCE, "max_absolute_errors": errors,
    }


def unused_output(directory):
    candidate = directory / "cumulative_hits_recomputed.csv"
    suffix = 2
    while candidate.exists():
        candidate = directory / f"cumulative_hits_recomputed_{suffix}.csv"
        suffix += 1
    return candidate


def main():
    directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=directory / "later_predictions.csv",
                        help="Saved predictions; default: later_predictions.csv beside this script")
    parser.add_argument("--expected", type=Path,
                        help="Optional reference; auto-check cumulative_hits.csv beside this script if present")
    parser.add_argument("--output", type=Path,
                        help="New CSV path; default: an unused cumulative_hits_recomputed*.csv beside this script")
    args = parser.parse_args()
    expected_path = args.expected
    if expected_path is None and (directory / "cumulative_hits.csv").is_file():
        expected_path = directory / "cumulative_hits.csv"
    try:
        required = ["REPORT_NUMBER", "cas"] + ["score_" + source for _, source in METHODS]
        predictions = read_csv(args.predictions, required)
        rows = cumulative_rows(predictions)
        comparison = compare_rows(rows, expected_path) if expected_path else None
        output = args.output or unused_output(directory)
        with output.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps({
        "predictions": str(args.predictions.resolve()), "output": str(output.resolve()),
        "reports": len(predictions), "casualty_reports": sum(int(row["cas"]) for row in predictions),
        "methods": len(METHODS), "points_per_method": len(predictions) + 1,
        "output_rows": len(rows), "random_draws": 0, "comparison": comparison,
    }, indent=2))
    return 1 if comparison is not None and not comparison["matched"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

