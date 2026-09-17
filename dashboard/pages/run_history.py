"""Dashboard page for browsing imported Slay the Spire 2 runs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.playstyle import display_name
from database.schema import connect

DATABASE_PATH = PROJECT_ROOT / "database" / "sts_analytics.db"

st.title("Run history")
st.caption("Every row is one archived local run. Use the run ID on the Run detail page to inspect it further.")

with connect(DATABASE_PATH) as connection:
    runs = [dict(row) for row in connection.execute("""
        SELECT id, character, ascension, result, death_cause, seed, game_mode, build_id
        FROM runs
        ORDER BY id DESC
    """)]

frame = pd.DataFrame(runs)
if frame.empty:
    st.info("No imported runs are available yet.")
    st.stop()

outcome_options = ["All"] + sorted(frame["result"].fillna("unknown").unique().tolist())
selected_outcome = st.selectbox("Outcome", outcome_options)
if selected_outcome != "All":
    frame = frame[frame["result"].fillna("unknown") == selected_outcome]

frame["result"] = frame["result"].fillna("unknown").str.title()
frame["death_cause"] = frame["death_cause"].map(display_name).fillna("Completed / unrecorded")
frame = frame.rename(columns={
    "id": "run ID",
    "character": "character",
    "ascension": "ascension",
    "result": "outcome",
    "death_cause": "ending",
    "seed": "seed",
    "game_mode": "mode",
    "build_id": "game build",
})

st.metric("Runs shown", len(frame))
st.dataframe(frame, hide_index=True, width="stretch")

st.download_button(
    "Download this view as CSV",
    frame.to_csv(index=False).encode("utf-8"),
    file_name="sts2_run_history.csv",
    mime="text/csv",
)
