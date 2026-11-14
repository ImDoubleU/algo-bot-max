"""Cosmetic cases paid in isolated play tokens, never school currency."""

import json
import secrets
from datetime import datetime

from app.services.arcade import MOSCOW, ArcadeError
from app.services.arcade_case_catalog import COLLECTIONS, QUALITIES, cases, catalogue

RARITIES = [
    dict(id="common", name="Обычный", color="#7d9bb8", fragments=1, craft=8),
    dict(id="rare", name="Редкий", color="#58b6ec", fragments=3, craft=20),
    dict(id="epic", name="Эпический", color="#bd8afa", fragments=8, craft=45),
    dict(id="legendary", name="Легендарный", color="#f8bd5b", fragments=18, craft=90),
]
BASE_ITEMS = [
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
PITY = 20
ITEMS = catalogue(BASE_ITEMS)
CASES = cases()
START_TOKENS = 300
PLAY_TOKENS = 30
DAILY_TOKEN_LIMIT = 240


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
              CREATE TABLE IF NOT EXISTS arcade_case_tokens(
                player TEXT NOT NULL REFERENCES arcade_players(id), source TEXT NOT NULL,
                amount INTEGER NOT NULL, created REAL NOT NULL, PRIMARY KEY(player,source));
            """)

    def _load(self, db, player):
        self.arcade._player(db, player)
        row = db.execute(
            "SELECT state FROM arcade_case_profiles WHERE player=?", (player,)
        ).fetchone()
        state = (
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
        # Lazy additive migration: inventory, receipts and favourite IDs are retained.
        state.setdefault("tokens", START_TOKENS)
        state.setdefault("tokens_since", self.arcade.clock())
        if "token_cursor" not in state:
            state["token_cursor"] = db.execute(
                "SELECT COALESCE(MAX(rowid),0) FROM arcade_runs WHERE player=?",
                (player,),
            ).fetchone()[0]
        self._earn(db, player, state)
        self._save(db, player, state)
        return state

    def _earn(self, db, player, state):
        from app.services.arcade import GAMES

        rows = db.execute(
            "SELECT rowid,id,game,score,report,created,accepted FROM arcade_runs "
            "WHERE player=? AND rowid>? ORDER BY rowid",
            (player, state["token_cursor"]),
        ).fetchall()
        for run in rows:
            state["token_cursor"] = run["rowid"]
            if (
                not run["accepted"]
                or run["game"] not in GAMES
                or run["score"] < GAMES[run["game"]][0]
            ):
                continue
            report = json.loads(run["report"])
            if report.get("timeMs", 0) < 15000 or not self.arcade._qualifies(
                {**report, "game": run["game"]}
            ):
                continue

            day = datetime.fromtimestamp(run["created"], MOSCOW).date().isoformat()
            source = f"play:{day}:{run['game']}"
            earned = db.execute(
                "SELECT COALESCE(SUM(amount),0) FROM arcade_case_tokens "
                "WHERE player=? AND source LIKE ?",
                (player, f"play:{day}:%"),
            ).fetchone()[0]
            if earned >= DAILY_TOKEN_LIMIT:
                continue
            amount = min(PLAY_TOKENS, DAILY_TOKEN_LIMIT - earned)
            cursor = db.execute(
                "INSERT OR IGNORE INTO arcade_case_tokens VALUES(?,?,?,?)",
                (player, source, amount, run["created"]),
            )
            if cursor.rowcount:
                state["tokens"] += amount

    @staticmethod
    def _save(db, player, state):
        db.execute(
            "INSERT INTO arcade_case_profiles VALUES(?,?) ON CONFLICT(player) "
            "DO UPDATE SET state=excluded.state",
            (player, json.dumps(state)),
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
            qualities=QUALITIES,
            collections=[dict(id=c[0], name=c[1]) for c in COLLECTIONS],
            token_reward=PLAY_TOKENS,
            token_daily_limit=DAILY_TOKEN_LIMIT,
            cases=[{**c, "unlocked": len(owned) >= c["unlock"]} for c in CASES],
            items=[
                dict(
                    **i,
                    count=owned.get(i["id"], 0),
                    craft=rarities[i["rarity"]]["craft"],
                )
                for i in ITEMS
            ],
            history=[json.loads(r[0]) for r in recent],
        )

    def get(self, player):
        with self.arcade.db() as db:
            state = self._load(db, player)
            return self._snapshot(db, player, state)

    def wallet(self, player):
        with self.arcade.db() as db:
            state = self._load(db, player)
            return dict(tokens=state["tokens"], fragments=state["fragments"])

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
            result = dict(action=action, created=now, rules=2)
            if action == "open":
                case = next((c for c in CASES if c["id"] == item), None)
                if not case or len(owned) < case["unlock"]:
                    raise ArcadeError("Сначала собери больше разных предметов.")
                if state["last_open"] is not None and now - state["last_open"] < 2:
                    raise ArcadeError("Дождись завершения открытия.")
                if state["tokens"] < case["price"]:
                    raise ArcadeError(
                        "Не хватает жетонов. Выполни цель в соревновании: "
                        "+30 жетонов за игру в день."
                    )
                guaranteed = state["since_legendary"] >= PITY - 1
                rarity = "legendary"
                if not guaranteed:
                    draw = secrets.randbelow(100)
                    for tier, weight in zip(RARITIES, case["weights"], strict=True):
                        draw -= weight
                        if draw < 0:
                            rarity = tier["id"]
                            break
                pool = [
                    i
                    for i in ITEMS
                    if i["rarity"] == rarity and i["collection"] == case["collection"]
                ]
                # Prefer uncollected items within the rolled rarity. No artificial near misses.
                pool = [i for i in pool if i["id"] not in owned] or pool
                selected = pool[secrets.randbelow(len(pool))]
                state["since_legendary"] = (
                    0 if rarity == "legendary" else state["since_legendary"] + 1
                )
                state["opens"] += 1
                state["last_open"] = now
                extra = (
                    next(r["fragments"] for r in RARITIES if r["id"] == rarity)
                    if selected["id"] in owned
                    else 0
                )
                state["fragments"] += extra
                state["tokens"] -= case["price"]
                result.update(
                    item=selected["id"],
                    rarity=rarity,
                    quality=selected["quality"],
                    new=selected["id"] not in owned,
                    fragments=extra,
                    guaranteed=guaranteed,
                    case=item,
                    tokens=-case["price"],
                )
                self._grant(db, player, selected["id"], now)
            elif action == "craft":
                selected = next((i for i in ITEMS if i["id"] == item), None)
                if not selected or item in owned:
                    raise ArcadeError("Этот предмет уже есть в коллекции или недоступен.")
                cost = next(r["craft"] for r in RARITIES if r["id"] == selected["rarity"])
                if state["fragments"] < cost:
                    raise ArcadeError("Пока не хватает деталей. Их дают за повторные предметы.")
                state["fragments"] -= cost
                self._grant(db, player, item, now)
                result.update(item=item, rarity=selected["rarity"], new=True, fragments=-cost)
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
