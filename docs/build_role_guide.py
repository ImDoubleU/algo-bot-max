from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from interaction_scenarios import SCENARIOS, InteractionScenario, write_markdown


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "user-guide-assets"
OUTPUT = ROOT / "docs" / "Algo_MAX_Руководство_по_ролям.pptx"
INTERACTION_GUIDE_OUTPUT = ROOT / "docs" / "INTERACTION_GUIDE_RU.md"

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
    frame.paragraphs[0].text = text
    for paragraph in frame.paragraphs:
        paragraph.alignment = align
        paragraph.space_after = Pt(0)
        paragraph.space_before = Pt(0)
        paragraph.line_spacing = 1.0
        for run in paragraph.runs:
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
    long_title = len(title) > 34
    add_rect(slide, x, y, w, 1.02, fill=background, line=None)
    add_rect(slide, x, y, 0.06, 1.02, fill=accent, line=None)
    if long_title:
        add_text(slide, title, x + 0.22, y + 0.09, w - 0.36, 0.42, size=11.5, bold=True, fill=foreground)
        add_text(slide, text, x + 0.22, y + 0.57, w - 0.36, 0.32, size=10.5, fill=MUTED)
    else:
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


def add_section_slide(
    prs: Presentation,
    *,
    section: str,
    title: str,
    subtitle: str,
    items: list[str],
    accent: str = PURPLE,
    background: str = PURPLE_LIGHT,
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, WHITE)
    add_rect(slide, 0, 0, 4.70, 7.5, fill=accent, line=None)
    add_text(slide, section.upper(), 0.62, 0.72, 3.55, 0.30, size=12, fill=WHITE, bold=True)
    title_size = 24 if len(title) > 24 else 31
    add_text(slide, title, 0.62, 1.48, 3.78, 1.58, size=title_size, fill=WHITE, bold=True)
    add_text(slide, subtitle, 0.62, 3.30, 3.42, 1.08, size=16, fill=WHITE)
    add_text(slide, f"{len(prs.slides):02d}", 0.62, 6.72, 0.72, 0.28, size=11, fill=WHITE)
    add_rect(slide, 5.18, 0.62, 7.58, 6.28, fill=background, line=None)
    add_text(slide, "В этом разделе", 5.62, 1.10, 4.50, 0.36, size=19, bold=True)
    add_bullets(
        slide,
        items,
        5.65,
        1.82,
        6.45,
        4.65,
        size=15,
        gap=0.70,
        accent=accent,
    )


def add_steps_slide(
    prs: Presentation,
    *,
    kicker: str,
    title: str,
    steps: list[tuple[str, str]],
    side_title: str,
    side_items: list[str],
    callout_title: str,
    callout_text: str,
    callout_kind: str = "purple",
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, len(prs.slides), title, kicker)
    left_w = 6.15
    step_gap = min(0.96, 4.65 / max(len(steps), 1))
    for index, (step_title, description) in enumerate(steps, start=1):
        add_step(slide, index, step_title, description, 0.62, 1.92 + (index - 1) * step_gap, left_w)
    add_rect(slide, 7.05, 1.92, 5.62, 3.80, fill=WHITE, line=LINE)
    add_text(slide, side_title, 7.38, 2.20, 4.92, 0.36, size=19, bold=True)
    add_bullets(
        slide,
        side_items,
        7.40,
        2.84,
        4.85,
        2.46,
        size=14,
        gap=0.56,
        accent=TEAL,
    )
    add_callout(slide, callout_title, callout_text, 7.05, 5.92, 5.62, kind=callout_kind)
    add_footer(slide)


def add_cards_slide(
    prs: Presentation,
    *,
    kicker: str,
    title: str,
    cards: list[tuple[str, str, str]],
    note_title: str,
    note_text: str,
    note_kind: str = "purple",
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, len(prs.slides), title, kicker)
    palettes = {
        "purple": (PURPLE_LIGHT, PURPLE),
        "yellow": (YELLOW_LIGHT, YELLOW),
        "teal": (TEAL_LIGHT, TEAL),
        "coral": (CORAL_LIGHT, CORAL),
    }
    columns = 3 if len(cards) > 4 else 2
    card_w = 3.78 if columns == 3 else 5.75
    start_x = 0.62
    gap_x = 0.42
    row_h = 1.58
    for index, (card_title, description, kind) in enumerate(cards):
        row = index // columns
        column = index % columns
        x = start_x + column * (card_w + gap_x)
        y = 1.92 + row * 1.82
        background, accent = palettes[kind]
        add_rect(slide, x, y, card_w, row_h, fill=background, line=None)
        add_rect(slide, x, y, 0.07, row_h, fill=accent, line=None)
        add_text(slide, card_title, x + 0.24, y + 0.18, card_w - 0.46, 0.34, size=15, bold=True)
        add_text(slide, description, x + 0.24, y + 0.63, card_w - 0.46, 0.70, size=11.7, fill=MUTED)
    add_callout(slide, note_title, note_text, 3.15, 5.92, 7.05, kind=note_kind)
    add_footer(slide)


def add_two_column_slide(
    prs: Presentation,
    *,
    kicker: str,
    title: str,
    left_title: str,
    left_items: list[str],
    right_title: str,
    right_items: list[str],
    callout_title: str,
    callout_text: str,
    callout_kind: str = "yellow",
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, len(prs.slides), title, kicker)
    for x, heading, items, background, accent in [
        (0.62, left_title, left_items, WHITE, PURPLE),
        (6.80, right_title, right_items, WHITE, TEAL),
    ]:
        add_rect(slide, x, 1.92, 5.86, 3.82, fill=background, line=LINE)
        add_rect(slide, x, 1.92, 0.07, 3.82, fill=accent, line=None)
        add_text(slide, heading, x + 0.32, 2.20, 5.10, 0.36, size=18, bold=True)
        add_bullets(
            slide,
            items,
            x + 0.34,
            2.82,
            5.03,
            2.52,
            size=13.5,
            gap=0.54,
            accent=accent,
        )
    add_callout(slide, callout_title, callout_text, 3.15, 5.94, 7.05, kind=callout_kind)
    add_footer(slide)


def add_screenshot_steps_slide(
    prs: Presentation,
    *,
    kicker: str,
    title: str,
    screenshot: str,
    label: str,
    steps: list[tuple[str, str]],
    callout_title: str,
    callout_text: str,
    callout_kind: str = "purple",
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, len(prs.slides), title, kicker)
    add_screenshot(slide, screenshot, 0.48, 1.92, 6.85, 4.92, label)
    for index, (step_title, description) in enumerate(steps, start=1):
        add_step(slide, index, step_title, description, 7.72, 1.98 + (index - 1) * 1.03, 4.88)
    add_callout(slide, callout_title, callout_text, 7.62, 5.84, 5.08, kind=callout_kind)
    add_footer(slide)


def add_interaction_slide(prs: Presentation, scenario: InteractionScenario) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, len(prs.slides), scenario.title, scenario.role)

    add_rect(slide, 0.58, 1.82, 7.02, 0.48, fill=PURPLE_LIGHT, line=None)
    add_text(slide, "ПУТЬ", 0.78, 1.96, 0.52, 0.18, size=9, fill=PURPLE, bold=True)
    add_text(slide, scenario.path, 1.38, 1.90, 5.95, 0.26, size=13, bold=True)

    step_gap = min(0.88, 4.38 / max(len(scenario.steps), 1))
    for index, (step_title, description) in enumerate(scenario.steps, start=1):
        add_step(
            slide,
            index,
            step_title,
            description,
            0.62,
            2.48 + (index - 1) * step_gap,
            6.92,
        )

    add_rect(slide, 7.90, 1.82, 4.82, 4.98, fill=WHITE, line=LINE)
    add_text(slide, "Кому доступно", 8.22, 2.10, 4.15, 0.26, size=12, fill=MUTED, bold=True)
    add_text(slide, scenario.role, 8.22, 2.45, 4.15, 0.58, size=18, bold=True)
    add_callout(slide, "Что произойдет", scenario.result, 8.16, 3.24, 4.30, kind="teal")
    add_callout(slide, "Если ошиблись", scenario.correction, 8.16, 4.64, 4.30, kind="coral")
    add_text(
        slide,
        "После сохранения обновите список и проверьте результат.",
        8.22,
        6.08,
        4.05,
        0.40,
        size=11.5,
        fill=PURPLE_DARK,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    add_footer(slide, "Практическая инструкция · Algo MAX")


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
        "Подробные сценарии для учеников, родителей и сотрудников школы",
        0.64,
        3.62,
        4.25,
        0.82,
        size=17,
        fill="E8DFFC",
    )
    add_rect(slide, 0.64, 5.76, 3.26, 0.48, fill=YELLOW, line=None)
    add_text(slide, "Редактируемая презентация", 0.80, 5.89, 2.95, 0.20, size=11, bold=True)
    add_text(slide, "Редакция 7 · сентябрь 2026", 0.64, 6.52, 3.2, 0.25, size=11, fill="CBB9E8")
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
    ]
    positions = [(0.55, 2.10), (4.30, 2.10), (8.05, 2.10), (0.55, 4.05), (4.30, 4.05), (8.05, 4.05)]
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

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, 14, "Жизненный цикл заказа", "Общий процесс")
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
    add_callout(slide, "Отмену оформляют сотрудники", "Администратор или директор указывает причину; списанные AC возвращаются ученику.", 6.75, 5.28, 5.80, kind="coral")
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

    add_section_slide(
        prs,
        section="Часть 2",
        title="Подробное руководство",
        subtitle="Пошаговые действия, правила и типовые ситуации для каждой роли.",
        items=[
            "Общие принципы входа, навигации и обновления данных.",
            "Полный путь ученика и родителя от баланса до получения заказа.",
            "Работа преподавателя с учениками, начислениями и выдачей.",
            "Операции куратора, администратора и директора.",
            "Чек-листы и разбор частых затруднений.",
        ],
    )

    add_cards_slide(
        prs,
        kicker="Общая схема",
        title="Из каких частей состоит Algo MAX",
        cards=[
            ("Профили", "Ученик, родитель и сотрудник входят через MAX и получают только разрешенные разделы.", "purple"),
            ("Астрокоины", "Баланс ученика, начисления, ручные корректировки и история операций.", "yellow"),
            ("Магазин", "Каталог физических и цифровых наград, отдельные корзины детей и избранное.", "teal"),
            ("Заказы", "Резервирование, назначение склада, сборка, доставка и выдача ученику.", "coral"),
            ("Управление", "Ученики, товары, остатки, склады, сотрудники, связи и импорт данных.", "purple"),
            ("Рассылки", "Новости для выбранных групп, площадок и форматов занятий.", "teal"),
        ],
        note_title="Единые данные",
        note_text="Изменение баланса, заказа или связи отображается всем ролям, которым доступна эта информация.",
        note_kind="yellow",
    )

    add_cards_slide(
        prs,
        kicker="Термины",
        title="Основные понятия",
        cards=[
            ("AC", "Астрокоины ученика. Используются для покупки наград в магазине.", "yellow"),
            ("Партнер", "Школа или город с собственными учениками, сотрудниками, товарами и складами.", "purple"),
            ("Площадка", "Место проведения занятий. Определяется по группам и используется при доставке.", "teal"),
            ("Связь", "Подтвержденное соответствие MAX-аккаунта ученику, родителю или сотруднику.", "coral"),
            ("Резерв", "Заказ оформлен, но склад для списания товара еще не назначен.", "yellow"),
            ("Автовыдача", "Цифровой код автоматически выдается после успешного оформления заказа.", "teal"),
        ],
        note_title="Названия статусов важны",
        note_text="При проверке заказа ориентируйтесь на его текущий статус, а не только на дату создания.",
        note_kind="purple",
    )

    add_steps_slide(
        prs,
        kicker="Доступ",
        title="Первый вход через MAX",
        steps=[
            ("Получите ссылку", "Школа отправляет персональную ссылку родителя, ученика или сотрудника."),
            ("Откройте бота", "Перейдите по ссылке в нужном MAX-аккаунте и подтвердите подключение."),
            ("Завершите привязку", "Родитель связывается с детьми, сотрудник получает назначенную роль."),
            ("Откройте кабинет", "Нажмите кнопку приложения в основном меню бота."),
            ("Проверьте данные", "Сверьте имя, ребенка, роль и выбранный город до начала работы."),
        ],
        side_title="Доступ не появится, если",
        side_items=[
            "ссылка уже была использована другим аккаунтом;",
            "роль сотрудника отозвана;",
            "родительская связь удалена;",
            "срок доступа выбывшего ученика завершился.",
        ],
        callout_title="Не выбирайте роль вручную",
        callout_text="Система показывает только подтвержденные роли и связанные профили.",
        callout_kind="coral",
    )

    add_two_column_slide(
        prs,
        kicker="Навигация",
        title="Где находятся разделы",
        left_title="На компьютере",
        left_items=[
            "Основное меню расположено слева.",
            "Активный раздел выделен фиолетовым.",
            "Рабочий город выбирается в верхней части страницы.",
            "Списки и фильтры рассчитаны на широкую область экрана.",
        ],
        right_title="На телефоне",
        right_items=[
            "Основные разделы находятся в нижнем меню.",
            "Дополнительные пункты открываются кнопкой «Еще».",
            "Горизонтальные списки можно листать пальцем.",
            "Модальные окна закрываются крестиком в правом верхнем углу.",
        ],
        callout_title="Возврат к главному экрану",
        callout_text="В приложении используйте пункт «Главная», а в боте — кнопку возврата в основное меню.",
    )

    add_cards_slide(
        prs,
        kicker="Общие действия",
        title="Профиль, город и обновление данных",
        cards=[
            ("Профиль", "Показывает активную роль и имя. Сотрудникам личный баланс AC не выводится.", "purple"),
            ("Баланс", "У ученика и родителя обновляется кнопкой рядом с суммой AC.", "yellow"),
            ("Ребенок", "У родителя выбранный ребенок определяет баланс, корзину, историю и заказы.", "teal"),
            ("Город", "Сотрудник выполняет операции только в выбранном и разрешенном ему городе.", "coral"),
            ("Обновить", "Перезагружает текущий список после действий другого сотрудника.", "purple"),
            ("Закрыть", "Крестик закрывает карточку без изменения данных, если сохранение не выполнялось.", "teal"),
        ],
        note_title="Перед массовой операцией",
        note_text="Проверьте активного ребенка, город, группу и выбранный фильтр.",
        note_kind="coral",
    )

    add_two_column_slide(
        prs,
        kicker="Заказы",
        title="Кто отвечает за каждый этап",
        left_title="Ученик и родитель",
        left_items=[
            "Выбирают товар и оформляют заказ.",
            "Следят за статусом в разделе «Заказы».",
            "Открывают цифровой код в полученном заказе.",
            "По отмене обращаются к администратору или директору.",
        ],
        right_title="Сотрудники школы",
        right_items=[
            "Администратор или директор назначает склад.",
            "Ответственный сотрудник собирает и доставляет товар.",
            "Преподаватель подтверждает получение комплекта.",
            "После фактической выдачи заказ отмечается полученным.",
        ],
        callout_title="Статус меняется после действия",
        callout_text="Нельзя подтверждать доставку, получение или выдачу заранее.",
        callout_kind="coral",
    )

    add_section_slide(
        prs,
        section="Роль 1",
        title="Ученик",
        subtitle="Баланс, магазин, корзина, заказы и история астрокоинов.",
        items=[
            "Проверка профиля и баланса.",
            "Поиск и выбор награды.",
            "Оформление заказа.",
            "Получение физического или цифрового товара.",
            "Просмотр истории AC.",
        ],
        accent=PURPLE,
        background=PURPLE_LIGHT,
    )

    add_screenshot_steps_slide(
        prs,
        kicker="Ученик",
        title="Главная страница ученика",
        screenshot="student-dashboard.png",
        label="Пример кабинета ученика",
        steps=[
            ("Проверьте имя", "В профиле должен быть выбран ваш ученик."),
            ("Посмотрите баланс", "Сумма показывает доступные для покупок AC."),
            ("Откройте нужный раздел", "Магазин, корзина, заказы или история AC."),
        ],
        callout_title="Если показан чужой профиль",
        callout_text="Закройте кабинет и сообщите школе. Не оформляйте заказ от чужого имени.",
        callout_kind="coral",
    )

    add_steps_slide(
        prs,
        kicker="Ученик",
        title="Баланс и история астрокоинов",
        steps=[
            ("Обновите баланс", "Нажмите кнопку обновления рядом с текущей суммой."),
            ("Откройте «История AC»", "В списке показаны начисления, списания и возвраты."),
            ("Проверьте операцию", "Смотрите дату, причину, сумму и итоговое изменение."),
            ("Сообщите о расхождении", "Передайте администратору имя ученика и дату операции."),
        ],
        side_title="Какие операции встречаются",
        side_items=[
            "начисление преподавателем;",
            "подарок ко дню рождения;",
            "списание при покупке;",
            "возврат после отмены заказа.",
        ],
        callout_title="История не редактируется учеником",
        callout_text="Корректировку выполняет сотрудник с доступом к карточке ученика.",
    )

    add_steps_slide(
        prs,
        kicker="Ученик",
        title="Как найти товар в магазине",
        steps=[
            ("Откройте «Магазин»", "Каталог показывает доступные награды выбранного города."),
            ("Используйте быстрые категории", "Категория сразу ограничивает список товаров."),
            ("Введите название", "Поиск работает по названию и описанию товара."),
            ("Настройте фильтры", "Можно показать товары в наличии или только избранное."),
            ("Откройте карточку", "Проверьте цену, наличие, описание и способ получения."),
        ],
        side_title="Сортировка",
        side_items=[
            "сначала рекомендуемые;",
            "сначала дешевые;",
            "сначала дорогие;",
            "по популярности.",
        ],
        callout_title="Недоступный товар",
        callout_text="Если товара или цифровых кодов нет, кнопка покупки будет отключена.",
        callout_kind="yellow",
    )

    add_two_column_slide(
        prs,
        kicker="Ученик",
        title="Физический и цифровой товар",
        left_title="Физическая награда",
        left_items=[
            "После заказа сотрудник назначает склад.",
            "Товар собирают и доставляют на площадку.",
            "Преподаватель получает комплект для выдачи.",
            "Заказ завершается после передачи ученику.",
        ],
        right_title="Цифровая награда",
        right_items=[
            "Для товара заранее загружены уникальные коды.",
            "Код выдается автоматически после покупки.",
            "Он находится внутри карточки полученного заказа.",
            "Код можно скопировать кнопкой рядом с ним.",
        ],
        callout_title="Цифровой код не приходит отдельным сообщением",
        callout_text="Откройте «Заказы» → «Получены» → нужный заказ.",
        callout_kind="purple",
    )

    add_steps_slide(
        prs,
        kicker="Ученик",
        title="Корзина и оформление заказа",
        steps=[
            ("Добавьте товар", "Выберите нужное количество в пределах доступного остатка."),
            ("Откройте корзину", "Проверьте название, количество и стоимость каждой позиции."),
            ("Сверьте расчет", "Посмотрите баланс до покупки, сумму списания и остаток."),
            ("Подтвердите заказ", "Нажмите желтую кнопку оформления только один раз."),
            ("Откройте заказы", "Убедитесь, что новый заказ появился в списке."),
        ],
        side_title="Перед подтверждением",
        side_items=[
            "выбран правильный профиль;",
            "количество товара верное;",
            "баланса AC достаточно;",
            "товар действительно нужен.",
        ],
        callout_title="Отмена через сотрудника",
        callout_text="Ученик и родитель не отменяют заказ самостоятельно. Обратитесь к администратору или директору.",
        callout_kind="coral",
    )

    add_steps_slide(
        prs,
        kicker="Ученик",
        title="Как проверить и получить заказ",
        steps=[
            ("Откройте «Заказы»", "Выберите вкладку с нужным статусом."),
            ("Откройте карточку", "Посмотрите состав, стоимость и историю изменений."),
            ("Дождитесь выдачи", "Физический товар передает преподаватель или сотрудник школы."),
            ("Проверьте завершение", "Полученный заказ находится в категории «Получены»."),
        ],
        side_title="Что означают статусы",
        side_items=[
            "зарезервирован — склад не назначен;",
            "ожидает доставки — товар собирают;",
            "на площадке — товар уже доставлен;",
            "у учителя — комплект принят педагогом.",
        ],
        callout_title="История показывает фактические этапы",
        callout_text="Дата и комментарий под статусом объясняют последнее действие сотрудника.",
        callout_kind="teal",
    )

    add_section_slide(
        prs,
        section="Роль 2",
        title="Родитель",
        subtitle="Управление профилями детей, отдельными корзинами, заказами и доступом ребенка.",
        items=[
            "Переключение между детьми.",
            "Проверка баланса и истории каждого ребенка.",
            "Покупки от имени выбранного ребенка.",
            "QR-код и ссылка для детского входа.",
            "Контроль заказов семьи.",
        ],
        accent=TEAL,
        background=TEAL_LIGHT,
    )

    add_screenshot_steps_slide(
        prs,
        kicker="Родитель",
        title="Главная страница родителя",
        screenshot="parent-dashboard.png",
        label="Пример семейного кабинета",
        steps=[
            ("Выберите ребенка", "Имя активного ребенка выделяется в переключателе."),
            ("Проверьте данные", "Баланс и последние заказы относятся к выбранному ребенку."),
            ("Перейдите к действию", "Откройте магазин, корзину, заказы или историю AC."),
        ],
        callout_title="Каждый ребенок — отдельный профиль",
        callout_text="Корзина, баланс и заказы не объединяются между детьми.",
        callout_kind="yellow",
    )

    add_two_column_slide(
        prs,
        kicker="Родитель",
        title="Переключение детей и отдельные корзины",
        left_title="Что меняется при выборе ребенка",
        left_items=[
            "имя получателя заказа;",
            "доступный баланс AC;",
            "содержимое корзины;",
            "история начислений и заказов.",
        ],
        right_title="Что проверить перед покупкой",
        right_items=[
            "выделено нужное имя;",
            "баланс относится к этому ребенку;",
            "в корзине нет старых лишних позиций;",
            "стоимость заказа рассчитана верно.",
        ],
        callout_title="Количество в корзине видно у имени ребенка",
        callout_text="Это помогает не смешивать незавершенные покупки нескольких детей.",
        callout_kind="teal",
    )

    add_steps_slide(
        prs,
        kicker="Родитель",
        title="QR-код и ссылка для входа ребенка",
        steps=[
            ("Откройте блок QR-кодов", "В кабинете показаны только связанные с родителем дети."),
            ("Выберите нужного ребенка", "Проверьте имя и группу над QR-кодом."),
            ("Передайте доступ", "Покажите QR с другого устройства или скопируйте ссылку."),
            ("Ребенок открывает MAX", "Связь создается только для выбранного детского профиля."),
            ("Проверьте результат", "В детском кабинете должны быть его имя, баланс и заказы."),
        ],
        side_title="Доступ прекращается, если",
        side_items=[
            "родитель заблокировал бота;",
            "связь удалена сотрудником;",
            "срок доступа после выбытия закончился;",
            "профиль ребенка архивирован.",
        ],
        callout_title="Не открывайте детскую ссылку в аккаунте родителя",
        callout_text="Ссылку должен использовать MAX-аккаунт ребенка.",
        callout_kind="coral",
    )

    add_cards_slide(
        prs,
        kicker="Родитель",
        title="Контроль заказов семьи",
        cards=[
            ("Все заказы", "Список показывает заказы выбранного ребенка и их текущие статусы.", "purple"),
            ("Поиск", "Найдите заказ по номеру, имени ребенка или товару.", "teal"),
            ("Карточка", "Откройте состав, стоимость, склад и историю статусов.", "yellow"),
            ("Полученные", "Завершенные заказы и цифровые коды находятся в этой категории.", "teal"),
            ("Отмененные", "В карточке отображается причина отмены и возврат AC.", "coral"),
            ("Вопрос по заказу", "Сообщите администратору номер заказа и имя ребенка.", "purple"),
        ],
        note_title="Родитель не меняет рабочие статусы",
        note_text="Назначение склада, доставка, отмена и выдача выполняются сотрудниками школы.",
        note_kind="coral",
    )

    add_section_slide(
        prs,
        section="Роль 3",
        title="Преподаватель",
        subtitle="Свои ученики, QR-коды, начисления и получение заказов для выдачи.",
        items=[
            "Работа только со своими группами.",
            "Выбор учеников для начисления AC.",
            "Просмотр карточки и истории ученика.",
            "Показ детских QR-кодов.",
            "Получение и выдача заказов.",
        ],
        accent=YELLOW,
        background=YELLOW_LIGHT,
    )

    add_screenshot_steps_slide(
        prs,
        kicker="Преподаватель",
        title="Главная страница преподавателя",
        screenshot="teacher-dashboard.png",
        label="Пример рабочего кабинета",
        steps=[
            ("Проверьте профиль", "Указана роль преподавателя и нужный город."),
            ("Откройте учеников", "Список ограничен назначенными преподавателю группами."),
            ("Выберите задачу", "Начисление AC, QR-коды или заказы учеников."),
        ],
        callout_title="Нет счета AC",
        callout_text="Сотрудник не покупает товары; баланс существует только у детей.",
        callout_kind="yellow",
    )

    add_steps_slide(
        prs,
        kicker="Преподаватель",
        title="Как начислить астрокоины",
        steps=[
            ("Откройте «Начисления»", "Выберите группу и при необходимости найдите ученика по имени."),
            ("Отметьте учеников", "Поставьте флажки только тем, кому предназначено начисление."),
            ("Выберите причину", "Стандартная причина автоматически подставляет разрешенную сумму."),
            ("Проверьте сумму", "Для нестандартной ситуации используйте ручную причину и сумму."),
            ("Подтвердите", "Проверьте количество выбранных учеников перед одной общей операцией."),
        ],
        side_title="После начисления",
        side_items=[
            "баланс учеников увеличивается;",
            "операция появляется в истории;",
            "в отчете видны педагог и группа;",
            "ошибку исправляет администратор.",
        ],
        callout_title="Не повторяйте нажатие",
        callout_text="Дождитесь сообщения об успешном начислении и обновления списка.",
        callout_kind="coral",
    )

    add_cards_slide(
        prs,
        kicker="Преподаватель",
        title="Карточка ученика и детский QR",
        cards=[
            ("Группа", "Фильтр показывает только группы, доступные текущему преподавателю.", "purple"),
            ("Карточка", "Содержит статус, баланс, группу и доступную историю ученика.", "teal"),
            ("История", "Показывает изменения состояния и операции AC в разрешенном объеме.", "yellow"),
            ("QR-код", "Преподаватель может показать код ребенку из своей группы.", "purple"),
            ("Нет родителя", "Ребенок увидит инструкцию открыть письмо и подключить родителя.", "coral"),
            ("Поиск", "Используйте фамилию, имя или группу для быстрого перехода.", "teal"),
        ],
        note_title="Доступ ограничен группами",
        note_text="Преподаватель не должен видеть учеников других педагогов и филиалов.",
        note_kind="coral",
    )

    add_steps_slide(
        prs,
        kicker="Преподаватель",
        title="Получение и выдача заказов",
        steps=[
            ("Откройте «Заказы»", "Список содержит заказы учеников доступных групп."),
            ("Сверьте комплект", "Проверьте товар, количество и ученика до подтверждения."),
            ("Подтвердите получение", "Нажмите «Учитель получил заказ» после фактической передачи."),
            ("Передайте ученику", "Выдайте товар указанному ребенку."),
            ("Завершите заказ", "Отметьте заказ полученным только после реальной выдачи."),
        ],
        side_title="В выжимке видно",
        side_items=[
            "какие товары приехали;",
            "количество каждой позиции;",
            "для каких учеников заказы;",
            "на какой площадке выдача.",
        ],
        callout_title="Не отменяйте заказ",
        callout_text="Отмена доступна администратору и директору.",
        callout_kind="coral",
    )

    add_section_slide(
        prs,
        section="Роль 4",
        title="Куратор",
        subtitle="Контроль учеников, заказов и коммуникаций в разрешенной области филиала.",
        items=[
            "Просмотр доступных учеников и групп.",
            "Контроль заказов и начислений.",
            "Фильтры отчета AC.",
            "Подготовка рассылок.",
            "Работа только в назначенном городе.",
        ],
        accent=CORAL,
        background=CORAL_LIGHT,
    )

    add_screenshot_steps_slide(
        prs,
        kicker="Куратор",
        title="Подготовка рассылки",
        screenshot="curator-broadcasts.png",
        label="Раздел рассылок",
        steps=[
            ("Выберите аудиторию", "Группы, площадки, формат занятий или другой доступный фильтр."),
            ("Заполните новость", "Введите понятный текст и при необходимости добавьте изображение."),
            ("Проверьте получателей", "Предварительный расчет показывает размер аудитории."),
            ("Отправьте", "После подтверждения просмотрите результат доставки."),
        ],
        callout_title="Не отправляйте без предварительного просмотра",
        callout_text="Проверьте текст, изображение, город и выбранные группы.",
        callout_kind="coral",
    )

    add_two_column_slide(
        prs,
        kicker="Куратор",
        title="Контроль начислений и заказов",
        left_title="Отчет AC",
        left_items=[
            "задайте период;",
            "выберите преподавателя;",
            "выберите группу;",
            "проверьте ученика, причину и сумму.",
        ],
        right_title="Заказы",
        right_items=[
            "используйте категории по статусам;",
            "найдите заказ по номеру или ученику;",
            "откройте историю статусов;",
            "передайте проблему администратору.",
        ],
        callout_title="Куратор не управляет доступами сотрудников",
        callout_text="Выдачу и отзыв ролей выполняет директор, а администратор действует в разрешенных пределах.",
        callout_kind="yellow",
    )

    add_section_slide(
        prs,
        section="Роль 5",
        title="Администратор",
        subtitle="Операционная работа с заказами, товарами, складами, учениками и импортом.",
        items=[
            "Назначение склада и комплектация заказов.",
            "Доставка на площадку и передача преподавателю.",
            "Товары, цифровые коды и остатки.",
            "Карточки учеников и корректировки AC.",
            "Импорт и контроль связей.",
        ],
        accent=PURPLE,
        background=PURPLE_LIGHT,
    )

    add_screenshot_steps_slide(
        prs,
        kicker="Администратор",
        title="Раздел заказов",
        screenshot="admin-orders.png",
        label="Статусы и выдача",
        steps=[
            ("Выберите категорию", "Счетчик показывает количество заказов на каждом этапе."),
            ("Используйте поиск", "Номер, ученик или товар помогают найти нужную карточку."),
            ("Откройте заказ", "Проверьте состав, склад, историю и доступное действие."),
        ],
        callout_title="Рабочие этапы разделены",
        callout_text="Назначение склада, сборка и распределение выполняются в отдельных режимах.",
        callout_kind="teal",
    )

    add_cards_slide(
        prs,
        kicker="Администратор",
        title="Три этапа комплектации",
        cards=[
            ("1. Назначить склад", "Для зарезервированных заказов выберите склад списания по каждой позиции.", "yellow"),
            ("2. Собрать", "Общий чек-лист объединяет одинаковые товары и группирует их по складам.", "purple"),
            ("3. Распределить", "Полностью собранные заказы распределяются по площадкам и преподавателям.", "teal"),
            ("Обновить", "Переход на следующий этап происходит после сохранения и обновления данных.", "coral"),
        ],
        note_title="Флажок сборки — промежуточная отметка",
        note_text="Он помогает комплектовать заказ, но сам по себе не меняет статус до подтверждения действия.",
        note_kind="yellow",
    )

    add_steps_slide(
        prs,
        kicker="Администратор",
        title="Назначение склада",
        steps=[
            ("Откройте режим", "Перейдите в «Заказы» → «Назначить склад»."),
            ("Откройте заказ", "Проверьте товары, количество и доступные остатки."),
            ("Выберите склады", "Основной склад сотрудника подставляется заранее, но его можно изменить."),
            ("Подтвердите", "Система резервирует остаток и переводит заказ к сборке."),
        ],
        side_title="Перед подтверждением",
        side_items=[
            "остатка достаточно;",
            "выбран правильный склад;",
            "цифровой товар не требует склада;",
            "в заказе нет ошибочной позиции.",
        ],
        callout_title="Нет остатка",
        callout_text="Измените склад, пополните остаток или отмените заказ с корректной причиной.",
        callout_kind="coral",
    )

    add_steps_slide(
        prs,
        kicker="Администратор",
        title="Общий чек-лист сборки",
        steps=[
            ("Откройте «Собрать»", "В списке только заказы с уже назначенными складами."),
            ("Идите по складам", "Одинаковые товары объединены в одну строку с общим количеством."),
            ("Отмечайте позиции", "Флажок фиксирует, что нужное количество физически собрано."),
            ("Сверьте итог", "Счетчик должен совпасть с фактическим комплектом."),
            ("Сохраните этап", "После подтверждения заказы становятся доступными для распределения."),
        ],
        side_title="В строке товара видно",
        side_items=[
            "название товара;",
            "необходимое количество;",
            "склад, откуда забрать;",
            "прогресс комплектации.",
        ],
        callout_title="Не отмечайте отсутствующий товар",
        callout_text="Чек-лист должен соответствовать реально собранным позициям.",
        callout_kind="coral",
    )

    add_steps_slide(
        prs,
        kicker="Администратор",
        title="Распределение и доставка",
        steps=[
            ("Откройте «Распределить»", "Здесь находятся полностью собранные заказы."),
            ("Раскройте площадку", "Внутри заказы сгруппированы по преподавателям."),
            ("Сверьте маршрут", "Проверьте площадку, педагога, учеников и состав."),
            ("Отметьте доставленные", "Выберите фактически привезенные заказы."),
            ("Подтвердите доставку", "Статус изменится на «Доставлен на площадку»."),
        ],
        side_title="После доставки",
        side_items=[
            "заказ исчезает из сборки;",
            "преподаватель видит комплект;",
            "ученик видит новый статус;",
            "история сохраняет дату действия.",
        ],
        callout_title="Обновляйте список",
        callout_text="Кнопка обновления подгружает действия других сотрудников и убирает завершенные этапы.",
        callout_kind="teal",
    )

    add_steps_slide(
        prs,
        kicker="Администратор",
        title="Отмена заказа и возврат AC",
        steps=[
            ("Откройте карточку", "Проверьте номер, ученика, состав и текущий статус."),
            ("Выберите отмену", "Команда находится в меню дополнительных действий."),
            ("Укажите причину", "Выберите стандартный вариант или заполните свою причину."),
            ("Подтвердите", "Заказ отменяется, а списанные AC возвращаются ученику."),
            ("Проверьте результат", "Причина видна в заказе, возврат — в истории AC."),
        ],
        side_title="Причина «Товар закончился»",
        side_items=[
            "используйте только при реальном отсутствии;",
            "проверьте остатки всех складов;",
            "при необходимости обнулите неверный остаток;",
            "сообщите ответственному за закупку.",
        ],
        callout_title="Право отмены",
        callout_text="Заказ отменяют администратор или директор независимо от этапа.",
        callout_kind="coral",
    )

    add_cards_slide(
        prs,
        kicker="Администратор",
        title="Товары, остатки и цифровые коды",
        cards=[
            ("Создание товара", "Название, категория, цена, описание, статус и фотография заполняются одной формой.", "purple"),
            ("SKU", "Формируется автоматически и не требует ручного ввода.", "yellow"),
            ("Остатки", "Для физического товара задаются прямо в карточке по выбранным складам.", "teal"),
            ("Цифровой товар", "Вместо складов добавляется список уникальных кодов автовыдачи.", "coral"),
            ("Коды", "Выданный код становится неактивным, но остается в истории товара.", "purple"),
            ("Массовый импорт", "Товары загружаются по подготовленному XLSX-шаблону.", "teal"),
        ],
        note_title="Перед публикацией",
        note_text="Проверьте изображение, цену, категорию, описание и фактическое наличие.",
        note_kind="yellow",
    )

    add_two_column_slide(
        prs,
        kicker="Администратор",
        title="Склады и остатки",
        left_title="Карточка склада",
        left_items=[
            "понятное название;",
            "адрес или примечание;",
            "активный статус;",
            "остатки товаров, хранящихся на складе.",
        ],
        right_title="Основной склад сотрудника",
        right_items=[
            "назначается один раз;",
            "подставляется при комплектации;",
            "может быть изменен перед подтверждением;",
            "можно переназначить в настройках сотрудника.",
        ],
        callout_title="Остатки редактируются в товаре",
        callout_text="Отдельная вкладка остатков не требуется: склады и количества собраны в карточке товара.",
        callout_kind="teal",
    )

    add_cards_slide(
        prs,
        kicker="Администратор",
        title="Карточка ученика",
        cards=[
            ("Основные данные", "ФИО, ID ученика, группа, преподаватель, дата рождения и родитель.", "purple"),
            ("Статус", "Обучается, выбыл или архив. Изменение сохраняется в истории.", "coral"),
            ("Баланс", "Администратор может установить корректное количество AC с указанием причины.", "yellow"),
            ("История", "Дата импорта, обновления, выбытия, статусы и административные действия.", "teal"),
            ("Связи", "Показывает привязанные MAX-аккаунты родителя и ребенка.", "purple"),
            ("Доступ после выбытия", "Срок и период заморозки задаются настройками города.", "teal"),
        ],
        note_title="Изменения должны быть объяснимыми",
        note_text="При ручной корректировке статуса или баланса указывайте понятную причину.",
        note_kind="coral",
    )

    add_steps_slide(
        prs,
        kicker="Администратор",
        title="Импорт учеников, групп и преподавателей из Excel",
        steps=[
            ("Скачайте шаблон", "Используйте листы «Инструкция» и «Шаблон» либо поддерживаемый лист «Сделки»."),
            ("Заполните город", "В каждой строке укажите существующий город, доступный директору."),
            ("Проверьте файл", "Предпросмотр покажет строки, группы, преподавателей и распределение по городам."),
            ("Запустите импорт", "Система создаст или обновит учеников в соответствующих филиалах."),
            ("Исправьте ошибки", "Неизвестный город или отсутствие прав останавливает импорт до записи данных."),
        ],
        side_title="До загрузки проверьте",
        side_items=[
            "ID учеников;",
            "полные фамилии и имена;",
            "названия и ID групп;",
            "город, преподавателей и родительские связи.",
        ],
        callout_title="Импорт распределяет данные автоматически",
        callout_text="Все города должны быть заранее созданы; лишние листы и столбцы система игнорирует.",
        callout_kind="coral",
    )

    add_section_slide(
        prs,
        section="Роль 6",
        title="Директор",
        subtitle="Управление сотрудниками, назначенными городами и операционными настройками.",
        items=[
            "Контроль операционной работы филиала.",
            "Выдача и отзыв ролей сотрудников.",
            "Настройка уведомлений.",
            "Управление несколькими городами директора.",
        ],
        accent=TEAL,
        background=TEAL_LIGHT,
    )

    add_screenshot_steps_slide(
        prs,
        kicker="Директор",
        title="Управление сотрудниками",
        screenshot="director-management.png",
        label="Сотрудники и роли",
        steps=[
            ("Создайте приглашение", "Нажмите «Пригласить сотрудника» и выберите разрешенную роль."),
            ("Отправьте ссылку", "Ссылка действует семь дней и срабатывает только один раз."),
            ("Проверьте привязку", "После перехода сотрудник сразу появится в активном списке."),
            ("Управляйте доступом", "Настройте уведомления либо отзовите роль при необходимости."),
        ],
        callout_title="Директор работает со своими сотрудниками",
        callout_text="Директор приглашает администратора, куратора или преподавателя только в выбранный город.",
        callout_kind="coral",
    )

    add_two_column_slide(
        prs,
        kicker="Директор",
        title="Роли сотрудников и уведомления",
        left_title="Что можно назначать",
        left_items=[
            "администраторов филиала;",
            "кураторов;",
            "преподавателей;",
            "основной склад сотрудника.",
        ],
        right_title="Какие уведомления настраиваются",
        right_items=[
            "новые и отмененные заказы;",
            "низкие остатки и цифровые коды;",
            "доставка и передача заказов;",
            "результаты рассылок.",
        ],
        callout_title="Отзыв роли прекращает рабочий доступ",
        callout_text="После отзыва сотрудник больше не должен видеть административные разделы города.",
        callout_kind="coral",
    )

    add_cards_slide(
        prs,
        kicker="Директор",
        title="Контроль филиала",
        cards=[
            ("Заказы", "Проверяйте очередь назначения склада, сборку, доставку и выдачу.", "purple"),
            ("Остатки", "Контролируйте наличие физических товаров и запас цифровых кодов.", "yellow"),
            ("Начисления", "Фильтруйте отчет по периоду, преподавателю и группе.", "teal"),
            ("Ученики", "Следите за статусами, балансом, связями и датами обновления.", "coral"),
            ("Сотрудники", "Проверяйте активные роли и персональные уведомления.", "purple"),
            ("Рассылки", "Контролируйте аудиторию, содержание и результат доставки.", "teal"),
        ],
        note_title="Несколько городов",
        note_text="Перед операцией директор выбирает нужный город из списка назначенных ему партнеров.",
        note_kind="yellow",
    )

    add_section_slide(
        prs,
        section="Часть 3",
        title="Практические действия по кнопкам",
        subtitle="Точные маршруты для ежедневной работы: куда перейти, что нажать, какой результат ждать и как исправить ошибку.",
        items=[
            "Навигация на компьютере и телефоне.",
            "Покупка, корзина, заказы и QR-коды.",
            "Начисления, выдача и рассылки.",
            "Склады, комплектация, товары и импорт.",
            "Сотрудники, связи, города и проверка результата.",
        ],
        accent=PURPLE,
        background=PURPLE_LIGHT,
    )

    for scenario in SCENARIOS:
        add_interaction_slide(prs, scenario)

    add_cards_slide(
        prs,
        kicker="Чек-листы",
        title="Что проверять каждый рабочий день",
        cards=[
            ("Преподаватель", "Новые начисления, QR учеников, полученные комплекты и фактическая выдача.", "yellow"),
            ("Куратор", "Проблемные заказы, корректность начислений и запланированные рассылки.", "coral"),
            ("Администратор", "Заказы без склада, чек-лист сборки, доставка и низкие остатки.", "purple"),
            ("Директор", "Очередь заказов, сотрудники, отчет AC и состояние товаров.", "teal"),
            ("Перед началом", "Проверьте рабочий город, роль и актуальность данных.", "purple"),
            ("Перед завершением", "Обновите списки и убедитесь, что статусы соответствуют фактическим действиям.", "teal"),
        ],
        note_title="Не держите незавершенное действие открытым",
        note_text="После массовой операции дождитесь подтверждения и обновите соответствующий список.",
        note_kind="yellow",
    )

    add_cards_slide(
        prs,
        kicker="Диагностика",
        title="Частые ситуации и решения",
        cards=[
            ("Нет нужного раздела", "Проверьте активную роль. Раздел может быть недоступен этому сотруднику.", "purple"),
            ("Не виден ученик", "Проверьте город, группу, преподавателя, статус и активность связи.", "teal"),
            ("Не меняется статус", "Обновите список и убедитесь, что предыдущий этап действительно завершен.", "yellow"),
            ("Неверный остаток", "Сверьте склад в товаре и незавершенные резервы по заказам.", "coral"),
            ("Не работает QR", "Получите актуальный код и проверьте активность родительской связи.", "purple"),
            ("Ошибка повторяется", "Запишите роль, город, раздел, номер заказа и последовательность действий.", "coral"),
        ],
        note_title="Что приложить к обращению",
        note_text="Снимок экрана, время ошибки, роль, город и номер связанного ученика или заказа.",
        note_kind="teal",
    )

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_brand(slide, len(prs.slides), "Раздел помощи", "Поддержка")
    add_screenshot(slide, "help-placeholder-desktop.png", 0.48, 1.92, 7.15, 4.85, "Страница на компьютере")
    add_screenshot(slide, "help-placeholder-mobile.png", 7.98, 1.92, 4.82, 3.65, "Страница на телефоне")
    add_callout(
        slide,
        "Сейчас раздел закрыт",
        "До публикации встроенных материалов используйте эту презентацию как основное руководство.",
        7.98,
        5.78,
        4.82,
        kind="yellow",
    )
    add_footer(slide)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, PURPLE_DARK)
    add_rect(slide, 0.68, 0.68, 0.58, 0.58, fill=YELLOW, line=None, radius=True)
    add_text(slide, "A", 0.68, 0.70, 0.58, 0.50, size=22, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_text(slide, "ALGO MAX", 1.48, 0.82, 2.20, 0.32, size=18, fill=WHITE, bold=True)
    add_text(slide, "Перед началом работы", 0.72, 2.05, 5.80, 0.62, size=31, fill=WHITE, bold=True)
    add_bullets(
        slide,
        [
            "Проверьте профиль, роль и город.",
            "Обновите данные нужного раздела.",
            "Перед подтверждением сверьте выбранные записи.",
            "Меняйте статус только после фактического действия.",
            "При ошибке сохраняйте номер заказа или ученика.",
        ],
        0.78,
        3.08,
        5.65,
        3.15,
        size=15,
        gap=0.62,
        accent=YELLOW,
        fill=WHITE,
    )
    add_rect(slide, 7.02, 1.02, 5.62, 5.56, fill=WHITE, line=None)
    add_text(slide, "Краткий маршрут", 7.48, 1.50, 4.70, 0.40, size=21, bold=True)
    add_step(slide, 1, "Войти через MAX", "Используйте свой подтвержденный аккаунт.", 7.48, 2.25, 4.55)
    add_step(slide, 2, "Выбрать профиль", "Ребенок, роль сотрудника и город.", 7.48, 3.28, 4.55)
    add_step(slide, 3, "Выполнить действие", "Проверить все выбранные данные.", 7.48, 4.31, 4.55)
    add_step(slide, 4, "Обновить результат", "Убедиться, что операция завершена.", 7.48, 5.34, 4.55)
    add_text(slide, f"{len(prs.slides):02d}", 12.02, 6.88, 0.62, 0.28, size=11, fill="CBB9E8", align=PP_ALIGN.RIGHT)

    return prs


def main() -> None:
    import sys

    from build_visual_guide import build_visual_presentation

    presentation = build_visual_presentation(sys.modules[__name__])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(OUTPUT)
    write_markdown(INTERACTION_GUIDE_OUTPUT)
    print(f"Created {OUTPUT} ({len(presentation.slides)} slides)")
    print(f"Created {INTERACTION_GUIDE_OUTPUT}")


if __name__ == "__main__":
    main()
