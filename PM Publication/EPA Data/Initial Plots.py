# ============================================================
# PLOT EPA PM2.5 AND PM10 DAILY DATA
# All stations on the same plot for each pollutant
#
# Input:
#   EPA_PM_daily_long_2020_2024.csv
#
# Output:
#   Plots shown on screen
# ============================================================


# ============================================================
# 0. IMPORTS
# ============================================================

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. USER SETTINGS
# ============================================================

DATA_PATH = Path(
    r"C:/Users/Richa/Documents/Python_Projects/PM_Data_EPA/combined_outputs/EPA_PM_daily_long_2020_2024.csv"
)

# Set to True if you want to plot only stations with good data coverage
FILTER_LOW_COVERAGE_STATIONS = False

# Minimum number of daily observations required per station if filtering is used
MIN_DAYS_REQUIRED = 300

# Optional rolling mean to make the plot easier to read.
# Use None for raw daily values.
# Use 7 for 7-day rolling mean.
ROLLING_MEAN_DAYS = None


# ============================================================
# 2. LOAD DATA
# ============================================================

pm_df = pd.read_csv(DATA_PATH)

pm_df["date"] = pd.to_datetime(pm_df["date"])
pm_df["concentration_ug_m3"] = pd.to_numeric(
    pm_df["concentration_ug_m3"],
    errors="coerce"
)

pm_df = pm_df.dropna(
    subset=["date", "pollutant", "station", "concentration_ug_m3"]
).copy()

pm_df = pm_df.sort_values(["pollutant", "station", "date"]).reset_index(drop=True)

print("\nLoaded data:")
print(pm_df.head())

print("\nRows:", pm_df.shape[0])
print("Date range:", pm_df["date"].min(), "to", pm_df["date"].max())
print("Pollutants:", sorted(pm_df["pollutant"].unique()))
print("Stations:", pm_df["station"].nunique())


# ============================================================
# 3. OPTIONAL FILTER BY DATA COVERAGE
# ============================================================

if FILTER_LOW_COVERAGE_STATIONS:
    coverage = (
        pm_df
        .groupby(["pollutant", "station"])["date"]
        .nunique()
        .reset_index(name="n_days")
    )

    keep = coverage[coverage["n_days"] >= MIN_DAYS_REQUIRED][
        ["pollutant", "station"]
    ]

    pm_df = pm_df.merge(
        keep,
        on=["pollutant", "station"],
        how="inner"
    )

    print("\nAfter filtering low-coverage stations:")
    print("Rows:", pm_df.shape[0])
    print("Stations:", pm_df["station"].nunique())


# ============================================================
# 4. OPTIONAL ROLLING MEAN
# ============================================================

if ROLLING_MEAN_DAYS is not None:
    pm_df["plot_value"] = (
        pm_df
        .groupby(["pollutant", "station"])["concentration_ug_m3"]
        .transform(
            lambda x: x.rolling(
                window=ROLLING_MEAN_DAYS,
                min_periods=1
            ).mean()
        )
    )
else:
    pm_df["plot_value"] = pm_df["concentration_ug_m3"]


# ============================================================
# 5. PLOTTING FUNCTION
# ============================================================

def plot_pollutant_all_stations(df, pollutant):
    """
    Plot all stations for one pollutant on the same graph.
    """
    plot_df = df[df["pollutant"] == pollutant].copy()

    if plot_df.empty:
        print(f"No data found for {pollutant}")
        return

    n_stations = plot_df["station"].nunique()

    plt.figure(figsize=(16, 8))

    for station, station_df in plot_df.groupby("station"):
        station_df = station_df.sort_values("date")

        plt.plot(
            station_df["date"],
            station_df["plot_value"],
            linewidth=0.8,
            alpha=0.45,
            label=station
        )

    if ROLLING_MEAN_DAYS is None:
        title = f"{pollutant} daily concentration across EPA stations"
    else:
        title = f"{pollutant} {ROLLING_MEAN_DAYS}-day rolling mean across EPA stations"

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Concentration (µg/m³)")
    plt.grid(True, alpha=0.3)

    # With many stations, the legend can be huge.
    # This keeps it outside the plot.
    plt.legend(
        title=f"Station ({n_stations})",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=7
    )

    plt.tight_layout()
    plt.show()


# ============================================================
# 6. MAKE PLOTS
# ============================================================

plot_pollutant_all_stations(pm_df, "PM2.5")
plot_pollutant_all_stations(pm_df, "PM10")
