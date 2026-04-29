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
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <header>
          <h1 className="text-2xl font-semibold text-white">Agent run</h1>
          <p className="mt-1 text-sm text-white/60">
            Drive the recon + enumeration pipeline against a selected
            engagement. Steps are scoped to the engagement&apos;s authorized
            CIDRs and routed through the gateway.
          </p>
        </header>

        <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
          <label className="block text-xs uppercase tracking-[0.3em] text-white/48">
            Engagement
          </label>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="mt-2 w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
          >
            <option value="">Select an engagement</option>
            {engagements.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} — {e.scope_cidrs.join(", ")}
              </option>
            ))}
          </select>

          <label className="mt-4 block text-xs uppercase tracking-[0.3em] text-white/48">
            Operator goal
          </label>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            rows={3}
            placeholder="e.g. Find open services on 172.20.32.59"
            className="mt-2 w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
          />

          <button
            type="button"
            onClick={onRun}
            disabled={running || !selectedId || !goal.trim()}
            className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-50"
          >
            {running ? "Running…" : "Run agent"}
          </button>

          {error ? (
            <p className="mt-3 text-sm text-rose-400">{error}</p>
          ) : null}
        </section>

        {history.length > 0 ? (
          <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
              Run history ({history.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {history.map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    onClick={() => onLoadHistory(h.id)}
                    className="w-full rounded-md border border-white/10 bg-black/30 p-3 text-left text-sm text-white/80 transition hover:border-accent/60 hover:bg-black/40"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-accent">
                        {h.intent || "—"} · {h.current_phase}
                      </span>
                      <span className="text-xs text-white/48">
                        {new Date(h.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-1 truncate text-white/80">
                      {h.operator_goal}
                    </div>
                    <div className="mt-1 text-xs text-white/48">
                      {h.planned_steps_count} steps · {h.step_results_count}{" "}
                      results · {h.findings_count} findings
                      {h.errors_count > 0 ? (
                        <span className="text-rose-400">
                          {" "}
                          · {h.errors_count} errors
                        </span>
                      ) : null}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {approvals.length > 0 ? (
          <section className="rounded-[24px] border border-amber-400/40 bg-amber-500/5 p-5 shadow-panel">
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-200">
              Awaiting approval ({approvals.length})
            </h2>
            <p className="mt-1 text-xs text-white/60">
              Gated exploit-prep steps require operator sign-off before execution.
            </p>
            <ul className="mt-3 space-y-3">
              {approvals.map((a) => (
                <li
                  key={a.id}
                  className="rounded-md border border-white/10 bg-black/30 p-3 text-sm text-white/80"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-accent">
                      {a.tool_name}.{a.operation_name}
                    </span>
                    <span className="font-mono text-xs uppercase text-amber-300">
                      {a.risk_level}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-white/60">
                    {a.requested_action} · requested by {a.requested_by}
                  </div>
                  <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-2 text-xs text-white/70">
                    {JSON.stringify(a.args, null, 2)}
                  </pre>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => onDecide(a.id, true)}
                      disabled={decidingId === a.id}
                      className="rounded-md bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-black disabled:opacity-50"
                    >
                      {decidingId === a.id ? "Saving…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onDecide(a.id, false)}
                      disabled={decidingId === a.id}
                      className="rounded-md border border-rose-400/60 px-3 py-1.5 text-xs font-semibold text-rose-300 disabled:opacity-50"
                    >
                      Deny
                    </button>
                    {a.agent_run_id ? (
                      <button
                        type="button"
                        onClick={() => onLoadHistory(a.agent_run_id!)}
                        className="ml-auto rounded-md border border-white/10 px-3 py-1.5 text-xs text-white/60 hover:border-accent/60 hover:text-accent"
                      >
                        View run →
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {decidedApprovals.length > 0 ? (
          <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
              Recent decisions ({decidedApprovals.length})
            </h2>
            <ul className="mt-3 space-y-2">
              {decidedApprovals.map((a) => (
                <li
                  key={a.id}
                  className="rounded-md border border-white/10 bg-black/30 p-3 text-sm text-white/80"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-accent">
                      {a.tool_name}.{a.operation_name}
                    </span>
                    <span
                      className={
                        a.approved
                          ? "font-mono text-xs uppercase text-emerald-400"
                          : "font-mono text-xs uppercase text-rose-400"
                      }
                    >
                      {a.approved ? "approved" : "denied"}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-white/48">
                    by {a.approved_by ?? "—"} ·{" "}
                    {a.decided_at
                      ? new Date(a.decided_at).toLocaleString()
                      : "—"}
                  </div>
                  {a.decision_reason ? (
                    <div className="mt-1 text-xs text-white/60">
                      {a.decision_reason}
                    </div>
                  ) : null}
                  {a.agent_run_id ? (
                    <button
                      type="button"
                      onClick={() => onLoadHistory(a.agent_run_id!)}
                      className="mt-2 text-xs text-white/48 hover:text-accent"
                    >
                      View run →
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {result ? (
          <section ref={resultRef} className="space-y-5">
            <div className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
              <div className="flex items-center justify-between">
                <p className="text-xs uppercase tracking-[0.3em] text-white/48">
                  Outcome
                </p>
                {pollingRunId === result.id ? (
                  <span className="flex items-center gap-1.5 text-xs text-amber-300">
                    <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-300" />
                    Waiting for execution…
                  </span>
                ) : null}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-4 text-sm text-white/80">
                <div>
                  <span className="text-white/48">Intent:</span> {result.intent}
                </div>
                <div>
                  <span className="text-white/48">Phase:</span>{" "}
                  {result.current_phase}
                </div>
              </div>
              {result.errors.length > 0 ? (
                <ul className="mt-3 list-disc pl-5 text-sm text-rose-400">
                  {result.errors.map((msg, i) => (
                    <li key={i}>{msg}</li>
                  ))}
                </ul>
              ) : null}
            </div>

            <div className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                Planned steps ({result.planned_steps.length})
              </h2>
              <ul className="mt-3 space-y-3">
                {result.planned_steps.map((step, i) => (
                  <li
                    key={i}
                    className="rounded-md border border-white/10 bg-black/30 p-3 text-sm text-white/80"
                  >
                    <div className="font-mono text-accent">
                      {step.tool_name}.{step.operation_name}
                    </div>
                    <div className="mt-1 text-white/60">{step.reason}</div>
                    <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-2 text-xs text-white/70">
                      {JSON.stringify(step.args, null, 2)}
                    </pre>
                    {step.citations.length > 0 ? (
                      <p className="mt-2 text-xs text-white/48">
                        Citations: {step.citations.join(", ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                Step results ({result.step_results.length})
              </h2>
              <ul className="mt-3 space-y-3">
                {result.step_results.map((r, i) => (
                  <li
                    key={i}
                    className="rounded-md border border-white/10 bg-black/30 p-3 text-sm text-white/80"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-accent">
                        {r.tool_name}.{r.operation_name}
                      </span>
                      <span
                        className={
                          r.status === "completed"
                            ? "text-emerald-400"
                            : "text-rose-400"
                        }
                      >
                        {r.status}
                        {r.exit_code !== null ? ` (exit ${r.exit_code})` : ""}
                      </span>
                    </div>
                    {r.stdout ? (
                      <pre className="mt-2 max-h-48 overflow-auto rounded bg-black/40 p-2 text-xs text-white/70">
                        {r.stdout}
                      </pre>
                    ) : null}
                    {r.stderr ? (
                      <pre className="mt-2 max-h-32 overflow-auto rounded bg-black/40 p-2 text-xs text-rose-300">
                        {r.stderr}
                      </pre>
                    ) : null}
                    {r.error ? (
                      <p className="mt-2 text-xs text-rose-400">{r.error}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
            {result.findings.length > 0 ? (
              <div className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72">
                  Findings ({result.findings.length})
                </h2>
                <ul className="mt-3 space-y-3">
                  {result.findings.map((f, i) => (
                    <li
                      key={i}
                      className="rounded-md border border-white/10 bg-black/30 p-3 text-sm text-white/80"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white">{f.title}</span>
                        <span className="font-mono text-xs uppercase text-accent">
                          {f.severity}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-white/60">
                        {f.attack_technique}
                      </div>
                      <p className="mt-2 text-sm text-white/80">{f.summary}</p>
                      <p className="mt-2 text-xs text-white/48">
                        Evidence: {f.evidence_refs.join(", ")}
                      </p>
                      {f.citations.length > 0 ? (
                        <p className="mt-1 text-xs text-white/48">
                          Citations: {f.citations.join(", ")}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
