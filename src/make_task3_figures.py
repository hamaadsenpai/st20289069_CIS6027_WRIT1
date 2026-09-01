"""
Report figures for Task 3 -- the two dashboards' interaction idioms.

fig6/fig7 come from the EXPLORATORY dashboard (drill-down and what-if);
fig8 comes from the EXPLANATORY one (act seven's flow diagram). fig8 was
previously exported by hand and had no script, so it could not be rebuilt from
the repo; it is generated here alongside the others.

Static exports lose the surrounding dashboard chrome, so the two figures that
depend on filter state (fig7) carry that state in the figure itself rather than
relying on a caption to supply it.

Run:  .venv/bin/python src/make_task3_figures.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import exploratory as e
import explanatory as x
from theme import CHROME

OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
MODE = "light"
c = CHROME[MODE]

W = len(e.WEEKS) - 1
base = dict(groups=None, rooms=None, price=[0, e.OPTS["price_max"]], weeks=[0, W],
            sel={"neighbourhoods": []}, mode=MODE)

# ---- Fig 6: drill-down idiom (treemap, whole city) ------------------------
e._treemap(**base).write_image(str(OUT / "fig6_exploratory_treemap.png"),
                               width=860, height=380, scale=2)
print("wrote fig6_exploratory_treemap.png")

# ---- Fig 7: what-if idiom (drilled to Belltown) ---------------------------
# On the dashboard the active selection is shown by a separate chip and the
# y unit by the KPI tile beside it. Neither survives a PNG export, so the
# figure was leaving a reader with an unlabelled y-axis and no way to tell
# which neighbourhood it showed. Both are restated on the figure.
PICK = "Belltown"
drill = dict(base, sel={"neighbourhoods": [PICK]})
n_listings = len(e._slice(**{k: drill[k] for k in
                             ("groups", "rooms", "price", "weeks", "sel")})[0])
f7 = e._whatif(**drill, dp=15, elast=1.5)
f7.update_layout(
    margin=dict(l=8, r=8, t=44, b=8),
    yaxis=dict(title="RevPAN proxy (index, not currency)", rangemode="tozero"),
    xaxis=dict(showgrid=False, title=None),
    legend=dict(orientation="h", y=1.02, x=0.28))
f7.add_annotation(x=0, y=1.16, xref="paper", yref="paper", xanchor="left",
                  showarrow=False, text=f"<b>{PICK}</b> · {n_listings} listings",
                  font=dict(size=12.5, color=c["ink"]))
f7.write_image(str(OUT / "fig7_exploratory_whatif.png"), width=860, height=380, scale=2)
print("wrote fig7_exploratory_whatif.png (drilled to Belltown, +15% @ e=1.5)")

# ---- Fig 8: explanatory flow idiom (Sankey, act seven) --------------------
x._act7(MODE).write_image(str(OUT / "fig8_explanatory_sankey.png"),
                          width=900, height=440, scale=2)
print("wrote fig8_explanatory_sankey.png")
