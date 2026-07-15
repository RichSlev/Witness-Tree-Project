# ============================================================
# PLOT EPA PM2.5 AND PM10 DAILY DATA
# Selected Dublin stations only
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
import re
import unicodedata

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. USER SETTINGS
# ============================================================

DATA_PATH = Path(
    r"C:/Users/Richa/Documents/Python_Projects/PM_Data_EPA/combined_outputs/EPA_PM_daily_long_2020_2024.csv"
)

SAVE_STATION_REPAIR_LOG = True
STATION_REPAIR_LOG_PATH = DATA_PATH.parent / "EPA_PM_station_name_repair_log.csv"

SAVE_DUBLIN_STATION_FILTER_LOG = True
DUBLIN_STATION_FILTER_LOG_PATH = DATA_PATH.parent / "EPA_PM_dublin_station_filter_log.csv"

FILTER_LOW_COVERAGE_STATIONS = False
MIN_DAYS_REQUIRED = 300

# Use None for raw daily values.
# Use 7 for 7-day rolling mean.
ROLLING_MEAN_DAYS = None

SHOW_LEGEND = True


# ============================================================
# 2. TARGET DUBLIN STATIONS
# ============================================================

TARGET_STATIONS = [
    "Amiens Street",
    "Ballyfermot",
    "Blanchardstown",
    "Clonskeagh",
    "DAA / Dublin Airport",
    "Davitt Road",
    "Dublin Port",
    "Dun Laoghaire",
    "Finglas",
    "Lucan",
    "Marino",
    "Pearse Street",
    "Phoenix Park",
    "Ringsend",
    "St Annes",
    "St John's Road",
    "Swords",
    "Tallaght",
    "Winetavern"
]


# ============================================================
# 3. STATION NAME REPAIR FUNCTIONS
# ============================================================

def clean_text(x):
    """
    Basic text cleaning.
    """
    if pd.isna(x):
        return ""

    x = str(x).strip()
    x = re.sub(r"\s+", " ", x)

    return x


def is_number_like(x):
    """
    Detect values like:
        13.21
        40.3
        9.735488613152
    """
    x = clean_text(x)

    if x == "":
        return False

    try:
        float(x)
        return True
    except ValueError:
        return False


def is_method_like(x):
    """
    Detect PM measurement method labels.
    """
    x = clean_text(x).lower()

    method_terms = [
        "gravimetric",
        "teom",
        "fdms",
        "bam",
        "beta",
        "fidas",
        "palas",
        "optical",
        "nephelometer",
        "reference",
        "monitor",
        "partisol"
    ]

    return any(term in x for term in method_terms)


def is_unit_like(x):
    """
    Detect unit-like labels.
    """
    x = clean_text(x).lower()
    x = x.replace("µ", "u").replace("μ", "u")

    unit_terms = [
        "ug",
        "ug/m3",
        "ug m-3",
        "ug/m^3",
        "ug m3",
        "mg",
        "ppm",
        "ppb",
        "unit",
        "units",
        "%"
    ]

    return any(term in x for term in unit_terms)


def repair_station_name(station):
    """
    Repair station labels caused by earlier header parsing.
    """
    original = clean_text(station)

    if original == "":
        return "", "empty"

    m = re.match(r"^(.*?)\s*\[(.*?)\]\s*$", original)

    if not m:
        return original, "unchanged"

    base = clean_text(m.group(1))
    bracket = clean_text(m.group(2))

    if is_number_like(bracket):
        return base, "removed_numeric_bracket"

    if is_method_like(base) and bracket != "":
        return bracket, "method_base_station_in_bracket"

    if is_unit_like(base) and bracket != "":
        return bracket, "unit_base_station_in_bracket"

    return base, "other_bracket_removed"


def remove_method_terms_from_key(x):
    """
    Remove method/instrument terms from a normalised station key.

    This lets:
        Finglas Fidas              -> Finglas
        Finglas LECKEL             -> Finglas
        Ringsend Fidas             -> Ringsend
        Phoenix Park LECKEL Fidas  -> Phoenix Park
        Winetavern st Fidas        -> Winetavern
    """
    x = normalize_station_key(x)

    method_terms = [
        "fidas",
        "leckel",
        "bam",
        "swam",
        "gravimetric",
        "teom",
        "fdms",
        "trailer"
    ]

    for term in method_terms:
        x = re.sub(rf"\b{term}\b", " ", x)

    x = re.sub(r"\band\b", " ", x)
    x = re.sub(r"\s+", " ", x).strip()

    # Normalise common short forms
    replacements = {
        "amiens st": "amiens street",
        "pearse st": "pearse street",
        "st john s road": "st johns road",
        "st johns rd": "st johns road",
        "st anne s": "st annes",
        "winetavern st": "winetavern",
        "daa": "daa dublin airport",
        "dublin airport": "daa dublin airport"
    }

    x = replacements.get(x, x)

    return x


def extract_method_stream(station_label):
    """
    Extract method/instrument information from the original or repaired label.
    """
    key = normalize_station_key(station_label)

    tags = []

    if re.search(r"\bfidas\b", key):
        tags.append("FIDAS")

    if re.search(r"\bleckel\b", key):
        tags.append("LECKEL")

    if re.search(r"\bbam\b", key):
        tags.append("BAM")

    if re.search(r"\bswam\b", key):
        tags.append("SWAM")

    if re.search(r"\bgravimetric\b", key):
        tags.append("GRAVIMETRIC")

    if re.search(r"\bteom\b", key):
        tags.append("TEOM")

    if re.search(r"\bfdms\b", key):
        tags.append("FDMS")

    if not tags:
        return "unlabelled"

    return " + ".join(tags)


# ============================================================
# 4. STATION MATCHING FUNCTIONS
# ============================================================

def normalize_station_key(x):
    """
    Create a robust matching key for station names.

    This helps match labels such as:
        Amiens st.       -> Amiens Street
        Pearse st.       -> Pearse Street
        St Anne's        -> St Annes
        St. John's Road  -> St John's Road
    """
    x = clean_text(x)

    x = unicodedata.normalize("NFKD", x)
    x = x.encode("ascii", "ignore").decode("ascii")

    x = x.lower()
    x = x.replace("&", " and ")

    # Remove punctuation but keep letters, numbers, and spaces.
    x = re.sub(r"[^a-z0-9\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip()

    return x


TARGET_LOOKUP = {
    normalize_station_key(station): station
    for station in TARGET_STATIONS
}

# Manual aliases for known EPA naming variants.
TARGET_LOOKUP.update({
    normalize_station_key("Amiens st."): "Amiens Street",
    normalize_station_key("Amiens St"): "Amiens Street",

    normalize_station_key("Pearse st."): "Pearse Street",
    normalize_station_key("Pearse St"): "Pearse Street",

    normalize_station_key("St Anne's"): "St Annes",
    normalize_station_key("St. Anne's"): "St Annes",
    normalize_station_key("St Annes Park"): "St Annes",

    normalize_station_key("St John's Rd"): "St John's Road",
    normalize_station_key("St. John's Road"): "St John's Road",

    normalize_station_key("DAA"): "DAA / Dublin Airport",
    normalize_station_key("Dublin Airport"): "DAA / Dublin Airport",
    normalize_station_key("DAA Dublin Airport"): "DAA / Dublin Airport",

    normalize_station_key("Dun Laoghaire"): "Dun Laoghaire",
    normalize_station_key("Dún Laoghaire"): "Dun Laoghaire",

    # Method-labelled station variants
    normalize_station_key("Clonskeagh Fidas"): "Clonskeagh",

    normalize_station_key("Finglas Fidas"): "Finglas",
    normalize_station_key("Finglas LECKEL"): "Finglas",
    normalize_station_key("Finglas LECKEL & Fidas"): "Finglas",

    normalize_station_key("Ringsend Fidas"): "Ringsend",

    normalize_station_key("Phoenix Park LECKEL & Fidas"): "Phoenix Park",

    normalize_station_key("Winetavern st Fidas"): "Winetavern",
    normalize_station_key("Winetavern st LECKEL"): "Winetavern",
    normalize_station_key("Winetavern st"): "Winetavern",
})

# Fix apostrophe/key mismatch for St John's Road
TARGET_LOOKUP["st johns road"] = "St John's Road"

# ============================================================
# 5. LOAD DATA
# ============================================================

pm_df = pd.read_csv(DATA_PATH)

pm_df["date"] = pd.to_datetime(pm_df["date"])

if "year" not in pm_df.columns:
    pm_df["year"] = pm_df["date"].dt.year

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
print("Original station labels:", pm_df["station"].nunique())


# ============================================================
# 6. REPAIR STATION LABELS
# ============================================================

pm_df["station_original"] = pm_df["station"]

repair_results = pm_df["station_original"].apply(repair_station_name)

pm_df["station_repaired"] = repair_results.apply(lambda x: x[0])
pm_df["station_repair_rule"] = repair_results.apply(lambda x: x[1])

pm_df = pm_df[pm_df["station_repaired"] != ""].copy()

repair_log = (
    pm_df[["station_original", "station_repaired", "station_repair_rule"]]
    .drop_duplicates()
    .sort_values(["station_repair_rule", "station_original"])
)

print("\nStation repair summary:")
print(
    repair_log
    .groupby("station_repair_rule")
    .size()
    .reset_index(name="n_station_labels")
    .to_string(index=False)
)

print("\nClean station labels before Dublin filtering:", pm_df["station_repaired"].nunique())

if SAVE_STATION_REPAIR_LOG:
    repair_log.to_csv(STATION_REPAIR_LOG_PATH, index=False)
    print("\nStation repair log written to:")
    print(STATION_REPAIR_LOG_PATH)


# ============================================================
# 7. KEEP SELECTED DUBLIN STATIONS ONLY
# ============================================================

pm_df["method_stream"] = pm_df["station_original"].apply(extract_method_stream)
pm_df["station_match_key"] = pm_df["station_repaired"].apply(remove_method_terms_from_key)
pm_df["station_target"] = pm_df["station_match_key"].map(TARGET_LOOKUP)

station_filter_log = (
    pm_df[["station_original", "station_repaired", "station_match_key", "station_target"]]
    .drop_duplicates()
    .sort_values(["station_target", "station_repaired"])
)

if SAVE_DUBLIN_STATION_FILTER_LOG:
    station_filter_log.to_csv(DUBLIN_STATION_FILTER_LOG_PATH, index=False)
    print("\nDublin station filter log written to:")
    print(DUBLIN_STATION_FILTER_LOG_PATH)

present_targets = sorted(pm_df["station_target"].dropna().unique())
missing_targets = sorted(set(TARGET_STATIONS) - set(present_targets))

print("\nSelected Dublin stations found in data:")
for station in present_targets:
    print(" ", station)

if missing_targets:
    print("\nSelected Dublin stations NOT found in data:")
    for station in missing_targets:
        print(" ", station)

pm_df = pm_df[pm_df["station_target"].notna()].copy()

# Replace repaired station label with the clean target label.
pm_df["station"] = pm_df["station_target"]

print("\nAfter keeping selected Dublin stations only:")
print("Rows:", pm_df.shape[0])
print("Stations:", pm_df["station"].nunique())


# ============================================================
# 8. COLLAPSE DUPLICATES CREATED BY STATION REPAIR AND ALIASING
# ============================================================

# Important:
# We keep method_stream in the grouping.
# This avoids blindly averaging FIDAS, LECKEL, gravimetric, and unlabelled
# records together when they exist on the same date.

pm_df = (
    pm_df
    .groupby(["date", "year", "pollutant", "station", "method_stream"], as_index=False)
    .agg(
        concentration_ug_m3=("concentration_ug_m3", "mean"),
        n_values_combined=("concentration_ug_m3", "count"),
        station_original_labels=("station_original", lambda x: " | ".join(sorted(set(x)))),
        station_repaired_labels=("station_repaired", lambda x: " | ".join(sorted(set(x))))
    )
)

pm_df = pm_df.sort_values(
    ["pollutant", "station", "method_stream", "date"]
).reset_index(drop=True)

print("\nAfter repairing station names and preserving method streams:")
print("Rows:", pm_df.shape[0])
print("Stations:", pm_df["station"].nunique())
print("Method streams:", sorted(pm_df["method_stream"].unique()))

overlap_check = (
    pm_df
    .groupby(["date", "pollutant", "station"])
    .agg(
        n_method_streams=("method_stream", "nunique"),
        method_streams=("method_stream", lambda x: " | ".join(sorted(set(x))))
    )
    .reset_index()
)

same_day_method_overlaps = overlap_check[overlap_check["n_method_streams"] > 1].copy()

print("\nSame-day method-stream overlaps after Dublin filtering:")
print("Rows:", same_day_method_overlaps.shape[0])

if not same_day_method_overlaps.empty:
    print(same_day_method_overlaps.head(30).to_string(index=False))

    same_day_method_overlaps.to_csv(
        DATA_PATH.parent / "EPA_PM_Dublin_same_day_method_stream_overlaps.csv",
        index=False
    )

    print("\nSame-day method-stream overlap log written to:")
    print(DATA_PATH.parent / "EPA_PM_Dublin_same_day_method_stream_overlaps.csv")


# ============================================================
# 9. OPTIONAL FILTER BY DATA COVERAGE
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
# 10. OPTIONAL ROLLING MEAN
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
# 11. PLOTTING FUNCTION
# ============================================================

def plot_pollutant_selected_stations(df, pollutant):
    """
    Plot selected Dublin stations for one pollutant on the same graph.
    """
    plot_df = df[df["pollutant"] == pollutant].copy()

    if plot_df.empty:
        print(f"No data found for {pollutant}")
        return

    n_stations = plot_df["station"].nunique()

    plt.figure(figsize=(16, 8))

    plot_df["plot_label"] = plot_df["station"] + " [" + plot_df["method_stream"] + "]"
    for station, station_df in plot_df.groupby("plot_label"):
        station_df = station_df.sort_values("date")

        plt.plot(
            station_df["date"],
            station_df["plot_value"],
            linewidth=0.9,
            alpha=0.55,
            label=station
        )

    if ROLLING_MEAN_DAYS is None:
        title = f"{pollutant} daily concentration across selected Dublin EPA stations"
    else:
        title = f"{pollutant} {ROLLING_MEAN_DAYS}-day rolling mean across selected Dublin EPA stations"

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Concentration (µg/m³)")
    plt.grid(True, alpha=0.3)

    if SHOW_LEGEND:
        plt.legend(
            title=f"Station ({n_stations})",
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            fontsize=8
        )

    plt.tight_layout()
    plt.show()


# ============================================================
# 12. MAKE PLOTS
# ============================================================

plot_pollutant_selected_stations(pm_df, "PM2.5")
plot_pollutant_selected_stations(pm_df, "PM10")

# ============================================================
# 13. SAVE
# ============================================================


DUBLIN_SELECTED_OUTPUT_PATH = DATA_PATH.parent / "EPA_PM_Dublin_selected_daily_long_2020_2024.csv"

pm_df.to_csv(DUBLIN_SELECTED_OUTPUT_PATH, index=False)

print("\nDublin selected dataset written to:")
print(DUBLIN_SELECTED_OUTPUT_PATH)




