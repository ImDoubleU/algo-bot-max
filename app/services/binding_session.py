"""Explain a denied session without confusing binding and school access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import MaxAccount
from app.models.enums import StudentAccessRole, StudentAccessStatus, StudentStatus
from app.models.student import Student, StudentAccessLink
from app.models.tenant import Tenant
from app.services.student_access_policy import student_access_window

NOT_LINKED_MESSAGE = (
    "Этот аккаунт MAX ещё не подключён. Родителю нужно открыть персональную ссылку "
    "из письма школы и выбрать «Я родитель» в боте. Ученику — открыть свой QR-код у преподавателя."
)
SCHOOL_UNAVAILABLE_MESSAGE = (
    "Школа из ссылки недоступна. Откройте свежую ссылку из письма школы. "
    "Если это не помогло, обратитесь к администратору."
)


async def denied_binding_reason(
    db: AsyncSession, *, tenant: Tenant, account: MaxAccount,
) -> tuple[str, str]:
    rows = list((await db.execute(
        select(StudentAccessLink, Student)
        .join(Student, Student.id == StudentAccessLink.student_id)
        .where(StudentAccessLink.tenant_id == tenant.id,
               StudentAccessLink.account_id == account.id)
        .order_by(StudentAccessLink.updated_at.desc())
    )).all())
    active = [(link, student) for link, student in rows
              if link.status == StudentAccessStatus.ACTIVE]
    eligible = [(link, student) for link, student in active
                if link.role == StudentAccessRole.STUDENT
                and student_access_window(student, tenant).allowed]
    if eligible:
        parent_rows = (await db.execute(
            select(StudentAccessLink.id, StudentAccessLink.student_id).where(
                StudentAccessLink.tenant_id == tenant.id,
                StudentAccessLink.student_id.in_([student.id for _, student in eligible]),
                StudentAccessLink.role == StudentAccessRole.PARENT,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            )
        )).all()
        parents = {student_id for _, student_id in parent_rows}
        parent_ids = {parent_id for parent_id, _ in parent_rows}
        if any(student.id not in parents for _, student in eligible):
            return "parent_required", (
                "Профиль ученика привязан. Чтобы открыть личный кабинет, родителю нужно "
                "перейти по персональной ссылке из письма школы и завершить подключение "
                "в боте. После этого нажмите «Проверить доступ»."
            )
        if any(link.sponsor_access_link_id is not None
               and link.sponsor_access_link_id not in parent_ids for link, _ in eligible):
            return "parent_disconnected", (
                "Родитель, выдавший ссылку ученика, отключён. Попросите подключённого "
                "родителя или преподавателя открыть новый QR-код ученика и перейдите по нему."
            )
    if active:
        if all(student.status == StudentStatus.ARCHIVED for _, student in active):
            return "student_archived", (
                "Профиль ученика находится в архиве школы. Обратитесь к преподавателю "
                "или администратору, чтобы проверить статус обучения."
            )
        return "access_expired", (
            "Срок доступа после завершения обучения закончился. Привязка сохранена. "
            "Если обучение продолжается, попросите администратора школы проверить статус ученика."
        )
    if rows:
        revoked_reason = rows[0][0].revoked_reason
        if revoked_reason == "bot_stopped":
            return "bot_stopped", (
                "Подключение отключилось после остановки бота в MAX. Откройте бота "
                "и запустите его снова. Родителю нужно пройти по ссылке из письма школы, "
                "а ученику — открыть свой QR-код у преподавателя."
            )
        if revoked_reason == "registration_reset":
            return "registration_reset", (
                "Подключение было сброшено для повторной регистрации. Родителю нужно "
                "открыть ссылку из письма школы, а ученику — свой QR-код у преподавателя."
            )
        if revoked_reason in {"sponsor_revoked", "sponsor_bot_stopped"}:
            return "parent_disconnected", (
                "Подключение родителя отключено. Попросите родителя снова открыть ссылку "
                "из письма школы и завершить подключение. Затем откройте QR-код ученика "
                "у преподавателя."
            )
        return "access_revoked", (
            "Доступ к этому профилю отключён. Обратитесь к администратору школы, "
            "чтобы уточнить причину и восстановить подключение."
        )
    return "not_linked", NOT_LINKED_MESSAGE
