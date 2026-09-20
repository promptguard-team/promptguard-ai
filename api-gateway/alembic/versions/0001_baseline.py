"""baseline: users and audit_events as they exist today

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("chat_user", "ciso", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "allowed",
                "blocked_prompt",
                "blocked_response",
                name="auditaction",
            ),
            nullable=False,
        ),
        sa.Column("rule", sa.String(64), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    sa.Enum(name="auditaction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
