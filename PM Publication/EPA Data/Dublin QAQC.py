# ============================================================
# STANDALONE QA/QC SCRIPT
# EPA PM2.5 AND PM10 DAILY DATA
# Selected Dublin stations only
#
# Input:
#   EPA_PM_Dublin_selected_daily_long_2020_2024.csv
#
# Outputs:
#   EPA_PM_Dublin_selected_QAQC_flags.csv
#   EPA_PM_Dublin_selected_QAQC_good_only.csv
#   EPA_PM_Dublin_selected_QAQC_observed_only.csv
#   EPA_PM_Dublin_selected_QAQC_status_summary.csv
#   EPA_PM_Dublin_selected_QAQC_flag_summary.csv
#
# Notes:
#   This script does NOT redo station selection.
#   It only performs QA/QC on the already-created Dublin-selected dataset.
#
# QA/QC status logic:
#   good    = observed and passes all QA/QC checks
#   suspect = observed but questionable
#   bad     = observed and physically/technically invalid
#   missing = expected internal date but no concentration value
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

DUBLIN_DATA_PATH = Path(
    r"C:/Users/Richa/Documents/Python_Projects/PM_Data_EPA/combined_outputs/EPA_PM_Dublin_selected_daily_long_2020_2024.csv"
)

OUTPUT_DIR = DUBLIN_DATA_PATH.parent

OUTPUT_QAQC_PATH = OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_flags.csv"
OUTPUT_GOOD_ONLY_PATH = OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_good_only.csv"
OUTPUT_OBSERVED_ONLY_PATH = OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_observed_only.csv"
OUTPUT_QAQC_STATUS_SUMMARY_PATH = OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_status_summary.csv"
OUTPUT_QAQC_FLAG_SUMMARY_PATH = OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_flag_summary.csv"

SAVE_OUTPUTS = True
PLOT_QAQC = True
SHOW_LEGEND = True


# ============================================================
# 2. QA/QC SETTINGS
# ============================================================

# These are screening thresholds, not automatic deletion rules.
# Anything flagged should be inspected before final exclusion.

ABSOLUTE_LIMITS = {
    "PM2.5": {
        "negative_bad": 0,
        "high_suspect": 100,
        "extreme_bad": 500
    },
    "PM10": {
        "negative_bad": 0,
        "high_suspect": 200,
        "extreme_bad": 1000
    }
}

# Rolling local anomaly detection
ROLLING_WINDOW_DAYS = 31
ROLLING_MIN_PERIODS = 10
ROBUST_Z_SUSPECT = 8

# Isolated spike detection
ISOLATED_SPIKE_RATIO = 3

ISOLATED_SPIKE_MIN_INCREASE = {
    "PM2.5": 25,
    "PM10": 40
}

# Flatline detection
REPEATED_VALUE_RUN_DAYS = 5

# PM2.5 should generally not exceed PM10 for the same station/date.
# A tolerance avoids flagging tiny rounding differences.
PM25_GT_PM10_TOLERANCE = 2.0


# ============================================================
# 3. CONSISTENT QA/QC COLOURS
# ============================================================

QC_COLORS = {
    "good": "lightgrey",
    "suspect": "orange",
    "bad": "red",
    "missing": "purple"
}


# ============================================================
# 4. LOAD DUBLIN SELECTED DATASET
# ============================================================

if not DUBLIN_DATA_PATH.exists():
    raise FileNotFoundError(
        "\nDublin selected dataset not found:\n"
        f"{DUBLIN_DATA_PATH}\n\n"
        "This QA/QC script expects the final Dublin-selected dataset to already exist.\n"
        "Add this to the end of your Dublin-selection script and run it once:\n\n"
        "DUBLIN_SELECTED_OUTPUT_PATH = DATA_PATH.parent / "
        "\"EPA_PM_Dublin_selected_daily_long_2020_2024.csv\"\n"
        "pm_df.to_csv(DUBLIN_SELECTED_OUTPUT_PATH, index=False)\n"
        "print(DUBLIN_SELECTED_OUTPUT_PATH)\n"
    )

pm_df = pd.read_csv(DUBLIN_DATA_PATH)

required_cols = [
    "date",
    "year",
    "pollutant",
    "station",
    "concentration_ug_m3"
]

missing_cols = [col for col in required_cols if col not in pm_df.columns]

if missing_cols:
    raise ValueError(
        "\nThe Dublin selected dataset is missing required columns:\n"
        f"{missing_cols}\n\n"
        "Expected columns are:\n"
        f"{required_cols}"
    )

pm_df["date"] = pd.to_datetime(pm_df["date"], errors="coerce")
pm_df["year"] = pd.to_numeric(pm_df["year"], errors="coerce")
pm_df["concentration_ug_m3"] = pd.to_numeric(
    pm_df["concentration_ug_m3"],
    errors="coerce"
)

pm_df["pollutant"] = pm_df["pollutant"].astype(str).str.strip()
pm_df["station"] = pm_df["station"].astype(str).str.strip()

pm_df = pm_df.dropna(subset=["date", "pollutant", "station"]).copy()

pm_df = pm_df.sort_values(["station", "pollutant", "date"]).reset_index(drop=True)

print("\nLoaded Dublin selected dataset:")
print("Rows:", pm_df.shape[0])
print("Stations:", pm_df["station"].nunique())
print("Pollutants:", sorted(pm_df["pollutant"].unique()))
print("Date range:", pm_df["date"].min(), "to", pm_df["date"].max())


# ============================================================
# 5. BASIC DUPLICATE CHECK
# ============================================================

duplicate_check = (
    pm_df
    .groupby(["date", "pollutant", "station"])
    .size()
    .reset_index(name="n_records")
)

n_duplicate_rows = int((duplicate_check["n_records"] > 1).sum())

print("\nDuplicate station-date-pollutant combinations:")
print(n_duplicate_rows)

if n_duplicate_rows > 0:
    print("\nCollapsing duplicates by mean concentration.")

    pm_df = (
        pm_df
        .groupby(["date", "year", "pollutant", "station"], as_index=False)
        .agg(
            concentration_ug_m3=("concentration_ug_m3", "mean"),
            n_values_combined_qaqc=("concentration_ug_m3", "count")
        )
    )

else:
    if "n_values_combined" not in pm_df.columns:
        pm_df["n_values_combined"] = 1


# ============================================================
# 6. CREATE INTERNAL DAILY DATE GRID
# ============================================================

grid_frames = []

for (station, pollutant), group in pm_df.groupby(["station", "pollutant"]):
    group = group.sort_values("date").copy()

    full_dates = pd.date_range(
        start=group["date"].min(),
        end=group["date"].max(),
        freq="D"
    )

    grid = pd.DataFrame({
        "date": full_dates,
        "station": station,
        "pollutant": pollutant
    })

    grid = grid.merge(
        group,
        on=["date", "station", "pollutant"],
        how="left"
    )

    grid["year"] = grid["date"].dt.year

    grid_frames.append(grid)

qa_df = pd.concat(grid_frames, ignore_index=True)

qa_df = qa_df.sort_values(["station", "pollutant", "date"]).reset_index(drop=True)

qa_df["flag_missing_internal_date"] = qa_df["concentration_ug_m3"].isna()

print("\nAfter adding internal missing-date rows:")
print("Rows:", qa_df.shape[0])
print("Internal missing records:", int(qa_df["flag_missing_internal_date"].sum()))


# ============================================================
# 7. ABSOLUTE VALUE FLAGS
# ============================================================

qa_df["flag_negative_or_invalid"] = False
qa_df["flag_high_suspect_absolute"] = False
qa_df["flag_extreme_bad_absolute"] = False

for pollutant, limits in ABSOLUTE_LIMITS.items():
    mask_pollutant = qa_df["pollutant"] == pollutant

    qa_df.loc[
        mask_pollutant
        & qa_df["concentration_ug_m3"].notna()
        & (qa_df["concentration_ug_m3"] < limits["negative_bad"]),
        "flag_negative_or_invalid"
    ] = True

    qa_df.loc[
        mask_pollutant
        & qa_df["concentration_ug_m3"].notna()
        & (qa_df["concentration_ug_m3"] > limits["high_suspect"]),
        "flag_high_suspect_absolute"
    ] = True

    qa_df.loc[
        mask_pollutant
        & qa_df["concentration_ug_m3"].notna()
        & (qa_df["concentration_ug_m3"] > limits["extreme_bad"]),
        "flag_extreme_bad_absolute"
    ] = True


# ============================================================
# 8. ROLLING MEDIAN AND ROBUST Z-SCORE FLAGS
# ============================================================

def rolling_mad(x):
    """
    Median absolute deviation for a rolling window.
    """
    median_x = np.nanmedian(x)
    return np.nanmedian(np.abs(x - median_x))


qa_df["rolling_median"] = (
    qa_df
    .groupby(["station", "pollutant"])["concentration_ug_m3"]
    .transform(
        lambda x: x.rolling(
            window=ROLLING_WINDOW_DAYS,
            min_periods=ROLLING_MIN_PERIODS,
            center=True
        ).median()
    )
)

qa_df["rolling_mad"] = (
    qa_df
    .groupby(["station", "pollutant"])["concentration_ug_m3"]
    .transform(
        lambda x: x.rolling(
            window=ROLLING_WINDOW_DAYS,
            min_periods=ROLLING_MIN_PERIODS,
            center=True
        ).apply(rolling_mad, raw=True)
    )
)

qa_df["robust_z"] = np.nan

valid_mad = qa_df["rolling_mad"] > 0

qa_df.loc[valid_mad, "robust_z"] = (
    0.6745
    * (
        qa_df.loc[valid_mad, "concentration_ug_m3"]
        - qa_df.loc[valid_mad, "rolling_median"]
    )
    / qa_df.loc[valid_mad, "rolling_mad"]
)

qa_df["flag_local_spike_robust_z"] = qa_df["robust_z"] > ROBUST_Z_SUSPECT


# ============================================================
# 9. ISOLATED SPIKE FLAGS
# ============================================================

qa_df["previous_value"] = (
    qa_df
    .groupby(["station", "pollutant"])["concentration_ug_m3"]
    .shift(1)
)

qa_df["next_value"] = (
    qa_df
    .groupby(["station", "pollutant"])["concentration_ug_m3"]
    .shift(-1)
)

qa_df["neighbour_mean"] = qa_df[["previous_value", "next_value"]].mean(axis=1)

qa_df["flag_isolated_spike"] = False

for pollutant, min_increase in ISOLATED_SPIKE_MIN_INCREASE.items():
    mask_pollutant = qa_df["pollutant"] == pollutant

    qa_df.loc[
        mask_pollutant
        & qa_df["concentration_ug_m3"].notna()
        & qa_df["previous_value"].notna()
        & qa_df["next_value"].notna()
        & qa_df["neighbour_mean"].notna()
        & (qa_df["concentration_ug_m3"] >= qa_df["neighbour_mean"] * ISOLATED_SPIKE_RATIO)
        & ((qa_df["concentration_ug_m3"] - qa_df["neighbour_mean"]) >= min_increase),
        "flag_isolated_spike"
    ] = True


# ============================================================
# 10. REPEATED VALUE / FLATLINE FLAGS
# ============================================================

flatline_frames = []

for (station, pollutant), group in qa_df.groupby(["station", "pollutant"]):
    group = group.sort_values("date").copy()

    value = group["concentration_ug_m3"]

    run_id = (
        (value != value.shift(1))
        | value.isna()
        | value.shift(1).isna()
    ).cumsum()

    run_length = value.groupby(run_id).transform("size")

    group["repeated_value_run_length"] = run_length

    group["flag_repeated_value_run"] = (
        value.notna()
        & (run_length >= REPEATED_VALUE_RUN_DAYS)
    )

    flatline_frames.append(group)

qa_df = pd.concat(flatline_frames, ignore_index=True)
qa_df = qa_df.sort_values(["station", "pollutant", "date"]).reset_index(drop=True)


# ============================================================
# 11. PM2.5 GREATER THAN PM10 CONSISTENCY FLAG
# ============================================================

wide_pm = (
    qa_df
    .pivot_table(
        index=["date", "station"],
        columns="pollutant",
        values="concentration_ug_m3",
        aggfunc="mean"
    )
    .reset_index()
)

wide_pm["flag_pm25_gt_pm10"] = False

if "PM2.5" in wide_pm.columns and "PM10" in wide_pm.columns:
    wide_pm["flag_pm25_gt_pm10"] = (
        wide_pm["PM2.5"].notna()
        & wide_pm["PM10"].notna()
        & (wide_pm["PM2.5"] > wide_pm["PM10"] + PM25_GT_PM10_TOLERANCE)
    )

pm25_gt_pm10_flags = wide_pm[["date", "station", "flag_pm25_gt_pm10"]].copy()

qa_df = qa_df.merge(
    pm25_gt_pm10_flags,
    on=["date", "station"],
    how="left"
)

qa_df["flag_pm25_gt_pm10"] = qa_df["flag_pm25_gt_pm10"].fillna(False)


# ============================================================
# 12. FINAL QA/QC STATUS
# ============================================================

missing_flags = [
    "flag_missing_internal_date"
]

bad_flags = [
    "flag_negative_or_invalid",
    "flag_extreme_bad_absolute"
]

suspect_flags = [
    "flag_high_suspect_absolute",
    "flag_local_spike_robust_z",
    "flag_isolated_spike",
    "flag_repeated_value_run",
    "flag_pm25_gt_pm10"
]

all_flag_cols = missing_flags + bad_flags + suspect_flags

qa_df["qc_missing"] = qa_df[missing_flags].any(axis=1)
qa_df["qc_bad"] = qa_df[bad_flags].any(axis=1)
qa_df["qc_suspect"] = qa_df[suspect_flags].any(axis=1)

qa_df["qc_status"] = "good"

# Order matters.
# Missing is a data-completeness category, not an observed concentration-quality category.
qa_df.loc[qa_df["qc_suspect"], "qc_status"] = "suspect"
qa_df.loc[qa_df["qc_bad"], "qc_status"] = "bad"
qa_df.loc[qa_df["qc_missing"], "qc_status"] = "missing"

qa_df["qc_flag_any"] = qa_df["qc_status"] != "good"

qa_df["qc_flag_reasons"] = ""

for col in all_flag_cols:
    reason = col.replace("flag_", "")
    qa_df.loc[qa_df[col], "qc_flag_reasons"] += reason + "; "

qa_df["qc_flag_reasons"] = qa_df["qc_flag_reasons"].str.strip("; ")


# ============================================================
# 13. CLEAN-ONLY AND OBSERVED-ONLY DATASETS
# ============================================================

qa_good_df = qa_df[qa_df["qc_status"] == "good"].copy()

# Observed-only keeps good, suspect, and bad observed values.
# It removes missing internal dates because those have no concentration value.
qa_observed_df = qa_df[qa_df["qc_status"] != "missing"].copy()


# ============================================================
# 14. SUMMARY TABLES
# ============================================================

qc_status_summary = (
    qa_df
    .groupby(["pollutant", "station", "qc_status"])
    .size()
    .reset_index(name="n_days")
    .sort_values(["pollutant", "station", "qc_status"])
)

flag_summary_list = []

for col in all_flag_cols:
    temp = (
        qa_df
        .groupby(["pollutant", "station"])[col]
        .sum()
        .reset_index(name="n_flagged")
    )

    temp["flag"] = col
    flag_summary_list.append(temp)

qc_flag_summary = pd.concat(flag_summary_list, ignore_index=True)

qc_flag_summary = (
    qc_flag_summary
    .query("n_flagged > 0")
    .sort_values(["pollutant", "station", "flag"])
)

print("\nQA/QC status summary:")
print(qc_status_summary.to_string(index=False))

print("\nQA/QC flag summary:")
if qc_flag_summary.empty:
    print("No QA/QC flags found.")
else:
    print(qc_flag_summary.to_string(index=False))

print("\nFinal QA/QC row counts:")
print("Full QA/QC dataset:", qa_df.shape[0])
print("Observed-only dataset:", qa_observed_df.shape[0])
print("Good-only dataset:", qa_good_df.shape[0])
print("Good rows:", int((qa_df["qc_status"] == "good").sum()))
print("Suspect rows:", int((qa_df["qc_status"] == "suspect").sum()))
print("Bad observed rows:", int((qa_df["qc_status"] == "bad").sum()))
print("Missing rows:", int((qa_df["qc_status"] == "missing").sum()))


# ============================================================
# 15. SAVE OUTPUTS
# ============================================================

if SAVE_OUTPUTS:
    qa_df.to_csv(OUTPUT_QAQC_PATH, index=False)
    qa_good_df.to_csv(OUTPUT_GOOD_ONLY_PATH, index=False)
    qa_observed_df.to_csv(OUTPUT_OBSERVED_ONLY_PATH, index=False)
    qc_status_summary.to_csv(OUTPUT_QAQC_STATUS_SUMMARY_PATH, index=False)
    qc_flag_summary.to_csv(OUTPUT_QAQC_FLAG_SUMMARY_PATH, index=False)

    print("\nQA/QC flagged dataset written to:")
    print(OUTPUT_QAQC_PATH)

    print("\nGood-only QA/QC dataset written to:")
    print(OUTPUT_GOOD_ONLY_PATH)

    print("\nObserved-only QA/QC dataset written to:")
    print(OUTPUT_OBSERVED_ONLY_PATH)

    print("\nQA/QC status summary written to:")
    print(OUTPUT_QAQC_STATUS_SUMMARY_PATH)

    print("\nQA/QC flag summary written to:")
    print(OUTPUT_QAQC_FLAG_SUMMARY_PATH)


# ============================================================
# 16. QA/QC PLOTTING FUNCTIONS
# ============================================================

def plot_qaqc_pollutant(df, pollutant):
    """
    Plot one pollutant across all selected Dublin stations.

    Good/unflagged observed station series are shown in light grey.
    Suspect and bad observed records are overlaid with consistent QA/QC colours.
    Missing records are not plotted here because they have no concentration value.
    """
    plot_df = df[df["pollutant"] == pollutant].copy()

    if plot_df.empty:
        print(f"No data found for {pollutant}")
        return

    observed_df = plot_df[plot_df["qc_status"] != "missing"].copy()

    plt.figure(figsize=(16, 8))

    for station, station_df in observed_df.groupby("station"):
        station_df = station_df.sort_values("date")

        plt.plot(
            station_df["date"],
            station_df["concentration_ug_m3"],
            linewidth=0.8,
            alpha=0.35,
            color=QC_COLORS["good"]
        )

    suspect_df = observed_df[observed_df["qc_status"] == "suspect"].copy()
    bad_df = observed_df[observed_df["qc_status"] == "bad"].copy()

    # Manual legend element for the grey background series.
    plt.plot(
        [],
        [],
        color=QC_COLORS["good"],
        linewidth=2,
        label="Good / unflagged series"
    )

    if not suspect_df.empty:
        plt.scatter(
            suspect_df["date"],
            suspect_df["concentration_ug_m3"],
            s=22,
            alpha=0.85,
            color=QC_COLORS["suspect"],
            label="Suspect"
        )

    if not bad_df.empty:
        plt.scatter(
            bad_df["date"],
            bad_df["concentration_ug_m3"],
            s=36,
            marker="x",
            alpha=0.95,
            color=QC_COLORS["bad"],
            label="Bad"
        )

    plt.title(f"{pollutant} QA/QC flags across selected Dublin EPA stations")
    plt.xlabel("Date")
    plt.ylabel("Concentration (µg/m³)")
    plt.grid(True, alpha=0.3)

    if SHOW_LEGEND:
        plt.legend(
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            fontsize=8
        )

    plt.tight_layout()
    plt.show()


def plot_qaqc_status_counts(df):
    """
    Plot total number of good, suspect, bad, and missing records by pollutant.
    Uses consistent QA/QC colours.
    """
    count_df = (
        df
        .groupby(["pollutant", "qc_status"])
        .size()
        .reset_index(name="n_records")
    )

    pivot_df = (
        count_df
        .pivot(index="pollutant", columns="qc_status", values="n_records")
        .fillna(0)
    )

    status_order = ["good", "suspect", "bad", "missing"]
    pivot_df = pivot_df.reindex(columns=status_order, fill_value=0)

    bar_colors = [QC_COLORS[status] for status in status_order]

    pivot_df.plot(
        kind="bar",
        figsize=(10, 6),
        color=bar_colors
    )

    plt.title("QA/QC status counts by pollutant")
    plt.xlabel("Pollutant")
    plt.ylabel("Number of daily records")
    plt.xticks(rotation=0)
    plt.grid(True, axis="y", alpha=0.3)
    plt.legend(title="QA/QC status")
    plt.tight_layout()
    plt.show()


def plot_missing_records_by_station(df):
    """
    Plot missing internal daily records by station and pollutant.
    This separates data completeness from observed concentration QA/QC.
    """
    missing_df = (
        df[df["qc_status"] == "missing"]
        .groupby(["pollutant", "station"])
        .size()
        .reset_index(name="n_missing_days")
    )

    if missing_df.empty:
        print("\nNo missing internal records found.")
        return

    for pollutant in sorted(missing_df["pollutant"].unique()):
        pollutant_df = (
            missing_df[missing_df["pollutant"] == pollutant]
            .sort_values("n_missing_days", ascending=True)
        )

        plt.figure(figsize=(10, 8))

        plt.barh(
            pollutant_df["station"],
            pollutant_df["n_missing_days"],
            color=QC_COLORS["missing"]
        )

        plt.title(f"{pollutant} missing internal daily records by station")
        plt.xlabel("Number of missing daily records")
        plt.ylabel("Station")
        plt.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()
        plt.show()


def plot_flag_counts_by_type(df):
    """
    Plot total number of records flagged by each QA/QC rule.
    This helps diagnose which tests are driving the QA/QC classification.
    """
    flag_cols = [
        "flag_missing_internal_date",
        "flag_negative_or_invalid",
        "flag_extreme_bad_absolute",
        "flag_high_suspect_absolute",
        "flag_local_spike_robust_z",
        "flag_isolated_spike",
        "flag_repeated_value_run",
        "flag_pm25_gt_pm10"
    ]

    flag_counts = []

    for col in flag_cols:
        if col in df.columns:
            flag_counts.append({
                "flag": col.replace("flag_", ""),
                "n_records": int(df[col].sum())
            })

    flag_counts_df = pd.DataFrame(flag_counts)

    flag_counts_df = flag_counts_df.sort_values("n_records", ascending=True)

    plt.figure(figsize=(10, 7))

    plt.barh(
        flag_counts_df["flag"],
        flag_counts_df["n_records"]
    )

    plt.title("Number of records flagged by each QA/QC rule")
    plt.xlabel("Number of records")
    plt.ylabel("QA/QC flag")
    plt.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    plt.show()


# ============================================================
# 17. MAKE QA/QC PLOTS
# ============================================================

if PLOT_QAQC:
    plot_qaqc_pollutant(qa_df, "PM2.5")
    plot_qaqc_pollutant(qa_df, "PM10")
    plot_qaqc_status_counts(qa_df)
    plot_missing_records_by_station(qa_df)
    plot_flag_counts_by_type(qa_df)


# ============================================================
# 18. QA/QC DIAGNOSTIC REVIEW
#
# Step 1:
#   Inspect flagged records manually
#
# Step 2:
#   Separate flag types into categories
#
# Step 3:
#   Produce station-level data coverage summaries
# ============================================================


# ============================================================
# 18.1 OUTPUT PATHS FOR QA/QC DIAGNOSTICS
# ============================================================

OUTPUT_FLAGGED_RECORDS_REVIEW_PATH = (
    OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_flagged_records_for_review.csv"
)

OUTPUT_TOP_SUSPECT_RECORDS_PATH = (
    OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_top_suspect_records.csv"
)

OUTPUT_FLAG_CATEGORY_SUMMARY_PATH = (
    OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_flag_category_summary.csv"
)

OUTPUT_STATION_COVERAGE_SUMMARY_PATH = (
    OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_station_coverage_summary.csv"
)

OUTPUT_STATION_YEAR_COVERAGE_SUMMARY_PATH = (
    OUTPUT_DIR / "EPA_PM_Dublin_selected_QAQC_station_year_coverage_summary.csv"
)


# ============================================================
# 18.2 STEP 1: INSPECT FLAGGED RECORDS MANUALLY
# ============================================================

# These are the columns most useful for checking whether a flag is a real
# data problem or a real pollution event.

review_cols = [
    "date",
    "year",
    "pollutant",
    "station",
    "concentration_ug_m3",
    "qc_status",
    "qc_flag_reasons",
    "robust_z",
    "rolling_median",
    "rolling_mad",
    "previous_value",
    "next_value",
    "neighbour_mean",
    "repeated_value_run_length",
    "flag_missing_internal_date",
    "flag_negative_or_invalid",
    "flag_extreme_bad_absolute",
    "flag_high_suspect_absolute",
    "flag_local_spike_robust_z",
    "flag_isolated_spike",
    "flag_repeated_value_run",
    "flag_pm25_gt_pm10"
]

# Keep only columns that actually exist in qa_df.
review_cols = [col for col in review_cols if col in qa_df.columns]

flagged_records_for_review = (
    qa_df[qa_df["qc_flag_any"]]
    .copy()
    .loc[:, review_cols]
    .sort_values(
        ["qc_status", "pollutant", "station", "date"]
    )
)

# Top suspect records ranked by concentration and robust z-score.
# Missing values are excluded here because they have no concentration value.
top_suspect_records = (
    qa_df[
        (qa_df["qc_status"] == "suspect")
        & qa_df["concentration_ug_m3"].notna()
    ]
    .copy()
)

top_suspect_records["abs_robust_z"] = top_suspect_records["robust_z"].abs()

top_suspect_records = (
    top_suspect_records
    .sort_values(
        ["pollutant", "abs_robust_z", "concentration_ug_m3"],
        ascending=[True, False, False]
    )
    .loc[:, [col for col in review_cols + ["abs_robust_z"] if col in top_suspect_records.columns]]
)

print("\nStep 1: Flagged records for manual review")
print("Total flagged records:", flagged_records_for_review.shape[0])
print("Total suspect observed records:", int((qa_df["qc_status"] == "suspect").sum()))
print("Total bad observed records:", int((qa_df["qc_status"] == "bad").sum()))
print("Total missing records:", int((qa_df["qc_status"] == "missing").sum()))

print("\nTop 30 suspect records by robust z-score / concentration:")
if top_suspect_records.empty:
    print("No suspect records found.")
else:
    print(top_suspect_records.head(30).to_string(index=False))

if SAVE_OUTPUTS:
    flagged_records_for_review.to_csv(
        OUTPUT_FLAGGED_RECORDS_REVIEW_PATH,
        index=False
    )

    top_suspect_records.to_csv(
        OUTPUT_TOP_SUSPECT_RECORDS_PATH,
        index=False
    )

    print("\nFlagged records for review written to:")
    print(OUTPUT_FLAGGED_RECORDS_REVIEW_PATH)

    print("\nTop suspect records written to:")
    print(OUTPUT_TOP_SUSPECT_RECORDS_PATH)


# ============================================================
# 18.3 STEP 2: SEPARATE FLAGS INTO INTERPRETABLE CATEGORIES
# ============================================================

# Missing flags:
#   Data completeness issue. Not an observed concentration problem.
#
# Exclusion flags:
#   Strong evidence of invalid observed data.
#
# Review flags:
#   Potential issue, but may also be a real pollution event.

missing_flag_cols = [
    "flag_missing_internal_date"
]

exclusion_flag_cols = [
    "flag_negative_or_invalid",
    "flag_extreme_bad_absolute"
]

review_flag_cols = [
    "flag_high_suspect_absolute",
    "flag_local_spike_robust_z",
    "flag_isolated_spike",
    "flag_repeated_value_run",
    "flag_pm25_gt_pm10"
]

missing_flag_cols = [col for col in missing_flag_cols if col in qa_df.columns]
exclusion_flag_cols = [col for col in exclusion_flag_cols if col in qa_df.columns]
review_flag_cols = [col for col in review_flag_cols if col in qa_df.columns]

qa_df["has_missing_flag"] = qa_df[missing_flag_cols].any(axis=1)
qa_df["has_exclusion_flag"] = qa_df[exclusion_flag_cols].any(axis=1)
qa_df["has_review_flag"] = qa_df[review_flag_cols].any(axis=1)

qa_df["qc_flag_category"] = "none"

qa_df.loc[qa_df["has_review_flag"], "qc_flag_category"] = "review"
qa_df.loc[qa_df["has_exclusion_flag"], "qc_flag_category"] = "exclude"
qa_df.loc[qa_df["has_missing_flag"], "qc_flag_category"] = "missing"

flag_category_summary = (
    qa_df
    .groupby(["pollutant", "station", "qc_flag_category"])
    .size()
    .reset_index(name="n_records")
    .sort_values(["pollutant", "station", "qc_flag_category"])
)

flag_category_summary_overall = (
    qa_df
    .groupby(["pollutant", "qc_flag_category"])
    .size()
    .reset_index(name="n_records")
    .sort_values(["pollutant", "qc_flag_category"])
)

print("\nStep 2: QA/QC flag category summary by pollutant")
print(flag_category_summary_overall.to_string(index=False))

if SAVE_OUTPUTS:
    flag_category_summary.to_csv(
        OUTPUT_FLAG_CATEGORY_SUMMARY_PATH,
        index=False
    )

    print("\nFlag category summary written to:")
    print(OUTPUT_FLAG_CATEGORY_SUMMARY_PATH)


# ============================================================
# 18.4 STEP 3: STATION-LEVEL DATA COVERAGE SUMMARY
# ============================================================

def safe_percent(numerator, denominator):
    """
    Return percentage safely.
    """
    if denominator == 0 or pd.isna(denominator):
        return np.nan
    return 100 * numerator / denominator


station_coverage_summary = (
    qa_df
    .groupby(["pollutant", "station"])
    .agg(
        date_start=("date", "min"),
        date_end=("date", "max"),
        n_expected_days=("date", "size"),
        n_observed_days=("concentration_ug_m3", lambda x: x.notna().sum()),
        n_missing_days=("qc_status", lambda x: (x == "missing").sum()),
        n_good_days=("qc_status", lambda x: (x == "good").sum()),
        n_suspect_days=("qc_status", lambda x: (x == "suspect").sum()),
        n_bad_days=("qc_status", lambda x: (x == "bad").sum()),
        n_review_flag_days=("has_review_flag", "sum"),
        n_exclusion_flag_days=("has_exclusion_flag", "sum"),
        n_missing_flag_days=("has_missing_flag", "sum"),
        mean_concentration_observed=("concentration_ug_m3", "mean"),
        median_concentration_observed=("concentration_ug_m3", "median"),
        max_concentration_observed=("concentration_ug_m3", "max")
    )
    .reset_index()
)

station_coverage_summary["percent_missing"] = station_coverage_summary.apply(
    lambda row: safe_percent(row["n_missing_days"], row["n_expected_days"]),
    axis=1
)

station_coverage_summary["percent_observed"] = station_coverage_summary.apply(
    lambda row: safe_percent(row["n_observed_days"], row["n_expected_days"]),
    axis=1
)

station_coverage_summary["percent_good_of_expected"] = station_coverage_summary.apply(
    lambda row: safe_percent(row["n_good_days"], row["n_expected_days"]),
    axis=1
)

station_coverage_summary["percent_good_of_observed"] = station_coverage_summary.apply(
    lambda row: safe_percent(row["n_good_days"], row["n_observed_days"]),
    axis=1
)

station_coverage_summary["percent_suspect_of_observed"] = station_coverage_summary.apply(
    lambda row: safe_percent(row["n_suspect_days"], row["n_observed_days"]),
    axis=1
)

station_coverage_summary["percent_bad_of_observed"] = station_coverage_summary.apply(
    lambda row: safe_percent(row["n_bad_days"], row["n_observed_days"]),
    axis=1
)

station_coverage_summary = station_coverage_summary.sort_values(
    ["pollutant", "percent_observed", "station"],
    ascending=[True, False, True]
)

print("\nStep 3: Station-level coverage summary")
print(station_coverage_summary.to_string(index=False))

if SAVE_OUTPUTS:
    station_coverage_summary.to_csv(
        OUTPUT_STATION_COVERAGE_SUMMARY_PATH,
        index=False
    )

    print("\nStation-level coverage summary written to:")
    print(OUTPUT_STATION_COVERAGE_SUMMARY_PATH)


# ============================================================
# 18.5 OPTIONAL: STATION-YEAR COVERAGE SUMMARY
# ============================================================

station_year_coverage_summary = (
    qa_df
    .groupby(["year", "pollutant", "station"])
    .agg(
        date_start=("date", "min"),
        date_end=("date", "max"),
        n_expected_days=("date", "size"),
        n_observed_days=("concentration_ug_m3", lambda x: x.notna().sum()),
        n_missing_days=("qc_status", lambda x: (x == "missing").sum()),
        n_good_days=("qc_status", lambda x: (x == "good").sum()),
        n_suspect_days=("qc_status", lambda x: (x == "suspect").sum()),
        n_bad_days=("qc_status", lambda x: (x == "bad").sum())
    )
    .reset_index()
)

station_year_coverage_summary["percent_missing"] = station_year_coverage_summary.apply(
    lambda row: safe_percent(row["n_missing_days"], row["n_expected_days"]),
    axis=1
)

station_year_coverage_summary["percent_observed"] = station_year_coverage_summary.apply(
    lambda row: safe_percent(row["n_observed_days"], row["n_expected_days"]),
    axis=1
)

station_year_coverage_summary["percent_good_of_observed"] = station_year_coverage_summary.apply(
    lambda row: safe_percent(row["n_good_days"], row["n_observed_days"]),
    axis=1
)

station_year_coverage_summary = station_year_coverage_summary.sort_values(
    ["year", "pollutant", "station"]
)

print("\nStation-year coverage summary:")
print(station_year_coverage_summary.to_string(index=False))

if SAVE_OUTPUTS:
    station_year_coverage_summary.to_csv(
        OUTPUT_STATION_YEAR_COVERAGE_SUMMARY_PATH,
        index=False
    )

    print("\nStation-year coverage summary written to:")
    print(OUTPUT_STATION_YEAR_COVERAGE_SUMMARY_PATH)


# ============================================================
# 18.6 DIAGNOSTIC PLOTS FOR STEP 3
# ============================================================

def plot_station_percent_observed(coverage_df):
    """
    Plot percent observed records by station and pollutant.
    """
    for pollutant in sorted(coverage_df["pollutant"].unique()):
        pollutant_df = (
            coverage_df[coverage_df["pollutant"] == pollutant]
            .sort_values("percent_observed", ascending=True)
        )

        plt.figure(figsize=(10, 8))

        plt.barh(
            pollutant_df["station"],
            pollutant_df["percent_observed"],
            color=QC_COLORS["good"]
        )

        plt.title(f"{pollutant} percent observed records by station")
        plt.xlabel("Observed records (%)")
        plt.ylabel("Station")
        plt.xlim(0, 100)
        plt.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()
        plt.show()


def plot_station_qc_composition(coverage_df):
    """
    Plot good, suspect, bad, and missing percentages by station.
    """
    plot_df = coverage_df.copy()

    plot_df["percent_good"] = plot_df.apply(
        lambda row: safe_percent(row["n_good_days"], row["n_expected_days"]),
        axis=1
    )

    plot_df["percent_suspect"] = plot_df.apply(
        lambda row: safe_percent(row["n_suspect_days"], row["n_expected_days"]),
        axis=1
    )

    plot_df["percent_bad"] = plot_df.apply(
        lambda row: safe_percent(row["n_bad_days"], row["n_expected_days"]),
        axis=1
    )

    plot_df["percent_missing"] = plot_df.apply(
        lambda row: safe_percent(row["n_missing_days"], row["n_expected_days"]),
        axis=1
    )

    for pollutant in sorted(plot_df["pollutant"].unique()):
        pollutant_df = (
            plot_df[plot_df["pollutant"] == pollutant]
            .sort_values("percent_good", ascending=True)
            .set_index("station")
        )

        stacked_df = pollutant_df[
            [
                "percent_good",
                "percent_suspect",
                "percent_bad",
                "percent_missing"
            ]
        ]

        stacked_df.plot(
            kind="barh",
            stacked=True,
            figsize=(11, 8),
            color=[
                QC_COLORS["good"],
                QC_COLORS["suspect"],
                QC_COLORS["bad"],
                QC_COLORS["missing"]
            ]
        )

        plt.title(f"{pollutant} QA/QC composition by station")
        plt.xlabel("Share of expected daily records (%)")
        plt.ylabel("Station")
        plt.xlim(0, 100)
        plt.grid(True, axis="x", alpha=0.3)
        plt.legend(
            ["Good", "Suspect", "Bad", "Missing"],
            title="QA/QC status",
            bbox_to_anchor=(1.02, 1),
            loc="upper left"
        )
        plt.tight_layout()
        plt.show()


def plot_suspect_records_by_station(coverage_df):
    """
    Plot number of suspect observed records by station and pollutant.
    """
    for pollutant in sorted(coverage_df["pollutant"].unique()):
        pollutant_df = (
            coverage_df[coverage_df["pollutant"] == pollutant]
            .sort_values("n_suspect_days", ascending=True)
        )

        plt.figure(figsize=(10, 8))

        plt.barh(
            pollutant_df["station"],
            pollutant_df["n_suspect_days"],
            color=QC_COLORS["suspect"]
        )

        plt.title(f"{pollutant} suspect records by station")
        plt.xlabel("Number of suspect daily records")
        plt.ylabel("Station")
        plt.grid(True, axis="x", alpha=0.3)
        plt.tight_layout()
        plt.show()


if PLOT_QAQC:
    plot_station_percent_observed(station_coverage_summary)
    plot_station_qc_composition(station_coverage_summary)
    plot_suspect_records_by_station(station_coverage_summary)


print("\nQA/QC diagnostic review through Step 3 complete.")
