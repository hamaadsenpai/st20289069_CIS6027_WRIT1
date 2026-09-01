"""Page CSS for both dashboards. Light only."""

from theme import CHROME, FONT

C = CHROME["light"]

CSS = f"""
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: {C['plane']}; color: {C['ink']};
  font-family: {FONT}; font-size: 14px;
}}
.wrap {{ max-width: 1400px; margin: 0 auto; padding: 20px 22px 48px; }}
h1 {{ font-size: 18px; font-weight: 650; margin: 0 0 16px; }}

.filters {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr));
  row-gap: 14px; column-gap: 26px; align-items: end;
  background: {C['surface']}; border: 1px solid {C['border']};
  border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;
}}
.f {{ min-width: 0; }}
.f label {{
  display: block; font-size: 11px; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: {C['muted']}; margin-bottom: 6px;
}}

/* A slider mark is centred on its own tick, so the first and last labels hang
   half their width past the ends of the track and out of the column: that is
   what put the price slider's "$1000" hard against the calendar slider's
   "2016-01-04", and the calendar's end date against the Clear selection button.
   Pin the two end labels inside the track (left- and right-aligned) and move
   each one's tick indicator to the edge that now sits over the tick, so a mark
   can never leave its own column. */
.f .dash-slider-mark {{ font-size: 11px; color: {C['ink2']}; }}
.f .dash-slider-mark:first-of-type {{ transform: translateX(0) !important; }}
.f .dash-slider-mark:first-of-type::before {{ left: 0; }}
.f .dash-slider-mark:last-of-type {{ transform: translateX(-100%) !important; }}
.f .dash-slider-mark:last-of-type::before {{ left: 100%; }}

.grid {{ display: grid; gap: 14px; margin-bottom: 14px; }}
.g2 {{ grid-template-columns: 1fr 1fr; }}
.g3 {{ grid-template-columns: 1fr 1fr 1fr; }}
.card {{
  background: {C['surface']}; border: 1px solid {C['border']};
  border-radius: 8px; padding: 10px 10px 4px; min-width: 0;
}}
.card h2 {{ font-size: 13px; font-weight: 620; margin: 0 0 6px; }}
@media (max-width: 1180px) {{ .g3 {{ grid-template-columns: 1fr 1fr; }} }}
@media (max-width: 900px) {{
  .g2, .g3 {{ grid-template-columns: 1fr; }}
}}

button {{
  background: {C['surface']}; color: {C['ink2']}; border: 1px solid {C['border']};
  border-radius: 6px; padding: 6px 13px; font-size: 12px; cursor: pointer;
  font-family: inherit;
}}
"""
