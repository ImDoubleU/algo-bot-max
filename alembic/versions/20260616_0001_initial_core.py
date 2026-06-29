"""initial core schema

Revision ID: 20260616_0001
Revises:
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

assignment_status = sa.Enum("ACTIVE", "REVOKED", name="assignmentstatus")
ledger_direction = sa.Enum("CREDIT", "DEBIT", "REVERSAL", name="ledgerdirection")
staff_role = sa.Enum(
    "SUPERADMIN",
    "PARTNER_DIRECTOR",
    "ADMIN",
    "CURATOR",
    "TEACHER",
    name="staffrole",
)
student_access_role = sa.Enum("PARENT", "STUDENT", name="studentaccessrole")
student_access_source = sa.Enum("ID_ENTRY", "ADMIN", "IMPORT", name="studentaccesssource")
student_access_status = sa.Enum("ACTIVE", "REVOKED", "DISPUTED", name="studentaccessstatus")
student_status = sa.Enum("ACTIVE", "DEPARTED", "ARCHIVED", name="studentstatus")
tenant_status = sa.Enum("ACTIVE", "ARCHIVED", name="tenantstatus")


def upgrade() -> None:
    bind = op.get_bind()
    assignment_status.create(bind, checkfirst=True)
    ledger_direction.create(bind, checkfirst=True)
    staff_role.create(bind, checkfirst=True)
    student_access_role.create(bind, checkfirst=True)
    student_access_source.create(bind, checkfirst=True)
    student_access_status.create(bind, checkfirst=True)
    student_status.create(bind, checkfirst=True)
    tenant_status.create(bind, checkfirst=True)

    op.create_table(
        "cities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cities")),
        sa.UniqueConstraint("slug", name=op.f("uq_cities_slug")),
    )
    op.create_index(op.f("ix_cities_slug"), "cities", ["slug"], unique=False)

    op.create_table(
        "partners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partners")),
        sa.UniqueConstraint("slug", name=op.f("uq_partners_slug")),
    )
    op.create_index(op.f("ix_partners_slug"), "partners", ["slug"], unique=False)

    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", tenant_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], name=op.f("fk_tenants_city_id_cities")),
        sa.ForeignKeyConstraint(
            ["partner_id"], ["partners.id"], name=op.f("fk_tenants_partner_id_partners")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("city_id", "partner_id", name="uq_tenants_city_partner"),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.create_index(op.f("ix_tenants_city_id"), "tenants", ["city_id"], unique=False)
    op.create_index(op.f("ix_tenants_partner_id"), "tenants", ["partner_id"], unique=False)
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=False)

    op.create_table(
        "max_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("max_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_max_accounts")),
        sa.UniqueConstraint("max_user_id", name=op.f("uq_max_accounts_max_user_id")),
    )
    op.create_index(
        op.f("ix_max_accounts_max_user_id"), "max_accounts", ["max_user_id"], unique=False
    )

    op.create_table(
        "staff_role_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("role", staff_role, nullable=False),
        sa.Column("status", assignment_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["max_accounts.id"],
            name=op.f("fk_staff_role_assignments_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_staff_role_assignments_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_role_assignments")),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "role",
            name="uq_staff_role_assignments_tenant_account_role",
        ),
    )
    op.create_index(
        op.f("ix_staff_role_assignments_account_id"),
        "staff_role_assignments",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_role_assignments_tenant_id"),
        "staff_role_assignments",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("address", sa.String(length=260), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_venues_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venues")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_venues_tenant_slug"),
    )
    op.create_index(op.f("ix_venues_tenant_id"), "venues", ["tenant_id"], unique=False)

    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=True),
        sa.Column("lms_student_id", sa.String(length=120), nullable=True),
        sa.Column("student_access_code", sa.String(length=80), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("group_name", sa.String(length=160), nullable=True),
        sa.Column("course_name", sa.String(length=160), nullable=True),
        sa.Column("venue_name", sa.String(length=160), nullable=True),
        sa.Column("teacher_name", sa.String(length=160), nullable=True),
        sa.Column("status", student_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_students_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name=op.f("fk_students_venue_id_venues")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
        sa.UniqueConstraint("tenant_id", "lms_student_id", name="uq_students_tenant_lms_student"),
        sa.UniqueConstraint(
            "tenant_id", "student_access_code", name="uq_students_tenant_access_code"
        ),
    )
    op.create_index(
        op.f("ix_students_lms_student_id"), "students", ["lms_student_id"], unique=False
    )
    op.create_index(
        op.f("ix_students_student_access_code"), "students", ["student_access_code"], unique=False
    )
    op.create_index(op.f("ix_students_tenant_id"), "students", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_students_venue_id"), "students", ["venue_id"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("external_contact_id", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_contacts_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint(
            "tenant_id", "external_contact_id", name="uq_contacts_tenant_external_id"
        ),
    )
    op.create_index(
        op.f("ix_contacts_external_contact_id"),
        "contacts",
        ["external_contact_id"],
        unique=False,
    )
    op.create_index(op.f("ix_contacts_tenant_id"), "contacts", ["tenant_id"], unique=False)

    op.create_table(
        "contact_student_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_contact_student_links_contact_id_contacts"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_contact_student_links_student_id_students"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_contact_student_links_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_student_links")),
        sa.UniqueConstraint(
            "tenant_id",
            "contact_id",
            "student_id",
            name="uq_contact_student_links_tenant_contact_student",
        ),
    )
    op.create_index(
        op.f("ix_contact_student_links_contact_id"),
        "contact_student_links",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contact_student_links_student_id"),
        "contact_student_links",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contact_student_links_tenant_id"),
        "contact_student_links",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "student_access_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("role", student_access_role, nullable=False),
        sa.Column("status", student_access_status, nullable=False),
        sa.Column("source", student_access_source, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["max_accounts.id"],
            name=op.f("fk_student_access_links_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_student_access_links_student_id_students"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_student_access_links_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_access_links")),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "student_id",
            "role",
            name="uq_student_access_links_tenant_account_student_role",
        ),
    )
    op.create_index(
        op.f("ix_student_access_links_account_id"),
        "student_access_links",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_access_links_student_id"),
        "student_access_links",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_student_access_links_tenant_id"),
        "student_access_links",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "wallets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_wallets_student_id_students")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_wallets_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallets")),
        sa.UniqueConstraint("student_id", name=op.f("uq_wallets_student_id")),
    )
    op.create_index(op.f("ix_wallets_student_id"), "wallets", ["student_id"], unique=False)
    op.create_index(op.f("ix_wallets_tenant_id"), "wallets", ["tenant_id"], unique=False)

    op.create_table(
        "astrocoin_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("direction", ledger_direction, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_astrocoin_ledger_entries_actor_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_astrocoin_ledger_entries_student_id_students"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_astrocoin_ledger_entries_tenant_id_tenants"),
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name=op.f("fk_astrocoin_ledger_entries_wallet_id_wallets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_astrocoin_ledger_entries")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_astrocoin_ledger_entries_idempotency_key")
        ),
    )
    op.create_index(
        op.f("ix_astrocoin_ledger_entries_actor_account_id"),
        "astrocoin_ledger_entries",
        ["actor_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_astrocoin_ledger_entries_student_id"),
        "astrocoin_ledger_entries",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_astrocoin_ledger_entries_tenant_id"),
        "astrocoin_ledger_entries",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_astrocoin_ledger_entries_wallet_id"),
        "astrocoin_ledger_entries",
        ["wallet_id"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_audit_logs_actor_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_audit_logs_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_actor_account_id"), "audit_logs", ["actor_account_id"], unique=False
    )
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_tenant_id"), "audit_logs", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_tenant_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_account_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(
        op.f("ix_astrocoin_ledger_entries_wallet_id"), table_name="astrocoin_ledger_entries"
    )
    op.drop_index(
        op.f("ix_astrocoin_ledger_entries_tenant_id"), table_name="astrocoin_ledger_entries"
    )
    op.drop_index(
        op.f("ix_astrocoin_ledger_entries_student_id"), table_name="astrocoin_ledger_entries"
    )
    op.drop_index(
        op.f("ix_astrocoin_ledger_entries_actor_account_id"), table_name="astrocoin_ledger_entries"
    )
    op.drop_table("astrocoin_ledger_entries")

    op.drop_index(op.f("ix_wallets_tenant_id"), table_name="wallets")
    op.drop_index(op.f("ix_wallets_student_id"), table_name="wallets")
    op.drop_table("wallets")

    op.drop_index(op.f("ix_student_access_links_tenant_id"), table_name="student_access_links")
    op.drop_index(op.f("ix_student_access_links_student_id"), table_name="student_access_links")
    op.drop_index(op.f("ix_student_access_links_account_id"), table_name="student_access_links")
    op.drop_table("student_access_links")

    op.drop_index(op.f("ix_contact_student_links_tenant_id"), table_name="contact_student_links")
    op.drop_index(op.f("ix_contact_student_links_student_id"), table_name="contact_student_links")
    op.drop_index(op.f("ix_contact_student_links_contact_id"), table_name="contact_student_links")
    op.drop_table("contact_student_links")

    op.drop_index(op.f("ix_contacts_tenant_id"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_external_contact_id"), table_name="contacts")
    op.drop_table("contacts")

    op.drop_index(op.f("ix_students_venue_id"), table_name="students")
    op.drop_index(op.f("ix_students_tenant_id"), table_name="students")
    op.drop_index(op.f("ix_students_student_access_code"), table_name="students")
    op.drop_index(op.f("ix_students_lms_student_id"), table_name="students")
    op.drop_table("students")

    op.drop_index(op.f("ix_staff_role_assignments_tenant_id"), table_name="staff_role_assignments")
    op.drop_index(op.f("ix_staff_role_assignments_account_id"), table_name="staff_role_assignments")
    op.drop_table("staff_role_assignments")

    op.drop_index(op.f("ix_venues_tenant_id"), table_name="venues")
    op.drop_table("venues")

    op.drop_index(op.f("ix_max_accounts_max_user_id"), table_name="max_accounts")
    op.drop_table("max_accounts")

    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_partner_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_city_id"), table_name="tenants")
    op.drop_table("tenants")

    op.drop_index(op.f("ix_partners_slug"), table_name="partners")
    op.drop_table("partners")

    op.drop_index(op.f("ix_cities_slug"), table_name="cities")
    op.drop_table("cities")

    bind = op.get_bind()
    tenant_status.drop(bind, checkfirst=True)
    student_status.drop(bind, checkfirst=True)
    student_access_status.drop(bind, checkfirst=True)
    student_access_source.drop(bind, checkfirst=True)
    student_access_role.drop(bind, checkfirst=True)
    staff_role.drop(bind, checkfirst=True)
    ledger_direction.drop(bind, checkfirst=True)
    assignment_status.drop(bind, checkfirst=True)
