from pathlib import Path
import csv
import hashlib
import io
import json
import zipfile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'/'story_research'
OUT.mkdir(parents=True,exist_ok=True)

def load_data(version='primary'):
    """Read locked raw fields and join the previously verified analysis columns."""
    manifest=json.loads((ROOT/'inputs/sources.json').read_text(encoding='utf-8'))
    path=ROOT/f'inputs/data/incident_{version}.zip'
    expected=next(f['sha256'] for f in manifest['files'] if f['path']==f'inputs/data/incident_{version}.zip')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    with zipfile.ZipFile(path) as z:
        d=pd.read_csv(io.BytesIO(z.read('incident_gas_distribution_jan2010_present.txt')),
            sep='\t',encoding='latin-1',quoting=csv.QUOTE_NONE,dtype=str,keep_default_na=False)
    d=d.apply(lambda s:s.str.strip('"'))
    prepared=pd.read_csv(ROOT/f'results/analysis_{version}.csv',dtype={'REPORT_NUMBER':str,'OPERATOR_ID':str})
    assert d.REPORT_NUMBER.is_unique and prepared.REPORT_NUMBER.is_unique
    assert set(d.REPORT_NUMBER)==set(prepared.REPORT_NUMBER)
    derived=[c for c in prepared.columns if c not in d.columns]
    d=d.merge(prepared[['REPORT_NUMBER']+derived],on='REPORT_NUMBER',validate='one_to_one')
    direct=(d.FATALITY_IND.eq('YES')|d.INJURY_IND.eq('YES')).astype(int)
    assert direct.equals(d.cas)
    assert d.OPERATOR_ID.ne('').all()
    return d

def write_json(name, obj):
    def convert(x):
        if isinstance(x,np.integer): return int(x)
        if isinstance(x,np.floating): return float(x)
        if isinstance(x,np.ndarray): return x.tolist()
        if isinstance(x,Path): return str(x)
        raise TypeError(type(x).__name__)
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=convert,allow_nan=False)+'\n',encoding='utf-8')

if __name__=='__main__':
    d=load_data()
    names=[c for c in d if any(s in c for s in ('CAUSE','IGNIT','EXPLO','FATAL','INJUR','NARRATIVE','BUILD','MIGRAT','LOCATION','CUSTOMER','ACCIDENT','PRESS','LEAK'))]
    print('\n'.join(names))
    print('Raw plus verified derived fields:',d.shape)
