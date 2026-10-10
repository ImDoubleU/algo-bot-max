"""Present link visits in ordinary history without rewriting the audit trail."""

from datetime import timedelta

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import aliased

from app.models.audit import AuditLog

TECHNICAL_ACTIONS = ("activity.request", "bot.interaction")
BINDING_PRIORITIES = {
    "student_qr_access_link.created": 100,
    "student_qr_access_link.restored": 100,
    "contact_access_links.created": 100,
    "pending_binding.confirmed": 110,
    "pending_binding.saved": 90,
    "student_qr_access_link.failed": 80,
    "contact_access_link.failed": 80,
    "contact_access.resolve_failed": 70,
    "contact_access.resolve_success": 60,
    "activity.request": 20,
    "bot.interaction": 10,
}
MISSING_PROFILE_REASONS = {
    "student_not_found", "contact_not_found", "contact_id_not_found", "contact_has_no_students",
}


def link_visit(log):
    p = log.payload
    target_kind = p["link_target"]["kind"].as_string()
    target_id = p["link_target"]["id"].as_string()
    return and_(
        target_kind.in_(("student", "contact")),
        target_id.is_not(None), target_id != "",
        or_(log.actor_account_id.is_not(None), p["max_user_id"].as_integer() > 0),
        or_(
            and_(log.action == "bot.interaction",
                 p["update_type"].as_string().in_(("bot_started", "message_created"))),
            and_(log.action == "activity.request",
                 or_(p["path"].as_string() == "/api/v1/miniapp/session",
                     p["path"].as_string().like("/api/v1/access/%"))),
        ),
    )


def _target(log):
    p = log.payload
    kind = func.coalesce(p["link_target"]["kind"].as_string(), case(
        (p["student_id"].as_string().is_not(None), "student"),
        (p["contact_id"].as_string().is_not(None), "contact"),
        (p["contact_id_hash"].as_string().is_not(None), "contact_hash"),
        (log.entity_type.like("student%"), "student"),
    ))
    value = func.coalesce(p["link_target"]["id"].as_string(), p["student_id"].as_string(),
                          p["contact_id"].as_string(), p["contact_id_hash"].as_string(),
                          case((log.entity_type.like("student%"), log.entity_id)))
    return kind, value


def ordinary_binding_events(db, *, snapshot):
    """Keep business events plus targeted visits, counting a multi-stage visit once.

    The five-second match requires the same account, school and exact target.
    Later retries and visits to a different child remain separate. Full audit is untouched.
    """
    other = aliased(AuditLog)
    kind, target = _target(AuditLog)
    other_kind, other_target = _target(other)
    def rank(log):
        return case(BINDING_PRIORITIES, value=log.action, else_=0)
    if db.get_bind().dialect.name == "sqlite":
        nearby = (func.abs(func.julianday(other.created_at)
                           - func.julianday(AuditLog.created_at)) * 86400) <= 5
    else:
        # A timestamp range can use the existing audit timeline indexes.
        nearby = and_(
            other.created_at >= AuditLog.created_at - timedelta(seconds=5),
            other.created_at <= AuditLog.created_at + timedelta(seconds=5),
        )
    same_actor = or_(
        and_(AuditLog.actor_account_id.is_not(None),
             other.actor_account_id == AuditLog.actor_account_id),
        and_(AuditLog.payload["max_user_id"].as_string().is_not(None),
             other.payload["max_user_id"].as_string()
             == AuditLog.payload["max_user_id"].as_string()),
    )
    same_school = or_(
        and_(AuditLog.tenant_id.is_not(None), other.tenant_id == AuditLog.tenant_id),
        and_(AuditLog.tenant_id.is_(None), other.tenant_id.is_(None)),
    )
    better_event = select(other.id).where(
        other.id != AuditLog.id, other.created_at <= snapshot,
        other.action.in_(BINDING_PRIORITIES),
        or_(other.action.not_in(TECHNICAL_ACTIONS), link_visit(other)),
        same_actor, same_school, kind == other_kind, target == other_target, nearby,
        rank(other) > rank(AuditLog),
    ).correlate(AuditLog).exists()
    return and_(
        or_(AuditLog.action.not_in(TECHNICAL_ACTIONS), link_visit(AuditLog)),
        or_(AuditLog.action.not_in(BINDING_PRIORITIES), ~better_event),
    )


def binding_presentation(action, payload, context):
    """Only confirmed student IDs; a parent's contact ID never becomes an LMS ID."""
    target = context.get("link_target")
    is_visit = action in TECHNICAL_ACTIONS and target and target.get("id")
    if action not in BINDING_PRIORITIES or (action in TECHNICAL_ACTIONS and not is_visit):
        return None
    students = context.get("students", [])
    reason = payload.get("reason")
    missing = reason in MISSING_PROFILE_REASONS
    role = "student" if (target or {}).get("kind") == "student" else "parent"
    recorded_role = payload.get("role") or context.get("actor_role")
    if recorded_role in {"student", "parent"}:
        role = recorded_role
    subject = {
        "role": role,
        "confirmed": action in {"student_qr_access_link.created",
                                 "student_qr_access_link.restored", "contact_access_links.created",
                                 "pending_binding.confirmed"},
        "state": "not_added" if missing else "known" if students else "unavailable",
        "target_kind": (target or {}).get("kind"),
        "target_id": (target or {}).get("id"),
        "name": None,
        "lms_id": None,
    }
    # A recorded student snapshot is useful when the local profile is no longer present.
    # IDs from contact links and internal UUIDs are deliberately never used as LMS IDs.
    if not students:
        subject["name"] = payload.get("student_name")
        lms_id = payload.get("lms_student_id")
        if isinstance(lms_id, (str, int)) and lms_id:
            subject["lms_id"] = str(lms_id)
    title = explanation = None
    if missing:
        title = (
            "Ученик пытался подключиться" if role == "student"
            else "Родитель пытался подключиться"
        )
        explanation = "Попытался зайти в аккаунт ученика, но его ещё не добавили в систему."
        if students:
            explanation = (
                "На момент перехода профиль ученика ещё не был добавлен. Сейчас он найден."
            )
    elif is_visit or action == "contact_access.resolve_success":
        title = "Ученик открыл свой QR-код" if role == "student" else "Родитель открыл ссылку"
        explanation = "Переход зафиксирован; успешная привязка этим событием не подтверждена."
    return {"subject": subject, "title": title, "explanation": explanation, "role": role}
