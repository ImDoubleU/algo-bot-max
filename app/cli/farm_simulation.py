"""Deterministic, isolated play-throughs through real FarmStore actions.

No grants or seeded progression. Only the response rendering is skipped between
inputs; periodic checkpoints use the complete production snapshot. Every mutation
still uses the normal transaction, clock, energy, resource and receipt validation.
"""

import argparse
import json
import sqlite3
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.services.arcade import MOSCOW, ArcadeStore
from app.services.arcade_farm import BADGES, BY_ID, FarmStore, level, price, stats
from app.services.farm_progression import RESEARCH


class SimulationClock:
    def __init__(self):
        self.started = datetime(2026, 11, 2, 9, tzinfo=MOSCOW).timestamp()
        self.now = self.started

    def __call__(self):
        return self.now

    def advance(self, seconds):
        assert seconds >= 0
        self.now += seconds


class SimulationStore(ArcadeStore):
    """One local SQLite connection avoids per-input fsync in long virtual years.

    Transactions, constraints and persistence across simulated restarts are kept.
    This store is never used by the application or with its databases.
    """

    def __init__(self, path, clock):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=MEMORY")
        self.connection.execute("PRAGMA synchronous=OFF")
        super().__init__(path, clock)
        with self.db() as db:
            # Fixed randomness for repeatable daily combinations; never a currency grant.
            db.execute(
                "UPDATE arcade_meta SET value=? WHERE key='secret'",
                ("isolated-farm-playthrough-v1",),
            )

    @contextmanager
    def db(self):
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise


class HeadlessFarm(FarmStore):
    def _snapshot(self, db, player, state, offline=None):
        # Snapshot freezing is a gameplay side effect, so retain it in headless mode.
        state.setdefault("badge_rewards", {})
        self._quests(state)
        self._lock_badge_rewards(state)
        return state


class Playthrough:
    def __init__(self, path, visits=3, session_seconds=600, taps_per_second=3):
        self.clock = SimulationClock()
        self.arcade = SimulationStore(path, self.clock)
        self.arcade.register([dict(id="simulation", name="Симуляция", group="Тест")])
        self.farm = HeadlessFarm(self.arcade)
        self.visits = visits
        self.session_seconds = session_seconds
        self.taps_per_second = taps_per_second
        self.state = self.farm.get("simulation")
        self.counts = Counter()
        self.milestones = {}
        self.days = []
        self.sequence = 0
        self.last_level = 1
        self.restarts = 0
        self.bonus = 0
        self.offline_lost = 0

    def action(self, name, item=None, count=1):
        self.sequence += 1
        result = self.farm.act("simulation", f"simulation-{self.sequence:012}", name, item, count)
        self.state = result["farm"]
        self.counts[name] += 1
        if name == "tap":
            assert 0 <= result["result"]["accepted"] <= min(count, 8)
        if name == "claim_all":
            self.bonus += result["result"]["amount"]
        assert self.state["balance"] >= 0
        assert all(n >= 0 for n in self.state["resources"].values())
        assert self.state["earned"] == self.state["manual"] + self.state["passive"]
        lv = level(self.state["earned"])
        for n in range(self.last_level + 1, lv + 1):
            self.milestones[str(n)] = round((self.clock.now - self.clock.started) / 86400, 3)
        self.last_level = lv
        return result

    def can_pay(self, cost):
        return self.state["balance"] >= cost.get("cost", 0) and all(
            self.state["resources"][key] >= cost.get(key, 0) for key in ("seeds", "materials")
        )

    def manage(self, seconds_left, next_visit):
        self.state = self.farm.get("simulation")
        self.action("claim_all")
        lv = level(self.state["earned"])
        # Research is finite; finish its prerequisite tree without gifted resources.
        for r in RESEARCH:
            n = self.state["research"][r["id"]]
            cost = {key: r[key] * (n + 1) for key in ("cost", "seeds", "materials")}
            if (
                lv >= r["unlock"]
                and n < r["maximum"]
                and self.state["research"].get(r.get("requires"), 0) >= r.get("requires_level", 0)
                and self.can_pay(cost)
            ):
                self.action("research", r["id"])
        # Buy actual affordable marginal improvements; no injected balance or XP.
        for _ in range(100):
            current = stats(self.state, self.state["last_ms"])
            choices = []
            for item in BY_ID.values():
                n = self.state["items"][item["id"]]
                cost = dict(
                    cost=price(item, n),
                    **{k: item.get(k, 0) * (n + 1) for k in ("seeds", "materials")},
                )
                if lv < item["unlock"] or n >= item["maximum"] or not self.can_pay(cost):
                    continue
                future = stats(
                    {**self.state, "items": {**self.state["items"], item["id"]: n + 1}},
                    self.state["last_ms"],
                )
                daily_taps = (
                    self.visits
                    * self.session_seconds
                    * min(self.taps_per_second, current["energy_per_second"])
                )
                gain = (
                    future["per_hour"]
                    - current["per_hour"]
                    + (future["base_tap"] - current["base_tap"]) * daily_taps / 24
                )
                # Utility has value when it prevents loss during the declared play style.
                if item["id"] == "silo" and current["offline_hours"] < 24 / self.visits:
                    gain += current["per_hour"] * 4
                if item["id"] == "well" and current["energy_per_second"] < self.taps_per_second:
                    gain += current["base_tap"] * 600
                if (
                    item["id"] == "battery"
                    and current["energy_max"] < self.session_seconds * self.taps_per_second + 400
                ):
                    gain += current["base_tap"] * 200
                if item["id"] in ("lighthouse", "foundry"):
                    gain += current["per_hour"] * 0.005
                # Once production is complete, finish the remaining useful collection.
                score = (gain if gain > 0 else 0.001) / cost["cost"]
                choices.append((score, item["id"]))
            if not choices:
                break
            self.action("buy", max(choices)[1])
            lv = level(self.state["earned"])
        progress = self.farm._progress_snapshot(self.state, lv)
        if not self.state["order"]:
            offers = [
                o
                for o in self.farm._offers(self.state)
                if o["unlock"] <= lv and o["cost"] <= self.state["balance"]
            ]
            if offers:
                self.action("start_order", max(offers, key=lambda o: o["profit"])["id"])
        if (
            seconds_left >= 30
            and self.state["daily"]["boosts"] < 2
            and self.state["last_ms"] >= self.state["boost_until"]
        ):
            self.action("boost")
        if (
            self.state["energy_milli"] < 10000
            and self.state["daily"]["refills"] < 2
            and self.state["last_ms"] >= self.state["refill_after"]
        ):
            self.action("refill")
        # Long projects before leaving; short projects when they fit within a visit.
        horizon = seconds_left if seconds_left >= 600 else max(1, next_visit - self.clock.now)
        for kind, choices in (("plot", progress["crops"]), ("expedition", progress["routes"])):
            if self.state["projects"][kind]:
                continue
            eligible = [
                c
                for c in choices
                if c["unlock"] <= lv
                and self.state["energy_milli"] >= c["energy"] * 1000
                and (not c.get("requires_item") or self.state["items"][c["requires_item"]])
                and self.can_pay(
                    {**c, "seeds": 0 if kind == "plot" else c["seeds"], "materials": 0}
                )
            ]
            if eligible:
                reward_key = "seeds" if kind == "plot" else "materials"
                choice = max(eligible, key=lambda c: c[reward_key] / max(c["seconds"], horizon))
                self.action("start_plot" if kind == "plot" else "start_expedition", choice["id"])
        p = self.state["projects"]["plot"]
        if (
            lv >= 5
            and p
            and not p["watered"]
            and self.state["last_ms"] < p["finish_at"]
            and self.state["energy_milli"] >= 50000
        ):
            self.action("water_plot", p["project_id"])
        if (
            lv >= 18
            and not self.state["trial"]
            and self.state["last_ms"] >= self.state["trial_after"]
        ):
            trials = [
                t
                for t in progress["trials"]
                if t["unlock"] <= lv
                and self.can_pay(dict(seeds=t["seeds"]))
                and t["goal"] <= min(seconds_left, t["seconds"]) * min(self.taps_per_second, 8)
                and t["goal"]
                <= self.state["energy_milli"] // 1000
                + t["seconds"] * stats(self.state, self.state["last_ms"])["energy_per_second"]
            ]
            if trials:
                self.action("start_trial", max(trials, key=lambda t: t["goal"])["id"])
        t = self.state["trial"]
        if t and self.state["last_ms"] >= t["finish_at"] and t["progress"] < t["goal"]:
            self.action("dismiss_trial", t["project_id"])

    def checkpoint(self, day):
        self.state = self.farm.get("simulation")
        with self.arcade.db() as db:
            snapshot = FarmStore._snapshot(self.farm, db, "simulation", self.state)
            self.farm._save(db, "simulation", self.state)
        assert snapshot["level"] == level(self.state["earned"])
        assert (
            sum(
                snapshot["production"]["sources"][i]["amount"]
                for i in range(len(snapshot["production"]["sources"]))
            )
            + snapshot["production"]["base"]
            + snapshot["production"]["bonus"]
            == snapshot["stats"]["per_hour"]
        )
        row = dict(
            day=day,
            level=snapshot["level"],
            earned=snapshot["earned"],
            balance=snapshot["balance"],
            per_hour=snapshot["stats"]["per_hour"],
            upgrades=sum(self.state["items"].values()),
            maxed=sum(i["maxed"] for i in snapshot["items"]),
            research=sum(self.state["research"].values()),
            badges=len(self.state["badges"]),
            resources=dict(self.state["resources"]),
            trials=self.state["activity_counts"]["trials"],
        )
        self.days.append(row)
        if day % 7 == 0:
            self.arcade.connection.close()
            self.arcade = SimulationStore(self.arcade.path, self.clock)
            self.farm = HeadlessFarm(self.arcade)
            restored = self.farm.get("simulation")
            assert restored == self.state
            self.restarts += 1
        return row

    def run(self, days):
        for day in range(days):
            for visit in range(self.visits):
                target = self.clock.started + (day + visit / self.visits) * 86400
                self.clock.advance(max(0, target - self.clock.now))
                next_visit = target + 86400 / self.visits
                self.manage(self.session_seconds, next_visit)
                for second in range(self.session_seconds):
                    self.clock.advance(1)
                    self.action("tap", count=self.taps_per_second)
                    if second % 60 == 59:
                        self.manage(self.session_seconds - second - 1, next_visit)
                self.action("claim_all")
            row = self.checkpoint(day + 1)
            if (
                day in (0, 1, 2, 6, 13, 29, 59, 89, 119, 179)
                or row["level"] == 50
                and not any(r["level"] == 50 for r in self.days[:-1])
            ):
                print(json.dumps(row, ensure_ascii=False), flush=True)
            if (
                row["level"] == 50
                and row["maxed"] == len(BY_ID)
                and row["badges"] == len(BADGES)
                and row["research"] == 15
            ):
                break
        assert not self.arcade.profile("simulation")["awards"]
        return dict(
            visits=self.visits,
            session_seconds=self.session_seconds,
            taps_per_second=self.taps_per_second,
            days=self.days,
            milestones=self.milestones,
            actions=dict(self.counts),
            restarts=self.restarts,
            bonus_carrots=self.bonus,
            remaining_badges=[
                dict(id=b[0], name=b[1], target=b[3], value=self.farm._metrics(self.state)[b[2]])
                for b in BADGES
                if b[0] not in self.state["badges"]
            ],
            remaining_items={
                k: BY_ID[k]["maximum"] - n
                for k, n in self.state["items"].items()
                if n < BY_ID[k]["maximum"]
            },
            complete=self.days[-1]["level"] == 50
            and self.days[-1]["maxed"] == len(BY_ID)
            and self.days[-1]["badges"] == len(BADGES),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--scenario", choices=("regular", "active", "short"), default="regular")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.days <= 1095:
        parser.error("days must be between 1 and 1095")
    params = {"regular": (3, 600, 3), "active": (6, 600, 6), "short": (2, 120, 3)}[args.scenario]
    with tempfile.TemporaryDirectory(prefix="algo-farm-simulation-") as folder:
        play = Playthrough(Path(folder) / "simulation.sqlite3", *params)
        try:
            result = play.run(args.days)
        finally:
            play.arcade.connection.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", args.report, flush=True)


if __name__ == "__main__":
    main()
