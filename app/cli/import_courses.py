from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

import app.db.base  # noqa: F401
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.tenant import Tenant
from app.services.course_import import CourseImportError, import_courses_for_tenant


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Импортировать курсы старого TG-бота")
    parser.add_argument("--tenant-slug", default=settings.default_tenant_slug)
    parser.add_argument("--source", type=Path, default=Path(settings.courses_json_path))
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, int | str]:
    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == args.tenant_slug))
        if tenant is None:
            raise CourseImportError(f"Tenant не найден: {args.tenant_slug}")
        return await import_courses_for_tenant(db, tenant=tenant, source_path=args.source)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = asyncio.run(run(parse_args()))
    except CourseImportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
