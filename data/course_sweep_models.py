"""Course methods: fixed-input, retrospective classification comparisons."""
from pathlib import Path
import hashlib
import itertools
import json
import platform
import time
import warnings

import numpy as np
import pandas as pd
import scipy
import sklearn
import statsmodels
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.ensemble import AdaBoostClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.inspection import permutation_importance
from sklearn.metrics import (average_precision_score, brier_score_loss, log_loss,
                             precision_recall_curve, roc_auc_score)
from sklearn.naive_bayes import BernoulliNB, CategoricalNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier, export_text
from threadpoolctl import threadpool_limits

from study_common import ROOT, load_data

OUT = ROOT / 'results/course_sweep_20261107/models'
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20261107
FEATURES = ['part', 'mat', 'location', 'cls']
RAW = ['SYSTEM_PART_INVOLVED', 'MATERIAL_INVOLVED', 'LOCATION_TYPE', 'CLASS_LOCATION_TYPE']
FORMULA = "cas ~ C(part, Treatment('MAIN')) + C(mat, Treatment('STEEL')) + C(location, Treatment('PUBLIC PROPERTY')) + C(cls, Treatment('CLASS 3 LOCATION'))"


def write_json(name, value):
    def default(x):
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.floating): return float(x)
        if isinstance(x, np.ndarray): return x.tolist()
        if isinstance(x, Path): return str(x)
        raise TypeError(type(x).__name__)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                     default=default, allow_nan=False) + '\n', encoding='utf-8')


def csv(name, rows):
    pd.DataFrame(rows).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def build_model(name, params):
    if name == 'logistic': return LogisticRegression(max_iter=5000, random_state=SEED, **params)
    if name == 'tree': return DecisionTreeClassifier(random_state=SEED, **params)
    if name == 'forest': return RandomForestClassifier(n_estimators=250, n_jobs=2, random_state=SEED, **params)
    if name == 'knn': return KNeighborsClassifier(n_jobs=2, **params)
    if name in ['svm_linear', 'svm_rbf']:
        return SVC(kernel='linear' if name == 'svm_linear' else 'rbf',
                   probability=True, random_state=SEED, **params)
    if name == 'bernoulli_nb': return BernoulliNB(**params)
    if name == 'adaboost':
        p = params.copy()
        depth = p.pop('depth')
        return AdaBoostClassifier(estimator=DecisionTreeClassifier(max_depth=depth, min_samples_leaf=20,
                                                                   random_state=SEED),
                                  n_estimators=100, random_state=SEED, **p)
    if name == 'gradient_boosting':
        return GradientBoostingClassifier(n_estimators=100, min_samples_leaf=20, random_state=SEED, **params)
    raise ValueError(name)


def fit(name, frame, params, columns=FEATURES):
    if name == 'constant': return float(frame.cas.mean())
    if name == 'part_only': return (frame.groupby('part').cas.mean(), float(frame.cas.mean()))
    if name == 'logistic_proposal':
        return smf.glm(FORMULA, frame, family=sm.families.Binomial()).fit()
    if name == 'categorical_nb':
        encoder = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)
        x = encoder.fit_transform(frame[columns]).astype(int) + 1
        model = CategoricalNB(min_categories=[len(c) + 1 for c in encoder.categories_], **params).fit(x, frame.cas)
        return encoder, model
    pipeline = make_pipeline(OneHotEncoder(handle_unknown='ignore', sparse_output=False), build_model(name, params))
    pipeline.fit(frame[columns], frame.cas)
    return pipeline


def predict(name, fitted, frame, columns=FEATURES):
    if name == 'constant': result = np.full(len(frame), fitted)
    elif name == 'part_only': result = frame.part.map(fitted[0]).fillna(fitted[1]).to_numpy()
    elif name == 'logistic_proposal': result = fitted.predict(frame).to_numpy()
    elif name == 'categorical_nb': result = fitted[1].predict_proba(fitted[0].transform(frame[columns]).astype(int) + 1)[:, 1]
    else: result = fitted.predict_proba(frame[columns])[:, 1]
    result = np.asarray(result, dtype=float)
    assert result.shape == (len(frame),) and np.isfinite(result).all()
    assert ((0 <= result) & (result <= 1)).all()
    return result


def budget(y, scores, fraction):
    y = np.asarray(y, dtype=int)
    scores = np.asarray(scores)
    n = int(np.ceil(len(y) * fraction))
    cut = np.sort(scores)[-n]
    higher = scores > cut
    tied = scores == cut
    slots = n - int(higher.sum())
    positive_ties = int(y[tied].sum())
    certain = int(y[higher].sum())
    expected = certain + slots * positive_ties / int(tied.sum())
    return {'review_n': n, 'expected_hits': expected, 'expected_precision': expected / n,
            'expected_recall': expected / int(y.sum()) if y.sum() else None,
            'minimum_hits_from_ties': certain + max(0, slots - int(tied.sum()) + positive_ties),
            'maximum_hits_from_ties': certain + min(slots, positive_ties),
            'tie_n': int(tied.sum()), 'cutoff': float(cut)}


def choose_threshold(y, s):
    p, r, thresholds = precision_recall_curve(y, s)
    f1 = np.divide(2*p[:-1]*r[:-1], p[:-1]+r[:-1], out=np.zeros(len(thresholds)), where=p[:-1]+r[:-1] > 0)
    # Among equal F1 values, prefer the larger threshold and hence fewer reviews.
    return float(thresholds[np.flatnonzero(np.isclose(f1, f1.max(), rtol=0, atol=1e-12))[-1]])


def metrics(frame, scores, threshold):
    y = frame.cas.to_numpy(dtype=int)
    flagged = scores >= threshold
    tp = int(y[flagged].sum())
    fp = int(flagged.sum()) - tp
    fn = int(y.sum()) - tp
    tn = len(y) - tp - fp - fn
    b = budget(y, scores, .2)
    return {'reports': len(y), 'casualty_reports': int(y.sum()),
            'AP': float(average_precision_score(y, scores)),
            'ROC_AUC': float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else None,
            'Brier': float(brier_score_loss(y, scores)),
            'log_loss': float(log_loss(y, np.clip(scores, 1e-12, 1-1e-12), labels=[0, 1])),
            'mean_probability': float(np.mean(scores)), 'threshold_from_earlier_validation': threshold,
            'flagged': int(flagged.sum()), 'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn,
            'precision': tp/(tp+fp) if tp+fp else 0., 'recall': tp/(tp+fn) if tp+fn else 0.,
            'budget20_n': b['review_n'], 'budget20_expected_hits': b['expected_hits'],
            'budget20_precision': b['expected_precision'], 'budget20_recall': b['expected_recall'],
            'budget20_tie_min_hits': b['minimum_hits_from_ties'],
            'budget20_tie_max_hits': b['maximum_hits_from_ties'], 'budget20_tie_n': b['tie_n']}


GRIDS = {
    'constant': [{}], 'part_only': [{}], 'logistic_proposal': [{}],
    'logistic': [{'C': c} for c in [.05, .2, 1., 5.]],
    'tree': [{'max_depth': d, 'min_samples_leaf': l} for d in [2, 3, 4] for l in [40, 20]],
    'forest': [{'max_depth': d, 'min_samples_leaf': l} for d in [4, 8, None] for l in [25, 10]],
    'knn': [{'n_neighbors': k, 'weights': w} for k in [15, 35, 65] for w in ['uniform', 'distance']],
    'svm_linear': [{'C': c} for c in [.1, 1., 10.]],
    'svm_rbf': [{'C': c, 'gamma': g} for c in [.1, 1., 10.] for g in ['scale', .1]],
    'bernoulli_nb': [{'alpha': a} for a in [5., 1., .1]],
    'categorical_nb': [{'alpha': a} for a in [5., 1., .1]],
    'adaboost': [{'learning_rate': r, 'depth': d} for d in [1, 2] for r in [.05, .2, .5]],
    'gradient_boosting': [{'learning_rate': r, 'max_depth': d} for d in [1, 2] for r in [.03, .1]],
}


def bootstrap(frame, predictions, references, repetitions=1200):
    groups = [np.flatnonzero(frame.OPERATOR_ID.to_numpy() == x) for x in sorted(frame.OPERATOR_ID.unique())]
    y = frame.cas.to_numpy(dtype=int)
    rng = np.random.default_rng(SEED)
    store = {(a, b): [] for a, b in references}
    skipped = 0
    names = sorted({n for pair in references for n in pair})
    for _ in range(repetitions):
        ix = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        if len(np.unique(y[ix])) < 2:
            skipped += 1
            continue
        ap = {n: average_precision_score(y[ix], predictions[n][ix]) for n in names}
        br = {n: np.mean((y[ix]-predictions[n][ix])**2) for n in names}
        hit = {n: budget(y[ix], predictions[n][ix], .2)['expected_recall'] for n in names}
        for a, b in references: store[(a, b)].append([ap[a]-ap[b], br[a]-br[b], hit[a]-hit[b]])
    rows = []
    for (a, b), values in store.items():
        arr = np.asarray(values)
        for j, measure in enumerate(['AP', 'Brier', 'recall_at20pct']):
            lo, hi = np.quantile(arr[:, j], [.025, .975])
            rows.append({'method': a, 'reference': b, 'metric': measure,
                         'low95': lo, 'high95': hi, 'replicates': len(values), 'operators': len(groups),
                         'scope': 'paired late-operator bootstrap; predictions fixed; exploratory, no selection correction'})
    return rows, skipped


def main():
    started = time.time()
    frame = load_data().sort_values('REPORT_NUMBER').reset_index(drop=True)
    basic = pd.read_csv(ROOT/'results/basic_comparison/audit/analysis_ready.csv', dtype={'REPORT_NUMBER': str})
    check = frame[['REPORT_NUMBER', 'cas']].merge(basic[['REPORT_NUMBER', 'cas']], on='REPORT_NUMBER', validate='one_to_one')
    assert len(check) == 1550 and check.cas_x.equals(check.cas_y) and int(check.cas_x.sum()) == 369
    assert frame[FEATURES].notna().all().all()
    early = frame[frame.received_year <= 2017].copy()
    validation = frame[frame.received_year.between(2018, 2021)].copy()
    train = frame[frame.received_year <= 2021].copy()
    late = frame[frame.received_year >= 2022].copy()
    assert len(train) == 1286 and len(late) == 264 and int(late.cas.sum()) == 65
    assert set(train.REPORT_NUMBER).isdisjoint(late.REPORT_NUMBER)
    assert set(early.REPORT_NUMBER).isdisjoint(validation.REPORT_NUMBER)
    raw_hash = hashlib.sha256((ROOT/'inputs/data/incident_primary.zip').read_bytes()).hexdigest()
    protocol = {'seed': SEED, 'raw_sha256': raw_hash,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'feature_columns': FEATURES, 'outcome': 'death or inpatient overnight injury, one indicator per incident report',
        'split': {'fit_through': 2017, 'validation': [2018, 2021], 'refit_through': 2021, 'retrospective_evaluation_from': 2022},
        'selection': 'maximum validation AP, then lower validation Brier, then original grid order; no later-period selection',
        'threshold': 'validation F1 maximum, ties prefer higher threshold; constant reference flags all at training prevalence',
        'budget': 'all methods inspect ceil(20% * evaluation reports); equal-score ties averaged uniformly',
        'grids': GRIDS, 'state': 'specified before new model fits; later-period outcomes have been studied previously',
        'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                     'scipy': scipy.__version__, 'sklearn': sklearn.__version__, 'statsmodels': statsmodels.__version__},
        'documentation': ['https://scikit-learn.org/stable/common_pitfalls.html',
                          'https://scikit-learn.org/stable/modules/calibration.html',
                          'https://scikit-learn.org/stable/modules/naive_bayes.html']}
    write_json('protocol.json', protocol)
    mapping = []
    for raw, derived in zip(RAW, FEATURES):
        assert raw in frame, raw
        tab = frame.groupby([raw, derived], dropna=False).size().reset_index(name='reports')
        for row in tab.to_dict('records'):
            mapping.append({'original_field': raw, 'model_field': derived, 'original_category': row[raw],
                            'model_category': row[derived], 'reports': row['reports']})
    csv('category_mapping.csv', mapping)
    csv('splits.csv', [{'role': role, 'reports': len(d), 'casualty_reports': int(d.cas.sum()),
                       'operators': d.OPERATOR_ID.nunique()} for role, d in [('fit', early), ('validation', validation),
                                                                           ('refit', train), ('evaluation', late)]])
    trials, final_rows, warnings_log = [], [], []
    fitted, scores, validation_scores, selected, cutoffs = {}, {}, {}, {}, {}
    for name, grid in GRIDS.items():
        candidates = []
        for index, params in enumerate(grid):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                model = fit(name, early, params)
                s = predict(name, model, validation)
            for warning in caught:
                warnings_log.append({'method': name, 'stage': 'validation', 'params': params, 'message': str(warning.message)})
            ap = float(average_precision_score(validation.cas, s))
            br = float(brier_score_loss(validation.cas, s))
            candidates.append((ap, -br, -index, params, s))
            trials.append({'method': name, 'grid_index': index, 'parameters': json.dumps(params), 'validation_AP': ap, 'validation_Brier': br})
        winner = max(candidates, key=lambda x: x[:3])
        selected[name] = winner[3]
        validation_scores[name] = winner[4]
        cutoff = choose_threshold(validation.cas.to_numpy(), winner[4])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            fitted[name] = fit(name, train, selected[name])
            scores[name] = predict(name, fitted[name], late)
        for warning in caught:
            warnings_log.append({'method': name, 'stage': 'refit', 'params': selected[name], 'message': str(warning.message)})
        if name == 'constant': cutoff = float(train.cas.mean())
        cutoffs[name] = cutoff
        final_rows.append({'method': name, 'parameters': json.dumps(selected[name]),
                           'validation_AP': winner[0], 'validation_Brier': -winner[1], **metrics(late, scores[name], cutoff)})
        print(name, 'validation AP', round(winner[0], 4), 'later AP', round(final_rows[-1]['AP'], 4), flush=True)
    csv('hyperparameter_trials.csv', trials)
    csv('model_metrics.csv', final_rows)
    csv('warnings.csv', warnings_log)
    write_json('selected_parameters.json', selected)
    late_out = late[['REPORT_NUMBER', 'OPERATOR_ID', 'received_year', 'cas']+FEATURES].copy()
    val_out = validation[['REPORT_NUMBER', 'OPERATOR_ID', 'received_year', 'cas']+FEATURES].copy()
    for name in scores:
        late_out['score_'+name] = scores[name]
        val_out['score_'+name] = validation_scores[name]
    csv('later_predictions.csv', late_out)
    csv('validation_predictions.csv', val_out)

    # A saved prediction comparison identifies reproduction versus new model variants.
    old = pd.read_csv(ROOT/'results/story_research/model_predictions_primary.csv', dtype={'REPORT_NUMBER': str})
    join = late_out.merge(old[['REPORT_NUMBER', 'score_constant', 'score_part_only', 'score_logistic']], on='REPORT_NUMBER', suffixes=('', '_old'), validate='one_to_one')
    reproduction = {n: float(np.max(np.abs(join['score_'+n]-join['score_'+oldname+'_old'])))
                    for n, oldname in [('constant', 'constant'), ('part_only', 'part_only')]}
    reproduction['logistic_proposal'] = float(np.max(np.abs(join.score_logistic_proposal-join.score_logistic_old)))
    assert max(reproduction.values()) < 1e-8, reproduction
    write_json('original_prediction_reproduction.json', reproduction)

    curve_rows, pr_rows, reliability_rows = [], [], []
    for name, s in scores.items():
        for fraction in [.05, .1, .2, .3, .5, 1.]:
            curve_rows.append({'method': name, 'review_fraction': fraction, **budget(late.cas, s, fraction)})
        p, r, t = precision_recall_curve(late.cas, s)
        for i in range(len(t)): pr_rows.append({'method': name, 'threshold': t[i], 'precision': p[i], 'recall': r[i]})
        bins = np.digitize(s, [.1, .2, .3, .4, .5, .75])
        for b in sorted(np.unique(bins)):
            ix = bins == b
            reliability_rows.append({'method': name, 'bin': int(b), 'reports': int(ix.sum()),
                                     'mean_probability': float(s[ix].mean()), 'observed_proportion': float(late.cas.to_numpy()[ix].mean())})
    csv('review_budgets.csv', curve_rows)
    csv('precision_recall_curves.csv', pr_rows)
    csv('probability_reliability.csv', reliability_rows)
    cohort_rows = []
    seen = late.OPERATOR_ID.isin(train.OPERATOR_ID)
    assert int(frame.REPORT_TYPE.str.endswith('FINAL').sum()) == 1382
    for scope, sub in [('operators_seen_earlier', late[seen]), ('operators_not_seen_earlier', late[~seen]),
                       ('FINAL_only', late[late.REPORT_TYPE.str.endswith('FINAL')]),
                       ('natural_gas_only', late[late.COMMODITY_RELEASED_TYPE.eq('NATURAL GAS')])]:
        assert not sub.empty, scope
        for name in scores:
            s = predict(name, fitted[name], sub)
            cohort_rows.append({'scope': scope, 'method': name, **metrics(sub, s, cutoffs[name])})
    csv('cohort_metrics.csv', cohort_rows)

    # Fixed regularization across feature subsets isolates removal of information.
    ablation_rows, ablation_scores = [], {}
    for length in range(1, 5):
        for columns in itertools.combinations(FEATURES, length):
            columns = list(columns)
            label = '+'.join(columns)
            model = fit('logistic', train, selected['logistic'], columns)
            s = predict('logistic', model, late, columns)
            ablation_scores[label] = s
            ablation_rows.append({'features': label, 'feature_count': length, 'fixed_C': selected['logistic']['C'],
                                  **metrics(late, s, cutoffs['logistic'])})
    assert np.allclose(ablation_scores['+'.join(FEATURES)], scores['logistic'])
    csv('feature_subsets.csv', ablation_rows)
    ablation_out = late[['REPORT_NUMBER', 'OPERATOR_ID', 'cas']].copy()
    for label, s in ablation_scores.items(): ablation_out[label] = s
    csv('feature_subset_predictions.csv', ablation_out)
    sensitivity_rows = []
    for label, columns, params in [('original_categories', RAW, selected['logistic']),
                                    ('balanced_logistic', FEATURES, {**selected['logistic'], 'class_weight': 'balanced'})]:
        model = fit('logistic', train, params, columns)
        s = predict('logistic', model, late, columns)
        # F1 threshold is selected on the same earlier validation using this variant.
        val_model = fit('logistic', early, params, columns)
        val_s = predict('logistic', val_model, validation, columns)
        cutoff = choose_threshold(validation.cas.to_numpy(), val_s)
        sensitivity_rows.append({'variant': label, **metrics(late, s, cutoff)})
    csv('encoding_and_weight_sensitivity.csv', sensitivity_rows)
    importance_rows = []
    for name in ['logistic', 'forest']:
        validation_model = fit(name, early, selected[name])
        imp = permutation_importance(validation_model, validation[FEATURES], validation.cas,
                                     scoring='average_precision', n_repeats=25, random_state=SEED, n_jobs=1)
        for i, field in enumerate(FEATURES):
            for repeat, change in enumerate(imp.importances[i]):
                importance_rows.append({'method': name, 'feature': field, 'repeat': repeat,
                                        'validation_AP_drop': change,
                                        'scope': '2018-2021 validation, unconditional field permutation; descriptive, correlated inputs may change interpretation'})
    csv('validation_permutation_importance.csv', importance_rows)
    encoded_names = fitted['forest'][0].get_feature_names_out()
    mdi = fitted['forest'][-1].feature_importances_
    csv('forest_impurity_importance.csv', [{'feature': field, 'importance': float(sum(v for n, v in zip(encoded_names, mdi) if n.startswith(field+'_')))} for field in FEATURES])
    oob_model = fit('forest', train, {**selected['forest'], 'oob_score': True})
    oob = oob_model[-1].oob_decision_function_[:, 1]
    assert np.isfinite(oob).all()
    write_json('forest_oob_diagnostic.json', {'reports': len(train), 'AP': float(average_precision_score(train.cas, oob)),
                                           'Brier': float(brier_score_loss(train.cas, oob)),
                                           'scope': 'Bootstrap out-of-bag predictions within 2010-2021. Training trees may include later dates than their OOB cases; not temporal validation.'})
    assert np.allclose(predict('forest', oob_model, late), scores['forest'])
    print('paired operator bootstrap', flush=True)
    comparisons = [(n, 'part_only') for n in scores if n not in ['constant', 'part_only']]
    comparisons += [('logistic', 'logistic_proposal')]
    intervals, skipped = bootstrap(late, scores, comparisons)
    csv('paired_model_intervals.csv', intervals)
    full = '+'.join(FEATURES)
    pairs = [(full, '+'.join(c for c in FEATURES if c != omitted)) for omitted in FEATURES]
    ablation_intervals, _ = bootstrap(late, ablation_scores, pairs)
    csv('paired_ablation_intervals.csv', ablation_intervals)

    tree = fitted['tree']
    (OUT/'selected_tree.txt').write_text(export_text(tree[-1], feature_names=tree[0].get_feature_names_out().tolist()), encoding='utf-8')
    coef = fitted['logistic'][-1].coef_[0]
    csv('logistic_coefficients.csv', [{'encoded_feature': n, 'coefficient': v}
                                     for n, v in zip(fitted['logistic'][0].get_feature_names_out(), coef)])
    # A second historical validation period checks sensitivity without touching later-period tuning.
    historic_rows = []
    htrain = frame[frame.received_year <= 2013]
    htest = frame[frame.received_year.between(2014, 2017)]
    for name in GRIDS:
        model = fit(name, htrain, selected[name])
        s = predict(name, model, htest)
        historic_rows.append({'method': name, 'train_through': 2013, 'evaluation_from': 2014,
                              'evaluation_through': 2017, 'parameters_selected_on_2018_2021': True,
                              'AP': float(average_precision_score(htest.cas, s)),
                              'Brier': float(brier_score_loss(htest.cas, s)), **budget(htest.cas, s, .2)})
    csv('historical_sensitivity.csv', historic_rows)
    best_validation = max(final_rows, key=lambda r: (r['validation_AP'], -r['validation_Brier']))['method']
    write_json('run_receipt.json', {'protocol': protocol, 'models': len(GRIDS), 'hyperparameter_trials': len(trials),
        'feature_subsets': len(ablation_rows), 'late_reports': len(late), 'late_casualty_reports': int(late.cas.sum()),
        'late_operators': late.OPERATOR_ID.nunique(), 'validation_selected_method': best_validation,
        'reproduced_original_predictions': reproduction, 'bootstrap_skipped': skipped,
        'wall_seconds': time.time()-started, 'warnings': len(warnings_log),
        'assessment': 'Exploratory retrospective comparison; fixed-prediction bootstrap does not include tuning uncertainty.'})
    print('DONE', best_validation, 'seconds', round(time.time()-started, 1), flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=2): main()
