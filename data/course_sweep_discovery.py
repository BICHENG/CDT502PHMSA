"""Frozen-period descriptive mining; casualty labels never select clusters."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
import json
import logging
from pathlib import Path
import platform
import sys
import warnings
from zipfile import ZipFile

import numpy as np
import pandas as pd
import scipy
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import cdist
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from threadpoolctl import threadpool_limits

from study_common import load_data


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/results/course_sweep_20261107/discovery"
FIELDS = ["part", "mat", "location", "cls"]
RAW = dict(zip(FIELDS, ["SYSTEM_PART_INVOLVED", "MATERIAL_INVOLVED", "LOCATION_TYPE", "CLASS_LOCATION_TYPE"]))
SEED = 20261107
MIN_REPORTS = 40
MIN_CASES = 10
MAX_ITEMS = 3
REVIEW_LIMIT = 5
EARLY_END = 2021
UNSEEN = "__UNSEEN_IN_EARLY_PERIOD__"
COURSE = ROOT / "research/course/session5.pdf"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serial(value):
    if isinstance(value, dict):
        return {str(key): serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [serial(item) for item in value]
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (np.floating, float)) and not np.isfinite(value):
        return None
    if isinstance(value, np.floating):
        return float(value)
    return value


def write_json(name, value):
    (OUT / name).write_text(json.dumps(serial(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(name, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(OUT / name, index=False, encoding="utf-8-sig")


def proportion(n, cases):
    if not n:
        return dict(n=0, cases=0, precision=np.nan, wilson_low=np.nan, wilson_high=np.nan)
    p, z = cases / n, 1.959963984540054
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return dict(n=int(n), cases=int(cases), precision=p, wilson_low=center - radius, wilson_high=center + radius)


def mask_metrics(mask, period, outcome):
    group = mask & period
    result = proportion(int(group.sum()), int(outcome[group].sum()))
    result["coverage"] = result["n"] / period.sum()
    result["joint_support"] = result["cases"] / period.sum()
    base = outcome[period].mean()
    result["lift"] = result["precision"] / base if base else np.nan
    return result


def itemset_id(items):
    return " & ".join(f"{field}={value}" for field, value in items)


def fp_growth(transactions, minimum, max_length=MAX_ITEMS):
    """Weighted prefix trees and conditional pattern bases, capped at three items."""
    found = {}

    def mine(weighted, prefix):
        counts = Counter()
        for items, weight in weighted:
            for item in items:
                counts[item] += weight
        counts = {item: n for item, n in counts.items() if n >= minimum}
        root = {"parent": None, "item": None, "count": 0, "children": {}}
        headers = defaultdict(list)
        for items, weight in weighted:
            ordered = sorted((item for item in items if item in counts), key=lambda item: (-counts[item], item))
            node = root
            for item in ordered:
                if item not in node["children"]:
                    child = {"parent": node, "item": item, "count": 0, "children": {}}
                    node["children"][item] = child
                    headers[item].append(child)
                node = node["children"][item]
                node["count"] += weight
        for item in sorted(headers, key=lambda value: (counts[value], value)):
            pattern = prefix + (item,)
            found[frozenset(pattern)] = sum(node["count"] for node in headers[item])
            if len(pattern) == max_length:
                continue
            conditional = []
            for node in headers[item]:
                path, ancestor = [], node["parent"]
                while ancestor["item"] is not None:
                    path.append(ancestor["item"])
                    ancestor = ancestor["parent"]
                if path:
                    conditional.append((tuple(reversed(path)), node["count"]))
            if conditional:
                mine(conditional, pattern)

    mine([(tuple(items), 1) for items in transactions], ())
    return found


def mine_rules(data, early, late):
    logging.info("Enumerating all early-category itemsets and fixed late counts")
    outcome = data.cas.to_numpy(int)
    levels = {field: sorted(data.loc[early, field].unique()) for field in FIELDS}
    values = {field: data[field].to_numpy() for field in FIELDS}
    masks, stats, rows = {}, {}, []
    all_mask = np.ones(len(data), dtype=bool)
    stats[()] = {name: mask_metrics(all_mask, period, outcome) for name, period in [("early", early), ("late", late)]}
    frequent = set()
    for length in range(1, MAX_ITEMS + 1):
        for fields in combinations(FIELDS, length):
            for categories in product(*(levels[field] for field in fields)):
                items = tuple(zip(fields, categories))
                mask = np.logical_and.reduce([values[field] == value for field, value in items])
                masks[items] = mask
                stats[items] = {name: mask_metrics(mask, period, outcome) for name, period in [("early", early), ("late", late)]}
                parents = list(combinations(items, length - 1)) if length > 1 else [()]
                apriori_candidate = length == 1 or all(parent in frequent for parent in parents)
                supported = stats[items]["early"]["n"] >= MIN_REPORTS
                assert not supported or apriori_candidate
                if supported:
                    frequent.add(items)
                row = {"itemset": itemset_id(items), "length": length, "apriori_candidate": apriori_candidate, "frequent_early": supported}
                for name in ("early", "late"):
                    row.update({f"{name}_{key}": value for key, value in stats[items][name].items()})
                rows.append(row)
    itemsets = pd.DataFrame(rows)
    write_csv("itemsets_all_candidates.csv", itemsets)
    write_csv("frequent_itemsets.csv", itemsets.loc[itemsets.frequent_early])

    transactions = [[(field, row[field]) for field in FIELDS] for _, row in data.loc[early].iterrows()]
    case_transactions = [items for items, is_case in zip(transactions, outcome[early]) if is_case]
    fp_all = fp_growth(transactions, MIN_REPORTS)
    fp_cases = fp_growth(case_transactions, MIN_CASES)
    expected_all = {frozenset(items): item["early"]["n"] for items, item in stats.items() if items and item["early"]["n"] >= MIN_REPORTS}
    expected_cases = {frozenset(items): item["early"]["cases"] for items, item in stats.items() if items and item["early"]["cases"] >= MIN_CASES}
    assert fp_all == expected_all and fp_cases == expected_cases
    crosscheck = {"apriori_matches_exact_enumeration": True, "fp_growth_matches_enumeration_reports": True, "fp_growth_matches_enumeration_cases": True,
                  "frequent_report_itemsets": len(fp_all), "frequent_case_itemsets": len(fp_cases), "implementation": "Local weighted prefix tree, no downloaded package", "independent_scientific_discoveries": 1}
    write_json("algorithm_crosscheck.json", crosscheck)
    write_csv("fp_growth_supports.csv", [{"itemset": itemset_id(tuple(sorted(items, key=lambda item: FIELDS.index(item[0])))), "report_support_if_at_least_40": fp_all.get(items), "case_support_if_at_least_10": fp_cases.get(items)} for items in sorted(set(fp_all) | set(fp_cases), key=lambda items: (len(items), sorted(items)))])

    rule_rows, parent_rows = [], []
    for items, metric in stats.items():
        if len(items) < 2:
            continue
        parents = list(combinations(items, len(items) - 1))
        row = {"rule": itemset_id(items), "length": len(items), "parents": json.dumps([itemset_id(parent) for parent in parents])}
        best_early_parent = max(parents, key=lambda parent: (-1 if np.isnan(stats[parent]["early"]["precision"]) else stats[parent]["early"]["precision"], itemset_id(parent)))
        for name in ("early", "late"):
            row.update({f"{name}_{key}": value for key, value in metric[name].items()})
            parent_precisions = [stats[parent][name]["precision"] for parent in parents if stats[parent][name]["n"]]
            best = max(parent_precisions) if parent_precisions else np.nan
            row[f"{name}_best_parent_precision"] = best
            row[f"{name}_gain_over_best_parent_pp"] = 100 * (metric[name]["precision"] - best)
            row[f"{name}_gain_over_early_best_parent_pp"] = 100 * (metric[name]["precision"] - stats[best_early_parent][name]["precision"])
            for parent in parents:
                remainder_n = stats[parent][name]["n"] - metric[name]["n"]
                remainder_cases = stats[parent][name]["cases"] - metric[name]["cases"]
                parent_rows.append({"rule": row["rule"], "parent": itemset_id(parent), "period": name,
                                    "child_n": metric[name]["n"], "child_cases": metric[name]["cases"], "child_precision": metric[name]["precision"],
                                    "parent_n": stats[parent][name]["n"], "parent_cases": stats[parent][name]["cases"], "parent_precision": stats[parent][name]["precision"],
                                    "gain_pp": 100 * (metric[name]["precision"] - stats[parent][name]["precision"]),
                                    "parent_remainder_n": remainder_n, "parent_remainder_cases": remainder_cases,
                                    "parent_remainder_precision": remainder_cases / remainder_n if remainder_n else np.nan})
        row["early_best_parent"] = itemset_id(best_early_parent)
        row["eligible_early"] = metric["early"]["n"] >= MIN_REPORTS and metric["early"]["cases"] >= MIN_CASES
        row["positive_increment_early"] = row["eligible_early"] and metric["early"]["lift"] > 1 and row["early_gain_over_best_parent_pp"] > 1e-10
        rule_rows.append(row)
    rules = pd.DataFrame(rule_rows).sort_values("rule").reset_index(drop=True)
    ranking = rules.loc[rules.positive_increment_early].sort_values(["early_gain_over_best_parent_pp", "early_cases", "length", "rule"], ascending=[False, False, True, True])
    review = ranking.head(REVIEW_LIMIT).rule.tolist()
    rules["frozen_review_rank"] = rules.rule.map({rule: i + 1 for i, rule in enumerate(review)})
    write_csv("rules_all_candidates.csv", rules)
    write_csv("rules_eligible_early.csv", rules.loc[rules.eligible_early])
    write_csv("rules_frozen_review_order.csv", ranking.assign(frozen_rank=np.arange(1, len(ranking) + 1)))
    write_csv("rule_parent_comparisons.csv", parent_rows)
    by_name = {itemset_id(items): mask for items, mask in masks.items()}
    memberships = []
    eligible_names = rules.loc[rules.eligible_early, "rule"].tolist()
    eligible_matrix = np.column_stack([by_name[rule] for rule in eligible_names])
    first_match = np.full(len(data), "UNMATCHED", dtype=object)
    for rule in review:
        first_match[(first_match == "UNMATCHED") & by_name[rule]] = rule
    for i, row in data.iterrows():
        memberships.append({"REPORT_NUMBER": row.REPORT_NUMBER, "period": "early" if early[i] else "late", "cas": row.cas,
                            "eligible_rule_count": int(eligible_matrix[i].sum()), "eligible_rules": json.dumps([rule for rule, match in zip(eligible_names, eligible_matrix[i]) if match]),
                            "first_frozen_review_rule": first_match[i]})
    write_csv("rule_membership.csv", memberships)
    queue, overlaps = [], []
    for name, period in [("early", early), ("late", late)]:
        for rule in review + ["UNMATCHED"]:
            queue.append({"period": name, "first_match_rule": rule, **mask_metrics(first_match == rule, period, outcome)})
        assert sum(row["n"] for row in queue if row["period"] == name) == int(period.sum())
        assert sum(row["cases"] for row in queue if row["period"] == name) == int(outcome[period].sum())
        for first, second in combinations(review, 2):
            intersection = int((by_name[first] & by_name[second] & period).sum())
            union = int(((by_name[first] | by_name[second]) & period).sum())
            overlaps.append({"period": name, "first": first, "second": second, "intersection": intersection, "union": union, "jaccard": intersection / union if union else np.nan})
    write_csv("rules_disjoint_review_groups.csv", queue)
    write_csv("rules_top5_overlap.csv", overlaps)
    prefix_rows, prefix_memberships = [], []
    previous = np.zeros(len(data), dtype=bool)
    for rank, rule in enumerate(review, 1):
        covered = previous | by_name[rule]
        added = covered & ~previous
        for name, period in [("early", early), ("late", late)]:
            prefix_rows.append({"first_rules": rank, "last_rule_added": rule, "period": name,
                                **mask_metrics(covered, period, outcome), "new_reports": int((added & period).sum()), "new_cases": int(outcome[added & period].sum())})
            for index in np.flatnonzero(covered & period):
                prefix_memberships.append({"first_rules": rank, "period": name, "REPORT_NUMBER": data.iloc[index].REPORT_NUMBER,
                                           "cas": int(outcome[index]), "new_at_this_step": bool(added[index])})
        assert np.all(covered >= previous)
        previous = covered
    write_csv("rules_top1to5_coverage_summary.csv", prefix_rows)
    write_csv("rules_top1to5_report_ids.csv", prefix_memberships)
    summary = {"candidate_2_or_3_item_rules": len(rules), "eligible_early_rules": int(rules.eligible_early.sum()), "positive_increment_early_rules": len(ranking),
               "positive_increment_late_among_frozen_positive_rules": int((ranking.late_gain_over_best_parent_pp > 1e-10).sum()),
               "late_at_least_20_and_positive_increment": int(((ranking.late_n >= 20) & (ranking.late_gain_over_best_parent_pp > 1e-10)).sum()),
               "review_top5_frozen_from_early_only": review,
               "review_cumulative_coverage": prefix_rows,
               "review_union_early": mask_metrics(first_match != "UNMATCHED", early, outcome), "review_union_late": mask_metrics(first_match != "UNMATCHED", late, outcome),
               "all_candidate_levels_from_early": levels, "algorithm_crosscheck": crosscheck}
    write_json("rules_summary.json", summary)
    logging.info("Rules complete: %d candidates, %d eligible, %d with positive early parent gain", len(rules), summary["eligible_early_rules"], len(ranking))
    return rules, summary


def encode(data, early, fields):
    levels = {field: sorted(data.loc[early, field].unique()) + [UNSEEN] for field in fields}
    blocks, names, unseen = [], [], {}
    for field in fields:
        values = data[field].where(data[field].isin(levels[field]), UNSEEN).to_numpy()
        blocks.append(np.column_stack([values == value for value in levels[field]]))
        names.extend(f"{field}={value}" for value in levels[field])
        unseen[field] = int((values == UNSEEN).sum())
    matrix = np.column_stack(blocks).astype(float) / np.sqrt(2 * len(fields))
    # Each unequal categorical block contributes exactly 1 / number_of_blocks.
    pairs = np.random.default_rng(SEED).integers(0, len(data), size=(100, 2))
    for first, second in pairs:
        expected = np.mean(data.iloc[first][fields].to_numpy() != data.iloc[second][fields].to_numpy())
        assert abs(np.sum((matrix[first] - matrix[second]) ** 2) - expected) < 1e-12
    return matrix, names, levels, unseen


def relabel(labels, centers):
    order = sorted(range(len(centers)), key=lambda group: tuple(np.round(centers[group], 14)))
    mapping = {old: new for new, old in enumerate(order)}
    return np.array([mapping[value] for value in labels]), centers[order]


def fit_clusters(matrix, algorithm, k):
    if algorithm == "kmeans":
        model = KMeans(n_clusters=k, random_state=SEED, n_init=50, max_iter=500, algorithm="lloyd").fit(matrix)
        labels, centers = model.labels_, model.cluster_centers_
    else:
        tree = linkage(matrix, method=algorithm, metric="euclidean", optimal_ordering=False)
        labels = cut_tree(tree, n_clusters=k).ravel()
        centers = np.vstack([matrix[labels == group].mean(axis=0) for group in range(k)])
    return relabel(labels, centers)


def purity(labels, categories):
    table = pd.crosstab(pd.Series(labels, name="cluster"), pd.Series(np.asarray(categories), name="category"))
    return table.max(axis=1).sum() / table.to_numpy().sum()


def cluster_tables(data, labels, algorithm, variant, period):
    outcome = data.cas.to_numpy(int)
    groups, features, within_part = [], [], []
    for group in sorted(set(labels)):
        mask = labels == group
        groups.append({"algorithm": algorithm, "variant": variant, "period": period, "cluster": int(group), **proportion(int(mask.sum()), int(outcome[mask].sum())),
                       "dominant_part": data.loc[mask, "part"].mode().iloc[0], "part_purity": data.loc[mask, "part"].value_counts(normalize=True).iloc[0]})
        for field in FIELDS:
            for category, count in data.loc[mask, field].value_counts().items():
                features.append({"algorithm": algorithm, "variant": variant, "period": period, "cluster": int(group), "field": field, "category": category, "n": int(count), "within_cluster_share": count / mask.sum()})
        for part in sorted(data.part.unique()):
            subset = mask & data.part.eq(part).to_numpy()
            within_part.append({"algorithm": algorithm, "variant": variant, "period": period, "cluster": int(group), "part": part, **proportion(int(subset.sum()), int(outcome[subset].sum()))})
    return groups, features, within_part


def cluster_experiments(data, early, late, algorithms=("kmeans", "ward"), k_values=range(2, 7), prefix="", best_hierarchical_only=False):
    logging.info("Selecting clusters on early feature structure only")
    matrix, names, levels, unseen = encode(data, early, FIELDS)
    minimum_cluster = max(MIN_REPORTS, int(np.ceil(0.05 * early.sum())))
    candidate_rows, candidate_assignments, fitted = [], [], {}
    for algorithm in algorithms:
        for k in k_values:
            labels, centers = fit_clusters(matrix[early], algorithm, k)
            sizes = np.bincount(labels, minlength=k)
            score = silhouette_score(matrix[early], labels, metric="euclidean")
            row = {"algorithm": algorithm, "k": k, "silhouette_early": score, "minimum_cluster_n": int(sizes.min()), "maximum_cluster_n": int(sizes.max()), "eligible_minimum_size": bool(sizes.min() >= minimum_cluster),
                   "inertia_early": float(np.sum((matrix[early] - centers[labels]) ** 2)), "part_ari_early": adjusted_rand_score(data.loc[early, "part"], labels),
                   "part_nmi_early": normalized_mutual_info_score(data.loc[early, "part"], labels), "part_purity_early": purity(labels, data.loc[early, "part"])}
            candidate_rows.append(row)
            candidate_assignments.extend({"REPORT_NUMBER": report, "algorithm": algorithm, "k": k, "cluster": int(label)} for report, label in zip(data.loc[early, "REPORT_NUMBER"], labels))
            fitted[(algorithm, k)] = (labels, centers)
    choices = pd.DataFrame(candidate_rows)
    choices["selected"] = False
    all_groups, all_features, all_within_part, assignments, comparisons, prototypes = [], [], [], [], [], {}
    raw_matrix, raw_names, raw_levels, raw_unseen = encode(data, early, list(RAW.values()))
    selected = {}
    rejected = []
    retained_algorithms = list(algorithms)
    if best_hierarchical_only:
        eligible_hierarchy = choices.loc[choices.algorithm.ne("kmeans") & choices.eligible_minimum_size]
        best_hierarchy = eligible_hierarchy.sort_values(["silhouette_early", "k", "algorithm"], ascending=[False, True, True]).iloc[0].algorithm if len(eligible_hierarchy) else None
        retained_algorithms = [algorithm for algorithm in algorithms if algorithm in ["kmeans", best_hierarchy]]
    for algorithm in algorithms:
        if not choices.loc[choices.algorithm.eq(algorithm), "eligible_minimum_size"].any():
            rejected.append({"algorithm": algorithm, "reason": "No k meets the prespecified minimum early group size"})
    for algorithm in retained_algorithms:
        eligible = choices.loc[choices.algorithm.eq(algorithm) & choices.eligible_minimum_size]
        if not len(eligible):
            continue
        chosen = eligible.sort_values(["silhouette_early", "k"], ascending=[False, True]).iloc[0]
        k = int(chosen.k)
        choices.loc[choices.algorithm.eq(algorithm) & choices.k.eq(k), "selected"] = True
        main_labels, centers = fitted[(algorithm, k)]
        raw_labels, raw_centers = fit_clusters(raw_matrix[early], algorithm, k)
        selected[algorithm] = {"k": k, "minimum_required_n": minimum_cluster, "silhouette_early": chosen.silhouette_early}
        prototypes[algorithm] = {"derived": {"feature_names": names, "centers": centers}, "raw_sensitivity": {"feature_names": raw_names, "centers": raw_centers}}
        labels_by_variant = {}
        for variant, features_matrix, train_labels, frozen_centers in [("derived", matrix, main_labels, centers), ("raw_sensitivity", raw_matrix, raw_labels, raw_centers)]:
            projected = cdist(features_matrix, frozen_centers).argmin(axis=1)
            combined = projected.copy()
            combined[early] = train_labels
            labels_by_variant[variant] = combined
            for period, mask in [("early", early), ("late", late)]:
                subset = data.loc[mask].reset_index(drop=True)
                labels = combined[mask]
                groups, distributions, within_part = cluster_tables(subset, labels, algorithm, variant, period)
                all_groups.extend(groups)
                all_features.extend(distributions)
                all_within_part.extend(within_part)
                assignments.extend({"REPORT_NUMBER": row.REPORT_NUMBER, "period": period, "algorithm": algorithm, "variant": variant, "k": k, "cluster": int(label), "nearest_center_cluster": int(nearest), "cas": int(row.cas)}
                                   for (_, row), label, nearest in zip(subset.iterrows(), labels, projected[mask]))
                comparisons.append({"algorithm": algorithm, "variant": variant, "period": period, "k": k, "n": len(subset),
                                    "silhouette": silhouette_score(features_matrix[mask], labels) if 1 < len(set(labels)) < len(labels) else np.nan,
                                    "part_ari": adjusted_rand_score(subset.part, labels), "part_nmi": normalized_mutual_info_score(subset.part, labels), "part_purity": purity(labels, subset.part),
                                    "minimum_cluster_n": int(np.bincount(labels, minlength=k).min()),
                                    "training_partition_nearest_center_disagreements": int((projected[early] != train_labels).sum()) if period == "early" else None})
        selected[algorithm]["raw_mapping_ari_early"] = adjusted_rand_score(labels_by_variant["derived"][early], labels_by_variant["raw_sensitivity"][early])
        selected[algorithm]["raw_mapping_ari_late"] = adjusted_rand_score(labels_by_variant["derived"][late], labels_by_variant["raw_sensitivity"][late])
        selected[algorithm]["late_cluster_counts"] = np.bincount(labels_by_variant["derived"][late], minlength=k).tolist()
    assert len(assignments) == len(data) * 2 * len(selected)
    write_csv(prefix + "cluster_selection.csv", choices)
    write_csv(prefix + "cluster_candidate_assignments.csv", candidate_assignments)
    write_csv(prefix + "cluster_assignments.csv", assignments)
    write_csv(prefix + "cluster_group_outcomes.csv", all_groups)
    write_csv(prefix + "cluster_feature_composition.csv", all_features)
    write_csv(prefix + "cluster_within_part_outcomes.csv", all_within_part)
    write_csv(prefix + "cluster_comparisons.csv", comparisons)
    write_json(prefix + "frozen_cluster_centers.json", prototypes)
    base = []
    for name, mask in [("early", early), ("late", late)]:
        base.append({"period": name, "part_groups": int(data.loc[mask, "part"].nunique()), "silhouette_in_same_four_block_space": silhouette_score(matrix[mask], data.loc[mask, "part"]),
                     "unique_four_field_combinations": len(data.loc[mask, FIELDS].drop_duplicates()), "reports": int(mask.sum())})
    write_csv(prefix + "part_baseline_structure.csv", base)
    summary = {"selected": selected, "minimum_group_n": minimum_cluster, "feature_blocks": FIELDS, "levels_from_early": levels, "unseen_by_field": unseen,
               "raw_levels_from_early": raw_levels, "raw_unseen_by_field": raw_unseen, "part_baseline": base,
               "squared_distance": "Number of differing categorical fields divided by four; full one-hot times 1/sqrt(8)",
               "late_assignment": "Nearest frozen early centroid; no late refitting. Hierarchical methods have no native predict method, so this is an explicit extension.",
               "selection": f"Highest early silhouette among k={list(k_values)} with every group >= max(40, ceil(0.05*n_early)); smaller k breaks exact ties; no casualty outcomes used.",
               "algorithms": algorithms, "rejected_algorithms": rejected,
               "best_hierarchical_only": best_hierarchical_only,
               "course_followup_reason": "Lectures cover single/complete/average and an individual clustering exercise uses k=2..8. This is method coverage, not a group-brief requirement; follow-up selection still ignores late outcomes" if prefix else None,
               "pca": "Not run: no decision requiring dimensional reduction; four categorical blocks remain directly interpretable.",
               "dbscan": "Not run: not found in checked Session 5 course outline/OCR; repeated discrete combinations also preclude treating density islands as new physical groups."}
    write_json(prefix + "clusters_summary.json", summary)
    logging.info("Clustering complete: %s", {name: value["k"] for name, value in selected.items()})
    return choices, pd.DataFrame(all_groups), pd.DataFrame(comparisons), summary


def condense_itemsets():
    table = pd.read_csv(OUT / "frequent_itemsets.csv")
    sets = [frozenset(value.split(" & ")) for value in table.itemset]
    closed, maximal = [], []
    for i, items in enumerate(sets):
        supersets = [j for j, other in enumerate(sets) if items < other]
        closed.append(not any(table.iloc[i].early_n == table.iloc[j].early_n for j in supersets))
        maximal.append(not supersets)
    table["closed_within_max_length_3"] = closed
    table["maximal_within_max_length_3"] = maximal
    write_csv("itemsets_condensed.csv", table)
    result = {"frequent_itemsets": len(table), "closed_within_length_3": sum(closed), "maximal_within_length_3": sum(maximal),
              "closed_removed_fraction": 1 - sum(closed) / len(table), "maximal_removed_fraction": 1 - sum(maximal) / len(table),
              "scope": "Closure/maximality only within the enumerated <=3-item search space. Four-feature supersets were not tested, so these are not globally maximal itemsets.",
              "interpretation": "Closed itemsets remove equal-support nested redundancy; maximal itemsets discard subset support needed for parent confidence comparisons. Frozen rules remain unchanged."}
    write_json("itemset_compression.json", result)
    return result


def process_information(data, early, late):
    from course_sweep_models import GRIDS, budget, fit, predict
    from sklearn.metrics import average_precision_score, brier_score_loss

    logging.info("Separate retrospective process-information experiment; no changes to rule or cluster selection")
    fields = ["CAUSE", "IGNITE_IND", "EXPLODE_IND"]
    assert all(field in data for field in fields)
    assert set(data.IGNITE_IND.unique()) == {"YES", "NO"}
    assert set(data.EXPLODE_IND.unique()) == {"YES", "NO", ""}
    assert data.CAUSE.ne("").all()
    blank = data.EXPLODE_IND.eq("")
    no_ignite_yes_explode = data.IGNITE_IND.eq("NO") & data.EXPLODE_IND.eq("YES")
    assert int(blank.sum()) == 173 and data.loc[blank, "IGNITE_IND"].eq("NO").all()
    columns_by_model = {"basic": FIELDS, "basic_cause": FIELDS + ["CAUSE"],
                        "basic_ignition_explosion": FIELDS + ["IGNITE_IND", "EXPLODE_IND"],
                        "basic_all_process": FIELDS + fields,
                        "basic_cause_ignition_no_explosion": FIELDS + ["CAUSE", "IGNITE_IND"]}
    frame = data.copy()
    frame["EXPLODE_IND"] = frame.EXPLODE_IND.replace("", "__BLANK_CONDITIONAL__")
    fitting = frame.loc[frame.received_year.le(2017)]
    validation = frame.loc[frame.received_year.between(2018, 2021)]
    training, evaluation = frame.loc[early], frame.loc[late]
    grid = GRIDS["logistic"]
    protocol = {"purpose": "Retrospective information ablation, excluded from the four-input algorithm leaderboard and from pre-incident facility prediction", "seed": SEED,
                "split": {"fit_through": 2017, "validation": [2018, 2021], "refit_through": 2021, "evaluation_from": 2022},
                "feature_sets": columns_by_model, "grid": grid, "selection": "Maximum validation AP, then minimum Brier, then original grid order",
                "same_review_budget": 53, "tie_policy": "Uniform random choice within equal score at cutoff; expected hits and min/max retained",
                "helper_source_sha256": sha(ROOT / "research/analysis/course_sweep_models.py"), "missing_explosion": "Independent categorical state; blank is not changed to NO",
                "time_scope": "Cause and ignition/explosion are reported after the event and may be revised. This experiment describes recorded outcomes, not causal effects or prevention performance."}
    write_json("process_protocol.json", protocol)
    with ZipFile(ROOT / "research/inputs/data/incident_primary.zip") as archive:
        form_name = next(name for name in archive.namelist() if name.endswith(".pdf"))
        form_hash = hashlib.sha256(archive.read(form_name)).hexdigest()
    definition = {"source_in_locked_zip": form_name, "source_sha256": form_hash, "form_pages": [3, 9],
                  "instructions_url": "https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2023-12/Current_GD_Incident_Instructions_PHMSA%20F%207100.1_2023-09%20and%20Beyond.pdf",
                  "instructions_pages": [10, 18], "verified_on": "2026-11-07",
                  "CAUSE": "Operator-reported apparent cause, one main cause category; not a causal effect estimate or all contributing factors.",
                  "IGNITE_IND": "Released gas ignited, including conflagration, detonation or explosion even without residual fire.",
                  "EXPLODE_IND": "Ignition with a sudden and violent energy release. Current form asks this after ignition=YES.",
                  "blank_explosion": {"all": int(blank.sum()), "early": int((blank.to_numpy() & early).sum()), "late": int((blank.to_numpy() & late).sum()), "all_have_ignite_no": True},
                  "ignite_no_explode_yes": {"all": int(no_ignite_yes_explode.sum()), "early": int((no_ignite_yes_explode.to_numpy() & early).sum()), "late": int((no_ignite_yes_explode.to_numpy() & late).sum()), "treatment": "Retain the recorded historical combination. Current-form definitions do not establish that historical reports are logically incorrect."}}
    write_json("process_field_definitions.json", definition)
    audit, tables, joints = [], [], []
    for period, mask in [("all", np.ones(len(data), bool)), ("early", early), ("late", late)]:
        for field in fields:
            audit.append({"period": period, "field": field, "reports": int(mask.sum()), "blank": int(data.loc[mask, field].eq("").sum()), "categories": json.dumps(data.loc[mask, field].value_counts().to_dict())})
            for category, rows in data.loc[mask].groupby(field):
                tables.append({"period": period, "field": field, "category": category or "__BLANK_CONDITIONAL__", **proportion(len(rows), int(rows.cas.sum()))})
        for (ignite, explode), rows in data.loc[mask].groupby(["IGNITE_IND", "EXPLODE_IND"]):
            joints.append({"period": period, "ignite": ignite, "explode": explode or "__BLANK_CONDITIONAL__", **proportion(len(rows), int(rows.cas.sum()))})
    write_csv("process_field_audit.csv", audit)
    write_csv("process_contingencies.csv", tables)
    write_csv("process_ignition_explosion_cells.csv", joints)
    write_csv("process_missingness_by_received_year.csv", data.groupby(["received_year", "IGNITE_IND", "EXPLODE_IND"]).agg(reports=("cas", "size"), casualty_reports=("cas", "sum")).reset_index())
    write_csv("process_ignite_no_explode_yes.csv", data.loc[no_ignite_yes_explode, ["REPORT_NUMBER", "received_year", "IGNITE_IND", "EXPLODE_IND", "cas"]])
    trials, results, predictions, coefficients, caught_warnings = [], [], [], [], []
    for name, columns in columns_by_model.items():
        candidates = []
        for index, parameters in enumerate(grid):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                fitted = fit("logistic", fitting, parameters, columns=columns)
                scores = predict("logistic", fitted, validation, columns=columns)
            caught_warnings.extend({"feature_set": name, "stage": "validation", "parameters": parameters, "warning": str(warning.message)} for warning in caught)
            ap = float(average_precision_score(validation.cas, scores))
            brier = float(brier_score_loss(validation.cas, scores))
            candidates.append((ap, -brier, -index, parameters, scores))
            trials.append({"feature_set": name, "grid_index": index, "C": parameters["C"], "validation_n": len(validation), "validation_cases": int(validation.cas.sum()), "validation_AP": ap, "validation_Brier": brier})
        winner = max(candidates, key=lambda candidate: candidate[:3])
        fitted = fit("logistic", training, winner[3], columns=columns)
        scores = predict("logistic", fitted, evaluation, columns=columns)
        reviewed = budget(evaluation.cas.to_numpy(), scores, .2)
        assert reviewed["review_n"] == 53
        row = {"feature_set": name, "fields": "|".join(columns), "selected_C": winner[3]["C"], "validation_AP": winner[0], "validation_Brier": -winner[1],
               "evaluation_n": len(evaluation), "evaluation_cases": int(evaluation.cas.sum()), "AP": float(average_precision_score(evaluation.cas, scores)),
               "Brier": float(brier_score_loss(evaluation.cas, scores)), **reviewed}
        results.append(row)
        for period, subset, probabilities in [("validation", validation, winner[4]), ("evaluation", evaluation, scores)]:
            predictions.extend({"REPORT_NUMBER": report, "period": period, "feature_set": name, "cas": int(case), "probability": float(probability)} for report, case, probability in zip(subset.REPORT_NUMBER, subset.cas, probabilities))
        names = fitted[0].get_feature_names_out(columns)
        coefficients.extend({"feature_set": name, "feature": feature, "coefficient": float(value)} for feature, value in zip(names, fitted[-1].coef_[0]))
        coefficients.append({"feature_set": name, "feature": "INTERCEPT", "coefficient": float(fitted[-1].intercept_[0])})
    result = pd.DataFrame(results)
    for metric in ["AP", "Brier", "expected_hits"]:
        result[f"delta_{metric}_vs_basic"] = result[metric] - result.iloc[0][metric]
    write_csv("process_information.csv", result)
    write_csv("process_parameter_selection.csv", trials)
    write_csv("process_predictions.csv", predictions)
    write_csv("process_coefficients.csv", coefficients)
    write_json("process_warnings.json", caught_warnings)
    basic_model = ROOT / "research/results/course_sweep_20261107/models/model_metrics.csv"
    if basic_model.exists():
        existing = pd.read_csv(basic_model).query("method == 'logistic'")
        if len(existing):
            check = {metric: abs(float(existing.iloc[0][metric]) - float(result.iloc[0][metric])) for metric in ["AP", "Brier"]}
            write_json("process_basic_model_match.json", check)
            assert max(check.values()) < 1e-10
    logging.info("Process information complete: %s", result[["feature_set", "AP", "Brier", "expected_hits"]].to_dict("records"))
    return result, definition


def rule_budget_comparison(data, late, rule_summary):
    from course_sweep_models import budget

    path = ROOT / "research/results/course_sweep_20261107/models/later_predictions.csv"
    scores = pd.read_csv(path, dtype={"REPORT_NUMBER": str}, float_precision="round_trip").sort_values("REPORT_NUMBER").reset_index(drop=True)
    expected = data.loc[late].reset_index(drop=True)
    assert scores.REPORT_NUMBER.tolist() == expected.REPORT_NUMBER.tolist()
    assert scores.cas.tolist() == expected.cas.tolist()
    rows = []
    for prefix in rule_summary["review_cumulative_coverage"]:
        if prefix["period"] != "late":
            continue
        n = prefix["n"]
        for method in ["part_only", "logistic_proposal", "forest"]:
            measured = budget(scores.cas, scores[f"score_{method}"], (n - .5) / len(scores))
            assert measured["review_n"] == n
            rows.append({"first_rules": prefix["first_rules"], "review_n": n, "rule_hits": prefix["cases"], "reference": method,
                         "reference_expected_hits": measured["expected_hits"], "rule_minus_reference_hits": prefix["cases"] - measured["expected_hits"],
                         "reference_tie_minimum_hits": measured["minimum_hits_from_ties"], "reference_tie_maximum_hits": measured["maximum_hits_from_ties"]})
    write_csv("rules_equal_budget_comparison.csv", rows)
    write_json("rules_equal_budget_source.json", {"path": str(path.relative_to(ROOT)), "sha256": sha(path), "method": "Read fixed model scores, use exactly the number of unique reports covered by each frozen rule prefix; equal-score ties averaged uniformly"})
    return pd.DataFrame(rows)


def verify_outputs(data, late):
    from sklearn.metrics import average_precision_score, brier_score_loss

    candidates = pd.read_csv(OUT / "rules_all_candidates.csv", float_precision="round_trip")
    for row in candidates.itertuples():
        mask = np.ones(len(data), dtype=bool)
        for item in row.rule.split(" & "):
            field, category = item.split("=", 1)
            mask &= data[field].eq(category).to_numpy()
        for name, period in [("early", ~late), ("late", late)]:
            selected = data.loc[mask & period]
            assert len(selected) == getattr(row, f"{name}_n")
            assert int(selected.cas.sum()) == getattr(row, f"{name}_cases")
    ids = pd.read_csv(OUT / "rules_top1to5_report_ids.csv", dtype={"REPORT_NUMBER": str})
    coverage = pd.read_csv(OUT / "rules_top1to5_coverage_summary.csv")
    for row in coverage.itertuples():
        subset = ids.loc[ids.period.eq(row.period) & ids.first_rules.eq(row.first_rules)]
        assert subset.REPORT_NUMBER.is_unique and len(subset) == row.n and subset.cas.sum() == row.cases
        assert subset.new_at_this_step.sum() == row.new_reports
        assert subset.loc[subset.new_at_this_step, "cas"].sum() == row.new_cases
    assignment_checks = 0
    for prefix in ["", "course_"]:
        centers = json.loads((OUT / f"{prefix}frozen_cluster_centers.json").read_text(encoding="utf-8"))
        assignments = pd.read_csv(OUT / f"{prefix}cluster_assignments.csv", dtype={"REPORT_NUMBER": str})
        summary = json.loads((OUT / f"{prefix}clusters_summary.json").read_text(encoding="utf-8"))
        target = data.loc[late].reset_index(drop=True)
        for algorithm, variants in centers.items():
            for variant, frozen in variants.items():
                levels = summary["levels_from_early"] if variant == "derived" else summary["raw_levels_from_early"]
                columns = []
                for name in frozen["feature_names"]:
                    field, category = name.split("=", 1)
                    values = target[field].where(target[field].isin(levels[field]), UNSEEN)
                    columns.append(values.eq(category).to_numpy())
                matrix = np.column_stack(columns) / np.sqrt(8)
                squared = np.sum((matrix[:, None, :] - np.asarray(frozen["centers"])[None, :, :]) ** 2, axis=2)
                saved = assignments.loc[assignments.period.eq("late") & assignments.algorithm.eq(algorithm) & assignments.variant.eq(variant)].set_index("REPORT_NUMBER").loc[target.REPORT_NUMBER]
                labels = saved.cluster.to_numpy(int)
                assert np.all(squared[np.arange(len(labels)), labels] <= squared.min(axis=1) + 1e-12)
                assert saved.cas.to_numpy().tolist() == target.cas.tolist()
                assignment_checks += len(labels)
    predictions = pd.read_csv(OUT / "process_predictions.csv", dtype={"REPORT_NUMBER": str}, float_precision="round_trip")
    measures = pd.read_csv(OUT / "process_information.csv", float_precision="round_trip")
    for row in measures.itertuples():
        subset = predictions.loc[predictions.period.eq("evaluation") & predictions.feature_set.eq(row.feature_set)]
        assert subset.REPORT_NUMBER.is_unique and len(subset) == 264 and subset.cas.sum() == 65
        assert abs(average_precision_score(subset.cas, subset.probability) - row.AP) < 1e-12
        assert abs(brier_score_loss(subset.cas, subset.probability) - row.Brier) < 1e-12
    write_json("saved_output_verification.json", {"rule_period_cells_recounted": len(candidates) * 2, "prefix_membership_groups_reconciled": len(coverage),
                                                  "late_cluster_assignments_checked_against_frozen_centers": assignment_checks, "process_metric_rows_recomputed": len(measures), "passed": True})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(OUT / "run.log", mode="w", encoding="utf-8"), logging.StreamHandler()])
    logging.info("Loading locked cohort and validating against current basic analysis table")
    data = load_data().sort_values("REPORT_NUMBER").reset_index(drop=True)
    assert len(data) == 1550 and int(data.cas.sum()) == 369
    assert data.REPORT_NUMBER.is_unique
    audit_path = ROOT / "research/results/basic_comparison/audit/analysis_ready.csv"
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False).sort_values("REPORT_NUMBER").reset_index(drop=True)
    assert data.REPORT_NUMBER.tolist() == audit.REPORT_NUMBER.tolist()
    compare = [column for column in audit if column in data]
    for column in compare:
        assert data[column].astype(str).equals(audit[column]), f"Audit mismatch in {column}"
    received = pd.to_datetime(data.REPORT_RECEIVED_DATE, format="%m/%d/%Y")
    assert np.array_equal(received.dt.year.to_numpy(), data.received_year.to_numpy())
    assert data.location.equals(data.LOCATION_TYPE) and data.cls.equals(data.CLASS_LOCATION_TYPE)
    early = data.received_year.between(2010, EARLY_END).to_numpy()
    late = data.received_year.ge(EARLY_END + 1).to_numpy()
    assert np.all(early ^ late)
    mapping = []
    for field, raw in RAW.items():
        assert data.groupby(raw)[field].nunique().max() == 1
        for (original, derived), group in data.groupby([raw, field]):
            mapping.append({"field": field, "raw_field": raw, "raw_category": original, "derived_category": derived,
                            "reports": len(group), "early_reports": int(early[group.index].sum()), "late_reports": int(late[group.index].sum())})
    write_csv("raw_to_derived_mapping.csv", mapping)
    write_csv("analysis_inputs.csv", data[["REPORT_NUMBER", "OPERATOR_ID", "received_year", "incident_year", "cas"] + FIELDS + list(RAW.values())].assign(period=np.where(early, "early", "late")))
    course_ocr = ROOT / "research/course/text/ocr_all.json"
    ocr = json.loads(course_ocr.read_text(encoding="utf-8"))
    relevant_course = [row for row in ocr if row["source"] == COURSE.name and (row["page"] in [2, 5, 29, 41, 43] or 14 <= row["page"] <= 28)]
    assert any("FP" in row["text"].replace(" ", "") and row["page"] == 2 for row in relevant_course)
    write_json("course_evidence.json", {"source": str(COURSE), "source_sha256": sha(COURSE), "ocr_cache_sha256": sha(course_ocr), "pages": relevant_course,
                                         "dbscan_text_found": any("dbscan" in row["text"].lower() for row in ocr if row["source"] == COURSE.name)})
    protocol = {"seed": SEED, "early_received_years": [2010, EARLY_END], "late_received_years": [2022, int(data.received_year.max())],
                "rule_minimum_reports_early": MIN_REPORTS, "rule_minimum_casualty_reports_early": MIN_CASES, "rule_antecedent_lengths": [2, 3],
                "rule_highlight": "First five rules with early lift>1 and positive gain over every immediate parent, ordered by minimum parent gain, cases, shorter antecedent, name. No late selection.",
                "rule_overlap": "Full eligible membership retained; highlighted rules assigned disjoint first-match groups in frozen early order, plus unmatched.",
                "intervals": "Wilson 95%, independent Bernoulli approximation; no adjustment for operator dependence or multiple mining comparisons. Not causal intervals.",
                "cluster_k": list(range(2, 7)), "cluster_minimum_group_n": max(MIN_REPORTS, int(np.ceil(0.05 * early.sum()))), "cluster_kmeans_n_init": 50,
                "cluster_selection": "Early silhouette and minimum size only, no outcome; raw-category sensitivity uses the selected k without retuning.",
                "late_use": "Evaluation only; failures and zero-support rules stay visible. 2026 coverage is incomplete.",
                "decision_scope": "Prioritize combinations for retrospective incident review; no estimate of pipeline failure probability, no causal effect, no replacement-budget optimization."}
    write_json("protocol.json", protocol)
    with threadpool_limits(limits=1):
        rules, rule_summary = mine_rules(data, early, late)
        choices, groups, comparisons, cluster_summary = cluster_experiments(data, early, late)
        course_choices, course_groups, course_comparisons, course_summary = cluster_experiments(data, early, late, algorithms=("kmeans", "single", "complete", "average"), k_values=range(2, 9), prefix="course_", best_hierarchical_only=True)
        compression = condense_itemsets()
        process_results, process_definitions = process_information(data, early, late)
        fair_budget = rule_budget_comparison(data, late, rule_summary)
        verify_outputs(data, late)
    receipt = {"completed_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
               "versions": {"numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__}, "seed": SEED,
               "sources": {str(path.relative_to(ROOT)): sha(path) for path in [ROOT / "research/inputs/data/incident_primary.zip", ROOT / "research/results/analysis_primary.csv", audit_path, ROOT / "research/inputs/sources.json", Path(__file__), ROOT / "research/analysis/study_common.py"]},
               "cohort": {"reports": len(data), "casualty_reports": int(data.cas.sum()), "early": proportion(int(early.sum()), int(data.loc[early, "cas"].sum())), "late": proportion(int(late.sum()), int(data.loc[late, "cas"].sum()))},
               "audit": {"reports_match": True, "columns_compared": compare, "all_shared_columns_match": True, "cls_matches_raw": True, "raw_mapping_checked": True},
               "self_checks": {"apriori_and_fp_growth_exact_counts": True, "disjoint_review_groups_reconcile": True, "categorical_distance_verified": True, "all_selected_assignments_complete": True},
               "outcome_used_for_cluster_features_or_k": False,
               "command": "python research/analysis/course_sweep_discovery.py"}
    write_json("receipt.json", receipt)
    highlights = rules.set_index("rule").loc[rule_summary["review_top5_frozen_from_early_only"]]
    lines = ["# 发现与无监督实验", "", "本轮只研究哪些基本条件组合值得事故复盘关注，以及自动分组能否补充既有部件分类。", "",
             f"固定样本为 1,550 份报告、369 份伤亡报告。早期为 {early.sum()} 份、{int(data.loc[early, 'cas'].sum())} 份伤亡；较晚为 {late.sum()} 份、{int(data.loc[late, 'cas'].sum())} 份伤亡。按收件年划分，较晚含不完整的 2026 年。", "",
             "## 关联规则", "", f"精确枚举了 {len(rules)} 个两项或三项候选；{rule_summary['eligible_early_rules']} 个达到早期至少40份报告和10份伤亡报告。{rule_summary['positive_increment_early_rules']} 个规则的早期伤亡比例高于总体且高于每个直接父规则。Apriori 与 FP-Growth 的支持度完全一致，这是一项发现、两种算法核对。", "",
             "| 早期固定顺序 | 规则 | 早期伤亡/报告 | 较晚伤亡/报告 | 较晚伤亡比例 | 较晚95% Wilson区间 | 较晚比最佳父规则高多少百分点 |", "|---:|---|---:|---:|---:|---:|---:|"]
    for rank, (rule, row) in enumerate(highlights.iterrows(), 1):
        lines.append(f"| {rank} | {rule} | {int(row.early_cases)}/{int(row.early_n)} | {int(row.late_cases)}/{int(row.late_n)} | {row.late_precision:.1%} | {row.late_wilson_low:.1%}–{row.late_wilson_high:.1%} | {row.late_gain_over_best_parent_pp:+.1f} |")
    review_union = rule_summary["review_union_late"]
    full_budget = fair_budget.loc[fair_budget.first_rules.eq(REVIEW_LIMIT)].set_index("reference")
    lines += ["", f"全部早期增益规则中，较晚仍高于所有直接父规则的有 {rule_summary['positive_increment_late_among_frozen_positive_rules']} 个，其中较晚覆盖至少20份的有 {rule_summary['late_at_least_20_and_positive_increment']} 个。这些是冻结规则的评价，不能再按较晚结果挑规则。", "",
              f"采用判断：关联规则仅补充复盘组合画像，不采用为优于简单部件排序的筛查方法，也不单列规则发现主章。固定前5条去重后查看较晚 {review_union['n']} 份、命中 {review_union['cases']} 份伤亡；同样查看 {review_union['n']} 份，部件规则期望命中 {full_budget.loc['part_only', 'reference_expected_hits']:.3f}，原GLM为 {full_budget.loc['logistic_proposal', 'reference_expected_hits']:.3f}，随机森林为 {full_budget.loc['forest', 'reference_expected_hits']:.3f}。前1至5条的每个累计额度均未超过部件规则。", "",
              f"早期增益最大的第1条由 {highlights.iloc[0].early_cases:.0f}/{highlights.iloc[0].early_n:.0f} 降至较晚 {highlights.iloc[0].late_cases:.0f}/{highlights.iloc[0].late_n:.0f}，其父规则增益由 {highlights.iloc[0].early_gain_over_best_parent_pp:+.1f} 变为 {highlights.iloc[0].late_gain_over_best_parent_pp:+.1f} 个百分点。第4条虽有 {highlights.iloc[3].late_precision:.1%} 的较晚伤亡比例，却低于最佳父规则的 {highlights.iloc[3].late_best_parent_precision:.1%}，且只有 {int(highlights.iloc[3].late_n)} 份。高比例本身不证明多加条件有价值。", "",
              "规则会重叠。第2条是第1条的子集，在两期都不增加独立案例。逐份匹配及冻结先后顺序见 rule_membership.csv，互斥分组见 rules_disjoint_review_groups.csv；不能相加各条原始覆盖数。前1至5条的累计编号和新增覆盖另存，供同等复盘数量的比较。", "",
              "| 固定采用前几条 | 较晚去重报告数 | 命中伤亡数 | 本步新增报告 | 本步新增伤亡 |", "|---:|---:|---:|---:|---:|"]
    for row in rule_summary["review_cumulative_coverage"]:
        if row["period"] == "late":
            lines.append(f"| {row['first_rules']} | {row['n']} | {row['cases']} | {row['new_reports']} | {row['new_cases']} |")
    lines += ["", "公平对照从 models/later_predictions.csv 的固定分数独立核算，结果见 rules_equal_budget_comparison.csv。对照只改变查看数量，不重拟合模型或重选规则。", ""]
    lines += ["", "## 初始聚类试验", "",
              "采用完整 one-hot，四类输入各占等权。平方距离等于四字段不一致的比例；没有给名义类别编顺序号，也没有用标准化放大稀有类别。早期在 k=2至6 中选择轮廓系数最高且每组不少于预定规模的方案。伤亡字段只用于选择完成后的描述。", "",
              "| 方法 | 早期选定k | 早期轮廓系数 | 较晚各组报告数 | 与原始类别编码分组的较晚ARI |", "|---|---:|---:|---|---:|"]
    for algorithm, selected in cluster_summary["selected"].items():
        lines.append(f"| {algorithm} | {selected['k']} | {selected['silhouette_early']:.3f} | {selected['late_cluster_counts']} | {selected['raw_mapping_ari_late']:.3f} |")
    composition = pd.read_csv(OUT / "cluster_feature_composition.csv")
    km_late = groups.loc[groups.algorithm.eq("kmeans") & groups.variant.eq("derived") & groups.period.eq("late")]
    baseline_silhouette = cluster_summary["part_baseline"][0]["silhouette_in_same_four_block_space"]
    ward_disagreements = int(comparisons.loc[comparisons.algorithm.eq("ward") & comparisons.variant.eq("derived") & comparisons.period.eq("early"), "training_partition_nearest_center_disagreements"].iloc[0])
    lines += ["", f"既有7类部件在同一四字段空间中的早期轮廓系数为 {baseline_silhouette:.3f}。KMeans为 {cluster_summary['selected']['kmeans']['silhouette_early']:.3f}，Ward为 {cluster_summary['selected']['ward']['silhouette_early']:.3f}；两种方法选到搜索上限6，只能称为本次2至6范围内的选择。与部件分组不同，不自动等于增加了可行动信息。", "",
              "KMeans 的组可以解释为材料与地点组合。下表按早期各组的主要类别描述，较晚只读回冻结分组的伤亡数；描述不是确定机制。", "",
              "| 冻结组编号 | 早期最常见部件 | 早期最常见材料 | 早期最常见地点 | 较晚伤亡/报告 | 较晚伤亡比例 |", "|---:|---|---|---|---:|---:|"]
    for group, feature_rows in composition.loc[composition.algorithm.eq("kmeans") & composition.variant.eq("derived") & composition.period.eq("early")].groupby("cluster"):
        dominant = {field: rows.sort_values("n", ascending=False).iloc[0] for field, rows in feature_rows.groupby("field")}
        late_row = km_late.loc[km_late.cluster.eq(group)].iloc[0]
        descriptions = [f"{dominant[field]['category']} {dominant[field]['within_cluster_share']:.1%}" for field in ["part", "mat", "location"]]
        lines.append(f"| {group} | {' | '.join(descriptions)} | {int(late_row.cases)}/{int(late_row.n)} | {late_row.precision:.1%} |")
    within = pd.read_csv(OUT / "cluster_within_part_outcomes.csv")
    main_cells = within.loc[within.algorithm.eq("kmeans") & within.variant.eq("derived") & within.period.eq("late") & within.part.eq("MAIN") & within.n.ge(20)]
    main_text = "、".join(f"组{int(row.cluster)}为{int(row.cases)}/{int(row.n)}={row.precision:.1%}" for row in main_cells.itertuples())
    lines += ["", f"在同为主管道、较晚至少20份的组内，{main_text}。各组比例区间有明显重叠，不能据此确立不同的风险档位。", "",
              "采用判断：KMeans仅补充分层复盘样本的描述，不采用为新增风险分级。它给出塑料进户管与私人地点、钢与公共地点等组合，但这些组合可直接用交叉表组织，尚未多交出一项明确行动。保留实验及逐份组别，正文不必另设聚类结论。", "",
              f"Ward不采用为当前决策分析方法。它的结构分离弱于部件分类；改回原始类别后，较晚分组ARI为 {cluster_summary['selected']['ward']['raw_mapping_ari_late']:.3f}。此外，{ward_disagreements}/{int(early.sum())}={ward_disagreements / early.sum():.1%} 的早期记录按最近中心规则会换组，限制了训练分组与较晚指派的直接解释。", "",
              "较晚记录分到冻结的早期中心。Ward 的最近中心指派是明确的外推规则，不是重新做层次聚类。完整组内部件、材料、地点和密度类别分布见 cluster_feature_composition.csv。", "",
              "## 方法边界与结果文件", "", "派生部件7类、材料5类沿用已固定映射，原始类别对应及计数见 raw_to_derived_mapping.csv；地点4类、cls4类保留。稀有部件归OTHER，铜与球墨铸铁归材料OTHER。原始类别对照使用同一已选k，没有重新调参。", "",
              "比例及父规则增益描述已报告事故，不能证明伤人机制。Wilson区间采用独立二元近似，不覆盖同运营商相关性、报告筛选和挖掘选择偏差。cls只是原表密度类别，私人地点也不能等同室内。", "",
              "未加 DBSCAN：核查的 Session 5 目录和OCR没有该方法。未加无决策用途的PCA。来源hash、环境、seed与完整运行日志见 receipt.json、protocol.json、run.log；全部候选、父规则、选择过程及逐份指派均已保存。", ""]
    lines += ["## 课程范围追加核对", "",
              "课件讲授 single、complete、average linkage，个人聚类练习要求 k=2至8。这是本轮方法覆盖的依据，不是小组作业的硬性要求。初始 k=2至6 与 Ward 结果保留；扩展后仍只用早期结构和同一最小65份门槛选择。", "",
              "| 方法 | 合格的k | 最终保留k | 最佳合格早期轮廓系数 |", "|---|---|---:|---:|"]
    for algorithm in ["kmeans", "single", "complete", "average"]:
        eligible = course_choices.loc[course_choices.algorithm.eq(algorithm) & course_choices.eligible_minimum_size]
        if len(eligible):
            chosen = course_summary["selected"].get(algorithm)
            lines.append(f"| {algorithm} | {', '.join(map(str, eligible.k))} | {chosen['k'] if chosen else '未优于保留的层次方案'} | {eligible.silhouette_early.max():.3f} |")
        else:
            smallest = course_choices.loc[course_choices.algorithm.eq(algorithm), "minimum_cluster_n"].max()
            lines.append(f"| {algorithm} | 无，最小组最多{int(smallest)}份 | 不采用 | 不适用 |")
    lines += ["", "course_ 文件记录全部28个候选、逐份指派和选择过程。只给最终KMeans与最佳合格层次方案补原始类别敏感性。", "",
              "| 课程范围保留方案 | 较晚各组报告数 | 原始类别对照较晚ARI | 早期分组改用最近中心后换组数 |", "|---|---|---:|---:|"]
    for algorithm, selected in course_summary["selected"].items():
        disagreement = int(course_comparisons.loc[course_comparisons.algorithm.eq(algorithm) & course_comparisons.variant.eq("derived") & course_comparisons.period.eq("early"), "training_partition_nearest_center_disagreements"].iloc[0])
        lines.append(f"| {algorithm} k={selected['k']} | {selected['late_cluster_counts']} | {selected['raw_mapping_ari_late']:.3f} | {disagreement}/{int(early.sum())} |")
    lines += ["", "课程范围的采用判断不变：KMeans可补充组合描述，不采用为新的风险等级；single和average未过规模门槛，不采用；complete虽可形成合格分组，轮廓系数仍低于直接部件分类，也没有交出更明确的行动解释，不采用为主文新增结论。KMeans再次选到搜索上限8，不能把它宣称为数据中真实存在的8种事故类型。", "",
              f"闭合/极大项集只在本次最多3项的搜索空间内计算。{compression['frequent_itemsets']} 个频繁项集压为 {compression['closed_within_length_3']} 个闭合项集，减少 {compression['closed_removed_fraction']:.1%}；或 {compression['maximal_within_length_3']} 个极大项集，减少 {compression['maximal_removed_fraction']:.1%}。闭合压缩可去掉嵌套且覆盖完全相同的重复；极大压缩会丢失父规则支持度，不能替代本题的增益比较。它们没有增加新的风险发现，也没有改选规则。", ""]
    process_lines = ["## 事故经过的信息价值", "",
                     "这是独立的事故复盘解释试验。CAUSE是填报的表观原因，IGNITE_IND与EXPLODE_IND记录事件已经发生后的经过；它们不进入设施事故前预测，也不加入基本4字段的算法排行榜。定义核对了锁定ZIP内表单第3、9页及[PHMSA 2023说明第10、18页](https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2023-12/Current_GD_Incident_Instructions_PHMSA%20F%207100.1_2023-09%20and%20Beyond.pdf)。", "",
                     "CAUSE与着火字段无空白；爆炸字段空白173份，早期58、较晚115，全部同时记录着火为NO。新版表单在着火为YES后追问爆炸，因此空白单独编码，不填为NO。另有15份早期记录着火NO、爆炸YES，保留历史填报组合，不直接判作逻辑错误。", "",
                     "5个特征组合使用同一逻辑回归，2017年以前拟合、2018至2021年选C，再用2021年以前全部记录重拟合，2022年后回顾。查看量同为53份；截点同分按随机抽取的期望命中处理。", "",
                     "| 特征组合 | C | 较晚AP | 较晚Brier | 同53份期望命中 | 同分可能命中范围 |", "|---|---:|---:|---:|---:|---:|"]
    labels = {"basic": "基本4字段", "basic_cause": "基本＋原因", "basic_ignition_explosion": "基本＋着火/爆炸", "basic_all_process": "基本＋全部经过", "basic_cause_ignition_no_explosion": "基本＋原因＋着火，不含爆炸"}
    for row in process_results.itertuples():
        process_lines.append(f"| {labels[row.feature_set]} | {row.selected_C:g} | {row.AP:.3f} | {row.Brier:.3f} | {row.expected_hits:.2f} | {row.minimum_hits_from_ties}至{row.maximum_hits_from_ties} |")
    no_explosion = process_results.loc[process_results.feature_set.eq("basic_cause_ignition_no_explosion")].iloc[0]
    all_process = process_results.loc[process_results.feature_set.eq("basic_all_process")].iloc[0]
    decision = "采用为独立复盘解释补充" if no_explosion.delta_AP_vs_basic > 0 and no_explosion.delta_Brier_vs_basic < 0 else "不采用为优于基本字段的信息补充"
    process_lines += ["", f"判断：{decision}。不含爆炸的对照相对基本字段，AP变化 {no_explosion.delta_AP_vs_basic:+.3f}、Brier变化 {no_explosion.delta_Brier_vs_basic:+.3f}，同53份期望命中变化 {no_explosion.delta_expected_hits_vs_basic:+.2f}。全部经过的相应变化为 {all_process.delta_AP_vs_basic:+.3f}、{all_process.delta_Brier_vs_basic:+.3f}、{all_process.delta_expected_hits_vs_basic:+.2f}。这个对照检验增益是否必须依赖爆炸字段的跳题与版本差异。", "",
                     "这里衡量已记录的经过与已记录的伤亡如何对应。即使指标提高，也不能解释为提前预警能力或原因的因果效应；补充调查后的信息与改换同一输入下的算法，是两个信息条件不同的任务。原因/着火列联表、条件空白、逐份分数、全部C试验与系数均保存于 process_ 文件。", ""]
    lines += process_lines
    (OUT / "process_findings.md").write_text("\n".join(process_lines), encoding="utf-8")
    (OUT / "findings.md").write_text("\n".join(lines), encoding="utf-8")
    logging.info("Completed discovery experiment; all assertions passed")


if __name__ == "__main__":
    main()
