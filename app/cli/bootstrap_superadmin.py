from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

import app.db.base  # noqa: F401
from app.core.config import get_settings, is_placeholder
from app.db.session import AsyncSessionLocal
from app.models.enums import StaffRole
from app.services.staff import StaffServiceError, bootstrap_staff_role


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Создать или активировать первичную staff-роль в tenant",
    )
    parser.add_argument("--tenant-slug", default=settings.default_tenant_slug)
    parser.add_argument("--max-user-id", type=int, default=None)
    parser.add_argument("--username", default=settings.initial_superadmin_username)
    parser.add_argument("--display-name", default=None)
    parser.add_argument(
        "--role",
        choices=[role.value for role in StaffRole],
        default=StaffRole.SUPERADMIN.value,
    )
    return parser.parse_args()


async def run_bootstrap(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    raw_user_id = args.max_user_id or settings.initial_superadmin_max_user_id
    if is_placeholder(str(raw_user_id) if raw_user_id is not None else None):
        raise SystemExit(
            "Укажите --max-user-id или заполните INITIAL_SUPERADMIN_MAX_USER_ID в .env."
        )

    async with AsyncSessionLocal() as db:
        result = await bootstrap_staff_role(
            db,
            tenant_slug=args.tenant_slug,
            max_user_id=int(raw_user_id),
            role=StaffRole(args.role),
            username=args.username,
            display_name=args.display_name,
        )
    return asdict(result)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    try:
        result = asyncio.run(run_bootstrap(parse_args()))
    except StaffServiceError as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
