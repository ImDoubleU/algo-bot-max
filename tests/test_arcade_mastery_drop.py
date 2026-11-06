"""Progression cannot be farmed; arenas use identical browser/server mechanics."""

import json

import pytest

from app.services import arcade_runtime
from app.services.arcade import ArcadeError, ArcadeStore
from app.services.arcade_mastery import league, mastery
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import finish_debug, trace
from tests.test_arcade_server import store as store


def test_mastery_is_derived_from_unique_stars_and_medals():
    journeys = {"drop": {"cleared": 4, "stars": 8}}
    badges = [dict(game="drop", tier=i, unlocked=True) for i in range(3)]
    m = mastery(journeys, badges)
    assert m["xp"] == 1100 and m["breadth"] == 1
    assert m["title"] == "Новичок"  # One game cannot earn a breadth-based title.
    assert m["floor"] <= m["xp"] < m["next"]
    assert mastery(journeys, badges) == m
    assert mastery({"drop": {"cleared": 4, "stars": 9}}, badges)["xp"] == 1125
    full = mastery(
        {str(i): {"cleared": 24, "stars": 72} for i in range(15)},
        [dict(game=str(g), tier=i, unlocked=True) for g in range(16) for i in range(3)],
    )
    assert full["level"] == 50 and full["next"] is None and full["title"] == "Легенда"


@pytest.mark.parametrize("score,tier", [(0, 0), (199, 0), (200, 1), (450, 2), (800, 3), (1200, 4)])
def test_weekly_league_requires_three_games(score, tier):
    assert league(score, 2)["name"] == "Квалификация"
    assert league(score, 3)["tier"] == tier


def test_mastery_survives_new_week_and_repeated_record_does_not_add_xp(store):
    finish_debug(store)
    initial = store.profile("p1")["mastery"]
    assert initial["xp"] == 600
    finish_debug(store)
    assert store.profile("p1")["mastery"] == initial
    store.clock.advance(8 * 86400)
    restarted = ArcadeStore(store.path, store.clock)
    profile = restarted.profile("p1")
    assert profile["mastery"] == initial
    assert profile["competition"]["score"] == 0
    assert profile["competition"]["league"]["name"] == "Квалификация"
    assert restarted.profile("p2")["mastery"]["xp"] == 0


def test_server_owns_competitive_arena_and_journey_assigns_arena(store):
    for arena in ("classic", "bowl", "slopes", "pins"):
        setup = store.session("p1", "drop", "practice", "touch", arena=arena)["setup"]
        assert arcade_runtime.verify(setup, [], 1)["details"]["arena"] == arena
        with pytest.raises(ArcadeError):
            store.session("p1", "drop", "ranked", "touch", arena=arena)
    assert store.session("p1", "drop", "ranked", "touch")["setup"]["arena"] == "classic"
    with pytest.raises(ArcadeError):
        store.session("p1", "drop", "practice", "touch", arena="fake")
    with pytest.raises(ArcadeError):
        store.session("p1", "debug", "practice", "touch", arena="bowl")
    with arcade_runtime.context() as vm:
        assert (
            vm.eval("JSON.stringify(Array.from({length:6},(_,i)=>ArcadeDrop.chapter(i*4+1)))")
            == '["classic","bowl","slopes","pins","bowl","pins"]'
        )


def test_rotation_coupling_breaks_a_vertically_balanced_tower():
    with arcade_runtime.context() as vm:
        vm.eval("""function tower(version){const W=ArcadeWorld,
          w=W.create({game:'drop',seed:42,mode:'practice',dropPhysics:version});
          function ball(id,r,level,y){return {id,x:180,y,r,level,vx:0,vy:0,age:3,angle:.1,
            spin:.4,squash:0,squashV:0,squashAxis:Math.PI/2,softLoad:0};}
          w.balls=[ball(1,31,3,385),ball(2,18,1,336)];w.nextId=2;W.advance(w,600);
          return w.balls;}""")
        old, new = vm.call("tower", 2), vm.call("tower", 3)
        assert old[0]["x"] == old[1]["x"] == 180  # Legacy replay compatibility.
        assert abs(new[1]["x"] - new[0]["x"]) > 49
        assert new[1]["y"] > 390
        assert abs(new[0]["vx"]) < 1 and abs(new[1]["vx"]) < 1


@pytest.mark.parametrize("arena", ["classic", "bowl", "slopes", "pins"])
def test_arenas_stay_finite_under_many_drops_and_replay_exactly(arena):
    setup = dict(
        game="drop", seed=71, mode="practice", device="keyboard", dropPhysics=3, arena=arena
    )
    result = trace(
        setup,
        """let bounded=true;
      for(let i=0;i<250&&!w.ended;i++){send({type:'tap',x:25+(i*83)%310});W.advance(w,42);
        if(!w.balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.squash].every(Number.isFinite)
          &&b.x>=10&&b.x<=350&&b.y<=417))throw Error('Unbounded arena');}
    """,
    )
    assert result["report"]["details"]["physics"] == "soft3"
    assert result["report"]["details"]["arena"] == arena
    assert arcade_runtime.verify(setup, result["events"], result["ticks"]) == result["report"]


def test_incompatible_drop_records_stay_in_history_but_not_competitive_board(store):
    rows = [
        dict(
            game="drop",
            rank_score=100,
            score=100,
            player="p1",
            name="Test",
            group_name="Demo",
            device="keyboard",
            created=1,
            report=json.dumps(dict(details=dict(physics="soft2"), level=1, timeMs=100)),
        )
    ]
    assert store._game_board(rows, "drop") == []
    rows[0]["report"] = json.dumps(
        dict(details=dict(physics="soft4", arena="classic"), level=1, timeMs=100)
    )
    assert len(store._game_board(rows, "drop")) == 1


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_mastery_and_arena_controls_fit_and_start_selected_arena(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=900))
    assert page.locator(".arcade-passport").is_visible()
    assert page.locator(".arcade-passport").evaluate("e=>e.scrollWidth<=e.clientWidth")
    page.locator('.game-card[data-game="drop"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator('[data-arena="pins"]').click()
    assert page.locator('[data-arena="pins"]').get_attribute("aria-pressed") == "true"
    assert page.locator(".arcade-arena-grid").evaluate("e=>e.scrollWidth<=e.clientWidth")
    page.locator("[data-practice-start]").click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.locator(".game-stage canvas").wait_for()
    with store.db() as db:
        saved = json.loads(
            db.execute(
                "SELECT setup FROM arcade_sessions ORDER BY created DESC LIMIT 1"
            ).fetchone()[0]
        )
    assert saved["arena"] == "pins" and saved["dropPhysics"] == 4
