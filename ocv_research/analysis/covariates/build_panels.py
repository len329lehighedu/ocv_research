"""Reconstruct covariate panels without proprietary spreadsheet dependencies.

Income and campaign-history country files are documented, human-coded inputs.
IHME values are additionally checked against the supplied original CSV.
Existing derived panels are verified, never silently replaced.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MAIN=ROOT/'analysis/main/outputs/analysis_data/active_outbreak_panel.csv'

def check_or_write(frame,path):
    if path.exists():
        old=pd.read_csv(path,keep_default_na=False)
        assert list(old.columns)==list(frame.columns),(path,'column mismatch')
        assert len(old)==len(frame),(path,'row mismatch')
        for col in frame:
            if pd.api.types.is_numeric_dtype(frame[col]):
                np.testing.assert_allclose(pd.to_numeric(old[col]),frame[col],rtol=0,atol=1e-10,err_msg=col)
            else:assert old[col].astype(str).tolist()==frame[col].astype(str).tolist(),col
    else:
        frame.to_csv(path,index=False,float_format='%.17g')
    print('Reconstructed and checked:',path.relative_to(ROOT))

def main():
    p=pd.read_csv(MAIN)
    assert len(p)==1650 and p.country.nunique()==25 and p.reactive_request.sum()==58
    income=pd.read_csv(HERE/'income/country_income_fy2015.csv',keep_default_na=False)
    assert len(income)==25 and income.country_panel.is_unique
    assert income.low_income_fy2015.eq(income.income_fy2015_group.eq('LIC').astype(int)).all()
    by=income.set_index('country_panel')
    q=p.copy();q['income_fy2015_group']=q.country.map(by.income_fy2015_group)
    q['low_income_fy2015']=q.country.map(by.low_income_fy2015)
    check_or_write(q,HERE/'income/active_outbreak_panel_income_fy2015.csv')

    folder=HERE/'expenditure/ihme_2013'
    lookup=pd.read_csv(folder/'country_ihme_2013.csv')
    raw=pd.read_csv(folder/'source/IHME_HEALTH_SPENDING_1995_2016_Y2019M09D30.CSV')
    raw=raw.loc[raw.level.eq('Country') & raw.year.eq(2013)].set_index('iso3')
    assert len(raw)==195 and raw.index.is_unique
    for r in lookup.itertuples(index=False):
        for prefix,raw_prefix in [('ghes','ghes'),('the','the')]:
            val=getattr(r,f'{prefix}_per_cap_ppp_2013')
            np.testing.assert_allclose(val,raw.loc[r.iso3,f'{raw_prefix}_per_cap_ppp_mean'],rtol=0,atol=1e-10)
            np.testing.assert_allclose(getattr(r,f'log1p_{prefix}_per_cap_ppp_2013'),np.log1p(val),rtol=0,atol=1e-12)
    by=lookup.set_index('country_panel');q=p.copy()
    for col in ['ghes_per_cap_ppp_2013','log1p_ghes_per_cap_ppp_2013','the_per_cap_ppp_2013','log1p_the_per_cap_ppp_2013']:
        q[col]=q.country.map(by[col])
    check_or_write(q,folder/'active_outbreak_panel_ihme_2013.csv')

    folder=HERE/'prior_campaign'
    ledger=json.loads((folder/'source_ledger.json').read_text())
    assert ledger['cutoff_exclusive']=='2014-07-01'
    positives={r['country_panel'] for r in ledger['documented_positive_countries']}
    assert len(positives)==7 and {'DR Congo','South Sudan'}<=positives
    lookup=pd.read_csv(folder/'country_prior_ocv_campaign_pre2014jul.csv',keep_default_na=False)
    assert lookup.prior_ocv_campaign_pre2014jul.eq(lookup.country_panel.isin(positives).astype(int)).all()
    q=p.copy();q['prior_ocv_campaign_pre2014jul']=q.country.isin(positives).astype(int)
    check_or_write(q,folder/'active_outbreak_panel_prior_ocv_campaign.csv')

if __name__=='__main__':main()
