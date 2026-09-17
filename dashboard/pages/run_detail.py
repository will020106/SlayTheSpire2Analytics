"""Run detail dashboard."""
from __future__ import annotations

import json
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
_SELECTION_KEYS = ("id", "name", "chosen", "selected", "picked", "choice", "card", "relic", "potion", "item", "value")
_OPTION_KEYS = ("options", "available_options", "available_cards", "cards", "relics", "potions", "rewards")


def _numeric_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _option_at(options: object, choice: object) -> object | None:
    """Resolve a numeric choice only when its saved option list makes it unambiguous."""
    index = _numeric_value(choice)
    if index is None or not isinstance(options, list):
        return None
    if 0 <= index < len(options):
        return options[index]
    if 1 <= index <= len(options):
        return options[index - 1]
    return None


def chosen_item(payload_json: str, kind: str) -> str:
    try:
        value = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        value = payload_json

    if isinstance(value, str):
        return display_name(value)

    numeric = _numeric_value(value)
    if numeric is not None:
        return f"Unresolved {kind.replace('_', ' ')} ID: {numeric}"

    if isinstance(value, list):
        return ", ".join(chosen_item(json.dumps(item), kind) for item in value)

    if isinstance(value, dict):
        selected = next((value[key] for key in _SELECTION_KEYS if value.get(key) not in (None, "")), None)
        if selected is not None:
            options = next((value[key] for key in _OPTION_KEYS if isinstance(value.get(key), list)), None)
            resolved = _option_at(options, selected)
            if resolved is not None:
                return chosen_item(json.dumps(resolved), kind)
            return chosen_item(json.dumps(selected), kind)
        fallback = next(iter(value.values()), "Unknown")
        numeric = _numeric_value(fallback)
        if numeric is not None:
            return f"Unresolved {kind.replace('_', ' ')} ID: {numeric}"
        return display_name(fallback)

    return "Unknown"


def load_runs() -> list[dict]:
    with connect(DATABASE_PATH) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id, character, ascension, result, death_cause FROM runs ORDER BY id DESC"
        )]


def run_label(run: dict) -> str:
    return f"Run {run['id']} — {display_name(run['character'])} A{run['ascension']} — {(run['result'] or 'unknown').title()}"


st.title("Run detail")
runs = load_runs()
characters = sorted({run["character"] or "unknown" for run in runs})
selected_character = st.selectbox(
    "Character",
    ["All characters", *characters],
    format_func=lambda character: character if character == "All characters" else display_name(character),
)
if selected_character != "All characters":
    runs = [run for run in runs if (run["character"] or "unknown") == selected_character]
if not runs:
    st.info("Import and parse some runs first.")
    st.stop()

selected = st.selectbox("Choose a run", runs, format_func=run_label)
with connect(DATABASE_PATH) as conn:
    run = dict(conn.execute("SELECT * FROM runs WHERE id = ?", (selected["id"],)).fetchone())
    floors = [dict(row) for row in conn.execute(
        "SELECT act_number, floor_number, node_type, encounter, event "
        "FROM floors WHERE run_id = ? ORDER BY act_number, floor_number, id",
        (selected["id"],),
    )]
    choices = [dict(row) for row in conn.execute(
        "SELECT act_number, floor_number, kind, choice_position, choice_path, payload_json "
        "FROM choices WHERE run_id = ? ORDER BY act_number, floor_number, choice_position",
        (selected["id"],),
    )]

first, second, third = st.columns(3)
first.metric("Outcome", (run.get("result") or "unknown").title())
second.metric("Ascension", run.get("ascension", "—"))
third.metric("Death cause", display_name(run.get("death_cause") or "Completed"))

st.subheader("Choices taken")
if choices:
    rows = [{
        "Act": choice["act_number"] or "—",
        "Floor": choice["floor_number"],
        "Type": choice["kind"].replace("_", " ").title(),
        "Chosen item": chosen_item(choice["payload_json"], choice["kind"]),
        "Position": choice["choice_position"],
    } for choice in choices]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Act and floor come directly from the run archive. Numeric values are resolved through saved options when available; otherwise they are labeled as unresolved game IDs rather than misidentified as cards.")
else:
    st.info("No choices were recorded for this run.")

st.subheader("Floor path")
if floors:
    st.dataframe(pd.DataFrame(floors), use_container_width=True, hide_index=True)

st.subheader("Raw choice payloads")
for choice in choices:
    act = choice["act_number"]
    label = chosen_item(choice["payload_json"], choice["kind"])
    with st.expander(f"Act {act if act is not None else '—'} · Floor {choice['floor_number']} · {choice['kind']} · {label}"):
        try:
            st.json(json.loads(choice["payload_json"]))
        except json.JSONDecodeError:
            st.code(choice["payload_json"])
