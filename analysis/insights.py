"""Evidence-backed observations from locally stored STS2 run data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from analysis.metrics import win_rate_by_ascension
from analysis.playstyle import choice_type_preferences, frequent_deaths
from database.schema import connect


@dataclass(frozen=True)
class Insight:
    """A dashboard-friendly observation with its supporting numbers."""

    category: str
    title: str
    message: str
    evidence: dict[str, Any]
    confidence: str = "descriptive"


def _outcome_totals(database_path: str | Path) -> dict[str, int]:
    with connect(database_path) as connection:
        row = connection.execute("""
            SELECT COUNT(*) AS runs,
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN result IS NULL OR result NOT IN ('win', 'loss') THEN 1 ELSE 0 END) AS unknown
            FROM runs
        """).fetchone()
    return {key: int(row[key] or 0) for key in ("runs", "wins", "losses", "unknown")}


def outcome_insight(database_path: str | Path) -> Insight:
    """Describe how much reliable outcome data is available."""
    totals = _outcome_totals(database_path)
    completed = totals["wins"] + totals["losses"]
    if not completed:
        message = "No runs currently have a confirmed win or loss outcome, so win/loss comparisons are not shown yet."
    elif totals["unknown"]:
        message = f"{completed} runs have confirmed outcomes; {totals['unknown']} runs are still unknown and are excluded from rate comparisons."
    else:
        rate = totals["wins"] / completed * 100
        message = f"{totals['wins']} of {completed} completed runs are wins ({rate:.1f}%)."
    return Insight("data quality", "Outcome coverage", message, totals, "data quality")


def death_cause_insight(database_path: str | Path) -> Insight | None:
    """Highlight the most common recorded loss cause, if any."""
    deaths = frequent_deaths(database_path, limit=1)
    totals = _outcome_totals(database_path)
    if not deaths or not totals["losses"]:
        return None
    top = deaths[0]
    share = top["death_count"] / totals["losses"] * 100
    return Insight(
        "survival",
        f"Most frequent loss: {top['label']}",
        f"{top['label']} accounts for {top['death_count']} of {totals['losses']} recorded losses ({share:.1f}%).",
        {"identifier": top["death_cause"], "losses": top["death_count"], "share_percent": round(share, 1)},
    )


def decision_mix_insight(database_path: str | Path) -> Insight | None:
    """Describe the decision type most represented in the imported history."""
    preferences = choice_type_preferences(database_path, limit=1)
    if not preferences:
        return None
    top = preferences[0]
    return Insight(
        "decision mix",
        f"Most recorded decision type: {top['label']}",
        f"Your run archive contains {top['choice_count']} {top['label'].lower()} decisions across {top['run_count']} runs.",
        {"kind": top["kind"], "choices": top["choice_count"], "runs": top["run_count"]},
    )


def ascension_insights(database_path: str | Path) -> list[Insight]:
    """Summarize confirmed-outcome coverage at each Ascension level."""
    insights: list[Insight] = []
    for row in win_rate_by_ascension(database_path):
        completed = row["wins"] + row["losses"]
        if completed:
            insights.append(Insight(
                "ascension",
                f"Ascension {row['ascension']} outcome snapshot",
                f"{row['wins']} wins and {row['losses']} losses across {completed} confirmed outcomes ({row['win_rate_percent']:.1f}% win rate).",
                dict(row),
            ))
    return insights


def build_insights(database_path: str | Path) -> list[dict[str, Any]]:
    """Return safe, display-ready insights without claiming causation."""
    insights: list[Insight] = [outcome_insight(database_path)]
    for candidate in (death_cause_insight(database_path), decision_mix_insight(database_path)):
        if candidate is not None:
            insights.append(candidate)
    insights.extend(ascension_insights(database_path))
    return [asdict(insight) for insight in insights]
