from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.models.account import MaxAccount
from app.models.enums import OrderStatus
from app.models.store import Order
from app.models.student import Student
from app.services.google_sheets import GoogleSheetsClient
from app.services.order_sheets import order_item_mapping, upsert_order_sheet_row


class FakeWorksheet:
    def __init__(self) -> None:
        self.rows: list[list[Any]] = []

    def row_values(self, row_number: int) -> list[Any]:
        if row_number > len(self.rows):
            return []
        return self.rows[row_number - 1]

    def col_values(self, column_number: int) -> list[Any]:
        result = []
        for row in self.rows:
            result.append(row[column_number - 1] if len(row) >= column_number else "")
        return result

    def append_row(self, values: list[Any], *, value_input_option: str) -> None:
        assert value_input_option == "USER_ENTERED"
        self.rows.append(list(values))

    def update_cell(self, row_number: int, column_number: int, value: Any) -> None:
        while row_number > len(self.rows):
            self.rows.append([])
        row = self.rows[row_number - 1]
        while column_number > len(row):
            row.append("")
        row[column_number - 1] = value


class FakeSpreadsheet:
    def __init__(self) -> None:
        self.sheets = {"orders": FakeWorksheet()}

    def worksheet(self, name: str) -> FakeWorksheet:
        return self.sheets[name]


def test_append_named_row_creates_headers_and_appends_values() -> None:
    spreadsheet = FakeSpreadsheet()
    client = GoogleSheetsClient(spreadsheet=spreadsheet)

    client.append_named_row(
        worksheet_name="orders",
        headers=["order_number", "status", "total_astrocoins"],
        row={
            "order_number": "42",
            "status": "created",
            "total_astrocoins": 150,
        },
    )

    assert spreadsheet.worksheet("orders").rows == [
        ["order_number", "status", "total_astrocoins"],
        ["42", "created", 150],
    ]


def test_update_row_by_key_updates_existing_row() -> None:
    spreadsheet = FakeSpreadsheet()
    sheet = spreadsheet.worksheet("orders")
    sheet.rows = [
        ["order_number", "status", "comment"],
        ["42", "created", ""],
    ]
    client = GoogleSheetsClient(spreadsheet=spreadsheet)

    row_number = client.update_row_by_key(
        worksheet_name="orders",
        key_column="order_number",
        key_value="42",
        updates={"status": "issued_to_student", "comment": "Выдано"},
    )

    assert row_number == 2
    assert sheet.rows[1] == ["42", "issued_to_student", "Выдано"]


def test_upsert_order_sheet_row_appends_missing_order() -> None:
    spreadsheet = FakeSpreadsheet()
    client = GoogleSheetsClient(spreadsheet=spreadsheet)
    order = Order(
        id=uuid4(),
        tenant_id=uuid4(),
        student_id=uuid4(),
        order_number=42,
        status=OrderStatus.RESERVED,
        total_astrocoins=240,
        venue_name="Союзный 45",
        teacher_name="Олейник Д",
    )
    student = Student(
        id=order.student_id,
        tenant_id=order.tenant_id,
        student_access_code="681",
        first_name="Алиса",
    )
    account = MaxAccount(max_user_id=53364725)

    upsert_order_sheet_row(
        client=client,
        tenant_slug="nizhniy-novgorod-partner-a",
        order=order,
        student=student,
        account=account,
        items=[
            order_item_mapping(
                product_id=str(uuid4()),
                product_name="Ручка",
                quantity=2,
                warehouse_id=str(uuid4()),
                warehouse_name="Союзный 45",
                unit_price_astrocoins=120,
                total_price_astrocoins=240,
            )
        ],
    )

    sheet = spreadsheet.worksheet("orders")
    assert sheet.rows[0][0] == "order_number"
    assert sheet.rows[1][0] == "42"
    assert sheet.rows[1][6] == "reserved"
    assert "Ручка" in sheet.rows[1][8]


def test_upsert_order_sheet_row_updates_existing_order() -> None:
    spreadsheet = FakeSpreadsheet()
    sheet = spreadsheet.worksheet("orders")
    sheet.rows = [
        [
            "order_number",
            "created_at",
            "tenant_slug",
            "max_user_id",
            "student_id",
            "student_name",
            "status",
            "total_astrocoins",
            "items_json",
            "venue_name",
            "teacher_name",
            "comment",
        ],
        ["42", "", "", "", "", "", "reserved", "", "", "", "", ""],
    ]
    client = GoogleSheetsClient(spreadsheet=spreadsheet)
    order = Order(
        id=uuid4(),
        tenant_id=uuid4(),
        student_id=uuid4(),
        order_number=42,
        status=OrderStatus.ISSUED_TO_STUDENT,
        total_astrocoins=240,
    )
    student = Student(
        id=order.student_id,
        tenant_id=order.tenant_id,
        student_access_code="681",
        first_name="Алиса",
    )
    account = MaxAccount(max_user_id=53364725)

    upsert_order_sheet_row(
        client=client,
        tenant_slug="nizhniy-novgorod-partner-a",
        order=order,
        student=student,
        account=account,
        items=[],
        comment="Выдано",
    )

    assert sheet.rows[1][6] == "issued_to_student"
    assert sheet.rows[1][11] == "Выдано"
