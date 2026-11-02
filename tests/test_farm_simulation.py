"""The fast local playthrough must retain the production rules and be repeatable."""

import json

from app.cli.farm_simulation import HeadlessFarm, Playthrough, SimulationClock, SimulationStore
from app.services.arcade_farm import FarmStore


def test_headless_actions_match_full_server_snapshots_and_duplicate_receipts(tmp_path):
    clocks = [SimulationClock(), SimulationClock()]
    stores = [SimulationStore(tmp_path / f"parity-{n}.sqlite3", clocks[n]) for n in range(2)]
    try:
        for store in stores:
            store.register([dict(id="simulation", name="Тест", group="Демо")])
        farms = [FarmStore(stores[0]), HeadlessFarm(stores[1])]
        for farm in farms:
            farm.get("simulation")
        actions = [
            (0, "claim_all", None, 1),
            (0, "buy", "shovel", 1),
            (1, "tap", None, 3),
            (3600, "claim_all", None, 1),
            (0, "buy", "beds", 1),
            (10000, "tap", None, 8),
            (0, "claim_all", None, 1),
        ]
        for i, (elapsed, action, item, count) in enumerate(actions):
            results = []
            for clock, farm in zip(clocks, farms, strict=True):
                clock.advance(elapsed)
                result = farm.act("simulation", f"parity-action-{i:04}", action, item, count)
                results.append(result["result"])
                assert farm.act("simulation", f"parity-action-{i:04}", action, item, count)[
                    "duplicate"
                ]
            assert results[0] == results[1]
            states = []
            for store in stores:
                with store.db() as db:
                    states.append(
                        json.loads(db.execute("SELECT state FROM kopatych_farms").fetchone()[0])
                    )
            assert states[0] == states[1]
    finally:
        for store in stores:
            store.connection.close()


def test_playthrough_is_repeatable_without_grants_or_school_rewards(tmp_path):
    results = []
    for n in range(2):
        play = Playthrough(
            tmp_path / f"repeatable-{n}.sqlite3", visits=1, session_seconds=30, taps_per_second=3
        )
        try:
            assert play.state["balance"] == 150 and play.state["earned"] == 0
            result = play.run(2)
            assert result["actions"]["tap"] == 60
            assert result["days"][-1]["level"] > 1
            assert not play.arcade.profile("simulation")["awards"]
            results.append(result)
        finally:
            play.arcade.connection.close()
    assert results[0] == results[1]
