"""Isolated, transactional local arcade backend. No school wallet or binding writes.

All ranked scores are replayed by arcade_runtime. SQLite is deliberately separate
from collection and school databases. Production mounting is an allowlisted staff pilot.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from app.services import arcade_hill, arcade_journey, arcade_runtime
from app.services.arcade_mastery import league, mastery

MOSCOW = timezone(timedelta(hours=3))
SPEED = {"orbit", "bugs", "tower", "typing", "react", "kopatych", "words"}
FINITE = {"typing", "debug", "memory", "react", "kopatych", "words"}
GAMES = {
    "orbit": (8, [25, 40, 60]),
    "evolve": (128, [1024, 2048, 4096]),
    "bugs": (20, [50, 80, 120]),
    "tower": (8, [25, 40, 60]),
    "typing": (120, [240, 320, 400]),
    "debug": (5, [8, 8, 8]),
    "2048": (128, [1024, 2048, 4096]),
    "drop": (100, [1000, 2500, 5000]),
    "memory": (8, [28, 40, 40]),
    "react": (5, [15, 15, 15]),
    "kopatych": (300, [12000, 30000, 60000]),
    "blocks": (300, [2000, 4000, 7000]),
    "hill": (500, [1500, 3000, 6000]),
    "bubbles": (200, [1500, 3000, 5000]),
    "sort": (3, [10, 15, 20]),
    "words": (10, [24, 32, 40]),
}
POINTS = [100, 80, 65, 55, 45, 35, 25, 20, 15, 10]
PRIZES = [100, 75, 50]
FIRST_GOAL_REWARD = 5
MEDAL_REWARDS = [3, 5, 10]
# A fixed Monday anchor keeps seasons stable across years and server restarts.
SEASON_ANCHOR = datetime(2026, 11, 2).date()
DEFAULT_SETTINGS = {
    "sound": False,
    "vibration": False,
    "quality": "auto",
    "theme": "space",
    "skin": "base",
    "tutorials": [],
    "ui": {"tab": "games", "filter": "all", "scroll": 0},
}


async def maintenance_worker(store, interval=15):
    while True:
        try:
            await asyncio.to_thread(store.maintain)
        except Exception:
            logging.getLogger(__name__).exception("Arcade maintenance failed; retrying")
        await asyncio.sleep(interval)


def week_key(stamp: float) -> str:
    today = datetime.fromtimestamp(stamp, MOSCOW).date()
    return (today - timedelta(days=today.weekday())).isoformat()


def season_key(stamp: float) -> str:
    today = datetime.fromtimestamp(stamp, MOSCOW).date()
    return (SEASON_ANCHOR + timedelta(days=((today - SEASON_ANCHOR).days // 14) * 14)).isoformat()


def season_info(stamp: float) -> dict:
    start = season_key(stamp)
    end = (datetime.fromisoformat(start) + timedelta(days=14)).date().isoformat()
    return {"start": start, "end": end, "days": 14}


def iso(stamp: float) -> str:
    return datetime.fromtimestamp(stamp, UTC).isoformat()


class ArcadeError(ValueError):
    pass


class ArcadeStore:
    def __init__(self, path: Path, clock=time.time):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self.db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS arcade_journeys(
                player TEXT NOT NULL REFERENCES arcade_players(id), game TEXT NOT NULL,
                stage INTEGER NOT NULL, stars INTEGER NOT NULL, score INTEGER NOT NULL,
                completed REAL NOT NULL, details TEXT NOT NULL,
                PRIMARY KEY(player,game,stage));
              CREATE TABLE IF NOT EXISTS arcade_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_players(id TEXT PRIMARY KEY,name TEXT NOT NULL,
                group_name TEXT NOT NULL,settings TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_sessions(id TEXT PRIMARY KEY,player TEXT NOT NULL,
                game TEXT NOT NULL,mode TEXT NOT NULL,device TEXT NOT NULL,seed INTEGER NOT NULL,
                created REAL NOT NULL,started REAL,paused REAL,pause_seconds REAL NOT NULL
                DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ready',setup TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_runs(id TEXT PRIMARY KEY,session TEXT NOT
                NULL UNIQUE,
                player TEXT NOT NULL,game TEXT NOT NULL,mode TEXT NOT NULL,device TEXT NOT NULL,
                week TEXT NOT NULL,created REAL NOT NULL,score INTEGER NOT NULL,rank_score
                INTEGER NOT NULL,
                report TEXT NOT NULL,actions TEXT NOT NULL,ticks INTEGER NOT NULL,accepted
                INTEGER NOT NULL);
              CREATE INDEX IF NOT EXISTS arcade_runs_player ON arcade_runs(player,created);
              CREATE INDEX IF NOT EXISTS arcade_runs_league ON arcade_runs(week,game,accepted);
              CREATE TABLE IF NOT EXISTS arcade_awards(id TEXT PRIMARY KEY,player TEXT NOT NULL,
                kind TEXT NOT NULL,period TEXT NOT NULL,amount INTEGER NOT NULL,label TEXT NOT NULL,
                created REAL NOT NULL,claimed INTEGER NOT NULL DEFAULT 0,credited REAL);
              CREATE TABLE IF NOT EXISTS arcade_credits(award TEXT PRIMARY KEY,player TEXT NOT NULL,
                week TEXT NOT NULL,amount INTEGER NOT NULL,created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_receipts(session TEXT PRIMARY KEY,
                payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_weeks(week TEXT PRIMARY KEY,closed REAL NOT NULL,
                winners TEXT NOT NULL,standings TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_seasons(week TEXT PRIMARY KEY,closed REAL NOT NULL,
                winners TEXT NOT NULL,standings TEXT NOT NULL);
              -- Historical settings are retained, but no longer restrict payouts.
              CREATE TABLE IF NOT EXISTS arcade_policy(week TEXT PRIMARY KEY,cap INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_log(id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL NOT NULL,player TEXT,session TEXT,event TEXT NOT NULL,detail
                TEXT NOT NULL);
            """)
            arcade_hill.install(db)
            from app.services import arcade_words

            arcade_words.install(db)
            db.execute(
                "INSERT OR IGNORE INTO arcade_meta VALUES('secret',?)", (secrets.token_hex(32),)
            )
            # Historical weekly podiums stay intact; never pay them again as old seasons.
            db.execute(
                "INSERT OR IGNORE INTO arcade_meta VALUES('season_prizes_start',?)",
                (season_key(self.clock()),),
            )

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def register(self, players: list[dict]):
        with self.db() as db:
            for player in players:
                db.execute(
                    """INSERT INTO arcade_players VALUES(?,?,?,?) ON CONFLICT(id)
                  DO UPDATE SET name=excluded.name,group_name=excluded.group_name""",
                    (
                        player["id"],
                        player["name"],
                        player.get("group", ""),
                        json.dumps(DEFAULT_SETTINGS),
                    ),
                )

    def _player(self, db, player):
        row = db.execute("SELECT * FROM arcade_players WHERE id=?", (player,)).fetchone()
        if not row:
            raise ArcadeError("Игрок не найден. Открой раздел заново.")
        return dict(row)

    def _log(self, db, player, session, event, detail=""):
        db.execute(
            "INSERT INTO arcade_log(created,player,session,event,detail) VALUES(?,?,?,?,?)",
            (self.clock(), player, session, event, str(detail)[:300]),
        )

    def _award(self, db, player, kind, period, key, amount, label, claimed=False):
        inserted = db.execute(
            "INSERT OR IGNORE INTO arcade_awards VALUES(?,?,?,?,?,?,?,?,NULL)",
            (key, player, kind, period, amount, label, self.clock(), int(claimed)),
        ).rowcount
        if claimed:
            collected = db.execute(
                "UPDATE arcade_awards SET claimed=1 WHERE id=? AND player=? AND claimed=0",
                (key, player),
            ).rowcount
            return key if inserted or collected else None
        return None

    def _credit(self, db, player):
        period = week_key(self.clock())
        rows = db.execute(
            """SELECT * FROM arcade_awards WHERE player=? AND claimed=1 AND credited IS NULL
          ORDER BY CASE kind WHEN 'podium' THEN 0 WHEN 'weekly' THEN 1 WHEN 'first' THEN 1
          ELSE 2 END,created,id""",
            (player,),
        ).fetchall()
        for row in rows:
            db.execute(
                "INSERT OR IGNORE INTO arcade_credits VALUES(?,?,?,?,?)",
                (row["id"], player, period, row["amount"], self.clock()),
            )
            db.execute("UPDATE arcade_awards SET credited=? WHERE id=?", (self.clock(), row["id"]))

    def _qualifies(self, report):
        return (
            report["game"] in GAMES
            and report["score"] >= GAMES[report["game"]][0]
            and (report["game"] != "typing" or report["details"].get("accuracy", 0) >= 90)
        )

    def _receipt(self, db, session):
        row = db.execute(
            "SELECT payload FROM arcade_receipts WHERE session=?", (session,)
        ).fetchone()
        receipt = json.loads(row[0]) if row else {"awards": [], "credited": 0, "pending": 0}
        awards = receipt["awards"]
        if awards:
            marks = ",".join("?" for _ in awards)
            credited = {
                row["id"]: row["credited"] is not None
                for row in db.execute(
                    f"SELECT id,credited FROM arcade_awards WHERE id IN ({marks})",
                    [award["id"] for award in awards],
                )
            }
            for award in awards:
                award["credited"] = credited.get(award["id"], award["credited"])
            receipt["credited"] = sum(a["amount"] for a in awards if a["credited"])
            receipt["pending"] = sum(a["amount"] for a in awards if not a["credited"])
        return receipt

    def _goal_award(self, db, player, game):
        # A previously earned weekly goal counts as the lifetime first reward.
        # Keep its original amount, including legacy pending/unclaimed awards.
        return db.execute(
            "SELECT * FROM arcade_awards WHERE player=? AND "
            "(id=? OR (kind='weekly' AND id LIKE ?)) "
            "ORDER BY credited IS NULL,created,id LIMIT 1",
            (player, f"first:{player}:{game}", f"%:{game}"),
        ).fetchone()

    def _master(self, game, score, details, tier):
        if game not in GAMES or score < GAMES[game][1][tier]:
            return False
        return self._quality(game, details, tier)

    def _quality(self, game, details, tier):
        rules = self._medal_requirements(game, tier)
        return (
            ("accuracy" not in rules or details.get("accuracy", 0) >= rules["accuracy"])
            and ("mistakes" not in rules or details.get("mistakes", 99) == rules["mistakes"])
            and (
                "reactionMs" not in rules
                or 80 <= details.get("reactionMs", 0) <= rules["reactionMs"]
            )
            and ("timeMs" not in rules or 0 < details.get("timeMs", 0) <= rules["timeMs"])
            and ("moves" not in rules or 0 < details.get("moves", 0) <= rules["moves"])
        )

    def _medal_requirements(self, game, tier):
        """Machine-readable counterparts of the conditions displayed to the player."""
        if game == "typing":
            return {"accuracy": [95, 97, 99][tier]}
        if game == "react":
            return {"mistakes": 0, "reactionMs": [320, 260, 220][tier]}
        if game == "debug":
            return {"timeMs": [180000, 120000, 60000][tier]}
        if game == "memory" and tier > 0:
            return {"moves": [0, 80, 60][tier]}
        if game == "words" and tier == 2:
            return {"timeMs": 150000}
        return {}

    def _medal_condition(self, game, tier):
        if game == "typing":
            return f"точность от {[95, 97, 99][tier]}%"
        if game == "react":
            return f"без ошибок, средняя реакция до {[320, 260, 220][tier]} мс"
        if game == "debug":
            return f"все задачи без ошибок за {[180, 120, 60][tier]} с"
        if game == "memory" and tier > 0:
            return f"не больше {[0, 80, 60][tier]} ходов"
        if game == "words" and tier == 2:
            return "за 150 с"
        return "за одну соревновательную партию"

    def session(self, player, game, mode, device, stage=None, arena=None):
        if (
            game not in GAMES
            or mode not in ("ranked", "practice", "journey")
            or device not in ("keyboard", "touch")
        ):
            raise ArcadeError("Выбери игру и режим заново.")
        if arena is not None and not (
            mode == "practice"
            and (
                game == "drop"
                and arena in ("classic", "bowl", "slopes", "pins")
                or game == "hill"
                and arena in dict(arcade_hill.ROUTES)
            )
        ):
            raise ArcadeError(
                "Выбери доступную трассу в свободном заезде."
                if game == "hill"
                else "Выбор арены доступен в тренировке Космодропа."
            )
        with self.db() as db:
            self._player(db, player)
            if mode != "journey" and stage is not None:
                raise ArcadeError("Номер задания доступен только в приключении.")
            try:
                journey = (
                    arcade_journey.prepare(db, player, game, stage) if mode == "journey" else None
                )
            except ValueError as error:
                raise ArcadeError(str(error)) from error
            count = db.execute(
                "SELECT COUNT(*) FROM arcade_sessions WHERE player=? AND created>?",
                (player, self.clock() - 60),
            ).fetchone()[0]
            if count >= 30:
                raise ArcadeError("Слишком много новых попыток. Подожди минуту.")
            secret = db.execute("SELECT value FROM arcade_meta WHERE key='secret'").fetchone()[0]
            controls = "pedals" if game == "hill" else device
            challenge = f"v3:{season_key(self.clock())}:{game}:{controls}".encode()
            seed = int.from_bytes(
                hmac.new(secret.encode(), challenge, hashlib.sha256).digest()[:4], "big"
            )
            if mode == "practice":
                seed = secrets.randbits(32)
            previous = db.execute(
                """SELECT report FROM arcade_runs WHERE player=? AND game='typing'
              ORDER BY created DESC LIMIT 5""",
                (player,),
            ).fetchall()
            weak = {}
            for row in previous:
                for ch, misses in json.loads(row[0]).get("badKeys", {}).items():
                    if ch.isalpha():
                        weak[ch] = weak.get(ch, 0) + misses
            setup = {
                "game": game,
                "seed": seed,
                "mode": mode,
                "device": device,
                "continuous": True,
                "weak": "".join(sorted(weak, key=weak.get, reverse=True)[:6])
                if mode == "practice"
                else "",
            }
            if game == "drop":
                setup["dropPhysics"] = 4
                setup["arena"] = arena or "classic"
            if game == "sort" and mode == "ranked":
                setup["roundSeconds"] = 600
            if game == "sort":
                setup["sortRules"] = 2
            if game == "words":
                setup["wordDictionary"] = 2
                from app.services import arcade_words

                setup["wordRoots"] = arcade_words.prepare(db, player)
            if game in ("typing", "debug"):
                setup["lessonVersion"] = 2
            if game == "evolve":
                setup["evolveRules"] = 2
            if journey:
                setup["journey"] = journey
                seed = int.from_bytes(
                    hmac.new(
                        secret.encode(),
                        f"journey-v1:{game}:{journey['stage']}".encode(),
                        hashlib.sha256,
                    ).digest()[:4],
                    "big",
                )
                setup["seed"] = seed
            if game == "hill":
                setup["hill"] = arcade_hill.setup(
                    db, player, mode, arena, journey["stage"] if journey else None
                )
            session = secrets.token_urlsafe(24)
            db.execute(
                """INSERT INTO arcade_sessions(id,player,game,mode,device,seed,created,setup)
              VALUES(?,?,?,?,?,?,?,?)""",
                (session, player, game, mode, device, seed, self.clock(), json.dumps(setup)),
            )
            return {"id": session, "setup": setup, "rule": 3, "server_time": iso(self.clock())}

    def clock_action(self, player, session, action):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM arcade_sessions WHERE id=? AND player=?", (session, player)
            ).fetchone()
            if not row or row["status"] == "finished" or self.clock() - row["created"] > 7200:
                raise ArcadeError("Эта попытка уже закрыта. Начни новую игру.")
            if action in ("pause", "resume") and json.loads(row["setup"]).get("continuous"):
                raise ArcadeError("В этой партии время идёт без пауз.")
            if action == "start" and row["started"] is None:
                db.execute(
                    "UPDATE arcade_sessions SET started=?,status='playing' WHERE id=?",
                    (self.clock(), session),
                )
            elif action == "pause" and row["started"] is not None and row["paused"] is None:
                db.execute(
                    "UPDATE arcade_sessions SET paused=?,status='paused' WHERE id=?",
                    (self.clock(), session),
                )
            elif action == "resume" and row["paused"] is not None:
                db.execute(
                    """UPDATE arcade_sessions SET pause_seconds=pause_seconds+?,paused=NULL,
                  status='playing' WHERE id=?""",
                    (self.clock() - row["paused"], session),
                )
            elif action not in ("start", "pause", "resume"):
                raise ArcadeError("Неизвестное действие.")
            return {"ok": True, "server_time": iso(self.clock())}

    def finish(self, player, session, actions, ticks, abandoned=False):
        with self.db() as db:
            previous = db.execute(
                "SELECT * FROM arcade_runs WHERE session=? AND player=?", (session, player)
            ).fetchone()
            if previous:
                self._credit(db, player)
                return {
                    "run": {
                        "id": previous["id"],
                        "score": previous["score"],
                        "accepted": bool(previous["accepted"]),
                        "report": json.loads(previous["report"]),
                    },
                    "duplicate": True,
                    "rewards": {"awards": [], "credited": 0, "pending": 0},
                    "receipt": self._receipt(db, session),
                    "garage_coins": arcade_hill.reward_for(db, session),
                }
            row = db.execute(
                "SELECT * FROM arcade_sessions WHERE id=? AND player=?", (session, player)
            ).fetchone()
            if not row or row["started"] is None or self.clock() - row["created"] > 7200:
                raise ArcadeError("Попытка не найдена или истекла. Начни новую игру.")
            active = (row["paused"] or self.clock()) - row["started"] - row["pause_seconds"]
            if not isinstance(ticks, int) or ticks < 0 or ticks / 60 > active + 0.18:
                self._log(db, player, session, "clock_rejected")
                db.commit()  # Preserve the rejection event when the transaction unwinds.
                raise ArcadeError("Время партии не совпало. Начни новую попытку.")
            setup = json.loads(row["setup"])
            row = dict(row)
        if not isinstance(actions, list) or len(actions) > 20000:
            raise ArcadeError("Слишком длинная запись партии.")
        buckets = {}
        for action in actions:
            if not isinstance(action, dict) or not isinstance(action.get("t"), int):
                raise ArcadeError("Запись партии повреждена.")
            second = action["t"] // 60
            buckets[second] = buckets.get(second, 0) + 1
            if buckets[second] > 50:
                raise ArcadeError("Нажатия слишком частые. Начни новую попытку.")
            if row["game"] in SPEED and action.get("source", row["device"]) != row["device"]:
                raise ArcadeError("Способ управления изменился. Выбери его перед новой партией.")
        try:
            report = arcade_runtime.verify(setup, actions, ticks)
        except arcade_runtime.InvalidArcadeRun as error:
            with self.db() as db:
                self._log(db, player, session, "replay_rejected", type(error.__cause__).__name__)
            raise ArcadeError(str(error)) from error
        report["game"] = row["game"]
        if row["game"] == "typing" and report["score"] > max(20, active * 25):
            raise ArcadeError("Слишком быстрый ввод для этой попытки. Попробуй ещё раз.")
        if (
            row["game"] == "react"
            and report["score"] >= 5
            and report["details"].get("reactionMs", 0) < 80
        ):
            raise ArcadeError("Время реакции не прошло проверку. Начни новую попытку.")
        # Closing the page on the winning frame must not erase a completed level.
        abandoned = bool(abandoned and not report["complete"])
        accepted = (
            row["mode"] == "ranked"
            and row["game"] in GAMES
            and (report["complete"] or not setup.get("continuous") and row["game"] not in FINITE)
            and not abandoned
            and season_key(row["created"]) == season_key(self.clock())
        )
        key = secrets.token_urlsafe(18)
        now = self.clock()
        with self.db() as db:
            previous = db.execute(
                "SELECT * FROM arcade_runs WHERE session=?", (session,)
            ).fetchone()
            if previous:
                self._credit(db, player)
                return {
                    "run": {
                        "id": previous["id"],
                        "score": previous["score"],
                        "accepted": bool(previous["accepted"]),
                        "report": json.loads(previous["report"]),
                    },
                    "duplicate": True,
                    "rewards": {"awards": [], "credited": 0, "pending": 0},
                    "receipt": self._receipt(db, session),
                    "garage_coins": arcade_hill.reward_for(db, session),
                }
            db.execute(
                "INSERT INTO arcade_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    session,
                    player,
                    row["game"],
                    row["mode"],
                    row["device"],
                    week_key(now),
                    now,
                    report["score"],
                    report["rankScore"],
                    json.dumps(report, ensure_ascii=False),
                    json.dumps(actions),
                    ticks,
                    int(accepted),
                ),
            )
            db.execute("UPDATE arcade_sessions SET status='finished' WHERE id=?", (session,))
            reward_keys = []

            def grant(kind, period, award_key, amount, label):
                collected = self._award(
                    db, player, kind, period, award_key, amount, label, claimed=True
                )
                if collected:
                    reward_keys.append(collected)

            def grant_first_goal(game):
                previous_goal = self._goal_award(db, player, game)
                if previous_goal:
                    grant(
                        previous_goal["kind"],
                        previous_goal["period"],
                        previous_goal["id"],
                        previous_goal["amount"],
                        previous_goal["label"],
                    )
                else:
                    title = next(g["name"] for g in arcade_runtime.catalogue() if g["id"] == game)
                    grant(
                        "first",
                        "all",
                        f"first:{player}:{game}",
                        FIRST_GOAL_REWARD,
                        f"{title} · первое выполнение цели",
                    )

            if (
                row["game"] in GAMES
                and row["mode"] == "journey"
                and not abandoned
                and report.get("journey", {}).get("success")
            ):
                arcade_journey.record(db, player, row["game"], report, now)
                if self._qualifies(report):
                    grant_first_goal(row["game"])
            if accepted:
                game = row["game"]
                title = next(g["name"] for g in arcade_runtime.catalogue() if g["id"] == game)
                if self._qualifies(report):
                    grant_first_goal(game)
                for tier in range(3):
                    if self._master(game, report["score"], report["details"], tier):
                        amount = MEDAL_REWARDS[tier]
                        grant(
                            "master",
                            "all",
                            f"master3:{player}:{game}:{tier}",
                            amount,
                            f"{title} · {['бронза', 'серебро', 'золото'][tier]}",
                        )
            garage_coins = 0
            if row["game"] == "hill" and report["complete"] and not abandoned:
                garage_coins = arcade_hill.record(db, player, session, report, now)
            self._credit(db, player)
            rewards = {"awards": [], "credited": 0, "pending": 0}
            for award_key in reward_keys:
                award = db.execute(
                    "SELECT id,amount,label,credited FROM arcade_awards WHERE id=? AND player=?",
                    (award_key, player),
                ).fetchone()
                credited = award["credited"] is not None
                rewards["awards"].append(
                    dict(
                        id=award["id"],
                        amount=award["amount"],
                        label=award["label"],
                        credited=credited,
                    )
                )
                rewards["credited" if credited else "pending"] += award["amount"]
            if reward_keys:
                self._log(
                    db,
                    player,
                    session,
                    "rewards_collected",
                    f"awards={len(reward_keys)};credited={rewards['credited']};pending={rewards['pending']}",
                )
            self._log(
                db, player, session, "run_verified", f"{row['game']}:{report['score']}:{accepted}"
            )
            db.execute("INSERT INTO arcade_receipts VALUES(?,?)", (session, json.dumps(rewards)))
        return {
            "run": {"id": key, "score": report["score"], "accepted": accepted, "report": report},
            "duplicate": False,
            "rewards": rewards,
            "receipt": rewards,
            "garage_coins": garage_coins,
        }

    def _rows(self, db, period, game=None):
        query = (
            "SELECT r.player,r.game,r.device,r.created,r.score,r.rank_score,r.report,"
            "p.name,p.group_name FROM arcade_runs r "
            "JOIN arcade_players p ON p.id=r.player WHERE accepted=1"
        )
        args = []
        if period != "all":
            end = (datetime.fromisoformat(period) + timedelta(days=14)).date().isoformat()
            query += " AND r.week>=? AND r.week<?"
            args.extend((period, end))
        if game:
            query += " AND r.game=?"
            args.append(game)
        return [dict(r) for r in db.execute(query, args)]

    def _game_board(self, rows, game, device=None, qualified=False):
        best = {}
        for row in rows:
            if row["rank_score"] <= 0:
                continue
            if row["game"] != game or (game in SPEED and device and row["device"] != device):
                continue
            report = json.loads(row["report"])
            if qualified and not self._qualifies(report):
                continue
            details = report["details"]
            # Preserve old replays and earned awards, but don't mix different physics in a board.
            if game == "drop" and details.get("physics") != "soft4":
                continue
            key = (
                -row["rank_score"],
                -details.get("accuracy", 0) if game == "typing" else 0,
                details.get("reactionMs", 10000) if game == "react" else 0,
                details.get("moves", 100000) if game == "memory" else 0,
                report["timeMs"] if game in ("debug", "memory") else 0,
            )
            item = {
                "player": row["player"],
                "name": row["name"],
                "group": row["group_name"],
                "score": row["rank_score"],
                "result": row["score"],
                "details": details,
                "level": report["level"],
                "device": row["device"],
                "created": row["created"],
                "sort": key,
            }
            if item["player"] not in best or key < best[item["player"]]["sort"]:
                best[item["player"]] = item
        items = sorted(best.values(), key=lambda r: (r["sort"], r["created"], r["player"]))
        previous = None
        rank = 0
        for index, row in enumerate(items):
            if row["sort"] != previous:
                rank = index + 1
            previous = row["sort"]
            row["rank"] = rank
        return items

    def _overall(self, db, period):
        rows = self._rows(db, period)
        people = {}
        for game in GAMES:
            contributions = {}
            for device in ["keyboard", "touch"] if game in SPEED else [None]:
                for row in self._game_board(rows, game, device, qualified=True):
                    points = POINTS[row["rank"] - 1] if row["rank"] <= 10 else 5
                    if (
                        row["player"] in contributions
                        and contributions[row["player"]]["points"] >= points
                    ):
                        continue
                    contributions[row["player"]] = {"game": game, "points": points, **row}
            for player, result in contributions.items():
                if player not in people:
                    people[player] = {
                        "player": player,
                        "name": result["name"],
                        "group": result["group"],
                        "score": 0,
                        "games": 0,
                        "wins": 0,
                        "created": 0,
                        "contributions": [],
                    }
                person = people[player]
                person["score"] += result["points"]
                person["games"] += 1
                person["wins"] += result["rank"] == 1
                person["created"] = max(person["created"], result["created"])
                person["contributions"].append(result)
        items = sorted(
            people.values(),
            key=lambda r: (-r["score"], -r["games"], -r["wins"], r["created"], r["player"]),
        )
        for i, row in enumerate(items):
            row["rank"] = i + 1
            row["prizeEligible"] = row["games"] >= 3
            row["league"] = league(row["score"], row["games"])
        return items

    def maintain(self):
        now = self.clock()
        with self.db() as db:
            current = season_key(now)
            first_season = db.execute(
                "SELECT value FROM arcade_meta WHERE key='season_prizes_start'"
            ).fetchone()[0]
            periods = sorted(
                {
                    season_key(datetime.fromisoformat(r[0]).replace(tzinfo=MOSCOW).timestamp())
                    for r in db.execute(
                        "SELECT DISTINCT week FROM arcade_runs "
                        "WHERE accepted=1 AND week>=? AND week<?",
                        (first_season, current),
                    )
                }
            )
            for period in periods:
                if db.execute("SELECT 1 FROM arcade_seasons WHERE week=?", (period,)).fetchone():
                    continue
                standings = self._overall(db, period)
                winners = [r for r in standings if r["prizeEligible"]][:3]
                for i, row in enumerate(winners):
                    row["prize"] = PRIZES[i]
                    row["prizeRank"] = i + 1
                    self._award(
                        db,
                        row["player"],
                        "podium",
                        period,
                        f"season-podium:{period}:{row['player']}",
                        PRIZES[i],
                        f"Общий рейтинг · {i + 1}-е место · сезон с {period}",
                        claimed=True,
                    )
                db.execute(
                    "INSERT INTO arcade_seasons VALUES(?,?,?,?)",
                    (
                        period,
                        now,
                        json.dumps(winners, ensure_ascii=False),
                        json.dumps(standings, ensure_ascii=False),
                    ),
                )
            for row in db.execute("SELECT id FROM arcade_players").fetchall():
                self._credit(db, row[0])
            db.execute(
                "UPDATE arcade_sessions SET status='expired' "
                "WHERE created<? AND status!='finished'",
                (now - 7200,),
            )

    def board(self, game="overall", period="week", device="keyboard"):
        self.maintain()
        period = "all" if period == "all" else season_key(self.clock())
        with self.db() as db:
            rows = (
                self._overall(db, period)
                if game == "overall"
                else self._game_board(self._rows(db, period, game), game, device)
            )
            history = [
                dict(r)
                for r in db.execute(
                    "SELECT week,closed,winners,standings,14 AS days FROM arcade_seasons "
                    "UNION ALL SELECT week,closed,winners,standings,7 AS days FROM arcade_weeks "
                    "ORDER BY week DESC LIMIT 12"
                )
            ]
            for row in history:
                row["winners"] = json.loads(row["winners"])
                row.pop("standings")
            return {
                "rows": rows,
                "history": history,
                "week": week_key(self.clock()),
                "season": season_info(self.clock()),
                "prizes": PRIZES,
                "min_games": 3,
                "server_time": iso(self.clock()),
                "device": device,
            }

    def profile(self, player):
        self.maintain()
        with self.db() as db:
            person = self._player(db, player)
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT id,session,player,game,mode,device,week,created,score,rank_score,"
                    "report,ticks,accepted FROM arcade_runs WHERE player=? "
                    "ORDER BY created DESC LIMIT 150",
                    (player,),
                )
            ]
            for row in rows:
                row["report"] = json.loads(row["report"])
            awards = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM arcade_awards WHERE player=? ORDER BY created DESC", (player,)
                )
            ]
            credits = [
                dict(r)
                for r in db.execute(
                    """SELECT c.*,a.label FROM arcade_credits c JOIN arcade_awards a ON a.id=c.award
              WHERE c.player=? ORDER BY c.created DESC""",
                    (player,),
                )
            ]
            verified = [
                dict(r)
                for r in db.execute(
                    "SELECT game,score,report FROM arcade_runs WHERE player=? AND accepted=1",
                    (player,),
                )
            ]
            for record in verified:
                record["report"] = json.loads(record["report"])
            best = {
                game: max((r["score"] for r in verified if r["game"] == game), default=0)
                for game in GAMES
            }
            current = week_key(self.clock())
            badges = []
            for game, (_goal, targets) in GAMES.items():
                records = [r for r in verified if r["game"] == game]
                for tier, target in enumerate(targets):
                    key = f"master3:{player}:{game}:{tier}"
                    award = next((r for r in awards if r["id"] == key), None)
                    value = max(
                        (
                            r["score"]
                            for r in records
                            if self._quality(game, r["report"]["details"], tier)
                        ),
                        default=0,
                    )
                    badges.append(
                        {
                            "id": key,
                            "game": game,
                            "tier": tier,
                            "target": target,
                            "value": min(target, value),
                            "reward": award["amount"] if award else MEDAL_REWARDS[tier],
                            "condition": self._medal_condition(game, tier),
                            "requirements": self._medal_requirements(game, tier),
                            "unlocked": bool(award),
                            "claimed": bool(award and award["claimed"]),
                            "credited": bool(award and award["credited"] is not None),
                        }
                    )
            goal_results = verified + [
                r
                for r in rows
                if r["mode"] == "journey" and r["report"].get("journey", {}).get("success")
            ]
            goals = {}
            for game, (goal, _) in GAMES.items():
                award = self._goal_award(db, player, game)
                score = max(
                    (r["score"] for r in goal_results if r["game"] == game),
                    default=0,
                )
                goals[game] = {
                    "score": max(score, goal if award else 0),
                    "target": goal,
                    "eligible": bool(award),
                    "claimed": bool(award and award["claimed"]),
                    "credited": bool(award and award["credited"] is not None),
                    "id": award["id"] if award else None,
                    "reward": award["amount"] if award else FIRST_GOAL_REWARD,
                }
            journeys = arcade_journey.progress(db, player)
            # Retired games keep earned permanent mastery and their full ledger.
            mastery_journeys = dict(journeys)
            legacy = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(stars),0) FROM arcade_journeys "
                "WHERE player=? AND game='runner'",
                (player,),
            ).fetchone()
            if legacy[0]:
                mastery_journeys["runner"] = dict(cleared=legacy[0], stars=legacy[1])
            legacy_badges = [
                dict(game="runner", tier=int(a["id"].rsplit(":", 1)[1]), unlocked=True)
                for a in awards
                if a["id"].startswith(f"master3:{player}:runner:")
            ]
            standing = next(
                (r for r in self._overall(db, season_key(self.clock())) if r["player"] == player),
                None,
            )
            return {
                "mastery": mastery(mastery_journeys, badges + legacy_badges),
                "competition": {
                    "score": standing["score"] if standing else 0,
                    "rank": standing["rank"] if standing else None,
                    "games": standing["games"] if standing else 0,
                    "league": standing["league"] if standing else league(0, 0),
                },
                "player": {"id": player, "name": person["name"], "group": person["group_name"]},
                "balance": sum(r["amount"] for r in credits),
                "settings": json.loads(person["settings"]),
                "best": best,
                "journeys": journeys,
                "goals": goals,
                "achievements": badges,
                "awards": awards,
                "credits": credits[:100],
                "runs": rows[:100],
                "week": current,
                "season": season_info(self.clock()),
                "server_time": iso(self.clock()),
            }

    def claim(self, player, key):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM arcade_awards WHERE id=? AND player=?", (key, player)
            ).fetchone()
            if not row:
                raise ArcadeError("Эта награда ещё не заработана.")
            db.execute("UPDATE arcade_awards SET claimed=1 WHERE id=?", (key,))
            self._credit(db, player)
        return self.profile(player)

    def settings(self, player, values):
        allowed = {"sound", "vibration", "quality", "theme", "skin", "tutorials", "ui"}
        if set(values) - allowed:
            raise ArcadeError("Неизвестная настройка.")
        with self.db() as db:
            person = self._player(db, player)
            settings = json.loads(person["settings"])
            for key in ("sound", "vibration"):
                if key in values and not isinstance(values[key], bool):
                    raise ArcadeError("Проверь настройку звука и вибрации.")
            if values.get("quality", "auto") not in ("auto", "low", "high"):
                raise ArcadeError("Неизвестное качество эффектов.")
            if "tutorials" in values and (
                not isinstance(values["tutorials"], list)
                or len(values["tutorials"]) > len(GAMES)
                or any(
                    not isinstance(game, str) or game not in GAMES for game in values["tutorials"]
                )
            ):
                raise ArcadeError("Неизвестная игра в обучении.")
            if "ui" in values and (
                not isinstance(values["ui"], dict) or len(json.dumps(values["ui"])) > 500
            ):
                raise ArcadeError("Не удалось сохранить положение раздела.")
            unlocks = db.execute(
                "SELECT id FROM arcade_awards WHERE player=? AND kind='master'", (player,)
            ).fetchall()
            tier = max((int(r[0].rsplit(":", 1)[1]) + 1 for r in unlocks), default=0)
            if values.get("skin", "base") not in ["base", "mint", "sun", "nebula"][: tier + 1]:
                raise ArcadeError("Этот образ пока не открыт.")
            if (
                values.get("theme", "space")
                not in ["space", "forest", "sunset", "nebula"][: tier + 1]
            ):
                raise ArcadeError("Эта тема пока не открыта.")
            settings.update(values)
            db.execute(
                "UPDATE arcade_players SET settings=? WHERE id=?", (json.dumps(settings), player)
            )
        return settings

    def replay(self, player, run):
        with self.db() as db:
            row = db.execute(
                """SELECT r.actions,r.ticks,s.setup FROM arcade_runs r JOIN arcade_sessions s
                ON s.id=r.session
              WHERE r.id=? AND r.player=?""",
                (run, player),
            ).fetchone()
            if not row:
                raise ArcadeError("Эта партия не найдена.")
            return {
                "setup": json.loads(row["setup"]),
                "actions": json.loads(row["actions"]),
                "ticks": row["ticks"],
            }
