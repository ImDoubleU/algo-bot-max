"""Collectibles are cosmetic, transactional and recoverable; never gamble school AC."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.arcade import ArcadeError, ArcadeStore
from app.services.arcade_cases import PITY, CaseStore
from tests.test_arcade_server import store as store


def test_cases_have_disclosed_valid_odds_and_opening_never_changes_ac_or_rank(store):
    cases = CaseStore(store)
    initial = cases.get("p1")
    assert initial["collected"] == initial["opens"] == initial["fragments"] == 0
    assert all(sum(c["weights"]) == 100 for c in initial["cases"])
    assert initial["cases"][0]["unlocked"] and not initial["cases"][1]["unlocked"]
    first = cases.act("p1", "case-open-first-001", "open", "scout")
    assert first["result"]["new"] and first["snapshot"]["collected"] == 1
    assert first["snapshot"]["opens"] == 1
    profile = store.profile("p1")
    assert profile["balance"] == 0 and not profile["awards"]
    assert not store.board()["rows"]


def test_retries_and_parallel_duplicate_requests_roll_once_after_restart(store):
    cases = CaseStore(store)
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(
            pool.map(lambda _: cases.act("p1", "same-opening-001", "open", "scout"), range(4))
        )
    assert sum(not v["duplicate"] for v in values) == 1
    assert len({v["result"]["item"] for v in values}) == 1
    restarted = CaseStore(ArcadeStore(store.path, store.clock))
    retry = restarted.act("p1", "same-opening-001", "open", "scout")
    assert retry["duplicate"] and retry["snapshot"]["opens"] == 1
    assert restarted.get("p2")["collected"] == 0
    with pytest.raises(ArcadeError, match="уже обработано"):
        restarted.act("p1", "same-opening-001", "open", "neon")


def test_pity_prevents_long_dry_streaks_and_new_items_precede_duplicates(store, monkeypatch):
    monkeypatch.setattr("app.services.arcade_cases.secrets.randbelow", lambda n: 0)
    cases = CaseStore(store)
    with store.db() as db:
        state = cases._load(db, "p1")
        state["tokens"] = 10000
        cases._save(db, "p1", state)
    seen = []
    for n in range(PITY):
        result = cases.act("p1", f"opening-{n:012}", "open", "scout")
        seen.append(result["result"])
        store.clock.advance(2)
    assert all(r["new"] for r in seen[:6])
    assert not seen[6]["new"] and seen[6]["fragments"] == 1
    assert seen[-1]["rarity"] == "legendary" and seen[-1]["guaranteed"]
    assert result["snapshot"]["guaranteed_in"] == PITY
    assert result["snapshot"]["cases"][1]["unlocked"]
    assert len(result["snapshot"]["history"]) == 12


def test_crafting_is_specific_spends_only_fragments_and_is_exactly_once(store, monkeypatch):
    monkeypatch.setattr("app.services.arcade_cases.secrets.randbelow", lambda n: 0)
    cases = CaseStore(store)
    with store.db() as db:
        state = cases._load(db, "p1")
        state["tokens"] = 10000
        cases._save(db, "p1", state)
    for n in range(30):
        cases.act("p1", f"earn-details-{n:012}", "open", "scout")
        store.clock.advance(2)
    before = cases.get("p1")
    item = next(i for i in before["items"] if i["rarity"] == "rare")
    result = cases.act("p1", "craft-first-0001", "craft", item["id"])
    assert result["result"]["item"] == item["id"]
    assert result["snapshot"]["fragments"] == before["fragments"] - item["craft"]
    assert cases.act("p1", "craft-first-0001", "craft", item["id"])["duplicate"]
    with pytest.raises(ArcadeError, match="уже есть"):
        cases.act("p1", "craft-second-0001", "craft", item["id"])
    favorite = cases.act("p1", "favorite-item-001", "favorite", item["id"])
    assert favorite["snapshot"]["favorite"] == item["id"]
    assert cases.get("p2")["favorite"] is None
    assert not store.profile("p1")["credits"]


def test_invalid_locked_and_spam_actions_do_not_mutate_inventory(store):
    cases = CaseStore(store)
    for action, item in [
        ("open", "neon"),
        ("craft", "ship"),
        ("favorite", "ship"),
        ("delete", "ship"),
    ]:
        with pytest.raises(ArcadeError):
            cases.act("p1", f"invalid-{action}-001", action, item)
    assert cases.get("p1")["collected"] == 0
    cases.act("p1", "cooldown-first-001", "open", "scout")
    with pytest.raises(ArcadeError, match="Дождись"):
        cases.act("p1", "cooldown-next-0001", "open", "scout")
    assert cases.get("p1")["opens"] == 1


def test_case_action_limit_does_not_block_recovery_of_an_existing_receipt(store):
    cases = CaseStore(store)
    first = cases.act("p1", "rate-limit-open-001", "open", "scout")
    item = first["result"]["item"]
    for n in range(59):
        cases.act("p1", f"favorite-{n:012}", "favorite", item)
    with pytest.raises(ArcadeError, match="Подожди минуту"):
        cases.act("p1", "favorite-limited-001", "favorite", item)
    assert cases.act("p1", "rate-limit-open-001", "open", "scout")["duplicate"]
    store.clock.advance(61)
    assert not cases.act("p1", "favorite-limited-001", "favorite", item)["duplicate"]
