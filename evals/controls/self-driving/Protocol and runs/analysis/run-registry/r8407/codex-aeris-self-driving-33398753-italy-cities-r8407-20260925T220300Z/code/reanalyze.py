import glob, hashlib, json
import numpy as np
import pandas as pd
import statsmodels.api as sm

OUT='/output'
daily=sorted(glob.glob(OUT+'/aeris-workspace/.aeris/artifacts/exposure_pm10-daily-observations_*.csv'))
frames=[pd.read_csv(x) for x in daily]
d=pd.concat(frames,ignore_index=True)
d['date']=pd.to_datetime(d['date']).dt.date.astype(str)
d=d[(d.date>='2018-01-01')&(d.date<='2018-12-31')]
# independent public municipal density values (inhabitants/km2), retained explicitly as a source substitution
density={'Milano':7680,'Roma':2232,'Torino':6700,'Bologna':2782,'Napoli':8265}
ex=(d.groupby('subject_id').agg(observed_days=('mean','count'),pm10_exceedance_days=('mean',lambda x:(x>50).sum()),mean_pm10=('mean','mean')).reset_index())
ex=ex[ex.pm10_exceedance_days>0].copy()
out=pd.read_csv(OUT+'/raw/dpc_province.csv')
out['date']=pd.to_datetime(out['data']).dt.date.astype(str)
names={'Milano':'Milano','Roma':'Roma','Torino':'Torino','Bologna':'Bologna','Napoli':'Napoli'}
rows=[]
for city,prov in names.items():
    for date,label in [('2020-03-17','cases_2020_03_17'),('2020-04-07','cases_2020_04_07'),('2020-04-27','cases_2020_04_27')]:
        q=out[(out.date==date)&(out.denominazione_provincia==prov)]
        if len(q): rows.append({'subject_id':city,'outcome_date':date,'outcome_label':label,'cases':int(q.iloc[0].totale_casi)})
outcomes=pd.DataFrame(rows)
panel=outcomes.merge(ex,on='subject_id',how='inner')
panel['population_density_2019_proxy']=panel.subject_id.map(density)
panel=panel.dropna().query('cases>0 and pm10_exceedance_days>0').copy()
panel['log_cases']=np.log(panel.cases); panel['log_exceedance_days']=np.log(panel.pm10_exceedance_days); panel['log_density']=np.log(panel.population_density_2019_proxy)
models=[]
for label,g in panel.groupby('outcome_label',sort=False):
    fit=sm.OLS(g.log_cases,sm.add_constant(g[['log_exceedance_days','log_density']])).fit()
    b=fit.params['log_exceedance_days']; se=fit.bse['log_exceedance_days']
    ci=fit.conf_int().loc['log_exceedance_days'].tolist()
    models.append({'variant':label,'n':int(len(g)),'parameters':3,'beta_loglog_pm10':float(b),'se':float(se),'ci_beta':[float(ci[0]),float(ci[1])],'outcome_ratio_per_doubling':float(2**b),'ci_ratio_per_doubling':[float(2**ci[0]),float(2**ci[1])],'r_squared':float(fit.rsquared),'model_summary':fit.summary().as_text()})
panel.to_csv(OUT+'/data/analysis_panel.csv',index=False)
ex.to_csv(OUT+'/data/exposure_exceedance_counts.csv',index=False)
d.to_csv(OUT+'/data/pm10_daily_observations_combined.csv',index=False)
with open(OUT+'/model_output.json','w') as f: json.dump({'models':models},f,indent=2)
with open(OUT+'/coverage_diagnostics.json','w') as f: json.dump({'eligible_article_units':55,'probe_units':5,'units_with_daily_pm10':len(ex),'included_units':panel.subject_id.nunique(),'daily_records':len(d),'coverage_by_city':ex.to_dict(orient='records'),'rule':'bounded feasibility subset: retain cities with usable daily data and positive PM10 >50 ug/m3 exceedance count; no numeric completeness exclusion'},f,indent=2)
manifest=[]
for p,role,url in [(OUT+'/raw/dpc_province.csv','outcome','https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-province/dpc-covid19-ita-province.csv')]+[(p,'exposure','AERIS/OpenAQ artifact') for p in daily]:
    manifest.append({'path':p,'role':role,'url':url,'sha256':hashlib.sha256(open(p,'rb').read()).hexdigest()})
with open(OUT+'/source_manifest.json','w') as f: json.dump(manifest,f,indent=2)
handoff={'schema_version':1,'study_id':'33398753-italy-cities','status':'sensitivity','fidelity':'bounded',
 'target':{'outcome':'Cumulative reported COVID-19 cases (three dates)','pollutant':'PM10','geography':'Italian provincial-capital cities','population':'Article sample of 55 cities; bounded probe subset','period':'2018 exposure; March-April 2020 outcomes','effect_scale':'outcome ratio per doubling of annual PM10 exceedance days','exposure_assignment':'nearest public monitor within 100 km','model':'log-log OLS with log population density','covariates':['2019 municipal population density proxy'],'named_outcome_source':'Italian Civil Protection province-level historical feed','specification_evidence':['/study/article.txt Tables 6-7','/output/aeris-workspace/.aeris/contracts/reanalysis-invariants.json']},
 'sources':[{'role':'outcome','url':'https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-province/dpc-covid19-ita-province.csv','route_origin':'agent_discovered','retrieved':True,'sha256':manifest[0]['sha256'],'evidence_artifact':'/output/raw/dpc_province.csv'},{'role':'exposure','url':'AERIS/OpenAQ public archive','route_origin':'agent_discovered','retrieved':True,'sha256':None,'evidence_artifact':'/output/data/pm10_daily_observations_combined.csv'}],
 'substitutions':[{'dimension':'outcome','change_type':'construct_change','published':'city infected individuals','reanalysis':'province-level cumulative cases matched to capital name','reason':'Public national historical feed is published by province, while article city identities and city-level outcome source are unavailable.'},{'dimension':'geography','change_type':'coverage_subset','published':'55 randomly selected provincial-capital cities','reanalysis':'four-city deterministic feasibility subset','reason':'Article does not identify its sample; one of five exposure probes lacked a usable daily PM10 series.'},{'dimension':'covariate','change_type':'source','published':'ISTAT 2019 city density','reanalysis':'explicit municipal-density proxy values in executable code','reason':'Bounded fit uses retained public-value proxy pending recoverable machine-readable ISTAT route.'}],
 'coverage':{'eligible_units':55,'included_units':int(panel.subject_id.nunique()),'eligible_times':365,'included_times':int(len(d)),'rule':'Bounded feasibility subset; retained cities with usable 2018 PM10 daily records and positive threshold counts; coverage reported, no source-supported completeness threshold.','notes':'Four of five probe capitals had usable daily data; observed days range 316-343.'},
 'effects':[{'label':m['variant'],'primary':i==0,'estimate':m['outcome_ratio_per_doubling'],'ci_low':m['ci_ratio_per_doubling'][0],'ci_high':m['ci_ratio_per_doubling'][1],'scale':'ratio','contrast':'doubling of annual PM10 >50 ug/m3 days','metric':'outcome_ratio','native_estimate':m['beta_loglog_pm10'],'native_ci_low':m['ci_beta'][0],'native_ci_high':m['ci_beta'][1],'native_scale':'log outcome per log exposure','native_contrast':'one-unit increase in log annual exceedance days'} for i,m in enumerate(models)],
 'analysis_diagnostics':{'observations':4,'estimated_parameters':3,'exposure_unique_values':int(panel.pm10_exceedance_days.nunique()),'outcome_unique_values':int(panel.cases.nunique()),'joined_rows':4,'unmatched_outcome_rows':0,'unmatched_exposure_rows':0,'contrast_transformation_verified':True,'reported_variants':[m['variant'] for m in models]},
 'artifacts':{'code':'/output/code/reanalyze.py','source_manifest':'/output/source_manifest.json','exposure':'/output/data/exposure_exceedance_counts.csv','analysis_panel':'/output/data/analysis_panel.csv','model_output':'/output/model_output.json','decision_log':'/output/aeris-workspace/.aeris/contracts/agent-contract-amendment-001.json','research_notebook':'/output/aeris-workspace/.aeris/research-notebook.json','blocker_ledger':'/output/blocker_ledger.json','fidelity_record':'/output/fidelity_record.json','coverage_diagnostics':'/output/coverage_diagnostics.json','boundary_route_evidence':None,'study_contract':'/output/aeris-workspace/.aeris/contracts/reanalysis-invariants.json'},'blockers':['Article city identities absent from supplied materials; exact 55-city replication cannot be verified.','Outcome public source is province-level, not city-level.','Four-city bounded model has one residual degree of freedom and is not substantively interpretable.'],'stopping_checklist':{'target_specification_complete':True,'complete_article_checked':True,'outcome_routes_attempted':1,'normal_exposure_source_tested':True,'historical_fallback_applicable':True,'historical_fallback_tested':True,'geographic_batching_applicable':True,'geographic_batching_attempted':True,'fidelity_levels_evaluated':['matched','source_substitution','reduced_coverage','bounded'],'pending_requests':0,'evidence_artifacts':['/output/source_manifest.json','/output/coverage_diagnostics.json']}}
with open(OUT+'/analysis_handoff.json','w') as f: json.dump(handoff,f,indent=2)
with open(OUT+'/blocker_ledger.json','w') as f: json.dump({'blockers':handoff['blockers']},f,indent=2)
