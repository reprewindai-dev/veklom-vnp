"""add signed heartbeat identity fields

Revision ID: b7c4d2e9a103
Revises: a1f4c7b8d9e2
Create Date: 2026-07-15 00:35:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "b7c4d2e9a103"
down_revision = "a1f4c7b8d9e2"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(table_name)
    return any(constraint["name"] == constraint_name for constraint in constraints)


def upgrade() -> None:
    _add_column_if_missing(
        "vnp_node_heartbeats",
        sa.Column("heartbeat_id", sa.String(length=100), nullable=True),
    )
    _add_column_if_missing(
        "vnp_node_heartbeats",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        "vnp_node_heartbeats",
        sa.Column("payload_digest", sa.String(length=128), nullable=True),
    )

    op.execute(
        """
        UPDATE vnp_node_heartbeats
        SET
            heartbeat_id = COALESCE(heartbeat_id, id::text),
            sequence = COALESCE(sequence, 0),
            payload_digest = COALESCE(payload_digest, md5(id::text || node_id::text || timestamp::text))
        """
    )
    op.alter_column("vnp_node_heartbeats", "heartbeat_id", nullable=False)
    op.alter_column("vnp_node_heartbeats", "sequence", nullable=False)
    op.alter_column("vnp_node_heartbeats", "payload_digest", nullable=False)

    if not _constraint_exists("vnp_node_heartbeats", "uq_vnp_node_heartbeats_heartbeat_id"):
        op.create_unique_constraint(
            "uq_vnp_node_heartbeats_heartbeat_id",
            "vnp_node_heartbeats",
            ["heartbeat_id"],
        )


def downgrade() -> None:
    if _constraint_exists("vnp_node_heartbeats", "uq_vnp_node_heartbeats_heartbeat_id"):
        op.drop_constraint(
            "uq_vnp_node_heartbeats_heartbeat_id",
            "vnp_node_heartbeats",
            type_="unique",
        )
    op.drop_column("vnp_node_heartbeats", "payload_digest")
    op.drop_column("vnp_node_heartbeats", "sequence")
    op.drop_column("vnp_node_heartbeats", "heartbeat_id")
