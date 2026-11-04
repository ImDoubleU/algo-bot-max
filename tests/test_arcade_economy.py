"""Lifetime goals, demanding medals and fortnightly prizes share a bounded ledger."""

from datetime import date, datetime

import pytest

from app.cli.arcade_economy_projection import project
from app.services.arcade import (
    FIRST_GOAL_REWARD,
    GAMES,
    MEDAL_REWARDS,
    MOSCOW,
    ArcadeStore,
    season_info,
    season_key,
)
from tests.test_arcade_server import finish_debug, trace, verified
from tests.test_arcade_server import store as store


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=MOSCOW).timestamp()


@pytest.mark.parametrize(
    "moment,start,end",
    [
        ("2026-11-02T00:00:00", "2026-11-02", "2026-11-16"),
        ("2026-11-09T00:00:00", "2026-11-02", "2026-11-16"),
        ("2026-11-15T23:59:59", "2026-11-02", "2026-11-16"),
        ("2026-11-16T00:00:00", "2026-11-16", "2026-11-30"),
        ("2027-01-01T00:00:00", "2026-12-28", "2027-01-11"),
    ],
)
def test_fixed_fortnights_follow_moscow_midnight_and_survive_new_year(moment, start, end):
    assert season_info(stamp(moment)) == dict(start=start, end=end, days=14)


def test_first_goal_and_medals_never_repeat_after_a_week_season_or_restart(store):
    finish_debug(store)
    first = store.profile("p1")
    assert first["balance"] == 23
    assert first["goals"]["debug"]["reward"] == FIRST_GOAL_REWARD == 5
    assert [a["amount"] for a in first["awards"] if a["kind"] == "master"] == [3, 5, 10]
    for days in (8, 14, 35):
        store.clock.advance(days * 86400)
        store = ArcadeStore(store.path, store.clock)
        result, _, _ = finish_debug(store)
        assert result["rewards"] == dict(awards=[], credited=0, pending=0)
        assert store.profile("p1")["balance"] == 23
        assert store.profile("p1")["goals"]["debug"]["credited"]


def test_two_weeks_share_records_and_seed_then_settle_exactly_once(store):
    store.clock.now = stamp("2026-11-02T12:00:00")
    for game in ("tower", "debug", "memory"):
        verified(store, "p1", game, GAMES[game][0])
    seed = store.session("p1", "tower", "ranked", "keyboard")["setup"]["seed"]
    store.clock.advance(8 * 86400)
    assert store.board()["rows"][0]["score"] == 300
    assert store.profile("p1")["competition"]["score"] == 300
    assert store.session("p2", "tower", "ranked", "keyboard")["setup"]["seed"] == seed
    assert store.profile("p1")["balance"] == 0
    store.clock.now = stamp("2026-11-16T00:00:00")
    assert store.profile("p1")["balance"] == 100
    assert not store.board()["rows"]
    history = store.board()["history"]
    assert len(history) == 1 and history[0]["days"] == 14
    assert history[0]["winners"][0]["prize"] == 100
    restarted = ArcadeStore(store.path, store.clock)
    assert restarted.profile("p1")["balance"] == 100
    assert restarted.board()["history"] == history


def test_legacy_earned_amounts_stay_intact_and_do_not_create_a_second_goal(store):
    with store.db() as db:
        store._award(
            db,
            "p1",
            "weekly",
            "2026-10-19",
            "weekly:2026-10-19:p1:debug",
            10,
            "Earlier goal",
            claimed=True,
        )
        store._award(
            db, "p1", "master", "all", "master3:p1:debug:2", 35, "Earlier gold", claimed=True
        )
        store._credit(db, "p1")
    finish_debug(store)
    profile = store.profile("p1")
    assert profile["balance"] == 53  # Original 45 + new bronze 3 + new silver 5.
    assert profile["goals"]["debug"]["reward"] == 10
    assert not any(a["kind"] == "first" for a in profile["awards"])
    gold = next(a for a in profile["achievements"] if a["game"] == "debug" and a["tier"] == 2)
    assert gold["reward"] == 35 and gold["unlocked"]


def test_existing_weekly_history_is_not_paid_again_as_an_old_season(store):
    for game in ("tower", "debug", "memory"):
        verified(store, "p1", game, GAMES[game][0])
    store.clock.now = stamp("2026-11-03T12:00:00")
    with store.db() as db:
        db.execute("DELETE FROM arcade_meta WHERE key='season_prizes_start'")
        db.execute(
            "INSERT INTO arcade_weeks VALUES(?,?,?,?)", ("2026-10-26", store.clock(), "[]", "[]")
        )
    migrated = ArcadeStore(store.path, store.clock)
    assert migrated.profile("p1")["balance"] == 0
    assert len(migrated.board()["history"]) == 1
    assert migrated.board()["history"][0]["days"] == 7


def test_lower_medal_rates_preserve_earned_unclaimed_amounts_and_apply_to_new_players(store):
    with store.db() as db:
        for tier, amount in enumerate((5, 10, 20)):
            store._award(
                db,
                "p1",
                "master",
                "all",
                f"master3:p1:debug:{tier}",
                amount,
                "Previously earned medal",
            )
    result, _, _ = finish_debug(store)
    assert result["rewards"]["credited"] == 40  # First goal 5 + existing medals 35.
    old = ArcadeStore(store.path, store.clock).profile("p1")
    assert [b["reward"] for b in old["achievements"] if b["game"] == "debug"] == [5, 10, 20]
    assert old["balance"] == 40
    new, _, _ = finish_debug(store, player="p2")
    assert new["rewards"]["credited"] == 23
    assert store.profile("p2")["balance"] == 23
    repeated, _, _ = finish_debug(store)
    assert not repeated["rewards"]["awards"] and store.profile("p1")["balance"] == 40


def test_medals_need_strong_scores_and_quality_not_a_basic_goal(store):
    for game, (goal, targets) in GAMES.items():
        assert goal < targets[0]
        assert not store._master(game, goal, {}, 0)
        assert targets == sorted(targets)
    assert MEDAL_REWARDS == [3, 5, 10]
    assert len(GAMES) * (FIRST_GOAL_REWARD + sum(MEDAL_REWARDS)) == 368
    assert not store._master("typing", 400, {"accuracy": 98}, 2)
    assert store._master("typing", 400, {"accuracy": 99}, 2)
    assert not store._master("react", 15, {"reactionMs": 221, "mistakes": 0}, 2)
    assert not store._master("react", 15, {"reactionMs": 200, "mistakes": 1}, 2)
    assert store._master("react", 15, {"reactionMs": 220, "mistakes": 0}, 2)
    assert not store._master("debug", 8, {"timeMs": 60001}, 2)
    assert store._master("debug", 8, {"timeMs": 60000}, 2)
    assert not store._master("memory", 40, {"moves": 61}, 2)
    assert store._master("memory", 40, {"moves": 60}, 2)
    assert not store._master("words", 40, {"timeMs": 150001}, 2)
    assert store._master("words", 40, {"timeMs": 150000}, 2)


def test_weekly_boundary_inside_a_season_keeps_a_valid_attempt_ranked(store):
    store.clock.now = stamp("2026-11-08T23:59:58")
    result, _, _ = finish_debug(store)
    assert result["run"]["accepted"]
    assert season_key(store.clock()) == "2026-11-02"
    assert store.profile("p1")["balance"] == 23


@pytest.mark.parametrize(
    "prize,expected",
    [(0, [368, 0, 0]), (50, [468, 100, 100]), (75, [518, 150, 150]), (100, [568, 200, 200])],
)
def test_calendar_projection_uses_actual_weekly_caps_and_two_fortnightly_payouts(prize, expected):
    months = project(date(2026, 11, 3), prize)
    assert [m["credited"] for m in months] == expected
    assert [m["pending"] for m in months] == [0, 0, 0]
    assert [m["start"] for m in months] == ["2026-11-03", "2026-12-03", "2027-01-03"]
    assert [m["credited"] for m in project(date(2026, 11, 3), medals=False)] == [80, 0, 0]


@pytest.mark.parametrize("game", ["typing", "react", "memory", "words", "kopatych"])
def test_hard_gold_targets_are_reachable_through_verified_actions(store, game):
    scripts = {
        "typing": """for(let i=0;i<400;i++){W.advance(w,8);
          send({type:'text',value:w.text[w.typed.length]});}W.advance(w,3610-w.tick);""",
        "react": """while(!w.ended&&w.tick<12000){
          if(w.signal==='go'&&w.time-w.since>=.2)send({type:'tap'});W.advance(w,1);}""",
        "memory": """while(!w.ended&&w.tick<12000){if(w.between)send({type:'next'});
          else{const a=w.cards.findIndex((_,i)=>!w.matched.includes(i));
            const b=w.cards.findIndex((v,i)=>i!==a&&v===w.cards[a]);
            send({type:'cell',i:a});W.advance(w,6);send({type:'cell',i:b});}
          W.advance(w,6);}""",
        "words": """while(!w.ended&&w.tick<9000){const word=w.wordPack.answers.find(
          a=>!w.roundWords.includes(a));send({type:'word',value:word});W.advance(w,45);}""",
        "kopatych": """while(!w.ended&&w.tick<5500){if(w.tick%5===0)send({type:'tap'});
          if(w.tick%30===0)for(let i=0;i<3;i++)if(w.upgrades[i]<6&&
          w.harvest-w.spent>=ArcadeExtras.cost(w,i))send({type:'buy',i});W.advance(w,1);}""",
    }
    session = store.session("p1", game, "ranked", "keyboard")
    run = trace(session["setup"], scripts[game])
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(run["ticks"] / 60 + 0.5)
    result = store.finish("p1", session["id"], run["events"], run["ticks"])
    assert result["run"]["accepted"]
    gold = next(
        a for a in store.profile("p1")["achievements"] if a["game"] == game and a["tier"] == 2
    )
    assert gold["unlocked"], result["run"]["report"]
    assert result["rewards"]["credited"] == 23
