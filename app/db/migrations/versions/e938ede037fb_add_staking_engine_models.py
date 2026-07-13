"""Add staking engine models

Revision ID: e938ede037fb
Revises: cf105b7c216a
Create Date: 2026-07-13 01:10:16.630423

"""
from alembic import op
import sqlalchemy as sa


revision = 'e938ede037fb'
down_revision = 'cf105b7c216a'
branch_labels = None
depends_on = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    # Enums safely
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bond_state_enum') THEN CREATE TYPE bond_state_enum AS ENUM ('draft', 'funded', 'active', 'breach_pending', 'slashed', 'released'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'challenge_state_enum') THEN CREATE TYPE challenge_state_enum AS ENUM ('pending', 'verifying', 'upheld', 'rejected'); END IF; END $$;")
    
    bond_state = postgresql.ENUM('draft', 'funded', 'active', 'breach_pending', 'slashed', 'released', name='bond_state_enum', create_type=False)
    challenge_state = postgresql.ENUM('pending', 'verifying', 'upheld', 'rejected', name='challenge_state_enum', create_type=False)

    # Provider Bonds
    op.create_table('vnp_provider_bonds',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_api_id', sa.String(length=200), nullable=False),
        sa.Column('state', bond_state, nullable=False, server_default='draft'),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('funded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['vnp_providers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_provider_bonds_target_state', 'vnp_provider_bonds', ['target_api_id', 'state'], unique=False)

    # Bond Conditions
    op.create_table('vnp_bond_conditions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bond_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('operator', sa.String(length=10), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['bond_id'], ['vnp_provider_bonds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Challenges
    op.create_table('vnp_challenges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bond_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('challenger_id', sa.String(length=100), nullable=False),
        sa.Column('state', challenge_state, nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['bond_id'], ['vnp_provider_bonds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Challenge Evidence
    op.create_table('vnp_challenge_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('challenge_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('measurement_window_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('vabp_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('evidence_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['vnp_challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['measurement_window_id'], ['vnp_measurement_windows.id'], ),
        sa.ForeignKeyConstraint(['vabp_run_id'], ['vnp_vabp_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Resolutions
    op.create_table('vnp_resolutions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('challenge_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('pgl_receipt_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['vnp_challenges.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('vnp_resolutions')
    op.drop_table('vnp_challenge_evidence')
    op.drop_table('vnp_challenges')
    op.drop_table('vnp_bond_conditions')
    op.drop_index('idx_provider_bonds_target_state', table_name='vnp_provider_bonds')
    op.drop_table('vnp_provider_bonds')
    
    op.execute("DROP TYPE bond_state_enum")
    op.execute("DROP TYPE challenge_state_enum")
