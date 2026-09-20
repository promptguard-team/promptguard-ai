"""add ML verdict columns and the provider_error action

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'provider_error'")

    ml_status = sa.Enum("skipped", "ok", "unavailable", name="mlstatus")
    ml_status.create(bind, checkfirst=True)

    op.add_column(
        "audit_events",
        sa.Column("ml_status", ml_status, nullable=False, server_default="skipped"),
    )
    op.add_column("audit_events", sa.Column("ml_score", sa.Float(), nullable=True))
    op.add_column("audit_events", sa.Column("ml_label", sa.String(32), nullable=True))
    op.add_column(
        "audit_events", sa.Column("ml_model_version", sa.String(64), nullable=True)
    )
    op.add_column(
        "audit_events",
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("audit_events", "flagged")
    op.drop_column("audit_events", "ml_model_version")
    op.drop_column("audit_events", "ml_label")
    op.drop_column("audit_events", "ml_score")
    op.drop_column("audit_events", "ml_status")
    sa.Enum(name="mlstatus").drop(op.get_bind(), checkfirst=True)
    # PostgreSQL cannot remove a value from an enum type once added, so
    # 'provider_error' stays in auditaction after this downgrade. Any rows
    # using it must be migrated to another action before downgrading.
