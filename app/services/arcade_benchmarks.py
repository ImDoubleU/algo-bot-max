"""Verified benchmark results, isolated from AC awards and the competition season."""

import json
import secrets

from app.services import arcade_runtime
from app.services.arcade import ArcadeError

TESTS = {"number", "verbal", "sequence", "spatial"}
REFERENCES = {
    "number": dict(
        value=7,
        unit="цифр",
        label="Ориентир Human Benchmark",
        source="https://humanbenchmark.com/tests/number-memory",
        note="Справочный ориентир сайта. Время показа и условия теста могут отличаться.",
    ),
    "verbal": dict(
        value=44,
        unit="ответа",
        label="Среднее участников Human Benchmark",
        source="https://humanbenchmark.com/tests/verbal-memory/statistics",
        note=(
            "Приблизительное среднее по опубликованной гистограмме. "
            "Там английские слова; здесь русские."
        ),
    ),
    "sequence": dict(
        value=10,
        unit="шагов",
        label="Среднее участников Human Benchmark",
        source="https://humanbenchmark.com/tests/sequence/statistics",
        note="Приблизительное среднее по опубликованной гистограмме, не точный мировой норматив.",
    ),
    "spatial": None,
}


class BenchmarkStore:
    def __init__(self, arcade):
        self.arcade = arcade
        with arcade.db() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS arcade_benchmark_sessions(
                id TEXT PRIMARY KEY, player TEXT NOT NULL REFERENCES arcade_players(id),
                test TEXT NOT NULL, seed INTEGER NOT NULL, created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS arcade_benchmark_runs(
                session TEXT PRIMARY KEY, player TEXT NOT NULL, test TEXT NOT NULL,
                score INTEGER NOT NULL, report TEXT NOT NULL, created REAL NOT NULL);
              CREATE INDEX IF NOT EXISTS arcade_bench_player
                ON arcade_benchmark_runs(player,test,created DESC);
            """)
            columns = {r[1] for r in db.execute("PRAGMA table_info(arcade_benchmark_sessions)")}
            if "rules" not in columns:
                db.execute(
                    "ALTER TABLE arcade_benchmark_sessions "
                    "ADD COLUMN rules INTEGER NOT NULL DEFAULT 1"
                )

    def start(self, player, test):
        if test not in TESTS:
            raise ArcadeError("Такого теста нет.")
        with self.arcade.db() as db:
            self.arcade._player(db, player)
            count = db.execute(
                "SELECT COUNT(*) FROM arcade_benchmark_sessions WHERE player=? AND created>?",
                (player, self.arcade.clock() - 60),
            ).fetchone()[0]
            if count >= 20:
                raise ArcadeError("Подожди минуту перед следующей попыткой.")
            session, seed = secrets.token_urlsafe(24), secrets.randbits(32)
            rules = 2 if test == "spatial" else 1
            db.execute(
                "INSERT INTO arcade_benchmark_sessions(id,player,test,seed,created,rules) "
                "VALUES(?,?,?,?,?,?)",
                (session, player, test, seed, self.arcade.clock(), rules),
            )
        return dict(id=session, setup=dict(test=test, seed=seed, rules=rules))

    def finish(self, player, session, events, ticks):
        with self.arcade.db() as db:
            previous = db.execute(
                "SELECT report FROM arcade_benchmark_runs WHERE session=? AND player=?",
                (session, player),
            ).fetchone()
            if previous:
                return dict(report=json.loads(previous[0]), duplicate=True)
            row = db.execute(
                "SELECT * FROM arcade_benchmark_sessions WHERE id=? AND player=?", (session, player)
            ).fetchone()
            if not row or self.arcade.clock() - row["created"] > 900:
                raise ArcadeError("Попытка закончилась. Начни новый тест.")
            if (
                not isinstance(ticks, int)
                or isinstance(ticks, bool)
                or ticks / 60 > self.arcade.clock() - row["created"] + 0.2
            ):
                raise ArcadeError("Время попытки не совпало. Начни тест заново.")
            setup = dict(test=row["test"], seed=row["seed"], rules=row["rules"])
        try:
            with arcade_runtime.context() as vm:
                report = vm.call("ArcadeBenchmarks.verify", setup, events, ticks, timeout_sec=3)
        except Exception as error:
            raise ArcadeError("Не получилось подтвердить результат теста.") from error
        if not report["complete"]:
            raise ArcadeError("Сначала заверши тест.")
        with self.arcade.db() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO arcade_benchmark_runs VALUES(?,?,?,?,?,?)",
                (
                    session,
                    player,
                    row["test"],
                    report["score"],
                    json.dumps(report),
                    self.arcade.clock(),
                ),
            ).rowcount
            saved = db.execute(
                "SELECT report FROM arcade_benchmark_runs WHERE session=? AND player=?",
                (session, player),
            ).fetchone()[0]
        return dict(report=json.loads(saved), duplicate=not inserted)

    def stats(self, player, test):
        if test not in TESTS:
            raise ArcadeError("Такого теста нет.")
        with self.arcade.db() as db:
            self.arcade._player(db, player)
            rules = 2 if test == "spatial" else 1
            history = [
                dict(row)
                for row in db.execute(
                    "SELECT score,created,COALESCE(json_extract(report,'$.rules'),1) rules "
                    "FROM arcade_benchmark_runs WHERE player=? AND test=? "
                    "ORDER BY created DESC LIMIT 10",
                    (player, test),
                )
            ]
            rows = db.execute(
                "SELECT MAX(score) score FROM arcade_benchmark_runs WHERE test=? "
                "AND COALESCE(json_extract(report,'$.rules'),1)=? GROUP BY player",
                (test, rules),
            ).fetchall()
            best = db.execute(
                "SELECT COALESCE(MAX(score),0) FROM arcade_benchmark_runs "
                "WHERE player=? AND test=? AND COALESCE(json_extract(report,'$.rules'),1)=?",
                (player, test, rules),
            ).fetchone()[0]
        reference = REFERENCES[test]
        return dict(
            rules=rules,
            history=history,
            best=best,
            local=dict(
                players=len(rows),
                mean=round(sum(r[0] for r in rows) / len(rows), 1) if len(rows) >= 5 else None,
            ),
            reference={**reference, "checked": "2026-11-06"} if reference else None,
        )
