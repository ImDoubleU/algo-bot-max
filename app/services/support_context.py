"""Current user information for the owner-only ticket inbox; no stored snapshots."""

from collections import defaultdict

from sqlalchemy import func, select

from app.models.account import MaxAccount, StaffRoleAssignment, StaffVenueScope
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink, Wallet
from app.models.tenant import City, Partner, Tenant, Venue
from app.services.audit_people import account_name
from app.services.staff import staff_names_match, teacher_staff_name


async def ticket_user_contexts(db, tickets):
    if not tickets:
        return {}
    authors = {ticket.max_user_id for ticket in tickets}
    accounts = list(await db.scalars(select(MaxAccount).where(MaxAccount.max_user_id.in_(authors))))
    by_max_id = {account.max_user_id: account for account in accounts}
    account_ids = [account.id for account in accounts]
    account_by_id = {account.id: account for account in accounts}
    schools = {
        tenant.id: {"slug": tenant.slug, "name": tenant.name, "city": city, "partner": partner}
        for tenant, city, partner in await db.execute(
            select(Tenant, City.name, Partner.name)
            .join(City, City.id == Tenant.city_id).join(Partner, Partner.id == Tenant.partner_id)
        )
    }
    school_by_slug = {school["slug"]: school for school in schools.values()}
    assignments = list(await db.scalars(select(StaffRoleAssignment).where(
        StaffRoleAssignment.account_id.in_(account_ids)
    ).order_by(StaffRoleAssignment.role)))
    venues = defaultdict(list)
    for assignment_id, name in await db.execute(
        select(StaffVenueScope.assignment_id, Venue.name)
        .join(Venue, Venue.id == StaffVenueScope.venue_id)
        .where(StaffVenueScope.assignment_id.in_([assignment.id for assignment in assignments]))
        .order_by(Venue.name)
    ):
        venues[assignment_id].append(name)
    links = list((await db.execute(
        select(StudentAccessLink, Student)
        .join(Student, Student.id == StudentAccessLink.student_id)
        .where(StudentAccessLink.account_id.in_(account_ids),
               Student.tenant_id == StudentAccessLink.tenant_id)
        .order_by(Student.group_name, Student.last_name, Student.first_name)
    )).all())
    students = {student.id: student for _, student in links}
    balances = dict((await db.execute(select(Wallet.student_id, Wallet.balance).where(
        Wallet.student_id.in_(students)
    ))).all())
    current_accounts = defaultdict(list)
    parent_connected = set()
    for link, account in await db.execute(
        select(StudentAccessLink, MaxAccount)
        .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
        .where(StudentAccessLink.student_id.in_(students),
               StudentAccessLink.status == StudentAccessStatus.ACTIVE)
        .order_by(StudentAccessLink.role, MaxAccount.max_user_id)
    ):
        if link.tenant_id != students[link.student_id].tenant_id:
            continue
        if link.role == StudentAccessRole.PARENT:
            parent_connected.add(link.student_id)
        current_accounts[link.student_id].append({
            "max_id": str(account.max_user_id), "name": account_name(account),
            "username": account.username, "phone": account.phone, "role": link.role.value,
        })
    contacts = defaultdict(list)
    for student_id, contact in await db.execute(
        select(ContactStudentLink.student_id, Contact)
        .join(Contact, Contact.id == ContactStudentLink.contact_id)
        .where(ContactStudentLink.student_id.in_(students))
        .order_by(Contact.display_name, Contact.external_contact_id)
    ):
        if contact.tenant_id == students[student_id].tenant_id:
            contacts[student_id].append({
                "id": contact.external_contact_id, "name": contact.display_name,
            })
    last_activity = dict((await db.execute(
        select(AuditLog.actor_account_id, func.max(AuditLog.created_at))
        .where(AuditLog.actor_account_id.in_(account_ids))
        .group_by(AuditLog.actor_account_id)
    )).all())
    teachers = (await db.execute(
        select(MaxAccount, StaffRoleAssignment.tenant_id)
        .join(StaffRoleAssignment, StaffRoleAssignment.account_id == MaxAccount.id)
        .where(StaffRoleAssignment.tenant_id.in_(
                   {student.tenant_id for student in students.values()}),
               StaffRoleAssignment.role == StaffRole.TEACHER,
               StaffRoleAssignment.status == AssignmentStatus.ACTIVE)
    )).all() if students else []
    teacher_ids = {}
    for student in students.values():
        matches = {account.max_user_id for account, tenant_id in teachers
                   if tenant_id == student.tenant_id
                   and staff_names_match(teacher_staff_name(account), student.teacher_name)}
        teacher_ids[student.id] = str(next(iter(matches))) if len(matches) == 1 else None
    teacher_tenants = {assignment.tenant_id for assignment in assignments
                       if assignment.role == StaffRole.TEACHER
                       and assignment.status == AssignmentStatus.ACTIVE}
    taught_students = list(await db.scalars(select(Student).where(
        Student.tenant_id.in_(teacher_tenants), Student.status == StudentStatus.ACTIVE
    ))) if teacher_tenants else []
    staff = defaultdict(list)
    for assignment in assignments:
        groups = {}
        if assignment.role == StaffRole.TEACHER and assignment.status == AssignmentStatus.ACTIVE:
            name = teacher_staff_name(account_by_id[assignment.account_id])
            for student in taught_students:
                if student.tenant_id == assignment.tenant_id and staff_names_match(
                    name, student.teacher_name,
                ):
                    key = (student.group_name, student.course_name, student.venue_name)
                    group = groups.setdefault(key, {"name": student.group_name,
                                                   "course": student.course_name,
                                                   "venue": student.venue_name, "students": 0})
                    group["students"] += 1
        staff[assignment.account_id].append({
            "role": assignment.role.value, "status": assignment.status.value,
            "school": schools.get(assignment.tenant_id), "venues": venues[assignment.id],
            "groups": sorted(groups.values(), key=lambda group: (group["name"] or "")),
            "since": assignment.created_at,
        })
    linked_students = defaultdict(dict)
    for link, student in links:
        item = linked_students[link.account_id].setdefault(student.id, {
            "id": str(student.id), "name": student.display_name, "lms_id": student.lms_student_id,
            "crm_id": student.crm_deal_id, "crm_uuid": student.crm_uuid,
            "birth_date": student.birth_date, "school": schools.get(student.tenant_id),
            "group": student.group_name, "course": student.course_name,
            "venue": student.venue_name, "teacher": student.teacher_name,
            "teacher_max_id": teacher_ids[student.id],
            "status": student.status.value, "balance": balances.get(student.id, 0),
            "parent_connected": student.id in parent_connected,
            "accounts": current_accounts[student.id], "contacts": contacts[student.id],
            "links": [],
        })
        item["links"].append({
            "id": str(link.id), "role": link.role.value, "status": link.status.value,
            "source": link.source.value, "connected_at": link.created_at,
            "revoked_at": link.revoked_at, "revoked_reason": link.revoked_reason,
        })
    result = {}
    for ticket in tickets:
        account = by_max_id.get(ticket.max_user_id)
        result[ticket.id] = {
            "account": {"id": str(account.id), "name": account.display_name,
                        "staff_name": teacher_staff_name(account)
                        if account.staff_profile_completed_at else None,
                        "username": account.username, "phone": account.phone,
                        "created_at": account.created_at, "updated_at": account.updated_at,
                        "last_activity_at": last_activity.get(account.id)} if account else None,
            "origin_school": school_by_slug.get(ticket.tenant_slug),
            "staff": staff[account.id] if account else [],
            "students": list(linked_students[account.id].values()) if account else [],
        }
    return result
