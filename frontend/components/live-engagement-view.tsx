"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  Approval,
  AuditEvent,
  Engagement,
  ExecutionEvent,
  Finding,
  FindingSeverity,
  Inventory,
  decideApproval,
  getInventory,
  listApprovals,
  listAuditEvents,
  listEngagements,
  listFindings,
} from "@/lib/api";

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

const SEVERITY_LABEL: Record<FindingSeverity, string> = {
  critical: "Critical",
  high: "High Risk",
  medium: "Medium",
  low: "Low",
  info: "Info",
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
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function LiveEngagementView() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [inventory, setInventory] = useState<Inventory>({ hosts: [], services: [] });
  const [executionEvents] = useState<ExecutionEvent[]>([]);
  const [now, setNow] = useState<number>(Date.now());
  const [error, setError] = useState<string | null>(null);
  const [busyApproval, setBusyApproval] = useState<string | null>(null);
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
      const [f, a, e, inv] = await Promise.all([
        listFindings(engagementId),
        listApprovals(engagementId),
        listAuditEvents(engagementId),
        getInventory(engagementId),
      ]);
      setFindings(f);
      setApprovals(a);
      setAudit(e);
      setInventory(inv);
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

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem-2rem)] -mx-gutter -my-gutter bg-bg-primary text-text-primary">
      <EngagementBar
        engagements={engagements}
        selectedId={selectedId}
        onSelect={setSelectedId}
        selected={selected}
        error={error}
      />

      <main className="grid grid-cols-12 flex-1 overflow-hidden">
        <FindingsPanel findings={sortedFindings} />
        <CenterPanel
          inventory={inventory}
          executionEvents={executionEvents}
          selected={selected}
        />
        <RightPanel
          approvals={pendingApprovals}
          busyApproval={busyApproval}
          onDecide={handleDecide}
          findings={sortedFindings}
          inventory={inventory}
        />
      </main>

      <AuditMarquee events={recentAudit} now={now} />
    </div>
  );
}

type EngagementBarProps = {
  engagements: Engagement[];
  selectedId: string;
  onSelect: (id: string) => void;
  selected: Engagement | undefined;
  error: string | null;
};

function EngagementBar({ engagements, selectedId, onSelect, selected, error }: EngagementBarProps) {
  return (
    <div className="h-10 border-b border-border-subtle bg-surface-secondary flex items-center justify-between px-4">
      <div className="flex items-center gap-4">
        <span className="font-display text-[10px] uppercase tracking-widest text-text-tertiary">
          Engagement
        </span>
        <select
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          className="bg-surface-tertiary border border-border-subtle px-2 py-1 font-mono text-[11px] text-text-primary focus:outline-none focus:border-primary"
        >
          {engagements.length === 0 && <option value="">— No engagements —</option>}
          {engagements.map((e) => (
            <option key={e.id} value={e.id}>
              {shortId(e.id)} · {e.name}
            </option>
          ))}
        </select>
        {selected && (
          <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 border border-border-subtle text-text-secondary">
            STATUS: <span className="text-secondary">{selected.status}</span>
          </span>
        )}
        {selected && (
          <span className="font-mono text-[10px] text-text-tertiary">
            SCOPE: {selected.scope_cidrs.join(", ")}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {error && (
          <span className="font-mono text-[10px] text-severity-critical">
            ERR: {error.slice(0, 60)}
          </span>
        )}
        <a
          href="/engagements/console"
          className="font-display text-[10px] uppercase tracking-wider text-text-tertiary hover:text-primary border-l border-border-subtle pl-3"
        >
          Operator Console
        </a>
      </div>
    </div>
  );
}

type FindingsPanelProps = {
  findings: Finding[];
};

function FindingsPanel({ findings }: FindingsPanelProps) {
  return (
    <section className="col-span-3 border-r border-border-subtle bg-surface-dim flex flex-col overflow-hidden">
      <div className="p-3 border-b border-border-subtle flex justify-between items-center bg-surface-secondary">
        <h2 className="font-display text-[11px] font-semibold uppercase tracking-widest text-text-primary">
          Live Findings
        </h2>
        <span className="font-mono text-[10px] text-severity-critical px-1 border border-severity-critical/30">
          REC: {findings.length}
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
    </section>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const color = SEVERITY_COLOR[finding.severity];
  return (
    <div className="relative pl-3 pr-4 py-3 bg-surface-secondary/40 hover:bg-surface-tertiary transition-colors border-b border-border-subtle/50 cursor-pointer">
      <div className="absolute left-0 top-0 bottom-0 w-1" style={{ background: color }} />
      <div className="flex justify-between items-start mb-1">
        <span
          className="font-mono text-[10px] uppercase"
          style={{ color }}
        >
          {SEVERITY_LABEL[finding.severity]} · F-{shortId(finding.id)}
        </span>
        <span className="font-mono text-[10px] text-text-tertiary">
          {timeOnly(finding.created_at)}
        </span>
      </div>
      <h3 className="font-display text-[11px] font-semibold uppercase tracking-wider text-text-primary mb-1">
        {finding.title}
      </h3>
      <p className="font-sans text-[11px] text-text-secondary leading-tight line-clamp-2">
        {finding.summary}
      </p>
      {finding.attack_technique && (
        <div className="mt-2 flex gap-2 flex-wrap">
          <span className="bg-surface-tertiary px-1.5 py-0.5 text-[10px] font-mono text-text-secondary border border-border-subtle">
            {finding.attack_technique}
          </span>
        </div>
      )}
    </div>
  );
}

type CenterPanelProps = {
  inventory: Inventory;
  executionEvents: ExecutionEvent[];
  selected: Engagement | undefined;
};

function CenterPanel({ inventory, executionEvents, selected }: CenterPanelProps) {
  return (
    <section className="col-span-6 bg-bg-primary relative overflow-hidden flex flex-col">
      <div className="p-3 border-b border-border-subtle flex justify-between items-center bg-surface-secondary/80">
        <div className="flex items-center gap-3">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-widest text-text-primary">
            Tactical View · Attack Vector Graph
          </h2>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-secondary animate-pulse rounded-full" />
            <span className="font-mono text-[10px] text-secondary uppercase">
              {selected?.status === "active" ? "Active Session" : "Idle"}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            aria-label="Zoom in"
            className="w-6 h-6 border border-border-subtle bg-surface-secondary hover:bg-surface-tertiary flex items-center justify-center"
          >
            <span className="material-symbols-outlined text-[14px]">zoom_in</span>
          </button>
          <button
            type="button"
            aria-label="Refresh graph"
            className="w-6 h-6 border border-border-subtle bg-surface-secondary hover:bg-surface-tertiary flex items-center justify-center"
          >
            <span className="material-symbols-outlined text-[14px]">refresh</span>
          </button>
        </div>
      </div>

      <div className="flex-1 relative cursor-crosshair overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "radial-gradient(#252836 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        />
        <AttackGraph inventory={inventory} />
        <div className="absolute bottom-3 left-3 bg-surface-secondary/90 border border-border-subtle p-2 flex flex-col gap-1 w-44">
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <span className="text-[9px] font-mono text-text-tertiary">NODES_DISCOVERED</span>
            <span className="text-[9px] font-mono text-text-primary">{inventory.hosts.length}</span>
          </div>
          <div className="flex justify-between border-b border-border-subtle pb-1">
            <span className="text-[9px] font-mono text-text-tertiary">SERVICES_FOUND</span>
            <span className="text-[9px] font-mono text-text-primary">
              {inventory.services.length}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[9px] font-mono text-text-tertiary">SESSION_ID</span>
            <span className="text-[9px] font-mono text-secondary">
              {selected ? shortId(selected.id) : "—"}
            </span>
          </div>
        </div>
      </div>

      <div className="h-56 border-t border-border-subtle bg-black overflow-hidden">
        <div className="px-3 py-2 border-b border-border-subtle/50 font-mono text-[10px] uppercase tracking-widest text-text-tertiary">
          Primary Payload Terminal
        </div>
        <div className="h-[calc(100%-2rem)]">
          <LiveTerminal events={executionEvents} />
        </div>
      </div>
    </section>
  );
}

function AttackGraph({ inventory }: { inventory: Inventory }) {
  const hosts = inventory.hosts.slice(0, 8);
  if (hosts.length === 0) {
    return (
      <div className="absolute inset-0 flex items-center justify-center font-mono text-[11px] text-text-tertiary uppercase tracking-widest">
        No hosts discovered yet · Launch a scan from the Operator Console
      </div>
    );
  }
  const cx = 400;
  const cy = 240;
  const r = 160;
  const angle = (i: number) => (2 * Math.PI * i) / hosts.length - Math.PI / 2;
  return (
    <svg className="absolute inset-0 w-full h-full" viewBox="0 0 800 480" preserveAspectRatio="xMidYMid meet">
      <rect x={cx - 18} y={cy - 18} width={36} height={36} fill="#141620" stroke="#4F8EF7" strokeWidth={2} />
      <text x={cx} y={cy + 38} fill="#4F8EF7" fontFamily="JetBrains Mono" fontSize={11} fontWeight="bold" textAnchor="middle">
        ORIGIN
      </text>
      {hosts.map((h, i) => {
        const x = cx + r * Math.cos(angle(i));
        const y = cy + r * Math.sin(angle(i));
        return (
          <g key={h.target}>
            <path d={`M${cx},${cy} L${x},${y}`} stroke="#2F3447" strokeWidth={1.5} fill="none" />
            <rect x={x - 16} y={y - 16} width={32} height={32} fill="#141620" stroke="#FF3366" strokeWidth={2} />
            <text x={x} y={y + 30} fill="#E8EAED" fontFamily="JetBrains Mono" fontSize={10} textAnchor="middle">
              {h.target}
            </text>
            {h.os_guess && (
              <text x={x} y={y + 42} fill="#9AA0B4" fontFamily="JetBrains Mono" fontSize={9} textAnchor="middle">
                {h.os_guess.slice(0, 18)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

type RightPanelProps = {
  approvals: Approval[];
  busyApproval: string | null;
  onDecide: (id: string, approved: boolean) => void;
  findings: Finding[];
  inventory: Inventory;
};

function RightPanel({ approvals, busyApproval, onDecide, findings, inventory }: RightPanelProps) {
  const criticalCount = findings.filter((f) => f.severity === "critical").length;
  const highCount = findings.filter((f) => f.severity === "high").length;

  return (
    <section className="col-span-3 border-l border-border-subtle bg-surface-dim flex flex-col overflow-hidden">
      <div className="p-3 border-b border-border-subtle bg-surface-secondary">
        <h2 className="font-display text-[11px] font-semibold uppercase tracking-widest text-text-primary">
          Critical Approvals
        </h2>
      </div>
      <div className="p-3 space-y-3 overflow-y-auto flex-1">
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

      <div className="border-t border-border-subtle p-3 bg-surface-secondary">
        <h2 className="font-display text-[11px] font-semibold uppercase tracking-widest text-text-tertiary mb-3">
          Tactical Status
        </h2>
        <StatusRow label="HOSTS" value={String(inventory.hosts.length)} tone="primary" />
        <StatusRow label="SERVICES" value={String(inventory.services.length)} tone="primary" />
        <StatusRow
          label="CRIT_FINDINGS"
          value={String(criticalCount)}
          tone={criticalCount > 0 ? "critical" : "muted"}
        />
        <StatusRow
          label="HIGH_FINDINGS"
          value={String(highCount)}
          tone={highCount > 0 ? "high" : "muted"}
        />
        <StatusRow
          label="PENDING_APPROVALS"
          value={String(approvals.length)}
          tone={approvals.length > 0 ? "high" : "muted"}
        />
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
    <div
      className={`bg-surface-tertiary border p-3 ${
        isHighRisk ? "border-severity-critical/50" : "border-border-accent"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`material-symbols-outlined text-[16px] ${
            isHighRisk ? "text-severity-critical" : "text-severity-medium"
          }`}
        >
          {isHighRisk ? "warning" : "info"}
        </span>
        <span
          className={`font-display text-[10px] uppercase font-bold ${
            isHighRisk ? "text-severity-critical" : "text-severity-medium"
          }`}
        >
          {isHighRisk ? "High Risk Action" : "Operator Action"}
        </span>
      </div>
      <h4 className="font-mono text-[11px] text-text-primary mb-1">
        {approval.tool_name}.{approval.operation_name}
      </h4>
      <p className="font-sans text-[11px] text-text-secondary mb-3">
        {approval.requested_action}
      </p>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecide(approval.id, true)}
          className="bg-severity-critical h-8 font-display text-[11px] text-white hover:opacity-80 disabled:opacity-40 transition-opacity uppercase tracking-wider"
        >
          {busy ? "..." : "Execute"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecide(approval.id, false)}
          className="border border-border-subtle h-8 font-display text-[11px] text-text-primary hover:bg-surface-tertiary disabled:opacity-40 transition-colors uppercase tracking-wider"
        >
          Abort
        </button>
      </div>
    </div>
  );
}

function StatusRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "primary" | "critical" | "high" | "muted";
}) {
  const toneClass = {
    primary: "text-secondary",
    critical: "text-severity-critical",
    high: "text-severity-high",
    muted: "text-text-secondary",
  }[tone];
  return (
    <div className="flex justify-between py-1">
      <span className="text-[10px] font-mono text-text-secondary">{label}</span>
      <span className={`text-[10px] font-mono uppercase ${toneClass}`}>{value}</span>
    </div>
  );
}

type AuditMarqueeProps = {
  events: AuditEvent[];
  now: number;
};

function AuditMarquee({ events, now }: AuditMarqueeProps) {
  if (events.length === 0) {
    return (
      <footer className="h-8 bg-surface-dim border-t border-border-subtle flex items-center px-4 text-text-tertiary font-mono text-[10px] uppercase tracking-widest">
        Live_Stream · Awaiting events…
      </footer>
    );
  }
  return (
    <footer className="h-8 bg-surface-dim border-t border-border-subtle flex items-center px-4 overflow-hidden">
      <div className="flex items-center gap-2 shrink-0 border-r border-border-subtle pr-4 mr-4">
        <span className="w-2 h-2 bg-secondary rounded-full animate-pulse" />
        <span className="font-display text-[10px] text-text-primary font-bold uppercase tracking-widest">
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
