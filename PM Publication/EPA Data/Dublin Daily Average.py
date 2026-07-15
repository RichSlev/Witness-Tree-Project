# ============================================================
# DUBLIN DAILY PM AVERAGE SCRIPT
#
# Input:
#   EPA_PM_Dublin_selected_QAQC_flags.csv
#
# Outputs:
#   EPA_PM_Dublin_station_daily_values_by_QC_version.csv
#   EPA_PM_Dublin_daily_average_long.csv
#   EPA_PM_Dublin_daily_average_wide.csv
#
# Logic:
#   1. Read QA/QC-flagged Dublin data
#   2. Create three QA/QC versions:
#        all_observed
#        good_only
#        good_plus_suspect
#   3. Collapse method streams to one value per:
#        date + pollutant + station
#   4. Average across stations to create Dublin daily PM estimate
# ============================================================


# ============================================================
# 0. IMPORTS
# ============================================================

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. USER SETTINGS
# ============================================================

QAQC_PATH = Path(
    r"C:/Users/Richa/Documents/Python_Projects/PM_Data_EPA/combined_outputs/EPA_PM_Dublin_selected_QAQC_flags.csv"
)

OUTPUT_DIR = QAQC_PATH.parent

OUTPUT_STATION_DAILY_PATH = OUTPUT_DIR / "EPA_PM_Dublin_station_daily_values_by_QC_version.csv"
OUTPUT_DUBLIN_DAILY_LONG_PATH = OUTPUT_DIR / "EPA_PM_Dublin_daily_average_long.csv"
OUTPUT_DUBLIN_DAILY_WIDE_PATH = OUTPUT_DIR / "EPA_PM_Dublin_daily_average_wide.csv"

SAVE_OUTPUTS = True
PLOT_DUBLIN_AVERAGES = True

# Minimum number of stations needed before treating a Dublin daily mean
# as reasonably representative. This does not delete data. It only flags days.
MIN_STATIONS_FOR_DUBLIN_AVERAGE = 3


# ============================================================
# 2. LOAD DATA
# ============================================================

if not QAQC_PATH.exists():
    raise FileNotFoundError(f"Could not find QA/QC file:\n{QAQC_PATH}")

qa_df = pd.read_csv(QAQC_PATH)

required_cols = [
    "date",
    "year",
    "pollutant",
    "station",
    "concentration_ug_m3",
    "qc_status"
]

missing_cols = [col for col in required_cols if col not in qa_df.columns]

if missing_cols:
    raise ValueError(
        "The QA/QC file is missing required columns:\n"
        f"{missing_cols}"
    )

qa_df["date"] = pd.to_datetime(qa_df["date"], errors="coerce")
qa_df["year"] = qa_df["date"].dt.year
qa_df["concentration_ug_m3"] = pd.to_numeric(
    qa_df["concentration_ug_m3"],
    errors="coerce"
)

qa_df["pollutant"] = qa_df["pollutant"].astype(str).str.strip()
qa_df["station"] = qa_df["station"].astype(str).str.strip()
qa_df["qc_status"] = qa_df["qc_status"].astype(str).str.strip()

# Some older QA/QC outputs may not yet preserve method_stream.
# If missing, create a placeholder so the script still works.
if "method_stream" not in qa_df.columns:
    qa_df["method_stream"] = "unlabelled"

qa_df["method_stream"] = qa_df["method_stream"].fillna("unlabelled").astype(str)

qa_df = qa_df.dropna(subset=["date", "pollutant", "station"]).copy()

print("\nLoaded QA/QC Dublin data:")
print("Rows:", qa_df.shape[0])
print("Stations:", qa_df["station"].nunique())
print("Pollutants:", sorted(qa_df["pollutant"].unique()))
print("Date range:", qa_df["date"].min(), "to", qa_df["date"].max())

print("\nQC status counts:")
print(qa_df["qc_status"].value_counts(dropna=False).to_string())


# ============================================================
# 3. EXPECTED STATION COVERAGE BY DATE AND POLLUTANT
# ============================================================

# Because qa_df includes internal missing-date rows, this gives the number
# of stations expected on each date and pollutant, based on each station's
# active date range.

expected_station_counts = (
    qa_df
    .groupby(["date", "year", "pollutant"])
    .agg(
        n_stations_expected=("station", "nunique")
    )
    .reset_index()
)


# ============================================================
# 4. CREATE QC VERSION FILTERS
# ============================================================

qa_df["is_observed"] = (
    qa_df["concentration_ug_m3"].notna()
    & (qa_df["qc_status"] != "missing")
)

version_filters = {
    "all_observed": (
        qa_df["is_observed"]
    ),
    "good_only": (
        qa_df["is_observed"]
        & (qa_df["qc_status"] == "good")
    ),
    "good_plus_suspect": (
        qa_df["is_observed"]
        & (qa_df["qc_status"].isin(["good", "suspect"]))
    )
}


# ============================================================
# 5. COLLAPSE METHOD STREAMS TO STATION-DAY VALUES
# ============================================================

station_daily_frames = []

for version_name, version_mask in version_filters.items():

    version_df = qa_df[version_mask].copy()

    if version_df.empty:
        print(f"\nNo records found for version: {version_name}")
        continue

    station_daily = (
        version_df
        .groupby(["date", "year", "pollutant", "station"], as_index=False)
        .agg(
            station_daily_mean_pm=("concentration_ug_m3", "mean"),
            station_daily_median_pm=("concentration_ug_m3", "median"),
            station_daily_min_pm=("concentration_ug_m3", "min"),
            station_daily_max_pm=("concentration_ug_m3", "max"),
            n_records_used=("concentration_ug_m3", "count"),
            n_method_streams_used=("method_stream", "nunique"),
            method_streams_used=("method_stream", lambda x: " | ".join(sorted(set(x)))),
            qc_statuses_used=("qc_status", lambda x: " | ".join(sorted(set(x))))
        )
    )

    station_daily["method_stream_range_pm"] = (
        station_daily["station_daily_max_pm"]
        - station_daily["station_daily_min_pm"]
    )

    station_daily["qc_version"] = version_name

    station_daily_frames.append(station_daily)


station_daily_all_versions = pd.concat(
    station_daily_frames,
    ignore_index=True
)

station_daily_all_versions = station_daily_all_versions.sort_values(
    ["qc_version", "pollutant", "station", "date"]
).reset_index(drop=True)

print("\nStation-day values created:")
print("Rows:", station_daily_all_versions.shape[0])
print("QC versions:", sorted(station_daily_all_versions["qc_version"].unique()))


# ============================================================
# 6. METHOD-STREAM OVERLAP DIAGNOSTIC
# ============================================================

method_overlap_station_days = (
    station_daily_all_versions[
        station_daily_all_versions["n_method_streams_used"] > 1
    ]
    .copy()
    .sort_values(
        ["qc_version", "pollutant", "station", "date"]
    )
)

print("\nStation-days with multiple method streams used:")
print(method_overlap_station_days.shape[0])

if not method_overlap_station_days.empty:
    print(method_overlap_station_days.head(30).to_string(index=False))


# ============================================================
# 7. CALCULATE DUBLIN DAILY AVERAGE ACROSS STATIONS
# ============================================================

dublin_daily_average = (
    station_daily_all_versions
    .groupby(["qc_version", "date", "year", "pollutant"], as_index=False)
    .agg(
        mean_dublin_pm=("station_daily_mean_pm", "mean"),
        median_dublin_pm=("station_daily_mean_pm", "median"),
        sd_between_stations_pm=("station_daily_mean_pm", "std"),
        min_station_pm=("station_daily_mean_pm", "min"),
        max_station_pm=("station_daily_mean_pm", "max"),
        n_stations_used=("station", "nunique"),
        stations_used=("station", lambda x: " | ".join(sorted(set(x)))),
        n_station_days_with_multiple_method_streams=(
            "n_method_streams_used",
            lambda x: int((x > 1).sum())
        ),
        max_method_stream_range_pm=("method_stream_range_pm", "max")
    )
)

dublin_daily_average = dublin_daily_average.merge(
    expected_station_counts,
    on=["date", "year", "pollutant"],
    how="left"
)

dublin_daily_average["percent_station_coverage"] = (
    100
    * dublin_daily_average["n_stations_used"]
    / dublin_daily_average["n_stations_expected"]
)

dublin_daily_average["meets_min_station_threshold"] = (
    dublin_daily_average["n_stations_used"]
    >= MIN_STATIONS_FOR_DUBLIN_AVERAGE
)

dublin_daily_average = dublin_daily_average.sort_values(
    ["pollutant", "date", "qc_version"]
).reset_index(drop=True)

print("\nDublin daily average created:")
print("Rows:", dublin_daily_average.shape[0])

print("\nDublin daily average summary by version and pollutant:")
summary = (
    dublin_daily_average
    .groupby(["qc_version", "pollutant"])
    .agg(
        n_days=("date", "nunique"),
        mean_n_stations_used=("n_stations_used", "mean"),
        min_n_stations_used=("n_stations_used", "min"),
        max_n_stations_used=("n_stations_used", "max"),
        mean_station_coverage=("percent_station_coverage", "mean"),
        mean_dublin_pm_over_period=("mean_dublin_pm", "mean"),
        median_dublin_pm_over_period=("mean_dublin_pm", "median"),
        max_dublin_pm_over_period=("mean_dublin_pm", "max")
    )
    .reset_index()
)

print(summary.to_string(index=False))


# ============================================================
# 8. WIDE VERSION FOR EASIER COMPARISON
# ============================================================

dublin_daily_wide = (
    dublin_daily_average
    .pivot_table(
        index=["date", "year", "pollutant"],
        columns="qc_version",
        values=[
            "mean_dublin_pm",
            "median_dublin_pm",
            "n_stations_used",
            "percent_station_coverage"
        ],
        aggfunc="first"
    )
)

dublin_daily_wide.columns = [
    f"{metric}_{version}"
    for metric, version in dublin_daily_wide.columns
]

dublin_daily_wide = dublin_daily_wide.reset_index()

dublin_daily_wide = dublin_daily_wide.sort_values(
    ["pollutant", "date"]
).reset_index(drop=True)


# ============================================================
# 9. SAVE OUTPUTS
# ============================================================

if SAVE_OUTPUTS:
    station_daily_all_versions.to_csv(
        OUTPUT_STATION_DAILY_PATH,
        index=False
    )

    dublin_daily_average.to_csv(
        OUTPUT_DUBLIN_DAILY_LONG_PATH,
        index=False
    )

    dublin_daily_wide.to_csv(
        OUTPUT_DUBLIN_DAILY_WIDE_PATH,
        index=False
    )

    print("\nStation daily values written to:")
    print(OUTPUT_STATION_DAILY_PATH)

    print("\nDublin daily average long file written to:")
    print(OUTPUT_DUBLIN_DAILY_LONG_PATH)

    print("\nDublin daily average wide file written to:")
    print(OUTPUT_DUBLIN_DAILY_WIDE_PATH)


# ============================================================
# 10. PLOTS
# ============================================================

def plot_dublin_average(df, pollutant):
    """
    Plot Dublin daily average for one pollutant across QA/QC versions.
    """
    plot_df = df[df["pollutant"] == pollutant].copy()

    if plot_df.empty:
        print(f"No Dublin average found for {pollutant}")
        return

    plt.figure(figsize=(16, 7))

    for version_name, version_df in plot_df.groupby("qc_version"):
        version_df = version_df.sort_values("date")

        plt.plot(
            version_df["date"],
            version_df["mean_dublin_pm"],
            linewidth=1.1,
            alpha=0.85,
            label=version_name
        )

    plt.title(f"Dublin daily average {pollutant}")
    plt.xlabel("Date")
    plt.ylabel("Dublin average concentration (µg/m³)")
    plt.grid(True, alpha=0.3)
    plt.legend(title="QA/QC version")
    plt.tight_layout()
    plt.show()


def plot_station_count_used(df, pollutant):
    """
    Plot number of stations contributing to the Dublin average.
    """
    plot_df = df[
        (df["pollutant"] == pollutant)
        & (df["qc_version"] == "good_plus_suspect")
    ].copy()

    if plot_df.empty:
        print(f"No station count data found for {pollutant}")
        return

    plt.figure(figsize=(16, 5))

    plt.plot(
        plot_df["date"],
        plot_df["n_stations_used"],
        linewidth=1.1,
        label="Stations used"
    )

    plt.plot(
        plot_df["date"],
        plot_df["n_stations_expected"],
        linewidth=1.1,
        linestyle="--",
        label="Stations expected"
    )

    plt.title(f"Number of Dublin stations contributing to {pollutant} average")
    plt.xlabel("Date")
    plt.ylabel("Number of stations")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


if PLOT_DUBLIN_AVERAGES:
    plot_dublin_average(dublin_daily_average, "PM2.5")
    plot_dublin_average(dublin_daily_average, "PM10")

    plot_station_count_used(dublin_daily_average, "PM2.5")
    plot_station_count_used(dublin_daily_average, "PM10")


print("\nDone.")
