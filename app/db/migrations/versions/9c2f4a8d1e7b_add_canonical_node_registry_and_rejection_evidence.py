"""Add canonical five-site registry and signed-ingestion evidence.

Revision ID: 9c2f4a8d1e7b
Revises: f61fc0779406
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9c2f4a8d1e7b"
down_revision = "4a6c552e87de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vnp_nodes", sa.Column("site_code", sa.String(length=50), nullable=True))
    op.add_column("vnp_nodes", sa.Column("provider", sa.String(length=50), nullable=True))
    op.add_column("vnp_nodes", sa.Column("platform", sa.String(length=50), nullable=True))
    op.add_column("vnp_nodes", sa.Column("coolify_server_uuid", sa.String(length=100), nullable=True))
    op.add_column("vnp_nodes", sa.Column("coolify_application_uuid", sa.String(length=100), nullable=True))
    op.add_column("vnp_nodes", sa.Column("image_digest", sa.String(length=255), nullable=True))
    op.add_column("vnp_nodes", sa.Column("probe_deployed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vnp_nodes", sa.Column("key_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE vnp_nodes
        SET
            site_code = CASE region_code
                WHEN 'us-east-1-ash' THEN 'us-ashburn'
                WHEN 'us-west-1-hil' THEN 'us-hillsboro'
                WHEN 'eu-central-1-nur' THEN 'de-nuremberg'
                WHEN 'eu-central-1-fal' THEN 'de-falkenstein'
                WHEN 'ap-southeast-1-sin' THEN 'sg-singapore'
                ELSE region_code
            END,
            region_code = CASE region_code
                WHEN 'us-east-1-ash' THEN 'us-ashburn'
                WHEN 'us-west-1-hil' THEN 'us-hillsboro'
                WHEN 'eu-central-1-nur' THEN 'de-nuremberg'
                WHEN 'eu-central-1-fal' THEN 'de-falkenstein'
                WHEN 'ap-southeast-1-sin' THEN 'sg-singapore'
                ELSE region_code
            END,
            provider = 'Hetzner',
            platform = 'Coolify',
            coolify_server_uuid = CASE name
                WHEN 'Ashburn Node' THEN 'q12oryfd1plt357b0550x0f5'
                WHEN 'Hillsboro Node' THEN 'localhost'
                WHEN 'Nuremberg Node' THEN 'xbqgn9v7jqgzycynzc6xgcyi'
                WHEN 'Falkenstein Node' THEN 'pjepy7fyr3unc0sl36if38vt'
                WHEN 'Singapore Node' THEN 'zls3c5cx8f3jngp5rlp0os0g'
                ELSE 'unregistered'
            END
        """
    )

    op.alter_column("vnp_nodes", "site_code", nullable=False)
    op.alter_column("vnp_nodes", "provider", nullable=False)
    op.alter_column("vnp_nodes", "platform", nullable=False)
    op.alter_column("vnp_nodes", "coolify_server_uuid", nullable=False)
    op.create_unique_constraint("uq_vnp_nodes_site_code", "vnp_nodes", ["site_code"])

    op.add_column("vnp_node_heartbeats", sa.Column("heartbeat_id", sa.String(length=100), nullable=True))
    op.add_column("vnp_node_heartbeats", sa.Column("sequence", sa.Integer(), nullable=True))
    op.add_column("vnp_node_heartbeats", sa.Column("payload_digest", sa.String(length=128), nullable=True))
    op.execute(
        """
        UPDATE vnp_node_heartbeats
        SET heartbeat_id = 'legacy-' || id::text,
            sequence = 0,
            payload_digest = md5(id::text)
        """
    )
    op.alter_column("vnp_node_heartbeats", "heartbeat_id", nullable=False)
    op.alter_column("vnp_node_heartbeats", "sequence", nullable=False)
    op.alter_column("vnp_node_heartbeats", "payload_digest", nullable=False)
    op.create_unique_constraint("uq_vnp_node_heartbeats_heartbeat_id", "vnp_node_heartbeats", ["heartbeat_id"])

    op.add_column("vnp_observations", sa.Column("site_code", sa.String(length=50), nullable=True))
    op.add_column("vnp_observations", sa.Column("write_ms", sa.Integer(), nullable=True))
    op.add_column("vnp_observations", sa.Column("body_ms", sa.Integer(), nullable=True))
    op.add_column("vnp_observations", sa.Column("http_version", sa.String(length=20), nullable=True))
    op.add_column("vnp_observations", sa.Column("tls_version", sa.String(length=50), nullable=True))
    op.add_column("vnp_observations", sa.Column("tls_cipher", sa.String(length=100), nullable=True))
    op.add_column("vnp_observations", sa.Column("transport_reachable", sa.Boolean(), nullable=True))
    op.add_column("vnp_observations", sa.Column("semantic_assertion", sa.Boolean(), nullable=True))
    op.add_column("vnp_observations", sa.Column("error_category", sa.String(length=100), nullable=True))
    op.add_column("vnp_observations", sa.Column("payload_digest", sa.String(length=128), nullable=True))
    op.execute(
        """
        UPDATE vnp_observations
        SET site_code = region,
            transport_reachable = (http_status IS NOT NULL),
            payload_digest = md5(observation_id)
        """
    )
    op.alter_column("vnp_observations", "site_code", nullable=False)
    op.alter_column("vnp_observations", "transport_reachable", nullable=False)
    op.alter_column("vnp_observations", "payload_digest", nullable=False)

    op.create_table(
        "vnp_observation_rejections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", sa.String(length=100), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signature_key_id", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("payload_digest", sa.String(length=128), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["vnp_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_vnp_observation_rejections_observation_id",
        "vnp_observation_rejections",
        ["observation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_vnp_observation_rejections_observation_id",
        table_name="vnp_observation_rejections",
    )
    op.drop_table("vnp_observation_rejections")
    for column in (
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
        op.drop_column("vnp_observations", column)
    op.drop_constraint("uq_vnp_node_heartbeats_heartbeat_id", "vnp_node_heartbeats", type_="unique")
    op.drop_column("vnp_node_heartbeats", "payload_digest")
    op.drop_column("vnp_node_heartbeats", "sequence")
    op.drop_column("vnp_node_heartbeats", "heartbeat_id")
    op.drop_constraint("uq_vnp_nodes_site_code", "vnp_nodes", type_="unique")
    for column in (
        "key_verified_at",
        "probe_deployed_at",
        "image_digest",
        "coolify_application_uuid",
        "coolify_server_uuid",
        "platform",
        "provider",
        "site_code",
    ):
        op.drop_column("vnp_nodes", column)
