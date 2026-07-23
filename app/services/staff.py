from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import AssignmentStatus, StaffRole
from app.models.tenant import Tenant


class StaffServiceError(RuntimeError):
    pass


def normalize_staff_name(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


@dataclass(frozen=True)
class StaffRoleBootstrapResult:
    tenant_slug: str
    max_user_id: int
    role: StaffRole
    account_created: bool
    assignment_created: bool
    assignment_status: AssignmentStatus


async def get_tenant_by_slug(db: AsyncSession, tenant_slug: str) -> Tenant | None:
    return await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug.strip().lower()))


async def get_or_create_max_account(
    db: AsyncSession,
    *,
    max_user_id: int,
    username: str | None = None,
    display_name: str | None = None,
) -> tuple[MaxAccount, bool]:
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is not None:
        if username is not None:
            account.username = username
        if display_name is not None:
            account.display_name = display_name
        return account, False

    account = MaxAccount(
        max_user_id=max_user_id,
        username=username,
        display_name=display_name,
    )
    db.add(account)
    await db.flush()
    return account, True


async def bootstrap_staff_role(
    db: AsyncSession,
    *,
    tenant_slug: str,
    max_user_id: int,
    role: StaffRole = StaffRole.SUPERADMIN,
    username: str | None = None,
    display_name: str | None = None,
) -> StaffRoleBootstrapResult:
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise StaffServiceError(f"Tenant не найден: {tenant_slug}")

    account, account_created = await get_or_create_max_account(
        db,
        max_user_id=max_user_id,
        username=username,
        display_name=display_name,
    )
    assignment = await db.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == account.id,
            StaffRoleAssignment.role == role,
        )
    )

    assignment_created = False
    if assignment is None:
        assignment = StaffRoleAssignment(
            tenant_id=tenant.id,
            account_id=account.id,
            role=role,
            status=AssignmentStatus.ACTIVE,
        )
        db.add(assignment)
        await db.flush()
        assignment_created = True
    elif assignment.status != AssignmentStatus.ACTIVE:
        assignment.status = AssignmentStatus.ACTIVE

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="staff_role.bootstrapped",
            entity_type="staff_role_assignment",
            entity_id=str(assignment.id),
            payload={
                "max_user_id": max_user_id,
                "role": role.value,
                "account_created": account_created,
                "assignment_created": assignment_created,
                "assignment_status": assignment.status.value,
            },
        )
    )
    await db.commit()
    await db.refresh(assignment)

    return StaffRoleBootstrapResult(
        tenant_slug=tenant.slug,
        max_user_id=max_user_id,
        role=role,
        account_created=account_created,
        assignment_created=assignment_created,
        assignment_status=assignment.status,
    )
