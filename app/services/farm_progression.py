"""Persistent progression content for the local farm; uses its existing transaction ledger."""

import math

from app.services.arcade import ArcadeError

LATE_ITEMS = [
    dict(
        id="vineyard",
        name="Виноградник",
        category="garden",
        icon="orchard",
        price=600000,
        growth=1.7,
        unlock=20,
        maximum=20,
        base=350000,
        seeds=1,
        materials=2,
        text="Новый урожай для большой фермы. Для каждого уровня нужны семена и материалы",
    ),
    dict(
        id="autoshovel",
        name="Механическая лопата",
        category="tools",
        icon="shovel",
        price=2500000,
        growth=1.7,
        unlock=24,
        maximum=15,
        seeds=2,
        materials=3,
        text="Добавляет 120 к основе ручного сбора за уровень",
    ),
    dict(
        id="balloon",
        name="Аэростат",
        category="garden",
        icon="balloon",
        price=1800000,
        growth=1.7,
        unlock=24,
        maximum=15,
        base=280000,
        seeds=2,
        materials=4,
        text="Открывает экспедиции к небесным островам",
    ),
    dict(
        id="orangery",
        name="Оранжерея",
        category="garden",
        icon="greenhouse",
        price=9000000,
        growth=1.75,
        unlock=28,
        maximum=20,
        base=1200000,
        seeds=3,
        materials=5,
        text="Редкие растения и большой постоянный урожай",
    ),
    dict(
        id="foundry",
        name="Ремесленный цех",
        category="business",
        icon="workshop",
        price=25000000,
        growth=1.75,
        unlock=32,
        maximum=10,
        seeds=3,
        materials=8,
        text="Каждый уровень добавляет материал к награде за испытание",
    ),
    dict(
        id="highland",
        name="Горная ферма",
        category="garden",
        icon="highland",
        price=70000000,
        growth=1.8,
        unlock=36,
        maximum=20,
        base=4000000,
        seeds=5,
        materials=10,
        text="Новые земли высоко над долиной",
    ),
    dict(
        id="exosuit",
        name="Экзоскелет фермера",
        category="tools",
        icon="exosuit",
        price=180000000,
        growth=1.8,
        unlock=40,
        maximum=15,
        seeds=6,
        materials=12,
        text="Добавляет 350 к основе ручного сбора за уровень",
    ),
    dict(
        id="lighthouse",
        name="Маяк долины",
        category="business",
        icon="lighthouse",
        price=900000000,
        growth=1.8,
        unlock=48,
        maximum=10,
        seeds=10,
        materials=20,
        text="Каждый уровень добавляет материал к награде за экспедицию",
    ),
]
CROPS = [
    dict(id="radish", name="Быстрый сорт", unlock=3, seconds=600, cost=100, energy=20, seeds=1),
    dict(
        id="amber", name="Янтарная морковь", unlock=10, seconds=2700, cost=1000, energy=50, seeds=4
    ),
    dict(id="moon", name="Лунный сорт", unlock=30, seconds=10800, cost=10000, energy=100, seeds=10),
]
ROUTES = [
    dict(
        id="forest",
        name="Лесная тропа",
        unlock=8,
        seconds=1200,
        cost=500,
        energy=100,
        seeds=0,
        materials=3,
    ),
    dict(
        id="coast",
        name="Дальний берег",
        unlock=16,
        seconds=3600,
        cost=3000,
        energy=200,
        seeds=1,
        materials=12,
    ),
    dict(
        id="sky",
        name="Небесные острова",
        unlock=24,
        seconds=10800,
        cost=20000,
        energy=400,
        seeds=2,
        materials=36,
        requires_item="balloon",
    ),
]
RESEARCH = [
    dict(
        id="garden_notes",
        name="Записки садовода",
        unlock=12,
        maximum=3,
        seeds=2,
        materials=3,
        cost=2500,
        text="+0,1 энергии в секунду за уровень",
    ),
    dict(
        id="seed_sorting",
        name="Отбор семян",
        unlock=12,
        maximum=3,
        seeds=3,
        materials=5,
        cost=5000,
        requires="garden_notes",
        requires_level=1,
        text="+1 семя с редкой грядки за уровень",
    ),
    dict(
        id="trail_maps",
        name="Карты долины",
        unlock=16,
        maximum=3,
        seeds=4,
        materials=8,
        cost=12000,
        requires="seed_sorting",
        requires_level=1,
        text="Экспедиции на 5% короче за уровень",
    ),
    dict(
        id="soil_calendar",
        name="Календарь урожая",
        unlock=20,
        maximum=3,
        seeds=6,
        materials=12,
        cost=35000,
        requires="garden_notes",
        requires_level=2,
        text="+2 часа накопления без захода за уровень",
    ),
    dict(
        id="challenge_training",
        name="Тренировка команды",
        unlock=26,
        maximum=3,
        seeds=8,
        materials=18,
        cost=100000,
        requires="trail_maps",
        requires_level=2,
        text="+15 секунд на испытание за уровень",
    ),
]
TRIALS = [
    dict(
        id="harvest",
        name="Урожайный рывок",
        unlock=18,
        goal=240,
        seconds=120,
        seeds=1,
        reward_seeds=3,
        reward_materials=4,
    ),
    dict(
        id="master",
        name="Мастер огорода",
        unlock=30,
        goal=500,
        seconds=180,
        seeds=2,
        reward_seeds=6,
        reward_materials=9,
    ),
    dict(
        id="legend",
        name="Легенда урожая",
        unlock=42,
        goal=900,
        seconds=240,
        seeds=4,
        reward_seeds=12,
        reward_materials=18,
    ),
]
UNLOCKS = {
    3: ["Редкая грядка"],
    5: ["Уход за грядкой"],
    8: ["Экспедиции"],
    12: ["Исследования"],
    16: ["Дальний берег"],
    18: ["Испытания"],
    24: ["Небесные острова"],
    30: ["Лунный сорт", "Испытание мастера"],
    42: ["Легендарное испытание"],
}
PROGRESSION_ACTIONS = {
    "start_plot",
    "water_plot",
    "start_expedition",
    "research",
    "start_trial",
    "claim_project",
    "claim_trial",
    "dismiss_trial",
}
CATEGORY_SPECS = [
    (
        "harvest",
        "Урожай",
        ("earned", "passive"),
        14,
        "earned",
        [50, 250, 2500, 50000, 500000, 5000000, 50000000, 5000000000],
        [
            "Первый росток",
            "Полная корзинка",
            "Сладкая морковь",
            "Урожайный сезон",
            "Золотая осень",
            "Щедрая земля",
            "Морковное море",
            "Бескрайние поля",
        ],
    ),
    (
        "manual",
        "Мастерство",
        ("taps",),
        12,
        "taps",
        [20, 100, 250, 1000, 5000, 20000, 100000, 500000],
        [
            "Первые шаги",
            "Ловкие лапы",
            "В ритме огорода",
            "Верная лопата",
            "Без передышки",
            "Руки мастера",
            "Рекордный труд",
            "Неутомимый Копатыч",
        ],
    ),
    (
        "building",
        "Строительство",
        ("upgrades", "variety"),
        14,
        "upgrades",
        [1, 3, 5, 20, 50, 100, 250],
        [
            "Первая покупка",
            "Начало хозяйства",
            "На вырост",
            "Свой участок",
            "Усадьба",
            "Размах строительства",
            "Великая стройка",
        ],
    ),
    (
        "neighbors",
        "Соседи",
        ("deliveries",),
        10,
        "deliveries",
        [3, 5, 15, 25, 75, 150, 300],
        [
            "Знакомство",
            "Свои люди",
            "Добрые дела",
            "Огород для друзей",
            "Нужен всей долине",
            "Почётный сосед",
            "Друзья навсегда",
        ],
    ),
    (
        "care",
        "Забота",
        ("best_streak",),
        8,
        "best_streak",
        [3, 5, 14, 21, 60, 100],
        [
            "Три добрых дня",
            "Заботливый хозяин",
            "Две недели вместе",
            "Привычка растить",
            "Долгая дружба",
            "Сто рассветов",
        ],
    ),
    (
        "rare",
        "Редкий огород",
        ("plots",),
        12,
        "plots",
        [1, 2, 3, 5, 10, 20, 35, 50, 75, 100, 150, 250],
        [
            "Необычный росток",
            "Вторая грядка",
            "Три редких сорта",
            "Любопытный садовод",
            "Собиратель семян",
            "Редкая коллекция",
            "Селекционер",
            "Заповедный огород",
            "Драгоценный урожай",
            "Сотня открытий",
            "Хранитель сортов",
            "Сокровища земли",
        ],
    ),
    (
        "expeditions",
        "Экспедиции",
        ("expeditions",),
        10,
        "expeditions",
        [1, 3, 5, 10, 20, 35, 50, 75, 120, 200],
        [
            "За калитку",
            "Новые тропы",
            "Лесной следопыт",
            "Дальний путь",
            "Карта долины",
            "Полный рюкзак",
            "Проводник",
            "За горизонт",
            "Открыватель земель",
            "Легенда дорог",
        ],
    ),
    (
        "research",
        "Наука",
        ("research",),
        10,
        "research",
        [1, 2, 3, 4, 5, 7, 9, 11, 13, 15],
        [
            "Первая заметка",
            "Верная гипотеза",
            "Опытный садовод",
            "Первые открытия",
            "Своя лаборатория",
            "Научный подход",
            "Новые методы",
            "Большое открытие",
            "Учёный долины",
            "Энциклопедия фермы",
        ],
    ),
    (
        "trials",
        "Испытания",
        ("trials",),
        10,
        "trials",
        [1, 2, 3, 5, 8, 12, 20, 35, 50, 100],
        [
            "Первый финиш",
            "Точно в срок",
            "Уверенный темп",
            "Крепкие нервы",
            "Урожайный азарт",
            "Настоящий мастер",
            "Сильнее вчера",
            "Воля к победе",
            "Чемпион долины",
            "Легендарный результат",
        ],
    ),
]
METRIC_LABELS = {
    "earned": "Выращено морковок",
    "passive": "Выросло само",
    "taps": "Нажатия",
    "upgrades": "Уровни улучшений",
    "variety": "Разных улучшений",
    "deliveries": "Доставки",
    "best_streak": "Дней подряд",
    "plots": "Редкие урожаи",
    "expeditions": "Экспедиции",
    "research": "Исследования",
    "trials": "Испытания",
}


def build_badges(legacy):
    badges = list(legacy)
    meta = {}
    categories = []
    for category, name, metrics, total, metric, targets, titles in CATEGORY_SPECS:
        existing = [b for b in badges if b[2] in metrics]
        seen = {(b[2], b[3]) for b in existing}
        needed = total - len(existing)
        added = 0
        for target, title in zip(targets, titles, strict=True):
            if added >= needed:
                break
            if (metric, target) in seen:
                continue
            reward = max(40, min(1000000, round((added + 1) ** 2 * 60)))
            key = f"{category}_milestone_{target}"
            badges.append((key, title, metric, target, reward))
            added += 1
        assert added == needed
        rows = sorted(
            [b for b in badges if b[2] in metrics], key=lambda b: (b[2] != "earned", b[3])
        )
        for b in rows:
            thresholds = {
                "earned": [1000, 50000, 1000000, 100000000],
                "passive": [5000, 100000, 1000000, 100000000],
                "taps": [250, 2500, 20000, 100000],
                "upgrades": [5, 30, 100, 250],
                "variety": [3, 6, 12, 25],
                "deliveries": [5, 15, 50, 150],
                "best_streak": [5, 14, 30, 60],
                "plots": [3, 10, 35, 100],
                "expeditions": [3, 10, 35, 100],
                "research": [3, 5, 9, 13],
                "trials": [3, 8, 20, 50],
            }
            tier = sum(b[3] >= threshold for threshold in thresholds[b[2]])
            unlock = {"plots": 3, "expeditions": 8, "research": 12, "trials": 18}.get(b[2], 1)
            meta[b[0]] = dict(
                category=category,
                tier=tier,
                unlock=unlock,
                income_minutes=(2, 5, 10, 20, 30)[tier],
                seed_reward={
                    "rare": (1, 2, 4, 7, 12),
                    "research": (1, 1, 2, 3, 5),
                    "trials": (1, 2, 3, 5, 8),
                    "expeditions": (0, 0, 1, 2, 3),
                }.get(category, (0, 0, 1, 2, 4))[tier],
                material_reward={
                    "expeditions": (1, 3, 6, 10, 18),
                    "research": (1, 2, 3, 5, 8),
                    "trials": (1, 3, 5, 8, 12),
                    "rare": (0, 0, 1, 2, 4),
                }.get(category, (0, 0, 1, 3, 6))[tier],
            )
        categories.append(dict(id=category, name=name, total=total))
    assert len(badges) == 100
    # Milestone floors complement the income-based prize, including early farms.
    badges = [
        (
            key,
            name,
            metric,
            target,
            max(
                reward,
                (60, 300, 2500, 25000, 250000)[meta[key]["tier"]],
                target * 3 // 100 if metric in ("earned", "passive") else 0,
            ),
        )
        for key, name, metric, target, reward in badges
    ]
    return badges, meta, categories


class ProgressionMixin:
    def _progress_defaults(self, state):
        state.setdefault("resources", dict(seeds=0, materials=0))
        state.setdefault("projects", dict(plot=None, expedition=None))
        state.setdefault("research", {r["id"]: 0 for r in RESEARCH})
        state.setdefault(
            "activity_counts", dict(plots=0, watering=0, expeditions=0, research=0, trials=0)
        )
        state.setdefault("trial", None)
        state.setdefault("trial_after", 0)
        return state

    def _pay_resources(self, state, cost):
        if state["balance"] < cost.get("cost", 0):
            raise ArcadeError("Пока не хватает морковок.")
        for key, label in [("seeds", "семян"), ("materials", "материалов")]:
            if state["resources"][key] < cost.get(key, 0):
                raise ArcadeError(f"Не хватает {label}. Загляни в раздел «Дела».")
        state["balance"] -= cost.get("cost", 0)
        for key in ("seeds", "materials"):
            state["resources"][key] -= cost.get(key, 0)

    def _progress_snapshot(self, state, lv):
        research = state["research"]
        now = state["last_ms"]
        plots = [{**c, "seeds": c["seeds"] + research["seed_sorting"]} for c in CROPS]
        routes = [
            {
                **r,
                "seconds": math.ceil(r["seconds"] * (100 - 5 * research["trail_maps"]) / 100),
                "materials": r["materials"] + state["items"].get("lighthouse", 0),
            }
            for r in ROUTES
        ]
        nodes = []
        for r in RESEARCH:
            n = research[r["id"]]
            cost = {k: r[k] * (n + 1) for k in ("cost", "seeds", "materials")}
            locked = lv < r["unlock"] or research.get(r.get("requires"), 0) < r.get(
                "requires_level", 0
            )
            nodes.append({**r, **cost, "level": n, "locked": locked, "maxed": n >= r["maximum"]})
        trials = [
            {
                **t,
                "seconds": t["seconds"] + 15 * research["challenge_training"],
                "reward_materials": t["reward_materials"] + state["items"].get("foundry", 0),
            }
            for t in TRIALS
        ]
        return dict(
            resources=state["resources"],
            projects=state["projects"],
            research=nodes,
            crops=plots,
            routes=routes,
            trials=trials,
            trial=state["trial"],
            trial_wait=max(0, math.ceil((state["trial_after"] - now) / 1000)),
            counts=state["activity_counts"],
        )

    def _progress_rewards(self, state):
        rewards = []
        now = state["last_ms"]
        for kind, p in state["projects"].items():
            if p and now >= p["finish_at"]:
                rewards.append(
                    dict(
                        kind=kind,
                        id=p["project_id"],
                        amount=0,
                        seeds=p.get("reward_seeds", 0),
                        materials=p.get("reward_materials", 0),
                    )
                )
        t = state["trial"]
        if t and t["progress"] >= t["goal"]:
            rewards.append(
                dict(
                    kind="trial",
                    id=t["project_id"],
                    amount=0,
                    seeds=t["reward_seeds"],
                    materials=t["reward_materials"],
                )
            )
        return rewards

    def _progress_collect(self, state, reward):
        kind = reward["kind"]
        if kind in ("plot", "expedition"):
            state["projects"][kind] = None
            state["activity_counts"]["plots" if kind == "plot" else "expeditions"] += 1
        elif kind == "trial":
            state["trial"] = None
            state["activity_counts"]["trials"] += 1
            state["trial_after"] = max(state["trial_after"], state["last_ms"] + 86400000)
        for key in ("seeds", "materials"):
            state["resources"][key] += reward.get(key, 0)

    def _progress_act(self, db, player, state, action, item, token, lv, result):
        now = state["last_ms"]
        v = self._progress_snapshot(state, lv)
        if action in ("start_plot", "start_expedition"):
            kind = "plot" if action == "start_plot" else "expedition"
            choices = v["crops"] if kind == "plot" else v["routes"]
            definition = next((r for r in choices if r["id"] == item), None)
            if not definition or lv < definition["unlock"]:
                raise ArcadeError("Это дело откроется на следующем этапе развития.")
            if state["projects"][kind]:
                raise ArcadeError("Сначала забери результат текущего дела.")
            if definition.get("requires_item") and not state["items"][definition["requires_item"]]:
                raise ArcadeError("Сначала построй аэростат.")
            energy = definition["energy"] * 1000
            if state["energy_milli"] < energy:
                raise ArcadeError("Нужно больше энергии. Дай Копатычу отдохнуть.")
            payment = {
                **definition,
                "seeds": 0 if kind == "plot" else definition["seeds"],
                "materials": 0,
            }
            self._pay_resources(state, payment)
            state["energy_milli"] -= energy
            state["projects"][kind] = {
                **definition,
                "project_id": token,
                "started_at": now,
                "finish_at": now + definition["seconds"] * 1000,
                "watered": False,
                "reward_seeds": definition["seeds"] if kind == "plot" else 0,
                "reward_materials": definition["materials"] if kind == "expedition" else 0,
            }
            result["amount"] = -definition["cost"]
        elif action == "water_plot":
            p = state["projects"]["plot"]
            if lv < 5 or not p or item != p["project_id"] or p["watered"] or now >= p["finish_at"]:
                raise ArcadeError("Полив сейчас недоступен.")
            if state["energy_milli"] < 50000:
                raise ArcadeError("Для полива нужно 50 энергии.")
            state["energy_milli"] -= 50000
            p["watered"] = True
            p["finish_at"] = max(now, p["finish_at"] - p["seconds"] * 200)
            state["activity_counts"]["watering"] += 1
        elif action == "research":
            r = next((r for r in v["research"] if r["id"] == item), None)
            if not r or r["locked"] or r["maxed"]:
                raise ArcadeError("Исследование ещё не открыто или уже завершено.")
            self._pay_resources(state, r)
            state["research"][item] += 1
            state["activity_counts"]["research"] += 1
            result["amount"] = -r["cost"]
        elif action == "start_trial":
            t = next((t for t in v["trials"] if t["id"] == item), None)
            if not t or lv < t["unlock"]:
                raise ArcadeError("Это испытание пока не открыто.")
            if state["trial"] or now < state["trial_after"]:
                raise ArcadeError("Заверши текущее испытание или дождись следующей попытки.")
            self._pay_resources(state, dict(seeds=t["seeds"]))
            state["trial"] = {
                **t,
                "project_id": token,
                "progress": 0,
                "started_at": now,
                "finish_at": now + t["seconds"] * 1000,
            }
            state["trial_after"] = now + 1800000
        elif action == "dismiss_trial":
            t = state["trial"]
            if (
                not t
                or item != t["project_id"]
                or now < t["finish_at"]
                or t["progress"] >= t["goal"]
            ):
                raise ArcadeError("Испытание ещё не окончено.")
            state["trial"] = None
        else:
            raise ArcadeError("Неизвестное дело.")
        self._event(db, player, action, result["amount"], item or "")
