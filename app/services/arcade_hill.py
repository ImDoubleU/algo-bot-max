"""Active-only driving progression. Garage coins never touch astrocoin balances."""

import json
import math
from datetime import datetime, timedelta, timezone

ROUTES = (("meadow", 1), ("dunes", 3), ("snow", 6), ("moon", 10), ("volcano", 15))
CARS = {
    "scout": (1, 0),
    "buggy": (4, 1800),
    "truck": (8, 5500),
    "rover": (13, 14000),
}
UPGRADES = {"engine": 130, "tires": 110, "suspension": 100, "tank": 90}
PAINTS = ("#e7a64d", "#66a99c", "#b87758", "#a0a8c0", "#d16b63", "#7596c0")


def install(db):
    db.executescript("""
      CREATE TABLE IF NOT EXISTS hill_garages(
        player TEXT PRIMARY KEY REFERENCES arcade_players(id), state TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS hill_actions(
        player TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(player,id));
      CREATE TABLE IF NOT EXISTS hill_results(
        session TEXT PRIMARY KEY, player TEXT NOT NULL, reward INTEGER NOT NULL);
    """)


def level(state):
    return min(25, 1 + math.isqrt(state["xp"] // 120))


def price(item, tier):
    return int(UPGRADES[item] * 1.62**tier)


def state_for(db, player):
    row = db.execute("SELECT state FROM hill_garages WHERE player=?", (player,)).fetchone()
    if row:
        return json.loads(row[0])
    state = dict(
        balance=250,
        xp=0,
        car="scout",
        owned=["scout"],
        paint=PAINTS[0],
        upgrades={car: dict.fromkeys(UPGRADES, 0) for car in CARS},
        distance=0,
        best=0,
        coins=0,
        flips=0,
        jumps=0,
        air=0,
        runs=0,
        route_best={},
        claimed=[],
        daily={},
    )
    save(db, player, state)
    return state


def save(db, player, state):
    db.execute(
        "INSERT INTO hill_garages VALUES(?,?) ON CONFLICT(player) "
        "DO UPDATE SET state=excluded.state",
        (player, json.dumps(state)),
    )


def setup(db, player, mode, route=None, stage=None):
    state = state_for(db, player)
    if mode == "ranked":
        return dict(route="meadow", car="scout", upgrades={}, paint=PAINTS[0])
    route = route or (ROUTES[(0, 0, 1, 2, 3, 4)[(stage - 1) // 4]][0] if stage else "meadow")
    required = dict(ROUTES).get(route)
    if required is None or (mode != "journey" and required > level(state)):
        from app.services.arcade import ArcadeError

        raise ArcadeError("Эта трасса пока закрыта. Посмотри её в гараже.")
    return dict(
        route=route,
        car=state["car"],
        upgrades=state["upgrades"][state["car"]],
        paint=state["paint"],
    )


def contracts(db, player, state):
    result = []

    def add(key, category, name, value, target, reward):
        result.append(
            dict(
                id=key,
                category=category,
                name=name,
                value=min(value, target),
                target=target,
                reward=reward,
                ready=value >= target,
                claimed=key in state["claimed"],
            )
        )

    for target, reward in ((1000, 150), (5000, 400), (20000, 1200), (80000, 4000)):
        add(
            f"distance:{target}",
            "Дорога",
            f"Проехать {target:,} м".replace(",", " "),
            state["distance"],
            target,
            reward,
        )
    for target, reward in ((300, 100), (800, 220), (1500, 450), (3000, 900), (6000, 1800)):
        add(f"best:{target}", "Рекорды", f"{target} м за один заезд", state["best"], target, reward)
    for key, name, tiers in (
        ("flips", "Сальто с посадкой", ((1, 200), (5, 500), (25, 1600))),
        ("jumps", "Приземлиться после прыжка", ((10, 150), (50, 450), (200, 1200))),
        ("air", "Секунд в воздухе", ((10, 150), (60, 500), (300, 1800))),
    ):
        for target, reward in tiers:
            add(f"{key}:{target}", "Трюки", f"{name}: {target}", state[key], target, reward)
    for route, _ in ROUTES:
        for target in (500, 1500):
            add(
                f"route:{route}:{target}",
                "Трассы",
                f"{target} м",
                state["route_best"].get(route, 0),
                target,
                target // 2,
            )
            result[-1]["route"] = route
    cleared = db.execute(
        "SELECT COUNT(*) FROM arcade_journeys WHERE player=? AND game='hill'", (player,)
    ).fetchone()[0]
    for target in (4, 12, 24):
        add(
            f"missions:{target}",
            "Экспедиция",
            f"Завершить заданий: {target}",
            cleared,
            target,
            target * 50,
        )
    total = sum(sum(car.values()) for car in state["upgrades"].values())
    for target in (5, 20, 50):
        add(
            f"upgrades:{target}",
            "Мастерская",
            f"Установить улучшений: {target}",
            total,
            target,
            target * 30,
        )
    return result


def daily(state, now):
    day = datetime.fromtimestamp(now, timezone(timedelta(hours=3))).date().isoformat()
    saved = state["daily"] if state["daily"].get("day") == day else dict(day=day)
    return [
        dict(
            id=f"daily:{day}:{key}",
            category="Сегодня",
            name=name,
            value=min(saved.get(key, 0), target),
            target=target,
            reward=reward,
            ready=saved.get(key, 0) >= target,
            claimed=f"daily:{day}:{key}" in state["claimed"],
        )
        for key, name, target, reward in (
            ("distance", "Проехать 1 000 м", 1000, 120),
            ("coins", "Собрать 100 монет на трассах", 100, 100),
            ("jumps", "Приземлиться после 8 прыжков", 8, 150),
        )
    ]


def record(db, player, session, report, now):
    d = report["details"]
    if (
        d.get("physics") != "hill1"
        or d.get("inputs", 0) < 1
        or report["ticks"] < 180
        or report["score"] < 20
    ):
        return 0
    reward = d["coins"] + report["score"] // 15
    if not db.execute(
        "INSERT OR IGNORE INTO hill_results VALUES(?,?,?)", (session, player, reward)
    ).rowcount:
        return 0
    state = state_for(db, player)
    state["balance"] += reward
    state["xp"] += report["score"] // 3 + d["flips"] * 30
    state["best"] = max(state["best"], report["score"])
    state["runs"] += 1
    additions = dict(
        distance=report["score"],
        coins=d["coins"],
        flips=d["flips"],
        jumps=d["jumps"],
        air=d["airTimeMs"] / 1000,
    )
    day = datetime.fromtimestamp(now, timezone(timedelta(hours=3))).date().isoformat()
    if state["daily"].get("day") != day:
        state["daily"] = dict(day=day)
    for key, value in additions.items():
        state[key] += value
        state["daily"][key] = state["daily"].get(key, 0) + value
    state["route_best"][d["route"]] = max(state["route_best"].get(d["route"], 0), report["score"])
    save(db, player, state)
    return reward


class HillStore:
    def __init__(self, arcade):
        self.arcade = arcade

    def snapshot(self, db, player, state):
        lv = level(state)
        return dict(
            **state,
            level=lv,
            next_xp=120 * lv * lv if lv < 25 else None,
            routes=[
                dict(
                    id=key,
                    level=required,
                    unlocked=required <= lv,
                    best=state["route_best"].get(key, 0),
                )
                for key, required in ROUTES
            ],
            cars=[
                dict(
                    id=key, level=v[0], price=v[1], unlocked=v[0] <= lv, owned=key in state["owned"]
                )
                for key, v in CARS.items()
            ],
            parts=[
                dict(
                    id=key,
                    tier=state["upgrades"][state["car"]][key],
                    price=price(key, state["upgrades"][state["car"]][key]),
                )
                for key in UPGRADES
            ],
            tasks=daily(state, self.arcade.clock()) + contracts(db, player, state),
            paints=list(PAINTS),
        )

    def get(self, player):
        with self.arcade.db() as db:
            self.arcade._player(db, player)
            return self.snapshot(db, player, state_for(db, player))

    def act(self, player, request, action, item=None):
        from app.services.arcade import ArcadeError

        with self.arcade.db() as db:
            self.arcade._player(db, player)
            payload = json.dumps([action, item])
            previous = db.execute(
                "SELECT payload FROM hill_actions WHERE player=? AND id=?", (player, request)
            ).fetchone()
            state = state_for(db, player)
            if previous:
                if previous[0] != payload:
                    raise ArcadeError("Повтори действие новой кнопкой.")
                return self.snapshot(db, player, state)
            lv = level(state)
            if action == "upgrade" and item in UPGRADES:
                tier = state["upgrades"][state["car"]][item]
                cost = price(item, tier)
                if tier >= 10 or state["balance"] < cost:
                    raise ArcadeError("Недостаточно монет или улучшение уже максимальное.")
                state["balance"] -= cost
                state["upgrades"][state["car"]][item] += 1
            elif action in ("buy", "select") and item in CARS:
                required, cost = CARS[item]
                if required > lv:
                    raise ArcadeError("Сначала повысь уровень водителя.")
                if item not in state["owned"]:
                    if action != "buy" or state["balance"] < cost:
                        raise ArcadeError("Недостаточно монет для этой машины.")
                    state["balance"] -= cost
                    state["owned"].append(item)
                state["car"] = item
            elif action == "paint" and item in PAINTS:
                state["paint"] = item
            elif action == "claim_all":
                for task in daily(state, self.arcade.clock()) + contracts(db, player, state):
                    if task["ready"] and not task["claimed"]:
                        state["claimed"].append(task["id"])
                        state["balance"] += task["reward"]
            else:
                raise ArcadeError("Это действие в гараже недоступно.")
            save(db, player, state)
            db.execute("INSERT INTO hill_actions VALUES(?,?,?)", (player, request, payload))
            return self.snapshot(db, player, state)
