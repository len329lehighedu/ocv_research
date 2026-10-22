#!/usr/bin/env python3
"""Two reviewer-requested sensitivities, keeping the frozen main model intact.

History July 2013-December 2019; common estimation July 2014-December 2019.
M1 adds year indicators to the original predictor. M2 shifts a twelve-month
window from t-12..t-1 to t-11..t. These changes are NOT combined.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import sys
import warnings
import numpy as np
import pandas as pd
import scipy
from scipy import optimize, special
import statsmodels
import statsmodels.api as sm

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STEM='log1p_active_outbreak_months_12m'
B,W=STEM+'_between',STEM+'_within'
IB,IW='inclusive_log1p_12m_between','inclusive_log1p_12m_within'
COUNTRIES={'Angola','Benin','Burundi','Cameroon','Chad','DR Congo','Ethiopia',
 'Ghana','Guinea','Ivory Coast','Kenya','Malawi','Mozambique','Namibia','Niger',
 'Nigeria','Republic of the Congo','Sierra Leone','Somalia','South Sudan','Sudan',
 'Tanzania','Uganda','Zambia','Zimbabwe'}
YEARS=[f'year_{year}' for year in range(2015,2020)]

def require(ok,message):
    if not ok: raise ValueError(message)

def close(a,b,tol=1e-8):
    np.testing.assert_allclose(a,b,rtol=0,atol=tol)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def prepare():
    sources={
      'requests.csv':'data/source/requests.csv',
      'zheng_outbreak_records.csv':'data/source/zheng_outbreak_records.csv',
      'active_outbreak_panel.csv':'analysis/main/outputs/analysis_data/active_outbreak_panel.csv',
      'active_outbreak_results_seeded.csv':'analysis/main/outputs/analysis_data/active_outbreak_results_seeded.csv',
      'build_request_outcomes.py':'analysis/main/code/research_pipeline/data/build_request_outcomes.py',
      'build_active_outbreak_panel.py':'analysis/main/code/research_pipeline/data/build_active_outbreak_panel.py',
      'wild_cluster_bootstrap.py':'analysis/main/code/research_pipeline/results/wild_cluster_bootstrap.py'}
    folder=HERE/'inputs'; folder.mkdir(exist_ok=True)
    originals={rel:sha(ROOT/rel) for rel in sources.values()}
    for name,rel in sources.items():
        target=folder/name; original=ROOT/rel
        if target.exists(): require(sha(target)==sha(original),'Existing snapshot differs: '+name)
        else: shutil.copy2(original,target)
    record={'original_sha256':originals,'snapshot_sha256':{n:sha(folder/n) for n in sources}}
    manifest=folder/'input_manifest.json'
    if manifest.exists(): require(json.loads(manifest.read_text())==record,'Source manifest changed')
    else: manifest.write_text(json.dumps(record,indent=2)+'\n')
    return record

def sum_overlap(start,end,lo,hi):
    """Independent count of active record-months, not daily duration or unique outbreaks."""
    return int(np.maximum(0,np.minimum(end,hi)-np.maximum(start,lo)+1).sum())

def validate_panel(p):
    require(set(p.country)==COUNTRIES and len(p)==1650,'Incorrect countries or rows')
    require(not p.duplicated(['country','yearmonth']).any(),'Duplicate keys')
    months=set(pd.period_range('2014-07','2019-12',freq='M').astype(str))
    require(all(set(g.yearmonth)==months for _,g in p.groupby('country')),'Wrong estimation months')
    require(p.reactive_request.isin([0,1]).all() and p.reactive_request.sum()==58,'Wrong reactive outcome')
    require(p.request_this_month.sum()==73,'Wrong all-request outcome')
    require(np.isfinite(p[[B,W,STEM]].to_numpy(float)).all(),'Nonfinite primary predictor')
    close(p[STEM],p[B]+p[W],1e-9)
    close(p[B],p.groupby('country')[STEM].transform('mean'),1e-9)

def build_panel(out):
    inputs=HERE/'inputs'
    outcomes=module(inputs/'build_request_outcomes.py','locked_outcomes').build(
        pd.read_csv(inputs/'requests.csv',keep_default_na=False))
    builder=module(inputs/'build_active_outbreak_panel.py','locked_activity')
    source=pd.read_csv(inputs/'zheng_outbreak_records.csv')
    p=builder.build(source,outcomes).sort_values(['country','yearmonth']).reset_index(drop=True)
    frozen=pd.read_csv(inputs/'active_outbreak_panel.csv').sort_values(['country','yearmonth']).reset_index(drop=True)
    pd.testing.assert_frame_equal(p[['country','yearmonth']],frozen[['country','yearmonth']])
    require(set(p.columns)==set(frozen.columns),'Rebuilt column mismatch')
    max_diff=0.
    for column in p.columns.difference(['country','yearmonth']):
        close(p[column],frozen[column],1e-9)
        max_diff=max(max_diff,float(np.max(np.abs(p[column]-frozen[column]))))
    validate_panel(p)
    source['mapped_country']=source.country.map(builder.COUNTRY_NAMES)
    starts=pd.to_datetime(source.start_date,errors='raise').dt.to_period('M').astype('int64').to_numpy()
    ends=pd.to_datetime(source.end_date,errors='raise').dt.to_period('M').astype('int64').to_numpy()
    require((ends>=starts).all(),'Invalid source intervals')
    history_months=pd.period_range('2013-07','2019-12',freq='M')
    history=[]
    # Reconstruct all 78 monthly counts directly from source interval overlap.
    for country in sorted(COUNTRIES):
        mask=source.mapped_country.eq(country).to_numpy(); s,e=starts[mask],ends[mask]
        counts=np.array([np.count_nonzero((s<=t.ordinal)&(e>=t.ordinal)) for t in history_months],dtype=int)
        prior=pd.Series(counts).shift(1).rolling(12,min_periods=12).sum()
        inclusive=pd.Series(counts).rolling(12,min_periods=12).sum()
        for i,t in enumerate(history_months):
            history.append(dict(country=country,yearmonth=str(t),active=int(counts[i]),
                lag12=float(counts[i-12]) if i>=12 else np.nan,
                prior_12m=prior.iloc[i],inclusive_12m=inclusive.iloc[i]))
    h=pd.DataFrame(history)
    require(len(h)==1950,'Expected 25 countries x 78 history months')
    p=p.merge(h,on=['country','yearmonth'],how='left',validate='one_to_one')
    require(p[['prior_12m','inclusive_12m','lag12']].notna().all().all(),'Incomplete history')
    close(p.active,p.active_outbreaks_this_month,0)
    close(p.prior_12m,p.active_outbreak_months_prior_12m,0)
    close(p.inclusive_12m,p.prior_12m+p.active-p.lag12,0)
    # Distinct interval-intersection implementation checks all 1,650 window pairs.
    for country,g in p.groupby('country'):
        mask=source.mapped_country.eq(country).to_numpy(); s,e=starts[mask],ends[mask]
        for row in g.itertuples(index=False):
            t=pd.Period(row.yearmonth,freq='M').ordinal
            require(sum_overlap(s,e,t-12,t-1)==row.prior_12m,'Independent prior interval mismatch')
            require(sum_overlap(s,e,t-11,t)==row.inclusive_12m,'Independent inclusive interval mismatch')
    p['inclusive_log1p_12m']=np.log1p(p.inclusive_12m)
    p[IB]=p.groupby('country').inclusive_log1p_12m.transform('mean')
    p[IW]=p.inclusive_log1p_12m-p[IB]
    close(p[IB]+p[IW],p.inclusive_log1p_12m,1e-12)
    close(p.groupby('country')[IW].mean(),0,1e-12)
    p['year']=p.yearmonth.str[:4].astype(int)
    for year in range(2015,2020): p[f'year_{year}']=(p.year==year).astype(float)
    require(p[YEARS].sum(axis=1).eq((p.year!=2014).astype(int)).all(),'Wrong reference-year coding')
    p.to_csv(out/'sensitivity_panel.csv',index=False,float_format='%.17g')
    h.to_csv(out/'monthly_activity_history_2013_2019.csv',index=False,float_format='%.17g')
    annual=p.groupby('year',as_index=False).agg(country_months=('country','size'),
        reactive_request_months=('reactive_request','sum'))
    annual.to_csv(out/'annual_event_counts.csv',index=False)
    events=p.loc[p.reactive_request.eq(1),['country','yearmonth','prior_12m','inclusive_12m','active','lag12']].copy()
    events['prior_zero']=events.prior_12m.eq(0); events['inclusive_zero']=events.inclusive_12m.eq(0)
    events['transition']=np.where(events.prior_zero,'zero','positive')+' -> '+np.where(events.inclusive_zero,'zero','positive')
    require(len(events)==58 and events.prior_zero.sum()==22,'Wrong event audit baseline')
    oldzero=events.loc[events.prior_zero]
    require(oldzero.inclusive_zero.sum()==20 and oldzero.active.gt(0).sum()==2,'Unexpected 22-month transition')
    events.to_csv(out/'event_window_transitions_58.csv',index=False)
    transitions=events.groupby('transition').size().reindex(
      ['zero -> zero','zero -> positive','positive -> zero','positive -> positive'],fill_value=0).rename('event_months').reset_index()
    transitions.to_csv(out/'event_transition_counts.csv',index=False)
    return p,dict(history_start='2013-07',history_end='2019-12',history_rows=len(h),
        estimation_start='2014-07',estimation_end='2019-12',estimation_rows=len(p),
        max_rebuilt_vs_frozen_difference=max_diff,interval_pairs_verified=len(p),
        inclusive_zero_event_months=int(events.inclusive_zero.sum()),
        all_event_transition_counts=dict(zip(transitions.transition,transitions.event_months.astype(int))))

def separation_check(X,y):
    """Numerical LP feasibility test for complete or quasi-complete separation.

    With signed rows Z, separation exists iff Z*b>=0 and sum(Z*b)>=1 is
    feasible (homogeneous rescaling). A second LP distinguishes strict separation.
    Neither near-zero probabilities nor a convergence flag is the criterion.
    """
    X=np.asarray(X,float); y=np.asarray(y,float)
    scale=np.maximum(np.max(np.abs(X),axis=0),1.)
    z=(2*y-1)[:,None]*(X/scale)
    A=np.vstack([-z,-z.sum(axis=0)[None,:]])
    rhs=np.r_[np.zeros(len(y)),-1.]
    res=optimize.linprog(np.zeros(X.shape[1]),A_ub=A,b_ub=rhs,
                        bounds=[(None,None)]*X.shape[1],method='highs')
    require(res.status in (0,2),'Separation LP indeterminate: '+res.message)
    if res.status==2:
        return dict(status='no separating direction found',lp_status=int(res.status))
    strict=optimize.linprog(np.zeros(X.shape[1]),A_ub=-z,b_ub=-np.ones(len(y)),
                          bounds=[(None,None)]*X.shape[1],method='highs')
    require(strict.status in (0,2),'Strict-separation LP indeterminate')
    return dict(status='complete separation' if strict.status==0 else 'quasi-complete separation',lp_status=int(res.status))

def fit_checked(y,design,groups,label,tol=1e-12):
    X=design.to_numpy(float)
    require(np.isfinite(X).all() and np.linalg.matrix_rank(X)==X.shape[1],'Invalid design: '+label)
    sep=separation_check(X,y)
    require(sep['status']=='no separating direction found',label+': '+sep['status'])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fit=sm.GLM(y,design,family=sm.families.Binomial()).fit(maxiter=200,tol=tol,
            cov_type='cluster',cov_kwds={'groups':groups,'use_correction':False})
    messages=[f'{w.category.__name__}: {w.message}' for w in caught]
    require(fit.converged,'Non-convergence: '+label)
    require(not any('separation' in x.lower() or 'converg' in x.lower() for x in messages),'Fit warning: '+label)
    require(np.isfinite(fit.params).all() and np.isfinite(fit.cov_params()).all().all(),'Nonfinite estimate: '+label)
    require((fit.bse>0).all(),'Nonpositive standard error: '+label)
    prob=np.asarray(fit.fittedvalues)
    score=X.T@(y-prob); J=X.T@((prob*(1-prob))[:,None]*X)
    require(np.max(np.abs(score))<1e-7,'Nonzero score: '+label)
    require(np.linalg.eigvalsh(J).min()>0,'Information not positive definite: '+label)
    # A second optimizer solves the score equations from an intercept-only start.
    initial=np.zeros(X.shape[1]); initial[0]=special.logit(np.mean(y))
    solved=optimize.root(lambda b:X.T@(y-special.expit(X@b)),initial,
       jac=lambda b:-(X.T@((special.expit(X@b)*(1-special.expit(X@b)))[:,None]*X)),tol=1e-10)
    require(solved.success,'Independent score solver failed: '+label)
    close(solved.x,np.asarray(fit.params),1e-7)
    # Independently assembled country scores/information and uncorrected sandwich.
    S=[]
    for country in sorted(set(groups)):
        take=groups==country; S.append(np.sum(X[take]*(y[take]-prob[take])[:,None],axis=0))
    S=np.array(S); inverse=np.linalg.inv(J)
    manual=inverse@S.T@S@inverse
    close(manual,fit.cov_params().to_numpy(),1e-8)
    diagnostic=dict(label=label,converged=bool(fit.converged),iterations=int(fit.fit_history['iteration']),
       parameters=X.shape[1],design_columns=list(design.columns),separation=sep,
       max_score=float(np.abs(score).max()),information_condition=float(np.linalg.cond(J)),
       min_information_eigenvalue=float(np.linalg.eigvalsh(J).min()),
       min_fitted_probability=float(prob.min()),max_fitted_probability=float(prob.max()),
       max_independent_coefficient_difference=float(np.abs(solved.x-np.asarray(fit.params)).max()),warnings=messages)
    return fit,diagnostic

def verify_bootstrap(X,y,groups,fit,restricted,term,reps,seed):
    """Separate full-draw computation using solves and explicit cluster residuals."""
    prob=np.asarray(restricted.fittedvalues); unique=sorted(set(groups)); n,k=X.shape; G=len(unique)
    S=[]; Jg=[]
    for g in unique:
        take=groups==g; x=X[take]; pg=prob[take]
        S.append(np.sum(x*(y[take]-pg)[:,None],axis=0))
        Jg.append(np.einsum('ni,n,nj->ij',x,pg*(1-pg),x))
    S,Jg=np.array(S),np.array(Jg); J=Jg.sum(axis=0)
    target=np.eye(k)[term]; direction=np.linalg.solve(J,target)
    factor=G*(n-1)/((G-1)*(n-k))
    observed=float(fit.params.iloc[term]/(fit.bse.iloc[term]*np.sqrt(factor)))
    rng=np.random.default_rng(seed); done=0; tail=0; minimum=float('inf')
    while done<reps:
        batch=min(4096,reps-done)
        weights=rng.choice(np.array([-1.,1.]),size=(batch,G))
        shocks=weights[:,:,None]*S[None,:,:]
        b=np.linalg.solve(J,shocks.sum(axis=1).T).T
        adjusted=shocks-np.einsum('gij,bj->bgi',Jg,b)
        se=np.sqrt(factor*np.sum((adjusted@direction)**2,axis=1))
        require(np.isfinite(se).all() and (se>0).all(),'Invalid independent bootstrap SE')
        t=(b@target)/se
        require(np.isfinite(t).all(),'Nonfinite bootstrap t')
        tail+=int(np.count_nonzero(np.abs(t)>=abs(observed)))
        done+=batch; minimum=min(minimum,float(se.min()))
    return (tail+1)/(reps+1),dict(completed_reps=done,tail_count=tail,
        minimum_bootstrap_se=minimum,observed_t_cv1=observed,all_draws_finite=True)

def run_models(p,out,reps,base_seed):
    locked=pd.read_csv(HERE/'inputs/active_outbreak_results_seeded.csv')
    reference=locked.loc[(locked.outcome=='reactive_request')&(locked.lookback_months==12)&(locked.countries==25)].set_index('component')
    require(len(reference)==2 and reference.index.is_unique,'Ambiguous main reference')
    helper=module(HERE/'inputs/wild_cluster_bootstrap.py','locked_bootstrap')
    y=p.reactive_request.to_numpy(float); groups=p.country.to_numpy()
    specs=[('M0_main',[B,W]),('M1_year_adjusted',[B,W]+YEARS),('M2_month_inclusive',[IB,IW])]
    rows=[]; all_coefficients=[]; diagnostics=[]; failures=[]
    for model_index,(model,terms) in enumerate(specs):
        design=sm.add_constant(p[terms],has_constant='add')
        try:
            fit,diag=fit_checked(y,design,groups,model)
            diagnostics.append(diag)
            ci=fit.conf_int()
            for name in design.columns:
                all_coefficients.append(dict(model=model,term=name,coefficient=float(fit.params[name]),
                  se=float(fit.bse[name]),ci95_low=float(ci.loc[name,0]),ci95_high=float(ci.loc[name,1]),
                  p_asymptotic=float(fit.pvalues[name])))
            if model_index==0:
                for component,name in [('between',B),('within',W)]:
                    close([fit.params[name],*ci.loc[name]],reference.loc[component,
                      ['coefficient_log_odds','ci95_low_asymptotic','ci95_high_asymptotic']].to_numpy(float))
            print(f'{model}: converged, {len(design.columns)} parameters; starting bootstrap checks.',flush=True)
            for term_index,(component,name) in enumerate(zip(['between','within'],terms[:2]),start=1):
                # Fixed before execution. Reference draws use the original saved seeds.
                seed=int(reference.loc[component,'bootstrap_seed']) if model_index==0 else base_seed+model_index*10000+term_index
                restricted_design=design.drop(columns=name)
                restricted,rd=fit_checked(y,restricted_design,groups,model+'_H0_'+component)
                diagnostics.append(rd)
                # The unchanged production helper fits the restricted GLM with default tolerance.
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    helper_null=sm.GLM(y,restricted_design.to_numpy(),family=sm.families.Binomial()).fit()
                require(helper_null.converged and not caught,'Helper restricted fit warning/non-convergence')
                close(helper_null.fittedvalues,restricted.fittedvalues,1e-7)
                bp,t=helper.wclr_c_pvalue(design.to_numpy(),y,groups,fit,term_index,reps,seed)
                independent,bd=verify_bootstrap(design.to_numpy(),y,groups,fit,restricted,term_index,reps,seed)
                close(bp,independent,1e-14); close(t,bd['observed_t_cv1'])
                repeat,_=helper.wclr_c_pvalue(design.to_numpy(),y,groups,fit,term_index,reps,seed)
                require(repeat==bp,'Fixed-seed repeat disagreement')
                if model_index==0 and reps==int(reference.loc[component,'bootstrap_reps']):
                    close(bp,float(reference.loc[component,'p_wclr_c_rademacher']),1e-14)
                rows.append(dict(model=model,component=component,coefficient_log_odds=float(fit.params[name]),
                    se_country_clustered=float(fit.bse[name]),ci95_low_asymptotic=float(ci.loc[name,0]),
                    ci95_high_asymptotic=float(ci.loc[name,1]),p_asymptotic=float(fit.pvalues[name]),
                    p_wclr_c_two_sided=float(bp),t_cv1=float(t),bootstrap_reps=reps,bootstrap_seed=seed,
                    bootstrap_tail_count=bd['tail_count'],countries=25,country_months=1650,event_months=58,
                    total_parameters=len(design.columns),year_adjusted=model_index==1,
                    window='t-11 through t (12 months)' if model_index==2 else 't-12 through t-1 (12 months)',
                    history_period='2013-07 through 2019-12',estimation_period='2014-07 through 2019-12',
                    change_from_main=float(fit.params[name]-reference.loc[component,'coefficient_log_odds']),
                    ci_method='asymptotic normal country-clustered; use_correction=False',
                    bootstrap_method='restricted WCLR-C Rademacher; CV1 studentization; plus-one p',
                    model_converged=True,restricted_converged=True))
                diag['bootstrap_'+component]=dict(seed=seed,**bd,independent_p=independent,
                    fixed_seed_repeat='PASS',restricted_default_vs_tight_max_probability_difference=
                    float(np.abs(helper_null.fittedvalues-restricted.fittedvalues).max()))
                print(f'  {component}: beta={fit.params[name]:.6f}, bootstrap p={bp:.5f}, verified {reps:,} draws.',flush=True)
                pd.DataFrame(rows).to_csv(out/'comparison_results.csv',index=False,float_format='%.17g')
        except (ValueError,AssertionError,np.linalg.LinAlgError,ArithmeticError) as error:
            failures.append(dict(model=model,error=str(error)))
            print(f'FAILED {model}: {error}; retained in diagnostics, not silently repaired.',flush=True)
    pd.DataFrame(all_coefficients).to_csv(out/'all_coefficients_including_years.csv',index=False,float_format='%.17g')
    (out/'model_diagnostics.json').write_text(json.dumps(dict(models=diagnostics,failures=failures),indent=2)+'\n')
    require(not failures,'Model/test failures recorded; do not treat output as fully verified')
    require(len(rows)==6,'Expected six component rows from three specifications')
    return pd.DataFrame(rows)

def make_report(results,construction,out):
    lines=['# Calendar-year and request-month-inclusive sensitivities','',
     'History: July 2013-December 2019. Common estimation period: July 2014-December 2019. '
     'All specifications contain 25 countries, 1,650 observations and 58 reactive request-months. '
     'Main estimates and original sources are unchanged.','',
     '| Specification | Component | Coefficient | Asymptotic 95% CI | WCLR-C p |',
     '| --- | --- | ---: | --- | ---: |']
    for r in results.itertuples(index=False):
        lines.append(f'| {r.model} | {r.component} | {r.coefficient_log_odds:.6f} | '
                     f'[{r.ci95_low_asymptotic:.6f}, {r.ci95_high_asymptotic:.6f}] | {r.p_wclr_c_two_sided:.5f} |')
    lines+=['','## Methods and limitations','',
      'M1 retains the original prior-12-month predictor and adds five calendar-year indicators '
      '(2015-2019; reference July-December 2014). The model has eight parameters including '
      'the intercept. These are annual intercept shifts, not country or year-month fixed effects. '
      'They do not adjust for all within-year shocks or monthly seasonality.','',
      'M2 uses exactly 12 months, t-11 through t, replacing the old t-12 month with the request '
      'month. The log1p transform and country means/deviations are recalculated on the common '
      '66-month estimation period. It is not a 13-month sum. Same-month inclusion cannot order '
      'outbreak and request within that month, and does not establish real-time information '
      'availability, response delay or a replication of Maffioli and Lu.','',
      'CIs use normal asymptotic country-clustered covariance with no small-sample correction, '
      'matching the frozen main table. P-values use restricted WCLR-C with CV1 studentization, '
      '99,999 country-level Rademacher draws and plus-one counting. CIs are not bootstrap-inverted. '
      'P-values are nominal/unadjusted additional reviewer-requested sensitivity tests. '
      'Changes in logit coefficients are not percentages of confounding explained.','',
      '## Event-window transitions','',
      *[f'- {k}: {v} event-months' for k,v in construction['all_event_transition_counts'].items()],
      '',f'Inclusive-window zero events: {construction["inclusive_zero_event_months"]}/58. '
      'Among the 22 originally prior-zero events, 20 remain zero and two become positive. '
      'Other transitions are evaluated over all 58 events, not only those 22.','',
      '## Verification','',
      'The released builders reconstruct the frozen panel from unchanged fundamental data. '
      'A separate interval-intersection calculation verifies both windows for every estimation '
      'row. Full and restricted fits pass rank, numerical separation LP, convergence, score '
      'and information checks. An independent score-equation estimator and manually assembled '
      'country-clustered covariance match the fitted results. Every bootstrap draw is checked '
      'by an additional implementation, and full fixed-seed repetition reproduces each p-value. '
      'Inspect model_diagnostics.json for numerical values and warnings. Numerical stability '
      'does not guarantee finite-sample inferential validity.','',
      'The unresolved local-versus-dashboard provenance of Mozambique 2016 is not settled by '
      'these sensitivity models. No campaign label or original record has been changed.']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reps',type=int,default=99999)
    parser.add_argument('--base-seed',type=int,default=20261007)
    args=parser.parse_args(); require(args.reps>0,'Positive replication count required')
    out=HERE/'outputs'; out.mkdir(exist_ok=True)
    manifest=prepare()
    p,construction=build_panel(out)
    (out/'construction_checks.json').write_text(json.dumps(construction,indent=2)+'\n')
    print('PASS: source history 07/2013-12/2019; common sample 07/2014-12/2019; both 12-month windows independently verified.',flush=True)
    results=run_models(p,out,args.reps,args.base_seed)
    for rel,h in manifest['original_sha256'].items(): require(sha(ROOT/rel)==h,'Original changed: '+rel)
    for name,h in manifest['snapshot_sha256'].items(): require(sha(HERE/'inputs'/name)==h,'Snapshot changed: '+name)
    make_report(results,construction,out)
    record=dict(**manifest,parameters=vars(args),python=sys.version,executable=sys.executable,
        numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,statsmodels=statsmodels.__version__,
        platform=platform.platform(),script_sha256=sha(__file__),originals_unchanged=True,
        bootstrap_seed_rule='M0 saved primary seeds; M1/M2 base_seed + model_index*10000 + component_index (1=between,2=within)',
        analysis_status='reviewer-requested exploratory sensitivities; nominal unadjusted p-values')
    (out/'run_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print(results[['model','component','coefficient_log_odds','ci95_low_asymptotic','ci95_high_asymptotic','p_wclr_c_two_sided']].to_string(index=False))
    print('PASS: all full/restricted fits and bootstrap verifications; canonical hashes unchanged.')

if __name__=='__main__': main()
