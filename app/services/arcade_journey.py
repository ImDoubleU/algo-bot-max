"""Persistent active-only adventures; no clock-based credits or offline production."""

import json
from functools import lru_cache

from app.services import arcade_runtime


@lru_cache(maxsize=1)
def catalogue():
    with arcade_runtime.context() as vm:
        return vm.call("ArcadeJourney.catalogue")


def progress(db, player):
    rows = [
        dict(r)
        for r in db.execute(
            "SELECT game,stage,stars,score,completed,details FROM arcade_journeys "
            "WHERE player=? ORDER BY game,stage",
            (player,),
        )
    ]
    result = {}
    for game in catalogue():
        records = [r for r in rows if r["game"] == game]
        cleared = {r["stage"] for r in records}
        maximum = len(catalogue()[game]["stages"])
        chapter_size = 12 if game in ("typing", "debug") else 4
        legacy = {
            r["stage"] for r in records if json.loads(r["details"]).get("lessonVersion", 1) < 2
        }
        unlocked = 1
        while unlocked in cleared and unlocked < maximum:
            unlocked += 1
        stars = sum(r["stars"] for r in records)
        result[game] = dict(
            unlocked=unlocked,
            cleared=len(records),
            stars=stars,
            maximum=maximum,
            chapterSize=chapter_size,
            breadthQualified=len(cleared) >= chapter_size or len(legacy) >= 4,
            charges=max(
                1 + int((chapter_size * 2) in cleared) + int((chapter_size * 4) in cleared),
                1 + int(8 in legacy) + int(16 in legacy),
            ),
            records=[{k: v for k, v in r.items() if k != "details"} for r in records],
            keepsakes=[
                n
                for n in range(1, maximum // chapter_size + 1)
                if all(
                    i in cleared for i in range((n - 1) * chapter_size + 1, n * chapter_size + 1)
                )
                or n <= 6
                and all(i in legacy for i in range((n - 1) * 4 + 1, n * 4 + 1))
            ],
        )
    return result


def prepare(db, player, game, stage):
    if game not in catalogue():
        raise ValueError("У этой игры нет приключения.")
    saved = progress(db, player)[game]
    if stage is None:
        stage = saved["unlocked"]
    if (
        isinstance(stage, bool)
        or not isinstance(stage, int)
        or not 1 <= stage <= saved["maximum"]
        or stage > saved["unlocked"]
    ):
        raise ValueError("Сначала заверши предыдущее задание.")
    return dict(stage=stage, charges=saved["charges"])


def record(db, player, game, report, now):
    result = report.get("journey") or {}
    if not result.get("success") or result.get("inputs", 0) < 1:
        return
    stage, stars = result["stage"], result["stars"]
    if (
        game not in catalogue()
        or not 1 <= stage <= len(catalogue()[game]["stages"])
        or not 1 <= stars <= 3
    ):
        raise ValueError("Не удалось подтвердить задание.")
    db.execute(
        """INSERT INTO arcade_journeys(player,game,stage,stars,score,completed,details)
                  VALUES(?,?,?,?,?,?,?) ON CONFLICT(player,game,stage) DO UPDATE SET
                  stars=MAX(arcade_journeys.stars,excluded.stars),
                  score=MAX(arcade_journeys.score,excluded.score),details=excluded.details""",
        (player, game, stage, stars, report["score"], now, json.dumps(result)),
    )
