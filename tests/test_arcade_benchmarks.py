"""Benchmark scores are replayed, owned, persistent and cannot issue AC."""

import pytest

from app.services import arcade_runtime
from app.services.arcade import ArcadeError
from app.services.arcade_benchmarks import BenchmarkStore
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import store as store


def trace(setup):
    with arcade_runtime.context() as vm:
        vm.eval("""function benchPilot(setup){
          const B=ArcadeBenchmarks,w=B.create(setup),events=[];
          const send=a=>{const e={...a,t:w.tick};events.push(e);B.input(w,e);};
          while(!w.ended&&w.tick<18000){
            if(w.phase==='show'){B.advance(w,w.until-w.tick+7);continue;}
            B.advance(w,12);
            if(w.test==='number')send({type:'number',value:w.score<5?w.number:'999999999999999999999999999'});
            if(w.test==='verbal'){
              const seen=!!w.seen[w.word],correct=seen?'seen':'new';
              send({type:'word',value:w.score<10?correct:seen?'new':'seen'});
            }
            if(w.test==='sequence')send({type:'cell',i:w.score<3?w.pattern[w.index]:(w.pattern[w.index]+1)%9});
            if(w.test==='spatial')send({type:'choice',i:w.score<12?w.correct:(w.correct+1)%4});
          }
          return {events,ticks:w.tick,report:B.report(w)};
        }""")
        return vm.call("benchPilot", setup)


@pytest.mark.parametrize(
    "test,score", [("number", 5), ("verbal", 10), ("sequence", 3), ("spatial", 12)]
)
def test_real_benchmark_replay_is_saved_once_without_awards(store, test, score):
    service = BenchmarkStore(store)
    session = service.start("p1", test)
    run = trace(session["setup"])
    assert run["report"]["complete"] and run["report"]["score"] == score
    with pytest.raises(ArcadeError):
        service.finish("p1", session["id"], run["events"], run["ticks"])
    store.clock.advance(run["ticks"] / 60 + 1)
    result = service.finish("p1", session["id"], run["events"], run["ticks"])
    assert result["report"] == run["report"]
    assert service.finish("p1", session["id"], run["events"], run["ticks"])["duplicate"]
    assert service.stats("p1", test)["history"][0]["score"] == score
    assert service.stats("p2", test)["history"] == []
    assert not store.profile("p1")["awards"] and store.profile("p1")["balance"] == 0
    with pytest.raises(ArcadeError):
        service.finish("p2", session["id"], run["events"], run["ticks"])


def test_benchmark_norms_are_sourced_and_spatial_average_is_not_invented(store):
    service = BenchmarkStore(store)
    for test in ("number", "verbal", "sequence"):
        value = service.stats("p1", test)
        assert value["reference"]["source"].startswith("https://humanbenchmark.com/")
        assert value["local"]["mean"] is None
        assert "percentile" not in value
    assert service.stats("p1", "spatial")["reference"] is None


def test_lifetime_record_is_kept_after_ten_lower_results(store):
    service = BenchmarkStore(store)
    with store.db() as db:
        for i in range(12):
            db.execute(
                "INSERT INTO arcade_benchmark_runs VALUES(?,?,?,?,?,?)",
                (f"history-{i}", "p1", "number", 15 if i == 0 else 3, "{}", store.clock() + i),
            )
    stats = service.stats("p1", "number")
    assert stats["best"] == 15
    assert len(stats["history"]) == 10 and all(r["score"] == 3 for r in stats["history"])


def test_spatial_choices_are_distinct_and_only_one_matches_under_rotation():
    with arcade_runtime.context() as vm:
        assert vm.eval("""(()=>{
          const norm=s=>{const x=Math.min(...s.map(p=>p[0])),y=Math.min(...s.map(p=>p[1]));
            return s.map(([a,b])=>[a-x,b-y]).map(p=>p.join(',')).sort().join(';');};
          const canon=s=>{const out=[];for(let n=0;n<4;n++){
            out.push(norm(s));s=s.map(([x,y])=>[-y,x]);}return out.sort()[0];};
          for(let seed=1;seed<=100;seed++){
            const w=ArcadeBenchmarks.create({test:'spatial',seed});
            for(let n=0;n<30;n++){
              if(new Set(w.choices.map(norm)).size!==4)return false;
              if(w.choices.filter(s=>canon(s)===canon(w.shape)).length!==1)return false;
              ArcadeBenchmarks.advance(w,12);ArcadeBenchmarks.input(w,{type:'choice',i:w.correct});
            }
          }return true;
        })()""")


@pytest.mark.parametrize("width", [320, 1440])
def test_hub_has_distinct_tests_large_controls_and_keeps_classic_reaction(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    page.locator('.game-card[data-game="react"]').click()
    assert page.locator(".benchmark-tests button").count() == 5
    for button in page.locator(".benchmark-tests button").all():
        assert button.bounding_box()["height"] >= 70
    page.locator('[data-benchmark="spatial"]').click()
    page.locator(".benchmark-primary").wait_for()
    assert page.locator(".benchmark-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    page.locator("[data-bench-back]").click()
    page.locator("[data-benchmark-react]").click()
    assert page.locator(".arcade-menu-actions>button").count() == 4
    page.locator(".game-close").click()


@pytest.mark.parametrize("width", [320, 1440])
def test_number_benchmark_real_ui_saves_terminal_result_and_displays_comparison(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=900))
    page.locator('.game-card[data-game="react"]').click()
    page.locator('[data-benchmark="number"]').click()
    page.locator("[data-bench-start]").click()
    page.locator("#benchmarkNumber").wait_for()
    page.wait_for_timeout(130)
    page.locator("#benchmarkNumber").fill("9999")
    page.locator(".benchmark-number-form button").click()
    page.locator(".benchmark-result").wait_for()
    assert page.locator(".benchmark-result>strong").inner_text() == "0"
    assert "7" in page.locator(".benchmark-comparison").inner_text()
    assert page.locator(".benchmark-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    assert not store.profile("p1")["awards"]
    page.locator("[data-bench-close]").click()
