"""
Dashboard 1 of 2 - exploratory. Filters, drill-down, what-if.

Run:  .venv/bin/python app/exploratory.py   ->  http://127.0.0.1:8050
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html

import data_access as da
from styles import CSS
from theme import CATEGORICAL, CHROME, SEQUENTIAL, tpl

MODE = "light"
C = CHROME[MODE]
COLORS = CATEGORICAL[MODE]
TPL = tpl(MODE)

OPTS = da.options()
WEEKS = OPTS["weeks"]
ROOM_ORDER = OPTS["room_types"]
ROOM_COLOR = {r: COLORS[i] for i, r in enumerate(ROOM_ORDER)}
SEQ = [[i / (len(SEQUENTIAL) - 1), h] for i, h in enumerate(SEQUENTIAL)]

# Per-listing RevPAN proxy is heavily right-skewed (median 17, p95 148, max 517).
# On a linear 0-max ramp the median listing sits at 3% of the scale and the whole
# city reads as one pale wash, so the map caps at p95 and says so on the colourbar
# -- the same cap report figures 3 and 4 use. Computed once on the unfiltered
# frame, so filtering never repaints the survivors.
CMAX = float(da.listings()["revpan_proxy"].quantile(0.95))
MAP_CBAR = dict(title=dict(text="RevPAN<br>proxy", font=dict(size=11)),
                thickness=9, len=0.66, y=0.44, yanchor="middle",
                outlinewidth=0, tickfont=dict(size=10),
                tickvals=[0, 25, 50, 75, 100, 125, CMAX],
                ticktext=["0", "25", "50", "75", "100", "125", f"{CMAX:.0f}+"])

# Drawable map area inside its card, in CSS pixels: the card is 360px tall and
# the colourbar eats the right ~75px of the 649px plot box.
MAP_PX = (560, 360)


def _merc_y(lat):
    """Web-Mercator northing normalised to the unit square, y down."""
    s = math.sin(math.radians(lat))
    return 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


def _map_view(lat, lon):
    """Centre and zoom that frame the current selection.

    px.scatter_map leaves layout.map.center empty, and MapLibre then defaults to
    lon/lat 0,0 -- at zoom 10 that is open ocean off West Africa, which is why
    the panel came up blank with every Seattle marker off-screen. Fitting the
    bounding box here also means drilling into one neighbourhood zooms to it.
    """
    lat0, lat1 = float(lat.min()), float(lat.max())
    lon0, lon1 = float(lon.min()), float(lon.max())
    centre = dict(lon=(lon0 + lon1) / 2,
                  lat=math.degrees(2 * math.atan(
                      math.exp((0.5 - (_merc_y(lat0) + _merc_y(lat1)) / 2) * 2 * math.pi))
                      - math.pi / 2))
    w, h = MAP_PX
    span_x = max((lon1 - lon0) / 360.0, 1e-7)
    span_y = max(_merc_y(lat0) - _merc_y(lat1), 1e-7)
    # MapLibre lays the world out over 512 * 2**zoom pixels.
    zoom = min(math.log2(w / (512 * span_x)), math.log2(h / (512 * span_y)))
    return centre, float(min(max(zoom - 0.3, 3.0), 14.5))


def card(title, graph_id, height=330):
    return html.Div(className="card", children=[
        html.H2(title),
        dcc.Graph(id=graph_id, config={"displayModeBar": False},
                  style={"height": f"{height}px"}),
    ])


def blank(msg):
    f = go.Figure()
    f.update_layout(template=TPL, xaxis_visible=False, yaxis_visible=False,
                    annotations=[dict(text=msg, showarrow=False,
                                      font=dict(color=C["muted"], size=13))])
    return f


app = Dash(__name__, title="Seattle Short-Let Explorer")
app.index_string = """<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>
{%favicon%}{%css%}<style>""" + CSS + """</style></head><body>
{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

app.layout = html.Div(className="wrap", children=[
    dcc.Store(id="sel", data={"neighbourhoods": []}),

    html.H1("Seattle short-let market"),

    html.Div(className="filters", children=[
        html.Div(className="f", children=[
            html.Label("Neighbourhood group"),
            dcc.Dropdown(id="f-group", options=OPTS["groups"], multi=True,
                         placeholder="All"),
        ]),
        html.Div(className="f", children=[
            html.Label("Room type"),
            dcc.Dropdown(id="f-room", options=ROOM_ORDER, multi=True, placeholder="All"),
        ]),
        html.Div(className="f", children=[
            html.Label("Listed price (USD/night)"),
            dcc.RangeSlider(id="f-price", min=0, max=OPTS["price_max"], step=25,
                            value=[0, OPTS["price_max"]],
                            tooltip={"placement": "bottom", "always_visible": False},
                            marks={0: "$0",
                                   int(OPTS["price_p99"]): f"${int(OPTS['price_p99'])}",
                                   int(OPTS["price_max"]): f"${int(OPTS['price_max'])}"}),
        ]),
        html.Div(className="f", children=[
            html.Label("Calendar window"),
            dcc.RangeSlider(id="f-week", min=0, max=len(WEEKS) - 1, step=1,
                            value=[0, len(WEEKS) - 1],
                            marks={0: str(pd.Timestamp(WEEKS[0]).date()),
                                   len(WEEKS) - 1: str(pd.Timestamp(WEEKS[-1]).date())},
                            tooltip={"placement": "bottom", "always_visible": False}),
        ]),
        html.Div(className="f", children=[
            html.Label(id="drill"),
            html.Button("Clear selection", id="clear", n_clicks=0),
        ]),
    ]),

    html.Div(className="grid g2", children=[
        card("Listings by neighbourhood, shaded by RevPAN proxy", "fig-treemap", 360),
        card("Listing locations, shaded by RevPAN proxy", "fig-map", 360),
    ]),

    html.Div(className="grid g2", children=[
        card("Blocked rate by week", "fig-blocked", 260),
        card("Asking price by week", "fig-adr", 260),
    ]),

    html.Div(className="grid g2", children=[
        card("RevPAN proxy by neighbourhood group and room type", "fig-room", 320),
        card("What-if: RevPAN proxy under a price change", "fig-whatif", 320),
    ]),

    html.Div(className="filters", style={"gridTemplateColumns": "1fr 1fr"}, children=[
        html.Div(className="f", children=[
            html.Label("Price change"),
            dcc.Slider(id="w-price", min=-30, max=30, step=5, value=0,
                       marks={-30: "-30%", 0: "0", 30: "+30%"},
                       tooltip={"placement": "bottom", "always_visible": True}),
        ]),
        html.Div(className="f", children=[
            html.Label("Assumed demand elasticity"),
            dcc.Slider(id="w-elast", min=0, max=2.5, step=0.25, value=1.0,
                       marks={0: "0", 1: "1", 2.5: "2.5"},
                       tooltip={"placement": "bottom", "always_visible": True}),
        ]),
    ]),
])


@app.callback(Output("sel", "data"), Output("drill", "children"),
              Input("fig-treemap", "clickData"), Input("fig-map", "clickData"),
              Input("clear", "n_clicks"), State("sel", "data"))
def _select(tree_click, map_click, _clear, sel):
    """Treemap and map write the same selection key, so views stay coordinated."""
    trigger = ctx.triggered_id
    picked = list(sel.get("neighbourhoods", []))

    if trigger == "clear":
        picked = []
    elif trigger == "fig-treemap" and tree_click:
        label = tree_click["points"][0].get("label")
        if tree_click["points"][0].get("parent"):    # a leaf, not a group header
            picked = [] if label in picked else [label]
    elif trigger == "fig-map" and map_click:
        cd = map_click["points"][0].get("customdata")
        if cd:
            picked = [] if cd[0] in picked else [cd[0]]

    return {"neighbourhoods": picked}, picked[0] if picked else "Whole city"


FILTER_INPUTS = [Input("f-group", "value"), Input("f-room", "value"),
                 Input("f-price", "value"), Input("f-week", "value"),
                 Input("sel", "data")]


def _slice(groups, rooms, price, weeks, sel):
    """Resolve the shared filter state into the frames the charts need."""
    picked = (sel or {}).get("neighbourhoods") or None
    wk = (WEEKS[weeks[0]], WEEKS[weeks[1]])

    lst = da.apply_filters(da.listings(), groups, rooms, picked, price)
    ids = set(lst["listing_id"])

    nw = da.apply_filters(da.neighbourhood_week(), groups, None, picked, None, wk)

    lm = da.listing_month()
    lm = lm[lm["listing_id"].isin(ids)]
    return lst, nw, lm


@app.callback(Output("fig-treemap", "figure"), *FILTER_INPUTS)
def _treemap(groups, rooms, price, weeks, sel):
    _, nw, _ = _slice(groups, rooms, price, weeks, sel)
    if nw.empty:
        return blank("No neighbourhoods match these filters")
    g = da.rollup(nw, ["neighbourhood_group", "neighbourhood"])
    g = g[g["listings"] > 0]
    f = px.treemap(g, path=[px.Constant("Seattle"), "neighbourhood_group", "neighbourhood"],
                   values="listings", color="revpan_proxy",
                   color_continuous_scale=SEQ,
                   custom_data=["blocked_rate", "asking_adr", "revpan_proxy"])
    f.update_traces(
        marker=dict(cornerradius=4, line=dict(width=2, color=C["surface"])),
        hovertemplate="<b>%{label}</b><br>%{value} listings<br>"
                      "Blocked %{customdata[0]:.1%}<br>Asking ADR $%{customdata[1]:,.0f}<br>"
                      "RevPAN proxy %{customdata[2]:,.1f}<extra></extra>",
        tiling=dict(pad=2))
    f.update_layout(
        template=TPL, margin=dict(l=6, r=6, t=6, b=6),
        uniformtext=dict(minsize=9, mode="hide"),
        coloraxis_colorbar=dict(title=dict(text="RevPAN<br>proxy", font=dict(size=11)),
                                thickness=9, len=0.72, outlinewidth=0,
                                tickfont=dict(size=10)))
    f.data[0].root = dict(color=C["plane"])
    return f


@app.callback(Output("fig-map", "figure"), *FILTER_INPUTS)
def _map(groups, rooms, price, weeks, sel):
    lst, _, _ = _slice(groups, rooms, price, weeks, sel)
    d = lst.dropna(subset=["latitude", "longitude", "revpan_proxy"])
    if d.empty:
        return blank("No priced listings in this selection")
    centre, zoom = _map_view(d["latitude"], d["longitude"])
    f = px.scatter_map(
        d, lat="latitude", lon="longitude", color="revpan_proxy",
        color_continuous_scale=SEQ, range_color=(0, CMAX), opacity=0.82,
        center=centre, zoom=zoom,
        custom_data=["neighbourhood", "room_type", "price", "blocked_rate", "revpan_proxy"])
    f.update_traces(
        marker=dict(size=8),
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                      "Listed $%{customdata[2]:,.0f}/night<br>Blocked %{customdata[3]:.1%}<br>"
                      "RevPAN proxy %{customdata[4]:,.1f}<extra></extra>")
    f.update_layout(template=TPL, map_style=C["map_style"],
                    margin=dict(l=0, r=0, t=0, b=0),
                    coloraxis_colorbar=MAP_CBAR)
    return f


def _weekly(nw, col, label):
    if nw.empty:
        return blank("No calendar rows in this window")
    g = da.rollup(nw, "week").sort_values("week")
    pct = col == "blocked_rate"
    f = go.Figure()
    f.add_trace(go.Scatter(
        x=g["week"], y=g[col], mode="lines", line=dict(width=2, color=COLORS[0]),
        hovertemplate="%{x|%d %b %Y}<br>" + label +
                      (" %{y:.1%}" if pct else " $%{y:,.0f}") + "<extra></extra>"))
    f.update_layout(
        template=TPL, showlegend=False, hovermode="x unified",
        margin=dict(l=8, r=12, t=10, b=8),
        yaxis=dict(title=dict(text=label), tickformat=".0%" if pct else "$,.0f"),
        xaxis=dict(showgrid=False))
    return f


@app.callback(Output("fig-blocked", "figure"), *FILTER_INPUTS)
def _blocked(groups, rooms, price, weeks, sel):
    _, nw, _ = _slice(groups, rooms, price, weeks, sel)
    return _weekly(nw, "blocked_rate", "Blocked rate")


@app.callback(Output("fig-adr", "figure"), *FILTER_INPUTS)
def _adr(groups, rooms, price, weeks, sel):
    _, nw, _ = _slice(groups, rooms, price, weeks, sel)
    return _weekly(nw, "asking_adr", "Asking ADR")


@app.callback(Output("fig-room", "figure"), *FILTER_INPUTS)
def _room(groups, rooms, price, weeks, sel):
    lst, _, lm = _slice(groups, rooms, price, weeks, sel)
    if lm.empty:
        return blank("No listing-months match these filters")
    d = lm[lm["listing_id"].isin(set(lst["listing_id"]))]
    g = (d.groupby(["neighbourhood_group", "room_type"], observed=True)
           .agg(nights=("nights", "sum"), blocked=("blocked_nights", "sum"),
                psum=("price_sum", "sum"), open_n=("open_nights", "sum"))
           .reset_index())
    g["blocked_rate"] = g["blocked"] / g["nights"]
    g["asking_adr"] = g["psum"] / g["open_n"].replace(0, pd.NA)
    g["revpan_proxy"] = g["asking_adr"] * g["blocked_rate"]
    g = g.dropna(subset=["revpan_proxy"])
    if g.empty:
        return blank("No priced nights in this selection")

    order = (g.groupby("neighbourhood_group")["revpan_proxy"].mean()
              .sort_values(ascending=False).index.tolist())
    f = go.Figure()
    for rt in ROOM_ORDER:                            # fixed order -> fixed hue
        s = g[g["room_type"] == rt].set_index("neighbourhood_group").reindex(order)
        if s["revpan_proxy"].isna().all():
            continue
        f.add_trace(go.Bar(
            x=order, y=s["revpan_proxy"], name=rt,
            marker=dict(color=ROOM_COLOR[rt], cornerradius=4,
                        line=dict(width=2, color=C["surface"])),
            hovertemplate=f"<b>{rt}</b> · %{{x}}<br>RevPAN proxy %{{y:,.1f}}<extra></extra>"))
    f.update_layout(template=TPL, barmode="group", bargap=0.28, bargroupgap=0.04,
                    margin=dict(l=8, r=8, t=8, b=8),
                    xaxis=dict(showgrid=False, tickangle=-32, tickfont=dict(size=10)),
                    yaxis=dict(title=dict(text="RevPAN proxy")),
                    legend=dict(orientation="h", y=1.06, x=0))
    return f


@app.callback(Output("fig-whatif", "figure"), *FILTER_INPUTS,
              Input("w-price", "value"), Input("w-elast", "value"))
def _whatif(groups, rooms, price, weeks, sel, dp, elast):
    """Constant elasticity: demand scales (1+dp)^-e, so RevPAN scales (1+dp)^(1-e)."""
    _, nw, _ = _slice(groups, rooms, price, weeks, sel)
    if nw.empty:
        return blank("No calendar rows in this window")
    g = da.rollup(nw, "week").sort_values("week")
    mult = 1 + dp / 100.0
    g["scenario"] = g["revpan_proxy"] * mult ** (1 - elast)

    f = go.Figure()
    f.add_trace(go.Scatter(x=g["week"], y=g["revpan_proxy"], mode="lines", name="Baseline",
                           line=dict(width=2, color=COLORS[0]),
                           hovertemplate="Baseline %{y:,.1f}<extra></extra>"))
    f.add_trace(go.Scatter(x=g["week"], y=g["scenario"], mode="lines",
                           name=f"{dp:+d}% at e={elast:g}",
                           line=dict(width=2, color=COLORS[1], dash="dot"),
                           hovertemplate="Scenario %{y:,.1f}<extra></extra>"))
    f.update_layout(template=TPL, hovermode="x unified",
                    margin=dict(l=8, r=8, t=8, b=8), xaxis=dict(showgrid=False),
                    yaxis=dict(title=dict(text="RevPAN proxy")),
                    legend=dict(orientation="h", y=1.06, x=0))
    return f


if __name__ == "__main__":
    app.run(debug=False, port=8050)
