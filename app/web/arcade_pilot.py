"""Add the private pilot entry without replacing the production miniapp template."""

import json
import re


def inject_pilot(source: str, max_ids: list[int]) -> str:
    config = json.dumps({"ids": sorted({i for i in max_ids if i > 0})})
    source = re.sub(r"(app-(?:core|shell)\.js)\?v=[^\"]+", r"\1?v=arcade-pilot-3", source)
    source = source.replace(
        '<script src="/miniapp/static/app-shell.js',
        f'<script type="application/json" id="arcadePilotConfig">{config}</script>'
        '<script src="/miniapp/static/app-arcade-pilot.js?v=4"></script>'
        '<script src="/miniapp/static/app-shell.js',
        1,
    )
    source = source.replace(
        '<button class="nav-button" data-view="store">',
        '<button class="nav-button" data-view="games" hidden>'
        '<i data-lucide="gamepad-2"></i><span>Игры</span></button>'
        '<button class="nav-button" data-view="store">',
        1,
    )
    return source.replace(
        '<section id="storeView"',
        '<section id="gamesView" class="view" data-view-panel="games">'
        '<div id="gamesRoot"></div></section><section id="storeView"',
        1,
    )
