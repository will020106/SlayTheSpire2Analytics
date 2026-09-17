"""Dashboard page for analyzing overall player tendencies."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from analysis.insights import build_insights
from analysis.playstyle import playstyle_summary
DATABASE_PATH = PROJECT_ROOT / "database" / "sts_analytics.db"
st.title("Your playstyle")
st.caption("Patterns are based only on your imported local run history.")
summary = playstyle_summary(DATABASE_PATH)
columns = st.columns(3)
columns[0].metric("Runs analyzed", summary.get("run_count", summary.get("runs_analyzed", 0)))
columns[1].metric("Choices recorded", summary.get("choice_count", summary.get("total_choices", 0)))
columns[2].metric("Most common choice", summary.get("most_common_choice", "—"))
st.subheader("What your runs suggest")
insights = build_insights(DATABASE_PATH)
if isinstance(insights, dict):
    insights = insights.get("insights", [])
for insight in insights or []:
    st.write(f"- {insight}")
for title, keys in (("Choice types", ("choice_types", "choice_type_counts")), ("Most frequent named choices", ("named_choices", "top_choices")), ("Death causes", ("death_causes",))):
    data = next((summary.get(key) for key in keys if summary.get(key) is not None), None)
    if data is not None:
        st.subheader(title)
        frame = pd.DataFrame(data)
        if not frame.empty:
            st.dataframe(frame, use_container_width=True, hide_index=True)
