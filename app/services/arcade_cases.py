"""Free cosmetic case simulator. Own ledger; never reads or spends school currency."""

import json
import secrets

from app.services.arcade import ArcadeError

RARITIES = [
    dict(id="common", name="Обычный", color="#7d9bb8", fragments=1, craft=8),
    dict(id="rare", name="Редкий", color="#58b6ec", fragments=3, craft=20),
    dict(id="epic", name="Эпический", color="#bd8afa", fragments=8, craft=45),
    dict(id="legendary", name="Легендарный", color="#f8bd5b", fragments=18, craft=90),
]
ITEMS = [
    ("radio", "Полевое радио", "common"),
    ("boots", "Лунные ботинки", "common"),
    ("thermos", "Термос пилота", "common"),
    ("compass", "Звёздный компас", "common"),
    ("camera", "Камера разведчика", "common"),
    ("headphones", "Радионаушники", "common"),
    ("helmet", "Шлем исследователя", "rare"),
    ("board", "Реактивный скейт", "rare"),
    ("plant", "Космический росток", "rare"),
    ("drone", "Почтовый дрон", "rare"),
    ("gamepad", "Пульт экспедиции", "rare"),
    ("telescope", "Мини-обсерватория", "rare"),
    ("robot", "Робот-компаньон", "epic"),
    ("fox", "Киберлис", "epic"),
    ("engine", "Ионный двигатель", "epic"),
    ("satellite", "Личный спутник", "epic"),
    ("ship", "Корабль «Рассвет»", "legendary"),
    ("planet", "Планета в капсуле", "legendary"),
    ("portal", "Карманный портал", "legendary"),
    ("dragon", "Звёздный дракон", "legendary"),
]
CASES = [
    dict(
        id="scout",
        name="Первая экспедиция",
        subtitle="Снаряжение исследователя",
        unlock=0,
        weights=[60, 27, 10, 3],
        color="#df9655",
    ),
    dict(
        id="neon",
        name="Неоновый сектор",
        subtitle="Находки с дальней станции",
        unlock=6,
        weights=[40, 35, 20, 5],
        color="#67c9c1",
    ),
    dict(
        id="relic",
        name="За горизонтом",
        subtitle="Артефакты глубокого космоса",
        unlock=12,
        weights=[25, 35, 30, 10],
        color="#b49ae8",
    ),
]
PITY = 20


class CaseStore:
    def __init__(self, arcade):
        self.arcade = arcade
        with arcade.db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS arcade_case_profiles(
                player TEXT PRIMARY KEY REFERENCES arcade_players(id), state TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_case_inventory(
                player TEXT NOT NULL REFERENCES arcade_players(id), item TEXT NOT NULL,
                count INTEGER NOT NULL, acquired REAL NOT NULL, PRIMARY KEY(player,item));
              CREATE TABLE IF NOT EXISTS arcade_case_receipts(
                player TEXT NOT NULL REFERENCES arcade_players(id), id TEXT NOT NULL,
                signature TEXT NOT NULL, result TEXT NOT NULL, created REAL NOT NULL,
                PRIMARY KEY(player,id));
              CREATE INDEX IF NOT EXISTS arcade_cases_recent
                ON arcade_case_receipts(player,created);
            """)

    def _load(self, db, player):
        self.arcade._player(db, player)
        row = db.execute(
            "SELECT state FROM arcade_case_profiles WHERE player=?", (player,)
        ).fetchone()
        return (
            json.loads(row[0])
            if row
            else dict(
                opens=0,
                fragments=0,
                since_legendary=0,
                favorite=None,
                last_open=None,
            )
        )

    def _snapshot(self, db, player, state):
        owned = {
            r["item"]: r["count"]
            for r in db.execute(
                "SELECT item,count FROM arcade_case_inventory WHERE player=?", (player,)
            )
        }
        rarities = {r["id"]: r for r in RARITIES}
        recent = db.execute(
            "SELECT result FROM arcade_case_receipts WHERE player=? "
            "AND json_extract(result,'$.action') IN ('open','craft') "
            "ORDER BY created DESC,rowid DESC LIMIT 12",
            (player,),
        ).fetchall()
        return dict(
            player=player,
            **state,
            total=len(ITEMS),
            collected=len(owned),
            pity=PITY,
            guaranteed_in=PITY - state["since_legendary"],
            wait=max(0, 2 - (self.arcade.clock() - state["last_open"]))
            if state["last_open"] is not None
            else 0,
            rarities=RARITIES,
            cases=[{**c, "unlocked": len(owned) >= c["unlock"]} for c in CASES],
            items=[
                dict(
                    id=key,
                    name=name,
                    rarity=rarity,
                    count=owned.get(key, 0),
                    craft=rarities[rarity]["craft"],
                )
                for key, name, rarity in ITEMS
            ],
            history=[json.loads(r[0]) for r in recent],
        )

    def get(self, player):
        with self.arcade.db() as db:
            state = self._load(db, player)
            return self._snapshot(db, player, state)

    def act(self, player, token, action, item):
        if not isinstance(token, str) or not 12 <= len(token) <= 80:
            raise ArcadeError("Обнови окно коллекции и попробуй ещё раз.")
        signature = json.dumps([action, item])
        with self.arcade.db() as db:
            state = self._load(db, player)
            previous = db.execute(
                "SELECT signature,result FROM arcade_case_receipts WHERE player=? AND id=?",
                (player, token),
            ).fetchone()
            if previous:
                if previous["signature"] != signature:
                    raise ArcadeError("Это действие уже обработано. Обнови коллекцию.")
                return dict(
                    snapshot=self._snapshot(db, player, state),
                    result=json.loads(previous["result"]),
                    duplicate=True,
                )
            now = self.arcade.clock()
            recent_count = db.execute(
                "SELECT COUNT(*) FROM arcade_case_receipts WHERE player=? AND created>?",
                (player, now - 60),
            ).fetchone()[0]
            if recent_count >= 60:
                raise ArcadeError("Слишком много действий подряд. Подожди минуту.")
            owned = {
                r[0]: r[1]
                for r in db.execute(
                    "SELECT item,count FROM arcade_case_inventory WHERE player=?", (player,)
                )
            }
            result = dict(action=action, created=now, rules=1)
            if action == "open":
                case = next((c for c in CASES if c["id"] == item), None)
                if not case or len(owned) < case["unlock"]:
                    raise ArcadeError("Сначала собери больше разных предметов.")
                if state["last_open"] is not None and now - state["last_open"] < 2:
                    raise ArcadeError("Дождись завершения открытия.")
                guaranteed = state["since_legendary"] >= PITY - 1
                rarity = "legendary"
                if not guaranteed:
                    draw = secrets.randbelow(100)
                    for tier, weight in zip(RARITIES, case["weights"], strict=True):
                        draw -= weight
                        if draw < 0:
                            rarity = tier["id"]
                            break
                pool = [i for i in ITEMS if i[2] == rarity]
                # Prefer uncollected items within the rolled rarity. No artificial near misses.
                pool = [i for i in pool if i[0] not in owned] or pool
                selected = pool[secrets.randbelow(len(pool))]
                state["since_legendary"] = (
                    0 if rarity == "legendary" else state["since_legendary"] + 1
                )
                state["opens"] += 1
                state["last_open"] = now
                extra = (
                    next(r["fragments"] for r in RARITIES if r["id"] == rarity)
                    if selected[0] in owned
                    else 0
                )
                state["fragments"] += extra
                result.update(
                    item=selected[0],
                    rarity=rarity,
                    new=selected[0] not in owned,
                    fragments=extra,
                    guaranteed=guaranteed,
                    case=item,
                )
                self._grant(db, player, selected[0], now)
            elif action == "craft":
                selected = next((i for i in ITEMS if i[0] == item), None)
                if not selected or item in owned:
                    raise ArcadeError("Этот предмет уже есть в коллекции или недоступен.")
                cost = next(r["craft"] for r in RARITIES if r["id"] == selected[2])
                if state["fragments"] < cost:
                    raise ArcadeError("Пока не хватает деталей. Их дают за повторные предметы.")
                state["fragments"] -= cost
                self._grant(db, player, item, now)
                result.update(item=item, rarity=selected[2], new=True, fragments=-cost)
            elif action == "favorite":
                if item not in owned:
                    raise ArcadeError("Сначала открой этот предмет.")
                state["favorite"] = item
                result["item"] = item
            else:
                raise ArcadeError("Такого действия в коллекции нет.")
            db.execute(
                "INSERT INTO arcade_case_profiles VALUES(?,?) ON CONFLICT(player) "
                "DO UPDATE SET state=excluded.state",
                (player, json.dumps(state)),
            )
            db.execute(
                "INSERT INTO arcade_case_receipts VALUES(?,?,?,?,?)",
                (player, token, signature, json.dumps(result), now),
            )
            return dict(snapshot=self._snapshot(db, player, state), result=result, duplicate=False)

    @staticmethod
    def _grant(db, player, item, now):
        db.execute(
            "INSERT INTO arcade_case_inventory VALUES(?,?,1,?) ON CONFLICT(player,item) "
            "DO UPDATE SET count=count+1",
            (player, item, now),
        )
