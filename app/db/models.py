import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, JSON, ForeignKey, DateTime, Enum, Numeric, BigInteger, UniqueConstraint, Index, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.database import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# Enums
class TenantType(str, enum.Enum):
    provider = "provider"
    customer = "customer"
    validator = "validator"
    operator = "operator"

class ApiStatus(str, enum.Enum):
    active = "active"
    degraded = "degraded"
    disabled = "disabled"
    pending = "pending"

class ProbeResultState(str, enum.Enum):
    success = "success"
    timeout = "timeout"
    http_error = "http_error"
    transport_error = "transport_error"
    dns_error = "dns_error"
    tls_error = "tls_error"

class IncidentState(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"
    suppressed = "suppressed"

class LedgerEntryType(str, enum.Enum):
    credit = "credit"
    debit = "debit"
    hold = "hold"
    release = "release"
    refund = "refund"
    adjustment = "adjustment"
    slash = "slash"
    reward = "reward"

class SettlementState(str, enum.Enum):
    pending = "pending"
    posted = "posted"
    failed = "failed"
    reversed = "reversed"

class ValidatorState(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    challenged = "challenged"
    retired = "retired"

class AttestationState(str, enum.Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"


# Models
class Provider(Base):
    __tablename__ = "vnp_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(100), unique=True, nullable=False)
    legal_name = Column(String(255), nullable=False)
    support_email = Column(String(255))
    billing_email = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    
    apis = relationship("Api", back_populates="provider", cascade="all, delete-orphan")


class Api(Base):
    __tablename__ = "vnp_apis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("vnp_providers.id", ondelete="CASCADE"), nullable=False)
    api_did = Column(String(200), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(String(64), nullable=False)
    base_url = Column(String, nullable=False)
    health_path = Column(String, nullable=False, default="/health")
    auth_scheme = Column(String(50), nullable=False)
    x402_ready = Column(Boolean, nullable=False, default=False)
    pricing_model = Column(String(50), nullable=False, default="metered")
    current_composite_score = Column(Float, nullable=False, default=100.0)
    stability_rating = Column(String(50), nullable=False, default="Stable")
    status = Column(Enum(ApiStatus, name="api_status_enum", create_type=False), nullable=False, default=ApiStatus.active)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    
    provider = relationship("Provider", back_populates="apis")
    regions = relationship("ApiRegion", back_populates="api", cascade="all, delete-orphan")


class ApiRegion(Base):
    __tablename__ = "vnp_api_regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(UUID(as_uuid=True), ForeignKey("vnp_apis.id", ondelete="CASCADE"), nullable=False)
    region_code = Column(String(50), nullable=False)
    endpoint_url = Column(String, nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("api_id", "region_code", name="uq_vnp_api_regions_api_region"),
        Index("idx_api_regions_lookup", "api_id", "region_code", postgresql_where=(active == True)),
    )

    api = relationship("Api", back_populates="regions")


class Customer(Base):
    __tablename__ = "vnp_customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    billing_mode = Column(String(50), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    stripe_customer_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    
    projects = relationship("Project", back_populates="customer", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "vnp_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("vnp_customers.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    environment = Column(String(50), nullable=False)

    __table_args__ = (
        UniqueConstraint("customer_id", "name", "environment", name="uq_vnp_projects_cust_name_env"),
    )

    customer = relationship("Customer", back_populates="projects")


class SdkCredential(Base):
    __tablename__ = "vnp_sdk_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("vnp_projects.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(255), nullable=False)
    api_key_hash = Column(String, nullable=False)
    public_key = Column(String, nullable=False)
    scopes = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class RoutePolicy(Base):
    __tablename__ = "vnp_route_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("vnp_customers.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    max_p99_latency_ms = Column(Integer)
    minimum_trust_score = Column(Numeric(5, 2))
    allowed_regions = Column(JSONB, nullable=False, default=[])
    allowed_provider_ids = Column(JSONB, nullable=False, default=[])
    weights = Column(JSONB, nullable=False)
    failover_mode = Column(String(50), nullable=False)


class ProbeEvent(Base):
    """Partitioned table for VNP data plane measurements."""
    __tablename__ = "vnp_probe_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(100), unique=True, nullable=False)
    worker_id = Column(String(100), nullable=False)
    worker_region = Column(String(50), nullable=False)
    runtime = Column(String(50), nullable=False, default="unknown")
    api_id = Column(UUID(as_uuid=True), ForeignKey("vnp_apis.id", ondelete="CASCADE"), nullable=False)
    api_region_code = Column(String(50), nullable=False)
    endpoint_url = Column(String, nullable=False, default="")
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    dns_ms = Column(Integer)
    connect_ms = Column(Integer)
    tls_ms = Column(Integer)
    ttfb_ms = Column(Integer)
    total_ms = Column(Integer, nullable=False)
    status_code = Column(Integer)
    result_state = Column(Enum(ProbeResultState, name="probe_result_state_enum", create_type=False), nullable=False)
    success = Column(Boolean, nullable=False)
    timeout = Column(Boolean, nullable=False)
    error_class = Column(String(100))
    signature_alg = Column(String(20), nullable=False, default="ed25519")
    signature_key_id = Column(String(100), nullable=False, default="unknown")
    signature_value = Column(String, nullable=False, default="")
    received_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_probe_events_api_region_time", "api_id", "api_region_code", "occurred_at"),
    )


class RegionalTelemetry(Base):
    __tablename__ = "vnp_regional_telemetry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(UUID(as_uuid=True), ForeignKey("vnp_apis.id", ondelete="CASCADE"), nullable=False)
    region_code = Column(String(50), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    sample_count = Column(Integer, nullable=False)
    success_count = Column(Integer, nullable=False)
    p50_latency_ms = Column(Integer, nullable=False)
    p95_latency_ms = Column(Integer, nullable=False)
    p99_latency_ms = Column(Integer, nullable=False)
    error_rate_percent = Column(Numeric(5, 2), nullable=False)
    uptime_percent = Column(Numeric(5, 2), nullable=False)
    throughput_rps = Column(Integer, nullable=False, default=0)
    trust_score = Column(Numeric(5, 2), nullable=False)
    provenance_hash = Column(String)
    on_chain_anchor = Column(String)
    measured_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_regional_telemetry_region_score", "region_code", "trust_score", "p99_latency_ms"),
    )


class RouteSnapshot(Base):
    __tablename__ = "vnp_route_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(UUID(as_uuid=True)) # Flattened per user request
    region = Column(String(50))
    score = Column(Float)
    p99_latency = Column(Float)
    uptime_pct = Column(Float)
    recommended = Column(Boolean, default=False)
    snapshot_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Keeping legacy fields for backward compatibility during transition
    customer_id = Column(UUID(as_uuid=True), ForeignKey("vnp_customers.id", ondelete="SET NULL"))
    policy_id = Column(UUID(as_uuid=True), ForeignKey("vnp_route_policies.id", ondelete="SET NULL"))
    snapshot = Column(JSONB)

    __table_args__ = (
        Index("idx_route_snapshots_at", "snapshot_at"),
    )


class UsageEvent(Base):
    __tablename__ = "vnp_usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(100), unique=True, nullable=False)
    partition_key = Column(String(20), nullable=False, index=True) # YYYY-MM
    customer_id = Column(UUID(as_uuid=True), ForeignKey("vnp_customers.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("vnp_projects.id", ondelete="CASCADE"), nullable=False)
    credential_id = Column(UUID(as_uuid=True), ForeignKey("vnp_sdk_credentials.id", ondelete="CASCADE"), nullable=False)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("vnp_route_policies.id", ondelete="SET NULL"))
    request_id = Column(String(100), nullable=False)
    api_id = Column(UUID(as_uuid=True), ForeignKey("vnp_apis.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("vnp_providers.id", ondelete="CASCADE"), nullable=False)
    provider_region = Column(String(50), nullable=False)
    sdk_region = Column(String(50))
    route_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("vnp_route_snapshots.id", ondelete="SET NULL"))
    billable_units = Column(BigInteger, nullable=False)
    unit_type = Column(String(50), nullable=False)
    success = Column(Boolean, nullable=False)
    response_ms = Column(Integer)
    http_status = Column(Integer)
    retry_count = Column(Integer, nullable=False, default=0)
    failover_count = Column(Integer, nullable=False, default=0)
    preauth_amount_minor = Column(BigInteger)
    final_amount_minor = Column(BigInteger)
    currency = Column(String(3), nullable=False, default="USD")
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    signature_alg = Column(String(20), nullable=False)
    signature_key_id = Column(String(100), nullable=False)
    signature_value = Column(String, nullable=False)
    received_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_usage_events_customer_time", "customer_id", "occurred_at"),
        Index("idx_usage_events_project_time", "project_id", "occurred_at"),
    )


class PrepaidBalance(Base):
    __tablename__ = "vnp_prepaid_balances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("vnp_customers.id", ondelete="CASCADE"), nullable=False)
    currency = Column(String(3), nullable=False)
    available_amount_minor = Column(BigInteger, nullable=False, default=0)
    reserved_amount_minor = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("customer_id", "currency", name="uq_vnp_prepaid_balances_cust_cur"),
    )


class SettlementEntry(Base):
    __tablename__ = "vnp_settlement_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("vnp_customers.id", ondelete="SET NULL"))
    provider_id = Column(UUID(as_uuid=True), ForeignKey("vnp_providers.id", ondelete="SET NULL"))
    usage_event_id = Column(UUID(as_uuid=True), ForeignKey("vnp_usage_events.id", ondelete="SET NULL"))
    entry_type = Column(Enum(LedgerEntryType, name="ledger_entry_type_enum", create_type=False), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    state = Column(Enum(SettlementState, name="settlement_state_enum", create_type=False), nullable=False, default=SettlementState.posted)
    reference_code = Column(String(100))
    entry_metadata = Column("metadata", JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_settlement_entries_customer_time", "customer_id", "created_at"),
    )


class Validator(Base):
    __tablename__ = "vnp_validators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    public_key = Column(String, nullable=False)
    stake_amount = Column(Numeric, default=0)
    status = Column(String, default='active')
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    @property
    def is_active(self) -> bool:
        return self.status == 'active'

    # Keeping legacy fields for now
    display_name = Column(String(255))
    operator_entity = Column(String(255))
    stake_currency = Column(String(3), default="USD")
    stake_amount_minor = Column(BigInteger)
    state = Column(Enum(ValidatorState, name="validator_state_enum", create_type=False), default=ValidatorState.active)


class Attestation(Base):
    __tablename__ = "vnp_attestations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    validator_id = Column(UUID(as_uuid=True), ForeignKey("vnp_validators.id", ondelete="CASCADE"), nullable=False)
    api_id = Column(UUID(as_uuid=True))
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    verdict = Column(String)
    signature = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Legacy fields
    incident_id = Column(UUID(as_uuid=True))
    state = Column(Enum(AttestationState, name="attestation_state_enum", create_type=False))
    payload = Column(JSONB)
    signature_value = Column(String)


class Incident(Base):
    __tablename__ = "vnp_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope_type = Column(String(50), nullable=False)
    scope_id = Column(UUID(as_uuid=True))
    title = Column(String(255), nullable=False)
    description = Column(String)
    state = Column(Enum(IncidentState, name="incident_state_enum", create_type=False), nullable=False, default=IncidentState.open)
    severity = Column(String(20), nullable=False)
    opened_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_incidents_state_opened", "state", "opened_at"),
    )


class AuditLog(Base):
    __tablename__ = "vnp_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_type = Column(Enum(TenantType, name="tenant_type_enum", create_type=False), nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    action = Column(String(100), nullable=False)
    scope_type = Column(String(50), nullable=False)
    scope_id = Column(UUID(as_uuid=True))
    log_metadata = Column("metadata", JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_audit_logs_scope_time", "scope_type", "scope_id", "created_at"),
    )

class AlertConfig(Base):
    __tablename__ = "vnp_alert_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_api = Column(String(100), nullable=False) # 'all' or API DID
    metric_type = Column(String(50), nullable=False)
    condition = Column(String(20), nullable=False) # '>', '<', etc.
    threshold_value = Column(Float, nullable=False)
    region = Column(String(50), nullable=False)
    actions = Column(JSONB, nullable=False, default=[])
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ClaimRequest(Base):
    __tablename__ = "vnp_claim_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(String(200), nullable=False, index=True)
    api_domain = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    company_email = Column(String(255), nullable=False)
    dns_record = Column(String(255), nullable=False)
    dns_value = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, verified, failed
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    verified_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), nullable=False)


class ClaimedAPI(Base):
    __tablename__ = "vnp_claimed_apis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_id = Column(String(200), nullable=False, unique=True, index=True)
    company_name = Column(String(255), nullable=False)
    company_email = Column(String(255), nullable=False)
    claim_verified_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    score_low_alert = Column(Boolean, nullable=False, default=True)
    score_low_threshold = Column(Integer, nullable=False, default=80)
    last_score_alert_sent = Column(DateTime(timezone=True))



class Node(Base):
    __tablename__ = "vnp_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    host_reference = Column(String(255))
    physical_location = Column(String(255), nullable=False)
    region_code = Column(String(50), nullable=False, unique=True)
    macro_region = Column(String(50), nullable=False)
    city = Column(String(100))
    country = Column(String(100))
    jurisdiction = Column(String(100), nullable=False)
    infrastructure_provider = Column(String(100), nullable=False, default="Hetzner")
    deployment_platform = Column(String(100), nullable=False, default="Coolify")
    coolify_application_ref = Column(String(255))
    container_image_digest = Column(String(255))
    gdpr_zone = Column(Boolean, nullable=False, default=False)
    software_version = Column(String(50))
    signing_key_id = Column(String(100))
    key_status = Column(String(50), nullable=False, default="configuration_incomplete")
    last_seen_at = Column(DateTime(timezone=True))
    health_state = Column(String(50), nullable=False, default="unknown")
    registration_status = Column(String(50), nullable=False, default="registered")
    revocation_state = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

class NodeKey(Base):
    __tablename__ = "vnp_node_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("vnp_nodes.id", ondelete="CASCADE"), nullable=False)
    key_id = Column(String(100), unique=True, nullable=False)
    public_key = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    node = relationship("Node", backref="keys")

class NodeHeartbeat(Base):
    __tablename__ = "vnp_node_heartbeats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("vnp_nodes.id", ondelete="CASCADE"), nullable=False)
    heartbeat_id = Column(String(100), nullable=False, unique=True)
    sequence = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    software_version = Column(String(50), nullable=False)
    signature_key_id = Column(String(100), nullable=False)
    signature = Column(String, nullable=False)
    payload_digest = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

class Observation(Base):
    __tablename__ = "vnp_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id = Column(String(100), unique=True, nullable=False)
    node_id = Column(UUID(as_uuid=True), ForeignKey("vnp_nodes.id"), nullable=False)
    region = Column(String(50), nullable=False)
    physical_location = Column(String(255), nullable=False)
    target_id = Column(String(200), nullable=False)
    measurement_profile = Column(String(100), nullable=False)
    measurement_version = Column(String(50), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    dns_ms = Column(Integer)
    tcp_ms = Column(Integer)
    tls_ms = Column(Integer)
    ttfb_ms = Column(Integer)
    total_ms = Column(Integer)
    http_status = Column(Integer)
    response_fingerprint = Column(String)
    error_code = Column(String)
    sequence = Column(Integer, nullable=False)
    previous_observation_hash = Column(String)
    signature_key_id = Column(String(100), nullable=False)
    signature = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_observations_target_region_time", "target_id", "region", "started_at"),
    )

class MeasurementWindow(Base):
    __tablename__ = "vnp_measurement_windows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(String(200), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    node_count = Column(Integer, nullable=False)
    physical_location_count = Column(Integer, nullable=False)
    macro_region_count = Column(Integer, nullable=False)
    sample_count = Column(Integer, nullable=False)
    freshness = Column(Integer)
    missing_regions = Column(JSONB, default=[])
    provisional_flag = Column(Boolean, nullable=False, default=True)
    confidence_band = Column(String(50))
    formula_version = Column(String(50), nullable=False)
    evidence_root = Column(String)
    pgl_evidence_id = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_measure_win_target_start", "target_id", "window_start"),
    )

class Score(Base):
    __tablename__ = "vnp_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(String(200), nullable=False)
    measurement_window_id = Column(UUID(as_uuid=True), ForeignKey("vnp_measurement_windows.id"), nullable=False)
    operational_score = Column(Float, nullable=False)
    latency_score = Column(Float, nullable=False)
    availability_score = Column(Float, nullable=False)
    reliability_score = Column(Float, nullable=False)
    score_version = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_vnp_scores_target_time", "target_id", "created_at"),
    )

class VabpRunState(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class VabpRun(Base):
    __tablename__ = "vnp_vabp_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(String(200), nullable=False)
    run_state = Column(Enum(VabpRunState, name="vabp_run_state_enum", create_type=False), nullable=False, default=VabpRunState.pending)
    total_score = Column(Integer)
    suite_version = Column(String(50), nullable=False)
    started_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True))
    error_reason = Column(String)

class VabpTestResult(Base):
    __tablename__ = "vnp_vabp_test_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("vnp_vabp_runs.id", ondelete="CASCADE"), nullable=False)
    test_name = Column(String(200), nullable=False)
    dimension = Column(String(50), nullable=False)
    passed = Column(Boolean, nullable=False)
    score_awarded = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)
    evidence_hash = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

class TrustCertificate(Base):
    __tablename__ = "vnp_trust_certificates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = Column(String(200), nullable=False)
    vabp_run_id = Column(UUID(as_uuid=True), ForeignKey("vnp_vabp_runs.id"), nullable=False)
    score = Column(Integer, nullable=False)
    passed_threshold = Column(Boolean, nullable=False)
    issued_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    pgl_evidence_id = Column(String)
    revoked = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index("idx_trust_certs_target", "target_id", "issued_at"),
    )

class BondState(str, enum.Enum):
    draft = "draft"
    funded = "funded"
    active = "active"
    breach_pending = "breach_pending"
    slashed = "slashed"
    released = "released"

class ChallengeState(str, enum.Enum):
    pending = "pending"
    verifying = "verifying"
    upheld = "upheld"
    rejected = "rejected"

class ProviderBond(Base):
    __tablename__ = "vnp_provider_bonds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("vnp_providers.id", ondelete="CASCADE"), nullable=False)
    target_api_id = Column(String(200), nullable=False)
    state = Column(Enum(BondState, name="bond_state_enum", create_type=False), nullable=False, default=BondState.draft)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    funded_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index("idx_provider_bonds_target_state", "target_api_id", "state"),
    )

class BondCondition(Base):
    __tablename__ = "vnp_bond_conditions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bond_id = Column(UUID(as_uuid=True), ForeignKey("vnp_provider_bonds.id", ondelete="CASCADE"), nullable=False)
    metric_type = Column(String(50), nullable=False) # e.g., 'p99_latency_ms', 'vabp_score'
    operator = Column(String(10), nullable=False)    # e.g., '<=', '>='
    threshold_value = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

class BondChallenge(Base):
    __tablename__ = "vnp_challenges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bond_id = Column(UUID(as_uuid=True), ForeignKey("vnp_provider_bonds.id", ondelete="CASCADE"), nullable=False)
    challenger_id = Column(String(100), nullable=False)
    state = Column(Enum(ChallengeState, name="challenge_state_enum", create_type=False), nullable=False, default=ChallengeState.pending)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    resolved_at = Column(DateTime(timezone=True))

class ChallengeEvidence(Base):
    __tablename__ = "vnp_challenge_evidence"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("vnp_challenges.id", ondelete="CASCADE"), nullable=False)
    measurement_window_id = Column(UUID(as_uuid=True), ForeignKey("vnp_measurement_windows.id"), nullable=True)
    vabp_run_id = Column(UUID(as_uuid=True), ForeignKey("vnp_vabp_runs.id"), nullable=True)
    evidence_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

class BondResolution(Base):
    __tablename__ = "vnp_resolutions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("vnp_challenges.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False) # 'slash', 'release', 'dismiss'
    amount_minor = Column(BigInteger, nullable=False)
    pgl_receipt_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
