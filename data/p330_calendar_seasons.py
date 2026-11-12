"""Recheck seasonal concentration using real month-days on a circular calendar."""
from pathlib import Path
import argparse
import hashlib
import json
import platform

import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import DBSCAN

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'research/results/course_visual_lab_20261109/natural_context/scope_records_693.csv'
OUT = ROOT / 'research/results/p330_external/seasons/calendar_days'
MATERIALS = ['CAST/WROUGHT IRON', 'STEEL', 'PLASTIC']


def assign_dates(group, eps=31, minimum=3, cyclic=True):
    days = group.calendar_day.to_numpy(dtype=float)
    distance = np.abs(days[:, None] - days[None, :])
    if cyclic:
        distance = np.minimum(distance, 366 - distance)
    model = DBSCAN(eps=eps, min_samples=minimum, metric='precomputed').fit(distance)
    result = group.copy()
    result['cluster'] = model.labels_
    result['core'] = False
    result.loc[result.index[model.core_sample_indices_], 'core'] = True
    result['neighbor_count'] = (distance <= eps).sum(axis=1)
    return result


def span(days):
    days = np.sort(np.unique(days))
    gaps = np.diff(np.r_[days, days[0] + 366])
    split = int(np.argmax(gaps))
    start, end = int(days[(split + 1) % len(days)]), int(days[split])
    date = lambda value: (pd.Timestamp('2000-01-01') + pd.Timedelta(days=value - 1)).strftime('%m-%d')
    return date(start), date(end), 366 - int(gaps[split])


def summary(group, eps=31, minimum=3, cyclic=True):
    labels = sorted(set(group.cluster) - {-1})
    parts = []
    for label in labels:
        g = group.loc[group.cluster.eq(label)]
        start, end, width = span(g.calendar_day)
        parts.append(f'{label}:n={len(g)},{start}..{end},span={width}d')
    return dict(material=group.material.iloc[0], eps_days=eps, min_samples=minimum,
                cyclic=cyclic, n=len(group), clusters=len(labels), noise_n=int(group.cluster.eq(-1).sum()),
                groups='; '.join(parts))


def main(source=SOURCE, out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(source, dtype={'REPORT_NUMBER': str, 'OPERATOR_ID': str})
    assert len(data) == 693 and data.REPORT_NUMBER.nunique() == 693 and data.cas.sum() == 141
    dates = pd.to_datetime(data.incident_date, errors='raise')
    data['month'] = dates.dt.month
    data['monthday'] = dates.dt.strftime('%m-%d')
    data['calendar_day'] = pd.to_datetime('2000-' + data.monthday).dt.dayofyear
    data['natural'] = data.CAUSE.eq('NATURAL FORCE DAMAGE')
    cols = ['REPORT_NUMBER', 'OPERATOR_ID', 'incident_date', 'month', 'monthday', 'calendar_day',
            'material', 'LOCATION_STATE_ABBREVIATION', 'CAUSE', 'CAUSE_DETAILS', 'TEMPERATURE_SUBTYPE', 'cas']
    data[cols].to_csv(out / 'input_693.csv', index=False)
    natural = data.loc[data.natural, cols].sort_values(['material', 'calendar_day', 'REPORT_NUMBER'])
    assert len(natural) == 42
    records, groups, checks, baselines, sensitivity = [], [], [], [], []
    for material in MATERIALS:
        g = natural.loc[natural.material.eq(material)].reset_index(drop=True)
        labels = assign_dates(g)
        records.append(labels)
        baselines.append(summary(labels))
        baselines.append(summary(assign_dates(g, cyclic=False), cyclic=False))
        for label, part in labels.groupby('cluster', sort=True):
            start, end, width = span(part.calendar_day)
            groups.append(dict(material=material, cluster=int(label), n=len(part), core_n=int(part.core.sum()),
                               casualty_n=int(part.cas.sum()), operators=part.OPERATOR_ID.nunique(),
                               start_monthday=start, end_monthday=end, arc_days=width))
        for eps in [14, 31, 45]:
            for minimum in [3, 4, 5]:
                sensitivity.append(summary(assign_dates(g, eps, minimum), eps, minimum))
        if material == 'CAST/WROUGHT IRON':
            for operator in sorted(g.OPERATOR_ID.unique()):
                reduced = g.loc[g.OPERATOR_ID.ne(operator)].reset_index(drop=True)
                checks.append(dict(removed_operator=operator, **summary(assign_dates(reduced))))
    assigned = pd.concat(records, ignore_index=True)
    assigned.to_csv(out / 'natural_date_clusters.csv', index=False)
    pd.DataFrame(groups).to_csv(out / 'cluster_arcs.csv', index=False)
    pd.DataFrame(baselines).to_csv(out / 'cyclic_vs_ordinary.csv', index=False)
    pd.DataFrame(sensitivity).to_csv(out / 'parameter_sensitivity.csv', index=False)
    pd.DataFrame(checks).to_csv(out / 'iron_leave_operator_out.csv', index=False)
    data.assign(period=np.where(data.month.isin([11, 12, 1, 2, 3]), 'Nov-Mar', 'Apr-Oct')).groupby(
        ['material', 'period']).agg(all_n=('REPORT_NUMBER', 'size'), natural_n=('natural', 'sum'),
                                  casualty_n=('cas', 'sum')).reset_index().to_csv(out / 'season_context.csv', index=False)
    receipt = dict(status='exploratory reanalysis after the existing monthly observation; not independent validation',
                   source=source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else source.name,
                   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   python=platform.python_version(), sklearn=sklearn.__version__, pandas=pd.__version__, numpy=np.__version__,
                   calendar='observed month-day mapped to leap year 2000; preserves Feb 29; annual period 366 days',
                   distance='min(abs(calendar_day_i-calendar_day_j),366-abs(calendar_day_i-calendar_day_j))',
                   eps_days=31, min_samples_including_self=3, random_seed=None,
                   input_order='material,calendar_day,REPORT_NUMBER', outcome_used_for_clustering=False,
                   comparison='monthly binned analysis retained separately; daily resolution is primary',
                   primary_results=baselines[::2])
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'natural_reports':len(assigned), 'results':baselines[::2]}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    main(args.input.resolve(), args.output.resolve())
