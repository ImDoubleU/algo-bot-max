from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, is_local_environment, is_placeholder
from app.models.account import MaxAccount, StaffRoleAssignment, StaffVenueScope
from app.models.audit import AuditLog
from app.models.enums import AssignmentStatus, StaffRole
from app.models.tenant import Tenant, Venue


class StaffServiceError(RuntimeError):
    pass


def configured_superadmin_max_user_id() -> int | None:
    raw_user_id = get_settings().initial_superadmin_max_user_id
    if is_placeholder(raw_user_id) or not str(raw_user_id).isdigit():
        return None
    user_id = int(str(raw_user_id))
    return user_id if user_id > 0 else None


def superadmin_identity_is_allowed(max_user_id: int) -> bool:
    configured_user_id = configured_superadmin_max_user_id()
    if configured_user_id is None:
        return is_local_environment(get_settings().app_env)
    return max_user_id == configured_user_id


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


def teacher_staff_name(account: MaxAccount) -> str | None:
    if account.staff_profile_completed_at:
        parts = [account.staff_last_name, account.staff_first_name]
        value = " ".join(part.strip() for part in parts if part and part.strip())
        if value:
            return value
    legacy_name = (account.display_name or "").strip()
    return legacy_name or None


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
    configured_user_id = configured_superadmin_max_user_id()
    assignment_id = await db.scalar(
        select(StaffRoleAssignment.id)
        .join(MaxAccount, MaxAccount.id == StaffRoleAssignment.account_id)
        .where(
            StaffRoleAssignment.account_id == account_id,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            StaffRoleAssignment.role == StaffRole.SUPERADMIN,
            *(
                [MaxAccount.max_user_id == configured_user_id]
                if configured_user_id is not None
                else []
            ),
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
    global_superadmin = await is_global_superadmin(db, account_id=account_id)
    if StaffRole.SUPERADMIN in roles and not global_superadmin:
        roles.discard(StaffRole.SUPERADMIN)
    if (
        allowed_roles is None or StaffRole.SUPERADMIN in allowed_roles
    ) and global_superadmin:
        roles.add(StaffRole.SUPERADMIN)
    return roles


async def staff_venue_scope_ids(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    role: StaffRole,
) -> set[UUID] | None:
    if role != StaffRole.PARTNER_DIRECTOR:
        return None
    assignment = await db.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.tenant_id == tenant_id,
            StaffRoleAssignment.account_id == account_id,
            StaffRoleAssignment.role == role,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
        )
    )
    if assignment is None:
        return set()
    scope_ids = set(
        (
            await db.scalars(
                select(StaffVenueScope.venue_id).where(
                    StaffVenueScope.assignment_id == assignment.id
                )
            )
        ).all()
    )
    return scope_ids or None


async def replace_director_venue_scopes(
    db: AsyncSession,
    *,
    tenant_slug: str,
    max_user_id: int,
    venue_names: list[str],
) -> list[str]:
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise StaffServiceError(f"Город не найден: {tenant_slug}")
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise StaffServiceError(f"MAX-аккаунт не найден: {max_user_id}")
    assignment = await db.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == account.id,
            StaffRoleAssignment.role == StaffRole.PARTNER_DIRECTOR,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
        )
    )
    if assignment is None:
        raise StaffServiceError("Сначала назначьте пользователю роль директора в этом городе")
    normalized_names = {name.strip().casefold() for name in venue_names if name.strip()}
    venues = list(
        (
            await db.scalars(
                select(Venue).where(
                    Venue.tenant_id == tenant.id,
                )
            )
        ).all()
    )
    selected = [venue for venue in venues if venue.name.casefold() in normalized_names]
    if len(selected) != len(normalized_names):
        found = {venue.name.casefold() for venue in selected}
        missing = sorted(normalized_names - found)
        raise StaffServiceError(f"Площадки не найдены: {', '.join(missing)}")
    existing = list(
        (
            await db.scalars(
                select(StaffVenueScope).where(StaffVenueScope.assignment_id == assignment.id)
            )
        ).all()
    )
    for scope in existing:
        await db.delete(scope)
    for venue in selected:
        db.add(StaffVenueScope(assignment_id=assignment.id, venue_id=venue.id))
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="staff_director.venue_scope_updated",
            entity_type="staff_role_assignment",
            entity_id=str(assignment.id),
            payload={"venue_names": [venue.name for venue in selected]},
        )
    )
    await db.commit()
    return [venue.name for venue in selected]


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
    if role == StaffRole.SUPERADMIN and not superadmin_identity_is_allowed(max_user_id):
        raise StaffServiceError(
            "Роль суперадминистра можно выдать только MAX ID из "
            "INITIAL_SUPERADMIN_MAX_USER_ID"
        )
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise StaffServiceError(f"Партнер не найден: {tenant_slug}")

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
