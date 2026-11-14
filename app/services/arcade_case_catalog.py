"""Stable cosmetic catalogue. Old item IDs stay valid across catalogue expansions."""

COLLECTIONS = [
    ("scout", "Первая экспедиция", "Полевой", "#dc995d"),
    ("neon", "Неоновый сектор", "Неоновый", "#38d6ce"),
    ("relic", "За горизонтом", "Древний", "#b391ef"),
    ("ocean", "Глубины океана", "Глубинный", "#349ace"),
    ("ember", "Сердце вулкана", "Огненный", "#f17b49"),
    ("frost", "Ледяная луна", "Полярный", "#8cdbe8"),
    ("forest", "Живая планета", "Лесной", "#79b45c"),
    ("solar", "Солнечная кузница", "Солнечный", "#e9bc43"),
    ("void", "Тёмная материя", "Теневой", "#8171ce"),
    ("candy", "Конфетная орбита", "Сахарный", "#f299bf"),
    ("storm", "Грозовой фронт", "Грозовой", "#669ae9"),
    ("desert", "Пески времени", "Песчаный", "#d6b579"),
    ("copper", "Медный город", "Медный", "#bf7c55"),
    ("crystal", "Кристальные пещеры", "Кристальный", "#94a9f2"),
    ("coral", "Коралловый риф", "Коралловый", "#f08978"),
    ("moon", "Лунный архив", "Лунный", "#a8b5c7"),
    ("toxic", "Зелёная аномалия", "Изотопный", "#b5cf4f"),
    ("royal", "Королевская станция", "Императорский", "#c185d6"),
    ("pixel", "Цифровой мир", "Цифровой", "#51baa5"),
    ("aurora", "Северное сияние", "Сияющий", "#61ccac"),
]
QUALITIES = [
    dict(id="standard", name="Стандарт", color="#c1c8cf"),
    dict(id="polished", name="Полированный", color="#8cdaea"),
    dict(id="engraved", name="С гравировкой", color="#c9abe9"),
    dict(id="holographic", name="Голографический", color="#77e0be"),
    dict(id="collector", name="Коллекционный", color="#edc776"),
]


def catalogue(base):
    return [
        dict(
            id=key if n == 0 else f"{collection}_{key}",
            name=name if n == 0 else f"{name} · {title}",
            rarity=rarity,
            collection=collection,
            quality=QUALITIES[(n + index // 4) % len(QUALITIES)]["id"],
            art=key,
            color=color,
        )
        for n, (collection, title, _, color) in enumerate(COLLECTIONS)
        for index, (key, name, rarity) in enumerate(base)
    ]


def cases():
    result = []
    for n, (key, title, _, color) in enumerate(COLLECTIONS):
        result.append(
            dict(
                id=key,
                name=title,
                subtitle="20 находок в коллекции",
                collection=key,
                unlock=[0, 6, 12][n] if n < 3 else min(80, 8 + (n - 3) * 4),
                price=[50, 100, 180][n] if n < 3 else 70 + (n % 6) * 20,
                weights=[[60, 27, 10, 3], [40, 35, 20, 5], [25, 35, 30, 10]][min(2, n % 3)],
                color=color,
            )
        )
    return result
