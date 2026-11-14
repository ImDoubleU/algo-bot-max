"""Local arcade, fictional pupils, server-verified scores and isolated test rewards.

Run: .venv/Scripts/python.exe -m app.cli.games_preview
Open: http://127.0.0.1:8772/
Production databases, wallets, bindings and bot delivery are never used.
"""

import re


def inject_games(source: str) -> str:
    source = source.replace(
        "</head>",
        '<link rel="stylesheet" href="/miniapp/static/games.css?v=2" />'
        '<link rel="stylesheet" href="/miniapp/static/games-extra.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-farm.css?v=2" />'
        '<link rel="stylesheet" href="/miniapp/static/games-cases.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-journey.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-mastery.css?v=4" />'
        '<link rel="stylesheet" href="/miniapp/static/games-menu.css?v=2" />'
        '<link rel="stylesheet" href="/miniapp/static/games-play.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-personality.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-farm-journal.css?v=6" />'
        '<link rel="stylesheet" href="/miniapp/static/games-lobby.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-ranking.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-hill.css?v=5" />'
        '<link rel="stylesheet" href="/miniapp/static/games-feedback.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-sort.css?v=4" />'
        '<link rel="stylesheet" href="/miniapp/static/games-lessons.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-expedition.css?v=2" />'
        '<link rel="stylesheet" href="/miniapp/static/games-benchmarks.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-mobile.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-drop-lab.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-gallery.css?v=2" />'
        '<link rel="stylesheet" href="/miniapp/static/games-worlds.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-interiors.css?v=3" />'
        '<link rel="stylesheet" href="/miniapp/static/games-frontiers.css?v=1" /></head>',
    )
    source = source.replace(
        '<button class="nav-button is-active" data-view="dashboard">',
        '<button class="nav-button" data-view="games"><i data-lucide="gamepad-2"></i>'
        "<span>Игры</span></button>"
        '<button class="nav-button is-active" data-view="dashboard">',
        1,
    )
    source = source.replace(
        '<section id="storeView"',
        '<section id="gamesView" class="view" data-view-panel="games">'
        '<div id="gamesRoot"></div></section><section id="storeView"',
        1,
    )
    source = re.sub(
        r'(<script src="/miniapp/static/app-core\.js[^\"]*"></script>)',
        lambda match: (
            match.group(1) + "<script>window.ALGO_GAMES_PROTOTYPE=true;"
            'if(queryParam("view")==="games")state.view="games";</script>'
        ),
        source,
        count=1,
    )
    return re.sub(
        r'(?=<script src="/miniapp/static/app\.js)',
        '<script src="/miniapp/static/games-words-data.js?v=2"></script>'
        '<script src="/miniapp/static/games-lessons.js?v=1"></script>'
        '<script src="/miniapp/static/games-sort-levels.js?v=2"></script>'
        '<script src="/miniapp/static/games-expedition.js?v=1"></script>'
        '<script src="/miniapp/static/games-frontiers.js?v=1"></script>'
        '<script src="/miniapp/static/games-extra.js?v=10"></script>'
        '<script src="/miniapp/static/games-hill.js?v=3"></script>'
        '<script src="/miniapp/static/games-engine.js?v=7"></script>'
        '<script src="/miniapp/static/games-motion.js?v=1"></script>'
        '<script src="/miniapp/static/games-art.js?v=3"></script>'
        '<script src="/miniapp/static/games-journey.js?v=6"></script>'
        '<script src="/miniapp/static/games-drop.js?v=3"></script>'
        '<script src="/miniapp/static/games-drop-stable.js?v=2"></script>'
        '<script src="/miniapp/static/games-drop-soft.js?v=2"></script>'
        '<script src="/miniapp/static/games-drop-lab.js?v=1"></script>'
        '<script src="/miniapp/static/games-clock.js?v=1"></script>'
        '<script src="/miniapp/static/games-world.js?v=13"></script>'
        '<script src="/miniapp/static/games-benchmarks.js?v=3"></script>'
        '<script src="/miniapp/static/games-world-art.js?v=5"></script>'
        '<script src="/miniapp/static/games-sprites.js?v=6"></script>'
        '<script src="/miniapp/static/games-drop-art.js?v=3"></script>'
        '<script src="/miniapp/static/games-feedback.js?v=2"></script>'
        '<script src="/miniapp/static/games-expedition-view.js?v=3"></script>'
        '<script src="/miniapp/static/games-frontier-view.js?v=1"></script>'
        '<script src="/miniapp/static/games-debug-view.js?v=1"></script>'
        '<script src="/miniapp/static/games-viewport.js?v=1"></script>'
        '<script src="/miniapp/static/games-drop-lab-view.js?v=3"></script>'
        '<script src="/miniapp/static/games-view.js?v=16"></script>'
        '<script src="/miniapp/static/games-sort-view.js?v=7"></script>'
        '<script src="/miniapp/static/games-extra-view.js?v=7"></script>'
        '<script src="/miniapp/static/games-hill-art.js?v=4"></script>'
        '<script src="/miniapp/static/games-hill-view.js?v=9"></script>'
        '<script src="/miniapp/static/games-hill-garage.js?v=6"></script>'
        '<script src="/miniapp/static/games-farm-art.js?v=4"></script>'
        '<script src="/miniapp/static/games-farm.js?v=7"></script>'
        '<script src="/miniapp/static/games-cases.js?v=4"></script>'
        '<script src="/miniapp/static/games-journey-view.js?v=9"></script>'
        '<script src="/miniapp/static/games-gallery.js?v=2"></script>'
        '<script src="/miniapp/static/games-menu.js?v=8"></script>'
        '<script src="/miniapp/static/games-personality.js?v=8"></script>'
        '<script src="/miniapp/static/games-results.js?v=13"></script>'
        '<script src="/miniapp/static/games-benchmark-view.js?v=4"></script>'
        '<script src="/miniapp/static/games-interiors.js?v=2"></script>'
        '<script src="/miniapp/static/app-games.js?v=39"></script>',
        source,
        count=1,
    )


if __name__ == "__main__":
    import runpy
    import sys

    sys.argv[1:1] = [
        "--games",
        "--port",
        "8772",
        "--database-name",
        "games-preview.sqlite3",
    ]
    runpy.run_module("app.cli.pizza_preview", run_name="__main__")
