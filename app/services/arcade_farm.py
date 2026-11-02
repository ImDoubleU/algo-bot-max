"""Persistent Kopatych farm. Carrots are isolated from arcade and school AC wallets."""

import hashlib
import hmac
import json
import math
from datetime import datetime, timedelta

from app.services.arcade import MOSCOW, ArcadeError

LEVELS = [
    0,
    250,
    750,
    1800,
    4000,
    8000,
    15000,
    28000,
    50000,
    90000,
    150000,
    250000,
    400000,
    650000,
    1000000,
    1600000,
    2500000,
]
ITEMS = [
    dict(
        id="shovel",
        name="Лопата",
        category="tools",
        icon="shovel",
        price=50,
        growth=1.65,
        unlock=1,
        maximum=20,
        text="Больше морковок за нажатие",
    ),
    dict(
        id="gloves",
        name="Перчатки",
        category="tools",
        icon="gloves",
        price=250,
        growth=1.6,
        unlock=2,
        maximum=15,
        text="Усиливают ручной сбор на 10% за уровень",
    ),
    dict(
        id="battery",
        name="Запас сил",
        category="tools",
        icon="energy",
        price=180,
        growth=1.6,
        unlock=1,
        maximum=15,
        text="Ещё 200 единиц энергии",
    ),
    dict(
        id="well",
        name="Колодец",
        category="tools",
        icon="water",
        price=400,
        growth=1.7,
        unlock=3,
        maximum=15,
        text="Быстрее восстанавливает энергию",
    ),
    dict(
        id="beds",
        name="Грядки",
        category="garden",
        icon="beds",
        price=120,
        growth=1.55,
        unlock=1,
        maximum=25,
        text="Морковки растут даже без тебя",
        base=90,
    ),
    dict(
        id="helper",
        name="Помощник",
        category="garden",
        icon="helper",
        price=220,
        growth=1.6,
        unlock=2,
        maximum=20,
        text="Ухаживает за огородом круглые сутки",
        base=180,
    ),
    dict(
        id="beehives",
        name="Пасека",
        category="garden",
        icon="bee",
        price=500,
        growth=1.6,
        unlock=3,
        maximum=20,
        text="Пчёлы помогают огороду расти",
        base=300,
    ),
    dict(
        id="greenhouse",
        name="Теплица",
        category="garden",
        icon="greenhouse",
        price=1000,
        growth=1.65,
        unlock=5,
        maximum=20,
        text="Большой урожай в любую погоду",
        base=650,
    ),
    dict(
        id="orchard",
        name="Сад",
        category="garden",
        icon="tree",
        price=2500,
        growth=1.7,
        unlock=7,
        maximum=20,
        text="Самое урожайное место в долине",
        base=1600,
    ),
    dict(
        id="irrigation",
        name="Полив",
        category="business",
        icon="water",
        price=700,
        growth=1.7,
        unlock=4,
        maximum=15,
        text="Все постройки дают на 7% больше за уровень",
    ),
    dict(
        id="market",
        name="Лавка",
        category="business",
        icon="market",
        price=1500,
        growth=1.8,
        unlock=6,
        maximum=15,
        text="Доход всех построек +5% за уровень",
    ),
    dict(
        id="silo",
        name="Амбар",
        category="business",
        icon="barn",
        price=300,
        growth=1.7,
        unlock=2,
        maximum=10,
        text="Ещё 2 часа накопления без захода в игру",
    ),
]
BY_ID = {item["id"]: item for item in ITEMS}
DAILY_REWARDS = [100, 150, 200, 300, 400, 600, 1000]
BADGES = [
    ("first_harvest", "Огородник", "earned", 1000, 300),
    ("ten_thousand", "Богатый урожай", "earned", 10000, 1000),
    ("hundred_thousand", "Хозяин долины", "earned", 100000, 5000),
    ("tap_500", "Трудолюбивый", "taps", 500, 300),
    ("tap_2500", "Золотые руки", "taps", 2500, 1000),
    ("build_10", "Хозяйственник", "upgrades", 10, 400),
    ("build_30", "Большая ферма", "upgrades", 30, 2000),
    ("idle_5000", "Растёт само", "passive", 5000, 1500),
]


def level(earned):
    return min(len(LEVELS), sum(earned >= value for value in LEVELS))


def stats(state, now_ms):
    upgrades = state["items"]
    production = 120 + sum(
        int(item["base"] * upgrades[item["id"]] * 1.12 ** max(0, upgrades[item["id"]] - 1))
        for item in ITEMS
        if "base" in item
    )
    production = production * (100 + 7 * upgrades["irrigation"] + 5 * upgrades["market"]) // 100
    tap = (1 + 2 * upgrades["shovel"]) * (100 + 10 * upgrades["gloves"]) // 100
    boost = state["boost_until"] > now_ms
    return dict(
        per_hour=production,
        per_tap=tap * (2 if boost else 1),
        base_tap=tap,
        energy_max=500 + 200 * upgrades["battery"],
        energy_per_second=1 + 0.2 * upgrades["well"],
        offline_hours=4 + 2 * upgrades["silo"],
        boost=boost,
        boost_seconds=max(0, math.ceil((state["boost_until"] - now_ms) / 1000)),
    )


def price(item, count):
    return math.ceil(item["price"] * item["growth"] ** count)


def league(earned):
    rows = [
        (0, "Росток"),
        (1000, "Огородник"),
        (10000, "Фермер"),
        (50000, "Агроном"),
        (250000, "Мастер урожая"),
        (1000000, "Хозяин долины"),
    ]
    index = sum(earned >= threshold for threshold, _ in rows) - 1
    start, name = rows[index]
    following = rows[index + 1] if index + 1 < len(rows) else None
    return dict(
        name=name,
        index=index,
        start=start,
        next=following[0] if following else None,
        next_name=following[1] if following else None,
    )


class FarmStore:
    def __init__(self, arcade):
        self.arcade = arcade
        with arcade.db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS kopatych_farms(
                player TEXT PRIMARY KEY REFERENCES arcade_players(id), state TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS kopatych_receipts(
                player TEXT NOT NULL, id TEXT NOT NULL, signature TEXT NOT NULL,
                result TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(player,id));
              CREATE TABLE IF NOT EXISTS kopatych_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, player TEXT NOT NULL,
                created REAL NOT NULL, kind TEXT NOT NULL, amount INTEGER NOT NULL,
                detail TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS kopatych_events_player
                ON kopatych_events(player,id DESC);
            """)

    def _now(self):
        return int(self.arcade.clock() * 1000)

    def _event(self, db, player, kind, amount, detail=""):
        db.execute(
            "INSERT INTO kopatych_events(player,created,kind,amount,detail) VALUES(?,?,?,?,?)",
            (player, self.arcade.clock(), kind, amount, detail),
        )

    def _load(self, db, player):
        self.arcade._player(db, player)
        row = db.execute("SELECT state FROM kopatych_farms WHERE player=?", (player,)).fetchone()
        if row:
            return json.loads(row[0])
        now = self._now()
        state = dict(
            version=1,
            balance=150,
            earned=0,
            passive=0,
            manual=0,
            taps=0,
            items={key: 0 for key in BY_ID},
            last_ms=now,
            production_carry=0,
            energy_milli=500000,
            energy_carry=0,
            tokens_milli=8000,
            boost_until=0,
            refill_after=0,
            daily=None,
            daily_last=None,
            streak=0,
            badges=[],
            created=now,
        )
        self._event(db, player, "welcome", 150, "На первые улучшения")
        return state

    def _save(self, db, player, state):
        db.execute(
            "INSERT INTO kopatych_farms VALUES(?,?) ON CONFLICT(player) "
            "DO UPDATE SET state=excluded.state",
            (player, json.dumps(state)),
        )

    def _day(self, db, player, state, now):
        day = datetime.fromtimestamp(now / 1000, MOSCOW).date().isoformat()
        if state["daily"] and state["daily"]["day"] >= day:
            return
        secret = db.execute("SELECT value FROM arcade_meta WHERE key='secret'").fetchone()[0]
        eligible = [
            item["id"]
            for item in ITEMS
            if item["unlock"] <= level(state["earned"])
            and state["items"][item["id"]] < item["maximum"]
        ]
        eligible.sort(
            key=lambda key: hmac.new(
                secret.encode(), f"farm-combo:{player}:{day}:{key}".encode(), hashlib.sha256
            ).hexdigest()
        )
        state["daily"] = dict(
            day=day,
            taps=0,
            passive=0,
            manual=0,
            upgrades=0,
            bought=[],
            claimed=[],
            combo=eligible[:3],
            boosts=0,
            refills=0,
        )

    def _settle(self, db, player, state):
        now = max(state["last_ms"], self._now())
        elapsed = now - state["last_ms"]
        values = stats(state, now)
        self._day(db, player, state, now)
        cap = values["offline_hours"] * 3600000
        effective = min(cap, elapsed)
        numerator = state["production_carry"] + effective * values["per_hour"]
        produced, state["production_carry"] = divmod(numerator, 3600000)
        state["balance"] += produced
        state["earned"] += produced
        state["passive"] += produced
        state["daily"]["passive"] += produced
        regen = state["energy_carry"] + elapsed * (1000 + state["items"]["well"] * 200)
        gain, state["energy_carry"] = divmod(regen, 1000)
        state["energy_milli"] = min(values["energy_max"] * 1000, state["energy_milli"] + gain)
        if state["energy_milli"] == values["energy_max"] * 1000:
            state["energy_carry"] = 0
        state["tokens_milli"] = min(8000, state["tokens_milli"] + elapsed * 8)
        state["last_ms"] = now
        if produced:
            self._event(db, player, "production", produced, f"{effective // 1000} с")
        return dict(
            amount=produced,
            seconds=elapsed // 1000,
            credited_seconds=effective // 1000,
            capped=elapsed > cap,
            limit_hours=values["offline_hours"],
        )

    def _quests(self, state):
        daily = state["daily"]
        available = sum(item["maximum"] - state["items"][item["id"]] for item in ITEMS)
        upgrade_goal = min(2, available)
        quests = [
            dict(
                id="tap",
                name="Разминка на грядках",
                goal=80,
                value=daily["taps"],
                reward=120,
                unit="нажатий",
            ),
            dict(
                id="passive",
                name="Ферма работает",
                goal=100,
                value=daily["passive"],
                reward=180,
                unit="морковок без нажатий",
            ),
            dict(
                id="upgrade",
                name="Растём дальше" if upgrade_goal else "Ручной урожай",
                goal=upgrade_goal or 750,
                value=daily["upgrades"] if upgrade_goal else daily["manual"],
                reward=250,
                unit="улучшения" if upgrade_goal else "морковок вручную",
            ),
        ]
        # Freeze the daily upgrade goal once it has been earned; buying the final level must not
        # replace a completed quest with a new requirement.
        if daily.get("upgrade_goal") is None:
            daily["upgrade_goal"] = upgrade_goal
        q = quests[2]
        fixed_goal = daily["upgrade_goal"]
        q.update(
            goal=fixed_goal or 750,
            value=daily["upgrades"] if fixed_goal else daily["manual"],
            name="Растём дальше" if fixed_goal else "Ручной урожай",
            unit="улучшения" if fixed_goal else "морковок вручную",
        )
        for quest in quests:
            quest["claimed"] = quest["id"] in daily["claimed"]
            quest["ready"] = quest["value"] >= quest["goal"] and not quest["claimed"]
        return quests

    def _snapshot(self, db, player, state, offline=None):
        now = state["last_ms"]
        values = stats(state, now)
        lv = level(state["earned"])
        items = []
        for item in ITEMS:
            count = state["items"][item["id"]]
            future = {**state, "items": {**state["items"], item["id"]: count + 1}}
            upgraded = stats(future, now)
            items.append(
                {
                    **item,
                    "level": count,
                    "cost": price(item, count),
                    "locked": lv < item["unlock"],
                    "maxed": count >= item["maximum"],
                    "per_hour_gain": upgraded["per_hour"] - values["per_hour"],
                    "per_tap_gain": upgraded["base_tap"] - values["base_tap"],
                    "affordable": state["balance"] >= price(item, count),
                }
            )
        daily = state["daily"]
        quests = self._quests(state)
        bonus_claimed = state["daily_last"] == daily["day"]
        today = datetime.fromisoformat(daily["day"]).date()
        yesterday = (today - timedelta(days=1)).isoformat()
        proposed_streak = state["streak"] + 1 if state["daily_last"] == yesterday else 1
        streak = state["streak"] if bonus_claimed else proposed_streak
        badges = []
        metrics = {
            "earned": state["earned"],
            "taps": state["taps"],
            "upgrades": sum(state["items"].values()),
            "passive": state["passive"],
        }
        for key, name, metric, target, reward in BADGES:
            badges.append(
                dict(
                    id=key,
                    name=name,
                    value=metrics[metric],
                    target=target,
                    reward=reward,
                    ready=metrics[metric] >= target,
                    claimed=key in state["badges"],
                )
            )
        next_day = datetime.fromisoformat(daily["day"]).replace(tzinfo=MOSCOW) + timedelta(days=1)
        events = [
            dict(r)
            for r in db.execute(
                "SELECT kind,amount,detail,created "
                "FROM kopatych_events WHERE player=? ORDER BY id DESC LIMIT 12",
                (player,),
            )
        ]
        return dict(
            player=player,
            version=1,
            balance=state["balance"],
            earned=state["earned"],
            manual=state["manual"],
            passive=state["passive"],
            taps=state["taps"],
            level=lv,
            level_start=LEVELS[lv - 1],
            level_next=LEVELS[lv] if lv < len(LEVELS) else None,
            league=league(state["earned"]),
            energy=state["energy_milli"] // 1000,
            stats=values,
            items=items,
            quests=quests,
            badges=badges,
            events=events,
            daily=dict(
                day=daily["day"],
                streak=streak,
                reward=DAILY_REWARDS[(streak - 1) % 7],
                claimed=bonus_claimed,
                rewards=DAILY_REWARDS,
                reset_at=int(next_day.timestamp() * 1000),
                combo=daily["combo"],
                bought=daily["bought"],
                combo_claimed="combo" in daily["claimed"],
                combo_ready=bool(daily["combo"])
                and all(key in daily["bought"] for key in daily["combo"]),
                combo_reward=600,
                boosts_left=2 - daily["boosts"],
                refills_left=2 - daily["refills"],
                refill_seconds=max(0, math.ceil((state["refill_after"] - now) / 1000)),
            ),
            offline=offline,
            server_ms=now,
        )

    def get(self, player):
        with self.arcade.db() as db:
            state = self._load(db, player)
            offline = self._settle(db, player, state)
            result = self._snapshot(db, player, state, offline)
            self._save(db, player, state)
            return result

    def act(self, player, action_id, action, item=None, count=1):
        if action not in (
            "tap",
            "buy",
            "claim_daily",
            "claim_quest",
            "claim_badge",
            "boost",
            "refill",
        ):
            raise ArcadeError("Неизвестное действие на ферме.")
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 20:
            raise ArcadeError("Слишком много нажатий за один раз.")
        if not isinstance(action_id, str) or not 12 <= len(action_id) <= 80:
            raise ArcadeError("Обнови ферму и попробуй ещё раз.")
        signature = json.dumps([action, item, count])
        with self.arcade.db() as db:
            state = self._load(db, player)
            offline = self._settle(db, player, state)
            previous = db.execute(
                "SELECT signature,result FROM kopatych_receipts WHERE player=? AND id=?",
                (player, action_id),
            ).fetchone()
            if previous:
                if previous["signature"] != signature:
                    raise ArcadeError("Это действие уже обработано. Обнови ферму.")
                snapshot = self._snapshot(db, player, state, offline)
                self._save(db, player, state)
                return {
                    "farm": snapshot,
                    "result": json.loads(previous["result"]),
                    "duplicate": True,
                }
            now, daily = state["last_ms"], state["daily"]
            result = {"action": action, "amount": 0}
            if action == "tap":
                accepted = min(count, state["tokens_milli"] // 1000, state["energy_milli"] // 1000)
                amount = accepted * stats(state, now)["per_tap"]
                state["tokens_milli"] -= accepted * 1000
                state["energy_milli"] -= accepted * 1000
                state["balance"] += amount
                state["earned"] += amount
                state["manual"] += amount
                state["taps"] += accepted
                daily["taps"] += accepted
                daily["manual"] += amount
                result.update(accepted=accepted, amount=amount)
                if accepted:
                    self._event(db, player, "tap", amount, str(accepted))
            elif action == "buy":
                if item not in BY_ID:
                    raise ArcadeError("Такого улучшения нет.")
                definition = BY_ID[item]
                old_level = state["items"][item]
                if level(state["earned"]) < definition["unlock"]:
                    raise ArcadeError(f"Нужен уровень {definition['unlock']}.")
                if old_level >= definition["maximum"]:
                    raise ArcadeError("Это улучшение уже прокачано полностью.")
                cost = price(definition, old_level)
                if state["balance"] < cost:
                    raise ArcadeError("Пока не хватает морковок.")
                state["balance"] -= cost
                state["items"][item] += 1
                daily["upgrades"] += 1
                if item not in daily["bought"]:
                    daily["bought"].append(item)
                result.update(item=item, amount=-cost)
                self._event(db, player, "upgrade", -cost, definition["name"])
            elif action == "claim_daily":
                if state["daily_last"] == daily["day"]:
                    raise ArcadeError("Сегодняшний подарок уже получен.")
                self._quests(state)
                bonus = self._snapshot(db, player, state)["daily"]
                state["daily_last"] = daily["day"]
                state["streak"] = bonus["streak"]
                state["balance"] += bonus["reward"]
                result["amount"] = bonus["reward"]
                self._event(db, player, "daily", result["amount"], f"День {state['streak']}")
            elif action == "claim_quest":
                if item == "combo":
                    ready = bool(daily["combo"]) and all(
                        key in daily["bought"] for key in daily["combo"]
                    )
                    reward = 600
                else:
                    quest = next((q for q in self._quests(state) if q["id"] == item), None)
                    ready, reward = bool(quest and quest["ready"]), quest["reward"] if quest else 0
                if not ready or item in daily["claimed"]:
                    raise ArcadeError("Задание ещё не выполнено или награда уже получена.")
                daily["claimed"].append(item)
                state["balance"] += reward
                result["amount"] = reward
                self._event(db, player, "quest", reward, item)
            elif action == "claim_badge":
                badge = next(
                    (b for b in self._snapshot(db, player, state)["badges"] if b["id"] == item),
                    None,
                )
                if not badge or not badge["ready"] or item in state["badges"]:
                    raise ArcadeError("Достижение ещё не открыто или награда уже получена.")
                state["badges"].append(item)
                state["balance"] += badge["reward"]
                result["amount"] = badge["reward"]
                self._event(db, player, "badge", badge["reward"], badge["name"])
            elif action == "boost":
                if daily["boosts"] >= 2 or state["boost_until"] > now:
                    raise ArcadeError("Усиление уже работает или на сегодня закончилось.")
                daily["boosts"] += 1
                state["boost_until"] = now + 30000
                self._event(db, player, "boost", 0, "Солнечный урожай ×2")
            elif action == "refill":
                if daily["refills"] >= 2 or state["refill_after"] > now:
                    raise ArcadeError("Полив пока восстанавливается. Загляни чуть позже.")
                maximum = stats(state, now)["energy_max"] * 1000
                if state["energy_milli"] >= maximum:
                    raise ArcadeError("Энергия уже полная.")
                daily["refills"] += 1
                state["energy_milli"] = maximum
                state["refill_after"] = now + 300000
                self._event(db, player, "refill", 0, "Энергия восстановлена")
            snapshot = self._snapshot(db, player, state, offline)
            self._save(db, player, state)
            db.execute(
                "INSERT INTO kopatych_receipts VALUES(?,?,?,?,?)",
                (player, action_id, signature, json.dumps(result), self.arcade.clock()),
            )
            return {"farm": snapshot, "result": result, "duplicate": False}

    def board(self, player):
        with self.arcade.db() as db:
            self.arcade._player(db, player)
            rows = []
            for row in db.execute(
                "SELECT f.player,f.state,p.name,p.group_name "
                "FROM kopatych_farms f JOIN arcade_players p ON p.id=f.player"
            ).fetchall():
                state = json.loads(row["state"])
                values = stats(state, state["last_ms"])
                elapsed = max(0, self._now() - state["last_ms"])
                effective = min(elapsed, values["offline_hours"] * 3600000)
                pending = (state["production_carry"] + effective * values["per_hour"]) // 3600000
                # Viewing a leaderboard must not extend somebody else's offline storage window.
                state["earned"] += pending
                rows.append(
                    dict(
                        player=row["player"],
                        name=row["name"],
                        group=row["group_name"],
                        earned=state["earned"],
                        per_hour=stats(state, state["last_ms"])["per_hour"],
                        level=level(state["earned"]),
                        league=league(state["earned"])["name"],
                    )
                )
            rows.sort(key=lambda r: (-r["earned"], r["player"]))
            for index, row in enumerate(rows):
                row["rank"] = index + 1
            own = next((r for r in rows if r["player"] == player), None)
            return {"rows": rows[:50], "me": own, "server_ms": self._now()}
