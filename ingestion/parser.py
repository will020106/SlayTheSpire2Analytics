"""Parse archived Slay the Spire 2 run-history files for analytics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

Json = dict[str, Any]
CHOICE_KEYS = {
    "card_choices", "relic_choices", "potion_choices", "event_choices",
    "shop_choices", "boss_relic_choices", "upgrade_choices", "remove_choices",
}
NONE_VALUES = {None, "", "NONE", "NONE.NONE", "null"}


def first(data: Json, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def extract_choices(
    value: Any,
    floor: int | None = None,
    act: int | None = None,
    path: str = "",
) -> list[Json]:
    """Flatten nested saved choice collections and retain their original payload."""
    found: list[Json] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in CHOICE_KEYS or key.endswith("_choices"):
                items = child if isinstance(child, list) else [child]
                for position, payload in enumerate(items):
                    found.append({
                        "floor": floor,
                        "act": act,
                        "kind": key.removesuffix("_choices"),
                        "path": child_path,
                        "position": position,
                        "payload": payload,
                    })
            found.extend(extract_choices(child, floor, act, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(extract_choices(child, floor, act, f"{path}[{index}]") )
    return found


def player_nodes(history_item: Any) -> list[Json]:
    """STS2 stores each map floor as a list of one record per player."""
    if isinstance(history_item, dict):
        return [history_item]
    if isinstance(history_item, list):
        return [node for node in history_item if isinstance(node, dict)]
    return []


def first_player_stats(history: list[Any]) -> Json:
    for item in history:
        for node in player_nodes(item):
            stats = node.get("player_stats", [])
            if isinstance(stats, list):
                for stat in stats:
                    if isinstance(stat, dict):
                        return stat
    return {}


def parse_run_data(raw: Json, source_path: str | None = None) -> Json:
    """Extract context, outcome, map-floor history, and recorded player choices."""
    history = raw.get("map_point_history", [])
    if not isinstance(history, list):
        raise ValueError("Expected map_point_history to be a list.")

    floor_history: list[Json] = []
    floor_choices: list[Json] = []
    # The outer list is Acts; each inner list contains the map points/floors.
    for act, act_history in enumerate(history, start=1):
        if not isinstance(act_history, list):
            act_history = [act_history]
        for floor, history_item in enumerate(act_history, start=1):
            nodes = player_nodes(history_item)
            if not nodes:
                continue
            primary = nodes[0]
            choices = [
                choice
                for node in nodes
                for choice in extract_choices(node, floor, act)
            ]
            floor_choices.extend(choices)
            room = next(
                (room for room in primary.get("rooms", []) if isinstance(room, dict)),
                {},
            )
            floor_history.append({
                "act": act,
                "floor": floor,
                "node_type": first(primary, "map_point_type", "room_type", "node_type", default=room.get("room_type")),
                "encounter": first(primary, "encounter", "encounter_id", "monster", "enemy", default=room.get("model_id")),
                "event": first(primary, "event", "event_id", default=room.get("model_id") if room.get("room_type") == "event" else None),
                "players": [node.get("player_stats", []) for node in nodes],
                "choices": choices,
                "raw": history_item,
            })

    killed_by_encounter = first(raw, "killed_by_encounter", "killed_by_enemy")
    killed_by_event = first(raw, "killed_by_event")
    death_cause = next(
        (cause for cause in (killed_by_encounter, killed_by_event) if cause not in NONE_VALUES),
        None,
    )
    explicit_win = first(raw, "victory", "won", "is_victory")
    result = "win" if explicit_win is True or (len(raw.get("acts", [])) >= 3 and raw.get("was_abandoned") is False and death_cause is None) else "loss" if death_cause else "unknown"
    stats = first_player_stats(history)
    players = raw.get("players", [])
    primary_player = players[0] if isinstance(players, list) and players and isinstance(players[0], dict) else {}

    run_metadata = {key: value for key, value in raw.items() if key != "map_point_history"}
    return {
        "source_path": source_path,
        "context": {
            "character": first(
                raw,
                "character",
                "character_id",
                "player_character",
                default=first(primary_player, "character", "character_id", default=first(stats, "character", "character_id", "character_name")),
            ),
            "ascension": raw.get("ascension"),
            "seed": first(raw, "seed", "run_seed"),
            "game_mode": raw.get("game_mode"),
            "build_id": raw.get("build_id"),
            "acts": raw.get("acts", []),
        },
        "outcome": {
            "result": result,
            "killed_by_encounter": killed_by_encounter,
            "killed_by_event": killed_by_event,
            "death_cause": death_cause,
            "death_floor": first(raw, "death_floor", "floor_died"),
        },
        "floor_history": floor_history,
        "choices": extract_choices(run_metadata) + floor_choices,
        "raw": raw,
    }


def parse_run_file(path: str | Path) -> Json:
    source = Path(path)
    with source.open(encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise ValueError("Expected the .run file to contain one JSON object.")
    return parse_run_data(raw, str(source))


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse one STS2 .run file as JSON.")
    parser.add_argument("run_file", help="Path to an archived .run file")
    parser.add_argument("--output", help="Optional path for parsed JSON output")
    args = parser.parse_args()
    parsed = parse_run_file(args.run_file)
    output = json.dumps(parsed, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
