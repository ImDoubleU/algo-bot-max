"""Upper-bound reward projection using the real ledger and an isolated temporary DB.

All first goals and medals are hypothetically earned on day one. This is a ceiling,
not an estimate of how quickly a child can actually complete the hard achievements.
"""

import calendar
import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from app.services.arcade import (
    FIRST_GOAL_REWARD,
    GAMES,
    MEDAL_REWARDS,
    MOSCOW,
    ArcadeStore,
    season_key,
)


def month_after(value: date, count: int) -> date:
    year, month = divmod(value.year * 12 + value.month - 1 + count, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def project(start: date, prize: int = 0, medals: bool = True) -> list[dict]:
    """Three calendar months; credits on the boundary belong to the next month."""
    boundaries = [month_after(start, i) for i in range(4)]
    totals = [
        dict(start=str(boundaries[i]), end=str(boundaries[i + 1]), earned=0, credited=0, pending=0)
        for i in range(3)
    ]
    day = start

    def stamp(value):
        return datetime.combine(value, datetime.min.time(), MOSCOW).timestamp()

    now = stamp(day)
    with tempfile.TemporaryDirectory(prefix="arcade-economy-") as directory:
        store = ArcadeStore(Path(directory) / "projection.sqlite3", lambda: now)
        store.register([dict(id="projection", name="Projection", group="Local only")])
        previous_season = season_key(now)
        month, credited_before = 0, 0
        while day < boundaries[-1]:
            now = stamp(day)
            if day == boundaries[month + 1]:
                month += 1
            with store.db() as db:
                if day == start:
                    for game in GAMES:
                        store._award(
                            db,
                            "projection",
                            "first",
                            "all",
                            f"first:{game}",
                            FIRST_GOAL_REWARD,
                            game,
                            claimed=True,
                        )
                        if medals:
                            for tier, amount in enumerate(MEDAL_REWARDS):
                                store._award(
                                    db,
                                    "projection",
                                    "master",
                                    "all",
                                    f"master:{game}:{tier}",
                                    amount,
                                    game,
                                    claimed=True,
                                )
                    totals[month]["earned"] += len(GAMES) * (
                        FIRST_GOAL_REWARD + (sum(MEDAL_REWARDS) if medals else 0)
                    )
                current = season_key(now)
                if current != previous_season:
                    if prize:
                        store._award(
                            db,
                            "projection",
                            "podium",
                            previous_season,
                            f"podium:{previous_season}",
                            prize,
                            "Podium",
                            claimed=True,
                        )
                        totals[month]["earned"] += prize
                    previous_season = current
                store._credit(db, "projection")
                credited = db.execute(
                    "SELECT COALESCE(SUM(amount),0) FROM arcade_credits"
                ).fetchone()[0]
                totals[month]["credited"] += credited - credited_before
                credited_before = credited
                totals[month]["pending"] = db.execute(
                    "SELECT COALESCE(SUM(amount),0) FROM arcade_awards WHERE credited IS NULL"
                ).fetchone()[0]
            day += timedelta(days=1)
    return totals


if __name__ == "__main__":
    start = datetime.now(MOSCOW).date()
    print(
        json.dumps(
            {
                "start": str(start),
                "goals_only": project(start, medals=False),
                "all_medals_no_podium": project(start),
                "third_every_season": project(start, 50),
                "second_every_season": project(start, 75),
                "first_every_season": project(start, 100),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
