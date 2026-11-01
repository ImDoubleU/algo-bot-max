"""Keep independent feature modules when merging the desktop and laptop branches."""

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from app.cli.games_preview import inject_games

STATIC = Path(__file__).parents[1] / "app/web/static/miniapp"


class Assets(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.scripts = []
        self.styles = []
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "script" and attributes.get("src"):
            self.scripts.append(Path(urlsplit(attributes["src"]).path).name)
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.styles.append(Path(urlsplit(attributes["href"]).path).name)


def test_games_preview_preserves_help_collections_and_connections():
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    required_scripts = {
        "app-pizza.js", "app-connections-export.js", "app-help-media-catalog.js",
        "app-help-guides.js", "app-help.js", "app.js",
    }
    for markup in (source, inject_games(source)):
        assets = Assets(markup)
        assert required_scripts <= set(assets.scripts)
        assert {"pizza.css", "connections.css", "help.css"} <= set(assets.styles)
        assert max(Counter(assets.scripts).values()) == 1
    production = Assets(source)
    assert "app-games.js" not in production.scripts
    assert "ALGO_GAMES_PROTOTYPE=true" not in source
    preview = Assets(inject_games(source))
    assert {"games-engine.js", "games-motion.js", "app-games.js"} <= set(preview.scripts)
    assert preview.scripts.index("app-pizza.js") < preview.scripts.index("app.js")
    assert preview.scripts.index("app-games.js") < preview.scripts.index("app.js")
