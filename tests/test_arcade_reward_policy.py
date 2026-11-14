"""Only student profiles can mint or display game AC; achievements remain playable."""

import pytest

from app.services.arcade import GAMES, ArcadeError
from tests.test_arcade_pilot_ui import pilot_page
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import finish_debug
from tests.test_arcade_server import store as store


@pytest.mark.parametrize("role", ["staff", "parent"])
def test_non_student_finishes_unlock_achievements_without_credits_or_prize_eligibility(store, role):
    store.register([dict(id="p1", name=role, rewards_enabled=False)])
    result, session, replay = finish_debug(store)
    assert result["run"]["accepted"] and result["run"]["score"] == 8
    assert result["rewards"] == dict(awards=[], credited=0, pending=0)
    profile = store.profile("p1")
    assert not profile["rewardsEnabled"] and profile["balance"] == 0 and not profile["credits"]
    assert sum(a["unlocked"] for a in profile["achievements"]) == 3
    assert all(a["reward"] == 0 for a in profile["achievements"])
    assert all(g["reward"] == 0 for g in profile["goals"].values())
    assert all(a["amount"] == 0 for a in profile["awards"])
    assert not store.board()["rows"][0]["prizeEligible"]
    assert store.board(viewer="p1")["prizes"] == []
    with pytest.raises(ArcadeError):
        store.claim("p1", profile["awards"][0]["id"])
    with pytest.raises(ArcadeError):
        store.settings("p1", {"rewards_enabled": True})
    assert (
        store.finish("p1", session["id"], replay["events"], replay["ticks"])["receipt"]["awards"]
        == []
    )
    # A student in the same store continues to receive the normal one-time awards.
    child, _, _ = finish_debug(store, "p2")
    assert child["rewards"]["credited"] > 0 and store.profile("p2")["balance"] > 0


def test_disabling_money_hides_previous_test_credits_without_erasing_achievements(store):
    finish_debug(store)
    old = store.profile("p1")
    assert old["balance"] > 0
    store.register([dict(id="p1", name="Staff", rewards_enabled=False)])
    now = store.profile("p1")
    assert now["balance"] == 0 and now["credits"] == []
    assert [a["unlocked"] for a in now["achievements"]] == [
        a["unlocked"] for a in old["achievements"]
    ]
    with store.db() as db:
        assert (
            db.execute("SELECT SUM(amount) FROM arcade_credits WHERE player='p1'").fetchone()[0]
            == old["balance"]
        )


def test_staff_ui_has_no_money_chips_claim_buttons_or_season_prizes(arcade):
    page, store = arcade
    store.register([dict(id="p1", name="Staff", rewards_enabled=False)])
    pilot_page(page)
    page.locator(".game-card").first.wait_for()
    assert page.locator('.game-reward,[data-tab="rewards"]').count() == 0
    assert "AC" not in page.locator("#gamesRoot").inner_text()
    page.locator('[data-tab="achievements"]').click()
    assert page.locator(".game-achievement").count() == len(GAMES) * 3
    assert page.locator("[data-claim]").count() == 0
    assert "AC" not in page.locator("#gamesRoot").inner_text()
    page.locator('.games-tabs [data-tab="leaders"]').click()
    page.locator(".arcade-ranking").wait_for()
    assert page.locator(".ranking-prizes,.ranking-qualification").count() == 0
    assert "AC" not in page.locator("#gamesRoot").inner_text()
