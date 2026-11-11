"""Finish R3 with frozen early-period rules. All writes remain beside this script."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import itertools
import json
import hashlib
import platform
import sys
import warnings

sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
import sklearn
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREVIOUS = ROOT / "work/p320_core/prediction"
CLUSTER = ROOT / "research/results/course_visual_lab_20261109/clustering"
spec = importlib.util.spec_from_file_location("p320_models", PREVIOUS / "run_trials.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
SEED, DRAWS, ASSOCIATION_DRAWS = 20261111, 2000, 1000
PHYS = ["age_years", "log_diameter", "log_pressure"]
SHORT = {"age_years": "age", "log_diameter": "diameter", "log_pressure": "pressure"}
CAT = ["part", "mat", "location", "cls"]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv(name, rows):
    pd.DataFrame(rows).to_csv(OUT / name, index=False, encoding="utf-8-sig")


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=base.cast,
                                     allow_nan=False) + "\n", encoding="utf-8")


def candidates():
    result = {"constant": {"categorical": [], "numeric": [], "field_count": 0},
              "categorical4": {"categorical": CAT, "numeric": [], "field_count": 4},
              "full7": {"categorical": CAT, "numeric": PHYS, "field_count": 7}}
    for size in [1, 2, 3]:
        for fields in itertools.combinations(PHYS, size):
            name = "physical_" + "_".join(SHORT[f] for f in fields)
            result[name] = {"categorical": [], "numeric": list(fields), "field_count": size}
    for field, label in [("age_years", "age"), ("log_diameter", "diameter"), ("log_pressure", "pressure"),
                         ("mat", "material"), ("location", "location"), ("cls", "class")]:
        result["full_without_" + label] = {"categorical": [x for x in CAT if x != field],
                                         "numeric": [x for x in PHYS if x != field], "field_count": 6}
    return result


def fit_model(train, model_spec):
    if model_spec["field_count"] == 0:
        return {"prevalence": float(train.cas.mean())}
    return base.FixedLogistic(categorical=model_spec["categorical"], numeric=model_spec["numeric"]).fit(train)


def predict(model, frame):
    return np.full(len(frame), model["prevalence"]) if isinstance(model, dict) else model.predict(frame)


def serialize(model):
    return model if isinstance(model, dict) else model.serialize()


def prediction_table(frame, scores):
    table = frame[["REPORT_NUMBER", "OPERATOR_ID", "incident_year", "received_year", "cas", "mat", "complete_physical"]].copy()
    for name, value in scores.items():
        table["score_" + name] = value
    return table


def metric_rows(frame, scores, role, cohort):
    return [{"cohort": cohort, "role": role, "method": name, **base.metrics(frame.cas, score)} for name, score in scores.items()]


def quick_metrics(y, score):
    count = int(np.ceil(.2 * len(y)))
    cutoff = np.sort(score)[-count]
    above, tied = score > cutoff, score == cutoff
    hits = y[above].sum() + (count - above.sum()) * y[tied].mean()
    return {"AP": float(average_precision_score(y, score)), "Brier": float(np.mean((y - score) ** 2)),
            "budget20_recall": float(hits / y.sum())}


def paired_bootstrap(frame, scores, pairs, name):
    op = frame.OPERATOR_ID.to_numpy()
    groups = [np.flatnonzero(op == g) for g in sorted(set(op))]
    rng, y = np.random.default_rng(SEED), frame.cas.to_numpy(dtype=int)
    point = {n: quick_metrics(y, p) for n, p in scores.items()}
    draws, invalid = [], 0
    for draw in range(DRAWS):
        ix = np.concatenate([groups[i] for i in rng.integers(len(groups), size=len(groups))])
        if np.unique(y[ix]).size != 2:
            invalid += 1
            continue
        measured = {n: quick_metrics(y[ix], p[ix]) for n, p in scores.items()}
        for left, right in pairs:
            draws.append({"draw": draw, "left": left, "right": right,
                          **{m: measured[left][m] - measured[right][m] for m in ["AP", "Brier", "budget20_recall"]}})
    table = pd.DataFrame(draws)
    csv(name + "_draws.csv", table)
    rows = []
    for left, right in pairs:
        group = table[table.left.eq(left) & table.right.eq(right)]
        for metric in ["AP", "Brier", "budget20_recall"]:
            lo, hi = group[metric].quantile([.025, .975])
            rows.append({"left": left, "right": right, "metric": metric,
                         "difference_left_minus_right": point[left][metric] - point[right][metric],
                         "ci_lower": lo, "ci_upper": hi, "valid_draws": DRAWS - invalid,
                         "single_class_skipped": invalid, "operators": len(groups),
                         "scope": "fixed fitted predictions; operator-paired exploratory percentile intervals"})
    csv(name + "_intervals.csv", rows)
    return pd.DataFrame(rows)


def select_input(specifications, validation_metrics):
    v = validation_metrics.copy()
    v["field_count"] = v.method.map(lambda n: specifications[n]["field_count"])
    v = v[v.method.ne("constant")]
    best = v.sort_values(["AP", "Brier", "method"], ascending=[False, True, True]).iloc[0]
    v["AP_loss_from_best"] = best.AP - v.AP
    v["Brier_increase_from_best"] = v.Brier - best.Brier
    v["passes_selection_rule"] = v.AP_loss_from_best.le(.03 + 1e-12) & v.Brier_increase_from_best.le(.01 + 1e-12)
    chosen = v[v.passes_selection_rule].sort_values(["field_count", "Brier", "AP", "method"],
                                                  ascending=[True, True, False, True]).iloc[0]
    v["selected"] = v.method.eq(chosen.method)
    csv("input_selection_early_only.csv", v)
    return str(chosen.method), str(best.method)


def rolling_scores(frame, model_spec, through):
    records = []
    for end, low, high in [(2013, 2014, 2015), (2015, 2016, 2017), (2017, 2018, 2019), (2019, 2020, 2021)]:
        if high > through:
            continue
        train = frame[frame.received_year.le(end)]
        test = frame[frame.received_year.between(low, high)].copy()
        assert train.cas.nunique() == 2 and len(test)
        model = fit_model(train, model_spec)
        score = predict(model, test)
        for row, probability in zip(test[["REPORT_NUMBER", "OPERATOR_ID", "received_year", "cas"]].to_dict("records"), score):
            records.append({"fit_through": end, "train_n": len(train), "validation_start": low,
                            "validation_end": high, **row, "probability": probability})
    result = pd.DataFrame(records)
    assert result.REPORT_NUMBER.is_unique
    return result


def fit_calibrators(oof):
    x = logit(np.clip(oof.probability.to_numpy(), 1e-12, 1 - 1e-12))
    y = oof.cas.to_numpy(dtype=int)
    intercept = brentq(lambda a: expit(x + a).mean() - y.mean(), -40, 40)
    sigmoid = LogisticRegression(C=1.0, solver="lbfgs", max_iter=5000, l1_ratio=0).fit(x[:, None], y)
    return {"raw": {"slope": 1., "intercept": 0., "parameters": 0},
            "intercept_only": {"slope": 1., "intercept": float(intercept), "parameters": 1},
            "sigmoid": {"slope": float(sigmoid.coef_[0, 0]), "intercept": float(sigmoid.intercept_[0]), "parameters": 2}}


def calibrate(score, parameters):
    return expit(parameters["intercept"] + parameters["slope"] * logit(np.clip(score, 1e-12, 1 - 1e-12)))


def threshold_on_validation(y, score):
    rows = []
    for cutoff in np.unique(score):
        flag = score >= cutoff
        tp, fp, fn = int(y[flag].sum()), int((1 - y[flag]).sum()), int(y[~flag].sum())
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.
        rows.append({"threshold": cutoff, "F1": f1, "TP": tp, "FP": fp, "FN": fn})
    grid = pd.DataFrame(rows).sort_values(["F1", "threshold"], ascending=[False, False])
    csv("threshold_candidates_validation_only.csv", grid)
    return float(grid.iloc[0].threshold)


def cluster_matrix(frame):
    return frame[PHYS].to_numpy(dtype=float)


def assign_clusters(frame, parameters):
    z = (cluster_matrix(frame) - np.array(parameters["scaler_mean"])) / np.array(parameters["scaler_scale"])
    distance = ((z[:, None, :] - np.array(parameters["centers_z_display_order"])[None, :, :]) ** 2).sum(axis=2)
    return np.argmin(distance, axis=1) + 1


def clustering_comparison(a):
    complete = a[a.complete_physical].copy().reset_index(drop=True)
    assert len(complete) == 621
    early = complete[complete.received_year.le(2017)].copy()
    validation = complete[complete.received_year.between(2018, 2021)].copy()
    refit = complete[complete.received_year.le(2021)].copy()
    later = complete[complete.received_year.ge(2022)].copy()
    assert [len(early), len(validation), len(refit), len(later)] == [299, 222, 521, 100]
    scaler = StandardScaler().fit(cluster_matrix(early))
    km = KMeans(n_clusters=3, random_state=20261109, n_init=50, max_iter=500, algorithm="lloyd").fit(scaler.transform(cluster_matrix(early)))
    back = scaler.inverse_transform(km.cluster_centers_)
    order = sorted(range(3), key=lambda i: (back[i, 0], back[i, 2], back[i, 1]))
    fit_parameters = {"scaler_mean": scaler.mean_, "scaler_scale": scaler.scale_, "centers_z_display_order": km.cluster_centers_[order]}
    frozen = json.loads((CLUSTER / "physical_frozen_parameters.json").read_text(encoding="utf-8"))
    original = pd.read_csv(CLUSTER / "physical_records_693.csv", dtype={"REPORT_NUMBER": str})
    actual = assign_clusters(complete, frozen)
    expected = original.set_index("REPORT_NUMBER").loc[complete.REPORT_NUMBER, "cluster"].astype(int).to_numpy()
    assert np.array_equal(actual, expected)
    complete["cluster"] = actual
    csv("cluster_membership_complete621.csv", complete[["REPORT_NUMBER", "OPERATOR_ID", "received_year", "cas", "mat", "cluster", "age_years", "diameter_in", "normal_psig"]])
    profiles = []
    names = {1: "较小管径、较年轻组", 2: "较大管径、较高压力组", 3: "高龄、低压力组"}
    for (period, label), group in complete.assign(period=np.where(complete.received_year.le(2021), "early", "later")).groupby(["period", "cluster"]):
        profiles.append({"period": period, "cluster": label, "name": names[label], "n": len(group), "casualty_reports": int(group.cas.sum()),
                         "operators": group.OPERATOR_ID.nunique(), "age_median": group.age_years.median(),
                         "diameter_median": group.diameter_in.median(), "pressure_median": group.normal_psig.median()})
    csv("cluster_profile_checked.csv", profiles)
    specifications = {"constant": {"categorical": [], "numeric": [], "field_count": 0},
                      "categorical4": {"categorical": CAT, "numeric": [], "field_count": 4},
                      "physical3": {"categorical": [], "numeric": PHYS, "field_count": 3},
                      "cluster_only": {"categorical": ["cluster_group"], "numeric": [], "field_count": 3},
                      "categorical_physical": {"categorical": CAT, "numeric": PHYS, "field_count": 7},
                      "categorical_cluster": {"categorical": CAT + ["cluster_group"], "numeric": [], "field_count": 7}}
    metrics, parameters, late_scores = [], {}, {}
    for role, train, test, cluster_params in [("validation", early, validation, fit_parameters), ("later", refit, later, frozen)]:
        train, test = train.copy(), test.copy().reset_index(drop=True)
        train["cluster_group"] = assign_clusters(train, cluster_params).astype(str)
        test["cluster_group"] = assign_clusters(test, cluster_params).astype(str)
        scores, parameters[role] = {}, {}
        for name, model_spec in specifications.items():
            model = fit_model(train, model_spec)
            scores[name], parameters[role][name] = predict(model, test), serialize(model)
        csv(f"cluster_{role}_predictions.csv", prediction_table(test, scores))
        metrics.extend(metric_rows(test, scores, role, "complete621"))
        if role == "later":
            late_scores, later = scores, test
    csv("cluster_metrics.csv", metrics)
    write_json("cluster_models_parameters.json", parameters)
    write_json("cluster_preprocessing.json", {"validation_training299": fit_parameters, "final_training521": frozen,
                                               "all621_labels_match_original": True, "group_names": names})
    pairs = [("cluster_only", "physical3"), ("categorical_cluster", "categorical_physical"),
             ("categorical_cluster", "categorical4"), ("categorical_physical", "categorical4")]
    intervals = paired_bootstrap(later, late_scores, pairs, "cluster_paired")
    csv("figure2_cluster_representation.csv", pd.DataFrame(metrics).query("role == 'later'"))
    return pd.DataFrame(metrics), intervals


def associations(train, full_model):
    contrasts = [
        {"name": "age10", "label": "管龄增加10年", "numeric": "age_years", "difference": 10.},
        {"name": "diameter2to4", "label": "管径2英寸至4英寸", "numeric": "log_diameter", "difference": np.log(5) - np.log(3)},
        {"name": "pressure20to40", "label": "正常压力20至40 psig", "numeric": "log_pressure", "difference": np.log(41) - np.log(21)},
        {"name": "plastic_steel", "label": "塑料相对钢", "left": "mat_PLASTIC", "right": "mat_STEEL"},
        {"name": "iron_steel", "label": "铸铁锻铁相对钢", "left": "mat_CAST/WROUGHT IRON", "right": "mat_STEEL"},
        {"name": "private_public", "label": "私人场地相对公共场地", "left": "location_PRIVATE PROPERTY", "right": "location_PUBLIC PROPERTY"},
        {"name": "class4_class3", "label": "地区等级4相对3", "left": "cls_CLASS 4 LOCATION", "right": "cls_CLASS 3 LOCATION"},
    ]
    def estimate(model):
        p = model.serialize()
        coefficients = dict(zip(p["feature_names"], p["coefficient"]))
        result = {}
        for contrast in contrasts:
            if "numeric" in contrast:
                field = contrast["numeric"]
                result[contrast["name"]] = coefficients[field] / p["train_scale"][p["numeric"].index(field)] * contrast["difference"]
            elif contrast["left"] in coefficients and contrast["right"] in coefficients:
                result[contrast["name"]] = coefficients[contrast["left"]] - coefficients[contrast["right"]]
        return result
    point = estimate(full_model)
    operators = sorted(train.OPERATOR_ID.unique())
    groups = [np.flatnonzero(train.OPERATOR_ID.to_numpy() == op) for op in operators]
    rng, records, single_class = np.random.default_rng(SEED), [], 0
    for draw in range(ASSOCIATION_DRAWS):
        ix = np.concatenate([groups[i] for i in rng.integers(len(groups), size=len(groups))])
        sample = train.iloc[ix].reset_index(drop=True)
        if sample.cas.nunique() != 2:
            single_class += 1
            continue
        model = fit_model(sample, {"categorical": CAT, "numeric": PHYS, "field_count": 7})
        for name, value in estimate(model).items():
            records.append({"draw": draw, "contrast": name, "log_OR": value})
    draws = pd.DataFrame(records)
    csv("conditional_association_draws.csv", draws)
    rows = []
    for contrast in contrasts:
        sample = draws.loc[draws.contrast.eq(contrast["name"]), "log_OR"]
        lo, hi = sample.quantile([.025, .975])
        rows.append({"contrast": contrast["name"], "label": contrast["label"], "OR": float(np.exp(point[contrast["name"]])),
                     "ci_lower": float(np.exp(lo)), "ci_upper": float(np.exp(hi)), "valid_draws": len(sample),
                     "missing_contrast_draws": ASSOCIATION_DRAWS - len(sample) - single_class,
                     "n": len(train), "casualty_reports": int(train.cas.sum()), "operators": len(operators),
                     "model": "L2 C=0.2 full7 conditional association, separate from selected predictive model",
                     "interpretation": "reported incident conditional odds; fixed unit contrasts; not causal risk ratios"})
    csv("conditional_associations.csv", rows)
    return pd.DataFrame(rows)


def error_summary(frame, probability, threshold, raw):
    table = frame[["REPORT_NUMBER", "OPERATOR_ID", "received_year", "mat", "part", "location", "cls", "cas",
                   "age_years", "diameter_in", "normal_psig", "complete_physical"]].copy()
    table["probability"] = probability
    table["threshold"] = threshold
    table["flagged"] = probability >= threshold
    table["classification"] = np.select([table.flagged & table.cas.eq(1), table.flagged & table.cas.eq(0),
                                          ~table.flagged & table.cas.eq(1)], ["TP", "FP", "FN"], default="TN")
    ex_post = raw[["REPORT_NUMBER", "CAUSE", "IGNITE_IND"]].rename(columns={"CAUSE": "cause_ex_post_not_input", "IGNITE_IND": "ignition_ex_post_not_input"})
    table = table.merge(ex_post, on="REPORT_NUMBER", validate="one_to_one")
    csv("selected_later_errors_all_reports.csv", table)
    rows = []
    for field in ["mat", "location", "complete_physical", "cause_ex_post_not_input", "ignition_ex_post_not_input"]:
        for value, group in table.groupby(field, dropna=False):
            counts = group.classification.value_counts()
            rows.append({"dimension": field, "value": value, "n": len(group), "casualty_reports": int(group.cas.sum()),
                         **{key: int(counts.get(key, 0)) for key in ["TP", "FP", "FN", "TN"]},
                         "mean_probability": group.probability.mean(), "context_only": "ex_post" in field})
    csv("error_scenarios.csv", rows)
    examples = pd.concat([table[table.classification.eq("FN")].sort_values("probability", ascending=False),
                          table[table.classification.eq("FP")].sort_values("probability", ascending=False).head(5)])
    csv("error_examples.csv", examples)
    counts = table.classification.value_counts()
    return {"n": len(table), "casualty_reports": int(table.cas.sum()), "threshold": threshold,
            **{key: int(counts.get(key, 0)) for key in ["TP", "FP", "FN", "TN"]}}


def probability_bins(frame, predictions):
    edges = [0, .1, .2, .4, 1.00000001]
    rows = []
    for name, score in predictions.items():
        bins = pd.cut(score, edges, right=False, labels=False)
        for index in range(4):
            mask = np.asarray(bins == index)
            if not mask.sum():
                continue
            rows.append({"method": name, "lower": edges[index], "upper": min(edges[index + 1], 1),
                         "n": int(mask.sum()), "casualty_reports": int(frame.cas.to_numpy()[mask].sum()),
                         "mean_probability": float(score[mask].mean()), "observed_fraction": float(frame.cas.to_numpy()[mask].mean())})
    csv("probability_bins_later.csv", rows)


def main():
    started = now()
    inputs = [PREVIOUS / "run_trials.py", PREVIOUS / "A_cohort_records.csv", PREVIOUS / "A_later_predictions.csv",
              PREVIOUS / "B_later_predictions.csv", PREVIOUS / "B_metrics.csv", PREVIOUS / "B_paired_operator_intervals.csv",
              CLUSTER / "physical_frozen_parameters.json", CLUSTER / "physical_records_693.csv", OUT / "protocol.md"]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    write_json("protocol_receipt.json", {"started_utc": started, "source_hashes": hashes, "script_sha256": sha(Path(__file__)),
                                          "seed": SEED, "later_data_already_explored": True})
    raw, a, b = base.prepare()
    saved = pd.read_csv(PREVIOUS / "A_cohort_records.csv", dtype={"REPORT_NUMBER": str, "OPERATOR_ID": str})
    assert a.REPORT_NUMBER.tolist() == saved.REPORT_NUMBER.tolist() and a.cas.tolist() == saved.cas.tolist()
    csv("cohort693.csv", a[["REPORT_NUMBER", "OPERATOR_ID", "incident_year", "received_year", "role", "cas", *CAT,
                           "age_years", "diameter_in", "normal_psig", "complete_physical"]])
    fit = a[a.received_year.le(2017)].copy().reset_index(drop=True)
    validation = a[a.received_year.between(2018, 2021)].copy().reset_index(drop=True)
    refit = a[a.received_year.le(2021)].copy().reset_index(drop=True)
    later = a[a.received_year.ge(2022)].copy().reset_index(drop=True)
    counts = [{"cohort": cohort, "role": role, "n": len(group), "casualty_reports": int(group.cas.sum()),
               "operators": group.OPERATOR_ID.nunique()} for cohort, f in [("all693", a), ("complete621", a[a.complete_physical])]
              for role, group in [("fit", f[f.received_year.le(2017)]), ("validation", f[f.received_year.between(2018, 2021)]),
                                  ("refit", f[f.received_year.le(2021)]), ("later", f[f.received_year.ge(2022)])]]
    csv("split_counts.csv", counts)
    specifications = candidates()
    write_json("input_candidates.json", specifications)
    validation_scores, fit_parameters = {}, {}
    for name, model_spec in specifications.items():
        model = fit_model(fit, model_spec)
        validation_scores[name], fit_parameters[name] = predict(model, validation), serialize(model)
    validation_metrics = pd.DataFrame(metric_rows(validation, validation_scores, "validation", "all693"))
    csv("input_validation_metrics.csv", validation_metrics)
    csv("input_validation_predictions.csv", prediction_table(validation, validation_scores))
    selected, best = select_input(specifications, validation_metrics)
    oof_fit = rolling_scores(a, specifications[selected], 2017)
    csv("calibration_rolling_fit_scores.csv", oof_fit)
    calibrators_fit = fit_calibrators(oof_fit)
    calibration_validation_scores = {n: calibrate(validation_scores[selected], par) for n, par in calibrators_fit.items()}
    cm = pd.DataFrame(metric_rows(validation, calibration_validation_scores, "validation", "all693"))
    cm["parameters"] = cm.method.map(lambda n: calibrators_fit[n]["parameters"])
    cm["positive_slope"] = cm.method.map(lambda n: calibrators_fit[n]["slope"] > 0)
    best_cal = cm[cm.positive_slope].sort_values(["Brier", "parameters", "method"]).iloc[0]
    raw_brier = float(cm.loc[cm.method.eq("raw"), "Brier"].iloc[0])
    chosen_calibration = str(best_cal.method) if raw_brier - best_cal.Brier >= .001 else "raw"
    cm["selected"] = cm.method.eq(chosen_calibration)
    csv("calibration_validation_metrics.csv", cm)
    csv("calibration_validation_predictions.csv", prediction_table(validation, calibration_validation_scores))
    threshold = threshold_on_validation(validation.cas.to_numpy(dtype=int), calibration_validation_scores[chosen_calibration])
    selection = {"frozen_utc_before_new_later_evaluation": now(), "selected_input": selected,
                 "selected_specification": specifications[selected], "highest_validation_AP_candidate": best,
                 "AP_simplification_tolerance": .03, "Brier_simplification_tolerance": .01,
                 "selected_calibration": chosen_calibration, "threshold": threshold,
                 "threshold_rule": "maximum validation F1, ties higher threshold; fixed before this run's later error inspection",
                 "calibration_minimum_validation_Brier_improvement": .001,
                 "model_name": "历史事故判别模型", "selection_scope": "early training/validation only; late data previously explored"}
    write_json("selection_frozen.json", selection)
    print("FROZEN", json.dumps(selection, ensure_ascii=False), flush=True)
    later_scores, refit_parameters, full_model = {}, {}, None
    for name, model_spec in specifications.items():
        model = fit_model(refit, model_spec)
        later_scores[name], refit_parameters[name] = predict(model, later), serialize(model)
        if name == "full7":
            full_model = model
    csv("input_later_predictions.csv", prediction_table(later, later_scores))
    late_metrics = pd.DataFrame(metric_rows(later, later_scores, "later", "all693"))
    csv("input_later_metrics.csv", late_metrics)
    write_json("input_model_parameters.json", {"fit337": fit_parameters, "refit581": refit_parameters})
    historical = pd.read_csv(PREVIOUS / "A_later_predictions.csv", dtype={"REPORT_NUMBER": str}, float_precision="round_trip")
    assert historical.REPORT_NUMBER.tolist() == later.REPORT_NUMBER.tolist()
    replay = {}
    for current, old in [("categorical4", "categorical4"), ("full7", "combined7"), ("physical_age_diameter_pressure", "physical3")]:
        replay[current] = float(np.max(np.abs(later_scores[current] - historical["score_" + old].to_numpy())))
        assert replay[current] < 1e-12
    oof_refit = rolling_scores(a, specifications[selected], 2021)
    csv("calibration_rolling_refit_scores.csv", oof_refit)
    calibrators_refit = fit_calibrators(oof_refit)
    calibration_later_scores = {n: calibrate(later_scores[selected], par) for n, par in calibrators_refit.items()}
    csv("calibration_later_predictions.csv", prediction_table(later, calibration_later_scores))
    calibration_later_metrics = pd.DataFrame(metric_rows(later, calibration_later_scores, "later", "all693"))
    csv("calibration_later_metrics.csv", calibration_later_metrics)
    write_json("calibration_parameters.json", {"fit_rolling_scores": calibrators_fit, "refit_rolling_scores": calibrators_refit})
    write_json("final_model.json", {**selection, "logistic": refit_parameters[selected],
                                    "calibration": calibrators_refit[chosen_calibration], "input_source": "cohort693.csv",
                                    "output_meaning": "Estimated casualty-report probability within historical reported incidents; not future injury probability at a verified field decision time"})
    error = error_summary(later, calibration_later_scores[chosen_calibration], threshold, raw)
    write_json("final_classification_counts.json", error)
    probability_bins(later, calibration_later_scores)
    csv("figure3_probability_and_errors.csv", calibration_later_metrics.assign(selected=lambda f: f.method.eq(chosen_calibration)))
    main_names = list(dict.fromkeys(["constant", "categorical4", "full7", "physical_age_diameter_pressure", selected]))
    csv("figure1_input_choice.csv", late_metrics[late_metrics.method.isin(main_names)].merge(
        validation_metrics[["method", "AP", "Brier"]].rename(columns={"AP": "validation_AP", "Brier": "validation_Brier"}), on="method"))
    pairs = [(n, "full7") for n in specifications if n not in ["full7", "constant"]]
    extra = [(selected, "physical_age_diameter_pressure"), (selected, "constant")]
    pairs.extend([p for p in extra if p[0] != p[1] and p not in pairs])
    intervals = paired_bootstrap(later, later_scores, pairs, "input_paired")
    validation_interval = paired_bootstrap(validation, {selected: validation_scores[selected], "full7": validation_scores["full7"]},
                                           [(selected, "full7")], "selected_early_paired") if selected != "full7" else pd.DataFrame()
    calibration_intervals = paired_bootstrap(later, calibration_later_scores,
                                             [("intercept_only", "raw"), ("sigmoid", "raw")], "calibration_paired")
    print("INPUT_AND_CALIBRATION_DONE", selected, chosen_calibration, error, flush=True)
    cluster_metrics, cluster_intervals = clustering_comparison(a)
    print("CLUSTER_DONE", flush=True)
    association = associations(refit, full_model)
    print("ASSOCIATION_DONE", flush=True)
    for source, target in [("B_later_predictions.csv", "steel_plastic_later_predictions.csv"),
                           ("B_metrics.csv", "steel_plastic_metrics.csv"),
                           ("B_paired_operator_intervals.csv", "steel_plastic_intervals.csv")]:
        source_table = pd.read_csv(PREVIOUS / source, dtype={"REPORT_NUMBER": str, "OPERATOR_ID": str} if "predictions" in source else None)
        csv(target, source_table)
    write_json("steel_plastic_reuse.json", {"refitted": False, "source": "work/p320_core/prediction",
                                            "choice": "pooled_main", "rationale": "Only 5 early steel positives and 1 later; no established interaction or separate-model benefit",
                                            "materials_and_context_are_retrospective": True})
    for path, digest in hashes.items():
        assert sha(ROOT / path) == digest
    write_json("execution_receipt.json", {"started_utc": started, "finished_utc": now(), "source_hashes_unchanged": True,
                                           "script_sha256": sha(Path(__file__)), "protocol_sha256": sha(OUT / "protocol.md"),
                                           "P320_prediction_max_errors": replay, "input_candidates": len(specifications),
                                           "selected_input": selected, "selected_calibration": chosen_calibration,
                                           "final_confusion": error, "paired_draws": DRAWS, "association_refits": ASSOCIATION_DRAWS,
                                           "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__}})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with warnings.catch_warnings(record=True) as captured, threadpool_limits(limits=1):
        warnings.simplefilter("once")
        main()
    write_json("warnings.json", list(dict.fromkeys(str(w.message) for w in captured)))
