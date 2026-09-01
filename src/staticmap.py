"""
Static raster basemap for report figures.

Why this exists
---------------
The dashboards draw their map with `px.scatter_map`, which renders through
MapLibre on a WebGL canvas. That is correct in a browser, but Kaleido's
headless Chrome exports the figure without a usable WebGL context: the map
canvas comes back empty, so the exported PNG has no basemap AND no markers --
only the SVG colourbar survives. That is what produced the blank
fig3_idiom_map.png.

The fix is to stop asking a headless browser to composite a map. Here the
basemap is assembled server-side instead: CARTO Positron raster tiles are
fetched over HTTP, placed as `layout.images` in Web-Mercator tile coordinates,
and the listings are drawn on top as an ordinary Cartesian scatter. Everything
then exports through Plotly's normal SVG/raster path, which Kaleido handles
reliably.

The result is the same idiom the dashboard shows -- same projection, same
sequential ramp, an equivalent light-grey canvas basemap -- but reproducible
offline once the tiles are cached in `.tilecache/`.

Tile source: Esri Light/Dark Gray Canvas rather than CARTO Positron. CARTO's
raster endpoint now stamps "API KEY REQUIRED" across every unkeyed tile, which
is unusable in a report; Esri's legacy ArcGIS Online canvas services are still
open and are the closest unkeyed match to Positron's styling.
"""

from __future__ import annotations

import math
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".tilecache"

_ESRI = ("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
         "World_{v}_Gray_{layer}/MapServer/tile/{z}/{y}/{x}")

# Keyed by the app/theme.py map_style values so callers can pass CHROME[mode]
# straight through. Each style is (base layer, label overlay).
TILE_URL = {
    "carto-positron": (_ESRI.replace("{v}", "Light").replace("{layer}", "Base"),
                       _ESRI.replace("{v}", "Light").replace("{layer}", "Reference")),
    "carto-darkmatter": (_ESRI.replace("{v}", "Dark").replace("{layer}", "Base"),
                         _ESRI.replace("{v}", "Dark").replace("{layer}", "Reference")),
}
ATTRIBUTION = "Basemap: Esri, HERE, Garmin  ·  © OpenStreetMap contributors"


# ---------------------------------------------------------------- projection

def merc(lon: float, lat: float) -> tuple[float, float]:
    """Web-Mercator (EPSG:3857) normalised to the unit square, y down."""
    x = lon / 360.0 + 0.5
    s = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    return x, y


def merc_x(lon):
    return lon / 360.0 + 0.5


def merc_y(lat):
    import numpy as np
    s = np.sin(np.radians(lat))
    return 0.5 - np.log((1 + s) / (1 - s)) / (4 * np.pi)


# ------------------------------------------------------------------ tiles

def _tile(template: str, z: int, x: int, y: int) -> str | None:
    """Return a tile as a base64 data URI, fetching and caching on first use.

    Returns None for a tile the service does not have (label overlays are
    sparse -- most tiles carry no place name at all).
    """
    import base64
    import hashlib

    CACHE.mkdir(exist_ok=True)
    tag = hashlib.md5(template.encode()).hexdigest()[:8]
    stem = CACHE / f"{tag}_{z}_{x}_{y}"
    hit = next((p for p in (stem.with_suffix(".png"), stem.with_suffix(".jpg"),
                            stem.with_suffix(".none")) if p.exists()), None)
    if hit is None:
        r = requests.get(template.format(z=z, x=x, y=y), timeout=30,
                         headers={"User-Agent": "roy-assignment-figures/1.0"})
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or "image" not in ctype:
            hit = stem.with_suffix(".none")
            hit.write_bytes(b"")
        else:
            hit = stem.with_suffix(".jpg" if "jpeg" in ctype else ".png")
            hit.write_bytes(r.content)
    if hit.suffix == ".none":
        return None
    mime = "image/jpeg" if hit.suffix == ".jpg" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(hit.read_bytes()).decode()


def _pick_zoom(span_x: float, device_px: float, max_zoom: int = 15) -> int:
    """Lowest zoom whose 256px tiles still out-resolve the output raster."""
    for z in range(1, max_zoom + 1):
        if span_x * (2 ** z) * 256 >= device_px:
            return z
    return max_zoom


# ----------------------------------------------------------------- basemap

def basemap(fig, lon_range, lat_range, *, device_px, style="carto-positron",
            attribution=True, labels=True):
    """Add tiled basemap images to `fig` and configure its Cartesian axes.

    `lon_range` / `lat_range` are the geographic extents to cover. The axes are
    left in Web-Mercator tile units (x east, y north) so that `scaleanchor`
    with ratio 1 gives the correct, undistorted Mercator aspect.

    Returns a `project(lon, lat) -> (x, y)` callable in those same tile units,
    which is what callers must use to place their own traces on top.
    """
    x0, x1 = sorted(merc_x(v) for v in lon_range)
    y0, y1 = sorted(merc_y(v) for v in lat_range)      # y0 = north edge

    z = _pick_zoom(x1 - x0, device_px)
    n = 2 ** z
    tx0, tx1 = int(x0 * n), int(x1 * n)
    ty0, ty1 = int(y0 * n), int(y1 * n)

    base_url, label_url = TILE_URL[style]
    # Base layer first, then labels on top -- Plotly draws layout images in list
    # order. The label overlay is fetched one zoom level coarser and stretched
    # over the 2x2 block it covers: place names are baked into the raster at a
    # fixed pixel size, so at the base zoom they come out ~6px tall and
    # illegible. Coarser tiles double them into something a reader can use.
    layers = [(base_url, 0)] + ([(label_url, -1)] if labels else [])

    # Tiles are placed edge to edge, which leaves a hairline seam where two
    # anti-aliased image edges meet. A sub-pixel overlap closes it.
    eps = 0.004

    images = []
    for template, dz in layers:
        k = 2 ** -dz                       # tile side, in base-zoom units
        for tx in range(tx0 // k, tx1 // k + 1):
            for ty in range(ty0 // k, ty1 // k + 1):
                src = _tile(template, z + dz, tx, ty)
                if src is None:
                    continue
                images.append(dict(
                    source=src, xref="x", yref="y",
                    x=tx * k - eps, y=-ty * k + eps,
                    sizex=k + 2 * eps, sizey=k + 2 * eps,
                    xanchor="left", yanchor="top",
                    sizing="stretch", layer="below", opacity=1))

    fig.update_layout(images=images)
    xr = [x0 * n, x1 * n]
    yr = [-y1 * n, -y0 * n]

    fig.update_xaxes(range=xr, showgrid=False, zeroline=False,
                     showticklabels=False, ticks="", title=None,
                     constrain="domain")
    fig.update_yaxes(range=yr, showgrid=False, zeroline=False,
                     showticklabels=False, ticks="", title=None,
                     scaleanchor="x", scaleratio=1, constrain="domain")

    if attribution:
        fig.add_annotation(
            x=1, y=0, xref="paper", yref="paper", xanchor="right", yanchor="bottom",
            text=ATTRIBUTION, showarrow=False,
            font=dict(size=9, color="#52514e"),
            bgcolor="rgba(255,255,255,0.72)", borderpad=3)

    def project(lon, lat):
        return merc_x(lon) * n, -merc_y(lat) * n

    return project


def fit_bounds(lon, lat, *, pad=0.06, aspect=None):
    """Data bounds padded by `pad`, optionally widened to a plot-box aspect.

    `aspect` is plot-box height / width. Because the axes are Mercator-square,
    matching the box aspect is what removes the dead margin that a fixed
    `scaleanchor` otherwise leaves on the wide axis.
    """
    lo0, lo1 = float(min(lon)), float(max(lon))
    la0, la1 = float(min(lat)), float(max(lat))
    dlo, dla = (lo1 - lo0) * pad, (la1 - la0) * pad
    lo0, lo1, la0, la1 = lo0 - dlo, lo1 + dlo, la0 - dla, la1 + dla

    if aspect:
        x0, x1 = merc_x(lo0), merc_x(lo1)
        y0, y1 = float(merc_y(la1)), float(merc_y(la0))   # y0 north, y1 south
        w, h = x1 - x0, y1 - y0
        if h / w > aspect:                                # too tall -> widen x
            need = h / aspect
            cx = (x0 + x1) / 2
            lo0, lo1 = (cx - need / 2 - 0.5) * 360, (cx + need / 2 - 0.5) * 360
        else:                                             # too wide -> heighten y
            need = w * aspect
            cy = (y0 + y1) / 2
            la1 = _inv_merc_y(cy - need / 2)
            la0 = _inv_merc_y(cy + need / 2)
    return (lo0, lo1), (la0, la1)


def _inv_merc_y(y: float) -> float:
    return math.degrees(2 * math.atan(math.exp((0.5 - y) * 2 * math.pi)) - math.pi / 2)
