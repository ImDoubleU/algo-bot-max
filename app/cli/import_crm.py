from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.crm_import import parse_crm_students
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Импорт CRM XLSX в локальную базу бота")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Путь к CRM XLSX. Если не задан, берется CRM_ACTIVE_EXPORT_PATH из .env.",
    )
    parser.add_argument(
        "--sheet-name",
        default="Сделки",
        help="Название листа CRM в XLSX.",
    )
    parser.add_argument(
        "--partner-slug",
        required=True,
        help="Короткий slug партнера, например partner-a.",
    )
    parser.add_argument(
        "--partner-name",
        required=True,
        help="Название партнера для отображения.",
    )
    parser.add_argument(
        "--fallback-city-name",
        default="Нижний Новгород",
        help="Город по умолчанию, если в строке CRM нет города.",
    )
    return parser.parse_args()


async def run_import(args: argparse.Namespace) -> dict[str, int]:
    settings = get_settings()
    source_path = args.path or settings.crm_active_export_path
    if not source_path:
        raise SystemExit("Укажите --path или заполните CRM_ACTIVE_EXPORT_PATH в .env.")

    rows = parse_crm_students(source_path, sheet_name=args.sheet_name)
    async with AsyncSessionLocal() as db:
        result = await upsert_crm_student_rows(
            db,
            rows,
            defaults=CrmSyncDefaults(
                partner_slug=args.partner_slug,
                partner_name=args.partner_name,
                fallback_city_name=args.fallback_city_name,
            ),
        )
    return result.__dict__


def main() -> int:
    result = asyncio.run(run_import(parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
