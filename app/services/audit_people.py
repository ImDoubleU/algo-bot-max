"""Batch-resolve people for a history page without changing historical audit data."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import String, cast, func, select

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import AssignmentStatus, StaffRole, StudentAccessStatus
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.models.tenant import Tenant
from app.services.access import hash_contact_id
from app.services.binding_targets import contact_target
from app.services.staff import staff_names_match, teacher_staff_name


def identifier(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def account_name(account):
    return " ".join(filter(None, [account.staff_last_name, account.staff_first_name])) or (
        account.display_name or account.username or ""
    )


async def history_people(db, rows, *, tenant_id, all_tenants=False, student_id=None):
    tenant_ids = {audit.tenant_id for audit, _, _ in rows if audit.tenant_id}
    if not all_tenants:
        tenant_ids = {tenant_id}
    student_ids, contact_ids, hashes, actor_ids = set(), set(), set(), set()
    event_students, event_contacts = defaultdict(set), {}
    event_targets, external_ids = {}, set()
    schools = {school.slug: school.id for school in await db.scalars(
        select(Tenant).where(Tenant.id.in_(tenant_ids))
    )}
    target_schools = {}
    for audit, actor, _ in rows:
        p = audit.payload or {}
        target = p.get("link_target")
        if not isinstance(target, dict):
            target = None
        if target and target.get("kind") == "contact":
            target = contact_target(target.get("id"), tenant_slug=target.get("tenant_slug"))
        elif target and target.get("kind") == "student":
            key = identifier(target.get("id"))
            school_id = identifier(target.get("tenant_id"))
            target = ({"kind": "student", "id": str(key),
                       **({"tenant_id": str(school_id)} if school_id else {})} if key else None)
        else:
            target = None
        if target is None and p.get("contact_id"):
            target = contact_target(p["contact_id"])
        if target is None and audit.action.startswith(("student_qr_access", "pending_binding")):
            if key := identifier(p.get("student_id")):
                target = {"kind": "student", "id": str(key)}
                if school_id := identifier(p.get("invitation_tenant_id")):
                    target["tenant_id"] = str(school_id)
        if target:
            event_targets[audit.id] = target
            scope = (identifier(target.get("tenant_id")) if target.get("tenant_id")
                     else schools.get(target["tenant_slug"]) if target.get("tenant_slug")
                     else audit.tenant_id)
            target_schools[audit.id] = scope if scope in tenant_ids else None
            if target["kind"] == "contact":
                external_ids.add(target["id"])
        values = [p.get("student_id"), *(p.get("student_ids") or [])]
        if target and target["kind"] == "student" and target_schools[audit.id]:
            values.append(target["id"])
        if audit.entity_type.startswith("student"):
            values.append(audit.entity_id)
        for value in values:
            if key := identifier(value):
                student_ids.add(key)
                event_students[audit.id].add(key)
        if audit.entity_type.startswith("contact") and (key := identifier(audit.entity_id)):
            contact_ids.add(key)
            event_contacts[audit.id] = key
        if p.get("contact_id_hash"):
            hashes.add(p["contact_id_hash"])
        if actor:
            actor_ids.add(actor.id)

    contacts = {}
    if contact_ids or hashes or external_ids:
        query = select(Contact).where(Contact.tenant_id.in_(tenant_ids))
        if not hashes and not external_ids:
            query = query.where(Contact.id.in_(contact_ids))
        for contact in (await db.scalars(query)).all():
            if (contact.id in contact_ids or hash_contact_id(contact.external_contact_id) in hashes
                    or contact.external_contact_id in external_ids):
                contacts[contact.id] = contact
        hash_contacts = {
            (c.tenant_id, hash_contact_id(c.external_contact_id)): c.id for c in contacts.values()
        }
        by_external_id = {(c.tenant_id, c.external_contact_id): c.id for c in contacts.values()}
        for audit, _, _ in rows:
            key = hash_contacts.get((audit.tenant_id, (audit.payload or {}).get("contact_id_hash")))
            target = event_targets.get(audit.id)
            if target and target["kind"] == "contact":
                key = by_external_id.get((target_schools.get(audit.id), target["id"]))
            if key:
                event_contacts[audit.id] = key
        links = (
            await db.execute(
                select(ContactStudentLink.contact_id, ContactStudentLink.student_id).where(
                    ContactStudentLink.contact_id.in_(contacts),
                    ContactStudentLink.tenant_id.in_(tenant_ids),
                )
            )
        ).all()
        for audit, _, _ in rows:
            for contact_key, student_key in links:
                if event_contacts.get(audit.id) == contact_key:
                    event_students[audit.id].add(student_key)
                    student_ids.add(student_key)

    students = {
        s.id: s
        for s in (
            await db.scalars(
                select(Student).where(
                    Student.id.in_(student_ids),
                    Student.tenant_id.in_(tenant_ids),
                    *([Student.id == student_id] if student_id else []),
                )
            )
        ).all()
    }
    current_links = defaultdict(list)
    parent_names = defaultdict(set)
    for parent_id, child_id, parent_name in (
        await db.execute(
            select(AuditLog.actor_account_id, ContactStudentLink.student_id, Contact.display_name)
            .join(
                Contact,
                func.replace(cast(Contact.id, String), "-", "")
                == func.replace(AuditLog.entity_id, "-", ""),
            )
            .join(ContactStudentLink, ContactStudentLink.contact_id == Contact.id)
            .where(
                AuditLog.action == "contact_access_links.created",
                ContactStudentLink.student_id.in_(students),
                Contact.tenant_id.in_(tenant_ids),
            )
        )
    ).all():
        if parent_name:
            parent_names[parent_id, child_id].add(parent_name)
    for link, account in (
        await db.execute(
            select(StudentAccessLink, MaxAccount)
            .join(
                MaxAccount,
                MaxAccount.id == StudentAccessLink.account_id,
            )
            .where(
                StudentAccessLink.student_id.in_(students),
                StudentAccessLink.tenant_id.in_(tenant_ids),
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            )
        )
    ).all():
        current_links[link.student_id].append(
            {
                "role": link.role.value,
                "name": students[link.student_id].display_name
                if link.role.value == "student"
                else account_name(account)
                or (
                    next(iter(parent_names[account.id, link.student_id]))
                    if len(parent_names[account.id, link.student_id]) == 1
                    else ""
                ),
                "max_user_id": account.max_user_id,
            }
        )
    roles = defaultdict(list)
    teachers = (
        await db.execute(
            select(MaxAccount, StaffRoleAssignment.tenant_id)
            .join(
                StaffRoleAssignment,
                StaffRoleAssignment.account_id == MaxAccount.id,
            )
            .where(
                StaffRoleAssignment.tenant_id.in_(tenant_ids),
                StaffRoleAssignment.role == StaffRole.TEACHER,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    ).all()
    teacher_ids = {}
    for s in students.values():
        matches = {
            teacher.max_user_id
            for teacher, school_id in teachers
            if school_id == s.tenant_id
            and s.teacher_name
            and staff_names_match(teacher_staff_name(teacher), s.teacher_name)
        }
        teacher_ids[s.id] = next(iter(matches)) if len(matches) == 1 else None
    for account_id, role in (
        await db.execute(
            select(
                StaffRoleAssignment.account_id,
                StaffRoleAssignment.role,
            ).where(
                StaffRoleAssignment.account_id.in_(actor_ids),
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                (
                    StaffRoleAssignment.tenant_id.in_(tenant_ids)
                    | StaffRoleAssignment.tenant_id.is_(None)
                ),
            )
        )
    ).all():
        roles[account_id].append(role.value)

    result = {}
    for audit, actor, _ in rows:
        p = audit.payload or {}
        role = p.get("role") or (
            "student"
            if audit.action.startswith("student_qr_access")
            else "parent"
            if audit.action.startswith("contact_access")
            else ", ".join(sorted(set(roles[actor.id])))
            if actor
            else ""
        )
        subject_students = [
            students[key] for key in sorted(event_students[audit.id], key=str) if key in students
        ]
        contact = contacts.get(event_contacts.get(audit.id))
        target = event_targets.get(audit.id)
        if target is None and contact and p.get("contact_id_hash"):
            target = {"kind": "contact", "id": contact.external_contact_id}
        if target is None and p.get("contact_id_hash"):
            target = {"kind": "contact", "id": None, "state": "historical_id_missing"}
        if target is None and p.get("reason") == "not_linked":
            target = {"kind": "unknown", "id": None, "state": "not_provided"}
        name = account_name(actor) if actor else ""
        if role == "student" and len(subject_students) == 1:
            name = subject_students[0].display_name
        elif role == "parent" and contact and contact.display_name:
            name = contact.display_name
        result[audit.id] = {
            "actor_name": name,
            "actor_role": role,
            "link_target": target,
            "students": [
                {
                    "id": str(s.id),
                    "name": s.display_name,
                    "tenant_id": str(s.tenant_id),
                    "tenant_slug": next((slug for slug, key in schools.items()
                                         if key == s.tenant_id), None),
                    "lms_id": s.lms_student_id,
                    "crm_id": s.crm_deal_id,
                    "group": s.group_name,
                    "teacher": s.teacher_name,
                    "teacher_max_user_id": teacher_ids[s.id],
                    "accounts": current_links[s.id],
                }
                for s in subject_students
            ],
        }
    return result
