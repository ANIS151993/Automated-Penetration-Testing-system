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

const SEVERITY_COLOR: Record<string, string> = {
  critical: "text-rose-400",
  high: "text-orange-400",
  medium: "text-amber-300",
  low: "text-blue-400",
  info: "text-white/48",
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
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <header>
          <h1 className="text-2xl font-semibold text-white">Reports</h1>
          <p className="mt-1 text-sm text-white/60">
            Generate and review pentest reports including agent-discovered findings.
          </p>
        </header>

        {/* Controls */}
        <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
          <label className="block text-xs uppercase tracking-[0.3em] text-white/48">
            Engagement
          </label>
          <select
            value={selectedId}
            onChange={(e) => { setSelectedId(e.target.value); setDoc(null); }}
            className="mt-2 w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
          >
            <option value="">Select an engagement</option>
            {engagements.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} — {e.scope_cidrs.join(", ")}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating || !selectedId}
            className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate report"}
          </button>
          {error ? <p className="mt-3 text-sm text-rose-400">{error}</p> : null}
        </section>

        {/* History */}
        {reports.length > 0 ? (
          <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
              Report history ({reports.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {reports.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => onLoad(r.id)}
                    className="w-full rounded-md border border-white/10 bg-black/30 p-3 text-left text-sm transition hover:border-accent/60 hover:bg-black/40"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-accent">
                        {r.report_format.toUpperCase()}
                      </span>
                      <span className="text-xs text-white/48">
                        {new Date(r.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-1 truncate font-mono text-xs text-white/40">
                      {r.id}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* Document */}
        {doc ? (
          <div className="space-y-5">
            {/* Summary */}
            {summary ? (
              <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                  Summary
                </h2>
                <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                  <Stat label="Confirmed Findings" value={summary.findings_total} accent />
                  <Stat label="Agent Findings" value={summary.agent_findings_total} accent />
                  <Stat label="Agent Runs" value={summary.agent_runs_total} />
                  <Stat label="Suggested Findings" value={summary.suggested_findings_total} />
                  <Stat label="Approved Actions" value={summary.approved_actions} />
                  <Stat label="Pending Approvals" value={summary.pending_approvals} warn={summary.pending_approvals > 0} />
                  <Stat label="Validated Requests" value={summary.validated_requests} />
                  <Stat label="Executions" value={summary.executions_total} />
                  <Stat label="Failed Executions" value={summary.failed_executions} warn={summary.failed_executions > 0} />
                  <Stat label="Inventory Hosts" value={summary.inventory_hosts} />
                  <Stat label="Inventory Services" value={summary.inventory_services} />
                </div>
              </section>
            ) : null}

            {/* Agent Findings */}
            {agentFindings.length > 0 ? (
              <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                  Agent-discovered findings ({agentFindings.length})
                </h2>
                <ul className="mt-3 space-y-3">
                  {agentFindings.map((f, i) => (
                    <FindingCard key={i} finding={f} />
                  ))}
                </ul>
              </section>
            ) : null}

            {/* Confirmed Findings */}
            {findings.length > 0 ? (
              <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                  Confirmed findings ({findings.length})
                </h2>
                <ul className="mt-3 space-y-3">
                  {findings.map((f, i) => (
                    <FindingCard key={i} finding={f} />
                  ))}
                </ul>
              </section>
            ) : null}

            {/* Raw JSON download */}
            <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                Raw document
              </h2>
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
                className="mt-3 rounded-md border border-white/10 px-4 py-2 text-sm text-white/80 hover:border-accent/60 hover:text-accent"
              >
                Download JSON
              </button>
            </section>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}

function Stat({
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
    <div className="rounded-md border border-white/10 bg-black/30 p-3">
      <div className="text-xs text-white/48">{label}</div>
      <div
        className={`mt-1 text-xl font-semibold ${
          warn ? "text-rose-400" : accent ? "text-accent" : "text-white"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function FindingCard({ finding }: { finding: AgentFinding }) {
  const color = SEVERITY_COLOR[finding.severity] ?? "text-white/60";
  return (
    <li className="rounded-md border border-white/10 bg-black/30 p-3 text-sm text-white/80">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-white">{finding.title}</span>
        <span className={`font-mono text-xs uppercase ${color}`}>
          {finding.severity}
        </span>
      </div>
      {finding.attack_technique ? (
        <div className="mt-1 text-xs text-white/48">{finding.attack_technique}</div>
      ) : null}
      <p className="mt-2 text-sm text-white/80">{finding.summary}</p>
      {finding.evidence_refs?.length > 0 ? (
        <p className="mt-2 text-xs text-white/40">
          Evidence: {finding.evidence_refs.join(", ")}
        </p>
      ) : null}
      {finding.agent_run_id ? (
        <p className="mt-1 text-xs text-white/40">
          Run: {finding.agent_run_id.split("-")[0]}
        </p>
      ) : null}
    </li>
  );
}
