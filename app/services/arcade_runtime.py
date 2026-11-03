"""Execute the same deterministic rules as the browser; never execute client code."""

import json
from functools import lru_cache
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "web/static/miniapp"


class InvalidArcadeRun(ValueError):
    pass


@lru_cache(maxsize=1)
def sources() -> str:
    return "var window=globalThis;\n" + "\n".join(
        (STATIC / name).read_text(encoding="utf-8")
        for name in (
            "games-extra.js",
            "games-hill.js",
            "games-engine.js",
            "games-journey.js",
            "games-drop.js",
            "games-world.js",
        )
    )


def context():
    try:
        from py_mini_racer import MiniRacer
    except ImportError as error:
        raise RuntimeError("Install requirements-games.txt to run the local arcade") from error
    runtime = MiniRacer()
    runtime.set_hard_memory_limit(96 * 1024 * 1024)
    runtime.eval(sources(), timeout_sec=2)
    return runtime


@lru_cache(maxsize=1)
def catalogue() -> list[dict]:
    with context() as runtime:
        return json.loads(runtime.eval("JSON.stringify(AlgoGameEngine.games)"))


def verify(setup: dict, actions: list[dict], ticks: int) -> dict:
    try:
        with context() as runtime:
            report = runtime.call("ArcadeWorld.verify", setup, actions, ticks, timeout_sec=8)
    except Exception as error:
        raise InvalidArcadeRun(
            "Не удалось подтвердить ход партии. Попробуй новую попытку."
        ) from error
    if not isinstance(report, dict) or not isinstance(report.get("score"), int):
        raise InvalidArcadeRun("Результат партии не прошёл проверку.")
    return report
