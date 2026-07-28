from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import AssignmentStatus, StaffRole
from app.models.tenant import Tenant


class StaffServiceError(RuntimeError):
    pass


def normalize_staff_name(value: str | None) -> str:
    return " ".join(re.findall(r"[a-zа-яё0-9]+", (value or "").casefold()))


def staff_names_match(left: str | None, right: str | None) -> bool:
    left_tokens = normalize_staff_name(left).split()
    right_tokens = normalize_staff_name(right).split()
    if not left_tokens or not right_tokens:
        return False
    if sorted(left_tokens) == sorted(right_tokens):
        return True

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    shared_names = {token for token in left_set & right_set if len(token) > 2}
    if not shared_names:
        return False

    left_remaining = [token for token in left_tokens if token not in shared_names]
    right_remaining = [token for token in right_tokens if token not in shared_names]
    left_full_names = {token for token in left_remaining if len(token) > 2}
    right_full_names = {token for token in right_remaining if len(token) > 2}
    if left_full_names and right_full_names and not left_full_names & right_full_names:
        return False
    left_initials = {token[0] for token in left_remaining}
    right_initials = {token[0] for token in right_remaining}
    return not left_initials or not right_initials or bool(left_initials & right_initials)


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


async def is_global_superadmin(
    db: AsyncSession,
    *,
    account_id: UUID,
) -> bool:
    """A superadmin assignment grants access to every active tenant."""
    assignment_id = await db.scalar(
        select(StaffRoleAssignment.id)
        .where(
            StaffRoleAssignment.account_id == account_id,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            StaffRoleAssignment.role == StaffRole.SUPERADMIN,
        )
        .limit(1)
    )
    return assignment_id is not None


async def active_staff_roles_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    allowed_roles: set[StaffRole] | None = None,
) -> set[StaffRole]:
    """Return tenant roles and the global superadmin role when applicable."""
    query = select(StaffRoleAssignment.role).where(
        StaffRoleAssignment.tenant_id == tenant_id,
        StaffRoleAssignment.account_id == account_id,
        StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
    )
    if allowed_roles is not None:
        query = query.where(StaffRoleAssignment.role.in_(allowed_roles))

    roles = set((await db.scalars(query)).all())
    if (
        allowed_roles is None or StaffRole.SUPERADMIN in allowed_roles
    ) and await is_global_superadmin(db, account_id=account_id):
        roles.add(StaffRole.SUPERADMIN)
    return roles


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
