"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  AgentRunResponse,
  AgentRunSummary,
  Approval,
  Engagement,
  decideApproval,
  getAgentRun,
  listAgentRuns,
  listApprovals,
  listEngagements,
  runAgent,
} from "@/lib/api";

const SEVERITY_TONE: Record<string, string> = {
  critical: "text-severity-critical",
  high: "text-severity-high",
  medium: "text-severity-medium",
  low: "text-primary",
  info: "text-text-tertiary",
};

export default function AgentRunPage() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [goal, setGoal] = useState<string>("");
  const [running, setRunning] = useState<boolean>(false);
  const [result, setResult] = useState<AgentRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<AgentRunSummary[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [decidedApprovals, setDecidedApprovals] = useState<Approval[]>([]);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);
  const resultRef = useRef<HTMLElement>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listEngagements();
      setEngagements(list);
      if (!selectedId && list.length > 0) {
        setSelectedId(list[0].id);
      }
    } catch (err) {
      setError(String(err));
    }
  }, [selectedId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const refreshHistory = useCallback(async (engagementId: string) => {
    if (!engagementId) {
      setHistory([]);
      return;
    }
    try {
      const items = await listAgentRuns(engagementId);
      setHistory(items);
    } catch (err) {
      setError(String(err));
    }
  }, []);

  const refreshApprovals = useCallback(async (engagementId: string) => {
    if (!engagementId) {
      setApprovals([]);
      setDecidedApprovals([]);
      return;
    }
    try {
      const [pending, decided] = await Promise.all([
        listApprovals(engagementId, { status: "pending" }),
        listApprovals(engagementId, { status: "decided" }),
      ]);
      setApprovals(
        pending.filter((a) => a.requested_action.startsWith("exploit-prep:")),
      );
      setDecidedApprovals(
        decided
          .filter((a) => a.requested_action.startsWith("exploit-prep:"))
          .sort(
            (a, b) =>
              new Date(b.decided_at ?? 0).getTime() -
              new Date(a.decided_at ?? 0).getTime(),
          )
          .slice(0, 5),
      );
    } catch (err) {
      setError(String(err));
    }
  }, []);

  useEffect(() => {
    refreshHistory(selectedId);
    refreshApprovals(selectedId);
  }, [selectedId, refreshHistory, refreshApprovals]);

  const onRun = useCallback(async () => {
    if (!selectedId || !goal.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data = await runAgent(selectedId, goal.trim());
      setResult(data);
      await refreshHistory(selectedId);
      await refreshApprovals(selectedId);
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  }, [selectedId, goal, refreshHistory, refreshApprovals]);

  const onLoadHistory = useCallback(async (runId: string) => {
    setError(null);
    try {
      const data = await getAgentRun(runId);
      setResult(data);
      setTimeout(
        () => resultRef.current?.scrollIntoView({ behavior: "smooth" }),
        50,
      );
    } catch (err) {
      setError(String(err));
    }
  }, []);

  const pollRun = useCallback(
    (runId: string, prevCount: number, attemptsLeft: number) => {
      if (attemptsLeft <= 0) {
        setPollingRunId(null);
        return;
      }
      pollTimer.current = setTimeout(async () => {
        try {
          const fresh = await getAgentRun(runId);
          setResult(fresh);
          if (fresh.step_results.length > prevCount) {
            setPollingRunId(null);
            return;
          }
        } catch {
          // ignore poll errors
        }
        pollRun(runId, prevCount, attemptsLeft - 1);
      }, 2500);
    },
    [],
  );

  useEffect(() => () => { if (pollTimer.current) clearTimeout(pollTimer.current); }, []);

  const onDecide = useCallback(
    async (approvalId: string, approved: boolean) => {
      const engagement = engagements.find((e) => e.id === selectedId);
      const operator = engagement?.operator_name ?? "operator";
      setDecidingId(approvalId);
      setError(null);
      try {
        const a = approvals.find((x) => x.id === approvalId);
        await decideApproval(approvalId, {
          approved,
          approved_by: operator,
          decision_reason: approved ? "approved via agent run page" : "denied via agent run page",
        });
        await refreshApprovals(selectedId);
        if (approved && a?.agent_run_id) {
          const runId = a.agent_run_id;
          const prevCount = result?.step_results.length ?? 0;
          setPollingRunId(runId);
          if (result?.id !== runId) {
            await onLoadHistory(runId);
          }
          pollRun(runId, prevCount, 8);
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setDecidingId(null);
      }
    },
    [engagements, selectedId, approvals, result, refreshApprovals, onLoadHistory, pollRun],
  );

  return (
    <AppShell>
      <div className="space-y-gutter">
        <div>
          <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
            Autonomous Recon
          </div>
          <h1 className="font-display text-[24px] font-semibold text-text-primary uppercase tracking-tight">
            Agent Run · v1
          </h1>
          <p className="mt-2 font-mono text-[11px] text-text-tertiary max-w-2xl leading-relaxed">
            Drive the recon + enumeration pipeline against a selected engagement.
            Steps are scoped to authorized CIDRs and routed through the gateway.
          </p>
        </div>

        {error && (
          <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
            {error}
          </div>
        )}

        {/* Launch panel */}
        <section className="border border-border-subtle bg-surface-secondary p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
              Mission Parameters
            </span>
            <span className="material-symbols-outlined text-[18px] text-text-tertiary">smart_toy</span>
          </div>

          <div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
              Engagement
            </span>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
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

          <div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
              Operator Goal
            </span>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={3}
              placeholder="e.g. Find open services on 172.20.32.59"
              className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary resize-none"
            />
          </div>

          <button
            type="button"
            onClick={onRun}
            disabled={running || !selectedId || !goal.trim()}
            className="bg-secondary px-5 py-2 font-display text-[11px] uppercase tracking-widest text-bg-primary font-bold hover:opacity-80 disabled:opacity-30"
          >
            {running ? "Executing…" : "▶ Run Agent"}
          </button>
        </section>

        {/* Run history */}
        {history.length > 0 && (
          <section className="border border-border-subtle bg-surface-secondary">
            <div className="px-4 h-10 flex items-center border-b border-border-subtle">
              <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                Run History ({history.length})
              </span>
            </div>
            <div className="divide-y divide-border-subtle/50 max-h-[30vh] overflow-y-auto custom-scrollbar">
              {history.map((h) => (
                <button
                  key={h.id}
                  type="button"
                  onClick={() => onLoadHistory(h.id)}
                  className="w-full px-4 py-3 flex flex-col gap-1 text-left hover:bg-surface-tertiary/40 transition-none"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-primary uppercase">
                      {h.intent || "—"} · {h.current_phase}
                    </span>
                    <span className="font-mono text-[10px] text-text-tertiary">
                      {new Date(h.created_at).toISOString().slice(0, 19)}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-text-secondary truncate">
                    {h.operator_goal}
                  </span>
                  <span className="font-mono text-[10px] text-text-tertiary">
                    {h.planned_steps_count} steps · {h.step_results_count} results · {h.findings_count} findings
                    {h.errors_count > 0 && (
                      <span className="text-severity-critical"> · {h.errors_count} errors</span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Pending approvals */}
        {approvals.length > 0 && (
          <section className="border border-severity-medium/50 bg-severity-medium/5">
            <div className="px-4 h-10 flex items-center justify-between border-b border-severity-medium/30">
              <span className="font-display text-[11px] uppercase tracking-widest text-severity-medium font-semibold">
                Awaiting Approval ({approvals.length})
              </span>
              <span className="material-symbols-outlined text-[18px] text-severity-medium">warning</span>
            </div>
            <p className="px-4 py-2 font-mono text-[10px] text-text-tertiary">
              Gated exploit-prep steps require operator sign-off before execution.
            </p>
            <div className="divide-y divide-border-subtle/50">
              {approvals.map((a) => (
                <div key={a.id} className="px-4 py-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[12px] text-primary">
                      {a.tool_name}.{a.operation_name}
                    </span>
                    <span className="font-mono text-[10px] uppercase font-bold text-severity-medium">
                      {a.risk_level}
                    </span>
                  </div>
                  <div className="font-mono text-[10px] text-text-tertiary">
                    {a.requested_action} · requested by {a.requested_by}
                  </div>
                  <pre className="bg-bg-primary border border-border-subtle p-2 font-mono text-[11px] text-text-secondary overflow-x-auto">
                    {JSON.stringify(a.args, null, 2)}
                  </pre>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => onDecide(a.id, true)}
                      disabled={decidingId === a.id}
                      className="bg-secondary px-3 py-1.5 font-display text-[10px] uppercase tracking-widest text-bg-primary font-bold hover:opacity-80 disabled:opacity-30"
                    >
                      {decidingId === a.id ? "Saving…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onDecide(a.id, false)}
                      disabled={decidingId === a.id}
                      className="border border-severity-critical/50 px-3 py-1.5 font-display text-[10px] uppercase tracking-widest text-severity-critical hover:bg-severity-critical/10 disabled:opacity-30"
                    >
                      Deny
                    </button>
                    {a.agent_run_id && (
                      <button
                        type="button"
                        onClick={() => onLoadHistory(a.agent_run_id!)}
                        className="ml-auto font-mono text-[10px] text-text-tertiary hover:text-primary uppercase tracking-wider"
                      >
                        View Run →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Recent decisions */}
        {decidedApprovals.length > 0 && (
          <section className="border border-border-subtle bg-surface-secondary">
            <div className="px-4 h-10 flex items-center border-b border-border-subtle">
              <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                Recent Decisions ({decidedApprovals.length})
              </span>
            </div>
            <div className="divide-y divide-border-subtle/50">
              {decidedApprovals.map((a) => (
                <div key={a.id} className="px-4 py-3 flex items-start justify-between gap-4">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono text-[11px] text-primary">
                      {a.tool_name}.{a.operation_name}
                    </span>
                    <span className="font-mono text-[10px] text-text-tertiary">
                      by {a.approved_by ?? "—"} · {a.decided_at ? new Date(a.decided_at).toISOString().slice(0, 19) : "—"}
                    </span>
                    {a.decision_reason && (
                      <span className="font-mono text-[10px] text-text-secondary">{a.decision_reason}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`font-mono text-[10px] uppercase font-bold ${a.approved ? "text-secondary" : "text-severity-critical"}`}>
                      {a.approved ? "approved" : "denied"}
                    </span>
                    {a.agent_run_id && (
                      <button
                        type="button"
                        onClick={() => onLoadHistory(a.agent_run_id!)}
                        className="font-mono text-[10px] text-text-tertiary hover:text-primary uppercase tracking-wider"
                      >
                        View →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Result */}
        {result && (
          <section ref={resultRef} className="space-y-gutter">
            {/* Outcome header */}
            <div className="border border-border-subtle bg-surface-secondary p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                  Outcome
                </span>
                {pollingRunId === result.id && (
                  <div className="flex items-center gap-2 font-mono text-[10px] text-severity-medium">
                    <span className="w-1.5 h-1.5 bg-severity-medium animate-pulse" />
                    Waiting for execution…
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest block">Intent</span>
                  <span className="font-mono text-[12px] text-text-primary">{result.intent}</span>
                </div>
                <div>
                  <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest block">Phase</span>
                  <span className="font-mono text-[12px] text-text-primary">{result.current_phase}</span>
                </div>
              </div>
              {result.errors.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {result.errors.map((msg, i) => (
                    <li key={i} className="font-mono text-[11px] text-severity-critical">▸ {msg}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Planned steps */}
            <div className="border border-border-subtle bg-surface-secondary">
              <div className="px-4 h-10 flex items-center border-b border-border-subtle">
                <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                  Planned Steps ({result.planned_steps.length})
                </span>
              </div>
              <div className="divide-y divide-border-subtle/50">
                {result.planned_steps.map((step, i) => (
                  <div key={i} className="px-4 py-3 space-y-1.5">
                    <span className="font-mono text-[12px] text-primary">
                      {step.tool_name}.{step.operation_name}
                    </span>
                    <p className="font-mono text-[11px] text-text-secondary">{step.reason}</p>
                    <pre className="bg-bg-primary border border-border-subtle p-2 font-mono text-[11px] text-text-secondary overflow-x-auto">
                      {JSON.stringify(step.args, null, 2)}
                    </pre>
                    {step.citations.length > 0 && (
                      <p className="font-mono text-[10px] text-text-tertiary">
                        Citations: {step.citations.join(", ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Step results */}
            <div className="border border-border-subtle bg-surface-secondary">
              <div className="px-4 h-10 flex items-center border-b border-border-subtle">
                <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                  Step Results ({result.step_results.length})
                </span>
              </div>
              <div className="divide-y divide-border-subtle/50">
                {result.step_results.map((r, i) => (
                  <div key={i} className="px-4 py-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[12px] text-primary">
                        {r.tool_name}.{r.operation_name}
                      </span>
                      <span className={`font-mono text-[10px] uppercase font-bold ${r.status === "completed" ? "text-secondary" : "text-severity-critical"}`}>
                        {r.status}{r.exit_code !== null ? ` (exit ${r.exit_code})` : ""}
                      </span>
                    </div>
                    {r.stdout && (
                      <pre className="bg-bg-primary border border-border-subtle p-2 font-mono text-[11px] text-text-secondary max-h-48 overflow-auto custom-scrollbar">
                        {r.stdout}
                      </pre>
                    )}
                    {r.stderr && (
                      <pre className="bg-bg-primary border border-severity-critical/30 p-2 font-mono text-[11px] text-severity-critical max-h-32 overflow-auto custom-scrollbar">
                        {r.stderr}
                      </pre>
                    )}
                    {r.error && (
                      <p className="font-mono text-[11px] text-severity-critical">{r.error}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Findings */}
            {result.findings.length > 0 && (
              <div className="border border-border-subtle bg-surface-secondary">
                <div className="px-4 h-10 flex items-center border-b border-border-subtle">
                  <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                    Findings ({result.findings.length})
                  </span>
                </div>
                <div className="divide-y divide-border-subtle/50">
                  {result.findings.map((f, i) => (
                    <div key={i} className="px-4 py-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[12px] text-text-primary">{f.title}</span>
                        <span className={`font-mono text-[10px] uppercase font-bold ${SEVERITY_TONE[f.severity] ?? "text-text-secondary"}`}>
                          {f.severity}
                        </span>
                      </div>
                      {f.attack_technique && (
                        <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-wider">
                          {f.attack_technique}
                        </div>
                      )}
                      <p className="font-mono text-[11px] text-text-secondary leading-relaxed">{f.summary}</p>
                      <p className="font-mono text-[10px] text-text-tertiary">
                        Evidence: {f.evidence_refs.join(", ")}
                      </p>
                      {f.citations.length > 0 && (
                        <p className="font-mono text-[10px] text-text-tertiary">
                          Citations: {f.citations.join(", ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}
