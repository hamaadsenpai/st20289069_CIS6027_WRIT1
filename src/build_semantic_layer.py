"""
Build the three-tier semantic layer for CIS6027 WRIT1.

    L0  atomic grain      one listing / one calendar-night / one review / one amenity
    L1  aggregates        listing-month, neighbourhood-week, review-month
    L2  KPIs              neighbourhood scorecards, market time-series, listing scorecards

Source: Seattle Airbnb Open Data (Kaggle: airbnb/seattle).
Outputs Parquet to data/ so dashboard callbacks read pre-computed frames.

Run:  .venv/bin/python src/build_semantic_layer.py
"""

import ast
import csv
import io
import json
import re
from pathlib import Path

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)

MONEY = re.compile(r"[^0-9.]")


def money(s: pd.Series) -> pd.Series:
    """'$1,250.00' -> 1250.0"""
    return pd.to_numeric(s.astype("string").str.replace(MONEY, "", regex=True), errors="coerce")


def pct(s: pd.Series) -> pd.Series:
    """'96%' -> 0.96"""
    return pd.to_numeric(s.astype("string").str.rstrip("%"), errors="coerce") / 100.0


def parse_amenities(cell) -> list[str]:
    """'{TV,"Cable TV",Internet}' -> ['TV', 'Cable TV', 'Internet']

    Brace-delimited set with quoted multi-word members: the semi-structured
    payload embedded inside an otherwise flat CSV cell.
    """
    if not isinstance(cell, str):
        return []
    inner = cell.strip().lstrip("{").rstrip("}")
    if not inner:
        return []
    row = next(csv.reader(io.StringIO(inner)), [])
    return [a.strip().strip('"') for a in row if a.strip().strip('"')]


def parse_verifications(cell) -> list[str]:
    """"['email', 'phone']" -> ['email', 'phone']"""
    if not isinstance(cell, str):
        return []
    try:
        val = ast.literal_eval(cell)
    except (ValueError, SyntaxError):
        return []
    return [str(v) for v in val] if isinstance(val, (list, tuple)) else []


# ---------------------------------------------------------------- L0: atomic

def build_l0():
    print("L0  reading raw files ...")
    listings = pd.read_csv(RAW / "listings.csv", low_memory=False)
    reviews = pd.read_csv(RAW / "reviews.csv")
    calendar = pd.read_csv(RAW / "calendar.csv")

    # --- l0_listing -------------------------------------------------------
    keep = {
        "id": "listing_id",
        "host_id": "host_id",
        "host_since": "host_since",
        "host_is_superhost": "host_is_superhost",
        "host_response_rate": "host_response_rate",
        "host_acceptance_rate": "host_acceptance_rate",
        "neighbourhood_cleansed": "neighbourhood",
        "neighbourhood_group_cleansed": "neighbourhood_group",
        "latitude": "latitude",
        "longitude": "longitude",
        "property_type": "property_type",
        "room_type": "room_type",
        "accommodates": "accommodates",
        "bathrooms": "bathrooms",
        "bedrooms": "bedrooms",
        "beds": "beds",
        "price": "price",
        "cleaning_fee": "cleaning_fee",
        "security_deposit": "security_deposit",
        "minimum_nights": "minimum_nights",
        "maximum_nights": "maximum_nights",
        "availability_365": "availability_365",
        "number_of_reviews": "number_of_reviews",
        "review_scores_rating": "review_scores_rating",
        "review_scores_cleanliness": "review_scores_cleanliness",
        "review_scores_location": "review_scores_location",
        "review_scores_value": "review_scores_value",
        "reviews_per_month": "reviews_per_month",
        "instant_bookable": "instant_bookable",
        "cancellation_policy": "cancellation_policy",
    }
    lst = listings[list(keep)].rename(columns=keep).copy()

    for col in ("price", "cleaning_fee", "security_deposit"):
        lst[col] = money(lst[col])
    for col in ("host_response_rate", "host_acceptance_rate"):
        lst[col] = pct(lst[col])
    for col in ("host_is_superhost", "instant_bookable"):
        lst[col] = lst[col].map({"t": True, "f": False})
    lst["host_since"] = pd.to_datetime(lst["host_since"], errors="coerce")

    lst.to_parquet(OUT / "l0_listing.parquet", index=False)

    # --- l0_amenity / l0_host_verification --------------------------------
    # Semi-structured -> normalised long form. This explode IS the abstraction
    # step Task 2 asks you to trace, so it stays a visible artefact.
    am = listings[["id", "amenities"]].copy()
    am["amenity"] = am["amenities"].map(parse_amenities)
    am = am.explode("amenity").dropna(subset=["amenity"])
    am = am[["id", "amenity"]].rename(columns={"id": "listing_id"})
    am.to_parquet(OUT / "l0_amenity.parquet", index=False)

    hv = listings[["host_id", "host_verifications"]].drop_duplicates("host_id").copy()
    hv["verification"] = hv["host_verifications"].map(parse_verifications)
    hv = hv.explode("verification").dropna(subset=["verification"])
    hv = hv[["host_id", "verification"]]
    hv.to_parquet(OUT / "l0_host_verification.parquet", index=False)

    # --- l0_calendar ------------------------------------------------------
    cal = calendar.rename(columns={"listing_id": "listing_id"}).copy()
    cal["date"] = pd.to_datetime(cal["date"])
    cal["price"] = money(cal["price"])
    # 'f' = not available. NOTE: this conflates guest-booked with host-blocked.
    # The distinction is unrecoverable from this source; occupancy below is
    # therefore an upper bound. Task 2's grain-mismatch critique starts here.
    cal["is_booked"] = cal["available"].eq("f")
    cal["year"] = cal["date"].dt.year
    cal["month"] = cal["date"].dt.to_period("M").astype(str)
    cal["week"] = cal["date"].dt.to_period("W").dt.start_time
    cal["dow"] = cal["date"].dt.dayofweek
    cal["is_weekend"] = cal["dow"].isin([4, 5])
    cal = cal[["listing_id", "date", "year", "month", "week", "dow",
               "is_weekend", "is_booked", "price"]]
    cal.to_parquet(OUT / "l0_calendar.parquet", index=False)

    # --- l0_review --------------------------------------------------------
    rev = reviews.rename(columns={"id": "review_id"}).copy()
    rev["date"] = pd.to_datetime(rev["date"])
    rev = rev.dropna(subset=["comments"])
    rev["comments"] = rev["comments"].astype("string")
    rev["char_len"] = rev["comments"].str.len()
    rev["word_count"] = rev["comments"].str.split().str.len()
    # Crude language flag: VADER is English-only, so scoring non-English text
    # produces noise near 0. Flag it rather than silently averaging it in.
    ascii_ratio = rev["comments"].map(lambda s: sum(c.isascii() for c in s) / max(len(s), 1))
    rev["likely_english"] = ascii_ratio > 0.95

    print(f"L0  scoring sentiment on {len(rev):,} reviews ...")
    sia = SentimentIntensityAnalyzer()
    rev["sentiment"] = [sia.polarity_scores(t)["compound"] for t in rev["comments"]]
    rev.loc[~rev["likely_english"], "sentiment"] = pd.NA

    rev["month"] = rev["date"].dt.to_period("M").astype(str)
    rev["week"] = rev["date"].dt.to_period("W").dt.start_time
    rev = rev[["review_id", "listing_id", "date", "month", "week", "reviewer_id",
               "comments", "char_len", "word_count", "likely_english", "sentiment"]]
    rev.to_parquet(OUT / "l0_review.parquet", index=False)

    print(f"L0  listing={len(lst):,}  calendar={len(cal):,}  review={len(rev):,} "
          f" amenity={len(am):,}  host_verification={len(hv):,}")
    return lst, cal, rev, am


# ------------------------------------------------------------ L1: aggregates

def build_l1(lst, cal, rev):
    """
    IMPORTANT — what `price` actually means in this source.

    calendar.price is populated ONLY on nights where available == 't'
    (934,542 rows) and is null on every available == 'f' night (459,028 rows,
    zero prices). So the price series is the *asking price on open nights*,
    never a transacted rate on a sold night.

    Two consequences, both load-bearing:
      1. Realised revenue is not derivable from this dataset. Anything of the
         form price x booked_nights multiplies an open-night asking price by a
         blocked-night count -- two disjoint sets of nights. No such column is
         emitted here.
      2. 'occupancy' is not measurable either. available == 'f' conflates
         guest-booked with host-blocked, so the honest name is `blocked_rate`
         and it is an UPPER BOUND on true occupancy.

    Metrics are therefore named for what they measure: `asking_adr`,
    `blocked_rate`, and `revpan_proxy` (their product -- a comparative index,
    not a currency amount). All aggregates roll up from atomic sums so that
    revpan_proxy == asking_adr * blocked_rate holds exactly at every level;
    mean-of-means would break that identity wherever price and availability
    correlate.
    """
    print("L1  aggregating ...")
    geo = lst[["listing_id", "neighbourhood", "neighbourhood_group",
               "room_type", "property_type", "latitude", "longitude"]]

    # --- listing x month --------------------------------------------------
    lm = (cal.groupby(["listing_id", "month"], observed=True)
             .agg(nights=("date", "size"),
                  blocked_nights=("is_booked", "sum"),
                  price_sum=("price", "sum"),
                  open_nights=("price", "count"),
                  price_min=("price", "min"),
                  price_max=("price", "max"))
             .reset_index())
    lm["blocked_rate"] = lm["blocked_nights"] / lm["nights"]
    # asking_adr is NaN where a listing was blocked for the whole month and so
    # quoted no price at all -- 13,519 of 49,634 listing-months.
    lm["asking_adr"] = lm["price_sum"] / lm["open_nights"].replace(0, pd.NA)
    lm["revpan_proxy"] = lm["asking_adr"] * lm["blocked_rate"]
    lm = lm.merge(geo, on="listing_id", how="left")
    lm.to_parquet(OUT / "l1_listing_month.parquet", index=False)

    # --- neighbourhood x week --------------------------------------------
    cw = cal.merge(geo, on="listing_id", how="left")
    nw = (cw.groupby(["neighbourhood_group", "neighbourhood", "week"], observed=True)
            .agg(listings=("listing_id", "nunique"),
                 nights=("date", "size"),
                 blocked_nights=("is_booked", "sum"),
                 price_sum=("price", "sum"),
                 open_nights=("price", "count"))
            .reset_index())
    nw["blocked_rate"] = nw["blocked_nights"] / nw["nights"]
    nw["asking_adr"] = nw["price_sum"] / nw["open_nights"].replace(0, pd.NA)
    nw["revpan_proxy"] = nw["asking_adr"] * nw["blocked_rate"]
    nw.to_parquet(OUT / "l1_neighbourhood_week.parquet", index=False)

    # --- review volume / sentiment x listing x month ----------------------
    rm = (rev.groupby(["listing_id", "month"], observed=True)
             .agg(reviews=("review_id", "size"),
                  sentiment_mean=("sentiment", "mean"),
                  words_mean=("word_count", "mean"),
                  english_share=("likely_english", "mean"))
             .reset_index()
             .merge(geo, on="listing_id", how="left"))
    rm.to_parquet(OUT / "l1_review_month.parquet", index=False)

    print(f"L1  listing_month={len(lm):,}  neighbourhood_week={len(nw):,}  "
          f"review_month={len(rm):,}")
    return lm, nw, rm


# ------------------------------------------------------------------ L2: KPIs

def build_l2(lst, lm, nw, rm, rev, am):
    print("L2  computing KPIs ...")

    # --- neighbourhood scorecard -----------------------------------------
    supply = (lst.groupby(["neighbourhood_group", "neighbourhood"], observed=True)
                 .agg(listings=("listing_id", "nunique"),
                      hosts=("host_id", "nunique"),
                      median_price=("price", "median"),
                      mean_rating=("review_scores_rating", "mean"),
                      superhost_share=("host_is_superhost", "mean"),
                      lat=("latitude", "mean"),
                      lon=("longitude", "mean"))
                 .reset_index())

    # Roll up from atomic sums, not from means, so the identity holds.
    demand = (lm.groupby(["neighbourhood_group", "neighbourhood"], observed=True)
                .agg(nights=("nights", "sum"),
                     blocked_nights=("blocked_nights", "sum"),
                     price_sum=("price_sum", "sum"),
                     open_nights=("open_nights", "sum"))
                .reset_index())
    demand["blocked_rate"] = demand["blocked_nights"] / demand["nights"]
    demand["asking_adr"] = demand["price_sum"] / demand["open_nights"].replace(0, pd.NA)
    demand["revpan_proxy"] = demand["asking_adr"] * demand["blocked_rate"]
    demand = demand.drop(columns=["price_sum"])

    # Review velocity: reviews per listing per month over the review window.
    # A demand proxy, not a booking count -- only a minority of stays review.
    window_months = rev["date"].dt.to_period("M").nunique()
    voice = (rev.merge(lst[["listing_id", "neighbourhood_group", "neighbourhood"]],
                       on="listing_id", how="left")
                .groupby(["neighbourhood_group", "neighbourhood"], observed=True)
                .agg(reviews_total=("review_id", "size"),
                     sentiment_index=("sentiment", "mean"),
                     english_share=("likely_english", "mean"))
                .reset_index())

    kpi = supply.merge(demand, on=["neighbourhood_group", "neighbourhood"], how="left")
    kpi = kpi.merge(voice, on=["neighbourhood_group", "neighbourhood"], how="left")
    kpi["review_velocity"] = kpi["reviews_total"] / kpi["listings"] / window_months
    kpi.to_parquet(OUT / "l2_kpi_neighbourhood.parquet", index=False)

    # --- market-level weekly time series ---------------------------------
    market = (nw.groupby("week", observed=True)
                .agg(listings=("listings", "sum"),
                     nights=("nights", "sum"),
                     blocked_nights=("blocked_nights", "sum"),
                     price_sum=("price_sum", "sum"),
                     open_nights=("open_nights", "sum"))
                .reset_index())
    market["blocked_rate"] = market["blocked_nights"] / market["nights"]
    market["asking_adr"] = market["price_sum"] / market["open_nights"].replace(0, pd.NA)
    market["revpan_proxy"] = market["asking_adr"] * market["blocked_rate"]
    market.to_parquet(OUT / "l2_kpi_market.parquet", index=False)

    # --- listing scorecard ------------------------------------------------
    ls = (lm.groupby("listing_id", observed=True)
            .agg(nights=("nights", "sum"),
                 blocked_nights=("blocked_nights", "sum"),
                 price_sum=("price_sum", "sum"),
                 open_nights=("open_nights", "sum"))
            .reset_index())
    ls["blocked_rate"] = ls["blocked_nights"] / ls["nights"]
    ls["asking_adr"] = ls["price_sum"] / ls["open_nights"].replace(0, pd.NA)
    ls["revpan_proxy"] = ls["asking_adr"] * ls["blocked_rate"]
    ls = ls.drop(columns=["price_sum"])

    rs = (rm.groupby("listing_id", observed=True)
            .agg(reviews=("reviews", "sum"),
                 sentiment=("sentiment_mean", "mean"))
            .reset_index())
    amn = am.groupby("listing_id", observed=True).size().rename("amenity_count").reset_index()
    card = (lst.merge(ls, on="listing_id", how="left")
               .merge(rs, on="listing_id", how="left")
               .merge(amn, on="listing_id", how="left"))
    card["amenity_count"] = card["amenity_count"].fillna(0).astype(int)
    card.to_parquet(OUT / "l2_listing_scorecard.parquet", index=False)

    # --- amenity penetration ---------------------------------------------
    pen = (am.merge(lst[["listing_id", "neighbourhood_group", "room_type"]],
                    on="listing_id", how="left")
             .groupby(["amenity", "neighbourhood_group"], observed=True)
             .size().rename("listings").reset_index())
    totals = lst.groupby("neighbourhood_group", observed=True).size().rename("total").reset_index()
    pen = pen.merge(totals, on="neighbourhood_group", how="left")
    pen["penetration"] = pen["listings"] / pen["total"]
    pen.to_parquet(OUT / "l2_amenity_penetration.parquet", index=False)

    print(f"L2  kpi_neighbourhood={len(kpi):,}  kpi_market={len(market):,}  "
          f"listing_scorecard={len(card):,}  amenity_penetration={len(pen):,}")
    return kpi, market, card


# ------------------------------------------------------------------ lineage

def write_lineage():
    lineage = {
        "source": "Seattle Airbnb Open Data (Kaggle: airbnb/seattle)",
        "layers": {
            "L0_atomic": {
                "l0_listing": "one row per listing; money and percent strings cast to numeric",
                "l0_calendar": "one row per listing-night; available 't'/'f' -> is_booked bool",
                "l0_review": "one row per review; VADER compound sentiment, English-only",
                "l0_amenity": "amenities set exploded to one row per (listing, amenity)",
                "l0_host_verification": "host_verifications list exploded per (host, method)",
            },
            "L1_aggregate": {
                "l1_listing_month": "listing x month: blocked_rate, asking_adr, revpan_proxy",
                "l1_neighbourhood_week": "neighbourhood x week: occupancy, ADR, RevPAN",
                "l1_review_month": "listing x month: review volume, mean sentiment",
            },
            "L2_kpi": {
                "l2_kpi_neighbourhood": "supply + demand + voice per neighbourhood",
                "l2_kpi_market": "city-wide weekly occupancy / ADR / RevPAN",
                "l2_listing_scorecard": "per-listing KPI roll-up for ranking and drill-down",
                "l2_amenity_penetration": "amenity share of listings by neighbourhood group",
            },
        },
        "known_limitations": [
            "calendar.price is populated ONLY on available=='t' nights (934,542) and is null on all 459,028 unavailable nights -- it is an asking price on open nights, never a transacted rate. Realised revenue is NOT derivable; no revenue column is emitted.",
            "calendar 'f' conflates guest-booked with host-blocked, so blocked_rate is an UPPER BOUND on true occupancy, not a measurement of it",
            "revpan_proxy = asking_adr * blocked_rate is a comparative index, not a currency amount",
            "asking_adr is null for 13,519 of 49,634 listing-months where the listing was blocked all month and quoted no price",
            "review dates (2009-06-07..2016-01-03) do not overlap calendar (2016-01-04..2017-01-02)",
            "review velocity is a demand proxy: only a minority of stays leave a review",
            "VADER is English-only and lexicon-based; non-English reviews are nulled, not translated",
            "listing attributes are a single 2016-01-04 scrape, so they are not time-varying",
        ],
    }
    (OUT / "lineage.json").write_text(json.dumps(lineage, indent=2))


if __name__ == "__main__":
    lst, cal, rev, am = build_l0()
    lm, nw, rm = build_l1(lst, cal, rev)
    build_l2(lst, lm, nw, rm, rev, am)
    write_lineage()
    print("\ndone ->", OUT)
