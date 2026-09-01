"""
Derived frames for the explanatory dashboard.

The story turns on one fact about the source: calendar.csv is a SINGLE forward
scrape taken on 2016-01-04, not a year of observations. Every frame here is
built to test, rather than assume, what that implies.
"""

from functools import lru_cache

import numpy as np
import pandas as pd

import data_access as da

SCRAPE = pd.Timestamp("2016-01-04")


@lru_cache(maxsize=None)
def horizon_curve() -> pd.DataFrame:
    """Blocked rate and asking price by days-ahead-of-scrape.

    If a forward scrape drives the weekly trend, blocked rate must decay with
    horizon: near nights have had time to accumulate bookings and blocks, far
    nights have not. This frame is what makes that testable.
    """
    c = da.load("l0_calendar")
    h = c.assign(horizon=(c["date"] - SCRAPE).dt.days)
    g = (h.groupby("horizon")
           .agg(blocked_rate=("is_booked", "mean"),
                asking_adr=("price", "mean"),
                n=("is_booked", "size"))
           .reset_index())
    g["blocked_smooth"] = g["blocked_rate"].rolling(14, center=True, min_periods=1).mean()
    g["adr_smooth"] = g["asking_adr"].rolling(14, center=True, min_periods=1).mean()
    g["month"] = (SCRAPE + pd.to_timedelta(g["horizon"], unit="D")).dt.month
    return g


@lru_cache(maxsize=None)
def horizon_spearman() -> float:
    g = horizon_curve()
    return float(g[["horizon", "blocked_rate"]].corr(method="spearman").iloc[0, 1])


@lru_cache(maxsize=None)
def review_seasonality() -> pd.DataFrame:
    """Monthly review index from 2013-2015.

    Reviews are written AFTER a stay, so they are backward-looking and carry no
    forward-scrape artifact at all. That independence is the whole point: it is
    the control against which the calendar's apparent trend is judged.
    """
    r = da.load("l0_review")
    r = r[r["date"].dt.year.between(2013, 2015)]
    s = r.groupby(r["date"].dt.month).size()
    return pd.DataFrame({
        "month": s.index,
        "index": (s / s.mean()).values,
        "reviews": s.values,
        "name": [pd.Timestamp(2016, m, 1).strftime("%b") for m in s.index],
    })


@lru_cache(maxsize=None)
def dow_curve() -> pd.DataFrame:
    """Blocked rate by day of week.

    A market driven by guest bookings peaks hard on Fri/Sat. A flat profile is
    evidence the 'f' flag is dominated by multi-day host blocks instead.
    """
    c = da.load("l0_calendar")
    g = c.groupby("dow")["is_booked"].mean().reset_index()
    g["name"] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return g


@lru_cache(maxsize=None)
def price_turnover_gap(min_listings: int = 20) -> pd.DataFrame:
    """Rank divergence between what a neighbourhood asks and how fast it turns over.

    Levels are not comparable across a 2.5x price range, so both measures are
    converted to percentile ranks and the story is the gap between them.
    """
    k = da.kpi_neighbourhood()
    k = k[k["listings"] >= min_listings].copy()
    k["adr_pct"] = k["asking_adr"].rank(pct=True)
    k["vel_pct"] = k["review_velocity"].rank(pct=True)
    k["gap"] = k["adr_pct"] - k["vel_pct"]
    return k.sort_values("gap")


@lru_cache(maxsize=None)
def sentiment_spread() -> dict:
    k = da.kpi_neighbourhood()
    s = k["sentiment_index"].dropna()
    return {"min": float(s.min()), "max": float(s.max()),
            "sd": float(s.std()), "mean": float(s.mean())}
