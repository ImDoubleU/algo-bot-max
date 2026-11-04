"""Uncapped settlement, historical pending rewards and their visible receipts."""

import json

import pytest

from app.services.arcade import FIRST_GOAL_REWARD, GAMES, MEDAL_REWARDS, ArcadeStore, week_key
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import finish_debug
from tests.test_arcade_server import store as store


def test_all_lifetime_rewards_and_a_prize_can_be_credited_on_the_same_day(store):
    with store.db() as db:
        for game in GAMES:
            for kind, suffix, amount in [
                ("first", "first", FIRST_GOAL_REWARD),
                *(("master", str(i), v) for i, v in enumerate(MEDAL_REWARDS)),
            ]:
                store._award(
                    db,
                    "p1",
                    kind,
                    "all",
                    f"earned:{game}:{suffix}",
                    amount,
                    "Earned reward",
                    claimed=True,
                )
        store._credit(db, "p1")
    assert store.profile("p1")["balance"] == 368
    with store.db() as db:
        store._award(db, "p1", "podium", "season", "prize", 100, "First place", claimed=True)
    assert store.profile("p1")["balance"] == 468
    assert len(store.profile("p1")["awards"]) == 65
    assert ArcadeStore(store.path, store.clock).profile("p1")["balance"] == 468
    assert store.profile("p2")["balance"] == 0


def test_old_queue_settles_once_without_repricing_paid_or_unclaimed_awards(store):
    with store.db() as db:
        db.execute("INSERT INTO arcade_policy VALUES(?,?)", ("2020-01-06", 200))
        for key, amount, claimed in [
            ("paid", 200, True),
            ("queued", 50, True),
            ("podium", 100, True),
            ("unclaimed", 20, False),
        ]:
            store._award(db, "p1", "master", "all", key, amount, "Earlier reward", claimed)
        db.execute(
            "INSERT INTO arcade_credits VALUES(?,?,?,?,?)",
            ("paid", "p1", week_key(store.clock()), 200, store.clock()),
        )
        db.execute("UPDATE arcade_awards SET credited=? WHERE id='paid'", (store.clock(),))
    profile = store.profile("p1")
    assert profile["balance"] == 350
    assert len(profile["credits"]) == 3
    assert next(a for a in profile["awards"] if a["id"] == "unclaimed")["credited"] is None
    for _ in range(3):
        store.maintain()
    restarted = ArcadeStore(store.path, store.clock)
    assert restarted.profile("p1")["balance"] == 350
    assert len(restarted.profile("p1")["credits"]) == 3


def test_retry_of_an_old_partially_credited_receipt_reflects_settlement_without_double_payment(
    store,
):
    first, session, _ = finish_debug(store)
    old_receipt = first["receipt"]
    award = next(a for a in old_receipt["awards"] if a["amount"] == 10)
    award["credited"] = False
    old_receipt.update(credited=13, pending=10)
    with store.db() as db:
        db.execute("DELETE FROM arcade_credits WHERE award=?", (award["id"],))
        db.execute("UPDATE arcade_awards SET credited=NULL WHERE id=?", (award["id"],))
        db.execute(
            "UPDATE arcade_receipts SET payload=? WHERE session=?",
            (json.dumps(old_receipt), session["id"]),
        )
    retry = store.finish("p1", session["id"], [], 0)
    assert retry["duplicate"] and retry["receipt"]["pending"] == 0
    assert retry["receipt"]["credited"] == store.profile("p1")["balance"] == 23
    assert all(a["credited"] for a in retry["receipt"]["awards"])
    assert not retry["rewards"]["awards"]
    assert store.finish("p1", session["id"], [], 0)["receipt"] == retry["receipt"]


@pytest.mark.parametrize("width", [320, 1440])
def test_rewards_rules_and_director_settings_have_no_weekly_limit(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    page.locator('.games-tabs [data-tab="rewards"]').click()
    assert "лимит" not in page.locator("#arcadeTabContent").inner_text().lower()
    assert "очеред" not in page.locator("#arcadeTabContent").inner_text().lower()
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    page.locator('.games-tabs [data-tab="leaders"]').click()
    page.locator(".ranking-rules summary").click()
    assert "лимит" not in page.locator(".ranking-rules").inner_text().lower()
    page.evaluate("window.pizzaPreview={role:'partner_director'}")
    page.locator("[data-settings]").click()
    assert "лимит" not in page.locator(".arcade-preferences").inner_text().lower()
    assert page.locator('.arcade-policy,[name="cap"]').count() == 0
