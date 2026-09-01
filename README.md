# CIS6027 WRIT1 - st20289069

Seattle Airbnb data. Two Dash dashboards.

## 1. Install

Open a terminal in this folder.

macOS / Linux:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

Windows:

    py -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt

## 2. Start a server

macOS / Linux:

    .venv/bin/python app/exploratory.py

Windows:

    .venv\Scripts\python app/exploratory.py

Open http://127.0.0.1:8050

For the second dashboard, do the same with `app/explanatory.py` and open
http://127.0.0.1:8051

Use two terminals if you want both open at once. Ctrl+C stops a server.

Notes:
- The data in `data/` is already built, so nothing else needs to be run.
- To rebuild it: `.venv/bin/python src/build_semantic_layer.py`
