"""Data-backed playstyle summaries for locally imported STS2 runs.

The game writes stable internal identifiers into run files. This module keeps those
identifiers for querying, then converts them into readable labels for display.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from database.schema import connect


DISPLAY_NAME_OVERRIDES = {
    "NONE.NONE": "None",
    "EVENT.NEOW": "Neow",
    "ENCOUNTER.AEONGLASS_BOSS": "Aeonglass",
    "ENCOUNTER.CEREMONIAL_DAGGER_BOSS": "Ceremonial Dagger",
    "ENCOUNTER.KAISER_CRAB_BOSS": "Kaiser Crab",
    "ENCOUNTER.KNOWLEDGE_DEMON_BOSS": "Knowledge Demon",
    "ENCOUNTER.LAGAVULIN_MATRIARCH_BOSS": "Lagavulin Matriarch",
    "ENCOUNTER.QUEEN_BOSS": "Queen",
    "ENCOUNTER.SOUL_FYSH_BOSS": "Soul Fysh",
    "ENCOUNTER.TEST_SUBJECT_BOSS": "Test Subject",
    "ENCOUNTER.THE_INSATIABLE_BOSS": "The Insatiable",
    "ENCOUNTER.THE_KIN_BOSS": "The Kin",
    "ENCOUNTER.VANTON_BOSS": "Vanton",
    "ENCOUNTER.WATERFALL_GIANT_BOSS": "Waterfall Giant",
    "CARD.ASCENDERS_BANE": "Ascender's Bane",
    "CARD.BANSHEES_CRY": "Banshee's Cry",
    "CARD.ANOINTED": "Anointed",
    "CARD.ANTICIPATE": "Anticipate",
    "CARD.APOTHEOSIS": "Apotheosis",
    "CARD.APPARITION": "Apparition",
    "CARD.ARMAMENTS": "Armaments",
    "CARD.ASHEN_STRIKE": "Ashen Strike",
    "CARD.ASSASSINATE": "Assassinate",
    "CARD.ASTRAL_PULSE": "Astral Pulse",
    "CARD.BACKFLIP": "Backflip",
    "CARD.BACKSTAB": "Backstab",
    "CARD.BALL_LIGHTNING": "Ball Lightning",
    "CARD.BARRAGE": "Barrage",
    "CARD.BARRICADE": "Barricade",
    "CARD.BASH": "Bash",
}


def display_name(value: object) -> str:
    """Turn a game identifier into a player-friendly label."""
    if value is None:
        return "Unknown"

    raw = str(value).strip()
    if not raw:
        return "Unknown"
    if raw in DISPLAY_NAME_OVERRIDES:
        return DISPLAY_NAME_OVERRIDES[raw]

    identifier = raw.rsplit(".", maxsplit=1)[-1]
    words = identifier.replace("-", "_").split("_")
    return " ".join(word.capitalize() for word in words if word) or raw


def _rows(database_path: str | Path, query: str, parameters: tuple[Any, ...] = ()) -> list[dict]:
    with connect(database_path) as connection:
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def choice_type_preferences(database_path: str | Path, limit: int = 10) -> list[dict]:
    """Return the types of decisions a player encounters most often."""
    rows = _rows(database_path, """
        SELECT kind, COUNT(*) AS choice_count, COUNT(DISTINCT run_id) AS run_count
        FROM choices GROUP BY kind ORDER BY choice_count DESC, kind ASC LIMIT ?
        """, (limit,))
    for row in rows:
        row["label"] = display_name(row["kind"])
    return rows


def frequent_deaths(database_path: str | Path, limit: int = 10) -> list[dict]:
    """Return loss causes with readable encounter or event names."""
    rows = _rows(database_path, """
        SELECT death_cause, COUNT(*) AS death_count FROM runs
        WHERE result = 'loss' AND death_cause IS NOT NULL AND death_cause != ''
        GROUP BY death_cause ORDER BY death_count DESC, death_cause ASC LIMIT ?
        """, (limit,))
    for row in rows:
        row["label"] = display_name(row["death_cause"])
    return rows


def _named_values(value: Any) -> set[str]:
    """Find likely selected game IDs in flexible choice payloads."""
    selection_keys = {"picked", "selected", "chosen", "choice", "card", "relic", "potion"}
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in selection_keys and isinstance(child, str) and child.strip():
                found.add(child)
            found.update(_named_values(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_named_values(child))
    return found


def preferred_named_choices(database_path: str | Path, kind: str, limit: int = 10) -> list[dict]:
    """Return frequently selected named cards, relics, or potions when available."""
    rows = _rows(database_path, "SELECT payload_json FROM choices WHERE kind = ?", (kind,))
    counts: Counter[str] = Counter()
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        counts.update(_named_values(payload))
    return [{"identifier": item, "label": display_name(item), "choice_count": count}
            for item, count in counts.most_common(limit)]


def playstyle_summary(database_path: str | Path) -> dict:
    """Return a dashboard-ready description of recorded player tendencies.

    It describes correlations in the saved runs; it does not claim a choice causes
    a win or loss.
    """
    totals_rows = _rows(database_path, """
        SELECT COUNT(*) AS run_count,
               SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses
        FROM runs
        """)
    totals = totals_rows[0] if totals_rows else {"run_count": 0, "wins": 0, "losses": 0}
    return {
        "run_count": int(totals["run_count"] or 0),
        "wins": int(totals["wins"] or 0),
        "losses": int(totals["losses"] or 0),
        "choice_types": choice_type_preferences(database_path),
        "frequent_deaths": frequent_deaths(database_path),
        "preferred_cards": preferred_named_choices(database_path, "card"),
        "preferred_relics": preferred_named_choices(database_path, "relic"),
        "preferred_potions": preferred_named_choices(database_path, "potion"),
    }
