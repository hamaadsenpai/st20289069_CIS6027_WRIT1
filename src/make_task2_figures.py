"""
Report figure for Task 2 -- the aggregation funnel.

Shows the calendar table's row count collapsing across the three semantic
layers (L0 atomic -> L1 aggregate -> L2 KPI), the central case study for the
grain-misalignment argument in section 2.4.

Counts are read from the built parquet files rather than hardcoded, so the
figure cannot silently drift away from the semantic layer it describes.

Encoding note. This was a bar chart on a log x-axis. A bar asserts that its
LENGTH is proportional to its value, and a log axis breaks exactly that: the
53-row layer drew at ~40% the length of the 1.39M-row layer, understating a
26,000x collapse by three orders of magnitude -- in the one figure whose entire
job is to show the size of that collapse. Position on a log scale is fine; a
length on one is not. Hence a lollipop: the marker's POSITION carries the
magnitude, and the stem is a leader line to the label, not a quantity.

Run:  .venv/bin/python src/make_task2_figures.py
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.graph_objects as go

from theme import CATEGORICAL, CHROME, tpl

OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
MODE = "light"
c, blue = CHROME[MODE], CATEGORICAL[MODE][0]

LAYERS = [
    ("L0 atomic<br><span style='font-size:11px'>one listing-night</span>", "l0_calendar"),
    ("L1 aggregate<br><span style='font-size:11px'>listing x month</span>", "l1_listing_month"),
    ("L2 KPI<br><span style='font-size:11px'>city x week</span>", "l2_kpi_market"),
]
labels = [lab for lab, _ in LAYERS]
counts = [len(pd.read_parquet(ROOT / "data" / f"{t}.parquet")) for _, t in LAYERS]

XMIN = 1
f = go.Figure()
# Stems: leader lines to the label, deliberately thin so they do not read as bars.
for lab, v in zip(labels, counts):
    f.add_shape(type="line", x0=XMIN, x1=v, y0=lab, y1=lab,
                line=dict(color=c["grid"], width=2), layer="below")
f.add_trace(go.Scatter(
    x=counts, y=labels, mode="markers+text", orientation="h",
    marker=dict(size=15, color=blue, line=dict(width=2, color=c["surface"])),
    text=[f"  {v:,}" for v in counts], textposition="middle right",
    textfont=dict(color=c["ink2"], size=12),
    hovertemplate="%{y}<br>%{x:,} rows<extra></extra>"))

# Annotate the two reductions -- the collapse is the message, so state it in
# figures rather than leaving it to be eyeballed off a log axis.
# On a log axis, annotation x is given in log10 units.
for i in range(len(counts) - 1):
    f.add_annotation(
        x=(math.log10(counts[i]) + math.log10(counts[i + 1])) / 2,
        y=i + 0.5, xanchor="center", yanchor="middle", showarrow=False,
        text=f"÷ {counts[i] / counts[i + 1]:,.0f}",
        font=dict(size=11.5, color=c["muted"]),
        bgcolor=c["surface"], borderpad=3)

f.update_layout(
    template=tpl(MODE), showlegend=False,
    margin=dict(l=8, r=8, t=20, b=8),
    xaxis=dict(type="log", title="Rows (log scale — position, not length, carries the value)",
               showgrid=True, range=[0, 7.05]),
    yaxis=dict(showgrid=False, autorange="reversed", ticklabelposition="outside"))
f.write_image(str(OUT / "fig5_grain_funnel.png"), width=820, height=290, scale=2)
print("wrote fig5_grain_funnel.png", dict(zip([l.split("<br>")[0] for l in labels], counts)))
