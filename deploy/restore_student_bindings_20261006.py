"""Restore QR bindings incorrectly revoked by the retired parent-required hotfix."""

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/etc/algo-max/algo-max.env")

from sqlalchemy import select  # noqa: E402

import app.db.base  # noqa: E402, F401
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.enums import (  # noqa: E402
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Student, StudentAccessLink  # noqa: E402
from app.services.access import get_effective_customer_access_link  # noqa: E402


async def restore_bindings(db):
    links = (
        await db.scalars(
            select(StudentAccessLink)
            .join(Student, Student.id == StudentAccessLink.student_id)
            .where(
                StudentAccessLink.role == StudentAccessRole.STUDENT,
                StudentAccessLink.status == StudentAccessStatus.REVOKED,
                StudentAccessLink.source == StudentAccessSource.TEACHER_QR,
                StudentAccessLink.revoked_reason == "parent_required_hotfix",
                StudentAccessLink.tenant_id == Student.tenant_id,
                Student.status == StudentStatus.ACTIVE,
            )
            .with_for_update(of=StudentAccessLink)
        )
    ).all()
    snapshots = []
    for link in links:
        before = {
            "id": str(link.id),
            "tenant_id": str(link.tenant_id),
            "student_id": str(link.student_id),
            "account_id": str(link.account_id),
            "status": link.status.value,
            "reason": link.revoked_reason,
            "revoked_at": str(link.revoked_at),
        }
        snapshots.append(before)
        link.status = StudentAccessStatus.ACTIVE
        link.revoked_reason = None
        link.revoked_at = None
        db.add(
            AuditLog(
                tenant_id=link.tenant_id,
                action="student_qr_access_link.restored",
                entity_type="student_access",
                entity_id=str(link.student_id),
                payload={
                    "link_id": str(link.id),
                    "before": dict(before),
                    "reason": "repair_remaining_parent_required_hotfix_bindings",
                    "parent_gate_preserved": True,
                },
            )
        )
    await db.flush()
    for link, before in zip(links, snapshots, strict=True):
        effective = await get_effective_customer_access_link(
            db,
            tenant_id=link.tenant_id,
            student_id=link.student_id,
            account_id=link.account_id,
            required_role=StudentAccessRole.STUDENT,
        )
        before["effective_access_after"] = effective is not None
    return snapshots


def save_backup(path, data):
    with Path(path).open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


async def main(apply, backup):
    async with AsyncSessionLocal() as db:
        data = await restore_bindings(db)
        if apply:
            await asyncio.to_thread(save_backup, backup, data)
            await db.commit()
        else:
            await db.rollback()
        print(
            json.dumps(
                {
                    "applied": apply,
                    "bindings": len(data),
                    "effective_access": sum(row["effective_access_after"] for row in data),
                    "waiting_for_parent": sum(not row["effective_access_after"] for row in data),
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="/tmp/student-bindings-before-20261006.json")
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.backup))
