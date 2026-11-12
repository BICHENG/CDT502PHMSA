"""Pool all natural-force reports in fixed two-dimensional calendar coordinates."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import DBSCAN

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'research/results/p330_external/seasons/calendar_days/input_693.csv'
OUTPUT = ROOT / 'research/results/p332_pooled'
TOLERANCE = 1e-12


def span(days):
    values = np.sort(np.unique(days))
    gaps = np.diff(np.r_[values, values[0] + 366])
    split = int(np.argmax(gaps))
    first, last = int(values[(split + 1) % len(values)]), int(values[split])
    date = lambda day: (pd.Timestamp('2000-01-01') + pd.Timedelta(days=day - 1)).strftime('%m-%d')
    return date(first), date(last), 366 - int(gaps[split])


def main(source, output):
    output.mkdir(parents=True, exist_ok=True)
    records = pd.read_csv(source, dtype={'REPORT_NUMBER': str, 'OPERATOR_ID': str})
    assert len(records) == records.REPORT_NUMBER.nunique() == 693
    data = records.loc[records.CAUSE.eq('NATURAL FORCE DAMAGE')].copy()
    data['monthday'] = pd.to_datetime(data.incident_date).dt.strftime('%m-%d')
    data['calendar_day'] = pd.to_datetime('2000-' + data.monthday).dt.dayofyear
    data = data.sort_values(['calendar_day', 'REPORT_NUMBER']).reset_index(drop=True)
    assert len(data) == data.REPORT_NUMBER.nunique() == 42
    data['theta'] = 2 * np.pi * (data.calendar_day - 1) / 366
    data['x'] = np.sin(data.theta)
    data['y'] = np.cos(data.theta)
    coordinates = data[['x', 'y']].to_numpy()
    days = data.calendar_day.to_numpy()
    direct = np.abs(days[:, None] - days[None, :])
    calendar_distance = np.minimum(direct, 366 - direct)
    euclidean = np.linalg.norm(coordinates[:, None, :] - coordinates[None, :, :], axis=2)
    np.testing.assert_allclose(euclidean, 2 * np.sin(np.pi * calendar_distance / 366), atol=TOLERANCE, rtol=0)
    assigned, summary, sensitivity = [], [], []
    equivalence = []
    for window in [14, 31, 45]:
        radius = float(2 * np.sin(np.pi * window / 366))
        same_neighborhood = np.array_equal(calendar_distance <= window, euclidean <= radius + TOLERANCE)
        assert same_neighborhood
        for minimum in [3, 4, 5]:
            model = DBSCAN(eps=radius + TOLERANCE, min_samples=minimum, metric='euclidean').fit(coordinates)
            reference = DBSCAN(eps=window, min_samples=minimum, metric='precomputed').fit(calendar_distance)
            np.testing.assert_array_equal(model.labels_, reference.labels_)
            np.testing.assert_array_equal(model.core_sample_indices_, reference.core_sample_indices_)
            part = data.copy()
            part['window_days'] = window
            part['min_samples'] = minimum
            part['cluster'] = model.labels_
            part['core'] = False
            part.loc[model.core_sample_indices_, 'core'] = True
            part['neighbor_count'] = (calendar_distance <= window).sum(axis=1)
            part['role'] = np.where(part.cluster.eq(-1), 'noise', np.where(part.core, 'core', 'border'))
            assigned.append(part)
            sensitivity.append({'window_days': window, 'min_samples': minimum,
                'clusters': int(part.loc[part.cluster.ge(0), 'cluster'].nunique()),
                'noise_n': int(part.cluster.eq(-1).sum()), 'radius': radius})
            for label, group in part.groupby('cluster', sort=True):
                first, last, width = span(group.calendar_day)
                counts = group.material.value_counts()
                summary.append({'window_days': window, 'min_samples': minimum, 'cluster': int(label),
                    'n': len(group), 'core_n': int(group.core.sum()), 'casualty_n': int(group.cas.sum()),
                    'iron_n': int(counts.get('CAST/WROUGHT IRON', 0)), 'steel_n': int(counts.get('STEEL', 0)),
                    'plastic_n': int(counts.get('PLASTIC', 0)), 'operators': int(group.OPERATOR_ID.nunique()),
                    'start_monthday': first, 'end_monthday': last, 'arc_days': width})
            equivalence.append({'window_days': window, 'min_samples': minimum, 'neighbor_mismatches': 0,
                'labels_equal': True, 'core_equal': True, 'all_ordered_pairs_including_self': len(data) ** 2})
    all_points = pd.concat(assigned, ignore_index=True)
    all_points.to_csv(output / 'all_settings.csv', index=False)
    plotted = all_points.loc[all_points.window_days.isin([14, 31]) & all_points.min_samples.eq(3)]
    plotted.to_csv(output / 'points.csv', index=False)
    pd.DataFrame(summary).to_csv(output / 'cluster_summary.csv', index=False)
    pd.DataFrame(sensitivity).to_csv(output / 'sensitivity.csv', index=False)
    context = data.assign(winter=pd.to_datetime(data.incident_date).dt.month.isin([11, 12, 1, 2, 3])).groupby(
        ['material', 'winter']).agg(n=('REPORT_NUMBER', 'size'), casualty_n=('cas', 'sum')).reset_index()
    context.to_csv(output / 'season_counts.csv', index=False)
    records.to_csv(output / 'input_693.csv', index=False)
    receipt = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'n': 42,
        'scope': 'All natural-force reports among the 693 three-material mains and main-valve incidents, 2010-2024',
        'input_features': ['observed month-day'], 'not_input': ['material', 'injury', 'winter label'],
        'two_dimensions': 'fixed sin/cos embedding of a single annual calendar variable; not geographic coordinates or two independent factors',
        'D': 'sqrt((sin(theta_i)-sin(theta_j))**2 + (cos(theta_i)-cos(theta_j))**2)',
        'theta': '2*pi*(calendar_day-1)/366', 'calendar': 'leap year 2000', 'distance_unit': 'dimensionless',
        'equivalent_radius': '2*sin(pi*window_days/366)', 'floating_absolute_tolerance': TOLERANCE,
        'settings': {'window_days': [14, 31, 45], 'min_samples_including_self': [3, 4, 5]},
        'settings_reason': 'carry forward the P330 sensitivity grid; 31-day former baseline and 14-day short-neighborhood comparison are both displayed',
        'random_seed': None, 'order': 'calendar_day,REPORT_NUMBER', 'new_exclusions': 0,
        'research_status': 'exploratory pooled reanalysis after existing monthly and material-specific observations, not independent validation',
        'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__,
        'equivalence': equivalence}
    (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(pd.DataFrame(summary).query('min_samples == 3 and window_days in [14,31]').to_json(orient='records'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    main(args.input.resolve(), args.output.resolve())
