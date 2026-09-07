from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import app.db.base  # noqa: F401
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.bank import process_bank_accounts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process daily Algo MAX bank interest")
    parser.add_argument(
        "--date",
        dest="processing_date",
        help="Override processing date in YYYY-MM-DD format",
    )
    return parser


async def run(processing_date: date) -> dict[str, object]:
    async with AsyncSessionLocal() as db:
        result = await process_bank_accounts(db, processing_date=processing_date)
    return {
        "processing_date": result.processing_date.isoformat(),
        "processed_deposits": result.processed_deposits,
        "processed_days": result.processed_days,
        "capitalizations": result.capitalizations,
        "matured_deposits": result.matured_deposits,
        "inactive_deposits": result.inactive_deposits,
    }


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    processing_date = (
        date.fromisoformat(args.processing_date)
        if args.processing_date
        else datetime.now(ZoneInfo(settings.app_timezone)).date()
    )
    print(json.dumps(asyncio.run(run(processing_date)), ensure_ascii=False))


if __name__ == "__main__":
    main()
