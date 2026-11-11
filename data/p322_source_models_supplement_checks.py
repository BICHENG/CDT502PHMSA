"""Requested paired checks, raw/calibrated errors and proposal reference; no fitting."""
from pathlib import Path
import importlib.util
import sys
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r3", OUT / "complete_models.py")
r3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)


def classify(y, probability, threshold):
    flag = probability >= threshold
    return np.select([flag & (y == 1), flag & (y == 0), ~flag & (y == 1)], ["TP", "FP", "FN"], default="TN")


def main():
    cohort = pd.read_csv(OUT / "cohort693.csv", dtype={"REPORT_NUMBER": str, "OPERATOR_ID": str})
    validation = pd.read_csv(OUT / "input_validation_predictions.csv", dtype={"REPORT_NUMBER": str}, float_precision="round_trip")
    selected = "physical_diameter_pressure"
    raw_scores = validation["score_" + selected].to_numpy()
    y = validation.cas.to_numpy(dtype=int)
    candidates = []
    for threshold in np.unique(raw_scores):
        flag = raw_scores >= threshold
        tp, fp, fn = int(y[flag].sum()), int((1 - y[flag]).sum()), int(y[~flag].sum())
        candidates.append((2 * tp / (2 * tp + fp + fn), float(threshold)))
    raw_threshold = max(candidates)[1]
    frozen = r3.json.loads((OUT / "selection_frozen.json").read_text(encoding="utf-8"))
    r3.write_json("raw_comparison_threshold_frozen.json", {
        "frozen_utc_before_raw_error_calculation": r3.now(), "raw_threshold": raw_threshold,
        "selected_sigmoid_threshold": frozen["threshold"],
        "rule": "same predeclared maximum early-validation F1; tie higher threshold",
        "validation_source_sha256": r3.sha(OUT / "input_validation_predictions.csv"),
        "changes_selected_model_or_threshold": False})
    late = pd.read_csv(OUT / "input_later_predictions.csv", dtype={"REPORT_NUMBER": str, "OPERATOR_ID": str}, float_precision="round_trip")
    calibrated = pd.read_csv(OUT / "calibration_later_predictions.csv", dtype={"REPORT_NUMBER": str}, float_precision="round_trip")
    assert late.REPORT_NUMBER.tolist() == calibrated.REPORT_NUMBER.tolist()
    scores = {"selected_raw": late["score_" + selected].to_numpy(),
              "selected_sigmoid": calibrated.score_sigmoid.to_numpy(),
              "physical3": late.score_physical_age_diameter_pressure.to_numpy(),
              "categorical4": late.score_categorical4.to_numpy(), "full7": late.score_full7.to_numpy()}
    pairs = [(left, right) for left in ["selected_raw", "selected_sigmoid"] for right in ["physical3", "categorical4", "full7"]]
    intervals = r3.paired_bootstrap(late, scores, pairs, "selected_input_comparisons")
    table = cohort.set_index("REPORT_NUMBER").loc[late.REPORT_NUMBER].reset_index()
    table["missing_diameter"] = table.diameter_in.isna()
    table["missing_pressure"] = table.normal_psig.isna()
    table["probability_raw"] = scores["selected_raw"]
    table["probability_sigmoid"] = scores["selected_sigmoid"]
    table["raw_validation_F1_threshold"] = raw_threshold
    table["sigmoid_validation_F1_threshold"] = frozen["threshold"]
    table["raw_classification"] = classify(table.cas.to_numpy(), scores["selected_raw"], raw_threshold)
    table["sigmoid_classification"] = classify(table.cas.to_numpy(), scores["selected_sigmoid"], frozen["threshold"])
    r3.csv("raw_calibrated_later_all_records.csv", table)
    rows = []
    for method, field, threshold in [("raw", "raw_classification", raw_threshold), ("sigmoid", "sigmoid_classification", frozen["threshold"])]:
        count = table[field].value_counts()
        rows.append({"method": method, "threshold": threshold, "n": len(table), "casualty_reports": int(table.cas.sum()),
                     **{key: int(count.get(key, 0)) for key in ["TP", "FP", "FN", "TN"]}})
    r3.csv("raw_calibrated_confusion.csv", rows)
    errors = table[table.raw_classification.isin(["FP", "FN"]) | table.sigmoid_classification.isin(["FP", "FN"])]
    r3.csv("raw_calibrated_all_errors.csv", errors)
    example = table[table.sigmoid_classification.eq("FN") & ~table.missing_diameter & ~table.missing_pressure].sort_values("REPORT_NUMBER").head(1)
    r3.csv("worked_case.csv", example)
    r3.write_json("worked_case_selection.json", {"rule": "earliest report number among final-model false negatives with observed diameter and pressure",
                                                "report_number": str(example.REPORT_NUMBER.iloc[0]),
                                                "use": "transparent calculation/error example, not a field-time prediction or representative case"})
    old = r3.ROOT / "research/results/course_sweep_20261107/models"
    reference = pd.read_csv(old / "model_metrics.csv")
    names = ["constant", "part_only", "logistic_proposal", "forest"]
    reference = reference[reference.method.isin(names)].copy()
    reference["cohort_total"] = 1550
    reference["training_n"] = 1286
    reference["comparison_scope"] = "same 264 later reports; never rank against 112-report physical experiment"
    r3.csv("proposal_four_method_reference.csv", reference)
    pred = pd.read_csv(old / "later_predictions.csv", dtype={"REPORT_NUMBER": str, "OPERATOR_ID": str}, float_precision="round_trip")
    r3.csv("proposal_four_method_predictions.csv", pred[["REPORT_NUMBER", "OPERATOR_ID", "received_year", "cas", *["score_" + n for n in names]]])
    r3.csv("figure1_input_choice.csv", [{"method": name, **r3.base.metrics(late.cas, score)} for name, score in scores.items()])
    r3.write_json("supplement_receipt.json", {"finished_utc": r3.now(), "new_model_fits": 0, "paired_comparisons": len(pairs),
                                             "raw_threshold": raw_threshold, "selected_threshold_unchanged": True,
                                             "worked_case": str(example.REPORT_NUMBER.iloc[0]),
                                             "reference_source_sha256": r3.sha(old / "model_metrics.csv")})
    print(r3.json.dumps({"raw_threshold": raw_threshold, "confusion": rows, "case": example.REPORT_NUMBER.iloc[0]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
