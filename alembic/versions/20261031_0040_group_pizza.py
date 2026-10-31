"""Add group pizza collections without changing wallets, students or links."""

import sqlalchemy as sa

from alembic import op

revision = "20261031_0040"
down_revision = "20261021_0039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pizza_offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("share > 0", name=op.f("ck_pizza_offers_pizza_offer_share_positive")),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["max_accounts.id"],
            name=op.f("fk_pizza_offers_created_by_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_pizza_offers_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pizza_offers")),
    )
    op.create_index(op.f("ix_pizza_offers_tenant_id"), "pizza_offers", ["tenant_id"], unique=False)
    op.create_table(
        "pizza_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("offer_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("group_name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("roster", sa.JSON(), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("collected", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "collected >= 0 AND collected <= target",
            name=op.f("ck_pizza_campaigns_pizza_campaign_amount_range"),
        ),
        sa.CheckConstraint(
            "share > 0 AND target > 0",
            name=op.f("ck_pizza_campaigns_pizza_campaign_amount_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["offer_id"], ["pizza_offers.id"], name=op.f("fk_pizza_campaigns_offer_id_pizza_offers")
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["max_accounts.id"],
            name=op.f("fk_pizza_campaigns_teacher_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_pizza_campaigns_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pizza_campaigns")),
    )
    op.create_index(
        op.f("ix_pizza_campaigns_deadline"), "pizza_campaigns", ["deadline"], unique=False
    )
    op.create_index(op.f("ix_pizza_campaigns_status"), "pizza_campaigns", ["status"], unique=False)
    op.create_index(
        op.f("ix_pizza_campaigns_teacher_id"), "pizza_campaigns", ["teacher_id"], unique=False
    )
    op.create_index(
        op.f("ix_pizza_campaigns_tenant_id"), "pizza_campaigns", ["tenant_id"], unique=False
    )
    op.create_index(
        "uq_pizza_live_group",
        "pizza_campaigns",
        ["tenant_id", "group_name"],
        unique=True,
        postgresql_where=sa.text("status IN ('open','funded','paid','ordered')"),
        sqlite_where=sa.text("status IN ('open','funded','paid','ordered')"),
    )
    op.create_table(
        "pizza_contributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_pizza_contributions_pizza_contribution_positive")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["max_accounts.id"],
            name=op.f("fk_pizza_contributions_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["pizza_campaigns.id"],
            name=op.f("fk_pizza_contributions_campaign_id_pizza_campaigns"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_pizza_contributions_student_id_students")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pizza_contributions")),
        sa.UniqueConstraint("campaign_id", "student_id", name="uq_pizza_contribution_student"),
    )
    op.create_index(
        op.f("ix_pizza_contributions_campaign_id"),
        "pizza_contributions",
        ["campaign_id"],
        unique=False,
    )
    op.create_table(
        "pizza_notices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=30), nullable=False),
        sa.Column("message", sa.String(length=700), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["max_accounts.id"],
            name=op.f("fk_pizza_notices_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["pizza_campaigns.id"],
            name=op.f("fk_pizza_notices_campaign_id_pizza_campaigns"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pizza_notices")),
        sa.UniqueConstraint("campaign_id", "account_id", "event", name="uq_pizza_notice_recipient"),
    )
    op.create_index(
        op.f("ix_pizza_notices_account_id"), "pizza_notices", ["account_id"], unique=False
    )


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM pizza_campaigns")):
        raise RuntimeError("Cannot discard collection transactions; keep the tables")
    for name in ("pizza_notices", "pizza_contributions", "pizza_campaigns", "pizza_offers"):
        op.drop_table(name)
