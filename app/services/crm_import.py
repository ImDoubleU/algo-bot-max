from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


class CrmImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrmStudentRow:
    row_number: int
    deal_id: str | None
    uuid: str | None
    lms_student_id: str | None
    first_name: str | None
    last_name: str | None
    group_name: str | None
    course_name: str | None
    venue_name: str | None
    teacher_name: str | None
    city: str | None
    status_name: str | None
    contact_ids: str | None
    contact_names: str | None

    @property
    def needs_generated_access_code(self) -> bool:
        return not self.contact_ids


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "deal_id": (
        "id \u0441\u0434\u0435\u043b\u043a\u0438",
        "id",
        "\u043d\u043e\u043c\u0435\u0440 \u0441\u0434\u0435\u043b\u043a\u0438",
    ),
    "uuid": ("uuid",),
    "lms_student_id": (
        "id \u0443\u0447\u0435\u043d\u0438\u043a\u0430",
        "id \u0440\u0435\u0431\u0435\u043d\u043a\u0430",
        "id \u0440\u0435\u0431\u0451\u043d\u043a\u0430",
        "student id",
        "lms student id",
        "backoffice_id",
    ),
    "first_name": (
        "\u0438\u043c\u044f \u0440\u0435\u0431\u0435\u043d\u043a\u0430 \u0438\u0437 lms",
        "\u0438\u043c\u044f \u0440\u0435\u0431\u0451\u043d\u043a\u0430 \u0438\u0437 lms",
        "\u0438\u043c\u044f \u0440\u0435\u0431\u0435\u043d\u043a\u0430",
        "\u0438\u043c\u044f \u0440\u0435\u0431\u0451\u043d\u043a\u0430",
    ),
    "last_name": (
        "\u0444\u0430\u043c\u0438\u043b\u0438\u044f \u0440\u0435\u0431\u0435\u043d\u043a\u0430 \u0438\u0437 lms",  # noqa: E501
        "\u0444\u0430\u043c\u0438\u043b\u0438\u044f \u0440\u0435\u0431\u0451\u043d\u043a\u0430 \u0438\u0437 lms",  # noqa: E501
        "\u0444\u0430\u043c\u0438\u043b\u0438\u044f \u0440\u0435\u0431\u0435\u043d\u043a\u0430",
        "\u0444\u0430\u043c\u0438\u043b\u0438\u044f \u0440\u0435\u0431\u0451\u043d\u043a\u0430",
    ),
    "group_name": (
        "\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0433\u0440\u0443\u043f\u043f\u044b lms",
        "\u0433\u0440\u0443\u043f\u043f\u0430 lms",
        "\u0433\u0440\u0443\u043f\u043f\u0430",
    ),
    "course_name": (
        "\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043a\u0443\u0440\u0441\u0430 \u0438\u0437 lms",  # noqa: E501
        "\u043a\u0443\u0440\u0441",
        "\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043a\u0443\u0440\u0441\u0430",
    ),
    "venue_name": (
        "\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043f\u043b\u043e\u0449\u0430\u0434\u043a\u0438",  # noqa: E501
        "\u043f\u043b\u043e\u0449\u0430\u0434\u043a\u0430",
        "\u043f\u043b\u043e\u0449\u0430\u0434\u043a\u0430 lms",
    ),
    "teacher_name": (
        "\u043f\u0440\u0435\u043f\u043e\u0434\u0430\u0432\u0430\u0442\u0435\u043b\u044c",
        "\u043f\u0435\u0434\u0430\u0433\u043e\u0433",
    ),
    "city": ("\u0433\u043e\u0440\u043e\u0434",),
    "status_name": (
        "\u0438\u043c\u044f \u0441\u0442\u0430\u0442\u0443\u0441\u0430",
        "\u0441\u0442\u0430\u0442\u0443\u0441",
        "\u0441\u0442\u0430\u0434\u0438\u044f",
    ),
    "contact_ids": (
        "id \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043e\u0432",
        "id \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u0430",
        "contact id",
        "contact ids",
    ),
    "contact_names": (
        "\u0438\u043c\u0435\u043d\u0430 \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043e\u0432",
        "\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u044b",
        "\u0438\u043c\u044f \u043a\u043e\u043d\u0442\u0430\u043a\u0442\u0430",
    ),
}


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def normalize_header(value: Any) -> str:
    text = normalize_text(value) or ""
    return text.lower().replace("\u0451", "\u0435")


def get_cell(row: dict[str, Any], field: str) -> str | None:
    for alias in HEADER_ALIASES[field]:
        value = row.get(alias.replace("\u0451", "\u0435"))
        if value is not None:
            return normalize_text(value)
    return None


def find_header_mapping(values: tuple[Any, ...]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    known_headers = {
        alias.replace("\u0451", "\u0435")
        for aliases in HEADER_ALIASES.values()
        for alias in aliases
    }

    for index, value in enumerate(values):
        header = normalize_header(value)
        if header in known_headers:
            mapping[index] = header

    return mapping


def parse_crm_students(
    path: str | Path,
    *,
    sheet_name: str = "\u0421\u0434\u0435\u043b\u043a\u0438",
) -> list[CrmStudentRow]:
    workbook_path = Path(path)
    if not workbook_path.exists():
        raise CrmImportError(f"CRM file not found: {workbook_path}")

    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        return parse_crm_workbook(workbook, sheet_name=sheet_name)
    finally:
        workbook.close()


def parse_crm_students_content(
    content: bytes,
    *,
    sheet_name: str = "\u0421\u0434\u0435\u043b\u043a\u0438",
) -> list[CrmStudentRow]:
    if not content:
        raise CrmImportError("CRM file is empty")
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise CrmImportError("CRM file is not a readable XLSX workbook") from exc
    try:
        return parse_crm_workbook(workbook, sheet_name=sheet_name)
    finally:
        workbook.close()


def parse_crm_workbook(
    workbook: Any,
    *,
    sheet_name: str,
) -> list[CrmStudentRow]:
    if sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
    else:
        sheet = None
        best_score = 0
        for candidate in workbook.worksheets:
            score = max(
                (
                    len(find_header_mapping(tuple(values)))
                    for _, values in zip(
                        range(30),
                        candidate.iter_rows(values_only=True),
                        strict=False,
                    )
                ),
                default=0,
            )
            if score > best_score:
                best_score = score
                sheet = candidate
        if sheet is None or best_score < 2:
            raise CrmImportError(f"Sheet not found: {sheet_name}")

    header_mapping: dict[int, str] | None = None
    result: list[CrmStudentRow] = []

    for row_number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
        if header_mapping is None:
            candidate = find_header_mapping(values)
            if len(candidate) >= 3:
                header_mapping = candidate
            continue

        row = {header: values[index] for index, header in header_mapping.items()}
        first_name = get_cell(row, "first_name")
        last_name = get_cell(row, "last_name")
        group_name = get_cell(row, "group_name")
        deal_id = get_cell(row, "deal_id")
        contact_ids = get_cell(row, "contact_ids")

        if not any([first_name, last_name, group_name, deal_id, contact_ids]):
            continue

        result.append(
            CrmStudentRow(
                row_number=row_number,
                deal_id=deal_id,
                uuid=get_cell(row, "uuid"),
                lms_student_id=get_cell(row, "lms_student_id"),
                first_name=first_name,
                last_name=last_name,
                group_name=group_name,
                course_name=get_cell(row, "course_name"),
                venue_name=get_cell(row, "venue_name"),
                teacher_name=get_cell(row, "teacher_name"),
                city=get_cell(row, "city"),
                status_name=get_cell(row, "status_name"),
                contact_ids=contact_ids,
                contact_names=get_cell(row, "contact_names"),
            )
        )

    if header_mapping is None:
        raise CrmImportError("CRM header row was not found")

    return result
