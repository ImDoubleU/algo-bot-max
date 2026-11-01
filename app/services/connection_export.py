"""Connection reports: one row per pupil, never one row per family account."""

from collections import defaultdict
from datetime import UTC, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from app.models.enums import StudentStatus
from app.schemas.miniapp import (
    MiniAppConnectionExportStudentRead,
    MiniAppConnectionsExportRequest,
)
from app.services.miniapp import MiniAppStoreError


def filter_connection_students(
    students: list[MiniAppConnectionExportStudentRead], payload: MiniAppConnectionsExportRequest,
) -> list[MiniAppConnectionExportStudentRead]:
    selections = [("teacher_name", payload.teachers), ("venue_name", payload.venues),
                  ("group_name", payload.groups)]
    for field, values in selections:
        if values is not None and not set(values).issubset({getattr(s, field) for s in students}):
            raise MiniAppStoreError("Список фильтров изменился. Откройте экспорт заново")
    selected = [s for s in students if (
        (payload.include_inactive or s.status == StudentStatus.ACTIVE)
        and all(values is None or getattr(s, field) in values for field, values in selections)
    )]
    if not selected:
        raise MiniAppStoreError("В выбранных преподавателях, площадках и группах нет учеников")
    return sorted(selected, key=lambda s: (
        s.group_name, s.venue_name, s.teacher_name, s.display_name, str(s.student_id),
    ))


def build_connection_workbook(
    students: list[MiniAppConnectionExportStudentRead], *, tenant_name: str,
    include_inactive: bool = False, generated_at: datetime | None = None,
) -> bytes:
    if not students:
        raise MiniAppStoreError("Нет учеников для экспорта")
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {
        "in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
    })
    workbook.set_properties({"title": "Подключения учеников", "author": "Algo MAX"})
    summary = workbook.add_worksheet("Сводка")
    detail = workbook.add_worksheet("Ученики")
    base = {"font_name": "Arial", "font_size": 10, "valign": "vcenter", "align": "left"}
    body = workbook.add_format(base)
    wrapped = workbook.add_format({**base, "text_wrap": True})
    identifier = workbook.add_format({**base, "num_format": "@"})
    checkbox = workbook.add_format({**base, "align": "center"})
    number = workbook.add_format({**base, "num_format": "0", "align": "right"})
    percent = workbook.add_format({**base, "num_format": "0.0%", "align": "right"})
    total = workbook.add_format({**base, "bold": True, "font_size": 18,
        "num_format": "0", "align": "right", "bg_color": "#F2F5F6"})
    connected_total = workbook.add_format({**base, "bold": True, "font_size": 18,
        "num_format": "0", "align": "right", "bg_color": "#E5F4EB", "font_color": "#17644B"})
    missing_total = workbook.add_format({**base, "bold": True, "font_size": 18,
        "num_format": "0", "align": "right", "bg_color": "#FFF0EC", "font_color": "#A33F32"})
    rule = {"bottom": 1, "bottom_color": "#E4E9EC"}
    row_text = [workbook.add_format({**base, **rule, "text_wrap": True, "bg_color": color})
                for color in ("#FFFFFF", "#F5F8F9")]
    row_number = [workbook.add_format({**base, **rule, "num_format": "0", "align": "right",
        "bg_color": color}) for color in ("#FFFFFF", "#F5F8F9")]
    title = workbook.add_format({**base, "font_size": 16, "bold": True, "font_color": "#203C48"})
    note = workbook.add_format({**base, "font_color": "#62727A"})
    section = workbook.add_format({**base, "bold": True, "font_size": 12})
    header = workbook.add_format({**base, "bold": True, "font_color": "#FFFFFF",
        "bg_color": "#275763", "text_wrap": True, "align": "center", "bottom": 1,
        "bottom_color": "#FFFFFF"})
    green = workbook.add_format({"bg_color": "#E5F4EB", "font_color": "#17644B"})
    neutral = workbook.add_format({"bg_color": "#F2F4F6", "font_color": "#6A737C"})
    missing = workbook.add_format({"bg_color": "#FFF0EC", "font_color": "#A33F32"})
    moment = (generated_at or datetime.now(UTC)).astimezone(ZoneInfo("Europe/Moscow"))
    scope = "Все ученики" if include_inactive else "Обучающиеся"
    for sheet in (summary, detail):
        sheet.hide_gridlines(2)
        sheet.set_default_row(24)
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_paper(9)
        sheet.set_margins(0.25, 0.25, 0.4, 0.4)
        sheet.write_string(1, 0, "Подключения учеников", title)
        sheet.set_row(1, 28)
        sheet.write_string(2, 0, f"{tenant_name} · {moment:%d.%m.%Y %H:%M} · {scope}", note)
        sheet.set_row(3, 8)
        sheet.set_row(4, 8)
        sheet.set_header("&LAlgo MAX&RПодключения учеников")
        sheet.set_footer("&RСтраница &P из &N")
    summary.set_tab_color("#275763")
    detail.set_tab_color("#A4C6CB")
    detail.set_column("A:A", 52, wrapped)
    detail.set_column("B:B", 20, identifier)
    detail.set_column("C:C", 30, wrapped)
    detail.set_column("D:E", 21, checkbox)
    detail.set_column("F:F", 30, wrapped)
    detail.set_column("G:G", 38, wrapped)
    detail.set_column("H:H", 17, body)
    headers = ["Группа", "ID ученика", "Ребёнок", "Ребёнок подключён",
               "Родитель подключён", "Преподаватель", "Площадка", "Статус"]
    states = {StudentStatus.ACTIVE: "Обучается", StudentStatus.DEPARTED: "Выбыл",
              StudentStatus.ARCHIVED: "Архив"}
    for row_index, student in enumerate(students, start=6):
        values = [student.group_name, student.lms_student_id or "", student.display_name,
                  student.student_connected, student.parent_connected, student.teacher_name,
                  student.venue_name, states[student.status]]
        for col, value in enumerate(values):
            if col in (3, 4):
                detail.insert_checkbox(row_index, col, value, checkbox)
            else:
                detail.write_string(row_index, col, str(value), identifier if col == 1 else wrapped)
        lines = max((len(str(values[col])) + width - 1) // width
                    for col, width in [(0, 48), (2, 28), (5, 28), (6, 35)])
        detail.set_row(row_index, max(24, lines * 14))
    last_row = len(students) + 5
    detail.add_table(5, 0, last_row, 7, {
        "name": "ConnectionStudents", "style": "Table Style Light 9",
        "columns": [{"header": label, "header_format": header} for label in headers],
    })
    detail.set_row(5, 34)
    detail.freeze_panes(6, 3)
    detail.repeat_rows(5)
    for col in (3, 4):
        letter = xl_col_to_name(col)
        for boolean, style in [("TRUE", green), ("FALSE", neutral)]:
            detail.conditional_format(6, col, last_row, col, {
                "type": "formula", "criteria": f"={letter}7={boolean}", "format": style,
            })

    summary.set_column("A:A", 52, wrapped)
    summary.set_column("B:C", 29, wrapped)
    summary.set_column("D:D", 12, number)
    summary.set_column("E:H", 17, number)
    summary.set_row(5, 32)
    for col, label in enumerate([
        "Подключения", "Учеников", "Подключены", "Не подключены", "% подключений",
    ]):
        summary.write_string(5, col, label, header)
    data_end = last_row + 1
    ranges = {field: f"'Ученики'!${col}$7:${col}${data_end}" for field, col in [
        ("group_name", "A"), ("teacher_name", "F"), ("venue_name", "G"),
        ("student_connected", "D"), ("parent_connected", "E"),
    ]}
    child_count = sum(s.student_connected for s in students)
    parent_count = sum(s.parent_connected for s in students)
    totals = [(6, "student_connected", "Дети", child_count),
              (7, "parent_connected", "Родители", parent_count)]
    for row, field, label, count in totals:
        summary.set_row(row, 36)
        summary.write_string(row, 0, label, body)
        summary.write_formula(row, 1, f"=COUNTA('Ученики'!$C$7:$C${data_end})", total,
                              len(students))
        summary.write_formula(row, 2, f"=SUMPRODUCT(--({ranges[field]}=TRUE))",
                              connected_total, count)
        summary.write_formula(row, 3, f"=B{row + 1}-C{row + 1}",
                              missing_total, len(students) - count)
        summary.write_formula(row, 4, f"=IF(B{row + 1}=0,0,C{row + 1}/B{row + 1})", percent,
                              count / len(students))
    for row, label, value in [(9, "Подключены оба", True),
                              (10, "Никто не подключён", False)]:
        summary.write_string(row, 0, label, body)
        boolean = str(value).upper()
        formula = f"=SUMPRODUCT(({ranges['student_connected']}={boolean})*"
        formula += f"({ranges['parent_connected']}={boolean}))"
        count = sum(s.student_connected == value and s.parent_connected == value for s in students)
        summary.write_formula(row, 1, formula, number, count)

    def breakdown(start, label, dimensions):
        summary.write_string(start, 0, label, section)
        first = len(dimensions)
        summary.merge_range(start, first + 1, start, first + 2, "Дети", header)
        summary.merge_range(start, first + 3, start, first + 4, "Родители", header)
        labels = [label for _, label in dimensions]
        labels += ["Учеников", "Подключены", "Не подключены", "Подключены", "Не подключены"]
        for col, text in enumerate(labels):
            summary.write_string(start + 1, col, text, header)
        summary.set_row(start + 1, 34)
        groups = defaultdict(list)
        for student in students:
            groups[tuple(getattr(student, field) for field, _ in dimensions)].append(student)
        for row, (key, members) in enumerate(sorted(groups.items()), start=start + 2):
            stripe = (row - start) % 2
            for col, text in enumerate(key):
                summary.write_string(row, col, text, row_text[stripe])
            summary.set_row(row, max(28, ((len(key[0]) + 47) // 48) * 14))
            factors = []
            for col, (field, _) in enumerate(dimensions):
                reference = f"{xl_col_to_name(col)}{row + 1}"
                factors.append(f"--({ranges[field]}={reference})")
            # Exact comparisons also work for names containing *, ? or =.
            common = "*".join(factors)
            summary.write_formula(row, first, f"=SUMPRODUCT({common})",
                                  row_number[stripe], len(members))
            for offset, field in [(1, "student_connected"), (3, "parent_connected")]:
                count = sum(getattr(student, field) for student in members)
                summary.write_formula(row, first + offset,
                    f"=SUMPRODUCT({common}*({ranges[field]}=TRUE))", row_number[stripe], count)
                total_cell = f"{xl_col_to_name(first)}{row + 1}"
                yes_cell = f"{xl_col_to_name(first + offset)}{row + 1}"
                summary.write_formula(row, first + offset + 1,
                    f"={total_cell}-{yes_cell}", row_number[stripe], len(members) - count)
        end = start + 1 + len(groups)
        for offset, style in [(1, green), (2, missing), (3, green), (4, missing)]:
            summary.conditional_format(start + 2, first + offset, end, first + offset, {
                "type": "cell", "criteria": ">", "value": 0, "format": style,
            })
        return start + 2 + len(groups) + 2

    next_row = breakdown(13, "По группам", [("group_name", "Группа"),
        ("venue_name", "Площадка"), ("teacher_name", "Преподаватель")])
    next_row = breakdown(next_row, "По преподавателям", [("teacher_name", "Преподаватель")])
    breakdown(next_row, "По площадкам", [("venue_name", "Площадка")])
    workbook.close()
    return output.getvalue()
