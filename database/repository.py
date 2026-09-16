"""Persistence functions for parsed STS2 run-history data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from database.schema import connect, initialize_database
from ingestion.parser import parse_run_file

Json = dict[str, Any]


@dataclass(frozen=True)
class SaveResult:
    run_id: int | None
    inserted: bool


def file_hash(path: str | Path) -> str:
    """Return a stable digest used to make imports idempotent."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def save_parsed_run(
    database_path: str | Path,
    parsed: Json,
    *,
    content_hash: str,
) -> SaveResult:
    """Save one parsed run atomically, or skip it when its raw file is known."""
    initialize_database(database_path)
    source_path = parsed.get("source_path", "<unknown>")
    context = parsed["context"]
    outcome = parsed["outcome"]

    with connect(database_path) as connection:
        existing = connection.execute(
            "SELECT id FROM imported_files WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            run = connection.execute(
                "SELECT id FROM runs WHERE imported_file_id = ?", (existing["id"],)
            ).fetchone()
            return SaveResult(run["id"] if run else None, False)

        file_cursor = connection.execute(
            "INSERT INTO imported_files (source_path, content_hash) VALUES (?, ?)",
            (source_path, content_hash),
        )
        run_cursor = connection.execute(
            """
            INSERT INTO runs (
                imported_file_id, character, ascension, seed, game_mode, build_id,
                acts_json, result, death_cause, killed_by_encounter, killed_by_event,
                death_floor, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_cursor.lastrowid,
                context.get("character"),
                context.get("ascension"),
                context.get("seed"),
                context.get("game_mode"),
                context.get("build_id"),
                _json(context.get("acts", [])),
                outcome.get("result"),
                outcome.get("death_cause"),
                outcome.get("killed_by_encounter"),
                outcome.get("killed_by_event"),
                outcome.get("death_floor"),
                _json(parsed["raw"]),
            ),
        )
        run_id = run_cursor.lastrowid
        floor_ids: dict[int, int] = {}

        for floor in parsed["floor_history"]:
            cursor = connection.execute(
                """
                INSERT INTO floors (
                    run_id, floor_number, node_type, encounter, event, players_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    floor["floor"],
                    floor.get("node_type"),
                    floor.get("encounter"),
                    floor.get("event"),
                    _json(floor.get("players", [])),
                    _json(floor["raw"]),
                ),
            )
            floor_ids[floor["floor"]] = cursor.lastrowid

        for choice in parsed["choices"]:
            floor_number = choice.get("floor")
            connection.execute(
                """
                INSERT INTO choices (
                    run_id, floor_id, floor_number, kind, choice_path, choice_position, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    floor_ids.get(floor_number),
                    floor_number,
                    choice["kind"],
                    choice["path"],
                    choice["position"],
                    _json(choice["payload"]),
                ),
            )

    return SaveResult(run_id, True)


def import_run_file(database_path: str | Path, run_file: str | Path) -> SaveResult:
    """Parse one archived .run file, then persist it unless already imported."""
    source = Path(run_file)
    return save_parsed_run(
        database_path,
        parse_run_file(source),
        content_hash=file_hash(source),
    )


@dataclass(frozen=True)
class BatchImportResult:
    discovered: int
    inserted: int
    skipped: int
    failed: int
    errors: tuple[str, ...]


def import_archive_directory(
    database_path: str | Path,
    archive_directory: str | Path,
) -> BatchImportResult:
    """Import every archived .run file and keep going if one file is malformed."""
    archive = Path(archive_directory)
    if not archive.is_dir():
        raise FileNotFoundError(f"Archive directory does not exist: {archive}")

    initialize_database(database_path)
    run_files = sorted(path for path in archive.rglob("*.run") if path.is_file())
    inserted = skipped = failed = 0
    errors: list[str] = []

    for run_file in run_files:
        try:
            result = import_run_file(database_path, run_file)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failed += 1
            errors.append(f"{run_file.name}: {error}")
            continue

        if result.inserted:
            inserted += 1
        else:
            skipped += 1

    return BatchImportResult(
        discovered=len(run_files),
        inserted=inserted,
        skipped=skipped,
        failed=failed,
        errors=tuple(errors),
    )
