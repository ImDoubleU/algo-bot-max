"""Permanent mastery is derived from unique verified accomplishments, never playtime."""

LEAGUES = ((0, "Бронза"), (200, "Серебро"), (450, "Золото"), (800, "Алмаз"), (1200, "Космос"))
TITLES = (
    (1, 0, "Новичок"),
    (5, 3, "Исследователь"),
    (12, 6, "Практик"),
    (22, 10, "Специалист"),
    (35, 12, "Мастер"),
    (45, 12, "Легенда"),
)


def league(score, games):
    if games < 3:
        return dict(name="Квалификация", tier=-1, next=0, remainingGames=3 - games)
    tier = max(i for i, (threshold, _) in enumerate(LEAGUES) if score >= threshold)
    return dict(
        name=LEAGUES[tier][1],
        tier=tier,
        next=LEAGUES[tier + 1][0] if tier < len(LEAGUES) - 1 else None,
        remainingGames=0,
    )


def mastery(journeys, badges):
    games = {}
    for game in dict.fromkeys([*journeys, *(b["game"] for b in badges)]):
        saved = journeys.get(game, {})
        cleared, stars = saved.get("cleared", 0), saved.get("stars", 0)
        medals = [b for b in badges if b["game"] == game and b["unlocked"]]
        xp = (
            cleared * 100
            + max(0, stars - cleared) * 25
            + sum((b["tier"] + 1) * 100 for b in medals)
        )
        games[game] = dict(
            xp=xp,
            cleared=cleared,
            stars=stars,
            medals=len(medals),
            chapter=min(6, cleared // 4 + 1),
        )
    xp = sum(g["xp"] for g in games.values())
    breadth = sum(g["cleared"] >= 4 or g["medals"] > 0 for g in games.values())
    level, floor = 1, 0
    while level < 50 and xp >= floor + 200 + (level - 1) * 40:
        floor += 200 + (level - 1) * 40
        level += 1
    title_index = max(
        i for i, (required, count, _) in enumerate(TITLES) if level >= required and breadth >= count
    )
    next_title = TITLES[title_index + 1] if title_index + 1 < len(TITLES) else None
    return dict(
        level=level,
        xp=xp,
        floor=floor,
        next=floor + 200 + (level - 1) * 40 if level < 50 else None,
        title=TITLES[title_index][2],
        titleTier=title_index,
        breadth=breadth,
        nextTitle=dict(level=next_title[0], games=next_title[1], name=next_title[2])
        if next_title
        else None,
        games=games,
    )
