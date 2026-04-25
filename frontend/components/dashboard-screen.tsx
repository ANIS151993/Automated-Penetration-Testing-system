"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  Engagement,
  EngagementStatus,
  Finding,
  FindingSeverity,
  HealthResponse,
  Inventory,
  getHealth,
  getInventory,
  listEngagements,
  listFindings,
} from "@/lib/api";

type DashboardData = {
  health: HealthResponse | null;
  engagements: Engagement[];
  findingsByEngagement: Record<string, Finding[]>;
  inventoryByEngagement: Record<string, Inventory>;
};

const SEVERITY_RANK: Record<FindingSeverity, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
};

const SEVERITY_BORDER: Record<FindingSeverity, string> = {
  critical: "border-severity-critical/40 text-severity-critical",
  high: "border-severity-high/40 text-severity-high",
  medium: "border-severity-medium/40 text-severity-medium",
  low: "border-severity-low/40 text-severity-low",
  info: "border-border-subtle text-text-tertiary",
};

const STATUS_COLOR: Record<EngagementStatus, string> = {
  active: "text-secondary",
  paused: "text-severity-medium",
  draft: "text-text-tertiary",
  aborted: "text-severity-critical",
  archived: "text-text-tertiary",
};

const STATUS_DOT: Record<EngagementStatus, string> = {
  active: "●",
  paused: "○",
  draft: "○",
  aborted: "●",
  archived: "○",
};

function topSeverity(findings: Finding[]): FindingSeverity | null {
  if (findings.length === 0) return null;
  return findings.reduce<FindingSeverity>(
    (acc, f) =>
      SEVERITY_RANK[f.severity] > SEVERITY_RANK[acc] ? f.severity : acc,
    "info",
  );
}

function relativeTtl(updatedAt: string): string {
  const updated = new Date(updatedAt).getTime();
  const now = Date.now();
  const deltaMs = Math.max(now - updated, 0);
  const days = Math.floor(deltaMs / (24 * 60 * 60 * 1000));
  const hours = Math.floor((deltaMs % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
  return `${String(days).padStart(2, "0")}d:${String(hours).padStart(2, "0")}h`;
}

function shortId(id: string): string {
  return id.split("-")[0].toUpperCase();
}

export function DashboardScreen() {
  const [data, setData] = useState<DashboardData>({
    health: null,
    engagements: [],
    findingsByEngagement: {},
    inventoryByEngagement: {},
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [health, engagements] = await Promise.all([
          getHealth().catch(() => null),
          listEngagements().catch(() => [] as Engagement[]),
        ]);
        const findingsEntries = await Promise.all(
          engagements.map((eng) =>
            listFindings(eng.id)
              .catch(() => [] as Finding[])
              .then((findings) => [eng.id, findings] as const),
          ),
        );
        const inventoryEntries = await Promise.all(
          engagements.map((eng) =>
            getInventory(eng.id)
              .catch(() => ({ hosts: [], services: [] }) as Inventory)
              .then((inv) => [eng.id, inv] as const),
          ),
        );
        if (cancelled) return;
        setData({
          health,
          engagements,
          findingsByEngagement: Object.fromEntries(findingsEntries),
          inventoryByEngagement: Object.fromEntries(inventoryEntries),
        });
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Dashboard load failed.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const activeOps = data.engagements.filter(
      (e) => e.status === "active",
    ).length;
    const allFindings = Object.values(data.findingsByEngagement).flat();
    const critFindings = allFindings.filter(
      (f) => f.severity === "critical" || f.severity === "high",
    ).length;
    const totalNodes = Object.values(data.inventoryByEngagement).reduce(
      (acc, inv) => acc + inv.hosts.length,
      0,
    );
    const totalEng = data.engagements.length || 1;
    const settledEng = data.engagements.filter(
      (e) => e.status === "active" || e.status === "archived",
    ).length;
    const postureIndex = Math.round((settledEng / totalEng) * 100);
    return {
      activeOps,
      critFindings,
      totalNodes,
      postureIndex,
      allFindings,
    };
  }, [data]);

  const topEngagements = useMemo(
    () => [...data.engagements].slice(0, 6),
    [data.engagements],
  );

  const liveIntel = useMemo(() => {
    return [...stats.allFindings]
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
      .slice(0, 4);
  }, [stats.allFindings]);

  const riskBuckets = useMemo(() => {
    const buckets = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    } as Record<FindingSeverity, number>;
    for (const f of stats.allFindings) buckets[f.severity] += 1;
    return buckets;
  }, [stats.allFindings]);

  return (
    <div className="space-y-4">
      <DashboardHeader
        operator={data.engagements[0]?.operator_name ?? "—"}
        now={now}
        activeOps={stats.activeOps}
      />

      <KpiGrid
        activeOps={stats.activeOps}
        critFindings={stats.critFindings}
        totalNodes={stats.totalNodes}
        postureIndex={stats.postureIndex}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        <OperationalQueue
          engagements={topEngagements}
          findingsByEngagement={data.findingsByEngagement}
          loading={loading}
          error={error}
        />
        <aside className="lg:col-span-4 space-y-4">
          <CoreHealthCard health={data.health} />
          <LiveIntelCard findings={liveIntel} />
        </aside>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 pb-gutter">
        <ScanPerimeterCard activeOps={stats.activeOps} />
        <RiskDistributionCard buckets={riskBuckets} />
      </section>
    </div>
  );
}

type DashboardHeaderProps = {
  operator: string;
  now: Date;
  activeOps: number;
};

function DashboardHeader({ operator, now, activeOps }: DashboardHeaderProps) {
  const stamp = now.toISOString().slice(11, 19);
  return (
    <section className="flex flex-col md:flex-row md:items-end justify-between gap-4">
      <div>
        <h1 className="font-h1 text-h1 text-text-primary tracking-tight">
          Operator Workspace: {operator}
        </h1>
        <p className="font-mono text-[11px] text-text-tertiary mt-0.5 uppercase tracking-widest">
          UTC: {stamp} | AGENTS: {String(activeOps).padStart(2, "0")}_ACTIVE | UPTIME: 99.98%
        </p>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          className="flex items-center gap-2 px-3 py-1.5 border border-border-accent text-[11px] font-bold uppercase tracking-wider hover:bg-surface-secondary transition"
        >
          <span className="material-symbols-outlined text-sm">file_download</span>
          Export_DB
        </button>
        <Link
          href="/engagements"
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-white text-[11px] font-bold uppercase tracking-wider hover:brightness-110 transition"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          New_Task
        </Link>
      </div>
    </section>
  );
}

type KpiGridProps = {
  activeOps: number;
  critFindings: number;
  totalNodes: number;
  postureIndex: number;
};

function KpiGrid({ activeOps, critFindings, totalNodes, postureIndex }: KpiGridProps) {
  return (
    <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <KpiCard
        icon="target"
        iconColor="text-primary"
        label="Active_Ops"
        value={String(activeOps).padStart(2, "0")}
        meta={activeOps > 0 ? "+RUNNING" : "IDLE"}
        metaColor="text-secondary"
      />
      <KpiCard
        icon="warning"
        iconColor="text-severity-critical"
        label="Crit_Findings"
        value={String(critFindings).padStart(2, "0")}
        valueColor="text-severity-critical"
        meta={critFindings > 0 ? "Immediate" : "Clear"}
        metaColor={
          critFindings > 0 ? "text-severity-critical" : "text-text-tertiary"
        }
      />
      <KpiCard
        icon="dns"
        iconColor="text-severity-medium"
        label="Total_Nodes"
        value={totalNodes.toLocaleString()}
        meta="VERIFIED"
        metaColor="text-text-tertiary"
      />
      <KpiCard
        icon="verified_user"
        iconColor="text-secondary"
        label="Posture_Index"
        value={`${postureIndex}%`}
        meta={postureIndex >= 80 ? "STABLE" : "AT_RISK"}
        metaColor={
          postureIndex >= 80 ? "text-secondary" : "text-severity-medium"
        }
      />
    </section>
  );
}

type KpiCardProps = {
  icon: string;
  iconColor: string;
  label: string;
  value: string;
  valueColor?: string;
  meta: string;
  metaColor: string;
};

function KpiCard({
  icon,
  iconColor,
  label,
  value,
  valueColor = "text-text-primary",
  meta,
  metaColor,
}: KpiCardProps) {
  return (
    <div className="bg-surface border border-border-subtle p-padding-card flex flex-col justify-between h-24">
      <div className="flex items-center gap-2 text-text-tertiary">
        <span className={`material-symbols-outlined text-xs ${iconColor}`}>
          {icon}
        </span>
        <span className="font-label-caps text-label-caps uppercase">{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`font-h2 text-h2 ${valueColor}`}>{value}</span>
        <span className={`font-mono text-[10px] uppercase ${metaColor}`}>
          {meta}
        </span>
      </div>
    </div>
  );
}

type OperationalQueueProps = {
  engagements: Engagement[];
  findingsByEngagement: Record<string, Finding[]>;
  loading: boolean;
  error: string | null;
};

function OperationalQueue({
  engagements,
  findingsByEngagement,
  loading,
  error,
}: OperationalQueueProps) {
  return (
    <section className="lg:col-span-8 bg-surface border border-border-subtle overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-border-subtle flex justify-between items-center bg-surface-container-low">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary text-base">
            lan
          </span>
          <h3 className="font-label-caps text-label-caps uppercase text-text-primary">
            Operational_Queue
          </h3>
        </div>
        <Link
          href="/engagements"
          className="text-[10px] text-primary font-bold uppercase tracking-wider hover:underline"
        >
          Full_Registry
        </Link>
      </div>
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border-subtle bg-surface-container-lowest">
              <th className="px-4 py-2 font-label-caps text-[9px] text-text-tertiary uppercase">
                UID / Engagement
              </th>
              <th className="px-4 py-2 font-label-caps text-[9px] text-text-tertiary uppercase">
                Status
              </th>
              <th className="px-4 py-2 font-label-caps text-[9px] text-text-tertiary uppercase">
                Findings
              </th>
              <th className="px-4 py-2 font-label-caps text-[9px] text-text-tertiary uppercase">
                Risk
              </th>
              <th className="px-4 py-2 font-label-caps text-[9px] text-text-tertiary uppercase">
                Age
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle font-mono text-[11px]">
            {loading && engagements.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-text-tertiary text-[10px] uppercase tracking-widest">
                  Loading registry…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-severity-critical text-[10px] uppercase tracking-widest">
                  {error}
                </td>
              </tr>
            ) : engagements.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-text-tertiary text-[10px] uppercase tracking-widest">
                  No engagements registered.
                </td>
              </tr>
            ) : (
              engagements.map((eng) => {
                const findings = findingsByEngagement[eng.id] ?? [];
                const sev = topSeverity(findings);
                const findingsCount = findings.length;
                const sevClass = sev
                  ? SEVERITY_BORDER[sev]
                  : "border-border-subtle text-text-tertiary";
                const sevLabel = sev ? sev.toUpperCase() : "NONE";
                return (
                  <tr
                    key={eng.id}
                    className="hover:bg-surface-container-high transition"
                  >
                    <td className="px-4 py-2">
                      <div className="flex flex-col">
                        <Link
                          href={`/engagements`}
                          className="text-text-primary font-bold hover:text-primary"
                        >
                          #EP-{shortId(eng.id)} :: {eng.name}
                        </Link>
                        <span className="text-[9px] text-text-tertiary">
                          {eng.scope_cidrs.join(", ")}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`text-[10px] uppercase font-bold ${STATUS_COLOR[eng.status]}`}
                      >
                        {STATUS_DOT[eng.status]} {eng.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-text-secondary">
                      {findingsCount}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`px-1.5 border text-[9px] font-bold uppercase ${sevClass}`}
                      >
                        {sevLabel}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-text-tertiary">
                      {relativeTtl(eng.updated_at)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

type CoreHealthCardProps = {
  health: HealthResponse | null;
};

function CoreHealthCard({ health }: CoreHealthCardProps) {
  const dbOk =
    health?.database_status?.toLowerCase() === "ok" ||
    health?.database_status?.toLowerCase() === "healthy";
  const apiOk = health?.status?.toLowerCase() === "ok" || !!health;
  return (
    <div className="bg-surface border border-border-subtle p-padding-card">
      <h3 className="font-label-caps text-label-caps uppercase text-text-primary mb-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-primary text-base">
          health_and_safety
        </span>
        Core_Health
      </h3>
      <div className="space-y-2">
        <HealthRow
          icon="bolt"
          label="Control_Plane"
          detail={health ? `ENV: ${health.environment}` : "OFFLINE"}
          ok={apiOk}
        />
        <HealthRow
          icon="storage"
          label="Database"
          detail={`STATUS: ${health?.database_status ?? "UNKNOWN"}`}
          ok={dbOk}
        />
        <HealthRow
          icon="hub"
          label="Weapon_Node"
          detail={health?.weapon_node_url ?? "—"}
          ok={!!health?.weapon_node_url}
        />
      </div>
    </div>
  );
}

type HealthRowProps = {
  icon: string;
  label: string;
  detail: string;
  ok: boolean;
};

function HealthRow({ icon, label, detail, ok }: HealthRowProps) {
  return (
    <div className="p-2 border border-border-accent bg-surface-container-low flex items-center justify-between font-mono">
      <div className="flex items-center gap-3">
        <span
          className={`material-symbols-outlined text-sm ${
            ok ? "text-secondary" : "text-severity-critical"
          }`}
        >
          {icon}
        </span>
        <div className="text-[10px]">
          <div className="font-bold text-text-primary uppercase">{label}</div>
          <div className="text-text-tertiary truncate max-w-[180px]">{detail}</div>
        </div>
      </div>
      <span
        className={`material-symbols-outlined text-sm ${
          ok ? "text-secondary" : "text-severity-critical"
        }`}
      >
        {ok ? "check_circle" : "error"}
      </span>
    </div>
  );
}

type LiveIntelCardProps = {
  findings: Finding[];
};

function LiveIntelCard({ findings }: LiveIntelCardProps) {
  return (
    <div className="bg-surface border border-border-subtle p-padding-card">
      <h3 className="font-label-caps text-label-caps uppercase text-text-primary mb-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-primary text-base">
          list_alt
        </span>
        Live_Intel
      </h3>
      <div className="space-y-3 font-mono">
        {findings.length === 0 ? (
          <div className="text-[10px] text-text-tertiary uppercase tracking-widest">
            No findings yet.
          </div>
        ) : (
          findings.map((f) => {
            const dot =
              f.severity === "critical" || f.severity === "high"
                ? "bg-severity-critical"
                : f.severity === "medium"
                  ? "bg-severity-medium"
                  : "bg-secondary";
            const stamp = new Date(f.created_at)
              .toISOString()
              .slice(11, 23);
            return (
              <div
                key={f.id}
                className="relative pl-4 border-l border-border-subtle"
              >
                <div
                  className={`absolute -left-[4.5px] top-1.5 w-2 h-2 ${dot}`}
                />
                <div className="text-[9px] text-text-tertiary mb-0.5">
                  {stamp}
                </div>
                <div className="text-[11px] text-text-primary uppercase tracking-tight truncate">
                  {f.title}
                </div>
              </div>
            );
          })
        )}
      </div>
      <Link
        href="/engagements"
        className="block w-full mt-4 py-1.5 border border-border-accent text-[10px] font-bold uppercase tracking-widest hover:bg-surface-container-high transition text-center"
      >
        Launch_Shell
      </Link>
    </div>
  );
}

type ScanPerimeterCardProps = {
  activeOps: number;
};

function ScanPerimeterCard({ activeOps }: ScanPerimeterCardProps) {
  const active = activeOps > 0;
  return (
    <div className="bg-surface border border-border-subtle p-padding-card relative">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-label-caps text-label-caps uppercase text-text-primary">
            Scan_Perimeter
          </h3>
          <p className="text-[9px] font-mono text-text-tertiary uppercase">
            real-time surface map
          </p>
        </div>
        <span className="material-symbols-outlined text-text-tertiary cursor-pointer">
          fullscreen
        </span>
      </div>
      <div className="h-40 bg-surface-container-lowest border border-border-accent relative flex items-center justify-center overflow-hidden">
        <div className="relative z-10 text-center font-mono flex flex-col items-center">
          <div
            className={`w-16 h-16 border-2 border-primary/20 mb-3 ${
              active ? "border-t-primary animate-spin" : "border-t-text-tertiary"
            }`}
          />
          <span className="text-[10px] text-primary tracking-widest uppercase">
            {active ? "Syscap_Active" : "Syscap_Idle"}
          </span>
        </div>
      </div>
    </div>
  );
}

type RiskDistributionCardProps = {
  buckets: Record<FindingSeverity, number>;
};

function RiskDistributionCard({ buckets }: RiskDistributionCardProps) {
  const total =
    buckets.critical + buckets.high + buckets.medium + buckets.low + buckets.info;
  const segments: Array<{ key: FindingSeverity; cls: string; label: string }> = [
    { key: "critical", cls: "bg-severity-critical", label: "Crit" },
    { key: "high", cls: "bg-severity-high", label: "High" },
    { key: "medium", cls: "bg-severity-medium", label: "Med" },
    { key: "low", cls: "bg-severity-low", label: "Low" },
    { key: "info", cls: "bg-severity-info", label: "Info" },
  ];
  return (
    <div className="bg-surface border border-border-subtle p-padding-card">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-label-caps text-label-caps uppercase text-text-primary">
            Risk_Distribution
          </h3>
          <p className="text-[9px] font-mono text-text-tertiary uppercase">
            by severity ({total} total)
          </p>
        </div>
        <div className="flex gap-2 font-mono">
          {segments.slice(0, 3).map((s) => (
            <div key={s.key} className="flex items-center gap-1">
              <div className={`w-1.5 h-1.5 ${s.cls}`} />
              <span className="text-[8px] text-text-tertiary uppercase">
                {s.label}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3 font-mono">
        {segments.map((s) => {
          const count = buckets[s.key];
          const pct = total === 0 ? 0 : Math.round((count / total) * 100);
          return (
            <div key={s.key} className="flex flex-col gap-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-text-secondary uppercase">{s.label}</span>
                <span className="text-text-tertiary text-[9px]">
                  {count} ({pct}%)
                </span>
              </div>
              <div className="h-1.5 bg-border-subtle relative overflow-hidden">
                <div
                  className={`h-1.5 ${s.cls} transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
