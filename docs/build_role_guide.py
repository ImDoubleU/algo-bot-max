from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "user-guide-assets"
OUTPUT = ROOT / "docs" / "Algo_MAX_Руководство_по_ролям.pptx"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
FONT = "Arial"

BG = "F7F6FA"
WHITE = "FFFFFF"
DARK = "21172F"
MUTED = "6E687D"
LINE = "DED9E8"
PURPLE = "6F35D4"
PURPLE_DARK = "3B1F68"
PURPLE_LIGHT = "EEE7FF"
YELLOW = "FFD43B"
YELLOW_LIGHT = "FFF5C9"
TEAL = "149B91"
TEAL_LIGHT = "E1F6F3"
CORAL = "D94261"
CORAL_LIGHT = "FCE7EC"


def color(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def set_background(slide, fill_color: str = BG) -> None:
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = color(fill_color)


def add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = WHITE,
    line: str | None = LINE,
    radius: bool = False,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(fill)
    if line:
        shape.line.color.rgb = color(line)
        shape.line.width = Pt(0.8)
    else:
        shape.line.fill.background()
    return shape


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 18,
    fill: str = DARK,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margin: float = 0,
    font: str = FONT,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = valign
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.alignment = align
    paragraph.space_after = Pt(0)
    paragraph.space_before = Pt(0)
    paragraph.line_spacing = 1.0
    run = paragraph.runs[0]
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color(fill)
    return box


def add_bullets(
    slide,
    items: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    fill: str = DARK,
    accent: str = PURPLE,
    gap: float = 0.47,
) -> None:
    for index, item in enumerate(items):
        item_y = y + index * gap
        dot = add_rect(slide, x, item_y + 0.08, 0.10, 0.10, fill=accent, line=None)
        dot.rotation = 45
        add_text(slide, item, x + 0.22, item_y, w - 0.22, gap, size=size, fill=fill)


def add_step(slide, number: int, title: str, description: str, x: float, y: float, w: float) -> None:
    add_rect(slide, x, y, 0.40, 0.40, fill=YELLOW, line=None, radius=True)
    add_text(
        slide,
        str(number),
        x,
        y + 0.01,
        0.40,
        0.36,
        size=15,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(slide, title, x + 0.55, y - 0.02, w - 0.55, 0.30, size=16, bold=True)
    add_text(slide, description, x + 0.55, y + 0.30, w - 0.55, 0.48, size=12.5, fill=MUTED)


def add_brand(slide, page: int, title: str, kicker: str | None = None) -> None:
    add_rect(slide, 0.45, 0.30, 0.42, 0.42, fill=PURPLE, line=None, radius=True)
    add_text(
        slide,
        "A",
        0.45,
        0.31,
        0.42,
        0.38,
        size=16,
        fill=WHITE,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(slide, "Algo MAX", 0.98, 0.33, 1.65, 0.32, size=17, bold=True)
    if kicker:
        add_text(slide, kicker.upper(), 0.48, 0.98, 4.0, 0.24, size=10, fill=PURPLE, bold=True)
        title_y = 1.20
    else:
        title_y = 0.96
    add_text(slide, title, 0.48, title_y, 12.05, 0.56, size=28, bold=True)
    add_text(slide, f"{page:02d}", 12.18, 0.34, 0.60, 0.28, size=11, fill=MUTED, align=PP_ALIGN.RIGHT)


def add_footer(slide, text: str = "Руководство пользователя · Algo MAX") -> None:
    add_rect(slide, 0.48, 7.15, 12.30, 0.01, fill=LINE, line=None)
    add_text(slide, text, 0.48, 7.22, 8.0, 0.20, size=9, fill=MUTED)


def add_screenshot(slide, filename: str, x: float, y: float, w: float, h: float, label: str) -> None:
    path = ASSETS / filename
    if not path.exists():
        raise FileNotFoundError(path)

    add_rect(slide, x, y, w, h, fill=WHITE, line=LINE)
    add_rect(slide, x, y, w, 0.35, fill=PURPLE_DARK, line=None)
    add_text(slide, label, x + 0.15, y + 0.07, w - 0.30, 0.20, size=10, fill=WHITE, bold=True)

    inner_x = Inches(x + 0.10)
    inner_y = Inches(y + 0.45)
    inner_w = Inches(w - 0.20)
    inner_h = Inches(h - 0.55)
    with Image.open(path) as image:
        image_w, image_h = image.size
    scale = min(inner_w / image_w, inner_h / image_h)
    picture_w = int(image_w * scale)
    picture_h = int(image_h * scale)
    picture_x = int(inner_x + (inner_w - picture_w) / 2)
    picture_y = int(inner_y + (inner_h - picture_h) / 2)
    slide.shapes.add_picture(str(path), picture_x, picture_y, width=picture_w, height=picture_h)


def add_callout(slide, title: str, text: str, x: float, y: float, w: float, *, kind: str = "purple") -> None:
    palettes = {
        "purple": (PURPLE_LIGHT, PURPLE, PURPLE_DARK),
        "yellow": (YELLOW_LIGHT, YELLOW, DARK),
        "teal": (TEAL_LIGHT, TEAL, DARK),
        "coral": (CORAL_LIGHT, CORAL, DARK),
    }
    background, accent, foreground = palettes[kind]
    add_rect(slide, x, y, w, 1.02, fill=background, line=None)
    add_rect(slide, x, y, 0.06, 1.02, fill=accent, line=None)
    add_text(slide, title, x + 0.22, y + 0.14, w - 0.36, 0.26, size=13, bold=True, fill=foreground)
    add_text(slide, text, x + 0.22, y + 0.46, w - 0.36, 0.42, size=11.5, fill=MUTED)


def add_role_slide(
    prs: Presentation,
    *,
    page: int,
    role: str,
    title: str,
    screenshot: str,
    bullets: list[str],
    callout_title: str,
    callout_text: str,
    callout_kind: str = "purple",
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, page, title, role)
    add_screenshot(slide, screenshot, 0.48, 1.93, 7.25, 4.92, f"Интерфейс роли: {role.lower()}")
    add_text(slide, "Что доступно", 8.10, 1.95, 4.45, 0.35, size=18, bold=True)
    add_bullets(slide, bullets, 8.12, 2.42, 4.35, 2.95, size=14.5, gap=0.58)
    add_callout(slide, callout_title, callout_text, 8.10, 5.60, 4.65, kind=callout_kind)
    add_footer(slide)


def build_presentation() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, WHITE)
    add_rect(slide, 0, 0, 5.70, 7.5, fill=PURPLE_DARK, line=None)
    add_rect(slide, 0.62, 0.62, 0.58, 0.58, fill=YELLOW, line=None, radius=True)
    add_text(slide, "A", 0.62, 0.65, 0.58, 0.48, size=22, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_text(slide, "ALGO MAX", 1.38, 0.76, 2.0, 0.32, size=18, fill=WHITE, bold=True)
    add_text(slide, "Руководство\nпользователя", 0.62, 2.08, 4.38, 1.30, size=34, fill=WHITE, bold=True)
    add_text(
        slide,
        "Основные сценарии для учеников, родителей и сотрудников школы",
        0.64,
        3.62,
        4.25,
        0.82,
        size=17,
        fill="E8DFFC",
    )
    add_rect(slide, 0.64, 5.76, 3.26, 0.48, fill=YELLOW, line=None)
    add_text(slide, "Редактируемая презентация", 0.80, 5.89, 2.95, 0.20, size=11, bold=True)
    add_text(slide, "Версия 1 · август 2026", 0.64, 6.52, 3.2, 0.25, size=11, fill="CBB9E8")
    add_rect(slide, 6.02, 0.60, 6.76, 6.30, fill=PURPLE_LIGHT, line=None)
    cover = ROOT / "app" / "web" / "static" / "miniapp" / "assets" / "dashboard-learning.png"
    slide.shapes.add_picture(str(cover), Inches(6.18), Inches(1.39), width=Inches(6.45))
    add_callout(
        slide,
        "Один сервис для всей школы",
        "Баланс и награды, магазин, заказы, ученики, рассылки и управление филиалом.",
        6.40,
        5.37,
        5.95,
        kind="teal",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 2, "Как войти и начать работу", "Общий порядок")
    add_step(slide, 1, "Откройте бота MAX", "Перейдите по персональной ссылке от школы или откройте уже подключенного бота.", 0.64, 2.00, 5.72)
    add_step(slide, 2, "Завершите привязку", "Родитель подтверждает связь с детьми. Сотрудник получает роль по приглашению школы.", 0.64, 3.04, 5.72)
    add_step(slide, 3, "Нажмите кнопку приложения", "Откроется кабинет с разделами, разрешенными для вашей роли.", 0.64, 4.08, 5.72)
    add_step(slide, 4, "Проверьте профиль", "Убедитесь, что указаны верный ребенок, город и рабочая роль.", 0.64, 5.12, 5.72)
    add_rect(slide, 6.80, 1.90, 5.90, 3.92, fill=WHITE, line=LINE)
    add_text(slide, "Навигация", 7.12, 2.18, 2.5, 0.36, size=19, bold=True)
    add_bullets(
        slide,
        [
            "На компьютере разделы находятся слева.",
            "На телефоне основные разделы расположены снизу.",
            "Остальные пункты открываются через «Еще».",
            "Раздел «Помощь» пока содержит страницу «Скоро...».",
        ],
        7.14,
        2.82,
        5.05,
        2.40,
        size=14.5,
        gap=0.58,
        accent=TEAL,
    )
    add_callout(slide, "Важно", "Не передавайте персональные ссылки и детские QR-коды посторонним.", 6.80, 5.98, 5.90, kind="yellow")
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 3, "Что доступно каждой роли", "Матрица доступа")
    roles = [
        ("Ученик", "Баланс, магазин, корзина, свои заказы и история AC", PURPLE_LIGHT, PURPLE),
        ("Родитель", "Дети, отдельные корзины, заказы, баланс и детские QR", TEAL_LIGHT, TEAL),
        ("Преподаватель", "Свои ученики, начисления, QR и выдача заказов", YELLOW_LIGHT, YELLOW),
        ("Куратор", "Ученики филиала, заказы, начисления и рассылки", CORAL_LIGHT, CORAL),
        ("Администратор", "Заказы, товары, склады, импорт, связи и сотрудники", PURPLE_LIGHT, PURPLE),
        ("Директор", "Операции филиала, сотрудники, роли и настройки", TEAL_LIGHT, TEAL),
        ("Суперадминистратор", "Все филиалы, создание партнеров и переключение города", YELLOW_LIGHT, YELLOW),
    ]
    positions = [(0.55, 1.95), (4.30, 1.95), (8.05, 1.95), (0.55, 3.55), (4.30, 3.55), (8.05, 3.55), (4.30, 5.15)]
    for (name, description, background, accent), (x, y) in zip(roles, positions, strict=True):
        add_rect(slide, x, y, 3.45, 1.25, fill=background, line=None)
        add_rect(slide, x, y, 0.07, 1.25, fill=accent, line=None)
        add_text(slide, name, x + 0.24, y + 0.18, 3.0, 0.30, size=15, bold=True)
        add_text(slide, description, x + 0.24, y + 0.57, 2.98, 0.50, size=11.5, fill=MUTED)
    add_text(slide, "Сотрудники не имеют личного счета AC и не оформляют покупки.", 0.64, 6.64, 11.90, 0.30, size=13, fill=PURPLE_DARK, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide)

    add_role_slide(
        prs,
        page=4,
        role="Ученик",
        title="Личный кабинет и баланс",
        screenshot="student-dashboard.png",
        bullets=[
            "Смотрите текущий баланс в профиле.",
            "Обновляйте баланс кнопкой рядом с суммой.",
            "Открывайте историю начислений AC.",
            "Проверяйте последние заказы на главной.",
        ],
        callout_title="Доступ только после привязки",
        callout_text="Вход ученика работает через связанную семью и персональный QR-код.",
        callout_kind="teal",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 5, "Как ученик получает награду", "Ученик")
    add_step(slide, 1, "Выберите товар", "Откройте магазин, используйте категории, поиск и фильтр наличия.", 0.62, 1.92, 5.72)
    add_step(slide, 2, "Добавьте в корзину", "Проверьте количество, стоимость и остаток AC после оформления.", 0.62, 2.94, 5.72)
    add_step(slide, 3, "Оформите заказ", "Заказ появится в статусе «Зарезервирован» и поступит сотрудникам.", 0.62, 3.96, 5.72)
    add_step(slide, 4, "Следите за статусом", "Откройте «Заказы» и дождитесь получения у преподавателя или цифрового кода.", 0.62, 4.98, 5.72)
    add_rect(slide, 6.75, 1.92, 5.95, 3.78, fill=WHITE, line=LINE)
    add_text(slide, "Что нужно помнить", 7.08, 2.20, 4.9, 0.35, size=19, bold=True)
    add_bullets(
        slide,
        [
            "Корзина относится к выбранному ребенку.",
            "Физический товар выдает сотрудник школы.",
            "Цифровой код находится внутри выполненного заказа.",
            "По вопросам заказа обратитесь к администратору.",
        ],
        7.10,
        2.83,
        5.05,
        2.55,
        size=14.5,
        gap=0.58,
        accent=TEAL,
    )
    add_callout(slide, "Статусы обновляются автоматически", "После действий сотрудников достаточно обновить раздел заказов.", 6.75, 5.92, 5.95, kind="yellow")
    add_footer(slide)

    add_role_slide(
        prs,
        page=6,
        role="Родитель",
        title="Семейный кабинет",
        screenshot="parent-dashboard.png",
        bullets=[
            "Переключайтесь между связанными детьми.",
            "Смотрите баланс и историю каждого ребенка.",
            "Оформляйте отдельные заказы для выбранного ребенка.",
            "Следите за заказами всей семьи.",
        ],
        callout_title="Корзины не смешиваются",
        callout_text="Выбор ребенка определяет баланс, корзину, историю и получателя заказа.",
        callout_kind="yellow",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 7, "Как дать ребенку доступ", "Родитель")
    add_step(slide, 1, "Выберите ребенка", "На главной странице нажмите имя нужного ребенка.", 0.62, 1.92, 5.74)
    add_step(slide, 2, "Раскройте его QR-код", "Каждый код привязывает только один детский профиль.", 0.62, 2.96, 5.74)
    add_step(slide, 3, "Покажите код ребенку", "Ребенок сканирует его с другого устройства и открывает бота.", 0.62, 4.00, 5.74)
    add_step(slide, 4, "Проверьте профиль", "После входа ребенок видит только свои баланс, корзину и заказы.", 0.62, 5.04, 5.74)
    add_rect(slide, 6.78, 1.92, 5.90, 2.20, fill=TEAL_LIGHT, line=None)
    add_text(slide, "В QR-коде есть персональная ссылка", 7.10, 2.22, 5.20, 0.35, size=18, bold=True)
    add_text(slide, "Ее можно скопировать или сохранить QR-код как изображение для ребенка.", 7.10, 2.80, 5.00, 0.72, size=15, fill=MUTED)
    add_rect(slide, 6.78, 4.42, 5.90, 1.35, fill=CORAL_LIGHT, line=None)
    add_text(slide, "Не пересылайте код посторонним", 7.10, 4.72, 5.00, 0.30, size=17, bold=True, fill=CORAL)
    add_text(slide, "Если связь отозвана, доступ ребенка прекращается.", 7.10, 5.16, 5.00, 0.32, size=13, fill=MUTED)
    add_callout(slide, "Если QR не открывается", "Обновите страницу и убедитесь, что родительская связь еще активна.", 6.78, 5.98, 5.90, kind="purple")
    add_footer(slide)

    add_role_slide(
        prs,
        page=8,
        role="Преподаватель",
        title="Ученики, QR-коды и начисления",
        screenshot="teacher-dashboard.png",
        bullets=[
            "Видит только свои группы и учеников.",
            "Показывает ученикам персональные QR-коды.",
            "Выбирает учеников и начисляет AC.",
            "Открывает историю учеников своих групп.",
        ],
        callout_title="Массовое начисление",
        callout_text="Отметьте учеников, выберите причину и сумму, затем подтвердите одну операцию.",
        callout_kind="yellow",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 9, "Получение и выдача заказов", "Преподаватель")
    add_rect(slide, 0.62, 1.90, 5.95, 4.80, fill=WHITE, line=LINE)
    add_text(slide, "Что видит преподаватель", 0.95, 2.20, 5.20, 0.38, size=19, bold=True)
    add_bullets(
        slide,
        [
            "Только заказы своих учеников.",
            "Какие товары и в каком количестве переданы.",
            "Площадку и сведения, необходимые для выдачи.",
            "Кнопку подтверждения получения заказа.",
            "Кнопку передачи заказа ученику.",
        ],
        0.98,
        2.85,
        5.00,
        3.20,
        size=15,
        gap=0.58,
        accent=TEAL,
    )
    add_step(slide, 1, "Получите комплект", "Сверьте список с фактически переданными товарами.", 7.00, 2.02, 5.22)
    add_step(slide, 2, "Подтвердите получение", "Заказ перейдет в статус «Учитель получил заказ».", 7.00, 3.14, 5.22)
    add_step(slide, 3, "Передайте ребенку", "После фактической выдачи отметьте заказ как полученный.", 7.00, 4.26, 5.22)
    add_callout(slide, "Не подтверждайте заранее", "Статус должен соответствовать фактическому движению товара.", 6.83, 5.80, 5.85, kind="coral")
    add_footer(slide)

    add_role_slide(
        prs,
        page=10,
        role="Куратор",
        title="Координация филиала и рассылки",
        screenshot="curator-broadcasts.png",
        bullets=[
            "Работает с учениками доступного филиала.",
            "Просматривает заказы и начисления.",
            "Фильтрует получателей по формату и площадке.",
            "Создает новости с текстом и изображением.",
        ],
        callout_title="Проверка перед отправкой",
        callout_text="Сначала выберите аудиторию, затем заполните новость и проверьте итоговый вид.",
        callout_kind="teal",
    )

    add_role_slide(
        prs,
        page=11,
        role="Администратор",
        title="Заказы и движение товаров",
        screenshot="admin-orders.png",
        bullets=[
            "Назначает склад зарезервированным заказам.",
            "Собирает товары по общему чек-листу.",
            "Распределяет заказы по площадкам и педагогам.",
            "Обновляет статусы после фактических действий.",
        ],
        callout_title="Отмена заказа",
        callout_text="Администратор выбирает причину отмены; списанные AC возвращаются ученику.",
        callout_kind="coral",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 12, "Ежедневное управление филиалом", "Администратор")
    columns = [
        ("Ученики", "Поиск, карточка, статус, дата рождения, баланс и история изменений", PURPLE_LIGHT, PURPLE),
        ("Товары", "Создание товара, фотография, цена, коды автовыдачи и остатки по складам", TEAL_LIGHT, TEAL),
        ("Склады", "Название, адрес или примечание, остатки и основной склад сотрудника", YELLOW_LIGHT, YELLOW),
        ("Импорт", "Загрузка подготовленного XLSX и просмотр результата обработки", CORAL_LIGHT, CORAL),
        ("Связи", "Контроль привязок родителей, учеников и сотрудников к MAX", PURPLE_LIGHT, PURPLE),
        ("Сотрудники", "Роли, отзыв доступа и персональные настройки уведомлений", TEAL_LIGHT, TEAL),
    ]
    positions = [(0.62, 1.92), (4.46, 1.92), (8.30, 1.92), (0.62, 4.12), (4.46, 4.12), (8.30, 4.12)]
    for (title, description, background, accent), (x, y) in zip(columns, positions, strict=True):
        add_rect(slide, x, y, 3.43, 1.72, fill=background, line=None)
        add_rect(slide, x, y, 0.07, 1.72, fill=accent, line=None)
        add_text(slide, title, x + 0.25, y + 0.22, 2.90, 0.32, size=17, bold=True)
        add_text(slide, description, x + 0.25, y + 0.70, 2.88, 0.76, size=12.5, fill=MUTED)
    add_callout(slide, "Порядок действий", "Сначала обновите данные, затем выполняйте операции и проверяйте историю.", 3.70, 6.14, 5.93, kind="yellow")
    add_footer(slide)

    add_role_slide(
        prs,
        page=13,
        role="Директор",
        title="Контроль филиала и сотрудников",
        screenshot="director-management.png",
        bullets=[
            "Видит операционную сводку своих филиалов.",
            "Контролирует заказы, товары, склады и низкие остатки.",
            "Выдает и отзывает роли сотрудников.",
            "Настраивает уведомления и параметры доступа учеников.",
        ],
        callout_title="Область ответственности",
        callout_text="Директор работает только с назначенными ему городами, филиалами и сотрудниками.",
        callout_kind="teal",
    )

    add_role_slide(
        prs,
        page=14,
        role="Суперадминистратор",
        title="Партнеры, города и общий контроль",
        screenshot="superadmin-management.png",
        bullets=[
            "Создает новых партнеров и города.",
            "Переключает рабочий филиал в верхней панели.",
            "Выполняет все административные операции.",
            "Контролирует изоляцию данных между партнерами.",
        ],
        callout_title="Перед любым изменением",
        callout_text="Проверьте выбранный город: действия применяются к текущему рабочему филиалу.",
        callout_kind="coral",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 15, "Жизненный цикл заказа", "Общий процесс")
    statuses = [
        ("1", "Зарезервирован", "Заказ создан, склад еще не подтвержден", PURPLE_LIGHT, PURPLE),
        ("2", "Ожидает доставки", "Склад назначен, товар собирают и везут", YELLOW_LIGHT, YELLOW),
        ("3", "Доставлен на площадку", "Комплект находится на площадке", TEAL_LIGHT, TEAL),
        ("4", "Учитель получил заказ", "Преподаватель принял комплект", CORAL_LIGHT, CORAL),
        ("5", "Получен", "Заказ фактически передан ученику", TEAL_LIGHT, TEAL),
    ]
    for index, (number, status, description, background, accent) in enumerate(statuses):
        x = 0.48 + index * 2.55
        add_rect(slide, x, 2.06, 2.25, 2.70, fill=background, line=None)
        add_rect(slide, x + 0.18, 2.26, 0.46, 0.46, fill=accent, line=None, radius=True)
        add_text(slide, number, x + 0.18, 2.32, 0.46, 0.28, size=14, fill=WHITE if accent != YELLOW else DARK, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, status, x + 0.18, 2.96, 1.88, 0.62, size=16, bold=True)
        add_text(slide, description, x + 0.18, 3.72, 1.88, 0.76, size=11.5, fill=MUTED)
        if index < len(statuses) - 1:
            add_text(slide, "→", x + 2.28, 3.03, 0.24, 0.36, size=20, fill=MUTED, bold=True, align=PP_ALIGN.CENTER)
    add_callout(slide, "Статус меняют после фактического действия", "Так родители, ученики и сотрудники видят одинаковую картину движения заказа.", 0.80, 5.28, 5.80, kind="yellow")
    add_callout(slide, "Отмену оформляют сотрудники", "Администратор, директор или суперадминистратор указывает причину и возвращает AC.", 6.75, 5.28, 5.80, kind="coral")
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 16, "Если что-то не получается", "Быстрая проверка")
    fixes = [
        ("Не открывается приложение", "Вернитесь в чат с ботом и снова нажмите кнопку приложения."),
        ("Показана неверная роль", "Закройте приложение, откройте заново и обратитесь к директору или администратору."),
        ("Не обновился баланс или статус", "Нажмите кнопку обновления рядом с балансом или в нужном разделе."),
        ("Не виден ученик или группа", "Проверьте выбранный город, роль и актуальность связи ученика с группой."),
        ("QR-код больше не работает", "Попросите родителя открыть кабинет и получить актуальный код ребенка."),
        ("Ошибка повторяется", "Сделайте снимок экрана и укажите роль, раздел и выполненное действие."),
    ]
    positions = [(0.62, 1.92), (6.72, 1.92), (0.62, 3.30), (6.72, 3.30), (0.62, 4.68), (6.72, 4.68)]
    kinds = [(PURPLE_LIGHT, PURPLE), (TEAL_LIGHT, TEAL), (YELLOW_LIGHT, YELLOW), (CORAL_LIGHT, CORAL), (TEAL_LIGHT, TEAL), (PURPLE_LIGHT, PURPLE)]
    for (title, description), (x, y), (background, accent) in zip(fixes, positions, kinds, strict=True):
        add_rect(slide, x, y, 5.58, 1.08, fill=background, line=None)
        add_rect(slide, x, y, 0.06, 1.08, fill=accent, line=None)
        add_text(slide, title, x + 0.23, y + 0.14, 5.02, 0.27, size=14.5, bold=True)
        add_text(slide, description, x + 0.23, y + 0.50, 5.02, 0.42, size=11.5, fill=MUTED)
    add_text(slide, "Раздел «Помощь» внутри приложения пока готовится.", 0.62, 6.38, 12.05, 0.32, size=13, fill=PURPLE_DARK, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide)

    return prs


def main() -> None:
    presentation = build_presentation()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(OUTPUT)
    print(f"Created {OUTPUT} ({len(presentation.slides)} slides)")


if __name__ == "__main__":
    main()
