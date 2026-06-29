from __future__ import annotations

from typing import Any

from app.services.google_sheets import GoogleSheetsClient


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
