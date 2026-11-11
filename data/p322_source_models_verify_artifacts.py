"""Read saved coefficients and reproduce predictions without estimator fitting."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.metrics import average_precision_score

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def reconstruct(frame, parameters):
    if "prevalence" in parameters:
        return np.full(len(frame), parameters["prevalence"])
    parts = []
    for field, categories in zip(parameters["categorical"], parameters.get("encoder_categories", [])):
        parts.append(np.column_stack([frame[field].eq(value).to_numpy(dtype=float) for value in categories]))
    numeric = parameters["numeric"]
    if numeric:
        q = frame.copy()
        q["log_diameter"], q["log_pressure"] = np.log1p(q.diameter_in), np.log1p(q.normal_psig)
        values = q[numeric].to_numpy(dtype=float)
        missing = np.isnan(values).astype(float)
        values = np.where(np.isnan(values), parameters["train_medians"], values)
        z = (values - parameters["train_scale_mean"]) / parameters["train_scale"]
        parts.extend([z, missing])
    return expit(np.column_stack(parts) @ parameters["coefficient"] + parameters["intercept"])


def main():
    cohort = pd.read_csv(OUT / "cohort693.csv", dtype={"REPORT_NUMBER": str, "OPERATOR_ID": str})
    rows = []
    for kind, filename, keys in [("input", "input_model_parameters.json", ["fit337", "refit581"]),
                                 ("cluster", "cluster_models_parameters.json", ["validation", "later"])]:
        parameters = json.loads((OUT / filename).read_text(encoding="utf-8"))
        for role, key in zip(["validation", "later"], keys):
            scores = pd.read_csv(OUT / f"{kind}_{role}_predictions.csv", dtype={"REPORT_NUMBER": str}, float_precision="round_trip")
            frame = cohort.set_index("REPORT_NUMBER").loc[scores.REPORT_NUMBER].reset_index()
            if kind == "cluster":
                cp = json.loads((OUT / "cluster_preprocessing.json").read_text(encoding="utf-8"))
                p = cp["validation_training299" if role == "validation" else "final_training521"]
                values = np.column_stack([frame.age_years, np.log1p(frame.diameter_in), np.log1p(frame.normal_psig)])
                z = (values - p["scaler_mean"]) / p["scaler_scale"]
                distances = ((z[:, None, :] - np.array(p["centers_z_display_order"])[None, :, :]) ** 2).sum(axis=2)
                frame["cluster_group"] = (np.argmin(distances, axis=1) + 1).astype(str)
            for name, model in parameters[key].items():
                error = float(np.max(np.abs(reconstruct(frame, model) - scores["score_" + name].to_numpy())))
                assert error < 1e-12, (kind, role, name, error)
                rows.append({"kind": kind, "role": role, "method": name, "maximum_absolute_error": error})
    calibrators = json.loads((OUT / "calibration_parameters.json").read_text(encoding="utf-8"))
    for role, key in [("validation", "fit_rolling_scores"), ("later", "refit_rolling_scores")]:
        raw = pd.read_csv(OUT / f"input_{role}_predictions.csv", float_precision="round_trip").score_physical_diameter_pressure.to_numpy()
        saved = pd.read_csv(OUT / f"calibration_{role}_predictions.csv", float_precision="round_trip")
        for name, p in calibrators[key].items():
            expected = expit(p["intercept"] + p["slope"] * logit(raw))
            error = float(np.max(np.abs(expected - saved["score_" + name].to_numpy())))
            assert error < 1e-12
            rows.append({"kind": "calibration", "role": role, "method": name, "maximum_absolute_error": error})
    selected = json.loads((OUT / "selection_frozen.json").read_text(encoding="utf-8"))
    choices = pd.read_csv(OUT / "input_selection_early_only.csv")
    winner = choices[choices.passes_selection_rule].sort_values(["field_count", "Brier", "AP", "method"], ascending=[True, True, False, True]).iloc[0]
    assert winner.method == selected["selected_input"]
    errors = pd.read_csv(OUT / "raw_calibrated_later_all_records.csv")
    confusion = json.loads((OUT / "final_classification_counts.json").read_text(encoding="utf-8"))
    for name in ["TP", "FP", "FN", "TN"]:
        assert int(errors.sigmoid_classification.eq(name).sum()) == confusion[name]
    assert errors.REPORT_NUMBER.is_unique and len(errors) == 112 and errors.cas.sum() == 15
    original = pd.read_csv(OUT / "proposal_four_method_reference.csv")
    old_predictions = pd.read_csv(OUT / "proposal_four_method_predictions.csv", float_precision="round_trip")
    for row in original.itertuples():
        score = old_predictions["score_" + row.method]
        assert abs(average_precision_score(old_predictions.cas, score) - row.AP) < 1e-12
        assert abs(np.mean((old_predictions.cas - score) ** 2) - row.Brier) < 1e-12
    receipt = json.loads((OUT / "protocol_receipt.json").read_text(encoding="utf-8"))
    for path, digest in receipt["source_hashes"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    for path in OUT.glob("*.csv"):
        pd.read_csv(path)
    for path in OUT.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    pd.DataFrame(rows).to_csv(OUT / "saved_parameter_readback.csv", index=False, encoding="utf-8-sig")
    result = {"saved_prediction_sets_reproduced": len(rows), "maximum_absolute_prediction_error": max(r["maximum_absolute_error"] for r in rows),
              "selected_input_rule_verified": True, "final_confusion_verified": confusion,
              "proposal_four_models_reproduced": True, "source_hashes_unchanged": True,
              "scope": "saved artifacts and formulas; no model refits or new model selection"}
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
