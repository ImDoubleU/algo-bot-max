"""Permission-scoped, paginated audit presentation."""

import re
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import String, case, cast, func, or_, select

from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.enums import StaffRole
from app.models.student import Contact, ContactStudentLink, Student
from app.models.tenant import Tenant
from app.schemas.miniapp import MiniAppAdminHistoryEntryRead, MiniAppAdminHistoryRead
from app.services.access import hash_contact_id

EXTRA_COPY = {
    "pending_binding.saved": ("Подключение ожидает появления профиля", "Привязки"),
    "pending_binding.ready": ("Профиль для подключения найден", "Привязки"),
    "pending_binding.review": ("Ожидающее подключение требует проверки", "Привязки"),
    "pending_binding.waiting": ("Подключение снова ожидает появления профиля", "Привязки"),
    "pending_binding.notified": ("Отправлено предложение завершить подключение", "Привязки"),
    "pending_binding.confirmed": ("Ожидающее подключение подтверждено", "Привязки"),
    "pending_binding.cancelled": ("Ожидающее подключение отменено", "Привязки"),
    "pending_binding.expired": ("Срок ожидания подключения закончился", "Привязки"),
    "contact_access.resolve_success": ("Ссылка родителя проверена", "Привязки"),
    "contact_access.resolve_failed": ("Ссылка родителя не найдена", "Привязки"),
    "contact_access.resolve_rate_limited": ("Проверка ссылки временно ограничена", "Привязки"),
    "contact_access_links.created": ("Родитель подключился", "Привязки"),
    "contact_access_link.failed": ("Родитель не смог подключиться", "Привязки"),
    "contact_access_link.rate_limited": ("Повторные подключения временно ограничены", "Привязки"),
    "student_qr_access_link.created": ("Ученик подключился по QR-коду", "Привязки"),
    "student_qr_access_link.failed": ("Ученик не смог подключиться", "Привязки"),
    "student_qr_access_link.restored": ("Привязка ученика восстановлена", "Привязки"),
    "student_access_link.revoked_parent_required": (
        "Привязка отключена проверкой родителя",
        "Привязки",
    ),
    "max_bot_access.revoked": ("Доступ отключён после остановки бота", "Привязки"),
    "student.updated": ("Данные ученика изменены", "Ученики"),
    "student.birth_date_changed": ("Дата рождения изменена", "Ученики"),
    "student_access_policy.updated": ("Правила доступа изменены", "Доступ"),
    "astrocoin_accrual_rules.updated": ("Правила начисления изменены", "Астрокоины"),
    "astrocoins.birthday_rewarded": ("Начислен подарок ко дню рождения", "Астрокоины"),
    "bank.rate_changed": ("Банковская ставка изменена", "Банк"),
    "staff_profile.updated": ("Рабочий профиль изменён", "Сотрудники"),
    "staff_profile.managed_updated": ("Профиль сотрудника изменён", "Сотрудники"),
    "staff_director.venue_scope_updated": ("Площадки директора изменены", "Сотрудники"),
    "staff_role.bootstrapped": ("Создан рабочий доступ", "Сотрудники"),
    "warehouse.unlinked": ("Склад отключён от школы", "Склады"),
    "feedback_schedule.created": ("Расписание обратной связи создано", "Обратная связь"),
    "feedback_schedule.updated": ("Расписание обратной связи изменено", "Обратная связь"),
    "support.ticket_created": ("Заявка в поддержку создана", "Поддержка"),
    "support.reply_sent": ("Ответ поддержки отправлен", "Поддержка"),
    "activity.request": ("Действие в приложении", "Запросы"),
    "bot.interaction": ("Действие в боте", "Бот"),
}
REASONS = {
    "account_already_connected": "Ожидание отменено: у аккаунта уже есть действующий доступ",
    "pending_expired": "Срок ожидания закончился; нужна свежая ссылка школы",
    "student_access_closed": "Доступ ученика закрыт",
    "student_not_found": "Профиль ученика ещё не найден",
    "ready": "Профиль найден, ожидается подтверждение пользователя",
    "connected": "Подключение завершено",
    "parent_required": "Родитель ещё не завершил подключение",
    "parent_link_inactive": "Родительская привязка отключена; нужен новый QR-код",
    "parent_disconnected": "Подключение родителя отключено",
    "contact_not_found": "Семья по ссылке не найдена",
    "contact_has_no_students": "Для контакта не найдены доступные ученики",
    "student_already_bound": "MAX-аккаунт уже привязан к другому ученику",
    "student_profile_already_bound": "Ученик уже подключён к другому аккаунту MAX",
    "account_role_conflict": "MAX-аккаунт используется с другой ролью",
    "access_revoked": "Доступ отключён школой",
    "access_expired": "Закончился срок доступа после обучения",
    "invitation_invalid": "Ссылка повреждена или недействительна",
    "invitation_legacy": "QR-код устарел",
    "too_many_attempts": "Слишком много попыток подряд",
    "missing_launch": "MAX не передал данные входа",
    "identity_mismatch": "Аккаунт не совпадает с данными запроса",
    "bot_stopped": "Пользователь остановил бота",
    "registration_reset": "Регистрация сброшена для повторного подключения",
    "student_archived": "Профиль ученика в архиве",
    "school_not_found": "Школа по ссылке не найдена",
    "school_inactive": "Школа отключена",
}
PRIVATE_KEYS = re.compile(
    r"token|secret|password|authorization|init.?data|signature|hash|"
    r"request_key|idempotency|(^|_)(body|text|message)(_|$)|photo",
    re.I,
)


def safe_payload(value, *, depth=0):
    if depth > 8:
        return "…"
    if isinstance(value, dict):
        return {
            str(key): safe_payload(item, depth=depth + 1)
            for key, item in value.items()
            if not PRIVATE_KEYS.search(str(key))
        }
    if isinstance(value, list):
        return [safe_payload(item, depth=depth + 1) for item in value[:200]]
    if isinstance(value, str):
        value = re.sub(r"https?://\S+", "[ссылка скрыта]", value)
        value = re.sub(r"(?i)Bearer\s+\S+", "[ключ скрыт]", value)
        return value[:4000]
    return value


def event_status(action, payload):
    result = str(payload.get("result") or payload.get("outcome") or "").lower()
    if result in {"denied", "rate_limited", "not_found"} or "rate_limited" in action:
        return "denied"
    if result in {"failed", "error"} or action.endswith(("failed", "sync_failed")):
        return "error"
    if payload.get("error"):
        return "error"
    if payload.get("incomplete_leads") or payload.get("unmatched_lead_ids"):
        return "partial"
    if result in {"queued", "pending", "processing"}:
        return "pending"
    return "success"


def copy_for(action, payload):
    from app.services.miniapp import AUDIT_ACTION_COPY

    title, category = {**AUDIT_ACTION_COPY, **EXTRA_COPY}.get(
        action,
        ("Системное событие", "Система"),
    )
    if action == "student_qr_access_link.created" and payload.get("created") is False:
        title = "Ученик повторно открыл QR-код"
    if action == "contact_access_links.created" and not (
        payload.get("created_links") or payload.get("reactivated_links")
    ):
        title = "Родитель повторно открыл свою ссылку"
    if action == "activity.request":
        title = str(payload.get("operation") or title)
    if action == "bot.interaction":
        title = str(payload.get("operation") or title)
    return title, category


async def history_page(
    db,
    *,
    max_user_id,
    tenant_slug,
    kind="actions",
    period_days=30,
    limit=100,
    offset=0,
    snapshot_at=None,
    category=None,
    outcome=None,
    actor_max_user_id=None,
    q=None,
    date_from=None,
    date_to=None,
    all_tenants=False,
    student_id=None,
):
    from app.services.miniapp import (
        AMOCRM_AUDIT_ACTIONS,
        MiniAppStoreError,
        _store_admin_context,
        _student_registry_context,
        _students_visible_to_staff_roles,
    )

    if student_id is not None:
        tenant, account, role, roles = await _student_registry_context(
            db,
            max_user_id=max_user_id,
            tenant_slug=tenant_slug,
        )
        student = await db.scalar(
            select(Student).where(
                Student.id == student_id,
                Student.tenant_id == tenant.id,
            )
        )
        visible = await _students_visible_to_staff_roles(
            db,
            tenant_id=tenant.id,
            account=account,
            staff_roles=roles,
            students=[student] if student else [],
        )
        if not visible:
            raise MiniAppStoreError("Нет доступа к истории этого ученика", status_code=403)
    else:
        tenant, account, role = await _store_admin_context(
            db,
            max_user_id=max_user_id,
            tenant_slug=tenant_slug,
            denied_message="Нет прав на просмотр истории действий",
        )
    full = kind == "audit"
    if (full or all_tenants) and role != StaffRole.SUPERADMIN:
        raise MiniAppStoreError(
            "Подробный аудит доступен только суперадминистратору", status_code=403
        )
    if kind not in {"actions", "amocrm", "bindings", "audit"}:
        raise MiniAppStoreError("Неизвестный вид истории")
    snapshot = snapshot_at or datetime.now(UTC)
    if snapshot.tzinfo is None:
        snapshot = snapshot.replace(tzinfo=UTC)
    snapshot = min(snapshot, datetime.now(UTC))
    conditions = [AuditLog.created_at <= snapshot]
    if not all_tenants:
        conditions.append(AuditLog.tenant_id == tenant.id)
    zone = ZoneInfo("Europe/Moscow")
    lower = (
        datetime.combine(date_from, time.min, zone).astimezone(UTC)
        if date_from
        else (snapshot - timedelta(days=max(1, min(period_days, 3650))))
    )
    conditions.append(AuditLog.created_at >= lower)
    if date_to:
        conditions.append(
            AuditLog.created_at
            < datetime.combine(
                date_to + timedelta(days=1),
                time.min,
                zone,
            ).astimezone(UTC)
        )
    if date_from and date_to and date_from > date_to:
        raise MiniAppStoreError("Начало периода должно быть раньше окончания")
    if not full:
        from app.services.binding_history import ordinary_binding_events

        conditions.append(ordinary_binding_events(db, snapshot=snapshot))
    if kind == "amocrm":
        conditions.append(AuditLog.action.in_(AMOCRM_AUDIT_ACTIONS))
    elif kind == "actions":
        conditions.append(AuditLog.action.not_in(AMOCRM_AUDIT_ACTIONS))
    if kind == "bindings":
        conditions.append(
            or_(
                AuditLog.action.like("contact_access%"),
                AuditLog.action.like("student%access%"),
                AuditLog.action.like("pending_binding.%"),
                AuditLog.action == "max_bot_access.revoked",
                AuditLog.action.in_(["activity.request", "bot.interaction"]),
            )
        )
    if student_id is not None:
        contacts = (
            await db.execute(
                select(Contact.id, Contact.external_contact_id)
                .join(ContactStudentLink, ContactStudentLink.contact_id == Contact.id)
                .where(ContactStudentLink.student_id == student_id)
            )
        ).all()
        conditions.append(
            or_(
                AuditLog.entity_id == str(student_id),
                AuditLog.entity_id.in_([str(key) for key, _ in contacts]),
                cast(AuditLog.payload, String).contains(str(student_id)),
                *[
                    cast(AuditLog.payload, String).contains(hash_contact_id(external))
                    for _, external in contacts
                ],
            )
        )
    if actor_max_user_id:
        conditions.append(
            or_(
                MaxAccount.max_user_id == actor_max_user_id,
                cast(AuditLog.payload["max_user_id"].as_string(), String) == str(actor_max_user_id),
            )
        )
    if q:
        from app.services.miniapp import AUDIT_ACTION_COPY

        text = q.strip().lower()
        matching = [
            action
            for action, (title, cat) in {**AUDIT_ACTION_COPY, **EXTRA_COPY}.items()
            if text in title.lower() or text in cat.lower()
        ]
        if not full:
            for action, title in {
                "bot.interaction": "Ученик открыл свой QR-код Родитель открыл ссылку",
                "activity.request": "Ученик открыл свой QR-код Родитель открыл ссылку",
                "contact_access.resolve_failed": "Родитель пытался подключиться",
                "contact_access_link.failed": "Родитель пытался подключиться",
                "student_qr_access_link.failed": "Ученик пытался подключиться",
                "pending_binding.saved": (
                    "Ученик пытался подключиться Родитель пытался подключиться"
                ),
            }.items():
                if text in title.lower():
                    matching.append(action)
        student_text = or_(
            func.lower(Student.last_name + " " + Student.first_name)
            .contains(text, autoescape=True),
            func.lower(Student.first_name + " " + Student.last_name)
            .contains(text, autoescape=True),
            func.lower(Student.lms_student_id).contains(text, autoescape=True),
        )
        student_key = func.replace(cast(Student.id, String), "-", "")
        direct_student = select(Student.id).where(
            Student.tenant_id == AuditLog.tenant_id, student_text,
            or_(
                func.replace(AuditLog.payload["student_id"].as_string(), "-", "") == student_key,
                (AuditLog.payload["link_target"]["kind"].as_string() == "student")
                & (func.replace(AuditLog.payload["link_target"]["id"].as_string(), "-", "")
                   == student_key),
                AuditLog.entity_type.like("student%")
                & (func.replace(AuditLog.entity_id, "-", "") == student_key),
                func.replace(cast(AuditLog.payload["student_ids"], String), "-", "")
                .contains(student_key),
            ),
        ).correlate(AuditLog).exists()
        contact_student = (
            select(ContactStudentLink.id)
            .join(Student, Student.id == ContactStudentLink.student_id)
            .join(Contact, Contact.id == ContactStudentLink.contact_id)
            .where(
                Contact.tenant_id == AuditLog.tenant_id, Student.tenant_id == AuditLog.tenant_id,
                student_text,
                or_(
                    Contact.external_contact_id == AuditLog.payload["contact_id"].as_string(),
                    (AuditLog.payload["link_target"]["kind"].as_string() == "contact")
                    & (Contact.external_contact_id
                       == AuditLog.payload["link_target"]["id"].as_string()),
                ),
            ).correlate(AuditLog).exists()
        )
        conditions.append(
            or_(
                func.lower(AuditLog.action).contains(text, autoescape=True),
                func.lower(MaxAccount.display_name).contains(text, autoescape=True),
                cast(MaxAccount.max_user_id, String).contains(text, autoescape=True),
                func.lower(cast(AuditLog.payload, String)).contains(text, autoescape=True),
                AuditLog.action.in_(matching),
                direct_student,
                contact_student,
            )
        )
    if category:
        from app.services.miniapp import AUDIT_ACTION_COPY

        matching = [
            action
            for action, (_, cat) in {**AUDIT_ACTION_COPY, **EXTRA_COPY}.items()
            if cat == category
        ]
        if category == "Система":
            conditions.append(
                AuditLog.action.not_in(
                    {**AUDIT_ACTION_COPY, **EXTRA_COPY}.keys(),
                )
            )
        else:
            category_condition = AuditLog.action.in_(matching)
            if not full and category == "Привязки":
                from app.services.binding_history import link_visit

                category_condition = or_(category_condition, link_visit(AuditLog))
            conditions.append(category_condition)
    if outcome:
        result = func.lower(
            func.coalesce(
                func.nullif(AuditLog.payload["result"].as_string(), ""),
                AuditLog.payload["outcome"].as_string(),
                "",
            )
        )
        status_expr = case(
            (
                or_(
                    result.in_(["denied", "rate_limited", "not_found"]),
                    AuditLog.action.like("%rate_limited%"),
                ),
                "denied",
            ),
            (
                or_(
                    result.in_(["failed", "error"]),
                    AuditLog.action.like("%failed"),
                    AuditLog.payload["error"].as_string().not_in(["", "null"]),
                ),
                "error",
            ),
            (
                or_(
                    AuditLog.payload["incomplete_leads"].as_string().not_in(
                        ["{}", "[]", "null", ""]
                    ),
                    AuditLog.payload["unmatched_lead_ids"].as_string().not_in(
                        ["{}", "[]", "null", ""]
                    ),
                ),
                "partial",
            ),
            (result.in_(["queued", "pending", "processing"]), "pending"),
            else_="success",
        )
        conditions.append(
            status_expr != "success" if outcome == "attention" else status_expr == outcome
        )
    stmt = (
        select(AuditLog, MaxAccount, Tenant)
        .outerjoin(
            MaxAccount,
            or_(
                MaxAccount.id == AuditLog.actor_account_id,
                (AuditLog.actor_account_id.is_(None))
                & (cast(MaxAccount.max_user_id, String)
                   == AuditLog.payload["max_user_id"].as_string()),
            ),
        )
        .outerjoin(Tenant, Tenant.id == AuditLog.tenant_id)
        .where(*conditions)
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    start = max(0, offset)
    page_size = max(1, min(limit, 500))
    rows = (
        await db.execute(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(start)
            .limit(page_size)
        )
    ).all()
    from app.services.audit_people import history_people

    people = await history_people(
        db,
        rows,
        tenant_id=tenant.id,
        all_tenants=all_tenants,
        student_id=student_id,
    )
    entries = []
    for audit, actor, event_tenant in rows:
        payload = safe_payload(dict(audit.payload or {}))
        context = people[audit.id]
        payload["actor_role"] = context["actor_role"]
        payload["students"] = context["students"]
        if full:
            payload["link_target"] = context["link_target"]
        if not full:
            for key in ("request_id", "webhook_event_id", "error_type", "http_status", "path",
                        "contact_id", "link_target"):
                payload.pop(key, None)
        title, event_category = copy_for(audit.action, payload)
        status = event_status(audit.action, payload)
        explanation = REASONS.get(str(payload.get("reason")), str(payload.get("detail") or ""))
        if not full:
            from app.services.binding_history import binding_presentation

            presentation = binding_presentation(audit.action, payload, context)
            if presentation:
                payload["binding_subject"] = presentation["subject"]
                payload["actor_role"] = presentation["role"]
                title = presentation["title"] or title
                explanation = presentation["explanation"] or explanation
                event_category = "Привязки"
        actor_id = actor.max_user_id if actor else (audit.payload or {}).get("max_user_id")
        if not isinstance(actor_id, int):
            actor_id = None
        entries.append(
            MiniAppAdminHistoryEntryRead(
                id=audit.id,
                action=audit.action,
                title=title,
                category=event_category,
                status=status,
                actor_name=context["actor_name"]
                or (actor.display_name or actor.username if actor else None)
                or (f"Аккаунт MAX {actor_id}" if actor_id else "Система"),
                actor_max_user_id=actor_id,
                entity_type=audit.entity_type,
                entity_id=audit.entity_id,
                payload=payload,
                created_at=audit.created_at,
                tenant_name=event_tenant.name if event_tenant else "Без выбранной школы",
                tenant_slug=event_tenant.slug if event_tenant else None,
                explanation=explanation,
                request_id=str(payload.get("request_id") or "") if full else None,
                ip_address=audit.ip_address if full else None,
            )
        )
    return MiniAppAdminHistoryRead(
        tenant_slug=tenant.slug,
        kind=kind,
        period_days=period_days,
        entries=entries,
        total=total or 0,
        offset=start,
        limit=page_size,
        has_more=start + page_size < (total or 0),
        snapshot_at=snapshot,
    )
