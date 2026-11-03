"""Deterministic driving, isolated garage accounting and archived runner records."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import arcade_runtime
from app.services.arcade import ArcadeError, ArcadeStore
from app.services.arcade_hill import HillStore
from tests.test_arcade_server import Clock, verified


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.arcade.secrets.randbits", lambda _: 17)
    store = ArcadeStore(tmp_path / "hill.sqlite3", Clock())
    store.register([dict(id="p1", name="Марк"), dict(id="p2", name="Соня")])
    return store


def drive(setup, seconds=30):
    with arcade_runtime.context() as vm:
        vm.eval("""function drive(setup,seconds){
          const W=ArcadeWorld,w=W.create(setup),events=[];
          const send=(pedal,value)=>{if(w.hill[pedal]===value)return;
            const a={type:'pedal',pedal,value,t:w.tick,source:w.device};
            W.input(w,a);events.push(a);};
          while(!w.ended&&w.tick<seconds*60){
            const h=w.hill,angle=Math.atan2(Math.sin(h.angle),Math.cos(h.angle));
            const error=-angle-h.omega*.35;
            send('gas',h.contact?Number(angle<.55):Number(error>0));
            send('brake',h.contact?Number(angle>.75):Number(error<-.08));
            W.advance(w,6);
          }
          return {report:W.report(w),events,ticks:w.tick};
        }""")
        return vm.call("drive", setup, seconds)


def finish(store, session, run, abandoned=False):
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(run["ticks"] / 60 + 0.5)
    return store.finish("p1", session["id"], run["events"], run["ticks"], abandoned)


@pytest.mark.parametrize("route", ["meadow", "dunes", "snow", "moon", "volcano"])
def test_all_surfaces_replay_exactly_with_real_jumps_and_different_gravity(route):
    setup = dict(
        game="hill",
        mode="practice",
        seed=17,
        device="touch",
        hill=dict(route=route, car="scout", upgrades={}),
    )
    run = drive(setup)
    assert arcade_runtime.verify(setup, run["events"], run["ticks"]) == run["report"]
    assert run["report"]["score"] > 100
    assert run["report"]["details"]["jumps"] > 0
    assert run["report"]["details"]["physics"] == "hill1"


def test_idle_garage_and_idle_car_do_not_generate_money(store):
    garage = HillStore(store)
    before = garage.get("p1")
    store.clock.advance(30 * 86400)
    after = garage.get("p1")
    assert {k: v for k, v in after.items() if k != "tasks"} == {
        k: v for k, v in before.items() if k != "tasks"
    }
    session = store.session("p1", "hill", "practice", "keyboard")
    with arcade_runtime.context() as vm:
        vm.eval(
            "function ready(s){const w=ArcadeWorld.create(s);"
            "return {wheels:w.hill.wheels.length,contact:w.hill.contact};}"
        )
        assert vm.call("ready", session["setup"]) == dict(wheels=2, contact=2)
    report = arcade_runtime.verify(session["setup"], [], 7200)
    assert report["score"] == 0
    result = finish(store, session, dict(events=[], ticks=report["ticks"]))
    assert result["garage_coins"] == 0
    assert garage.get("p1")["balance"] == before["balance"]


def test_verified_finish_pays_garage_once_and_never_touches_other_player_or_farm(store):
    garage = HillStore(store)
    other = garage.get("p2")
    session = store.session("p1", "hill", "practice", "keyboard")
    run = drive(session["setup"])
    result = finish(store, session, run)
    reward = run["report"]["details"]["coins"] + run["report"]["score"] // 15
    assert result["garage_coins"] == reward > 0
    assert not result["run"]["accepted"]
    saved = garage.get("p1")
    assert saved["balance"] == 250 + reward
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: store.finish("p1", session["id"], [], 0), range(3)))
    assert all(r["duplicate"] for r in results)
    assert garage.get("p1") == saved
    assert garage.get("p2") == other
    assert store.profile("p1")["balance"] == 0
    assert HillStore(ArcadeStore(store.path, store.clock)).get("p1") == saved


def test_abandon_and_fake_input_do_not_pay_garage(store):
    garage = HillStore(store)
    session = store.session("p1", "hill", "practice", "keyboard")
    run = drive(session["setup"], 5)
    assert finish(store, session, run, abandoned=True)["garage_coins"] == 0
    assert garage.get("p1")["balance"] == 250
    session = store.session("p1", "hill", "practice", "keyboard")
    report = arcade_runtime.verify(session["setup"], [dict(type="score", score=100000, t=0)], 3600)
    assert report["score"] == 0


def test_parts_have_exact_costs_ownership_and_idempotency_and_ranked_is_stock(store):
    garage = HillStore(store)
    first = garage.act("p1", "unique-upgrade-01", "upgrade", "engine")
    assert first["balance"] == 120
    assert first["upgrades"]["scout"]["engine"] == 1
    assert garage.act("p1", "unique-upgrade-01", "upgrade", "engine") == first
    with pytest.raises(ArcadeError):
        garage.act("p1", "unique-upgrade-01", "upgrade", "tank")
    with pytest.raises(ArcadeError):
        garage.act("p1", "unique-upgrade-02", "upgrade", "engine")
    with pytest.raises(ArcadeError):
        garage.act("p1", "unique-buy-rover-01", "buy", "rover")
    with pytest.raises(ArcadeError):
        store.session("p1", "hill", "practice", "keyboard", arena="moon")
    with pytest.raises(ArcadeError):
        store.session("p1", "hill", "ranked", "keyboard", arena="meadow")
    ranked = store.session("p1", "hill", "ranked", "keyboard")["setup"]["hill"]
    practice = store.session("p1", "hill", "practice", "keyboard")["setup"]["hill"]
    assert ranked["car"] == "scout" and ranked["upgrades"] == {}
    assert practice["upgrades"]["engine"] == 1
    assert garage.get("p2")["upgrades"]["scout"]["engine"] == 0
    keyboard = store.session("p1", "hill", "ranked", "keyboard")["setup"]
    touch = store.session("p2", "hill", "ranked", "touch")["setup"]
    assert keyboard["seed"] == touch["seed"]
    assert keyboard["hill"] == touch["hill"]


def test_claim_all_uses_verified_metrics_once_and_expired_daily_tasks_never_appear_ready(store):
    garage = HillStore(store)
    session = store.session("p1", "hill", "practice", "keyboard")
    finish(store, session, drive(session["setup"]))
    before = garage.get("p1")
    ready = [t for t in before["tasks"] if t["ready"] and not t["claimed"]]
    assert ready
    after = garage.act("p1", "unique-claim-all-01", "claim_all")
    assert after["balance"] == before["balance"] + sum(t["reward"] for t in ready)
    assert not any(t["ready"] and not t["claimed"] for t in after["tasks"])
    again = garage.act("p1", "unique-claim-all-02", "claim_all")
    assert again == after
    store.clock.advance(86400)
    assert not any(t["ready"] for t in garage.get("p1")["tasks"] if t["category"] == "Сегодня")


def test_retired_runner_keeps_replay_coins_and_mastery_without_becoming_a_car_record(store):
    verified(store, "p1", "runner", 40)
    with store.db() as db:
        db.execute(
            "INSERT INTO arcade_journeys VALUES(?,?,?,?,?,?,?)",
            ("p1", "runner", 1, 3, 20, store.clock(), "{}"),
        )
        store._award(
            db, "p1", "master", "all", "master3:p1:runner:0", 10, "Рывок · бронза", claimed=True
        )
    profile = store.profile("p1")
    assert profile["balance"] == 10
    assert profile["mastery"]["games"]["runner"]["xp"] == 250
    assert profile["best"]["hill"] == 0 and profile["journeys"]["hill"]["cleared"] == 0
    assert any(r["game"] == "runner" for r in profile["runs"])
    assert not store.board()["rows"]
    with pytest.raises(ArcadeError):
        store.session("p1", "runner", "ranked", "keyboard")
    report = arcade_runtime.verify(
        dict(game="runner", seed=17, mode="ranked", device="keyboard"), [], 180
    )
    assert report["score"] == 0 and "hill" not in report["details"]


def test_journey_finishes_with_stars_and_server_records_new_missions(store):
    session = store.session("p1", "hill", "journey", "keyboard", stage=1)
    run = drive(session["setup"])
    assert run["report"]["journey"]["success"]
    assert run["report"]["journey"]["stars"] >= 1
    finish(store, session, run)
    assert store.profile("p1")["journeys"]["hill"]["unlocked"] == 2
    assert store.profile("p1")["journeys"]["debug"]["unlocked"] == 1
