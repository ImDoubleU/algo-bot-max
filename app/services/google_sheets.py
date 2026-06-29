from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import get_settings

SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


class GoogleSheetsError(RuntimeError):
    pass


class GoogleSheetsClient:
    def __init__(
        self,
        *,
        service_account_file: str | None = None,
        spreadsheet_id: str | None = None,
        spreadsheet: Any | None = None,
    ) -> None:
        if spreadsheet is not None:
            self.spreadsheet = spreadsheet
            return

        if not service_account_file:
            raise GoogleSheetsError("Не указан GOOGLE_SERVICE_ACCOUNT_FILE.")
        if not spreadsheet_id:
            raise GoogleSheetsError("Не указан GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID.")

        try:
            import gspread
        except ImportError as exc:
            raise GoogleSheetsError("Пакет gspread не установлен.") from exc

        client = gspread.service_account(
            filename=service_account_file,
            scopes=list(SHEETS_SCOPES),
        )
        self.spreadsheet = client.open_by_key(spreadsheet_id)

    @classmethod
    def from_settings(cls) -> GoogleSheetsClient:
        settings = get_settings()
        return cls(
            service_account_file=settings.google_service_account_file,
            spreadsheet_id=settings.google_sheets_orders_spreadsheet_id,
        )

    def worksheet(self, name: str) -> Any:
        try:
            return self.spreadsheet.worksheet(name)
        except Exception as exc:  # noqa: BLE001
            raise GoogleSheetsError(f"Лист Google Sheets не найден: {name}") from exc

    def ensure_headers(self, worksheet_name: str, headers: Sequence[str]) -> None:
        sheet = self.worksheet(worksheet_name)
        if sheet.row_values(1):
            return
        sheet.append_row(list(headers), value_input_option="USER_ENTERED")

    def append_named_row(
        self,
        *,
        worksheet_name: str,
        headers: Sequence[str],
        row: Mapping[str, Any],
    ) -> None:
        self.ensure_headers(worksheet_name, headers)
        values = [row.get(header, "") for header in headers]
        self.worksheet(worksheet_name).append_row(values, value_input_option="USER_ENTERED")

    def update_row_by_key(
        self,
        *,
        worksheet_name: str,
        key_column: str,
        key_value: str,
        updates: Mapping[str, Any],
    ) -> int:
        sheet = self.worksheet(worksheet_name)
        headers = sheet.row_values(1)
        if key_column not in headers:
            raise GoogleSheetsError(f"В листе {worksheet_name} нет колонки {key_column}.")

        key_column_number = headers.index(key_column) + 1
        key_values = sheet.col_values(key_column_number)
        row_number = None
        for index, value in enumerate(key_values[1:], start=2):
            if str(value).strip() == key_value:
                row_number = index
                break

        if row_number is None:
            raise GoogleSheetsError(
                f"В листе {worksheet_name} не найдена строка {key_column}={key_value}."
            )

        for column_name, value in updates.items():
            if column_name not in headers:
                raise GoogleSheetsError(f"В листе {worksheet_name} нет колонки {column_name}.")
            sheet.update_cell(row_number, headers.index(column_name) + 1, value)

        return row_number
