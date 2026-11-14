"""400 stable cosmetics, bounded server-owned token earnings and exactly-once spending."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.arcade import ArcadeError
from app.services.arcade_case_catalog import COLLECTIONS
from app.services.arcade_cases import BASE_ITEMS, CASES, ITEMS, CaseStore
from tests.test_arcade_server import make_client, verified
from tests.test_arcade_server import store as store


def test_catalogue_is_complete_and_keeps_every_old_item_id(store):
    cases = CaseStore(store)
    data = cases.get("p1")
    assert len(ITEMS) == len({i["id"] for i in ITEMS}) == data["total"] == 400
    assert len(data["collections"]) == len(CASES) == 20
    assert set(i[0] for i in BASE_ITEMS) <= {i["id"] for i in ITEMS}
    assert len({i["quality"] for i in ITEMS}) == 5
    for collection in COLLECTIONS:
        pool = [i for i in ITEMS if i["collection"] == collection[0]]
        assert len(pool) == 20 and len({i["rarity"] for i in pool}) == 4


def test_concurrent_distinct_draws_cannot_overdraw_wallet(store):
    cases = CaseStore(store)
    with store.db() as db:
        state = cases._load(db, "p1")
        state["tokens"] = 50
        cases._save(db, "p1", state)

    def buy(n):
        try:
            return cases.act("p1", f"concurrent-{n:012}", "open", "scout")
        except ArcadeError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(buy, range(4)))
    assert sum(r is not None for r in results) == 1
    assert cases.get("p1")["tokens"] == 0
    assert cases.get("p1")["opens"] == 1
    assert store.profile("p1")["balance"] == 0


def test_old_profiles_migrate_without_losing_inventory_or_repeated_grants(store):
    cases = CaseStore(store)
    old = dict(opens=4, fragments=17, since_legendary=4, favorite="robot", last_open=None)
    with store.db() as db:
        db.execute("INSERT INTO arcade_case_profiles VALUES(?,?)", ("p1", json.dumps(old)))
        cases._grant(db, "p1", "robot", store.clock())
    first = cases.get("p1")
    assert first["favorite"] == "robot" and first["fragments"] == 17
    assert first["collected"] == 1 and first["tokens"] == 300
    cases.act("p1", "migration-open-001", "open", "scout")
    assert CaseStore(store).get("p1")["tokens"] == 250


def test_only_server_verified_goals_earn_tokens_once_per_game_and_day(store):
    cases = CaseStore(store)
    cases.get("p1")

    def verified(n, game="tower", accepted=1, score=8, time_ms=20000):
        report = dict(score=score, timeMs=time_ms, details={})
        with store.db() as db:
            db.execute(
                "INSERT INTO arcade_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(n),
                    str(n),
                    "p1",
                    game,
                    "ranked",
                    "keyboard",
                    "2026-10-26",
                    store.clock(),
                    score,
                    score,
                    json.dumps(report),
                    "[]",
                    1200,
                    accepted,
                ),
            )

    verified(1)
    verified(2)
    verified(3, "orbit", accepted=0)
    verified(4, "bugs", score=1)
    verified(5, "memory", score=8, time_ms=1000)
    assert cases.get("p1")["tokens"] == 330
    assert cases.get("p1")["tokens"] == 330
    store.clock.advance(86400)
    verified(6)
    assert cases.get("p1")["tokens"] == 360
    assert cases.get("p2")["tokens"] == 300


def test_receipt_retry_does_not_spend_twice_and_case_cannot_drop_other_collection(store):
    cases = CaseStore(store)
    first = cases.act("p1", "paid-case-first-001", "open", "scout")
    second = cases.act("p1", "paid-case-first-001", "open", "scout")
    assert second["duplicate"] and second["snapshot"]["tokens"] == 250
    assert second["result"] == first["result"]
    found = next(i for i in ITEMS if i["id"] == first["result"]["item"])
    assert found["collection"] == "scout"
    with pytest.raises(ArcadeError):
        cases.act("p1", "paid-case-first-001", "open", "neon")


def test_profile_starts_the_wallet_before_the_first_game_and_quality_is_required(store):
    client = make_client(store)
    try:
        assert (
            client.get("/preview/arcade/profile", headers={"X-Miniapp-Token": "p1"}).status_code
            == 200
        )
        verified(store, "p1", "tower", 8)
        verified(store, "p1", "typing", 120, detail={"accuracy": 50})
        data = client.get("/preview/arcade/cases", headers={"X-Miniapp-Token": "p1"}).json()
        assert data["tokens"] == 330
    finally:
        client.close()
