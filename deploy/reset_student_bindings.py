"""Reset one student's access bindings; preview by default, retain an audit and backup."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/etc/algo-max/algo-max.env")

from sqlalchemy import select  # noqa: E402

import app.db.base  # noqa: E402, F401
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.enums import StudentAccessStatus  # noqa: E402
from app.models.student import Student, StudentAccessLink  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402


async def reset_bindings(db, student):
    links = (
        await db.scalars(
            select(StudentAccessLink)
            .where(
                StudentAccessLink.student_id == student.id,
                StudentAccessLink.tenant_id == student.tenant_id,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            )
            .with_for_update()
        )
    ).all()
    before = []
    for link in links:
        snapshot = {
            "link_id": str(link.id),
            "account_id": str(link.account_id),
            "student_id": str(student.id),
            "role": link.role.value,
            "status": link.status.value,
            "reason": link.revoked_reason,
            "revoked_at": str(link.revoked_at),
        }
        before.append(snapshot)
        link.status = StudentAccessStatus.REVOKED
        link.revoked_at = datetime.now(UTC)
        link.revoked_reason = "registration_reset"
        db.add(
            AuditLog(
                tenant_id=student.tenant_id,
                action="student_access_link.registration_reset",
                entity_type="student_access",
                entity_id=str(student.id),
                payload={"before": snapshot, "reason": "owner_requested_fresh_registration"},
            )
        )
    await db.flush()
    return before


def save_backup(path, data):
    with Path(path).open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


async def main(tenant_slug, deal_id, apply, backup):
    async with AsyncSessionLocal() as db:
        student = await db.scalar(
            select(Student)
            .join(Tenant, Student.tenant_id == Tenant.id)
            .where(
                Tenant.slug == tenant_slug,
                Student.crm_deal_id == deal_id,
            )
        )
        if student is None:
            raise RuntimeError("Student was not found")
        data = await reset_bindings(db, student)
        if apply:
            await asyncio.to_thread(save_backup, backup, data)
            await db.commit()
        else:
            await db.rollback()
        print(json.dumps({"applied": apply, "reset_links": len(data)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--deal-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="/tmp/student-registration-reset-before.json")
    args = parser.parse_args()
    asyncio.run(main(args.tenant, args.deal_id, args.apply, args.backup))
