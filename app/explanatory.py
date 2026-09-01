"""
Dashboard 2 of 2 - explanatory. Fixed sequence, no filters.

Run:  .venv/bin/python app/explanatory.py   ->  http://127.0.0.1:8051
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html

import data_access as da
import story_data as sd
from styles import CSS
from theme import CATEGORICAL, CHROME, FONT, STATUS, tpl

MODE = "light"
C = CHROME[MODE]
COLORS = CATEGORICAL[MODE]
TPL = tpl(MODE)
BLUE = COLORS[0]

SPEARMAN = sd.horizon_spearman()
ROOM_ORDER = da.options()["room_types"]
ROOM_COLOR = {r: COLORS[i] for i, r in enumerate(ROOM_ORDER)}


def card(title, figure, height=340):
    return html.Div(className="card", children=[
        html.H2(title),
        dcc.Graph(figure=figure, config={"displayModeBar": False},
                  style={"height": f"{height}px"}),
    ])


def _base(fig, **kw):
    fig.update_layout(template=TPL, showlegend=kw.pop("legend", False),
                      margin=kw.pop("margin", dict(l=8, r=8, t=10, b=8)), **kw)
    return fig


# ------------------------------------------------------------------ figures

def act1():
    g = da.kpi_market().sort_values("week")
    f = go.Figure()
    f.add_trace(go.Scatter(x=g["week"], y=g["blocked_rate"], mode="lines",
                           line=dict(width=2, color=BLUE),
                           hovertemplate="%{x|%d %b %Y}<br>Blocked %{y:.1%}<extra></extra>"))
    return _base(f, hovermode="x unified",
                 yaxis=dict(title=dict(text="Blocked rate"), tickformat=".0%",
                            rangemode="tozero"),
                 xaxis=dict(title=dict(text="Week"), showgrid=False))


def act2():
    g = sd.horizon_curve()
    f = go.Figure()
    f.add_trace(go.Scatter(x=g["horizon"], y=g["blocked_rate"], mode="markers",
                           marker=dict(size=3.5, color=BLUE, opacity=0.28),
                           hoverinfo="skip"))
    f.add_trace(go.Scatter(x=g["horizon"], y=g["blocked_smooth"], mode="lines",
                           line=dict(width=2, color=BLUE),
                           hovertemplate="%{x} days ahead<br>Blocked %{y:.1%}<extra></extra>"))
    return _base(f, hovermode="x unified",
                 yaxis=dict(title=dict(text="Blocked rate"), tickformat=".0%",
                            rangemode="tozero"),
                 xaxis=dict(title=dict(text="Days ahead of the 4 Jan 2016 scrape"),
                            showgrid=False))


def act3():
    g = sd.review_seasonality()
    f = go.Figure()
    f.add_trace(go.Bar(
        x=g["name"], y=g["index"],
        marker=dict(color=BLUE, cornerradius=4, line=dict(width=2, color=C["surface"])),
        hovertemplate="<b>%{x}</b><br>%{y:.2f}x the annual mean<extra></extra>"))
    f.add_hline(y=1.0, line=dict(width=1, color=C["axis"]))
    return _base(f, bargap=0.32,
                 yaxis=dict(title=dict(text="Index (1.0 = annual mean)"), rangemode="tozero"),
                 xaxis=dict(title=dict(text="Month"), showgrid=False))


def act4():
    g = sd.horizon_curve()
    f = go.Figure()
    f.add_vrect(x0=120, x1=240, fillcolor=BLUE, opacity=0.07, line_width=0,
                annotation_text="May - Aug", annotation_position="top left",
                annotation_font=dict(size=11.5, color=C["muted"]))
    f.add_trace(go.Scatter(x=g["horizon"], y=g["blocked_smooth"], mode="lines",
                           line=dict(width=2, color=BLUE),
                           hovertemplate="%{x} days ahead<br>Blocked %{y:.1%}<extra></extra>"))
    return _base(f, hovermode="x unified",
                 yaxis=dict(title=dict(text="Blocked rate (14-day mean)"),
                            tickformat=".0%", rangemode="tozero"),
                 xaxis=dict(title=dict(text="Days ahead of scrape"), showgrid=False))


def act5():
    g = sd.dow_curve()
    f = go.Figure()
    f.add_trace(go.Bar(
        x=g["name"], y=g["is_booked"],
        marker=dict(color=STATUS["warning"], cornerradius=4,
                    line=dict(width=2, color=C["surface"])),
        hovertemplate="<b>%{x}</b><br>Blocked %{y:.2%}<extra></extra>"))
    return _base(f, bargap=0.34,
                 yaxis=dict(title=dict(text="Blocked rate"), tickformat=".0%",
                            rangemode="tozero", range=[0, 0.5]),
                 xaxis=dict(title=dict(text="Day of week"), showgrid=False))


def act6():
    g = sd.price_turnover_gap()
    g = pd.concat([g.head(6), g.tail(6)]).sort_values("gap")
    f = go.Figure()
    for r in g.itertuples():                       # connector first, dots on top
        f.add_trace(go.Scatter(
            x=[r.adr_pct, r.vel_pct], y=[r.neighbourhood, r.neighbourhood],
            mode="lines", line=dict(width=1.5, color=C["grid"]),
            showlegend=False, hoverinfo="skip"))
    f.add_trace(go.Scatter(
        x=g["adr_pct"], y=g["neighbourhood"], mode="markers", name="Asking price rank",
        marker=dict(size=11, color=COLORS[0], line=dict(width=2, color=C["surface"])),
        hovertemplate="<b>%{y}</b><br>Price rank %{x:.0%}<extra></extra>"))
    f.add_trace(go.Scatter(
        x=g["vel_pct"], y=g["neighbourhood"], mode="markers", name="Turnover rank",
        marker=dict(size=11, symbol="diamond", color=COLORS[1],
                    line=dict(width=2, color=C["surface"])),
        hovertemplate="<b>%{y}</b><br>Turnover rank %{x:.0%}<extra></extra>"))
    return _base(f, legend=True, margin=dict(l=8, r=8, t=34, b=8),
                 xaxis=dict(tickformat=".0%", range=[-0.04, 1.04],
                            title=dict(text="Percentile rank among 46 neighbourhoods")),
                 yaxis=dict(showgrid=False, tickfont=dict(size=11.5)))


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


PRICE_TIERS = ["Budget (<$100)", "Mid ($100-199)", "Premium ($200+)"]


def _price_tier(p):
    if p < 100:
        return PRICE_TIERS[0]
    if p < 200:
        return PRICE_TIERS[1]
    return PRICE_TIERS[2]


def act7():
    """Neighbourhood group -> room type -> price tier, top 5 groups plus a fold."""
    lst = da.listings().dropna(subset=["neighbourhood_group", "room_type", "price"]).copy()
    named = lst.loc[lst["neighbourhood_group"] != "Other neighborhoods", "neighbourhood_group"]
    top_groups = named.value_counts().head(5).index.tolist()
    lst["group"] = lst["neighbourhood_group"].where(
        lst["neighbourhood_group"].isin(top_groups), "Rest of Seattle")
    lst["tier"] = lst["price"].map(_price_tier)

    groups = lst.groupby("group").size().sort_values(ascending=False).index.tolist()
    nodes = groups + ROOM_ORDER + PRICE_TIERS
    idx = {n: i for i, n in enumerate(nodes)}
    node_color = ([C["axis"]] * len(groups) + [ROOM_COLOR[r] for r in ROOM_ORDER]
                  + [C["axis"]] * len(PRICE_TIERS))

    stage1 = lst.groupby(["group", "room_type"]).size().reset_index(name="n")
    stage2 = lst.groupby(["room_type", "tier"]).size().reset_index(name="n")

    src, tgt, val, link_color = [], [], [], []
    for r in stage1.itertuples():
        src.append(idx[r.group]); tgt.append(idx[r.room_type]); val.append(r.n)
        link_color.append(_rgba(ROOM_COLOR[r.room_type], 0.28))
    for r in stage2.itertuples():
        src.append(idx[r.room_type]); tgt.append(idx[r.tier]); val.append(r.n)
        link_color.append(_rgba(ROOM_COLOR[r.room_type], 0.28))

    f = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nodes, color=node_color, pad=14, thickness=14,
                  line=dict(width=0),
                  hovertemplate="<b>%{label}</b><br>%{value:,} listings<extra></extra>"),
        link=dict(source=src, target=tgt, value=val, color=link_color,
                  hovertemplate="<b>%{source.label} -> %{target.label}</b><br>"
                                "%{value:,} listings<extra></extra>"),
        textfont=dict(color=C["ink"], size=12, family=FONT),
    ))
    f.update_layout(template=TPL, margin=dict(l=8, r=8, t=8, b=8),
                    font=dict(color=C["ink"]))
    return f


# ------------------------------------------------------------------- layout

app = Dash(__name__, title="Seattle Short-Let Findings")
app.index_string = """<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>
{%favicon%}{%css%}<style>""" + CSS + """</style></head><body>
{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

app.layout = html.Div(className="wrap", children=[
    html.H1("Seattle short-let market: what the calendar data supports"),

    html.Div(className="grid g2", children=[
        card("1. Blocked rate by week, as the source presents it", act1(), 300),
        card(f"2. Same rows by booking horizon (Spearman rho = {SPEARMAN:.2f})",
             act2(), 300),
    ]),

    html.Div(className="grid g3", children=[
        card("3. Review seasonality, 2013-2015", act3(), 285),
        card("4. Blocked rate by horizon, May-August marked", act4(), 285),
        card("5. Blocked rate by day of week", act5(), 285),
    ]),

    html.Div(className="grid g2", children=[
        card("6. Asking price rank vs review velocity rank", act6(), 430),
        card("7. Neighbourhood group to room type to price tier", act7(), 430),
    ]),
])


if __name__ == "__main__":
    app.run(debug=False, port=8051)
