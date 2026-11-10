"""Reproductions from the November 10 audit; old replays remain valid."""

import json

from app.services import arcade_runtime
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import store as store


def test_school_word_curation_is_versioned_and_keeps_the_general_dictionary(store):
    assert store.session("p1", "words", "practice", "keyboard")["setup"]["wordDictionary"] == 3
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const p=ArcadeExtras.packsV2.find(p=>p.answers.includes('пенис')),
            old=ArcadeWorld.create({game:'words',seed:17,mode:'practice',wordDictionary:2,wordRoots:[p.root]}),
            current=ArcadeWorld.create({game:'words',seed:17,mode:'practice',wordDictionary:3,wordRoots:[p.root]});
          return {legacy:old.wordPack.answers.includes('пенис'),
            current:current.wordPack.answers.includes('пенис'),
            remaining:current.wordPack.answers.length, roots:ArcadeExtras.packsV2.length};
        })())""")
        )
    assert result["legacy"] and not result["current"]
    assert result["remaining"] > 20 and result["roots"] > 100


def test_live_medal_hint_uses_play_time_instead_of_time_spent_between_tasks(arcade):
    page, _ = arcade
    result = page.evaluate("""() => ArcadeResults.liveGoal(
      {id:'debug',clockRules:2,activeTicks:600,time:500,score:8,details:{}},
      {goal:5,unit:'задач'}, {claimed:true},
      {target:8,requirements:{timeMs:180000}}, false)""")
    assert result["text"] == "Цель выполнена · закончи игру"


def test_random_case_results_cannot_impersonate_a_player_through_the_api(arcade):
    page, _ = arcade
    result = page.evaluate("""async()=>{
      const r=await fetch('/preview/arcade/cases/actions',{method:'POST',
        headers:{'X-Miniapp-Token':'p1','Content-Type':'application/json'},
        body:JSON.stringify({id:'spoofed-player-0001',action:'open',item:'scout',player:'p2'})});
      return r.status;
    }""")
    assert result == 422
