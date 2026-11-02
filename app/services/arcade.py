"""Isolated, transactional local arcade backend. No school wallet or binding writes.

All ranked scores are replayed by arcade_runtime. SQLite is deliberately separate
from the collection preview and production databases. Public mounting is not enabled.
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

from app.services import arcade_journey, arcade_runtime
from app.services.arcade_mastery import league, mastery

MOSCOW = timezone(timedelta(hours=3))
SPEED = {"orbit", "bugs", "tower", "typing", "react", "kopatych", "runner", "words"}
FINITE = {"typing", "debug", "memory", "react", "kopatych", "words"}
GAMES = {
    "orbit": (8, [10, 18, 25]),
    "evolve": (128, [256, 1024, 2048]),
    "bugs": (20, [20, 35, 50]),
    "tower": (8, [10, 18, 25]),
    "typing": (120, [140, 200, 240]),
    "debug": (5, [6, 7, 8]),
    "2048": (128, [256, 512, 1024]),
    "drop": (100, [250, 600, 1000]),
    "memory": (8, [10, 28, 40]),
    "react": (5, [8, 12, 15]),
    "kopatych": (300, [1500, 12000, 30000]),
    "blocks": (300, [600, 1200, 2000]),
    "runner": (15, [25, 40, 60]),
    "bubbles": (200, [400, 800, 1500]),
    "sort": (3, [4, 7, 10]),
    "words": (10, [16, 24, 32]),
}
POINTS = [100, 80, 65, 55, 45, 35, 25, 20, 15, 10]
PRIZES = [100, 75, 50]
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
              CREATE TABLE IF NOT EXISTS arcade_weeks(week TEXT PRIMARY KEY,closed REAL NOT NULL,
                winners TEXT NOT NULL,standings TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_policy(week TEXT PRIMARY KEY,cap INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_log(id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL NOT NULL,player TEXT,session TEXT,event TEXT NOT NULL,detail
                TEXT NOT NULL);
            """)
            db.execute(
                "INSERT OR IGNORE INTO arcade_meta VALUES('secret',?)", (secrets.token_hex(32),)
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

    def _cap(self, db, period):
        row = db.execute(
            "SELECT cap FROM arcade_policy WHERE week<=? ORDER BY week DESC LIMIT 1", (period,)
        ).fetchone()
        return row[0] if row else 200

    def _award(self, db, player, kind, period, key, amount, label, claimed=False):
        db.execute(
            "INSERT OR IGNORE INTO arcade_awards VALUES(?,?,?,?,?,?,?,?,NULL)",
            (key, player, kind, period, amount, label, self.clock(), int(claimed)),
        )

    def _credit(self, db, player):
        period = week_key(self.clock())
        used = db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM arcade_credits WHERE player=? AND week=?",
            (player, period),
        ).fetchone()[0]
        cap = self._cap(db, period)
        rows = db.execute(
            """SELECT * FROM arcade_awards WHERE player=? AND claimed=1 AND credited IS NULL
          ORDER BY CASE kind WHEN 'podium' THEN 0 WHEN 'weekly' THEN 1 ELSE 2 END,created,id""",
            (player,),
        ).fetchall()
        for row in rows:
            if used + row["amount"] > cap:
                continue
            db.execute(
                "INSERT OR IGNORE INTO arcade_credits VALUES(?,?,?,?,?)",
                (row["id"], player, period, row["amount"], self.clock()),
            )
            db.execute("UPDATE arcade_awards SET credited=? WHERE id=?", (self.clock(), row["id"]))
            used += row["amount"]

    def _qualifies(self, report):
        return report["score"] >= GAMES[report["game"]][0] and (
            report["game"] != "typing" or report["details"].get("accuracy", 0) >= 90
        )

    def _master(self, game, score, details, tier):
        if score < GAMES[game][1][tier]:
            return False
        return self._quality(game, details, tier)

    def _quality(self, game, details, tier):
        if game == "typing":
            return details.get("accuracy", 0) >= [90, 93, 95][tier]
        if game == "react":
            return (
                details.get("mistakes", 99) <= [1, 0, 0][tier]
                and 0 < details.get("reactionMs", 0) <= [450, 400, 350][tier]
            )
        return True

    def session(self, player, game, mode, device, stage=None, arena=None):
        if (
            game not in GAMES
            or mode not in ("ranked", "practice", "journey")
            or device not in ("keyboard", "touch")
        ):
            raise ArcadeError("Выбери игру и режим заново.")
        if arena is not None and (
            game != "drop"
            or mode != "practice"
            or arena not in ("classic", "bowl", "slopes", "pins")
        ):
            raise ArcadeError("Выбор арены доступен в тренировке Космодропа.")
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
            challenge = f"v3:{week_key(self.clock())}:{game}:{device}".encode()
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
                "weak": "".join(sorted(weak, key=weak.get, reverse=True)[:6])
                if mode == "practice"
                else "",
            }
            if game == "drop":
                setup["dropPhysics"] = 3
                setup["arena"] = arena or "classic"
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
                return {
                    "run": {
                        "id": previous["id"],
                        "score": previous["score"],
                        "accepted": bool(previous["accepted"]),
                        "report": json.loads(previous["report"]),
                    },
                    "duplicate": True,
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
        accepted = (
            row["mode"] == "ranked"
            and (report["complete"] or row["game"] not in FINITE)
            and not abandoned
            and week_key(row["created"]) == week_key(self.clock())
        )
        key = secrets.token_urlsafe(18)
        now = self.clock()
        with self.db() as db:
            previous = db.execute(
                "SELECT * FROM arcade_runs WHERE session=?", (session,)
            ).fetchone()
            if previous:
                return {
                    "run": {
                        "id": previous["id"],
                        "score": previous["score"],
                        "accepted": bool(previous["accepted"]),
                        "report": json.loads(previous["report"]),
                    },
                    "duplicate": True,
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
            if row["mode"] == "journey" and report.get("journey", {}).get("success"):
                arcade_journey.record(db, player, row["game"], report, now)
                if (
                    report.get("journey", {}).get("success")
                    and self._qualifies(report)
                    and week_key(row["created"]) == week_key(now)
                ):
                    title = next(
                        g["name"] for g in arcade_runtime.catalogue() if g["id"] == row["game"]
                    )
                    self._award(
                        db,
                        player,
                        "weekly",
                        week_key(now),
                        f"weekly:{week_key(now)}:{player}:{row['game']}",
                        10,
                        f"{title} · цель недели",
                    )
            if accepted:
                game = row["game"]
                title = next(g["name"] for g in arcade_runtime.catalogue() if g["id"] == game)
                if self._qualifies(report):
                    self._award(
                        db,
                        player,
                        "weekly",
                        week_key(now),
                        f"weekly:{week_key(now)}:{player}:{game}",
                        10,
                        f"{title} · цель недели",
                    )
                for tier in range(3):
                    if self._master(game, report["score"], report["details"], tier):
                        amount = [
                            10,
                            20,
                            40 if game in ("typing", "2048", "memory", "react") else 35,
                        ][tier]
                        self._award(
                            db,
                            player,
                            "master",
                            "all",
                            f"master3:{player}:{game}:{tier}",
                            amount,
                            f"{title} · {['бронза', 'серебро', 'золото'][tier]}",
                        )
            self._log(
                db, player, session, "run_verified", f"{row['game']}:{report['score']}:{accepted}"
            )
        return {
            "run": {"id": key, "score": report["score"], "accepted": accepted, "report": report},
            "duplicate": False,
        }

    def _rows(self, db, period, game=None):
        query = (
            "SELECT r.*,p.name,p.group_name FROM arcade_runs r "
            "JOIN arcade_players p ON p.id=r.player WHERE accepted=1"
        )
        args = []
        if period != "all":
            query += " AND r.week=?"
            args.append(period)
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
            if game == "drop" and details.get("physics") != "soft3":
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
            current = week_key(now)
            periods = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT week FROM arcade_runs WHERE accepted=1 AND week<?", (current,)
                )
            ]
            for period in periods:
                if db.execute("SELECT 1 FROM arcade_weeks WHERE week=?", (period,)).fetchone():
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
                        f"podium:{period}:{row['player']}",
                        PRIZES[i],
                        f"Общий рейтинг · {i + 1}-е место · неделя {period}",
                        claimed=True,
                    )
                db.execute(
                    "INSERT INTO arcade_weeks VALUES(?,?,?,?)",
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
        period = "all" if period == "all" else week_key(self.clock())
        with self.db() as db:
            rows = (
                self._overall(db, period)
                if game == "overall"
                else self._game_board(self._rows(db, period, game), game, device)
            )
            history = [
                dict(r)
                for r in db.execute("SELECT * FROM arcade_weeks ORDER BY week DESC LIMIT 12")
            ]
            for row in history:
                row["winners"] = json.loads(row["winners"])
                row.pop("standings")
            return {
                "rows": rows,
                "history": history,
                "week": week_key(self.clock()),
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
                    "SELECT * FROM arcade_runs WHERE player=? ORDER BY created DESC LIMIT 150",
                    (player,),
                )
            ]
            for row in rows:
                row["report"] = json.loads(row["report"])
                row.pop("actions")
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
                    "SELECT * FROM arcade_runs WHERE player=? AND accepted=1", (player,)
                )
            ]
            for record in verified:
                record["report"] = json.loads(record["report"])
            best = {
                game: max((r["score"] for r in verified if r["game"] == game), default=0)
                for game in GAMES
            }
            current = week_key(self.clock())
            used = sum(r["amount"] for r in credits if r["week"] == current)
            next_period = (datetime.fromisoformat(current) + timedelta(days=7)).date().isoformat()
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
                            "reward": [
                                10,
                                20,
                                40 if game in ("typing", "2048", "memory", "react") else 35,
                            ][tier],
                            "unlocked": bool(award),
                            "claimed": bool(award and award["claimed"]),
                            "credited": bool(award and award["credited"] is not None),
                        }
                    )
            weekly_results = verified + [
                r
                for r in rows
                if r["mode"] == "journey" and r["report"].get("journey", {}).get("success")
            ]
            goals = {}
            for game, (goal, _) in GAMES.items():
                award = next(
                    (r for r in awards if r["id"] == f"weekly:{current}:{player}:{game}"), None
                )
                score = max(
                    (
                        r["score"]
                        for r in weekly_results
                        if r["game"] == game and r["week"] == current
                    ),
                    default=0,
                )
                goals[game] = {
                    "score": max(score, goal if award else 0),
                    "target": goal,
                    "eligible": bool(award),
                    "claimed": bool(award and award["claimed"]),
                    "id": award["id"] if award else None,
                }
            journeys = arcade_journey.progress(db, player)
            standing = next((r for r in self._overall(db, current) if r["player"] == player), None)
            return {
                "mastery": mastery(journeys, badges),
                "competition": {
                    "score": standing["score"] if standing else 0,
                    "rank": standing["rank"] if standing else None,
                    "games": standing["games"] if standing else 0,
                    "league": standing["league"] if standing else league(0, 0),
                },
                "player": {"id": player, "name": person["name"], "group": person["group_name"]},
                "balance": sum(r["amount"] for r in credits),
                "cap": {"limit": self._cap(db, current), "used": used},
                "nextCap": self._cap(db, next_period),
                "settings": json.loads(person["settings"]),
                "best": best,
                "journeys": journeys,
                "goals": goals,
                "achievements": badges,
                "awards": awards,
                "credits": credits[:100],
                "runs": rows[:100],
                "week": current,
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

    def policy(self, cap):
        if not isinstance(cap, int) or not 50 <= cap <= 1000:
            raise ArcadeError("Выбери лимит от 50 до 1000 AC.")
        next_week = (
            (datetime.fromisoformat(week_key(self.clock())) + timedelta(days=7)).date().isoformat()
        )
        with self.db() as db:
            db.execute(
                "INSERT INTO arcade_policy VALUES(?,?) "
                "ON CONFLICT(week) DO UPDATE SET cap=excluded.cap",
                (next_week, cap),
            )
        return {"week": next_week, "cap": cap}

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
