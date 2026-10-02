from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


STUDY_START = pd.Timestamp("2021-07-01", tz="UTC")
STUDY_END_EXCLUSIVE = pd.Timestamp("2025-09-01", tz="UTC")
MONTHLY_CAPTURE_THRESHOLD = 0.75

PHASE_RULES = {
    "overall": 45,
    "baseline": 16,
    "anticipation": 7,
    "year1": 11,
    "year2": 11,
}

# Final primary sites plus BY7, which is retained only for sensitivity analysis.
SITES = [
    {"site_code":"HV1","site_name":"Havering - Rainham","group":"treated","source":"laqn"},
    {"site_code":"HV3","site_name":"Havering - Romford","group":"treated","source":"laqn"},
    {"site_code":"BY7","site_name":"Bromley - Harwood Avenue","group":"treated","source":"laqn"},
    {"site_code":"LEIR","site_name":"Leicester A594 Roadside","group":"control","source":"aurn"},
    {"site_code":"DCST","site_name":"Doncaster A630 Cleveland Street","group":"control","source":"aurn"},
    {"site_code":"BLAR","site_name":"Blackburn Accrington Road","group":"control","source":"aurn"},
]

OUTPUT_DIR = Path("data/processed")


@dataclass
class FetchRecord:
    site_code: str
    source: str
    url: str
    status: str
    rows: int = 0
    note: str = ""


def http_get(url: str, timeout: int = 120, retries: int = 4) -> bytes:
    headers = {
        "User-Agent":"Mozilla/5.0 (compatible; RA02-data-analysis/1.0)",
        "Accept":"application/json,text/csv,text/plain,*/*",
    }
    last_error = None
    for attempt in range(1, retries+1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 ** (attempt-1))
    raise RuntimeError(f"Failed after {retries} attempts: {url}\n{last_error}")


def decode_csv(raw: bytes) -> str:
    for encoding in ("utf-8-sig","utf-8","latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("Could not decode CSV")


def find_column(columns, exact: str):
    for col in columns:
        if str(col).strip().lower() == exact.lower():
            return col
    return None


def parse_aurn_csv(raw: bytes, site_code: str) -> pd.DataFrame:
    frame = pd.read_csv(io.StringIO(decode_csv(raw)), skiprows=4, low_memory=False)
    date_col = find_column(frame.columns, "date")
    time_col = find_column(frame.columns, "time")
    no2_col = find_column(frame.columns, "nitrogen dioxide")
    if date_col is None or time_col is None or no2_col is None:
        raise ValueError(f"Unexpected AURN columns for {site_code}: {list(frame.columns)}")

    dates = pd.to_datetime(frame[date_col], dayfirst=True, errors="coerce")
    hours = pd.to_numeric(
        frame[time_col].astype(str).str.extract(r"^(\d{1,2})", expand=False),
        errors="coerce",
    )
    # UK-AIR column files use hour-ending timestamps.
    ts = dates + pd.to_timedelta(hours, unit="h") - pd.Timedelta(hours=1)
    ts = pd.DatetimeIndex(ts).tz_localize("UTC", ambiguous="NaT", nonexistent="NaT")
    values = pd.to_numeric(frame[no2_col], errors="coerce")

    out = pd.DataFrame({"timestamp":ts,"no2":values.to_numpy(),"site_code":site_code})
    out = out.dropna(subset=["timestamp"]).drop_duplicates("timestamp", keep="last")
    return out[(out["timestamp"]>=STUDY_START)&(out["timestamp"]<STUDY_END_EXCLUSIVE)].sort_values("timestamp")


def fetch_aurn_site(site_code: str, log: list[FetchRecord]) -> pd.DataFrame:
    frames=[]
    for year in range(2021,2026):
        urls=[
            f"https://uk-air.defra.gov.uk/datastore/data_files/site_data/{site_code}_{year}.csv",
            f"https://uk-air.defra.gov.uk/data_files/site_data/{site_code}_{year}.csv",
        ]
        last_error=None
        for url in urls:
            try:
                raw=http_get(url)
                frame=parse_aurn_csv(raw,site_code)
                frames.append(frame)
                log.append(FetchRecord(site_code,"AURN",url,"ok",len(frame),"hourly NO2"))
                break
            except Exception as exc:
                last_error=exc
        else:
            raise RuntimeError(f"Could not download {site_code} {year}: {last_error}")
    return pd.concat(frames,ignore_index=True).drop_duplicates("timestamp",keep="last").sort_values("timestamp")


def parse_laqn_json(raw: bytes, site_code: str) -> pd.DataFrame:
    payload=json.loads(raw.decode("utf-8-sig"))
    data=payload.get("RawAQData",{}).get("Data",[])
    if isinstance(data,dict):
        data=[data]
    rows=[{
        "timestamp":x.get("@MeasurementDateGMT"),
        "no2":x.get("@Value"),
        "site_code":site_code,
    } for x in (data or [])]
    frame=pd.DataFrame(rows,columns=["timestamp","no2","site_code"])
    if frame.empty:
        return frame
    frame["timestamp"]=pd.to_datetime(frame["timestamp"],errors="coerce",utc=True)
    frame["no2"]=pd.to_numeric(frame["no2"],errors="coerce")
    frame=frame.dropna(subset=["timestamp"]).drop_duplicates("timestamp",keep="last")
    return frame[(frame["timestamp"]>=STUDY_START)&(frame["timestamp"]<STUDY_END_EXCLUSIVE)].sort_values("timestamp")


def fetch_laqn_site(site_code: str, log: list[FetchRecord]) -> pd.DataFrame:
    frames=[]
    current=STUDY_START
    while current<STUDY_END_EXCLUSIVE:
        nxt=min(current+pd.Timedelta(days=180),STUDY_END_EXCLUSIVE)
        start=current.strftime("%Y-%m-%d")
        end=nxt.strftime("%Y-%m-%d")
        url=(
            "https://api.erg.ic.ac.uk/AirQuality/Data/SiteSpecies/"
            f"SiteCode={site_code}/SpeciesCode=NO2/StartDate={start}/EndDate={end}/Json"
        )
        raw=http_get(url)
        frame=parse_laqn_json(raw,site_code)
        frames.append(frame)
        log.append(FetchRecord(site_code,"LAQN",url,"ok",len(frame),"hourly NO2; GMT"))
        current=nxt
    return pd.concat(frames,ignore_index=True).drop_duplicates("timestamp",keep="last").sort_values("timestamp")


def phase_for_month(month: pd.Period) -> str:
    if pd.Period("2021-07","M") <= month <= pd.Period("2022-12","M"):
        return "baseline"
    if pd.Period("2023-01","M") <= month <= pd.Period("2023-08","M"):
        return "anticipation"
    if pd.Period("2023-09","M") <= month <= pd.Period("2024-08","M"):
        return "year1"
    if pd.Period("2024-09","M") <= month <= pd.Period("2025-08","M"):
        return "year2"
    raise ValueError(month)


def expected_hours(month: pd.Period) -> int:
    start=month.start_time.tz_localize("UTC")
    end=(month+1).start_time.tz_localize("UTC")
    return int((end-start).total_seconds()//3600)


def build_monthly(hourly: pd.DataFrame, site: dict) -> pd.DataFrame:
    months=pd.period_range("2021-07","2025-08",freq="M")
    temp=hourly.copy()
    temp["month"]=temp["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).dt.to_period("M")
    grouped=temp.groupby("month")["no2"].agg(["mean","count"]).rename(
        columns={"mean":"raw_mean_no2","count":"valid_hours"}
    )

    rows=[]
    for month in months:
        exp=expected_hours(month)
        valid=int(grouped.loc[month,"valid_hours"]) if month in grouped.index else 0
        raw_mean=float(grouped.loc[month,"raw_mean_no2"]) if valid else np.nan
        capture=valid/exp
        valid_month=capture>=MONTHLY_CAPTURE_THRESHOLD
        rows.append({
            "site_code":site["site_code"],"site_name":site["site_name"],
            "group":site["group"],"source":site["source"],"month":month.start_time.date().isoformat(),
            "phase":phase_for_month(month),"expected_hours":exp,"valid_hours":valid,
            "capture_rate":capture,"valid_month":valid_month,
            "no2_ug_m3":raw_mean if valid_month else np.nan,
            "raw_mean_no2_ug_m3":raw_mean,
        })
    return pd.DataFrame(rows)


def retention_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for code,g in monthly.groupby("site_code"):
        first=g.iloc[0]
        c={p:int(g.loc[g["phase"]==p,"valid_month"].sum()) for p in ["baseline","anticipation","year1","year2"]}
        overall=int(g["valid_month"].sum())
        retained=(overall>=45 and c["baseline"]>=16 and c["anticipation"]>=7 and c["year1"]>=11 and c["year2"]>=11)
        rows.append({
            "site_code":code,"site_name":first["site_name"],"group":first["group"],
            "valid_months_overall":overall,"valid_baseline":c["baseline"],
            "valid_anticipation":c["anticipation"],"valid_year1":c["year1"],
            "valid_year2":c["year2"],"retained_by_coverage_rule":retained,
        })
    return pd.DataFrame(rows).sort_values(["group","site_code"])


def main():
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    log=[]
    monthly=[]
    for site in SITES:
        print(f"{site['site_code']:5s} {site['site_name']}")
        hourly=fetch_laqn_site(site["site_code"],log) if site["source"]=="laqn" else fetch_aurn_site(site["site_code"],log)
        monthly.append(build_monthly(hourly,site))

    panel=pd.concat(monthly,ignore_index=True)
    retention=retention_summary(panel)

    # Fixed analysis decisions from the pre-result screening:
    assert bool(retention.loc[retention.site_code=="HV1","retained_by_coverage_rule"].iloc[0])
    assert bool(retention.loc[retention.site_code=="HV3","retained_by_coverage_rule"].iloc[0])
    assert not bool(retention.loc[retention.site_code=="BY7","retained_by_coverage_rule"].iloc[0])

    panel_path=OUTPUT_DIR/"monthly_panel.csv"
    panel.to_csv(panel_path,index=False)
    retention.to_csv(OUTPUT_DIR/"site_retention_summary.csv",index=False)
    pd.DataFrame([asdict(x) for x in log]).to_csv(OUTPUT_DIR/"download_log.csv",index=False)

    panel_sha256=hashlib.sha256(panel_path.read_bytes()).hexdigest()

    metadata={
        "retrieved_utc":datetime.now(timezone.utc).isoformat(),
        "study_window":"2021-07 to 2025-08",
        "monthly_capture_threshold":MONTHLY_CAPTURE_THRESHOLD,
        "phase_rules":PHASE_RULES,
        "processed_monthly_panel_sha256":panel_sha256,
    }
    (OUTPUT_DIR/"source_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")

    print("\nCoverage summary")
    print(retention.to_string(index=False))


if __name__=="__main__":
    main()
