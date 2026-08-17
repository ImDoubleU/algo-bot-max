from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import LedgerDirection, StudentStatus
from app.models.student import AstrocoinLedgerEntry, Student, Wallet
from app.models.tenant import Tenant
from app.services.crm_sync import ensure_wallet

BIRTHDAY_GIFT_AMOUNT = 50
BIRTHDAY_GIFT_REASON = "Подарок на день рождения"


@dataclass(frozen=True)
class BirthdayRewardResult:
    reward_date: date
    eligible_students: int
    credited_students: int
    already_credited_students: int
    credited_student_ids: tuple[UUID, ...]


def has_birthday_on(birth_date: date, reward_date: date) -> bool:
    if (birth_date.month, birth_date.day) == (reward_date.month, reward_date.day):
        return True
    return (
        birth_date.month == 2
        and birth_date.day == 29
        and reward_date.month == 2
        and reward_date.day == 28
        and not calendar.isleap(reward_date.year)
    )


def birthday_idempotency_key(*, student_id: UUID, year: int) -> str:
    return f"birthday_reward:{year}:{student_id}"


async def grant_birthday_rewards(
    db: AsyncSession,
    *,
    reward_date: date,
) -> BirthdayRewardResult:
    rows = (
        await db.execute(
            select(Student, Tenant)
            .join(Tenant, Tenant.id == Student.tenant_id)
            .where(
                Student.status == StudentStatus.ACTIVE,
                Student.birth_date.is_not(None),
            )
            .order_by(Student.tenant_id, Student.id)
        )
    ).all()
    candidates = [
        (student, tenant)
        for student, tenant in rows
        if student.birth_date and has_birthday_on(student.birth_date, reward_date)
    ]
    if not candidates:
        return BirthdayRewardResult(reward_date, 0, 0, 0, ())

    keys = {
        student.id: birthday_idempotency_key(
            student_id=UUID(str(student.id)),
            year=reward_date.year,
        )
        for student, _ in candidates
    }
    existing_keys = set(
        (
            await db.scalars(
                select(AstrocoinLedgerEntry.idempotency_key).where(
                    AstrocoinLedgerEntry.idempotency_key.in_(keys.values())
                )
            )
        ).all()
    )
    credited_ids: list[UUID] = []
    already_credited = 0

    for student, tenant in candidates:
        key = keys[student.id]
        if key in existing_keys:
            already_credited += 1
            continue

        await ensure_wallet(db, tenant=tenant, student=student)
        wallet = await db.scalar(
            select(Wallet).where(Wallet.student_id == student.id).with_for_update()
        )
        if wallet is None:
            continue

        try:
            async with db.begin_nested():
                db.add(
                    AstrocoinLedgerEntry(
                        tenant_id=tenant.id,
                        wallet_id=wallet.id,
                        student_id=student.id,
                        idempotency_key=key,
                        direction=LedgerDirection.CREDIT,
                        amount=BIRTHDAY_GIFT_AMOUNT,
                        reason=BIRTHDAY_GIFT_REASON,
                        comment=f"Подарок за {reward_date.year} год",
                    )
                )
                await db.flush()
        except IntegrityError:
            already_credited += 1
            continue

        wallet.balance += BIRTHDAY_GIFT_AMOUNT
        credited_ids.append(UUID(str(student.id)))
        db.add(
            AuditLog(
                tenant_id=tenant.id,
                action="astrocoins.birthday_rewarded",
                entity_type="student",
                entity_id=str(student.id),
                payload={
                    "student_name": student.display_name,
                    "birth_date": student.birth_date.isoformat(),
                    "reward_date": reward_date.isoformat(),
                    "amount": BIRTHDAY_GIFT_AMOUNT,
                },
            )
        )

    await db.commit()
    return BirthdayRewardResult(
        reward_date=reward_date,
        eligible_students=len(candidates),
        credited_students=len(credited_ids),
        already_credited_students=already_credited,
        credited_student_ids=tuple(credited_ids),
    )
