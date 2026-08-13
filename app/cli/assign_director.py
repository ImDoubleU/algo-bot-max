from __future__ import annotations

import argparse
import asyncio
import json
import sys

import app.db.base  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.models.enums import StaffRole
from app.services.staff import (
    StaffServiceError,
    bootstrap_staff_role,
    replace_director_venue_scopes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Назначить директору город и при необходимости ограничить площадками",
    )
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--max-user-id", required=True, type=int)
    parser.add_argument("--display-name", default=None)
    parser.add_argument(
        "--venue",
        action="append",
        default=[],
        help="Название доступной площадки. Можно указать несколько раз. Без параметра доступен весь город.",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, object]:
    async with AsyncSessionLocal() as db:
        await bootstrap_staff_role(
            db,
            tenant_slug=args.tenant_slug,
            max_user_id=args.max_user_id,
            role=StaffRole.PARTNER_DIRECTOR,
            display_name=args.display_name,
        )
        venues = await replace_director_venue_scopes(
            db,
            tenant_slug=args.tenant_slug,
            max_user_id=args.max_user_id,
            venue_names=args.venue,
        )
    return {
        "tenant_slug": args.tenant_slug,
        "max_user_id": args.max_user_id,
        "venues": venues,
        "scope": "selected_venues" if venues else "whole_city",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = asyncio.run(run(parse_args()))
    except StaffServiceError as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
