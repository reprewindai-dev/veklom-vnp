"""Add VNP scores and VABP sandbox models

Revision ID: cf105b7c216a
Revises: f61fc0779406
Create Date: 2026-07-12 23:51:59.040507

"""
from alembic import op
import sqlalchemy as sa


revision = 'cf105b7c216a'
down_revision = 'f61fc0779406'
branch_labels = None
depends_on = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    # Create ENUMs
    sa.Enum('pending', 'running', 'completed', 'failed', name='vabp_run_state_enum').create(op.get_bind())

    # Create vnp_scores
    op.create_table(
        'vnp_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(length=200), nullable=False),
        sa.Column('measurement_window_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operational_score', sa.Float(), nullable=False),
        sa.Column('latency_score', sa.Float(), nullable=False),
        sa.Column('availability_score', sa.Float(), nullable=False),
        sa.Column('reliability_score', sa.Float(), nullable=False),
        sa.Column('score_version', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['measurement_window_id'], ['vnp_measurement_windows.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vnp_scores_target_time', 'vnp_scores', ['target_id', 'created_at'], unique=False)

    # Create vnp_vabp_runs
    op.create_table(
        'vnp_vabp_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(length=200), nullable=False),
        sa.Column('run_state', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='vabp_run_state_enum', create_type=False), nullable=False),
        sa.Column('total_score', sa.Integer(), nullable=True),
        sa.Column('suite_version', sa.String(length=50), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_reason', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create vnp_vabp_test_results
    op.create_table(
        'vnp_vabp_test_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('test_name', sa.String(length=200), nullable=False),
        sa.Column('dimension', sa.String(length=50), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('score_awarded', sa.Integer(), nullable=False),
        sa.Column('max_score', sa.Integer(), nullable=False),
        sa.Column('evidence_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['vnp_vabp_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create vnp_trust_certificates
    op.create_table(
        'vnp_trust_certificates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(length=200), nullable=False),
        sa.Column('vabp_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('passed_threshold', sa.Boolean(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pgl_evidence_id', sa.String(), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['vabp_run_id'], ['vnp_vabp_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_trust_certs_target', 'vnp_trust_certificates', ['target_id', 'issued_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_trust_certs_target', table_name='vnp_trust_certificates')
    op.drop_table('vnp_trust_certificates')
    op.drop_table('vnp_vabp_test_results')
    op.drop_table('vnp_vabp_runs')
    op.drop_index('idx_vnp_scores_target_time', table_name='vnp_scores')
    op.drop_table('vnp_scores')
    sa.Enum('pending', 'running', 'completed', 'failed', name='vabp_run_state_enum').drop(op.get_bind())
