"""SQLite-backed aggregate metrics for the STS2 analytics dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from database.schema import connect


def _rows(database_path: str | Path, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect(database_path) as connection:
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def win_rate_by_ascension(
    database_path: str | Path,
    character: str | None = None,
) -> list[dict[str, Any]]:
    """Return wins, losses, and win rate for each Ascension level."""
    return _rows(
        database_path,
        """
        SELECT
            ascension,
            COUNT(*) AS run_count,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN result = 'unknown' THEN 1 ELSE 0 END) AS unknown_results,
            ROUND(
                100.0 * SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN result IN ('win', 'loss') THEN 1 ELSE 0 END), 0),
                1
            ) AS win_rate_percent
        FROM runs
        WHERE (? IS NULL OR character = ?)
        GROUP BY ascension
        ORDER BY ascension
        """,
        (character, character),
    )


def death_causes(
    database_path: str | Path,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the encounters or events most often responsible for losses."""
    return _rows(
        database_path,
        """
        SELECT
            death_cause,
            killed_by_encounter,
            killed_by_event,
            COUNT(*) AS death_count,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM runs WHERE result = 'loss'), 1)
                AS percent_of_losses
        FROM runs
        WHERE result = 'loss' AND death_cause IS NOT NULL
        GROUP BY death_cause, killed_by_encounter, killed_by_event
        ORDER BY death_count DESC, death_cause
        LIMIT ?
        """,
        (limit,),
    )


def most_common_choice_types(
    database_path: str | Path,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return decision categories such as card, relic, event, and shop choices."""
    return _rows(
        database_path,
        """
        SELECT
            kind,
            COUNT(*) AS choice_count,
            COUNT(DISTINCT run_id) AS runs_with_choice,
            ROUND(AVG(floor_number), 1) AS average_floor
        FROM choices
        GROUP BY kind
        ORDER BY choice_count DESC, kind
        LIMIT ?
        """,
        (limit,),
    )
