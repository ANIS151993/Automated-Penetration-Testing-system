"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  Engagement,
  Report,
  ReportDocument,
  generateReport,
  getReportDocument,
  listEngagements,
  listReports,
} from "@/lib/api";

type AgentFinding = {
  agent_run_id: string;
  title: string;
  severity: string;
  attack_technique: string;
  summary: string;
  evidence_refs: string[];
};

type ReportSummary = {
  findings_total: number;
  agent_findings_total: number;
  agent_runs_total: number;
  suggested_findings_total: number;
  approved_actions: number;
  pending_approvals: number;
  validated_requests: number;
  executions_total: number;
  completed_executions: number;
  failed_executions: number;
  inventory_hosts: number;
  inventory_services: number;
};

const SEVERITY_TONE: Record<string, string> = {
  critical: "text-severity-critical",
  high: "text-severity-high",
  medium: "text-severity-medium",
  low: "text-primary",
  info: "text-text-tertiary",
};

export default function ReportsPage() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [reports, setReports] = useState<Report[]>([]);
  const [doc, setDoc] = useState<ReportDocument | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEngagements()
      .then((list) => {
        setEngagements(list);
        if (list.length > 0) setSelectedId(list[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const refreshReports = useCallback(async (engId: string) => {
    if (!engId) { setReports([]); return; }
    try {
      setReports(await listReports(engId));
    } catch (e) { setError(String(e)); }
  }, []);

  useEffect(() => { refreshReports(selectedId); }, [selectedId, refreshReports]);

  const onGenerate = useCallback(async () => {
    if (!selectedId) return;
    setGenerating(true);
    setError(null);
    try {
      const r = await generateReport(selectedId);
      await refreshReports(selectedId);
      setDoc(await getReportDocument(r.id));
    } catch (e) { setError(String(e)); }
    finally { setGenerating(false); }
  }, [selectedId, refreshReports]);

  const onLoad = useCallback(async (reportId: string) => {
    setError(null);
    try { setDoc(await getReportDocument(reportId)); }
    catch (e) { setError(String(e)); }
  }, []);

  const summary = doc?.content?.summary as ReportSummary | undefined;
  const agentFindings = (doc?.content?.agent_findings ?? []) as AgentFinding[];
  const findings = (doc?.content?.findings ?? []) as AgentFinding[];

  return (
    <AppShell>
      <div className="space-y-gutter">
        <div>
          <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
            Intelligence Output
          </div>
          <h1 className="font-display text-[24px] font-semibold text-text-primary uppercase tracking-tight">
            Reports · v1
          </h1>
          <p className="mt-2 font-mono text-[11px] text-text-tertiary max-w-2xl leading-relaxed">
            Generate and review pentest reports including agent-discovered findings.
          </p>
        </div>

        {error && (
          <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
            {error}
          </div>
        )}

        {/* Controls */}
        <section className="border border-border-subtle bg-surface-secondary p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
              Generate Report
            </span>
            <span className="material-symbols-outlined text-[18px] text-text-tertiary">summarize</span>
          </div>
          <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
                Engagement
              </span>
              <select
                value={selectedId}
                onChange={(e) => { setSelectedId(e.target.value); setDoc(null); }}
                className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
              >
                <option value="">Select an engagement</option>
                {engagements.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} — {e.scope_cidrs.join(", ")}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={onGenerate}
              disabled={generating || !selectedId}
              className="bg-primary px-4 py-2 font-display text-[11px] uppercase tracking-widest text-white hover:opacity-80 disabled:opacity-30"
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          </div>
        </section>

        {/* History */}
        {reports.length > 0 && (
          <section className="border border-border-subtle bg-surface-secondary">
            <div className="px-4 h-10 flex items-center border-b border-border-subtle">
              <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                Report History ({reports.length})
              </span>
            </div>
            <div className="divide-y divide-border-subtle/50">
              {reports.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => onLoad(r.id)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-surface-tertiary/40 transition-none"
                >
                  <div className="flex flex-col items-start gap-0.5">
                    <span className="font-mono text-[11px] text-primary uppercase">
                      {r.report_format.toUpperCase()}
                    </span>
                    <span className="font-mono text-[10px] text-text-tertiary truncate max-w-[320px]">
                      {r.id}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-text-tertiary">
                    {new Date(r.created_at).toISOString().slice(0, 19)}
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Document */}
        {doc && (
          <div className="space-y-gutter">
            {summary && (
              <section className="border border-border-subtle bg-surface-secondary p-4 space-y-3">
                <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold block">
                  Summary
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  <StatCard label="Findings" value={summary.findings_total} accent />
                  <StatCard label="Agent Findings" value={summary.agent_findings_total} accent />
                  <StatCard label="Agent Runs" value={summary.agent_runs_total} />
                  <StatCard label="Suggested" value={summary.suggested_findings_total} />
                  <StatCard label="Approved" value={summary.approved_actions} />
                  <StatCard label="Pending" value={summary.pending_approvals} warn={summary.pending_approvals > 0} />
                  <StatCard label="Validated Reqs" value={summary.validated_requests} />
                  <StatCard label="Executions" value={summary.executions_total} />
                  <StatCard label="Failed Exec" value={summary.failed_executions} warn={summary.failed_executions > 0} />
                  <StatCard label="Inv. Hosts" value={summary.inventory_hosts} />
                  <StatCard label="Inv. Services" value={summary.inventory_services} />
                </div>
              </section>
            )}

            {agentFindings.length > 0 && (
              <section className="border border-border-subtle bg-surface-secondary">
                <div className="px-4 h-10 flex items-center border-b border-border-subtle">
                  <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                    Agent-Discovered Findings ({agentFindings.length})
                  </span>
                </div>
                <div className="divide-y divide-border-subtle/50">
                  {agentFindings.map((f, i) => (
                    <FindingRow key={i} finding={f} />
                  ))}
                </div>
              </section>
            )}

            {findings.length > 0 && (
              <section className="border border-border-subtle bg-surface-secondary">
                <div className="px-4 h-10 flex items-center border-b border-border-subtle">
                  <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                    Confirmed Findings ({findings.length})
                  </span>
                </div>
                <div className="divide-y divide-border-subtle/50">
                  {findings.map((f, i) => (
                    <FindingRow key={i} finding={f} />
                  ))}
                </div>
              </section>
            )}

            <section className="border border-border-subtle bg-surface-secondary p-4">
              <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold block mb-3">
                Raw Document
              </span>
              <button
                type="button"
                onClick={() => {
                  const blob = new Blob(
                    [JSON.stringify(doc.content, null, 2)],
                    { type: "application/json" },
                  );
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `report-${doc.report.id}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-4 py-2 border border-border-subtle font-display text-[11px] uppercase tracking-widest text-text-primary hover:bg-surface-tertiary"
              >
                Export_Report_JSON
              </button>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function StatCard({
  label,
  value,
  accent,
  warn,
}: {
  label: string;
  value: number;
  accent?: boolean;
  warn?: boolean;
}) {
  return (
    <div className="border border-border-subtle bg-surface-tertiary p-3">
      <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">{label}</div>
      <div
        className={`mt-1.5 font-display text-[22px] font-bold ${
          warn ? "text-severity-critical" : accent ? "text-secondary" : "text-text-primary"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function FindingRow({ finding }: { finding: AgentFinding }) {
  const color = SEVERITY_TONE[finding.severity] ?? "text-text-secondary";
  return (
    <div className="px-4 py-3 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[12px] text-text-primary">{finding.title}</span>
        <span className={`font-mono text-[10px] uppercase tracking-widest font-bold ${color}`}>
          {finding.severity}
        </span>
      </div>
      {finding.attack_technique && (
        <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-wider">
          {finding.attack_technique}
        </div>
      )}
      <p className="font-mono text-[11px] text-text-secondary leading-relaxed">{finding.summary}</p>
      {finding.evidence_refs?.length > 0 && (
        <p className="font-mono text-[10px] text-text-tertiary">
          Evidence: {finding.evidence_refs.join(", ")}
        </p>
      )}
      {finding.agent_run_id && (
        <p className="font-mono text-[10px] text-text-tertiary">
          Run: {finding.agent_run_id.split("-")[0]}
        </p>
      )}
    </div>
  );
}
