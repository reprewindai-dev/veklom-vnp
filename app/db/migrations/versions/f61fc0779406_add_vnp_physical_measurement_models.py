"""Add VNP physical measurement models

Revision ID: f61fc0779406
Revises: 145939825773
Create Date: 2026-07-12 23:27:18.629014

"""
from alembic import op
import sqlalchemy as sa


revision = 'f61fc0779406'
down_revision = '145939825773'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # vnp_nodes
    op.create_table(
        'vnp_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('physical_location', sa.String(length=255), nullable=False),
        sa.Column('region_code', sa.String(length=50), nullable=False),
        sa.Column('macro_region', sa.String(length=50), nullable=False),
        sa.Column('jurisdiction', sa.String(length=100), nullable=False),
        sa.Column('gdpr_zone', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('software_version', sa.String(length=50), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_state', sa.String(length=50), nullable=False, server_default='unknown'),
        sa.Column('registration_status', sa.String(length=50), nullable=False, server_default='registered'),
        sa.Column('revocation_state', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('region_code')
    )

    # Hardcode the 5 initial nodes
    op.execute("""
    INSERT INTO vnp_nodes (id, name, physical_location, region_code, macro_region, jurisdiction, gdpr_zone, health_state, registration_status, created_at)
    VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Ashburn Node', 'Ashburn, Virginia', 'us-east-1-ash', 'North America', 'United States', false, 'unknown', 'registered', NOW()),
    ('00000000-0000-0000-0000-000000000002', 'Hillsboro Node', 'Hillsboro, Oregon', 'us-west-1-hil', 'North America', 'United States', false, 'unknown', 'registered', NOW()),
    ('00000000-0000-0000-0000-000000000003', 'Nuremberg Node', 'Nuremberg, Germany', 'eu-central-1-nur', 'Europe', 'European Union', true, 'unknown', 'registered', NOW()),
    ('00000000-0000-0000-0000-000000000004', 'Falkenstein Node', 'Falkenstein, Germany', 'eu-central-1-fal', 'Europe', 'European Union', true, 'unknown', 'registered', NOW()),
    ('00000000-0000-0000-0000-000000000005', 'Singapore Node', 'Singapore', 'ap-southeast-1-sin', 'APAC', 'Singapore', false, 'unknown', 'registered', NOW());
    """)

    # vnp_node_keys
    op.create_table(
        'vnp_node_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_id', sa.String(length=100), nullable=False),
        sa.Column('public_key', sa.String(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['node_id'], ['vnp_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_id')
    )

    # vnp_node_heartbeats
    op.create_table(
        'vnp_node_heartbeats',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('software_version', sa.String(length=50), nullable=False),
        sa.Column('signature_key_id', sa.String(length=100), nullable=False),
        sa.Column('signature', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['node_id'], ['vnp_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # vnp_observations
    op.create_table(
        'vnp_observations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('observation_id', sa.String(length=100), nullable=False),
        sa.Column('node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('region', sa.String(length=50), nullable=False),
        sa.Column('physical_location', sa.String(length=255), nullable=False),
        sa.Column('target_id', sa.String(length=200), nullable=False),
        sa.Column('measurement_profile', sa.String(length=100), nullable=False),
        sa.Column('measurement_version', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dns_ms', sa.Integer(), nullable=True),
        sa.Column('tcp_ms', sa.Integer(), nullable=True),
        sa.Column('tls_ms', sa.Integer(), nullable=True),
        sa.Column('ttfb_ms', sa.Integer(), nullable=True),
        sa.Column('total_ms', sa.Integer(), nullable=True),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('response_fingerprint', sa.String(), nullable=True),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('previous_observation_hash', sa.String(), nullable=True),
        sa.Column('signature_key_id', sa.String(length=100), nullable=False),
        sa.Column('signature', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['node_id'], ['vnp_nodes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('observation_id')
    )
    op.create_index('idx_observations_target_region_time', 'vnp_observations', ['target_id', 'region', 'started_at'], unique=False)

    # vnp_measurement_windows
    op.create_table(
        'vnp_measurement_windows',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(length=200), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('node_count', sa.Integer(), nullable=False),
        sa.Column('physical_location_count', sa.Integer(), nullable=False),
        sa.Column('macro_region_count', sa.Integer(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('freshness', sa.Integer(), nullable=True),
        sa.Column('missing_regions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('provisional_flag', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('confidence_band', sa.String(length=50), nullable=True),
        sa.Column('formula_version', sa.String(length=50), nullable=False),
        sa.Column('evidence_root', sa.String(), nullable=True),
        sa.Column('pgl_evidence_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_measure_win_target_start', 'vnp_measurement_windows', ['target_id', 'window_start'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_measure_win_target_start', table_name='vnp_measurement_windows')
    op.drop_table('vnp_measurement_windows')
    op.drop_index('idx_observations_target_region_time', table_name='vnp_observations')
    op.drop_table('vnp_observations')
    op.drop_table('vnp_node_heartbeats')
    op.drop_table('vnp_node_keys')
    op.drop_table('vnp_nodes')
