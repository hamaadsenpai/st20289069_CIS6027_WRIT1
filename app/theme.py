"""
Palette, Plotly templates and shared chart chrome.

Values come from the validated reference palette. The categorical order is
fixed (blue, orange, aqua) and assigned by entity, never by rank, so filtering
never repaints the survivors. Only the first three slots are used: they are the
set that clears the all-pairs CVD and normal-vision floors in both modes, which
is what map and scatter forms require.

Validator run (light, --pairs all, surface #fcfcfb):
    lightness band PASS | chroma floor PASS
    CVD separation PASS  worst aqua<->orange dE 9.2 (deutan)
    normal-vision  PASS  worst aqua<->blue   dE 24.0
    contrast       WARN  aqua 2.74:1 -> relief rule: every categorical series
                         carries a visible direct label AND a table view.
"""

import plotly.graph_objects as go
import plotly.io as pio

# --- categorical: fixed order, assigned by entity -------------------------
CATEGORICAL = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a"],
    "dark": ["#3987e5", "#d95926", "#199e70"],
}

# --- sequential: one hue, light -> dark (magnitude only) -------------------
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

# --- diverging: warm/cool poles, neutral gray midpoint --------------------
DIVERGING = {
    "light": [[0.0, "#0d366b"], [0.5, "#f0efec"], [1.0, "#d03b3b"]],
    "dark": [[0.0, "#3987e5"], [0.5, "#383835"], [1.0, "#e66767"]],
}

STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

CHROME = {
    "light": {
        "surface": "#fcfcfb", "plane": "#f9f9f7",
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7",
        "border": "rgba(11,11,11,0.10)",
        "map_style": "carto-positron",
    },
    "dark": {
        "surface": "#1a1a19", "plane": "#0d0d0d",
        "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835",
        "border": "rgba(255,255,255,0.10)",
        "map_style": "carto-darkmatter",
    },
}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _template(mode: str) -> go.layout.Template:
    c = CHROME[mode]
    axis = dict(
        showgrid=True, gridcolor=c["grid"], gridwidth=1, griddash="solid",
        zeroline=False, showline=True, linecolor=c["axis"], linewidth=1,
        ticks="outside", ticklen=4, tickcolor=c["axis"],
        tickfont=dict(color=c["muted"], size=11),
        title=dict(font=dict(color=c["ink2"], size=12)),
        automargin=True,
    )
    return go.layout.Template(layout=dict(
        colorway=CATEGORICAL[mode],
        paper_bgcolor=c["surface"], plot_bgcolor=c["surface"],
        font=dict(family=FONT, color=c["ink"], size=12),
        title=dict(font=dict(size=14, color=c["ink"]), x=0, xanchor="left", y=0.97),
        xaxis=axis, yaxis=axis,
        margin=dict(l=8, r=8, t=44, b=8),
        hoverlabel=dict(
            bgcolor=c["surface"], bordercolor=c["axis"], font=dict(family=FONT, size=12, color=c["ink"])
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=11, color=c["ink2"]), bgcolor="rgba(0,0,0,0)",
            title=dict(text=""),
        ),
        colorscale=dict(sequential=[[i / (len(SEQUENTIAL) - 1), h] for i, h in enumerate(SEQUENTIAL)],
                        diverging=DIVERGING[mode]),
    ))


pio.templates["viz_light"] = _template("light")
pio.templates["viz_dark"] = _template("dark")


def tpl(mode: str) -> str:
    return f"viz_{mode}"
