"""restore observation evidence contract

Revision ID: c31f8a407b22
Revises: b7c4d2e9a103
Create Date: 2026-07-15 00:42:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c31f8a407b22"
down_revision = "b7c4d2e9a103"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    _add_column_if_missing("vnp_nodes", sa.Column("site_code", sa.String(length=50), nullable=True))
    op.execute("UPDATE vnp_nodes SET site_code = COALESCE(site_code, region_code)")

    for column in (
        sa.Column("site_code", sa.String(length=50), nullable=True),
        sa.Column("write_ms", sa.Integer(), nullable=True),
        sa.Column("body_ms", sa.Integer(), nullable=True),
        sa.Column("http_version", sa.String(length=20), nullable=True),
        sa.Column("tls_version", sa.String(length=50), nullable=True),
        sa.Column("tls_cipher", sa.String(length=100), nullable=True),
        sa.Column("transport_reachable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("semantic_assertion", sa.Boolean(), nullable=True),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column("payload_digest", sa.String(length=128), nullable=True),
    ):
        _add_column_if_missing("vnp_observations", column)

    op.execute(
        """
        UPDATE vnp_observations
        SET
          site_code = COALESCE(site_code, region),
          payload_digest = COALESCE(payload_digest, md5(observation_id || node_id::text || sequence::text))
        """
    )

    if not _table_exists("vnp_observation_rejections"):
        op.create_table(
            "vnp_observation_rejections",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("observation_id", sa.String(length=100), nullable=False),
            sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("signature_key_id", sa.String(length=100), nullable=True),
            sa.Column("reason", sa.String(length=100), nullable=False),
            sa.Column("payload_digest", sa.String(length=128), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_vnp_observation_rejections_observation_id",
            "vnp_observation_rejections",
            ["observation_id"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("vnp_observation_rejections"):
        op.drop_index("ix_vnp_observation_rejections_observation_id", table_name="vnp_observation_rejections")
        op.drop_table("vnp_observation_rejections")
    for column_name in (
        "payload_digest",
        "error_category",
        "semantic_assertion",
        "transport_reachable",
        "tls_cipher",
        "tls_version",
        "http_version",
        "body_ms",
        "write_ms",
        "site_code",
    ):
        op.drop_column("vnp_observations", column_name)
    op.drop_column("vnp_nodes", "site_code")
