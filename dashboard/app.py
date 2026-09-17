"""Streamlit entry point for the Slay the Spire 2 analytics dashboard."""

from pathlib import Path

import streamlit as st

from pages.overview import render_overview


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "database" / "sts_analytics.db"


st.set_page_config(page_title="STS2 Playstyle Lab", page_icon="", layout="wide")
render_overview(DATABASE_PATH)
