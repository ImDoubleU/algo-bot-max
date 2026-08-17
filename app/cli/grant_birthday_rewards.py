from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import app.db.base  # noqa: F401
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.birthday_rewards import grant_birthday_rewards


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grant annual birthday rewards")
    parser.add_argument(
        "--date",
        dest="reward_date",
        help="Override processing date in YYYY-MM-DD format",
    )
    return parser


async def run(reward_date: date) -> dict[str, object]:
    async with AsyncSessionLocal() as db:
        result = await grant_birthday_rewards(db, reward_date=reward_date)
    return {
        "reward_date": result.reward_date.isoformat(),
        "eligible_students": result.eligible_students,
        "credited_students": result.credited_students,
        "already_credited_students": result.already_credited_students,
        "credited_student_ids": [str(student_id) for student_id in result.credited_student_ids],
    }


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    reward_date = (
        date.fromisoformat(args.reward_date)
        if args.reward_date
        else datetime.now(ZoneInfo(settings.app_timezone)).date()
    )
    print(json.dumps(asyncio.run(run(reward_date)), ensure_ascii=False))


if __name__ == "__main__":
    main()
