"""Overview page for the local STS2 analytics dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.metrics import death_causes, most_common_choice_types, win_rate_by_ascension


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def render_overview(database_path: str | Path) -> None:
    """Render a compact summary of locally imported STS2 run data."""
    database_path = Path(database_path)
    st.title("STS2 Playstyle Lab")
    st.caption("Local-only analysis of your archived Slay the Spire 2 runs.")

    if not database_path.exists():
        st.info("No analytics database found. Import your archived runs first.")
        return

    try:
        win_rows = win_rate_by_ascension(database_path)
        death_rows = death_causes(database_path)
        choice_rows = most_common_choice_types(database_path)
    except Exception as error:
        st.error(f"Could not read the analytics database: {error}")
        return

    win_frame = _frame(win_rows)
    death_frame = _frame(death_rows)
    choice_frame = _frame(choice_rows)

    total_runs = int(win_frame["run_count"].sum()) if not win_frame.empty else 0
    wins = int(win_frame["wins"].sum()) if not win_frame.empty else 0
    losses = int(win_frame["losses"].sum()) if not win_frame.empty else 0
    rate = (wins / (wins + losses) * 100) if wins + losses else 0.0

    top_death = death_frame.iloc[0]["death_cause"] if not death_frame.empty else "No losses recorded"
    top_choice = choice_frame.iloc[0]["kind"] if not choice_frame.empty else "No choices recorded"

    first, second, third, fourth = st.columns(4)
    first.metric("Imported runs", total_runs)
    second.metric("Win rate", f"{rate:.1f}%")
    third.metric("Most common death", top_death)
    fourth.metric("Most common choice", top_choice)

    st.subheader("Win rate by Ascension")
    if win_frame.empty:
        st.info("Import runs to see win rates by Ascension.")
    else:
        st.bar_chart(win_frame.set_index("ascension")["win_rate_percent"])
        st.dataframe(win_frame, hide_index=True, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Death causes")
        st.dataframe(death_frame, hide_index=True, use_container_width=True)
    with right:
        st.subheader("Choice types")
        st.dataframe(choice_frame, hide_index=True, use_container_width=True)
