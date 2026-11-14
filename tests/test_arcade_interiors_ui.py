"""Illustrated playfields preserve real controls and fit the visible phone viewport."""

from pathlib import Path

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (844, 390), (1440, 1000)])
def test_rally_uses_the_field_without_bands_or_selectable_pedal_text(arcade, size):
    page, _ = arcade
    page.set_viewport_size(dict(width=size[0], height=size[1]))
    page.locator('.game-card[data-game="hill"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_selector(".arcade-countdown", state="detached")
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
    assert page.locator(".arcade-live-goal").is_hidden()
    assert page.locator("#gameLevel").is_hidden()
    assert page.locator(".hill-pedals button").all_inner_texts() == ["", ""]
    geometry = page.locator("#gameDialog").evaluate("""dialog => {
      const canvas = dialog.querySelector('.hill-canvas').getBoundingClientRect();
      const rect = dialog.getBoundingClientRect();
      return {ratio: canvas.height / rect.height, right: rect.right, bottom: rect.bottom,
        hudInside: [...dialog.querySelectorAll('.hill-trip, .hill-instruments>div')].every(n => {
          const r = n.getBoundingClientRect();
          return r.left >= canvas.left && r.right <= canvas.right + 1
            && r.top >= canvas.top && r.bottom <= canvas.bottom;
        }), selection: getComputedStyle(dialog.querySelector('.hill-drive')).userSelect};
    }""")
    assert geometry["ratio"] > .97
    assert geometry["right"] <= size[0] and geometry["bottom"] <= size[1]
    assert geometry["hudInside"] and geometry["selection"] == "none"
    gas = page.locator('[data-pedal="gas"]')
    box = gas.bounding_box()
    assert box["width"] >= 120 and box["height"] >= 180
    page.mouse.move(box["x"] + box["width"] * .8, box["y"] + box["height"] * .65)
    page.mouse.down()
    assert "is-pressed" in gas.get_attribute("class")
    page.wait_for_timeout(250)
    page.mouse.up()
    assert "is-pressed" not in gas.get_attribute("class")
    assert page.evaluate("getSelection().toString()") == ""
    captures = Path(__file__).parents[1] / ".deploy_tmp/game-design-20261114"
    captures.mkdir(exist_ok=True)
    page.locator("#gameDialog").screenshot(path=str(captures / f"hill-{size[0]}-checked.png"))
    page.locator(".game-close").click()


def test_scene_assets_decode_and_code_has_no_small_syntax_spans(arcade):
    page, _ = arcade
    dimensions = page.evaluate("""async () => {
      return Promise.all(['laboratory-v2.webp', 'playroom-v2.webp'].map(async name => {
        const image = new Image(); image.src = '/miniapp/static/worlds/' + name;
        await image.decode(); return [image.naturalWidth, image.naturalHeight];
      }));
    }""")
    assert all(width >= 960 and height >= 1000 for width, height in dimensions)
    page.locator('.game-card[data-game="debug"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
    assert page.locator("#gameDialog").get_attribute("data-interior") == "terminal"
    assert page.locator(".arcade-live-goal").is_hidden()
    assert page.locator("#gameDialog header h2").is_hidden()
    assert page.locator(".debug-code code span").evaluate_all(
        "nodes=>nodes.every(n=>parseFloat(getComputedStyle(n).fontSize)>=18)"
    )
    assert page.locator("#gameScore").evaluate(
        "n=>parseFloat(getComputedStyle(n).fontSize)>=28"
    )
    page.locator(".game-close").click()


@pytest.mark.parametrize("game", ["sort", "blocks", "memory", "typing", "words"])
def test_floating_counters_do_not_cover_the_puzzle_or_inputs(arcade, game):
    page, _ = arcade
    page.set_viewport_size(dict(width=320, height=568))
    page.locator(f'.game-card[data-game="{game}"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_selector(".arcade-countdown", state="detached")
    page.wait_for_selector(".game-dialog.has-interior")
    assert page.locator(".arcade-live-goal").is_hidden()
    assert page.locator("#gameDialog header h2").is_hidden()
    assert page.locator("#gameDialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    assert page.locator("#gameDialog").evaluate("""dialog => {
      const hud = dialog.querySelector('.game-hud').getBoundingClientRect();
      const selector = '.sort-glass,.blocks-board,.memory-grid,.typing-surface,.words-source';
      const field = dialog.querySelector(selector);
      return field.getBoundingClientRect().top >= hud.bottom;
    }""")
    if game == "blocks":
        page.locator('[data-piece="0"]').click()
    elif game == "memory":
        page.locator('[data-card="0"]').click()
        assert "flipped" in page.locator('[data-card="0"]').get_attribute("class")
    elif game == "sort":
        page.locator('[data-tube="0"]').click()
        assert "is-selected" in page.locator('[data-tube="0"]').get_attribute("class")
    elif game == "typing":
        page.locator(".typing-input").press_sequentially("а")
    else:
        page.locator("#arcadeWordInput").fill("кот")
        assert page.locator("#arcadeWordInput").input_value() == "кот"
    page.locator(".game-close").click()


def test_memory_pictures_fill_the_cards_and_decode_at_double_resolution(arcade):
    page, _ = arcade
    page.evaluate("Promise.all(ArcadeSprites.memory.map(id=>ArcadeWorldArt.ready(id)))")
    page.locator('.game-card[data-game="memory"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_selector(".arcade-countdown", state="detached")
    page.locator('[data-card="0"]').click()
    result = page.locator('[data-card="0"] canvas').evaluate("""canvas=>{
      const box=canvas.getBoundingClientRect(),card=canvas.parentElement.getBoundingClientRect();
      return {width:canvas.width,height:canvas.height,ratio:box.width/card.width,
        visible:canvas.getContext('2d').getImageData(0,0,200,200).data.some((v,i)=>i%4===3&&v>0)};
    }""")
    assert result["width"] == result["height"] == 200
    assert result["ratio"] >= .9 and result["visible"]
    page.locator(".game-close").click()


def test_repainting_changes_body_panels_but_keeps_windows_and_alpha(arcade):
    page, _ = arcade
    result = page.evaluate("""async()=>{
      const image=new Image();image.src='/miniapp/static/worlds/car-scout.webp';
      await image.decode();
      const original=document.createElement('canvas');
      original.width=image.width;original.height=image.height;
      const ctx=original.getContext('2d');ctx.drawImage(image,0,0);
      const parent=document.createElement('div');
      parent.innerHTML=ArcadeWorldArt.vehicleMarkup('scout','#d16b63');
      document.body.append(parent);ArcadeWorldArt.paintVehiclePreviews(parent);
      while(parent.firstChild.dataset.paintReady!=='true')await new Promise(r=>setTimeout(r,10));
      const painted=ArcadeWorldArt.vehicleSource('scout','#d16b63').getContext('2d');
      const pixel=(context,x,y)=>[...context.getImageData(x,y,1,1).data];
      const data={original:pixel(ctx,450,250),body:pixel(painted,450,250),
        windowBefore:pixel(ctx,420,155),windowAfter:pixel(painted,420,155),alpha:pixel(painted,0,0)[3]};
      parent.remove();return data;
    }""")
    assert result["body"] != result["original"]
    assert result["body"][0] > result["body"][1]
    assert result["windowBefore"] == result["windowAfter"]
    assert result["alpha"] == 0
