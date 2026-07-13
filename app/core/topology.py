from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalVNPNode:
    node_uuid: str
    host_reference: str
    location_code: str
    physical_location: str
    city: str
    country: str
    jurisdiction: str
    infrastructure_provider: str = "Hetzner"
    deployment_platform: str = "Coolify"
    coolify_application_ref: str | None = None
    container_image_digest: str | None = None
    software_version: str | None = None
    signing_key_id: str | None = None
    key_status: str = "configuration_incomplete"


CANONICAL_VNP_NODES: tuple[CanonicalVNPNode, ...] = (
    CanonicalVNPNode(
        node_uuid="00000000-0000-0000-0000-000000000001",
        host_reference="veklom-edge-us-east",
        location_code="us-ashburn",
        physical_location="Ashburn, Virginia, United States",
        city="Ashburn",
        country="United States",
        jurisdiction="United States",
    ),
    CanonicalVNPNode(
        node_uuid="00000000-0000-0000-0000-000000000002",
        host_reference="veklom-prod-1",
        location_code="us-hillsboro",
        physical_location="Hillsboro, Oregon, United States",
        city="Hillsboro",
        country="United States",
        jurisdiction="United States",
    ),
    CanonicalVNPNode(
        node_uuid="00000000-0000-0000-0000-000000000003",
        host_reference="veklom-edge-eu-north2",
        location_code="de-nuremberg",
        physical_location="Nuremberg, Germany",
        city="Nuremberg",
        country="Germany",
        jurisdiction="European Union / GDPR",
    ),
    CanonicalVNPNode(
        node_uuid="00000000-0000-0000-0000-000000000004",
        host_reference="veklom-edge-eu-central",
        location_code="de-falkenstein",
        physical_location="Falkenstein, Germany",
        city="Falkenstein",
        country="Germany",
        jurisdiction="European Union / GDPR",
    ),
    CanonicalVNPNode(
        node_uuid="00000000-0000-0000-0000-000000000005",
        host_reference="veklom-edge-ap-southeast",
        location_code="sg-singapore",
        physical_location="Singapore",
        city="Singapore",
        country="Singapore",
        jurisdiction="Singapore / APAC",
    ),
)

CANONICAL_LOCATION_CODES = frozenset(node.location_code for node in CANONICAL_VNP_NODES)

LEGACY_REGION_CODE_MAP = {
    "us-east-1-ash": "us-ashburn",
    "us-west-1-hil": "us-hillsboro",
    "eu-central-1-nur": "de-nuremberg",
    "eu-central-1-fal": "de-falkenstein",
    "ap-southeast-1-sin": "sg-singapore",
}
