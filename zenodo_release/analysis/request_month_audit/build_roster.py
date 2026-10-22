#!/usr/bin/env python3
"""Freeze the 22-month audit universe from the canonical panel and sources."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FINAL = ROOT / "analysis/main"
COUNTRY = dict(zip(
    ["AGO","BEN","BDI","CMR","TCD","COD","ETH","GHA","GIN","CIV","KEN","MWI","MOZ",
     "NAM","NER","NGA","COG","SLE","SOM","SSD","SDN","TZA","UGA","ZMB","ZWE"],
    ["Angola","Benin","Burundi","Cameroon","Chad","DR Congo","Ethiopia","Ghana","Guinea",
     "Ivory Coast","Kenya","Malawi","Mozambique","Namibia","Niger","Nigeria",
     "Republic of the Congo","Sierra Leone","Somalia","South Sudan","Sudan","Tanzania",
     "Uganda","Zambia","Zimbabwe"]))
COUNTRY["TZA_zanzibar"] = "Tanzania"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def main():
    inputs, outputs = HERE / "inputs", HERE / "outputs"
    inputs.mkdir(exist_ok=True); outputs.mkdir(exist_ok=True)
    paths = [ROOT / "data/source/requests.csv", ROOT / "data/source/zheng_outbreak_records.csv",
             FINAL / "outputs/analysis_data/active_outbreak_panel.csv",
             FINAL / "outputs/analysis_data/active_outbreak_results_seeded.csv"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    for path in paths:
        shutil.copy2(path, inputs / path.name)
        require(sha(inputs / path.name) == sha(path), "Snapshot mismatch")
    panel = pd.read_csv(inputs / "active_outbreak_panel.csv")
    requests = pd.read_csv(inputs / "requests.csv", keep_default_na=False)
    source = pd.read_csv(inputs / "zheng_outbreak_records.csv")
    require(len(panel) == 1650 and panel.country.nunique() == 25, "Wrong frozen panel")
    require(panel.reactive_request.sum() == 58, "Wrong event total")
    require(not panel.duplicated(["country","yearmonth"]).any(), "Duplicate panel keys")
    zero = panel.loc[panel.reactive_request.eq(1) & panel.active_outbreak_months_prior_12m.eq(0)].copy()
    zero = zero.sort_values(["country","yearmonth"]).reset_index(drop=True)
    zero["audit_id"] = [f"Z{i:02d}" for i in range(1,len(zero)+1)]
    require(len(zero) == 22 and zero.country.nunique() == 12, "Wrong audit universe")
    require(zero.active_outbreaks_this_month.eq(0).sum() == 20, "Wrong current-month split")
    requests["parsed_date"] = pd.to_datetime(requests.request_date,format="%m/%d/%Y",errors="coerce")
    requests["yearmonth"] = requests.parsed_date.dt.to_period("M").astype(str)
    linked = requests.loc[requests.campaign_type.eq("Reactive")].merge(
        zero[["audit_id","country","yearmonth"]],on=["country","yearmonth"],validate="many_to_one")
    require(len(linked)==24 and linked.request_id.nunique()==24,"Wrong record-ID linkage")
    require(linked.request_id.eq(linked["request_id.1"]).all(),"Duplicate ID columns disagree")
    require(set(linked.audit_id)==set(zero.audit_id),"Some months lack a linked request")
    ids = linked.groupby("audit_id").request_id.agg(lambda s:"; ".join(s))
    dates = linked.groupby("audit_id").request_date.agg(lambda s:"; ".join(sorted(set(s))))
    zero["request_record_ids"] = zero.audit_id.map(ids)
    zero["request_dates_as_recorded"] = zero.audit_id.map(dates)
    zero["n_request_record_ids"] = zero.audit_id.map(linked.groupby("audit_id").size())
    periods = pd.PeriodIndex(zero.yearmonth,freq="M")
    zero["prior_window_start"] = (periods-12).start_time.strftime("%Y-%m-%d")
    zero["prior_window_end"] = (periods-1).end_time.strftime("%Y-%m-%d")
    zero["request_month_start"] = periods.start_time.strftime("%Y-%m-%d")
    zero["request_month_end"] = periods.end_time.strftime("%Y-%m-%d")
    mapped = source.country.map(COUNTRY)
    start = pd.to_datetime(source.start_date).dt.to_period("M").astype("int64").to_numpy()
    end = pd.to_datetime(source.end_date).dt.to_period("M").astype("int64").to_numpy()
    for row in zero.itertuples(index=False):
        month = pd.Period(row.yearmonth,freq="M").ordinal
        mask = mapped.eq(row.country).to_numpy()
        current = int(((start[mask]<=month)&(end[mask]>=month)).sum())
        prior = sum(int(((start[mask]<=month-lag)&(end[mask]>=month-lag)).sum()) for lag in range(1,13))
        require(prior==0 and current==row.active_outbreaks_this_month,f"Interval disagreement: {row.audit_id}")
    keep = ["audit_id","country","yearmonth","request_record_ids","request_dates_as_recorded",
            "n_request_record_ids","prior_window_start","prior_window_end","request_month_start",
            "request_month_end","active_outbreak_months_prior_12m","active_outbreaks_this_month",
            "log1p_active_outbreak_months_12m_between","log1p_active_outbreak_months_12m_within"]
    zero[keep].to_csv(outputs / "master_roster_22.csv",index=False,float_format="%.17g")
    linked[["audit_id","country","yearmonth","request_id","request_date","campaign_type"]].to_csv(
        outputs / "request_linkage_24.csv",index=False)
    require(hashes=={str(p.relative_to(ROOT)):sha(p) for p in paths},"Original input changed")
    manifest={"source_sha256":hashes,"snapshot_sha256":{p.name:sha(inputs/p.name) for p in paths},
              "roster_n":22,"request_record_ids_n":24,"countries_n":12,"current_zero_n":20,
              "current_positive_n":2,"independent_interval_check":"PASS","no_recoding":True}
    (outputs / "input_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(zero[["audit_id","country","yearmonth","n_request_record_ids","active_outbreaks_this_month"]].to_string(index=False))
    print("PASS: 22 months, 24 record IDs, 12 countries, 20+2 split; independent intervals agree; original hashes unchanged.")

if __name__=="__main__":
    main()
