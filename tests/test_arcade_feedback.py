"""Feedback uses legal replays, stays bounded and cannot affect the game economy."""

from pathlib import Path

import pytest

from app.services.arcade import GAMES
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser

OTHER_GAMES = [game for game in GAMES if game not in {"hill", "kopatych"}]
PILOT = Path(__file__).resolve().parents[1] / "app/cli/arcade_journey_pilot.js"


@pytest.mark.parametrize("width", [320, 1440])
def test_legal_gameplay_feedback_preserves_all_fourteen_worlds_and_controls(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=900))
    page.add_script_tag(path=str(PILOT))
    rows = page.evaluate(
        """games=>games.map(game=>{
      const setup={game,seed:17,mode:'journey',device:'keyboard',journey:{stage:1,charges:1}},
        trace=playAdventure(setup), w=ArcadeWorld.create(setup), abort=new AbortController();
      const stage=document.createElement('div');stage.className='game-stage';
      stage.style.cssText='width:'+Math.min(innerWidth-20,480)+'px;position:relative';
      document.body.append(stage);
      const view=ArcadeView.mount(game,stage,()=>{throw Error('Painting sent a game action')},
        {signal:abort.signal,mode:'journey',device:'keyboard',theme:'space',readOnly:true,
          quality:()=> 'high',paused:()=>false});
      let unchanged=true,maxParticles=0,observed=0;
      const update=()=>{const before=JSON.stringify(w);view.update(w,.05);
        unchanged=unchanged&&JSON.stringify(w)===before;
        const count=stage.querySelector('.arcade-feedback')?.childElementCount||0;
        maxParticles=Math.max(maxParticles,count);if(count)observed++;
      };
      update();
      for(const a of trace.events) {
        while(w.tick<a.t){ArcadeWorld.advance(w,Math.min(12,a.t-w.tick));update();}
        ArcadeWorld.input(w,a);update();
      }
      while(w.tick<trace.ticks&&!w.ended){ArcadeWorld.advance(w,Math.min(12,trace.ticks-w.tick));update();}
      const hits=stage.querySelector('.arcade-feedback')?.getAttribute('aria-hidden')==='true';
      abort.abort();const cleaned=stage.querySelector('.arcade-feedback')===null;
      stage.remove();return {game,unchanged,maxParticles,observed,hits,cleaned,
        success:trace.report.journey.success};
    })""",
        OTHER_GAMES,
    )
    assert len(rows) == 14
    for row in rows:
        assert row["unchanged"] and row["hits"] and row["cleaned"], row
        assert row["maxParticles"] <= 44, row
        assert row["observed"] > 0, row
        assert row["success"], row
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_runs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM arcade_credits").fetchone()[0] == 0


def test_reduced_motion_and_low_quality_suppress_particles_and_aborted_effects(arcade):
    page, _ = arcade
    page.emulate_media(reduced_motion="reduce")
    result = page.evaluate("""()=>{
      const stage=document.createElement('div');document.body.append(stage);
      const abort=new AbortController(),
        w=ArcadeWorld.create({game:'tower',mode:'practice',seed:17,device:'keyboard'});
      const view=ArcadeView.mount('tower',stage,()=>{},
        {signal:abort.signal,readOnly:true,quality:()=> 'low',paused:()=>false});
      view.update(w,0);
      for(let n=0;n<500&&!w.ended;n++) {
        ArcadeWorld.advance(w,3);
        if(Math.abs(w.left-w.blocks.at(-1).left)<3)ArcadeWorld.input(w,{type:'tap'});
        view.update(w,.05);
      }
      const reduced=stage.querySelector('.arcade-feedback').dataset.reduced,
        particles=stage.querySelectorAll('.arcade-impact-piece,.arcade-impact-ring,.arcade-flight-trail').length;
      abort.abort();const cleaned=!stage.querySelector('.arcade-feedback');stage.remove();
      return {reduced,particles,cleaned};
    }""")
    assert result == dict(reduced="true", particles=0, cleaned=True)


def test_result_card_contains_only_public_game_result_and_download_is_repeatable(arcade, tmp_path):
    page, store = arcade
    page.evaluate("""()=>{
      const host=document.createElement('div');host.id='shareCheck';host.className='game-result';
      host.innerHTML='<div class="arcade-result-actions"></div>';document.body.append(host);
      const run={g:AlgoGameEngine.games.find(g=>g.id==='tower'),mode:'ranked',oldBest:2,
        finishResult:{run:{accepted:true}}};
      ArcadeFeedback.result(run,host,{score:12,details:{},complete:true});
      Object.defineProperty(navigator,'canShare',{configurable:true,value:()=>false});
    }""")
    with page.expect_download() as event:
        page.locator("#shareCheck .arcade-share-result").click()
    download = event.value
    assert download.suggested_filename == "algo-tower.png"
    path = tmp_path / "result.png"
    download.save_as(path)
    from PIL import Image

    with Image.open(path) as image:
        assert image.size == (1080, 1080)
    assert page.locator("#shareCheck .arcade-share-note").inner_text() == "Карточка сохранена"
    assert page.locator("#shareCheck .arcade-share-result").is_enabled()
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_credits").fetchone()[0] == 0


def test_typing_keeps_the_same_passage_nodes_between_inputs(arcade):
    page, _ = arcade
    result = page.evaluate("""()=>{
      const stage=document.createElement('div');document.body.append(stage);
      const abort=new AbortController();
      const w=ArcadeWorld.create({game:'typing',mode:'practice',device:'keyboard',seed:17});
      const view=ArcadeView.mount('typing',stage,()=>{},
        {signal:abort.signal,mode:'practice',device:'keyboard',quality:()=> 'high',
          paused:()=>false,readOnly:true});
      view.update(w,0);const first=stage.querySelector('.typing-passage>span');
      for(let i=0;i<60;i++){ArcadeWorld.advance(w,1);view.update(w,1/60);}
      const stable=first===stage.querySelector('.typing-passage>span');
      ArcadeWorld.input(w,{type:'text',value:w.text[0],source:'keyboard'});view.update(w,.05);
      const correct=stage.querySelector('.typing-passage>.correct')!==null;
      abort.abort();stage.remove();return {stable,correct};
    }""")
    assert result == dict(stable=True, correct=True)


def test_all_fourteen_share_cards_render_without_pupil_names_or_ids(arcade):
    page, _ = arcade
    rows = page.evaluate(
        """async games=>{
          const original=CanvasRenderingContext2D.prototype.fillText,words=[];
          CanvasRenderingContext2D.prototype.fillText=function(s,...args){
            words.push(String(s));return original.call(this,s,...args);};
          try {
            const rows=[];
            for(const game of games){
              const g=AlgoGameEngine.games.find(g=>g.id===game);
              const blob=await ArcadeFeedback.card(g,{score:12345,details:{reactionMs:250},
                journey:{stage:12,stars:3}},'journey');
              rows.push({game,type:blob.type,size:blob.size});
            }
            return {rows,words};
          } finally {CanvasRenderingContext2D.prototype.fillText=original;}
        }""",
        OTHER_GAMES,
    )
    assert len(rows["rows"]) == 14
    assert all(row["type"] == "image/png" and row["size"] > 3000 for row in rows["rows"])
    assert not {"Марк", "Соня", "p1", "p2", "Демо"}.intersection(rows["words"])


def test_denied_native_share_falls_back_to_download_and_cancel_does_not_download(arcade):
    page, _ = arcade
    page.evaluate("""()=>{
      const host=document.createElement('div');host.id='nativeShare';
      host.innerHTML='<div class="arcade-result-actions"></div>';document.body.append(host);
      ArcadeFeedback.result({g:AlgoGameEngine.games.find(g=>g.id==='tower'),mode:'practice'},
        host,{score:4,details:{},complete:true});
      Object.defineProperty(navigator,'canShare',{configurable:true,value:()=>true});
      Object.defineProperty(navigator,'share',{configurable:true,
        value:()=>Promise.reject(new DOMException('Denied','NotAllowedError'))});
    }""")
    with page.expect_download():
        page.locator("#nativeShare .arcade-share-result").click()
    page.wait_for_function("!document.querySelector('#nativeShare .arcade-share-result').disabled")
    downloads = []
    page.on("download", lambda download: downloads.append(download))
    page.evaluate("""()=>{
      Object.defineProperty(navigator,'share',{configurable:true,
        value:()=>Promise.reject(new DOMException('Cancelled','AbortError'))});
    }""")
    page.locator("#nativeShare .arcade-share-result").click()
    page.wait_for_function("!document.querySelector('#nativeShare .arcade-share-result').disabled")
    assert not downloads
    assert page.locator("#nativeShare .arcade-share-note").is_hidden()
