"""canonical Hetzner Coolify node registry

Revision ID: a1f4c7b8d9e2
Revises: f61fc0779406
Create Date: 2026-07-13 20:50:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "a1f4c7b8d9e2"
down_revision = "f61fc0779406"
branch_labels = None
depends_on = None


def _add_column_if_missing(column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("vnp_nodes")}
    if column.name not in columns:
        op.add_column("vnp_nodes", column)


def upgrade() -> None:
    _add_column_if_missing(sa.Column("host_reference", sa.String(length=255), nullable=True))
    _add_column_if_missing(sa.Column("city", sa.String(length=100), nullable=True))
    _add_column_if_missing(sa.Column("country", sa.String(length=100), nullable=True))
    _add_column_if_missing(sa.Column("infrastructure_provider", sa.String(length=100), nullable=False, server_default="Hetzner"))
    _add_column_if_missing(sa.Column("deployment_platform", sa.String(length=100), nullable=False, server_default="Coolify"))
    _add_column_if_missing(sa.Column("coolify_application_ref", sa.String(length=255), nullable=True))
    _add_column_if_missing(sa.Column("container_image_digest", sa.String(length=255), nullable=True))
    _add_column_if_missing(sa.Column("signing_key_id", sa.String(length=100), nullable=True))
    _add_column_if_missing(sa.Column("key_status", sa.String(length=50), nullable=False, server_default="configuration_incomplete"))

    op.execute(
        """
        UPDATE vnp_nodes
        SET
            name = 'VNP Ashburn Probe',
            host_reference = 'veklom-edge-us-east',
            physical_location = 'Ashburn, Virginia, United States',
            region_code = 'us-ashburn',
            macro_region = 'North America',
            city = 'Ashburn',
            country = 'United States',
            jurisdiction = 'United States',
            infrastructure_provider = 'Hetzner',
            deployment_platform = 'Coolify',
            registration_status = 'configuration_incomplete',
            key_status = 'configuration_incomplete'
        WHERE id = '00000000-0000-0000-0000-000000000001'
           OR region_code = 'us-east-1-ash';

        UPDATE vnp_nodes
        SET
            name = 'VNP Hillsboro Probe',
            host_reference = 'veklom-prod-1',
            physical_location = 'Hillsboro, Oregon, United States',
            region_code = 'us-hillsboro',
            macro_region = 'North America',
            city = 'Hillsboro',
            country = 'United States',
            jurisdiction = 'United States',
            infrastructure_provider = 'Hetzner',
            deployment_platform = 'Coolify',
            registration_status = 'configuration_incomplete',
            key_status = 'configuration_incomplete'
        WHERE id = '00000000-0000-0000-0000-000000000002'
           OR region_code = 'us-west-1-hil';

        UPDATE vnp_nodes
        SET
            name = 'VNP Nuremberg Probe',
            host_reference = 'veklom-edge-eu-north2',
            physical_location = 'Nuremberg, Germany',
            region_code = 'de-nuremberg',
            macro_region = 'Europe',
            city = 'Nuremberg',
            country = 'Germany',
            jurisdiction = 'European Union / GDPR',
            infrastructure_provider = 'Hetzner',
            deployment_platform = 'Coolify',
            registration_status = 'configuration_incomplete',
            key_status = 'configuration_incomplete'
        WHERE id = '00000000-0000-0000-0000-000000000003'
           OR region_code = 'eu-central-1-nur';

        UPDATE vnp_nodes
        SET
            name = 'VNP Falkenstein Probe',
            host_reference = 'veklom-edge-eu-central',
            physical_location = 'Falkenstein, Germany',
            region_code = 'de-falkenstein',
            macro_region = 'Europe',
            city = 'Falkenstein',
            country = 'Germany',
            jurisdiction = 'European Union / GDPR',
            infrastructure_provider = 'Hetzner',
            deployment_platform = 'Coolify',
            registration_status = 'configuration_incomplete',
            key_status = 'configuration_incomplete'
        WHERE id = '00000000-0000-0000-0000-000000000004'
           OR region_code = 'eu-central-1-fal';

        UPDATE vnp_nodes
        SET
            name = 'VNP Singapore Probe',
            host_reference = 'veklom-edge-ap-southeast',
            physical_location = 'Singapore',
            region_code = 'sg-singapore',
            macro_region = 'APAC',
            city = 'Singapore',
            country = 'Singapore',
            jurisdiction = 'Singapore / APAC',
            infrastructure_provider = 'Hetzner',
            deployment_platform = 'Coolify',
            registration_status = 'configuration_incomplete',
            key_status = 'configuration_incomplete'
        WHERE id = '00000000-0000-0000-0000-000000000005'
           OR region_code = 'ap-southeast-1-sin';
        """
    )


def downgrade() -> None:
    for column in (
        "key_status",
        "signing_key_id",
        "container_image_digest",
        "coolify_application_ref",
        "deployment_platform",
        "infrastructure_provider",
        "country",
        "city",
        "host_reference",
    ):
        op.drop_column("vnp_nodes", column)
