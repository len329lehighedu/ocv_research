#!/usr/bin/env python3
"""Reviewer-requested two-sided test of beta_between == beta_within.

The original main specification is frozen. Reparameterizing its linear
predictor permits reuse of the unchanged restricted WCLR-C helper.
No primary data, main results or campaign labels are modified.
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
from scipy import optimize, special, stats
import statsmodels
import statsmodels.api as sm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STEM = 'log1p_active_outbreak_months_12m'
BETWEEN, WITHIN = STEM+'_between', STEM+'_within'
COUNTRIES = {'Angola','Benin','Burundi','Cameroon','Chad','DR Congo','Ethiopia',
 'Ghana','Guinea','Ivory Coast','Kenya','Malawi','Mozambique','Namibia','Niger',
 'Nigeria','Republic of the Congo','Sierra Leone','Somalia','South Sudan','Sudan',
 'Tanzania','Uganda','Zambia','Zimbabwe'}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def close(a,b,tol=1e-8):
    np.testing.assert_allclose(a,b,atol=tol,rtol=0)

def prepare():
    folder=HERE/'inputs'; folder.mkdir(exist_ok=True)
    paths={
      'active_outbreak_panel.csv':ROOT/'analysis/main/outputs/analysis_data/active_outbreak_panel.csv',
      'active_outbreak_results_seeded.csv':ROOT/'analysis/main/outputs/analysis_data/active_outbreak_results_seeded.csv',
      'wild_cluster_bootstrap.py':ROOT/'analysis/main/code/research_pipeline/results/wild_cluster_bootstrap.py',
    }
    originals=list(paths.values())+[
      ROOT/'data/source/requests.csv',
      ROOT/'data/source/zheng_outbreak_records.csv']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in originals}
    # Existing snapshots may not be silently refreshed to bypass a discrepancy.
    for name,path in paths.items():
        target=folder/name
        if target.exists():
            require(sha(target)==sha(path),f'Snapshot/canonical discrepancy: {name}')
        else:
            shutil.copy2(path,target)
    record={'original_sha256':hashes,'snapshot_sha256':{n:sha(folder/n) for n in paths}}
    manifest=folder/'input_manifest.json'
    if manifest.exists():
        require(json.loads(manifest.read_text())==record,'Input provenance changed; investigate first')
    else:
        manifest.write_text(json.dumps(record,indent=2)+'\n')
    return record

def panel_checks(p):
    require(set(p.country)==COUNTRIES,'Incorrect country roster')
    require(len(p)==1650 and not p.duplicated(['country','yearmonth']).any(),'Panel keys/size wrong')
    months=set(pd.period_range('2014-07','2019-12',freq='M').astype(str))
    require(all(set(g.yearmonth)==months for _,g in p.groupby('country')),'Wrong estimation months')
    require(p.reactive_request.isin([0,1]).all() and p.reactive_request.sum()==58,'Wrong outcome')
    cols=[STEM,BETWEEN,WITHIN,'reactive_request']
    require(np.isfinite(p[cols].to_numpy(float)).all(),'Nonfinite input')
    close(p[STEM],p[BETWEEN]+p[WITHIN],1e-9)
    close(p[BETWEEN],p.groupby('country')[STEM].transform('mean'),1e-9)

def fit_glm(y,design,groups):
    require(np.linalg.matrix_rank(design)==design.shape[1],'Rank-deficient design')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=sm.GLM(y,design,family=sm.families.Binomial()).fit(
            cov_type='cluster',cov_kwds={'groups':groups,'use_correction':False},
            maxiter=200,tol=1e-12)
    messages=[f'{w.category.__name__}: {w.message}' for w in caught]
    require(result.converged,'Non-converged model')
    require(not any('separation' in x.lower() or 'converg' in x.lower() for x in messages),
            'Convergence/separation warning: '+'; '.join(messages))
    require(np.isfinite(result.params).all() and np.isfinite(result.cov_params()).all().all(),
            'Nonfinite fit/covariance')
    return result,messages

def cluster_arrays(X,y,prob,groups):
    # Separate implementation for verification, not the production helper.
    score=[]; info=[]
    for country in sorted(set(groups)):
        take=groups==country
        x=X[take]; pg=prob[take]
        score.append(np.sum(x*(y[take]-pg)[:,None],axis=0))
        info.append(np.einsum('ni,n,nj->ij',x,pg*(1-pg),x))
    return np.array(score),np.array(info)

def direct_contrast_bootstrap(X,y,groups,unrestricted_prob,restricted_prob,c,reps,seed):
    """Independent original-parameterization contrast with imposed equality.

    c=[0,1,-1]; restricted probabilities come from alpha + beta*X_logged.
    Uses scalar draws/solves to cross-check the vectorized production helper.
    """
    G=len(set(groups)); n,k=X.shape
    factor=G*(n-1)/((G-1)*(n-k))
    us,uj=cluster_arrays(X,y,unrestricted_prob,groups)
    ujinv=np.linalg.inv(uj.sum(axis=0))
    v=factor*ujinv@(us.T@us)@ujinv
    rs,rj=cluster_arrays(X,y,restricted_prob,groups)
    j=rj.sum(axis=0)
    direction=np.linalg.solve(j,c)
    rng=np.random.default_rng(seed)
    tstar=[]
    for _ in range(reps):
        signs=rng.choice(np.array([-1.,1.]),size=G)
        s=rs*signs[:,None]
        b=np.linalg.solve(j,s.sum(axis=0))
        residual=np.array([s[g]-rj[g]@b for g in range(G)])
        se=np.sqrt(factor*np.sum((residual@direction)**2))
        require(np.isfinite(se) and se>0,'Invalid verification bootstrap SE')
        tstar.append(float(c@b/se))
    return np.array(tstar),v

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reps',type=int,default=99999)
    parser.add_argument('--seed',type=int,default=20261007)
    args=parser.parse_args()
    require(args.reps>0,'Positive replication count required')
    out=HERE/'outputs'; out.mkdir(exist_ok=True)
    manifest=prepare()
    p=pd.read_csv(HERE/'inputs/active_outbreak_panel.csv').sort_values(['country','yearmonth']).reset_index(drop=True)
    panel_checks(p)
    y=p.reactive_request.to_numpy(float); groups=p.country.to_numpy()
    original=sm.add_constant(p[[BETWEEN,WITHIN]],has_constant='add')
    # Derive X from the exact same two design columns: algebraic equality by construction.
    eq=pd.DataFrame({'const':1.,'X':p[BETWEEN]+p[WITHIN],'delta':p[BETWEEN]})
    fit,w1=fit_glm(y,original,groups)
    refit,w2=fit_glm(y,eq,groups)
    frozen=pd.read_csv(HERE/'inputs/active_outbreak_results_seeded.csv')
    frozen=frozen.loc[(frozen.outcome=='reactive_request')&(frozen.lookback_months==12)&(frozen.countries==25)].set_index('component')
    require(len(frozen)==2 and frozen.index.is_unique,'Ambiguous frozen baseline')
    for component,term in [('between',BETWEEN),('within',WITHIN)]:
        close([fit.params[term],*fit.conf_int().loc[term]],frozen.loc[component,
          ['coefficient_log_odds','ci95_low_asymptotic','ci95_high_asymptotic']].to_numpy(float))
    c=np.array([0.,1.,-1.]); beta=fit.params.to_numpy()
    delta=float(c@beta); cov=fit.cov_params().to_numpy()
    se=float(np.sqrt(c@cov@c))
    ci=delta+stats.norm.ppf([.025,.975])*se
    close(delta,refit.params['delta']); close(fit.params[WITHIN],refit.params['X'])
    close(fit.fittedvalues,refit.fittedvalues,1e-10)
    close(fit.llf,refit.llf,1e-9); close(se,refit.bse['delta'])
    contrast=fit.t_test(c)
    close(delta,float(np.asarray(contrast.effect).item()))
    close(se,float(np.asarray(contrast.sd).item()))
    # Independent score-equation MLE, initialized without the GLM estimates.
    X=original.to_numpy(float)
    solution=optimize.root(lambda b:X.T@(y-special.expit(X@b)),
       np.array([special.logit(y.mean()),0.,0.]),
       jac=lambda b:-(X.T@((special.expit(X@b)*(1-special.expit(X@b)))[:,None]*X)),tol=1e-10)
    require(solution.success,'Independent MLE score solver failed')
    close(solution.x,beta,1e-8)
    restricted,w3=fit_glm(y,eq[['const','X']],groups)
    rp=np.asarray(restricted.fittedvalues)
    equal_beta=np.array([restricted.params['const'],restricted.params['X'],restricted.params['X']])
    close(special.expit(X@equal_beta),rp,1e-12)
    scores,Jg=cluster_arrays(X,y,rp,groups)
    null_score=np.array([scores[:,0].sum(),scores[:,1:].sum()])
    require(np.max(np.abs(null_score))<1e-7,'Restricted nuisance score not zero')
    require(np.linalg.eigvalsh(Jg.sum(axis=0)).min()>0,'Restricted information not positive definite')
    for design,result in [(original,fit),(eq,refit),(eq[['const','X']],restricted)]:
        require(np.max(np.abs(design.to_numpy().T@(y-np.asarray(result.fittedvalues))))<1e-7,
                'Nonzero fitted score')
    spec=importlib.util.spec_from_file_location('locked_wild',HERE/'inputs/wild_cluster_bootstrap.py')
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    # Equality is imposed by removing DELTA from the equivalent model, not by
    # removing between or within from the original specification.
    probe=513
    independent_t,cv1=direct_contrast_bootstrap(X,y,groups,np.asarray(fit.fittedvalues),rp,c,probe,args.seed)
    factor=len(COUNTRIES)*(len(p)-1)/((len(COUNTRIES)-1)*(len(p)-3))
    close(np.sqrt(c@cv1@c),np.sqrt(factor)*se)
    observed=delta/np.sqrt(c@cv1@c)
    direct_p=(np.count_nonzero(np.abs(independent_t)>=abs(observed))+1)/(probe+1)
    probe_p,probe_t=helper.wclr_c_pvalue(eq.to_numpy(),y,groups,refit,2,probe,args.seed)
    close(probe_t,observed); close(probe_p,direct_p,1e-14)
    # Compare every bootstrap t, not just a coincidentally matching tail count.
    rs2,j2=helper._cluster_scores_and_information(eq.to_numpy(),y,rp,groups)
    signs=np.random.default_rng(args.seed).choice(np.array([-1.,1.]),size=(probe,len(COUNTRIES)))
    ss=signs[:,:,None]*rs2[None,:,:]; jinv=np.linalg.inv(j2.sum(axis=0))
    bs=ss.sum(axis=1)@jinv.T
    residual=ss-np.einsum('gij,bj->bgi',j2,bs)
    tst=bs[:,2]/np.sqrt(factor*np.sum((residual@jinv[2,:])**2,axis=1))
    close(independent_t,tst,1e-8)
    reverse=eq.copy(); reverse['delta']=-reverse['delta']
    reverse_fit,w4=fit_glm(y,reverse,groups)
    reverse_p,reverse_t=helper.wclr_c_pvalue(reverse.to_numpy(),y,groups,reverse_fit,2,probe,args.seed)
    close(reverse_fit.params['delta'],-delta); close(reverse_fit.bse['delta'],se)
    close(reverse_p,probe_p,1e-14); close(reverse_t,-probe_t)
    print('PASS: frozen model, equivalent model, covariance contrast, independent MLE and 513 paired bootstrap draws.',flush=True)
    print(f'Running {args.reps:,} WCLR-C draws; seed={args.seed}; two-sided H0: beta_B=beta_W.',flush=True)
    bootstrap_p,t=helper.wclr_c_pvalue(eq.to_numpy(),y,groups,refit,2,args.reps,args.seed)
    repeated_p,repeated_t=helper.wclr_c_pvalue(eq.to_numpy(),y,groups,refit,2,args.reps,args.seed)
    require(bootstrap_p==repeated_p and t==repeated_t,'Bootstrap repeat-run disagreement')
    # Recover the count from the helper's documented plus-one convention.
    tail_count=int(round(bootstrap_p*(args.reps+1)-1))
    require(0<=tail_count<=args.reps,'Invalid bootstrap tail count')
    for rel,h in manifest['original_sha256'].items():
        require(sha(ROOT/rel)==h,f'Canonical file changed: {rel}')
    for name,h in manifest['snapshot_sha256'].items():
        require(sha(HERE/'inputs'/name)==h,f'Snapshot changed: {name}')
    result=dict(outcome='reactive_request',lookback_months=12,countries=25,country_months=1650,event_months=58,
      beta_between=float(fit.params[BETWEEN]),beta_within=float(fit.params[WITHIN]),
      contrast='between-minus-within',null_hypothesis='beta_between = beta_within',
      delta_log_odds=delta,se_country_clustered_asymptotic=se,
      ci95_low_asymptotic=float(ci[0]),ci95_high_asymptotic=float(ci[1]),
      p_asymptotic_two_sided=float(2*stats.norm.sf(abs(delta/se))),
      p_wclr_c_two_sided=float(bootstrap_p),t_cv1_for_wclr_c=float(t),
      covariance_between_within=float(cov[1,2]),bootstrap_reps=args.reps,bootstrap_seed=args.seed,
      bootstrap_tail_count=tail_count,bootstrap_p_convention='(tail_count+1)/(reps+1)',
      ci_method='normal asymptotic country-clustered; use_correction=False; not bootstrap-inverted',
      bootstrap_method='restricted WCLR-C; Rademacher cluster weights; CV1 studentization',
      scale='unstandardized log-odds per unit of log1p outbreak activity',
      analysis_status='additional reviewer-requested contrast; main specification unchanged')
    pd.DataFrame([result]).to_csv(out/'contrast_results.csv',index=False,float_format='%.17g')
    diagnostics=dict(original_converged=bool(fit.converged),equivalent_converged=bool(refit.converged),
      restricted_converged=bool(restricted.converged),original_log_likelihood=float(fit.llf),
      equivalent_log_likelihood=float(refit.llf),restricted_log_likelihood=float(restricted.llf),
      maximum_probability_disagreement=float(np.max(np.abs(fit.fittedvalues-refit.fittedvalues))),
      maximum_independent_mle_disagreement=float(np.max(np.abs(solution.x-beta))),
      restricted_nuisance_score_max_abs=float(np.max(np.abs(null_score))),
      original_design_condition=float(np.linalg.cond(X)),
      restricted_information_condition=float(np.linalg.cond(Jg.sum(axis=0))),
      probe_reps=probe,probe_two_sided_p=probe_p,
      max_direct_vs_equivalent_bootstrap_t_difference=float(np.max(np.abs(independent_t-tst))),
      reverse_contrast_probe='PASS',fixed_seed_full_repeat='PASS',canonical_hashes_unchanged=True,
      warnings=w1+w2+w3+w4)
    (out/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    versions=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__,
      scipy=scipy.__version__,statsmodels=statsmodels.__version__,script_sha256=sha(__file__),
      **manifest,command_parameters=vars(args))
    (out/'run_manifest.json').write_text(json.dumps(versions,indent=2)+'\n')
    (out/'RESULTS.md').write_text(
      '# Between-minus-within contrast\n\n'
      'Additional reviewer-requested analysis of the frozen 25-country reactive-request model. '
      'No data or main estimates were changed.\n\n'
      f'- Between coefficient: {result["beta_between"]:.9f}\n'
      f'- Within coefficient: {result["beta_within"]:.9f}\n'
      f'- Difference (between minus within): {delta:.9f}\n'
      f'- Asymptotic country-clustered SE: {se:.9f}\n'
      f'- Asymptotic 95% CI: [{ci[0]:.9f}, {ci[1]:.9f}]\n'
      f'- Two-sided restricted WCLR-C p-value: {bootstrap_p:.5f}\n'
      f'- Replications: {args.reps:,}; seed: {args.seed}; exceedances: {tail_count:,}\n\n'
      'The CI is asymptotic, not bootstrap-inverted. Bootstrap studentization uses '
      'the existing CV1 finite-sample correction. Inference should be described '
      'from the direct contrast, not a comparison of individual significance labels. '
      'A rejection does not establish causation or absence of a within association; '
      'non-rejection does not establish equivalence.\n\n'
      'Verification: original/equivalent fits, independent score-equation MLE, '
      'covariance contrast, 513 paired original/equivalent bootstrap t statistics, '
      'reverse contrast, full fixed-seed rerun and frozen hashes all passed. '
      'Numerical verification does not validate source provenance or guarantee '
      'finite-sample calibration with 25 clusters and 58 events.\n')
    print(pd.DataFrame([result]).to_string(index=False))
    print('PASS: full fixed-seed repeat; canonical inputs and frozen results unchanged.')

if __name__=='__main__':
    main()
