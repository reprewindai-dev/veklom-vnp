"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Activity, CheckCircle2, Clock3, Database, MapPin, Radio, Server } from "lucide-react";
import {
  fetchTopology,
  TOPOLOGY_ENDPOINT,
  type TopologyNode,
  type TopologySnapshot,
} from "../lib/topology";

function formatCount(value: number | undefined): string {
  return value === undefined ? "Needs proof" : value.toLocaleString();
}

function formatAge(seconds: number | undefined): string {
  if (seconds === undefined) return "Needs proof";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function formatTimestamp(value: string | undefined): string {
  if (!value) return "Needs proof";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

function evidenceState(value: string | undefined): "Present" | "Needs proof" {
  return value ? "Present" : "Needs proof";
}

function StatusPill({ value }: { value: string | undefined }) {
  const label = value || "Needs proof";
  const tone = value?.toUpperCase() === "LIVE"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : value?.toUpperCase() === "STANDBY"
      ? "border-slate-600 bg-slate-500/10 text-slate-300"
      : "border-amber-500/30 bg-amber-500/10 text-amber-300";

  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${tone}`}>
      {label}
    </span>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/[0.06] py-2.5 last:border-0">
      <span className="text-[10px] uppercase tracking-[0.16em] text-gray-500">{label}</span>
      <span className="text-right text-xs text-gray-200">{value}</span>
    </div>
  );
}

function NodeCard({ node, selected, onSelect }: { node: TopologyNode; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`card w-full text-left transition-colors ${selected ? "border-[#FFB800]/50" : "hover:border-white/20"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="mt-0.5 rounded-lg border border-cyan-400/20 bg-cyan-400/10 p-2">
            <Server className="h-4 w-4 text-cyan-300" />
          </div>
          <div className="min-w-0">
            <div className="truncate font-sans text-sm font-semibold text-white">{node.name}</div>
            <div className="mt-1 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-gray-500">
              <MapPin className="h-3 w-3 text-cyan-300" />
              {node.region}
            </div>
          </div>
        </div>
        <StatusPill value={node.status_str || node.status} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-gray-500">Heartbeat</div>
          <div className="mt-1 font-mono text-xs text-gray-200">{formatAge(node.heartbeatFreshnessSeconds)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-gray-500">Observations</div>
          <div className="mt-1 font-mono text-xs text-gray-200">{formatCount(node.observationCount)}</div>
        </div>
      </div>
    </button>
  );
}

export default function NetworkTopologyPanel() {
  const { data, error, isLoading } = useSWR<TopologySnapshot>(TOPOLOGY_ENDPOINT, fetchTopology, {
    refreshInterval: 5000,
    revalidateOnFocus: true,
  });
  const [selectedNodeId, setSelectedNodeId] = useState<string>();

  useEffect(() => {
    if (!selectedNodeId && data?.nodes[0]) setSelectedNodeId(data.nodes[0].id);
    if (selectedNodeId && data?.nodes.every((node) => node.id !== selectedNodeId)) {
      setSelectedNodeId(data.nodes[0]?.id);
    }
  }, [data, selectedNodeId]);

  const selectedNode = data?.nodes.find((node) => node.id === selectedNodeId) || data?.nodes[0];

  return (
    <section className="space-y-5 text-sm">
      <div className="flex flex-col gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300">
            <Radio className="h-3.5 w-3.5" />
            Canonical topology feed
          </div>
          <p className="mt-2 max-w-xl text-xs leading-relaxed text-gray-500">
            Registry observations from the five canonical Hetzner sites. State, freshness, and counts below are rendered exactly from the response.
          </p>
        </div>
        <div className="rounded-lg border border-white/[0.08] bg-black/20 px-3 py-2 font-mono text-[10px] text-gray-500">
          GET {TOPOLOGY_ENDPOINT}
        </div>
      </div>

      {error ? (
        <div className="card border-amber-500/30 text-sm text-amber-200">
          Topology evidence unavailable. <span className="text-amber-300/70">Needs proof</span>
        </div>
      ) : isLoading || !data ? (
        <div className="card flex min-h-52 items-center justify-center text-xs font-mono uppercase tracking-[0.16em] text-gray-500">
          Reading registry evidence…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ["Expected sites", formatCount(data.expectedNodes)],
              ["Registered", formatCount(data.registeredNodes)],
              ["Active", formatCount(data.activeNodes)],
              ["Nodes returned", data.nodes.length.toLocaleString()],
            ].map(([label, value]) => (
              <div key={label} className="card p-4">
                <div className="text-[10px] uppercase tracking-[0.15em] text-gray-500">{label}</div>
                <div className="mt-2 font-mono text-xl text-white">{value}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-3">
              {data.nodes.map((node) => (
                <NodeCard
                  key={node.id}
                  node={node}
                  selected={node.id === selectedNode?.id}
                  onSelect={() => setSelectedNodeId(node.id)}
                />
              ))}
              {data.nodes.length === 0 && (
                <div className="card text-sm text-gray-400">
                  No canonical nodes returned. <span className="text-amber-300">Needs proof</span>
                </div>
              )}
            </div>

            {selectedNode ? (
              <div className="card h-fit p-5">
                <div className="flex items-start justify-between gap-3 border-b border-white/[0.08] pb-4">
                  <div>
                    <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.17em] text-gray-500">
                      <Activity className="h-3.5 w-3.5 text-[#FFB800]" />
                      Node evidence
                    </div>
                    <h3 className="mt-2 text-lg font-semibold text-white">{selectedNode.name}</h3>
                    <p className="mt-1 font-mono text-[10px] text-gray-500">{selectedNode.id}</p>
                  </div>
                  <StatusPill value={selectedNode.status_str || selectedNode.status} />
                </div>
                <div className="mt-3">
                  <EvidenceRow label="Operational status" value={selectedNode.status || "Needs proof"} />
                  <EvidenceRow label="Status reason" value={selectedNode.status_str || "Needs proof"} />
                  <EvidenceRow label="Site / region" value={selectedNode.region} />
                  <EvidenceRow label="Physical location" value={selectedNode.physicalLocation || "Needs proof"} />
                  <EvidenceRow label="Registration" value={selectedNode.registrationStatus || "Needs proof"} />
                  <EvidenceRow label="Active keys" value={selectedNode.activeKeyCount === undefined ? "Needs proof" : `${selectedNode.activeKeyCount}`} />
                  <EvidenceRow label="Heartbeat freshness" value={formatAge(selectedNode.heartbeatFreshnessSeconds)} />
                  <EvidenceRow label="Accepted observations" value={formatCount(selectedNode.observationCount)} />
                  <EvidenceRow label="Last heartbeat" value={formatTimestamp(selectedNode.lastHeartbeat)} />
                  <EvidenceRow label="Last observation" value={formatTimestamp(selectedNode.lastObservation)} />
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3 border-t border-white/[0.08] pt-4">
                  <div className="rounded-lg border border-white/[0.07] bg-black/20 p-3">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-gray-500">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
                      Registration evidence
                    </div>
                    <div className="mt-2 font-mono text-xs text-gray-200">{evidenceState(selectedNode.registrationStatus)}</div>
                  </div>
                  <div className="rounded-lg border border-white/[0.07] bg-black/20 p-3">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-gray-500">
                      <Clock3 className="h-3.5 w-3.5 text-cyan-300" />
                      Freshness evidence
                    </div>
                    <div className="mt-2 font-mono text-xs text-gray-200">
                      {selectedNode.heartbeatFreshnessSeconds === undefined ? "Needs proof" : "Present"}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="card flex min-h-52 items-center justify-center text-xs text-gray-500">Select a canonical node.</div>
            )}
          </div>
        </>
      )}
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-gray-600">
        <Database className="h-3.5 w-3.5" />
        Evidence source: nested `topology` response · no scores or settlement data rendered
      </div>
    </section>
  );
}
