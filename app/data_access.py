"""
Read-side of the semantic layer.

Frames are loaded once at import and treated as immutable; every filter returns
a copy. Dashboard callbacks never touch the raw CSVs -- they read the Parquet
tables built by src/build_semantic_layer.py, which is what keeps interaction
responsive on 1.4M atomic rows.

Metric names are deliberate. See build_semantic_layer.build_l1 for why there is
no revenue column and why occupancy is called `blocked_rate`.
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# Human-facing metric labels + the caveat each one carries.
METRICS = {
    "blocked_rate": ("Blocked rate", "Share of nights unavailable. Conflates guest-booked "
                                     "with host-blocked, so it is an upper bound on occupancy."),
    "asking_adr": ("Asking ADR", "Mean listed nightly price across OPEN nights only. "
                                 "Not a transacted rate -- blocked nights carry no price."),
    "revpan_proxy": ("RevPAN proxy", "Asking ADR x blocked rate. A comparative index for "
                                     "ranking listings and areas, not a currency amount."),
    "review_velocity": ("Review velocity", "Reviews per listing per month. A demand proxy: "
                                           "only a minority of stays leave a review."),
    "sentiment_index": ("Sentiment", "Mean VADER compound score, English reviews only. "
                                     "Heavily left-skewed -- read deviations, not levels."),
}


@lru_cache(maxsize=None)
def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


def listings() -> pd.DataFrame:
    return load("l2_listing_scorecard")


def listing_month() -> pd.DataFrame:
    return load("l1_listing_month")


def neighbourhood_week() -> pd.DataFrame:
    return load("l1_neighbourhood_week")


def review_month() -> pd.DataFrame:
    return load("l1_review_month")


def kpi_neighbourhood() -> pd.DataFrame:
    return load("l2_kpi_neighbourhood")


def kpi_market() -> pd.DataFrame:
    return load("l2_kpi_market")


def amenity_penetration() -> pd.DataFrame:
    return load("l2_amenity_penetration")


def options():
    """Static filter domains, computed once."""
    lst = listings()
    nw = neighbourhood_week()
    return {
        "groups": sorted(lst["neighbourhood_group"].dropna().unique().tolist()),
        "room_types": sorted(lst["room_type"].dropna().unique().tolist()),
        "weeks": sorted(nw["week"].unique().tolist()),
        "price_max": float(lst["price"].max()),
        "price_p99": float(lst["price"].quantile(0.99)),
    }


def apply_filters(df, groups=None, room_types=None, neighbourhoods=None,
                  price_range=None, week_range=None):
    """
    Shared predicate pushdown. Each clause is skipped when the caller passes
    nothing, so the same function serves every chart regardless of which
    columns that chart's frame happens to carry.
    """
    out = df
    if groups and "neighbourhood_group" in out.columns:
        out = out[out["neighbourhood_group"].isin(groups)]
    if room_types and "room_type" in out.columns:
        out = out[out["room_type"].isin(room_types)]
    if neighbourhoods and "neighbourhood" in out.columns:
        out = out[out["neighbourhood"].isin(neighbourhoods)]
    if price_range and "price" in out.columns:
        lo, hi = price_range
        out = out[out["price"].between(lo, hi)]
    if week_range and "week" in out.columns:
        lo, hi = week_range
        out = out[out["week"].between(pd.Timestamp(lo), pd.Timestamp(hi))]
    return out


def rollup(nw: pd.DataFrame, by) -> pd.DataFrame:
    """
    Re-derive metrics from atomic sums at whatever grain `by` names.

    Aggregating the ratio columns directly would break the identity
    revpan_proxy == asking_adr * blocked_rate wherever price and availability
    correlate, so ratios are always recomputed from the underlying counts.
    """
    g = (nw.groupby(by, observed=True)
           .agg(listings=("listings", "max"),
                nights=("nights", "sum"),
                blocked_nights=("blocked_nights", "sum"),
                price_sum=("price_sum", "sum"),
                open_nights=("open_nights", "sum"))
           .reset_index())
    g["blocked_rate"] = g["blocked_nights"] / g["nights"]
    g["asking_adr"] = g["price_sum"] / g["open_nights"].replace(0, pd.NA)
    g["revpan_proxy"] = g["asking_adr"] * g["blocked_rate"]
    return g
