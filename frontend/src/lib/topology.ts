export const TOPOLOGY_ENDPOINT = "/api/v1/beacon/topology";

export const CANONICAL_SITE_CODES = [
  "us-ashburn",
  "us-hillsboro",
  "de-nuremberg",
  "de-falkenstein",
  "sg-singapore",
] as const;

export type CanonicalSiteCode = (typeof CANONICAL_SITE_CODES)[number];

export interface TopologyNode {
  id: string;
  name: string;
  region: CanonicalSiteCode;
  physicalLocation?: string;
  status?: string;
  status_str?: string;
  registrationStatus?: string;
  activeKeyCount?: number;
  heartbeatFreshnessSeconds?: number;
  lastHeartbeat?: string;
  observationCount?: number;
  lastObservation?: string;
}

export interface TopologySnapshot {
  nodes: TopologyNode[];
  expectedNodes?: number;
  registeredNodes?: number;
  activeNodes?: number;
}

interface TopologyResponse {
  topology?: {
    nodes?: unknown;
    expectedNodes?: unknown;
    registeredNodes?: unknown;
    activeNodes?: unknown;
  };
}

function isCanonicalSiteCode(value: unknown): value is CanonicalSiteCode {
  return typeof value === "string" && CANONICAL_SITE_CODES.includes(value as CanonicalSiteCode);
}

function asOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function parseNode(value: unknown): TopologyNode | null {
  if (!value || typeof value !== "object") return null;
  const node = value as Record<string, unknown>;
  if (typeof node.id !== "string" || typeof node.name !== "string" || !isCanonicalSiteCode(node.region)) {
    return null;
  }

  return {
    id: node.id,
    name: node.name,
    region: node.region,
    physicalLocation: asOptionalString(node.physicalLocation),
    status: asOptionalString(node.status),
    status_str: asOptionalString(node.status_str),
    registrationStatus: asOptionalString(node.registrationStatus),
    activeKeyCount: asOptionalNumber(node.activeKeyCount),
    heartbeatFreshnessSeconds: asOptionalNumber(node.heartbeatFreshnessSeconds),
    lastHeartbeat: asOptionalString(node.lastHeartbeat),
    observationCount: asOptionalNumber(node.observationCount),
    lastObservation: asOptionalString(node.lastObservation),
  };
}

export function parseTopologyResponse(response: unknown): TopologySnapshot {
  const payload = response as TopologyResponse;
  const topology = payload?.topology;
  const nodes = Array.isArray(topology?.nodes)
    ? topology.nodes.map(parseNode).filter((node): node is TopologyNode => node !== null)
    : [];

  return {
    nodes,
    expectedNodes: asOptionalNumber(topology?.expectedNodes),
    registeredNodes: asOptionalNumber(topology?.registeredNodes),
    activeNodes: asOptionalNumber(topology?.activeNodes),
  };
}

export async function fetchTopology(url: string = TOPOLOGY_ENDPOINT): Promise<TopologySnapshot> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Topology request failed (${response.status})`);
  }
  return parseTopologyResponse(await response.json());
}
