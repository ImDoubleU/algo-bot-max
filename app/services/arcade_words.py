"""Persistent, non-repeating source-word decks; chosen roots are part of the replay."""

import json
import secrets
from functools import lru_cache

from app.services import arcade_runtime


def install(db):
    db.execute("""CREATE TABLE IF NOT EXISTS arcade_word_decks(
        player TEXT PRIMARY KEY REFERENCES arcade_players(id), state TEXT NOT NULL)""")


@lru_cache(maxsize=1)
def roots():
    with arcade_runtime.context() as vm:
        return json.loads(vm.eval("JSON.stringify(ArcadeExtras.packsV2.map(p=>p.root))"))


def prepare(db, player):
    row = db.execute("SELECT state FROM arcade_word_decks WHERE player=?", (player,)).fetchone()
    state = json.loads(row[0]) if row else dict(remaining=[], recent=[], cycles=0)
    catalogue = roots()
    available = set(catalogue)
    remaining = list(dict.fromkeys(w for w in state["remaining"] if w in available))
    selected = []
    while len(selected) < 5:
        if not remaining:
            remaining = catalogue.copy()
            secrets.SystemRandom().shuffle(remaining)
            avoid = set(state["recent"]) | set(selected)
            remaining = [w for w in remaining if w not in avoid] + [
                w for w in remaining if w in avoid
            ]
            state["cycles"] += 1
        candidate = remaining.pop(0)
        if candidate not in selected:
            selected.append(candidate)
    state.update(remaining=remaining, recent=selected)
    db.execute(
        "INSERT INTO arcade_word_decks VALUES(?,?) ON CONFLICT(player) "
        "DO UPDATE SET state=excluded.state",
        (player, json.dumps(state)),
    )
    return selected
