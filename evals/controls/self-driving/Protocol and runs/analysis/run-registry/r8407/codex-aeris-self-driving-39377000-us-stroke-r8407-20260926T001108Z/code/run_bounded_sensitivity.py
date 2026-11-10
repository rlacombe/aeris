"""Public-data bounded sensitivity for PMID 39377000.

This deliberately does not use article outcome/exposure values.  It joins CDC
Tracking Network EPA-Downscaler county PM2.5 (2016--2020 average) to CDC Atlas
2018--2020 county stroke mortality.  The latter is all-stroke, age 35+, so this
is explicitly a bounded source-substituted sensitivity, not the article model.
"""
import json
from pathlib import Path
import pandas as pd
import statsmodels.api as sm

ROOT = Path('/output')
RAW = ROOT / 'raw'
DERIVED = ROOT / 'derived'
DERIVED.mkdir(exist_ok=True)

states = {'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10','DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19','KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44','SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55','WY':'56'}

def norm(x):
    return str(x).lower().replace(' county','').replace(' parish','').replace(' borough','').replace(' census area','').replace(' municipality','').replace(' city and borough','').replace(' city','').replace("'",'').replace('.','').strip()

pm = pd.DataFrame(json.load(open(RAW/'cdc_pm25_county_2016_2020.json')))
pm['fips'] = pm.statefips.str.zfill(2) + pm.countyfips.str.zfill(3)
pm['pm25'] = pd.to_numeric(pm.pm25_mean_2016_2020)
pm['days'] = pd.to_numeric(pm.days)

out = pd.read_csv(RAW/'cdc_stroke_2018_2020.csv', dtype={'LocationID':str})
out = out[(out.GeographicLevel=='County') & (out.StratificationCategory1=='Sex') &
          (out.Stratification1=='Overall') & (out.StratificationCategory2=='Race/Ethnicity') &
          (out.Stratification2=='Overall')].copy()
out['stroke_rate_35plus'] = pd.to_numeric(out.Data_Value, errors='coerce')
out['fips'] = out.LocationID.str.zfill(5)
out = out[['fips','LocationDesc','LocationAbbr','stroke_rate_35plus','Data_Value_Type']].drop_duplicates('fips')

# PLACES 2020 release gives 2018 county modeled risk-factor estimates. It is
# used only in the adjusted sensitivity, never presented as article covariates.
pl = pd.read_csv(RAW/'cdc_places_2020.csv')
ids = ['DIABETES','OBESITY','CSMOKING','ACCESS2']
pl = pl[(pl.Year==2018) & (pl.StateAbbr.isin(states)) & (pl.MeasureId.isin(ids)) &
        (pl.Data_Value_Type=='Crude prevalence')].copy()
pl['key'] = pl.StateAbbr + '|' + pl.LocationName.map(norm)
wide = pl.pivot_table(index='key', columns='MeasureId', values='Data_Value', aggfunc='first').reset_index()
out['key'] = out.LocationAbbr + '|' + out.LocationDesc.map(norm)

panel = out.merge(pm[['fips','pm25','days']], on='fips', how='inner').merge(wide, on='key', how='left')
panel['in_scope_state'] = panel.LocationAbbr.isin(states)
panel = panel[panel.in_scope_state & panel.stroke_rate_35plus.notna() & panel.pm25.notna()].copy()
panel.to_csv(DERIVED/'bounded_analysis_panel.csv', index=False)

def fit(cols, label):
    d = panel.dropna(subset=['stroke_rate_35plus'] + cols).copy()
    X = sm.add_constant(d[cols].astype(float), has_constant='add')
    m = sm.OLS(d.stroke_rate_35plus.astype(float), X).fit(cov_type='HC3')
    rows=[]
    for term in m.params.index:
        rows.append({'term':term,'estimate':float(m.params[term]),'se_hc3':float(m.bse[term]),
                     'ci_low':float(m.conf_int().loc[term,0]),'ci_high':float(m.conf_int().loc[term,1]),
                     'p_value':float(m.pvalues[term])})
    return {'label':label,'n':int(m.nobs),'parameters':int(len(m.params)),'r_squared':float(m.rsquared),
            'terms':rows}

models=[fit(['pm25'],'univariable_OLS')]
adjusters=['DIABETES','OBESITY','CSMOKING','ACCESS2']
models.append(fit(['pm25']+adjusters,'risk_factor_adjusted_OLS_HC3'))
summary={'study_id':'39377000-us-stroke','analysis_type':'bounded source-substituted sensitivity',
         'outcome_construct':'CDC Atlas all-stroke age-adjusted 3-year mortality rate among adults 35+ (2018-2020)',
         'exposure_construct':'CDC Tracking Network county EPA Downscaler mean daily PM2.5, 2016-2020 average',
         'native_contrast':'additive deaths per 100,000 per 1 ug/m3 PM2.5',
         'eligible_atlas_counties':int(len(out)),'joined_counties':int(len(panel)),
         'pm25_days_min':int(panel.days.min()),'pm25_days_max':int(panel.days.max()),
         'pm25_unique_values':int(panel.pm25.nunique()),'outcome_unique_values':int(panel.stroke_rate_35plus.nunique()),
         'models':models,
         'limitations':['Outcome differs materially from article: all stroke, age 35+, spatially smoothed 2018-2020 three-year rate rather than ischemic/hemorrhagic age 65+ 2016-2020.','Adjusted sensitivity uses PLACES 2018 modeled adult prevalences and omits article income, Gini, poverty, CAD, and park-access covariates.','No conversion of additive OLS slopes to a ratio was performed.']}
json.dump(summary, open(DERIVED/'bounded_model_output.json','w'), indent=2)
pd.DataFrame([t | {'model':m['label'],'n':m['n'],'r_squared':m['r_squared']} for m in models for t in m['terms']]).to_csv(DERIVED/'bounded_model_terms.csv',index=False)
print(json.dumps(summary,indent=2))
