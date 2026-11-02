"""Local arcade, fictional pupils, server-verified scores and isolated test rewards.

Run: .venv/Scripts/python.exe -m app.cli.games_preview
Open: http://127.0.0.1:8772/
Production databases, wallets, bindings and bot delivery are never used.
"""

import re


def inject_games(source: str) -> str:
    source = source.replace(
        "</head>",
        '<link rel="stylesheet" href="/miniapp/static/games.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-extra.css?v=1" />'
        '<link rel="stylesheet" href="/miniapp/static/games-farm.css?v=1" /></head>',
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
        '<script src="/miniapp/static/games-extra.js?v=1"></script>'
        '<script src="/miniapp/static/games-engine.js?v=1"></script>'
        '<script src="/miniapp/static/games-motion.js?v=1"></script>'
        '<script src="/miniapp/static/games-art.js?v=1"></script>'
        '<script src="/miniapp/static/games-world.js?v=1"></script>'
        '<script src="/miniapp/static/games-sprites.js?v=1"></script>'
        '<script src="/miniapp/static/games-view.js?v=1"></script>'
        '<script src="/miniapp/static/games-extra-view.js?v=1"></script>'
        '<script src="/miniapp/static/games-farm.js?v=1"></script>'
        '<script src="/miniapp/static/app-games.js?v=1"></script>',
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
