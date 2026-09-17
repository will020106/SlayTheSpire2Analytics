"""SQLite schema for locally stored STS2 analytics data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS imported_files (
    id INTEGER PRIMARY KEY,
    source_path TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    imported_file_id INTEGER NOT NULL UNIQUE REFERENCES imported_files(id) ON DELETE CASCADE,
    character TEXT,
    ascension INTEGER,
    seed TEXT,
    game_mode TEXT,
    build_id TEXT,
    acts_json TEXT NOT NULL,
    result TEXT NOT NULL,
    death_cause TEXT,
    killed_by_encounter TEXT,
    killed_by_event TEXT,
    death_floor INTEGER,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS floors (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    act_number INTEGER,
    floor_number INTEGER NOT NULL,
    node_type TEXT,
    encounter TEXT,
    event TEXT,
    players_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    UNIQUE(run_id, act_number, floor_number)
);

CREATE TABLE IF NOT EXISTS choices (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    floor_id INTEGER REFERENCES floors(id) ON DELETE SET NULL,
    act_number INTEGER,
    floor_number INTEGER,
    kind TEXT NOT NULL,
    choice_path TEXT NOT NULL,
    choice_position INTEGER NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_character_ascension ON runs(character, ascension);
CREATE INDEX IF NOT EXISTS idx_runs_result ON runs(result);
CREATE INDEX IF NOT EXISTS idx_floors_run_number ON floors(run_id, act_number, floor_number);
CREATE INDEX IF NOT EXISTS idx_choices_run_kind ON choices(run_id, kind);
"""


def connect(database_path: str | Path) -> sqlite3.Connection:
    """Open the local analytics database with foreign-key enforcement."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    """Create all analytics tables if they do not already exist."""
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)
        floor_columns = {row["name"] for row in connection.execute("PRAGMA table_info(floors)")}
        if "act_number" not in floor_columns:
            connection.execute("ALTER TABLE floors ADD COLUMN act_number INTEGER")
        choice_columns = {row["name"] for row in connection.execute("PRAGMA table_info(choices)")}
        if "act_number" not in choice_columns:
            connection.execute("ALTER TABLE choices ADD COLUMN act_number INTEGER")
