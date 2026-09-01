"""
Report figures for Task 1 -- grammar vs idiom, temporal and spatial.

Reuses the same data the dashboards read (app/data_access.py, app/story_data.py)
so every figure here is consistent with what the dashboards show; nothing is
recomputed differently for the report.

One deliberate exception, figure 3. The dashboard draws its map through
MapLibre/WebGL, which Kaleido's headless Chrome cannot rasterise -- exporting it
yields an empty canvas, which is what the previous fig3_idiom_map.png was.
Figure 3 therefore composites raster tiles server-side (src/staticmap.py) and
draws the points as an ordinary Cartesian scatter in Web-Mercator coordinates:
same projection, same ramp, an equivalent light-grey canvas basemap, no GPU.

Run:  .venv/bin/python src/make_task1_figures.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "src"))

import plotly.graph_objects as go

import data_access as da
import staticmap as sm
import story_data as sd
from theme import CATEGORICAL, CHROME, SEQUENTIAL, tpl

OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
MODE = "light"
SEQ = [[i / (len(SEQUENTIAL) - 1), h] for i, h in enumerate(SEQUENTIAL)]
c, blue = CHROME[MODE], CATEGORICAL[MODE][0]


def save(fig, name, w=820, h=340):
    fig.write_image(str(OUT / name), width=w, height=h, scale=2)
    print("wrote", name)


# ---- Fig 1: idiom-first temporal (weekly line, calendar time on x) --------
g = da.kpi_market().sort_values("week")
f1 = go.Figure()
f1.add_trace(go.Scatter(x=g["week"], y=g["blocked_rate"], mode="lines",
                        line=dict(width=2, color=blue),
                        hovertemplate="%{x|%d %b %Y}<br>Blocked %{y:.1%}<extra></extra>"))
f1.update_layout(template=tpl(MODE), showlegend=False,
                 margin=dict(l=8, r=8, t=20, b=8),
                 yaxis=dict(tickformat=".0%", rangemode="tozero", title="Blocked rate"),
                 xaxis=dict(showgrid=False, title="Calendar date (idiom: time on x)"))
save(f1, "fig1_idiom_calendar.png")

# ---- Fig 2: grammar-first temporal (horizon on x) --------------------------
h = sd.horizon_curve()
f2 = go.Figure()
f2.add_trace(go.Scatter(x=h["horizon"], y=h["blocked_rate"], mode="markers",
                        marker=dict(size=3.5, color=blue, opacity=0.28), hoverinfo="skip"))
f2.add_trace(go.Scatter(x=h["horizon"], y=h["blocked_smooth"], mode="lines",
                        line=dict(width=2, color=blue),
                        hovertemplate="%{x} days ahead<br>Blocked %{y:.1%}<extra></extra>"))
f2.update_layout(template=tpl(MODE), showlegend=False,
                 margin=dict(l=8, r=8, t=20, b=8),
                 yaxis=dict(tickformat=".0%", rangemode="tozero", title="Blocked rate"),
                 xaxis=dict(showgrid=False,
                            title="Days ahead of scrape (grammar: free choice of x)"))
save(f2, "fig2_grammar_calendar.png")

# ---- shared spatial encoding ---------------------------------------------
# RevPAN proxy is heavily right-skewed (median 17, p95 148, max 517). On a
# linear 0-max ramp the median listing lands at 3% of the scale and the whole
# city reads as one flat pale wash, in BOTH figures. Capping at p95 and saying
# so on the colourbar keeps the encoding honest while making it legible; the
# cap is identical in figures 3 and 4 so the idiom/grammar comparison is still
# a like-for-like one.
lst = da.listings().dropna(subset=["latitude", "longitude", "revpan_proxy"])
CMAX = float(lst["revpan_proxy"].quantile(0.95))
CBAR = dict(title=dict(text="RevPAN<br>proxy", font=dict(size=11)),
            thickness=9, len=0.66, y=0.44, yanchor="middle",
            outlinewidth=0, tickfont=dict(size=10),
            tickvals=[0, 25, 50, 75, 100, 125, CMAX],
            ticktext=["0", "25", "50", "75", "100", "125", f"{CMAX:.0f}+"])

MAP_W, MAP_H = 760, 620
PLOT_W = MAP_W - 120                      # colourbar + margins take the rest

# ---- Fig 3: idiom-first spatial (map idiom, basemap tiles) -----------------
lon_r, lat_r = sm.fit_bounds(lst["longitude"], lst["latitude"],
                             pad=0.08, aspect=(MAP_H - 16) / PLOT_W)
f3 = go.Figure()
f3.update_layout(template=tpl(MODE), showlegend=False,
                 margin=dict(l=8, r=8, t=8, b=8))
project = sm.basemap(f3, lon_r, lat_r, device_px=PLOT_W * 2,
                     style=CHROME[MODE]["map_style"])
mx, my = project(lst["longitude"], lst["latitude"])
f3.add_trace(go.Scatter(
    x=mx, y=my, mode="markers", customdata=lst[["revpan_proxy"]],
    marker=dict(size=6, color=lst["revpan_proxy"], colorscale=SEQ,
                cmin=0, cmax=CMAX, opacity=0.82, line=dict(width=0),
                colorbar=CBAR),
    hovertemplate="RevPAN proxy %{customdata[0]:,.1f}<extra></extra>"))
save(f3, "fig3_idiom_map.png", w=MAP_W, h=MAP_H)

# ---- Fig 4: grammar-first spatial (bare Cartesian scatter, no basemap) -----
# Position = lat/long as plain x/y encoding channels. Nothing beyond the four
# stated channels (x, y, colour, and the axis scales themselves) is asserted --
# no basemap, no implied streets or boundaries, no Mercator area distortion.
# The plot box is sized to the data so the equal-scale constraint does not
# leave two thirds of the panel empty.
f4 = go.Figure()
f4.add_trace(go.Scatter(
    x=lst["longitude"], y=lst["latitude"], mode="markers",
    marker=dict(size=6, color=lst["revpan_proxy"], colorscale=SEQ,
                cmin=0, cmax=CMAX, opacity=0.75, line=dict(width=0),
                colorbar=CBAR),
    hovertemplate="lon %{x:.3f}, lat %{y:.3f}<br>"
                  "RevPAN proxy %{marker.color:,.1f}<extra></extra>"))
f4.update_layout(template=tpl(MODE), showlegend=False,
                 margin=dict(l=8, r=8, t=20, b=8),
                 xaxis=dict(title="longitude (grammar: bare position channel)",
                            scaleanchor="y", scaleratio=1, constrain="domain"),
                 yaxis=dict(title="latitude", constrain="domain"))
save(f4, "fig4_grammar_scatter.png", w=MAP_W, h=MAP_H)

print("done ->", OUT)
