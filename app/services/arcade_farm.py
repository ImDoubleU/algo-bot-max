"""Persistent Kopatych farm. Carrots are isolated from arcade and school AC wallets."""

import copy
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
    4000000,
    6500000,
    10000000,
    16000000,
    25000000,
    40000000,
    65000000,
    100000000,
    160000000,
    250000000,
    400000000,
    650000000,
    1000000000,
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
        text="Каждый уровень: +10% базового сбора, минимум +1 морковка",
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
ITEMS += [
    dict(
        id="compost",
        name="Компостер",
        category="business",
        icon="compost",
        price=4500,
        growth=1.75,
        unlock=8,
        maximum=15,
        text="Питательная почва: +9% к общему урожаю за уровень",
    ),
    dict(
        id="windmill",
        name="Мельница",
        category="garden",
        icon="windmill",
        price=6500,
        growth=1.65,
        unlock=9,
        maximum=25,
        base=3800,
        text="Перерабатывает урожай всей долины",
    ),
    dict(
        id="pond",
        name="Пруд",
        category="garden",
        icon="pond",
        price=15000,
        growth=1.7,
        unlock=11,
        maximum=25,
        base=9000,
        text="Водный сад с круглосуточным урожаем",
    ),
    dict(
        id="tractor",
        name="Трактор",
        category="tools",
        icon="tractor",
        price=25000,
        growth=1.7,
        unlock=12,
        maximum=20,
        text="+20 к базовому ручному сбору за уровень; перчатки усиливают его",
    ),
    dict(
        id="nursery",
        name="Питомник",
        category="garden",
        icon="nursery",
        price=60000,
        growth=1.7,
        unlock=14,
        maximum=25,
        base=35000,
        text="Выращивает лучшие сорта для большого хозяйства",
    ),
    dict(
        id="railway",
        name="Железная дорога",
        category="garden",
        icon="railway",
        price=250000,
        growth=1.75,
        unlock=17,
        maximum=25,
        base=150000,
        text="Связывает ферму со всей долиной",
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
    ("million", "Морковный миллион", "earned", 1000000, 15000),
    ("ten_million", "Оранжевая империя", "earned", 10000000, 75000),
    ("billion", "Легенда долины", "earned", 1000000000, 1000000),
    ("tap_10000", "Без устали", "taps", 10000, 5000),
    ("tap_50000", "Мастер лопаты", "taps", 50000, 20000),
    ("build_75", "Строитель долины", "upgrades", 75, 8000),
    ("build_150", "Большие планы", "upgrades", 150, 30000),
    ("idle_100000", "Самоходная ферма", "passive", 100000, 8000),
    ("idle_million", "Урожай без границ", "passive", 1000000, 25000),
    ("variety_6", "На все руки", "variety", 6, 1000),
    ("variety_12", "Полное хозяйство", "variety", 12, 10000),
    ("variety_18", "Есть всё", "variety", 18, 50000),
    ("orders_1", "Добрый сосед", "deliveries", 1, 150),
    ("orders_10", "Надёжный поставщик", "deliveries", 10, 1500),
    ("orders_50", "Вся долина знакома", "deliveries", 50, 10000),
    ("streak_7", "Неделя на ферме", "best_streak", 7, 1500),
    ("streak_30", "Месяц заботы", "best_streak", 30, 10000),
]
CHAPTERS = [
    ("start", "Первый росток", "Вырастить первые 80 морковок", "earned", 80, 80),
    ("build", "Дом для урожая", "Купить 3 уровня улучшений", "upgrades", 3, 180),
    ("neighbour", "Знакомство с соседями", "Выполнить первый заказ", "deliveries", 1, 200),
    ("harvest", "Тысяча причин расти", "Вырастить 1 000 морковок", "earned", 1000, 400),
    ("variety", "Разнообразный огород", "Приобрести 6 разных улучшений", "variety", 6, 700),
    ("power", "Дело пошло", "Достичь дохода 2 000 в час", "income", 2000, 1000),
    ("village", "Свой человек", "Выполнить 10 заказов", "deliveries", 10, 2000),
    ("large", "Большое хозяйство", "Купить 50 уровней улучшений", "upgrades", 50, 4000),
    ("river", "На другом берегу", "Открыть пруд", "pond", 1, 6000),
    ("million", "Первый миллион", "Вырастить 1 000 000 морковок", "earned", 1000000, 12000),
    ("rail", "Дорога в долину", "Построить железную дорогу", "railway", 1, 25000),
    ("legend", "Урожайная легенда", "Вырастить 10 000 000 морковок", "earned", 10000000, 50000),
]
ORDERS = [
    dict(
        id="basket",
        name="Пирог для друзей",
        person="Ёжик",
        portrait="hedgehog",
        request="Собираю друзей на чай. Привезёшь морковку для пирога?",
        cost=40,
        profit=140,
        factor=3.6,
        seconds=300,
        unlock=1,
    ),
    dict(
        id="picnic",
        name="Большой пикник",
        person="Крош",
        portrait="rabbit",
        request="Нужен запас на целую компанию. Устроим пикник у озера!",
        cost=200,
        profit=900,
        factor=3,
        seconds=1800,
        unlock=5,
    ),
    dict(
        id="fair",
        name="Урожайная ярмарка",
        person="Совунья",
        portrait="owl",
        request="Вся долина ждёт твой урожай. Готовлю самое большое место на ярмарке.",
        cost=1000,
        profit=5000,
        factor=2.5,
        seconds=7200,
        unlock=9,
    ),
]


def level(earned):
    return min(len(LEVELS), sum(earned >= value for value in LEVELS))


def stats(state, now_ms):
    upgrades = {key: state["items"].get(key, 0) for key in BY_ID}
    production = 120 + sum(
        int(item["base"] * upgrades[item["id"]] * 1.12 ** max(0, upgrades[item["id"]] - 1))
        for item in ITEMS
        if "base" in item
    )
    production = (
        production
        * (100 + 7 * upgrades["irrigation"] + 5 * upgrades["market"] + 9 * upgrades["compost"])
        // 100
    )
    raw_tap = 1 + 2 * upgrades["shovel"] + 20 * upgrades["tractor"]
    tap = raw_tap + max(upgrades["gloves"], raw_tap * 10 * upgrades["gloves"] // 100)
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
            state = json.loads(row[0])
            for key in BY_ID:
                state["items"].setdefault(key, 0)
            state.setdefault("chapters", [])
            state.setdefault("deliveries", 0)
            state.setdefault("order", None)
            state.setdefault("best_streak", state["streak"])
            if state["daily"]:
                state["daily"].setdefault("deliveries", 0)
            state["version"] = 2
            return state
        now = self._now()
        state = dict(
            version=2,
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
            chapters=[],
            deliveries=0,
            order=None,
            best_streak=0,
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
            deliveries=0,
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
        daily.setdefault(
            "variety_goal", min(3, sum(state["items"][i["id"]] < i["maximum"] for i in ITEMS))
        )
        variety_goal = daily["variety_goal"]
        quests.extend(
            [
                dict(
                    id="manual",
                    name="Личная забота",
                    goal=600,
                    value=daily["manual"],
                    reward=180,
                    unit="морковок вручную",
                ),
                dict(
                    id="variety",
                    name="Мастер на все руки" if variety_goal else "Запас на зиму",
                    goal=variety_goal or 1000,
                    value=len(daily["bought"]) if variety_goal else daily["passive"],
                    reward=240,
                    unit="разных улучшений" if variety_goal else "морковок без нажатий",
                ),
                dict(
                    id="sun",
                    name="Солнечная смена",
                    goal=1,
                    value=daily["boosts"],
                    reward=60,
                    unit="усиление",
                ),
                dict(
                    id="delivery",
                    name="Соседская помощь",
                    goal=1,
                    value=daily["deliveries"],
                    reward=120,
                    unit="заказ",
                ),
            ]
        )
        for quest in quests:
            quest["claimed"] = quest["id"] in daily["claimed"]
            quest["ready"] = quest["value"] >= quest["goal"] and not quest["claimed"]
        return quests

    def _metrics(self, state):
        return {
            "earned": state["earned"],
            "taps": state["taps"],
            "upgrades": sum(state["items"].values()),
            "passive": state["passive"],
            "variety": sum(v > 0 for v in state["items"].values()),
            "deliveries": state["deliveries"],
            "best_streak": state["best_streak"],
            "income": stats(state, state["last_ms"])["per_hour"],
            **{key: state["items"][key] for key in ("pond", "railway")},
        }

    def _neighbors(self, state):
        thresholds = [0, 5, 15, 30, 50]
        rank = sum(state["deliveries"] >= n for n in thresholds) - 1
        return dict(
            rank=rank,
            name=["Знакомство", "Свой сосед", "Надёжный друг", "Любимец долины", "Легенда долины"][
                rank
            ],
            bonus=rank * 5,
            deliveries=state["deliveries"],
            start=thresholds[rank],
            next=thresholds[rank + 1] if rank < 4 else None,
        )

    def _offers(self, state):
        income = stats(state, state["last_ms"])["per_hour"]
        bonus = self._neighbors(state)["bonus"]
        offers = []
        for definition in ORDERS:
            profit = math.ceil(
                max(
                    definition["profit"],
                    income * definition["seconds"] / 3600 * definition["factor"],
                )
                * (100 + bonus)
                / 100
            )
            offers.append(
                {
                    **definition,
                    "profit": profit,
                    "reward": definition["cost"] + profit,
                    "income_minutes": round(profit * 60 / income),
                    "bonus": bonus,
                }
            )
        return offers

    def _chapters(self, state):
        metrics = self._metrics(state)
        first = next((key for key, *_ in CHAPTERS if key not in state["chapters"]), None)
        return [
            dict(
                id=key,
                name=name,
                text=text,
                value=metrics[metric],
                goal=goal,
                reward=reward,
                claimed=key in state["chapters"],
                locked=key != first,
                ready=key == first and metrics[metric] >= goal,
            )
            for key, name, text, metric, goal, reward in CHAPTERS
        ]

    def _available(self, state):
        """Only server-earned rewards; bonuses never increase productive experience."""
        daily = state["daily"]
        rewards = []
        if state["daily_last"] != daily["day"]:
            yesterday = (
                (datetime.fromisoformat(daily["day"]) - timedelta(days=1)).date().isoformat()
            )
            streak = state["streak"] + 1 if state["daily_last"] == yesterday else 1
            rewards.append(
                dict(
                    kind="daily", id="daily", amount=DAILY_REWARDS[(streak - 1) % 7], streak=streak
                )
            )
        for q in self._quests(state):
            if q["ready"]:
                rewards.append(dict(kind="quest", id=q["id"], amount=q["reward"]))
        if (
            daily["combo"]
            and "combo" not in daily["claimed"]
            and all(key in daily["bought"] for key in daily["combo"])
        ):
            rewards.append(dict(kind="quest", id="combo", amount=600))
        metrics = self._metrics(state)
        for key, _name, metric, target, reward in BADGES:
            if key not in state["badges"] and metrics[metric] >= target:
                rewards.append(dict(kind="badge", id=key, amount=reward))
        for key, _name, _text, metric, goal, reward in CHAPTERS:
            if key in state["chapters"]:
                continue
            if metrics[metric] < goal:
                break
            rewards.append(dict(kind="chapter", id=key, amount=reward))
        order = state["order"]
        if order and state["last_ms"] >= order["finish_at"]:
            rewards.append(dict(kind="order", id=order["id"], amount=order["reward"]))
        return rewards

    def _collect(self, db, player, state, rewards):
        for reward in rewards:
            kind, key = reward["kind"], reward["id"]
            if kind == "daily":
                state["daily_last"] = state["daily"]["day"]
                state["streak"] = reward["streak"]
                state["best_streak"] = max(state["best_streak"], state["streak"])
            elif kind == "quest":
                state["daily"]["claimed"].append(key)
            elif kind == "badge":
                state["badges"].append(key)
            elif kind == "chapter":
                state["chapters"].append(key)
            elif kind == "order":
                state["order"] = None
                state["deliveries"] += 1
                state["daily"]["deliveries"] += 1
            state["balance"] += reward["amount"]
            if db is not None:
                self._event(db, player, kind, reward["amount"], key)

    def _bundle(self, state):
        projected = copy.deepcopy(state)
        bundle = []
        while rewards := self._available(projected):
            bundle.extend(rewards)
            self._collect(None, None, projected, rewards)
        return bundle

    def _snapshot(self, db, player, state, offline=None):
        now = state["last_ms"]
        values = stats(state, now)
        lv = level(state["earned"])
        items = []
        for item in ITEMS:
            count = state["items"][item["id"]]
            future = {
                **state,
                "items": {**state["items"], item["id"]: min(count + 1, item["maximum"])},
            }
            upgraded = stats(future, now)
            without = stats({**state, "items": {**state["items"], item["id"]: 0}}, now)
            if "base" in item:
                effect = dict(
                    label="Доход этой постройки",
                    unit="/ ч",
                    current=values["per_hour"] - without["per_hour"],
                    next=upgraded["per_hour"] - without["per_hour"],
                )
            else:
                field, label, unit = (
                    ("energy_max", "Запас энергии", "энергии")
                    if item["id"] == "battery"
                    else ("energy_per_second", "Восстановление", "/ с")
                    if item["id"] == "well"
                    else ("offline_hours", "Накопление без захода", "ч")
                    if item["id"] == "silo"
                    else ("base_tap", "Ручной сбор без усиления", "/ нажатие")
                    if item["id"] in ("shovel", "gloves", "tractor")
                    else ("per_hour", "Доход всей фермы", "/ ч")
                )
                effect = dict(label=label, unit=unit, current=values[field], next=upgraded[field])
            effect["gain"] = round(effect["next"] - effect["current"], 2)
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
                    "effect": effect,
                    "payback_hours": round(
                        price(item, count) / (upgraded["per_hour"] - values["per_hour"]), 2
                    )
                    if upgraded["per_hour"] > values["per_hour"]
                    else None,
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
        metrics = self._metrics(state)
        for key, name, metric, target, reward in BADGES:
            badges.append(
                dict(
                    id=key,
                    name=name,
                    value=metrics[metric],
                    target=target,
                    reward=reward,
                    ready=metrics[metric] >= target and key not in state["badges"],
                    claimed=key in state["badges"],
                    description={
                        "earned": "Выращено морковок",
                        "taps": "Нажатия",
                        "upgrades": "Уровни улучшений",
                        "passive": "Выросло само",
                        "variety": "Разных улучшений",
                        "deliveries": "Заказы соседей",
                        "best_streak": "Дней подряд",
                    }[metric],
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
        sources = [
            dict(
                id=i["id"],
                name=i["name"],
                amount=int(
                    i["base"]
                    * state["items"][i["id"]]
                    * 1.12 ** max(0, state["items"][i["id"]] - 1)
                ),
            )
            for i in ITEMS
            if "base" in i and state["items"][i["id"]]
        ]
        raw = 120 + sum(row["amount"] for row in sources)
        available = self._bundle(state)
        return dict(
            player=player,
            version=2,
            balance=state["balance"],
            earned=state["earned"],
            manual=state["manual"],
            passive=state["passive"],
            taps=state["taps"],
            level=lv,
            level_start=LEVELS[lv - 1],
            level_next=LEVELS[lv] if lv < len(LEVELS) else None,
            roadmap=[
                dict(
                    level=n + 1,
                    earned=threshold,
                    unlocks=[i["name"] for i in ITEMS if i["unlock"] == n + 1],
                )
                for n, threshold in enumerate(LEVELS)
            ],
            league=league(state["earned"]),
            energy=state["energy_milli"] // 1000,
            stats=values,
            items=items,
            quests=quests,
            badges=badges,
            chapters=self._chapters(state),
            orders=self._offers(state),
            neighbors=self._neighbors(state),
            order=state["order"],
            deliveries=state["deliveries"],
            claimable=dict(count=len(available), amount=sum(r["amount"] for r in available)),
            production=dict(
                base=120,
                sources=sources,
                raw=raw,
                bonus=values["per_hour"] - raw,
                total=values["per_hour"],
                percent=7 * state["items"]["irrigation"]
                + 5 * state["items"]["market"]
                + 9 * state["items"]["compost"],
            ),
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
            "claim_all",
            "claim_chapter",
            "claim_order",
            "start_order",
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
            if action in ("claim_all", "claim_chapter", "claim_order"):
                collected = []
                # A completed order can finish a daily quest or chapter. Collect those too.
                while True:
                    rewards = self._available(state)
                    if action != "claim_all":
                        kind = "chapter" if action == "claim_chapter" else "order"
                        rewards = [r for r in rewards if r["kind"] == kind][:1]
                        if item and rewards and rewards[0]["id"] != item:
                            rewards = []
                    if not rewards:
                        break
                    self._collect(db, player, state, rewards)
                    collected.extend(rewards)
                    if action != "claim_all":
                        break
                if not collected and action != "claim_all":
                    raise ArcadeError("Награда пока не готова или уже получена.")
                result.update(
                    amount=sum(r["amount"] for r in collected),
                    rewards=collected,
                    count=len(collected),
                )
            elif action == "start_order":
                definition = next((o for o in self._offers(state) if o["id"] == item), None)
                if not definition or level(state["earned"]) < definition["unlock"]:
                    raise ArcadeError("Этот заказ пока недоступен.")
                if state["order"]:
                    raise ArcadeError("Сначала забери награду за текущий заказ.")
                if state["balance"] < definition["cost"]:
                    raise ArcadeError("На подготовку заказа пока не хватает морковок.")
                state["balance"] -= definition["cost"]
                state["order"] = {
                    **definition,
                    "started_at": now,
                    "finish_at": now + definition["seconds"] * 1000,
                }
                result["amount"] = -definition["cost"]
                self._event(db, player, "order_start", -definition["cost"], definition["name"])
            elif action == "tap":
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
                state["best_streak"] = max(state["best_streak"], state["streak"])
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
