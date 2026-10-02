from __future__ import annotations

from pathlib import Path
from statistics import NormalDist
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


INPUT = Path("data/processed/monthly_panel.csv")
OUTPUT = Path("outputs")
VISUALS = Path("visuals")
DOC_ASSETS = Path("docs/assets")

TREATED = ["HV1","HV3"]
CONTROLS = ["LEIR","DCST","BLAR"]


def hac_fit(formula: str, data: pd.DataFrame):
    return smf.ols(formula,data=data).fit(cov_type="HAC",cov_kwds={"maxlags":3})


def add_terms(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    out["t"]=(out["month"].dt.year-2021)*12+(out["month"].dt.month-7)
    out["sin12"]=np.sin(2*np.pi*out["t"]/12)
    out["cos12"]=np.cos(2*np.pi*out["t"]/12)
    out["month_num"]=out["month"].dt.month.astype("category")
    for phase in ["anticipation","year1","year2"]:
        out[phase]=(out["phase"]==phase).astype(int)
    return out


def baseline_centred_series(df: pd.DataFrame, treated, controls):
    subset=df[df["site_code"].isin(treated+controls)&df["valid_month"]&df["no2_ug_m3"].notna()].copy()
    baseline=subset[subset["phase"]=="baseline"].groupby("site_code")["no2_ug_m3"].mean()
    subset["delta"]=subset["no2_ug_m3"]-subset["site_code"].map(baseline)
    series=subset.groupby(["month","group"])["delta"].mean().unstack().reset_index()
    phase_map=subset.drop_duplicates("month").set_index("month")["phase"]
    series["phase"]=series["month"].map(phase_map)
    series["gap_delta"]=series["treated"]-series["control"]
    return add_terms(series)


def effects(fit,name):
    ci=fit.conf_int()
    return pd.DataFrame([{
        "model":name,"phase":phase,"estimate_ug_m3":fit.params[phase],
        "std_error":fit.bse[phase],"ci95_low":ci.loc[phase,0],
        "ci95_high":ci.loc[phase,1],"p_value":fit.pvalues[phase],
    } for phase in ["anticipation","year1","year2"]])


def save_copy(fig, filename):
    VISUALS.mkdir(exist_ok=True)
    DOC_ASSETS.mkdir(parents=True,exist_ok=True)
    fig.savefig(VISUALS/filename,dpi=180)
    fig.savefig(DOC_ASSETS/filename,dpi=180)


def main():
    OUTPUT.mkdir(exist_ok=True)
    df=pd.read_csv(INPUT,parse_dates=["month"])
    series=baseline_centred_series(df,TREATED,CONTROLS)

    primary=hac_fit("gap_delta ~ sin12 + cos12 + anticipation + year1 + year2",series)
    month_fe=hac_fit("gap_delta ~ month_num + anticipation + year1 + year2",series)
    trend_harm=hac_fit("gap_delta ~ t + sin12 + cos12 + anticipation + year1 + year2",series)
    trend_month=hac_fit("gap_delta ~ t + month_num + anticipation + year1 + year2",series)

    # Complete-case sensitivity.
    valid=df[df["site_code"].isin(TREATED+CONTROLS)&df["valid_month"]&df["no2_ug_m3"].notna()].copy()
    counts=valid.groupby("month")["site_code"].nunique()
    complete=counts[counts==5].index
    cc=valid[valid["month"].isin(complete)].groupby(["month","group"])["no2_ug_m3"].mean().unstack().reset_index()
    phase_map=valid.drop_duplicates("month").set_index("month")["phase"]
    cc["phase"]=cc["month"].map(phase_map); cc["gap"]=cc["treated"]-cc["control"]
    cc=add_terms(cc)
    cc_fit=hac_fit("gap ~ sin12 + cos12 + anticipation + year1 + year2",cc)

    model_effects=pd.concat([
        effects(primary,"Primary harmonic phase model"),
        effects(month_fe,"Calendar-month FE phase model"),
        effects(trend_harm,"Harmonic plus linear-trend diagnostic"),
        effects(trend_month,"Month-FE plus linear-trend diagnostic"),
        effects(cc_fit,"43-month complete-case sensitivity"),
    ],ignore_index=True)
    model_effects.to_csv(OUTPUT/"model_effects_all_specifications.csv",index=False)

    # Baseline diagnostic.
    baseline=series[series["phase"]=="baseline"].copy()
    baseline["baseline_t"]=np.arange(len(baseline),dtype=float)
    pre=hac_fit("gap_delta ~ baseline_t",baseline)
    ci=pre.conf_int().loc["baseline_t"]
    pd.DataFrame([{
        "baseline_months":len(baseline),
        "differential_slope_ug_m3_per_month":pre.params["baseline_t"],
        "std_error":pre.bse["baseline_t"],"ci95_low":ci[0],"ci95_high":ci[1],
        "p_value":pre.pvalues["baseline_t"],
    }]).to_csv(OUTPUT/"pretrend_gate.csv",index=False)

    # Leave-one-control-out.
    rows=[]
    for dropped in [None]+CONTROLS:
        controls=CONTROLS if dropped is None else [c for c in CONTROLS if c!=dropped]
        s=baseline_centred_series(df,TREATED,controls)
        fit=hac_fit("gap_delta ~ sin12 + cos12 + anticipation + year1 + year2",s)
        ci=fit.conf_int()
        for phase in ["anticipation","year1","year2"]:
            rows.append({
                "panel":"primary" if dropped is None else f"drop_{dropped}",
                "phase":phase,"estimate_ug_m3":fit.params[phase],
                "ci95_low":ci.loc[phase,0],"ci95_high":ci.loc[phase,1],
                "p_value":fit.pvalues[phase],
            })
    pd.DataFrame(rows).to_csv(OUTPUT/"leave_one_control_out.csv",index=False)

    # BY7 sensitivity.
    by7_series=baseline_centred_series(df,["HV1","HV3","BY7"],CONTROLS)
    by7_fit=hac_fit("gap_delta ~ sin12 + cos12 + anticipation + year1 + year2",by7_series)
    by7_out=effects(by7_fit,"BY7 sensitivity")
    by7_out["calendar_months_used"]=len(by7_series)
    by7_out.to_csv(OUTPUT/"by7_sensitivity.csv",index=False)

    # Phase contrasts.
    cov=primary.cov_params(); nd=NormalDist()
    def one(a,b,label):
        est=primary.params[a]-primary.params[b]
        var=cov.loc[a,a]+cov.loc[b,b]-2*cov.loc[a,b]
        se=math.sqrt(var); z=est/se
        return {
            "contrast":label,"estimate_ug_m3":est,"std_error":se,
            "ci95_low":est-1.96*se,"ci95_high":est+1.96*se,
            "p_value":2*(1-nd.cdf(abs(z))),
        }
    pd.DataFrame([
        one("year1","anticipation","Year 1 minus anticipation"),
        one("year2","year1","Year 2 minus Year 1"),
        one("year2","anticipation","Year 2 minus anticipation"),
    ]).to_csv(OUTPUT/"phase_contrasts.csv",index=False)

    series.assign(month=series["month"].dt.strftime("%Y-%m-%d")).to_csv(
        OUTPUT/"primary_baseline_centred_monthly_series.csv",index=False
    )

    # Validation gates for the published snapshot.
    assert len(series)==50
    assert abs(primary.params["year1"] - (-2.181239)) < 0.02
    assert abs(primary.params["year2"] - (-4.074907)) < 0.02
    assert abs(pre.params["baseline_t"]) < 0.02

    # Visual 1.
    fig,ax=plt.subplots(figsize=(10,5))
    ax.plot(series["month"],series["treated"],marker="o",markersize=3,label="Outer-London treated sites")
    ax.plot(series["month"],series["control"],marker="o",markersize=3,label="Comparison sites")
    ax.axhline(0,linewidth=1)
    ax.axvline(pd.Timestamp("2023-01-01"),linestyle="--",linewidth=1)
    ax.axvline(pd.Timestamp("2023-09-01"),linestyle="--",linewidth=1)
    ax.set_ylabel("Change from each site's baseline mean NO₂ (µg/m³)")
    ax.set_xlabel(""); ax.set_title("Roadside NO₂ change relative to each site's baseline")
    ax.legend(); fig.tight_layout(); save_copy(fig,"01_group_change_from_baseline.png"); plt.close(fig)

    # Visual 2.
    fig,ax=plt.subplots(figsize=(10,5))
    ax.plot(series["month"],series["gap_delta"],marker="o",markersize=3)
    ax.axhline(0,linewidth=1)
    ax.axvline(pd.Timestamp("2023-01-01"),linestyle="--",linewidth=1)
    ax.axvline(pd.Timestamp("2023-09-01"),linestyle="--",linewidth=1)
    ax.set_ylabel("Treated minus control change (µg/m³)")
    ax.set_xlabel(""); ax.set_title("Monthly treated-control NO₂ gap")
    fig.tight_layout(); save_copy(fig,"02_treated_control_gap.png"); plt.close(fig)

    # Visual 3.
    prim=model_effects[model_effects["model"]=="Primary harmonic phase model"].set_index("phase")
    trend=model_effects[model_effects["model"]=="Harmonic plus linear-trend diagnostic"].set_index("phase")
    order=["year2","year1","anticipation"]; y=np.arange(len(order))
    labels={"year2":"Year 2","year1":"Year 1","anticipation":"Anticipation"}
    fig,ax=plt.subplots(figsize=(8.5,4.8)); ax.axvline(0,linewidth=1)
    for off,frame,marker,label in [(-0.10,prim,"o","Primary model"),(0.10,trend,"s","Linear-trend diagnostic")]:
        s=frame.loc[order]; x=s["estimate_ug_m3"].to_numpy(); lo=s["ci95_low"].to_numpy(); hi=s["ci95_high"].to_numpy()
        ax.errorbar(x,y+off,xerr=np.vstack([x-lo,hi-x]),fmt=marker,capsize=4,label=label)
    ax.set_yticks(y,[labels[p] for p in order])
    ax.set_xlabel("Change in treated-control NO₂ gap vs baseline (µg/m³)")
    ax.set_title("Phase estimates and model-specification sensitivity")
    ax.legend(); fig.tight_layout(); save_copy(fig,"03_phase_estimates_and_sensitivity.png"); plt.close(fig)

    print(model_effects.round(3).to_string(index=False))


if __name__=="__main__":
    main()
