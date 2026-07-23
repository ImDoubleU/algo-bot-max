import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Contact, ContactStudentLink, Student, Wallet
from app.models.tenant import City, Partner, Tenant, Venue
from app.services.access import normalize_contact_id, normalize_student_code
from app.services.crm_import import CrmStudentRow


class CrmSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrmSyncDefaults:
    partner_slug: str
    partner_name: str
    fallback_city_name: str = (
        "\u041d\u0438\u0436\u043d\u0438\u0439 \u041d\u043e\u0432\u0433\u043e\u0440\u043e\u0434"
    )
    tenant_slug: str | None = None


@dataclass(frozen=True)
class CrmSyncResult:
    created_cities: int = 0
    created_partners: int = 0
    created_tenants: int = 0
    created_venues: int = 0
    created_students: int = 0
    updated_students: int = 0
    created_wallets: int = 0
    created_contacts: int = 0
    created_contact_student_links: int = 0
    skipped_rows: int = 0

    def add(self, **changes: int) -> "CrmSyncResult":
        data = self.__dict__ | changes
        return CrmSyncResult(**data)


def slugify(value: str) -> str:
    text = value.strip().lower().replace("\u0451", "\u0435")
    translit = str.maketrans(
        {
            "\u0430": "a",
            "\u0431": "b",
            "\u0432": "v",
            "\u0433": "g",
            "\u0434": "d",
            "\u0435": "e",
            "\u0436": "zh",
            "\u0437": "z",
            "\u0438": "i",
            "\u0439": "y",
            "\u043a": "k",
            "\u043b": "l",
            "\u043c": "m",
            "\u043d": "n",
            "\u043e": "o",
            "\u043f": "p",
            "\u0440": "r",
            "\u0441": "s",
            "\u0442": "t",
            "\u0443": "u",
            "\u0444": "f",
            "\u0445": "h",
            "\u0446": "c",
            "\u0447": "ch",
            "\u0448": "sh",
            "\u0449": "sch",
            "\u044a": "",
            "\u044b": "y",
            "\u044c": "",
            "\u044d": "e",
            "\u044e": "yu",
            "\u044f": "ya",
        }
    )
    text = text.translate(translit)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def make_tenant_slug(city_name: str, partner_slug: str) -> str:
    return f"{slugify(city_name)}-{slugify(partner_slug)}"


def make_generated_access_code(*, tenant_slug: str, row: CrmStudentRow) -> str:
    source = "|".join(
        [
            tenant_slug,
            row.lms_student_id or "",
            row.deal_id or "",
            row.uuid or "",
            row.first_name or "",
            row.last_name or "",
            row.group_name or "",
        ]
    )
    digest = hashlib.sha256(source.encode()).hexdigest()[:10].upper()
    return f"AC{digest}"


def split_contact_ids(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,;\n/]+", value)
    return [normalize_contact_id(part) for part in parts if normalize_contact_id(part)]


async def get_or_create_city(db: AsyncSession, name: str) -> tuple[City, bool]:
    slug = slugify(name)
    city = await db.scalar(select(City).where(City.slug == slug))
    if city:
        return city, False
    city = City(slug=slug, name=name)
    db.add(city)
    await db.flush()
    return city, True


async def get_or_create_partner(
    db: AsyncSession,
    *,
    slug: str,
    name: str,
) -> tuple[Partner, bool]:
    normalized_slug = slugify(slug)
    partner = await db.scalar(select(Partner).where(Partner.slug == normalized_slug))
    if partner:
        partner.name = name
        return partner, False
    partner = Partner(slug=normalized_slug, name=name)
    db.add(partner)
    await db.flush()
    return partner, True


async def get_or_create_tenant(
    db: AsyncSession,
    *,
    city: City,
    partner: Partner,
    tenant_slug: str | None = None,
) -> tuple[Tenant, bool]:
    tenant = await db.scalar(
        select(Tenant).where(Tenant.city_id == city.id, Tenant.partner_id == partner.id)
    )
    if tenant:
        if tenant_slug and tenant.slug != slugify(tenant_slug):
            raise CrmSyncError(
                f"City and partner already belong to tenant '{tenant.slug}', "
                f"not '{slugify(tenant_slug)}'"
            )
        tenant.name = f"{city.name} / {partner.name}"
        return tenant, False
    tenant = Tenant(
        city_id=city.id,
        partner_id=partner.id,
        slug=slugify(tenant_slug) if tenant_slug else make_tenant_slug(city.name, partner.slug),
        name=f"{city.name} / {partner.name}",
    )
    db.add(tenant)
    await db.flush()
    return tenant, True


async def get_or_create_venue(
    db: AsyncSession,
    *,
    tenant: Tenant,
    name: str | None,
) -> tuple[Venue | None, bool]:
    if not name:
        return None, False
    slug = slugify(name)
    venue = await db.scalar(select(Venue).where(Venue.tenant_id == tenant.id, Venue.slug == slug))
    if venue:
        venue.name = name
        return venue, False
    venue = Venue(tenant_id=tenant.id, slug=slug, name=name)
    db.add(venue)
    await db.flush()
    return venue, True


async def find_existing_student(
    db: AsyncSession,
    *,
    tenant: Tenant,
    row: CrmStudentRow,
    access_code: str,
) -> Student | None:
    if row.lms_student_id:
        return await db.scalar(
            select(Student).where(
                Student.tenant_id == tenant.id,
                Student.lms_student_id == normalize_student_code(row.lms_student_id),
            )
        )
    return await db.scalar(
        select(Student).where(
            Student.tenant_id == tenant.id,
            Student.student_access_code == access_code,
        )
    )


async def ensure_wallet(db: AsyncSession, *, tenant: Tenant, student: Student) -> bool:
    wallet = await db.scalar(select(Wallet).where(Wallet.student_id == student.id))
    if wallet:
        return False
    db.add(Wallet(tenant_id=tenant.id, student_id=student.id, balance=0))
    await db.flush()
    return True


async def get_or_create_contact(
    db: AsyncSession,
    *,
    tenant: Tenant,
    contact_id: str,
    display_name: str | None,
) -> tuple[Contact, bool]:
    normalized_contact_id = normalize_contact_id(contact_id)
    contact = await db.scalar(
        select(Contact).where(
            Contact.tenant_id == tenant.id,
            Contact.external_contact_id == normalized_contact_id,
        )
    )
    if contact:
        contact.display_name = display_name or contact.display_name
        return contact, False
    contact = Contact(
        tenant_id=tenant.id,
        external_contact_id=normalized_contact_id,
        display_name=display_name,
    )
    db.add(contact)
    await db.flush()
    return contact, True


async def ensure_contact_student_link(
    db: AsyncSession,
    *,
    tenant: Tenant,
    contact: Contact,
    student: Student,
) -> bool:
    link = await db.scalar(
        select(ContactStudentLink).where(
            ContactStudentLink.tenant_id == tenant.id,
            ContactStudentLink.contact_id == contact.id,
            ContactStudentLink.student_id == student.id,
        )
    )
    if link:
        return False
    db.add(
        ContactStudentLink(
            tenant_id=tenant.id,
            contact_id=contact.id,
            student_id=student.id,
        )
    )
    await db.flush()
    return True


async def upsert_crm_student_rows(
    db: AsyncSession,
    rows: list[CrmStudentRow],
    *,
    defaults: CrmSyncDefaults,
    commit: bool = True,
    target_tenant: Tenant | None = None,
) -> CrmSyncResult:
    result = CrmSyncResult()
    partner: Partner | None = None
    if target_tenant is None and defaults.tenant_slug:
        requested_slug = slugify(defaults.tenant_slug)
        target_tenant = await db.scalar(select(Tenant).where(Tenant.slug == requested_slug))
        if target_tenant is None:
            city, created_city = await get_or_create_city(db, defaults.fallback_city_name)
            if created_city:
                result = result.add(created_cities=result.created_cities + 1)
            partner, created_partner = await get_or_create_partner(
                db,
                slug=defaults.partner_slug,
                name=defaults.partner_name,
            )
            if created_partner:
                result = result.add(created_partners=result.created_partners + 1)
            target_tenant, created_tenant = await get_or_create_tenant(
                db,
                city=city,
                partner=partner,
                tenant_slug=requested_slug,
            )
            if created_tenant:
                result = result.add(created_tenants=result.created_tenants + 1)
    elif target_tenant is None:
        partner, created_partner = await get_or_create_partner(
            db,
            slug=defaults.partner_slug,
            name=defaults.partner_name,
        )
        if created_partner:
            result = result.add(created_partners=result.created_partners + 1)

    for row in rows:
        if target_tenant is not None:
            tenant = target_tenant
        else:
            city_name = row.city or defaults.fallback_city_name
            city, created_city = await get_or_create_city(db, city_name)
            if created_city:
                result = result.add(created_cities=result.created_cities + 1)

            if partner is None:
                raise CrmSyncError("CRM partner is not initialized")
            tenant, created_tenant = await get_or_create_tenant(db, city=city, partner=partner)
            if created_tenant:
                result = result.add(created_tenants=result.created_tenants + 1)

        if not row.first_name:
            result = result.add(skipped_rows=result.skipped_rows + 1)
            continue

        venue, created_venue = await get_or_create_venue(db, tenant=tenant, name=row.venue_name)
        if created_venue:
            result = result.add(created_venues=result.created_venues + 1)

        access_code = (
            normalize_student_code(row.lms_student_id)
            if row.lms_student_id
            else make_generated_access_code(tenant_slug=tenant.slug, row=row)
        )
        student = await find_existing_student(db, tenant=tenant, row=row, access_code=access_code)
        if student is None:
            student = Student(
                tenant_id=tenant.id,
                venue_id=venue.id if venue else None,
                lms_student_id=normalize_student_code(row.lms_student_id)
                if row.lms_student_id
                else None,
                student_access_code=access_code,
                first_name=row.first_name,
            )
            db.add(student)
            result = result.add(created_students=result.created_students + 1)
        else:
            result = result.add(updated_students=result.updated_students + 1)

        student.venue_id = venue.id if venue else None
        student.first_name = row.first_name
        student.last_name = row.last_name
        student.group_name = row.group_name
        student.course_name = row.course_name
        student.venue_name = row.venue_name
        student.teacher_name = row.teacher_name

        await db.flush()
        if await ensure_wallet(db, tenant=tenant, student=student):
            result = result.add(created_wallets=result.created_wallets + 1)

        for contact_id in split_contact_ids(row.contact_ids):
            contact, created_contact = await get_or_create_contact(
                db,
                tenant=tenant,
                contact_id=contact_id,
                display_name=row.contact_names,
            )
            if created_contact:
                result = result.add(created_contacts=result.created_contacts + 1)
            if await ensure_contact_student_link(
                db,
                tenant=tenant,
                contact=contact,
                student=student,
            ):
                result = result.add(
                    created_contact_student_links=result.created_contact_student_links + 1
                )

    if commit:
        await db.commit()

    return result
