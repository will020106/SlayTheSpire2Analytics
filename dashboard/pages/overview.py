"""Overview screen for the local STS2 analytics dashboard."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

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
        st.code(
            "python -c "from database.repository import import_archive_directory; "
            "print(import_archive_directory('database/sts_analytics.db', 'data/raw'))""
        )
        return

    try:
        win_rows = win_rate_by_ascension(database_path)
        deaths = death_causes(database_path)
        choice_types = most_common_choice_types(database_path)
    except sqlite3.Error as error:
        st.error(f"Could not read the analytics database: {error}")
        return

    total_runs = sum(row["run_count"] for row in win_rows)
    wins = sum(row["wins"] for row in win_rows)
    losses = sum(row["losses"] for row in win_rows)
    known_results = wins + losses
    overall_rate = (100 * wins / known_results) if known_results else None
    top_death = deaths[0]["death_cause"] if deaths else "No recorded losses"
    top_choice = choice_types[0]["kind"] if choice_types else "No choices recorded"

    runs_col, win_col, death_col, choice_col = st.columns(4)
    runs_col.metric("Imported runs", total_runs)
    win_col.metric("Overall win rate", f"{overall_rate:.1f}%" if overall_rate is not None else "—")
    death_col.metric("Most common death", top_death)
    choice_col.metric("Most common choice", top_choice)

    st.subheader("Win rate by Ascension")
    win_frame = _frame(win_rows)
    if win_frame.empty:
        st.info("No completed run outcomes are available yet.")
    else:
        st.bar_chart(win_frame.set_index("ascension")["win_rate_percent"])
        st.dataframe(
            win_frame[["ascension", "run_count", "wins", "losses", "unknown_results", "win_rate_percent"]],
            hide_index=True,
            use_container_width=True,
        )

    left, right = st.columns(2)
    with left:
        st.subheader("Most common deaths")
        st.dataframe(_frame(deaths), hide_index=True, use_container_width=True)
    with right:
        st.subheader("Choice categories")
        st.dataframe(_frame(choice_types), hide_index=True, use_container_width=True)
