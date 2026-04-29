"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AgentRunSummary,
  Approval,
  AuditEvent,
  Engagement,
  ExecutionEvent,
  Finding,
  FindingSeverity,
  Inventory,
  decideApproval,
  getInventory,
  listAgentRuns,
  listApprovals,
  listAuditEvents,
  listEngagements,
  listFindings,
  updateEngagementStatus,
} from "@/lib/api";
import { ToolLaunchDrawer } from "./tool-launch-drawer";

const LiveTerminal = dynamic(
  () => import("./live-terminal").then((mod) => mod.LiveTerminal),
  { ssr: false },
);

const SEVERITY_COLOR: Record<FindingSeverity, string> = {
  critical: "#FF3366",
  high: "#FF8C42",
  medium: "#FFB800",
  low: "#4F8EF7",
  info: "#5C6378",
};

const SEV_BADGE: Record<FindingSeverity, string> = {
  critical: "bg-severity-critical text-white",
  high: "bg-severity-high text-white",
  medium: "bg-severity-medium text-white",
  low: "bg-severity-low text-white",
  info: "bg-severity-info text-white",
};

function shortId(id: string): string {
  return id.split("-")[0]?.toUpperCase() ?? id.slice(0, 6).toUpperCase();
}

function timeOnly(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour12: false });
}

function relativeAge(iso: string, now: number): string {
  const ms = now - new Date(iso).getTime();
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function elapsedFrom(iso: string, now: number): string {
  const ms = Math.max(0, now - new Date(iso).getTime());
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function LiveEngagementView() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [inventory, setInventory] = useState<Inventory>({ hosts: [], services: [] });
  const [agentRuns, setAgentRuns] = useState<AgentRunSummary[]>([]);
  const [executionEvents, setExecutionEvents] = useState<ExecutionEvent[]>([]);
  const [executionActive, setExecutionActive] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [now, setNow] = useState<number>(Date.now());
  const [error, setError] = useState<string | null>(null);
  const [busyApproval, setBusyApproval] = useState<string | null>(null);
  const [terminating, setTerminating] = useState(false);
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    listEngagements()
      .then((rows) => {
        setEngagements(rows);
        if (rows.length > 0) setSelectedId((prev) => prev || rows[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const refreshDetails = useCallback(async (engagementId: string) => {
    try {
      const [f, a, e, inv, runs] = await Promise.all([
        listFindings(engagementId),
        listApprovals(engagementId),
        listAuditEvents(engagementId),
        getInventory(engagementId),
        listAgentRuns(engagementId),
      ]);
      setFindings(f);
      setApprovals(a);
      setAudit(e);
      setInventory(inv);
      setAgentRuns(runs);
      setError(null);
    } catch (err) {
      setError(String(err));
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    refreshDetails(selectedId);
    if (refreshTimer.current) clearInterval(refreshTimer.current);
    refreshTimer.current = setInterval(() => refreshDetails(selectedId), 5000);
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, [selectedId, refreshDetails]);

  const selected = engagements.find((e) => e.id === selectedId);

  const sortedFindings = useMemo(
    () =>
      [...findings].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      ),
    [findings],
  );

  const pendingApprovals = useMemo(
    () => approvals.filter((a) => a.decided_at === null),
    [approvals],
  );

  const recentAudit = useMemo(() => audit.slice(0, 12), [audit]);

  const handleDecide = useCallback(
    async (approvalId: string, approved: boolean) => {
      if (!selectedId) return;
      setBusyApproval(approvalId);
      try {
        await decideApproval(approvalId, {
          approved,
          decision_reason: approved ? "operator-approved" : "operator-aborted",
          approved_by: selected?.operator_name ?? "operator",
        });
        await refreshDetails(selectedId);
      } catch (err) {
        setError(String(err));
      } finally {
        setBusyApproval(null);
      }
    },
    [selectedId, selected, refreshDetails],
  );

  const handleTerminate = useCallback(async () => {
    if (!selectedId || !selected || selected.status !== "active") return;
    setTerminating(true);
    try {
      await updateEngagementStatus(selectedId, "aborted");
      await refreshDetails(selectedId);
      setEngagements((prev) =>
        prev.map((e) => (e.id === selectedId ? { ...e, status: "aborted" } : e)),
      );
    } catch (err) {
      setError(String(err));
    } finally {
      setTerminating(false);
    }
  }, [selectedId, selected, refreshDetails]);

  const progressPct = useMemo(() => {
    if (!selected) return 0;
    const phaseMap: Record<string, number> = {
      draft: 0,
      active: 20,
      reconnaissance: 35,
      enumeration: 55,
      vulnerability_scan: 70,
      exploitation: 85,
      reporting: 95,
      archived: 100,
      aborted: 100,
      paused: 50,
    };
    const latestPhase = agentRuns[0]?.current_phase ?? selected.status;
    return phaseMap[latestPhase] ?? 20;
  }, [selected, agentRuns]);

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] -mx-gutter -my-gutter bg-bg-primary text-text-primary overflow-hidden">
      <EngagementHeader
        engagements={engagements}
        selectedId={selectedId}
        onSelect={setSelectedId}
        selected={selected}
        agentRuns={agentRuns}
        progressPct={progressPct}
        now={now}
        error={error}
        onTerminate={handleTerminate}
        terminating={terminating}
      />

      {/* 12-col grid: attack graph + right column, with terminal at bottom */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left column: attack graph + terminal */}
        <div className="flex flex-col" style={{ flex: "0 0 66.666%" }}>
          <GraphPanel inventory={inventory} selected={selected} />
          <TerminalPanel
            executionEvents={executionEvents}
            executionActive={executionActive}
            onLaunchClick={() => setDrawerOpen(true)}
            launchDisabled={!selectedId}
          />
        </div>

        {/* Right column: findings + approvals */}
        <div className="flex flex-col border-l border-border-subtle" style={{ flex: "0 0 33.333%" }}>
          <FindingsPanel findings={sortedFindings} />
          <ApprovalsPanel
            approvals={pendingApprovals}
            busyApproval={busyApproval}
            onDecide={handleDecide}
          />
        </div>
      </div>

      <AuditMarquee events={recentAudit} now={now} />

      <ToolLaunchDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        engagementId={selectedId}
        onExecutionStart={() => {
          setExecutionEvents([]);
          setExecutionActive(true);
        }}
        onExecutionEvent={(ev) => setExecutionEvents((cur) => [...cur, ev])}
        onExecutionEnd={() => {
          setExecutionActive(false);
          if (selectedId) refreshDetails(selectedId);
        }}
      />
    </div>
  );
}

/* ─── Engagement Header ──────────────────────────────────────────────────── */

type EngagementHeaderProps = {
  engagements: Engagement[];
  selectedId: string;
  onSelect: (id: string) => void;
  selected: Engagement | undefined;
  agentRuns: AgentRunSummary[];
  progressPct: number;
  now: number;
  error: string | null;
  onTerminate: () => void;
  terminating: boolean;
};

function EngagementHeader({
  engagements,
  selectedId,
  onSelect,
  selected,
  agentRuns,
  progressPct,
  now,
  error,
  onTerminate,
  terminating,
}: EngagementHeaderProps) {
  const latestRun = agentRuns[0];
  const elapsed = selected ? elapsedFrom(selected.created_at, now) : "00:00:00";
  const isActive = selected?.status === "active";
  const scope = selected?.scope_cidrs.join(", ") ?? "—";

  return (
    <div className="border-b border-border-subtle bg-surface-secondary flex items-center justify-between px-4 py-2.5 shrink-0">
      <div className="flex items-center gap-5">
        {/* Engagement selector */}
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-[9px] text-text-tertiary uppercase tracking-widest">
            Engagement
          </span>
          <select
            value={selectedId}
            onChange={(e) => onSelect(e.target.value)}
            className="bg-surface-tertiary border border-border-subtle px-2 py-0.5 font-mono text-[11px] text-text-primary focus:outline-none focus:border-primary"
          >
            {engagements.length === 0 && (
              <option value="">— No engagements —</option>
            )}
            {engagements.map((e) => (
              <option key={e.id} value={e.id}>
                #{shortId(e.id)} · {e.name}
              </option>
            ))}
          </select>
        </div>

        <div className="h-7 w-px bg-border-subtle" />

        {/* Target / scope */}
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-[9px] text-text-tertiary uppercase tracking-widest flex items-center gap-1">
            <span className="material-symbols-outlined text-[11px]">location_on</span>
            Target Scope
          </span>
          <span className="font-mono text-[11px] text-text-secondary uppercase">{scope}</span>
        </div>

        {/* Progress */}
        {selected && (
          <>
            <div className="h-7 w-px bg-border-subtle" />
            <div className="flex flex-col gap-1 w-52">
              <div className="flex justify-between text-[9px] font-mono uppercase tracking-wider text-text-secondary">
                <span>{latestRun?.current_phase ?? selected.status}</span>
                <span className="text-primary">{progressPct}%</span>
              </div>
              <div className="h-1.5 w-full bg-surface-container border border-border-subtle">
                <div
                  className="h-full bg-primary transition-all duration-700"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          </>
        )}

        {/* Agent runs badge */}
        {agentRuns.length > 0 && (
          <a
            href="/engagements/agent"
            className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-primary/40 text-primary hover:bg-primary/10"
          >
            AGENT: {agentRuns.length}× {latestRun?.current_phase ?? "—"}
          </a>
        )}
      </div>

      <div className="flex items-center gap-4">
        {error && (
          <span className="font-mono text-[10px] text-severity-critical truncate max-w-[200px]">
            ERR: {error.slice(0, 50)}
          </span>
        )}

        {/* Elapsed timer */}
        <div className="flex flex-col items-end">
          <span className="text-[9px] text-text-tertiary uppercase font-mono tracking-wider">
            Elapsed
          </span>
          <span className="font-mono text-text-primary text-sm tabular-nums">{elapsed}</span>
        </div>

        {/* Terminate */}
        <button
          type="button"
          disabled={!isActive || terminating}
          onClick={onTerminate}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-error text-on-error text-[11px] font-bold uppercase tracking-wider hover:brightness-110 disabled:opacity-30 transition"
        >
          <span className="material-symbols-outlined text-sm">stop</span>
          {terminating ? "Stopping…" : "Terminate"}
        </button>
      </div>
    </div>
  );
}

/* ─── Graph Panel ────────────────────────────────────────────────────────── */

type GraphPanelProps = {
  inventory: Inventory;
  selected: Engagement | undefined;
};

function GraphPanel({ inventory, selected }: GraphPanelProps) {
  return (
    <div
      className="flex-1 relative overflow-hidden"
      style={{
        backgroundImage:
          "linear-gradient(to right, #1a1d26 1px, transparent 1px), linear-gradient(to bottom, #1a1d26 1px, transparent 1px)",
        backgroundSize: "20px 20px",
        backgroundColor: "#0A0B0F",
      }}
    >
      <div className="absolute top-3 left-3 z-10">
        <span className="px-2 py-1 bg-surface-tertiary border border-border-accent text-[10px] font-mono text-primary uppercase tracking-widest font-bold">
          Network_Topology_Live
        </span>
      </div>

      <AttackGraph inventory={inventory} />

      {/* Telemetry matrix */}
      <div className="absolute bottom-3 right-3 p-3 bg-surface-secondary/95 border border-border-accent w-44">
        <h4 className="text-[9px] font-bold uppercase tracking-widest text-text-tertiary mb-2 border-b border-border-accent pb-1">
          Telemetry_Matrix
        </h4>
        <TelemetryRow label="NODES" value={inventory.hosts.length} />
        <TelemetryRow label="SERVICES" value={inventory.services.length} />
        <TelemetryRow
          label="SESSION"
          value={selected ? `#${shortId(selected.id)}` : "—"}
          mono
        />
      </div>

      {/* Graph controls */}
      <div className="absolute bottom-3 left-3 flex gap-1">
        {["add", "remove", "refresh"].map((icon) => (
          <button
            key={icon}
            type="button"
            aria-label={icon}
            className="w-7 h-7 bg-surface-tertiary border border-border-accent flex items-center justify-center hover:bg-border-accent transition"
          >
            <span className="material-symbols-outlined text-sm">{icon}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function TelemetryRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: number | string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-[11px] text-text-secondary font-mono">{label}</span>
      <span className={`text-[11px] font-mono ${mono ? "text-secondary" : "text-text-primary"}`}>
        {value}
      </span>
    </div>
  );
}

function AttackGraph({ inventory }: { inventory: Inventory }) {
  const hosts = inventory.hosts.slice(0, 8);
  if (hosts.length === 0) {
    return (
      <div className="absolute inset-0 flex items-center justify-center font-mono text-[11px] text-text-tertiary uppercase tracking-widest">
        No hosts discovered · launch a scan to begin
      </div>
    );
  }
  const cx = 400;
  const cy = 230;
  const r = 170;
  const angle = (i: number) => (2 * Math.PI * i) / hosts.length - Math.PI / 2;
  return (
    <svg
      className="absolute inset-0 w-full h-full"
      viewBox="0 0 800 460"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Center origin node */}
      <rect x={cx - 18} y={cy - 18} width={36} height={36} fill="#141620" stroke="#4F8EF7" strokeWidth={2} />
      <text x={cx} y={cy + 38} fill="#4F8EF7" fontFamily="JetBrains Mono" fontSize={10} fontWeight="bold" textAnchor="middle">
        ENTRY-01
      </text>

      {hosts.map((h, i) => {
        const x = cx + r * Math.cos(angle(i));
        const y = cy + r * Math.sin(angle(i));
        const isCompromised = i % 3 === 0;
        const edgeColor = isCompromised ? "#FF3366" : "#2F3447";
        const nodeStroke = isCompromised ? "#FF3366" : "#FFB800";
        return (
          <g key={h.target}>
            <path d={`M${cx},${cy} L${x},${y}`} stroke={edgeColor} strokeWidth={isCompromised ? 2 : 1} fill="none" />
            <rect x={x - 16} y={y - 16} width={32} height={32} fill="#0A0B0F" stroke={nodeStroke} strokeWidth={2} />
            <text x={x} y={y + 30} fill="#E8EAED" fontFamily="JetBrains Mono" fontSize={10} textAnchor="middle">
              {h.target}
            </text>
            {h.os_guess && (
              <text x={x} y={y + 42} fill="#9AA0B4" fontFamily="JetBrains Mono" fontSize={9} textAnchor="middle">
                {h.os_guess.slice(0, 16)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/* ─── Terminal Panel ─────────────────────────────────────────────────────── */

type TerminalPanelProps = {
  executionEvents: ExecutionEvent[];
  executionActive: boolean;
  onLaunchClick: () => void;
  launchDisabled: boolean;
};

function TerminalPanel({
  executionEvents,
  executionActive,
  onLaunchClick,
  launchDisabled,
}: TerminalPanelProps) {
  return (
    <div className="h-[200px] border-t border-border-subtle bg-black flex flex-col shrink-0">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border-subtle/50">
        <h4 className="font-mono text-[10px] font-bold uppercase tracking-widest text-text-tertiary flex items-center gap-2">
          <span className="material-symbols-outlined text-[14px]">terminal</span>
          Live_Execution_Stream
        </h4>
        <div className="flex items-center gap-3">
          {executionActive && (
            <span className="flex items-center gap-1.5 font-mono text-[10px] text-secondary">
              <span className="w-1.5 h-1.5 bg-secondary animate-pulse" />
              Running
            </span>
          )}
          <button
            type="button"
            disabled={launchDisabled}
            onClick={onLaunchClick}
            className="bg-primary px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-white hover:brightness-110 disabled:opacity-30 transition"
          >
            {executionActive ? "Tool Active…" : "Launch_Tool"}
          </button>
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-green-500 rounded-full" />
            <span className="w-2 h-2 bg-yellow-500 rounded-full" />
            <span className="w-2 h-2 bg-red-500 rounded-full" />
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <LiveTerminal events={executionEvents} />
      </div>
    </div>
  );
}

/* ─── Findings Panel ─────────────────────────────────────────────────────── */

function FindingsPanel({ findings }: { findings: Finding[] }) {
  return (
    <section className="flex flex-col overflow-hidden border-b border-border-subtle" style={{ flex: "0 0 60%" }}>
      <div className="px-3 py-2 border-b border-border-subtle flex justify-between items-center bg-surface-tertiary shrink-0">
        <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-text-primary flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-lg">bug_report</span>
          Latest_Findings
        </h2>
        <span className="font-mono text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 border border-primary/20">
          TOTAL: {findings.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {findings.length === 0 && (
          <div className="p-4 font-mono text-[11px] text-text-tertiary">
            No findings recorded yet.
          </div>
        )}
        {findings.map((f) => (
          <FindingRow key={f.id} finding={f} />
        ))}
      </div>
      <button
        type="button"
        className="p-2.5 text-[9px] font-bold text-primary uppercase tracking-widest bg-surface-container border-t border-border-subtle hover:bg-primary/5 transition shrink-0"
      >
        Export_Findings_JSON
      </button>
    </section>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const color = SEVERITY_COLOR[finding.severity];
  return (
    <div className="px-3 py-2.5 border-b border-border-subtle hover:bg-surface-tertiary transition cursor-pointer group">
      <div className="flex justify-between items-start mb-1">
        <span
          className={`px-1.5 py-0.5 text-[9px] font-bold uppercase ${SEV_BADGE[finding.severity]}`}
        >
          {finding.severity}
        </span>
        <span className="font-mono text-[10px] text-text-tertiary">
          {timeOnly(finding.created_at)}
        </span>
      </div>
      <h3
        className="font-mono text-xs font-bold text-text-primary group-hover:text-primary transition leading-tight truncate"
        style={{ color: undefined }}
      >
        {finding.title}
      </h3>
      <p className="font-mono text-[10px] text-text-tertiary mt-0.5 truncate">
        {finding.attack_technique ? `TECH: ${finding.attack_technique}` : finding.summary?.slice(0, 50)}
      </p>
    </div>
  );
}

/* ─── Approvals Panel ────────────────────────────────────────────────────── */

type ApprovalsPanelProps = {
  approvals: Approval[];
  busyApproval: string | null;
  onDecide: (id: string, approved: boolean) => void;
};

function ApprovalsPanel({ approvals, busyApproval, onDecide }: ApprovalsPanelProps) {
  return (
    <section className="flex flex-col flex-1 overflow-hidden">
      <div className="px-3 py-2 border-b border-border-subtle bg-surface-tertiary flex justify-between items-center shrink-0">
        <h2 className="font-mono text-[11px] font-bold uppercase tracking-widest text-text-primary flex items-center gap-2">
          <span className="material-symbols-outlined text-tertiary text-lg">verified_user</span>
          Auth_Required
        </h2>
        {approvals.length > 0 && (
          <div className="w-2 h-2 bg-tertiary animate-pulse" />
        )}
      </div>
      <div className="flex-1 p-3 flex flex-col gap-2 overflow-y-auto">
        {approvals.length === 0 && (
          <p className="font-mono text-[11px] text-text-tertiary">No pending approvals.</p>
        )}
        {approvals.map((a) => (
          <ApprovalCard
            key={a.id}
            approval={a}
            busy={busyApproval === a.id}
            onDecide={onDecide}
          />
        ))}
      </div>
    </section>
  );
}

function ApprovalCard({
  approval,
  busy,
  onDecide,
}: {
  approval: Approval;
  busy: boolean;
  onDecide: (id: string, approved: boolean) => void;
}) {
  const isHighRisk = approval.risk_level === "high";
  return (
    <div className={`p-2.5 border bg-surface-container ${isHighRisk ? "border-severity-critical/50" : "border-border-accent"}`}>
      <div className="flex justify-between mb-1">
        <span className={`font-mono text-[9px] uppercase font-bold ${isHighRisk ? "text-severity-critical" : "text-severity-medium"}`}>
          {isHighRisk ? "Destructive_Action" : "Operator_Action"}
        </span>
        <span className="font-mono text-[9px] text-text-tertiary">
          {approval.tool_name}
        </span>
      </div>
      <p className="font-mono text-[11px] text-text-primary mb-2.5">
        {approval.operation_name} &rarr;{" "}
        <span className="text-primary">{approval.requested_action.slice(0, 40)}</span>
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecide(approval.id, true)}
          className="flex-1 py-1 bg-primary text-white text-[10px] font-bold uppercase hover:brightness-110 disabled:opacity-40 transition"
        >
          {busy ? "…" : "Approve"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecide(approval.id, false)}
          className="flex-1 py-1 border border-border-accent text-text-secondary text-[10px] font-bold uppercase hover:bg-surface-tertiary disabled:opacity-40 transition"
        >
          Deny
        </button>
      </div>
    </div>
  );
}

/* ─── Audit Marquee ──────────────────────────────────────────────────────── */

function AuditMarquee({ events, now }: { events: AuditEvent[]; now: number }) {
  if (events.length === 0) {
    return (
      <footer className="h-8 bg-surface-dim border-t border-border-subtle flex items-center px-4 text-text-tertiary font-mono text-[10px] uppercase tracking-widest shrink-0">
        Live_Stream · Awaiting events…
      </footer>
    );
  }
  return (
    <footer className="h-8 bg-surface-dim border-t border-border-subtle flex items-center px-4 overflow-hidden shrink-0">
      <div className="flex items-center gap-2 shrink-0 border-r border-border-subtle pr-4 mr-4">
        <span className="w-2 h-2 bg-secondary animate-pulse" />
        <span className="font-mono text-[10px] text-text-primary font-bold uppercase tracking-widest">
          Live_Stream
        </span>
      </div>
      <div className="flex gap-6 overflow-hidden whitespace-nowrap flex-1">
        {events.map((ev, i) => (
          <span key={`${ev.evidence_hash}-${i}`} className="font-mono text-[11px] text-text-secondary">
            <span className="text-severity-low uppercase">
              {ev.event_type.split(".")[0]}
            </span>{" "}
            {ev.event_type}{" "}
            <span className="text-text-tertiary">{relativeAge(ev.occurred_at, now)}</span>
          </span>
        ))}
      </div>
    </footer>
  );
}
