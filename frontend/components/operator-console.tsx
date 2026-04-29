"use client";

import { FormEvent, useCallback, useEffect, useRef, useState, useTransition } from "react";

import {
  Approval,
  AuditEvent,
  cancelToolExecution,
  Engagement,
  EngagementStatus,
  ExecutionEvent,
  Finding,
  FindingSuggestion,
  FindingSeverity,
  HealthResponse,
  Inventory,
  Report,
  ReportDocument,
  ParsedExecutionContent,
  ParsedDiagnostic,
  ParsedFingerprint,
  ParsedWebObservation,
  ToolExecution,
  ToolExecutionArtifact,
  ToolInvocation,
  ToolValidationResponse,
  createApproval,
  createEngagement,
  createFinding,
  decideApproval,
  generateReport,
  getInventory,
  getHealth,
  getReportDocument,
  getToolExecutionArtifact,
  listApprovals,
  listAuditEvents,
  listEngagements,
  listFindings,
  listFindingSuggestions,
  listReports,
  listToolExecutions,
  listToolInvocations,
  streamToolExecution,
  updateEngagementStatus,
  validateToolInvocation,
} from "@/lib/api";
import dynamic from "next/dynamic";

const LiveTerminal = dynamic(
  () => import("./live-terminal").then((mod) => mod.LiveTerminal),
  { ssr: false },
);

type OperationOption = {
  label: string;
  toolName: string;
  operationName: string;
  riskLevel: "low" | "high";
  requiresApproval: boolean;
  argumentKind: "target" | "url";
  help: string;
};

const operationOptions: OperationOption[] = [
  {
    label: "Nmap Service Scan",
    toolName: "nmap",
    operationName: "service_scan",
    riskLevel: "low",
    requiresApproval: false,
    argumentKind: "target",
    help: "Low-risk validation path for scoped TCP service enumeration.",
  },
  {
    label: "HTTP Header Fetch",
    toolName: "http_probe",
    operationName: "fetch_headers",
    riskLevel: "low",
    requiresApproval: false,
    argumentKind: "url",
    help: "Low-risk header probe for a scoped HTTP endpoint.",
  },
  {
    label: "Nmap OS Detection",
    toolName: "nmap",
    operationName: "os_detection",
    riskLevel: "high",
    requiresApproval: true,
    argumentKind: "target",
    help: "High-risk path. The backend will block this until a matching approval exists.",
  },
];

const engagementStatuses: EngagementStatus[] = [
  "draft",
  "active",
  "paused",
  "aborted",
  "archived",
];

const findingSeverities: FindingSeverity[] = [
  "info",
  "low",
  "medium",
  "high",
  "critical",
];

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Pending";
  }
  return new Date(value).toLocaleString();
}

function formatOperationLabel(toolName: string, operationName: string) {
  return `${toolName}.${operationName}`;
}

function formatEventLabel(eventType: string) {
  return eventType.replaceAll("_", " ");
}

function truncateHash(value: string) {
  return `${value.slice(0, 10)}...${value.slice(-8)}`;
}

function previewPayload(payload: Record<string, unknown>) {
  const serialized = JSON.stringify(payload);
  if (serialized.length <= 160) {
    return serialized;
  }
  return `${serialized.slice(0, 157)}...`;
}

function previewJson(value: unknown) {
  const serialized = JSON.stringify(value);
  if (serialized.length <= 240) {
    return serialized;
  }
  return `${serialized.slice(0, 237)}...`;
}

function getParsedExecutionContent(
  artifact: ToolExecutionArtifact | null,
): ParsedExecutionContent | null {
  const parsed = artifact?.content.parsed;
  if (!parsed || typeof parsed !== "object") {
    return null;
  }
  return parsed as ParsedExecutionContent;
}

function getParsedWebObservations(
  artifact: ToolExecutionArtifact | null,
): ParsedWebObservation[] {
  const parsed = getParsedExecutionContent(artifact);
  return Array.isArray(parsed?.web) ? parsed.web : [];
}

function getParsedFingerprints(
  artifact: ToolExecutionArtifact | null,
): ParsedFingerprint[] {
  const parsed = getParsedExecutionContent(artifact);
  return Array.isArray(parsed?.fingerprints) ? parsed.fingerprints : [];
}

function getParsedDiagnostics(
  artifact: ToolExecutionArtifact | null,
): ParsedDiagnostic[] {
  const parsed = getParsedExecutionContent(artifact);
  return Array.isArray(parsed?.diagnostics) ? parsed.diagnostics : [];
}

function pillClassName(tone: "accent" | "caution" | "danger" | "neutral") {
  if (tone === "accent") {
    return "border border-accent/30 bg-accent/10 text-accent";
  }
  if (tone === "caution") {
    return "border border-caution/30 bg-caution/10 text-caution";
  }
  if (tone === "danger") {
    return "border border-danger/30 bg-danger/10 text-danger";
  }
  return "border border-white/10 bg-white/5 text-white/72";
}

function severityTone(severity: FindingSeverity) {
  if (severity === "critical" || severity === "high") {
    return "danger";
  }
  if (severity === "medium") {
    return "caution";
  }
  if (severity === "low" || severity === "info") {
    return "accent";
  }
  return "neutral";
}

function executionTone(status: string) {
  if (status === "completed") {
    return "accent";
  }
  if (status === "cancelled") {
    return "caution";
  }
  if (status === "timed_out" || status === "failed") {
    return "danger";
  }
  if (status === "running") {
    return "caution";
  }
  return "neutral";
}

function isTerminalExecutionEvent(event: ExecutionEvent) {
  return ["completed", "failed", "cancelled", "timed_out"].includes(event.type);
}

function diagnosticTone(kind: string) {
  if (kind === "connectivity") {
    return "danger";
  }
  if (kind === "permissions") {
    return "caution";
  }
  return "neutral";
}

export function OperatorConsole() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedEngagementId, setSelectedEngagementId] = useState<string>("");
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingSuggestions, setFindingSuggestions] = useState<FindingSuggestion[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [toolInvocations, setToolInvocations] = useState<ToolInvocation[]>([]);
  const [toolExecutions, setToolExecutions] = useState<ToolExecution[]>([]);
  const [selectedExecutionArtifact, setSelectedExecutionArtifact] =
    useState<ToolExecutionArtifact | null>(null);
  const [inventory, setInventory] = useState<Inventory>({ hosts: [], services: [] });
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportDocument | null>(null);
  const [validationResult, setValidationResult] = useState<ToolValidationResponse | null>(null);
  const [executionEvents, setExecutionEvents] = useState<ExecutionEvent[]>([]);
  const [executionInvocationId, setExecutionInvocationId] = useState<string | null>(null);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [cancellingExecutionId, setCancellingExecutionId] = useState<string | null>(null);
  const [notice, setNotice] = useState("Loading operator console state...");
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const selectedExecutionIdRef = useRef<string | null>(null);

  const [engagementForm, setEngagementForm] = useState({
    name: "Target Node Engagement",
    description: "Scoped engagement for the intentionally vulnerable target node.",
    scopeCidr: "172.20.32.59/32",
    authorizerName: "Lab Owner",
    operatorName: "Analyst One",
    authorizationConfirmed: true,
  });
  const [toolForm, setToolForm] = useState({
    operationKey: "nmap.service_scan",
    target: "172.20.32.59",
    ports: "22",
    url: "http://172.20.32.59",
  });
  const [approvalForm, setApprovalForm] = useState({
    requestedAction: "Run OS detection against the target node",
    requestedBy: "Analyst One",
    approvedBy: "Lab Owner",
    decisionReason: "Approved for scoped lab validation.",
  });
  const [findingForm, setFindingForm] = useState({
    title: "Open SSH service",
    severity: "medium" as FindingSeverity,
    attackTechnique: "T1046",
    summary: "The target exposes SSH within the authorized scope and should be tracked as supporting evidence.",
    evidenceText: "nmap -Pn -sV -p 22 172.20.32.59\nOpenSSH banner captured",
    evidenceRefs: [] as string[],
    reportedBy: "Analyst One",
  });

  const selectedEngagement =
    engagements.find((engagement) => engagement.id === selectedEngagementId) ?? null;
  const selectedOperation =
    operationOptions.find(
      (operation) =>
        `${operation.toolName}.${operation.operationName}` === toolForm.operationKey,
    ) ?? operationOptions[0];

  useEffect(() => {
    void refreshDashboard();
  }, []);

  async function refreshDashboard(preferredEngagementId?: string) {
    try {
      const [healthResponse, engagementResponse] = await Promise.all([
        getHealth(),
        listEngagements(),
      ]);

      startTransition(() => {
        setHealth(healthResponse);
        setEngagements(engagementResponse);
        setSelectedEngagementId((current) => {
          if (preferredEngagementId && engagementResponse.some((item) => item.id === preferredEngagementId)) {
            return preferredEngagementId;
          }
          if (current && engagementResponse.some((item) => item.id === current)) {
            return current;
          }
          return engagementResponse[0]?.id ?? "";
        });
        setNotice(
          engagementResponse.length
            ? `Loaded ${engagementResponse.length} engagement records from the backend.`
            : "No engagements yet. Create one to begin a scoped operation.",
        );
        setError(null);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh dashboard state.");
    }
  }

  const refreshEngagementDetails = useCallback(async (engagementId: string) => {
    try {
      const [
        approvalResponse,
        findingResponse,
        findingSuggestionResponse,
        auditResponse,
        toolInvocationResponse,
        toolExecutionResponse,
        inventoryResponse,
        reportResponse,
      ] = await Promise.all([
        listApprovals(engagementId),
        listFindings(engagementId),
        listFindingSuggestions(engagementId),
        listAuditEvents(engagementId),
        listToolInvocations(engagementId),
        listToolExecutions(engagementId),
        getInventory(engagementId),
        listReports(engagementId),
      ]);

      startTransition(() => {
        setApprovals(approvalResponse);
        setFindings(findingResponse);
        setFindingSuggestions(findingSuggestionResponse);
        setAuditEvents(auditResponse);
        setToolInvocations(toolInvocationResponse);
        setToolExecutions(toolExecutionResponse);
        setInventory(inventoryResponse);
        setReports(reportResponse);
      });

      const currentExecutionId = selectedExecutionIdRef.current;
      const preferredExecutionId = currentExecutionId ?? toolExecutionResponse[0]?.id;
      if (preferredExecutionId) {
        const artifact = await getToolExecutionArtifact(engagementId, preferredExecutionId);
        selectedExecutionIdRef.current = artifact.execution.id;
        startTransition(() => {
          setSelectedExecutionArtifact(artifact);
        });
      } else {
        selectedExecutionIdRef.current = null;
        startTransition(() => {
          setSelectedExecutionArtifact(null);
        });
      }

      if (reportResponse.length > 0) {
        const latest = await getReportDocument(reportResponse[0].id);
        startTransition(() => {
          setSelectedReport(latest);
        });
      } else {
        startTransition(() => {
          setSelectedReport(null);
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh engagement details.");
    }
  }, []);

  useEffect(() => {
    if (!selectedEngagementId) {
      setApprovals([]);
      setFindings([]);
      setFindingSuggestions([]);
      setAuditEvents([]);
      setToolInvocations([]);
      setToolExecutions([]);
      setSelectedExecutionArtifact(null);
      setInventory({ hosts: [], services: [] });
      setReports([]);
      setSelectedReport(null);
      setExecutionEvents([]);
      setExecutionInvocationId(null);
      selectedExecutionIdRef.current = null;
      return;
    }

    void refreshEngagementDetails(selectedEngagementId);
  }, [selectedEngagementId, refreshEngagementDetails]);

  function buildArgs(): Record<string, string> {
    if (selectedOperation.argumentKind === "url") {
      return {
        url: toolForm.url.trim(),
      };
    }

    return {
      target: toolForm.target.trim(),
      ports: toolForm.ports.trim(),
    };
  }

  function buildEvidence(): string[] {
    return findingForm.evidenceText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function toggleEvidenceRef(invocationId: string) {
    setFindingForm((current) => ({
      ...current,
      evidenceRefs: current.evidenceRefs.includes(invocationId)
        ? current.evidenceRefs.filter((item) => item !== invocationId)
        : [...current.evidenceRefs, invocationId],
    }));
  }

  function handleApplyFindingSuggestion(suggestion: FindingSuggestion) {
    setFindingForm((current) => ({
      ...current,
      title: suggestion.title,
      severity: suggestion.severity,
      attackTechnique: suggestion.attack_technique ?? "",
      summary: suggestion.summary,
      evidenceText: suggestion.evidence.join("\n"),
      evidenceRefs: Array.from(
        new Set([...suggestion.evidence_refs, ...current.evidenceRefs]),
      ),
    }));
    setNotice(`Loaded parser-derived suggestion into the finding form: ${suggestion.title}.`);
    setError(null);
  }

  async function handleGenerateReport() {
    if (!selectedEngagement) {
      setError("Select an engagement before generating a report.");
      return;
    }

    setBusyAction("generate-report");
    try {
      const created = await generateReport(selectedEngagement.id, { report_format: "json" });
      const document = await getReportDocument(created.id);
      await refreshEngagementDetails(selectedEngagement.id);
      setSelectedReport(document);
      setNotice(`Generated ${created.report_format} report artifact for ${selectedEngagement.name}.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSelectReport(reportId: string) {
    setBusyAction(`report-${reportId}`);
    try {
      const document = await getReportDocument(reportId);
      setSelectedReport(document);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleExecuteInvocation(invocationId: string) {
    if (!selectedEngagement) {
      setError("Select an engagement before executing a validated request.");
      return;
    }

    setBusyAction(`execute-${invocationId}`);
    setExecutionInvocationId(invocationId);
    setActiveExecutionId(null);
    setExecutionEvents([]);

    try {
      await streamToolExecution(selectedEngagement.id, invocationId, (event) => {
        if (event.execution_id) {
          setActiveExecutionId(event.execution_id);
        }
        if (isTerminalExecutionEvent(event)) {
          setActiveExecutionId(null);
          setCancellingExecutionId(null);
        }
        setExecutionEvents((current) => [...current, event]);
      });
      await refreshEngagementDetails(selectedEngagement.id);
      setNotice("Execution stream completed and the engagement state was refreshed.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute the validated request.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCancelExecution(executionId: string) {
    if (!selectedEngagement) {
      setError("Select an engagement before cancelling an execution.");
      return;
    }

    setCancellingExecutionId(executionId);
    try {
      const result = await cancelToolExecution(selectedEngagement.id, executionId);
      setNotice(result.detail);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to request execution cancellation.");
    } finally {
      setCancellingExecutionId(null);
    }
  }

  async function handleSelectExecution(executionId: string) {
    if (!selectedEngagement) {
      setError("Select an engagement before loading execution evidence.");
      return;
    }

    setBusyAction(`execution-artifact-${executionId}`);
    try {
      const artifact = await getToolExecutionArtifact(selectedEngagement.id, executionId);
      selectedExecutionIdRef.current = artifact.execution.id;
      setSelectedExecutionArtifact(artifact);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load execution evidence.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateEngagement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("create-engagement");
    try {
      const created = await createEngagement({
        name: engagementForm.name.trim(),
        description: engagementForm.description.trim(),
        scope_cidrs: [engagementForm.scopeCidr.trim()],
        authorization_confirmed: engagementForm.authorizationConfirmed,
        authorizer_name: engagementForm.authorizerName.trim(),
        operator_name: engagementForm.operatorName.trim(),
      });

      await refreshDashboard(created.id);
      setNotice(`Created engagement ${created.name} and selected it in the console.`);
      setValidationResult(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create engagement.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleStatusUpdate(status: EngagementStatus) {
    if (!selectedEngagement) {
      setError("Select an engagement before changing status.");
      return;
    }

    setBusyAction(`status-${status}`);
    try {
      const updated = await updateEngagementStatus(selectedEngagement.id, status);
      await refreshDashboard(updated.id);
      setNotice(`Updated ${updated.name} to ${updated.status}.`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update engagement status.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateApproval() {
    if (!selectedEngagement) {
      setError("Select an engagement before requesting approval.");
      return;
    }

    setBusyAction("create-approval");
    try {
      const created = await createApproval(selectedEngagement.id, {
        requested_action: approvalForm.requestedAction.trim(),
        requested_by: approvalForm.requestedBy.trim(),
        tool_name: selectedOperation.toolName,
        operation_name: selectedOperation.operationName,
        args: buildArgs(),
      });

      await refreshEngagementDetails(selectedEngagement.id);
      setNotice(
        `Created ${created.risk_level} risk approval request for ${formatOperationLabel(
          created.tool_name,
          created.operation_name,
        )}.`,
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create approval.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleApprovalDecision(approvalId: string, approved: boolean) {
    setBusyAction(`approval-${approvalId}`);
    try {
      await decideApproval(approvalId, {
        approved,
        approved_by: approvalForm.approvedBy.trim(),
        decision_reason: approvalForm.decisionReason.trim(),
      });

      if (selectedEngagement) {
        await refreshEngagementDetails(selectedEngagement.id);
      }
      setNotice(approved ? "Approval granted." : "Approval denied.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to decide approval.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleValidate() {
    if (!selectedEngagement) {
      setError("Select an engagement before validating a tool request.");
      return;
    }

    setBusyAction("validate-tool");
    try {
      const result = await validateToolInvocation(selectedEngagement.id, {
        tool_name: selectedOperation.toolName,
        operation_name: selectedOperation.operationName,
        args: buildArgs(),
      });

      setValidationResult(result);
      if (result.invocation_id) {
        const invocationId = result.invocation_id;
        setFindingForm((current) => ({
          ...current,
          evidenceRefs: current.evidenceRefs.includes(invocationId)
            ? current.evidenceRefs
            : [invocationId, ...current.evidenceRefs],
        }));
        setExecutionInvocationId(invocationId);
      }
      setNotice(
        `Validated ${formatOperationLabel(result.tool, result.operation)} against the remote gateway.`,
      );
      setError(null);
      await refreshEngagementDetails(selectedEngagement.id);
    } catch (err) {
      setValidationResult(null);
      setError(err instanceof Error ? err.message : "Failed to validate the tool request.");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateFinding() {
    if (!selectedEngagement) {
      setError("Select an engagement before recording a finding.");
      return;
    }

    setBusyAction("create-finding");
    try {
      const created = await createFinding(selectedEngagement.id, {
        title: findingForm.title.trim(),
        severity: findingForm.severity,
        attack_technique: findingForm.attackTechnique.trim(),
        summary: findingForm.summary.trim(),
        evidence: buildEvidence(),
        evidence_refs: findingForm.evidenceRefs,
        reported_by: findingForm.reportedBy.trim(),
      });

      await refreshEngagementDetails(selectedEngagement.id);
      setNotice(`Recorded finding ${created.title} and appended it to the audit timeline.`);
      setFindingForm((current) => ({ ...current, evidenceRefs: [] }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create finding.");
    } finally {
      setBusyAction(null);
    }
  }

  const interactionsDisabled = busyAction !== null || isPending;

  return (
    <div className="text-text-primary">
      <section className="flex flex-col gap-8">
        <header className="grid gap-6 rounded-[28px] border border-white/10 bg-white/5 p-6 shadow-panel backdrop-blur md:grid-cols-[1.3fr_0.7fr]">
          <div className="space-y-5">
            <p className="text-sm uppercase tracking-[0.35em] text-accent/90">
              Command Node 172.20.32.74
            </p>
            <div className="space-y-3">
              <h1 className="max-w-3xl text-4xl font-semibold leading-tight md:text-6xl">
                Operator workflows are now live against the real gateway path.
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-white/72 md:text-base">
                Create scoped engagements, approve high-risk actions, validate tool
                invocations, and capture findings with a matching audit timeline in one console.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs uppercase tracking-[0.28em] text-white/62">
              <span className={`rounded-full px-4 py-2 font-mono ${pillClassName("accent")}`}>
                Three-layer scope enforcement
              </span>
              <span className={`rounded-full px-4 py-2 font-mono ${pillClassName("caution")}`}>
                Human approval for high-risk actions
              </span>
              <span className={`rounded-full px-4 py-2 font-mono ${pillClassName("neutral")}`}>
                Findings and audit evidence aligned
              </span>
            </div>
          </div>

          <div className="rounded-[24px] border border-accent/30 bg-accent/10 p-5">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent">
              Platform State
            </p>
            <div className="mt-5 grid gap-3 text-sm">
              <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                <div className="text-white/54">API Status</div>
                <div className="mt-1 font-mono text-accent">{health?.status ?? "loading"}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                <div className="text-white/54">Allowed Network</div>
                <div className="mt-1 font-mono">{health?.allowed_network ?? "..."}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                <div className="text-white/54">Weapon Node</div>
                <div className="mt-1 font-mono break-all">
                  {health?.weapon_node_url ?? "loading"}
                </div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                <div className="text-white/54">Database</div>
                <div className="mt-1 font-mono text-caution">
                  {health?.database_status ?? "checking"}
                </div>
              </div>
            </div>
          </div>
        </header>

        <section className="grid gap-4 xl:grid-cols-6">
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Engagements</p>
            <div className="mt-4 text-3xl font-semibold text-accent">{engagements.length}</div>
            <p className="mt-3 text-sm leading-7 text-white/72">Current records in scope.</p>
          </article>
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Pending Approvals</p>
            <div className="mt-4 text-3xl font-semibold text-caution">
              {approvals.filter((approval) => !approval.approved).length}
            </div>
            <p className="mt-3 text-sm leading-7 text-white/72">Requests awaiting a decision.</p>
          </article>
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Approved</p>
            <div className="mt-4 text-3xl font-semibold text-accent">
              {approvals.filter((approval) => approval.approved).length}
            </div>
            <p className="mt-3 text-sm leading-7 text-white/72">High-risk approvals on file.</p>
          </article>
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Findings</p>
            <div className="mt-4 text-3xl font-semibold text-caution">{findings.length}</div>
            <p className="mt-3 text-sm leading-7 text-white/72">Captured evidence records.</p>
          </article>
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Audit Events</p>
            <div className="mt-4 text-3xl font-semibold text-accent">{auditEvents.length}</div>
            <p className="mt-3 text-sm leading-7 text-white/72">Tamper-evident timeline entries.</p>
          </article>
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Reports</p>
            <div className="mt-4 text-3xl font-semibold text-caution">{reports.length}</div>
            <p className="mt-3 text-sm leading-7 text-white/72">Generated engagement artifacts.</p>
          </article>
          <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
            <p className="text-xs uppercase tracking-[0.3em] text-white/48">Last Validation</p>
            <div className="mt-4 text-2xl font-semibold text-accent">
              {validationResult ? validationResult.operation : "none"}
            </div>
            <p className="mt-3 text-sm leading-7 text-white/72">Latest gateway-confirmed request.</p>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-accent">Engagement Control</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Define explicit scope before the operator can ask the backend to validate or record anything.
                </p>
              </div>
              <button
                className="rounded-full border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.28em] text-white/72 transition hover:border-accent/40 hover:text-accent"
                onClick={() => void refreshDashboard(selectedEngagementId)}
                type="button"
              >
                Refresh
              </button>
            </div>

            <form className="mt-6 grid gap-4" onSubmit={handleCreateEngagement}>
              <label className="grid gap-2 text-sm text-white/76">
                Engagement Name
                <input
                  className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) => setEngagementForm((current) => ({ ...current, name: event.target.value }))}
                  value={engagementForm.name}
                />
              </label>
              <label className="grid gap-2 text-sm text-white/76">
                Description
                <textarea
                  className="min-h-24 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) =>
                    setEngagementForm((current) => ({ ...current, description: event.target.value }))
                  }
                  value={engagementForm.description}
                />
              </label>
              <div className="grid gap-4 md:grid-cols-3">
                <label className="grid gap-2 text-sm text-white/76">
                  Scope CIDR
                  <input
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                    onChange={(event) => setEngagementForm((current) => ({ ...current, scopeCidr: event.target.value }))}
                    value={engagementForm.scopeCidr}
                  />
                </label>
                <label className="grid gap-2 text-sm text-white/76">
                  Authorizer
                  <input
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                    onChange={(event) => setEngagementForm((current) => ({ ...current, authorizerName: event.target.value }))}
                    value={engagementForm.authorizerName}
                  />
                </label>
                <label className="grid gap-2 text-sm text-white/76">
                  Operator
                  <input
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                    onChange={(event) => setEngagementForm((current) => ({ ...current, operatorName: event.target.value }))}
                    value={engagementForm.operatorName}
                  />
                </label>
              </div>
              <label className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/15 px-4 py-3 text-sm text-white/76">
                <input
                  checked={engagementForm.authorizationConfirmed}
                  className="h-4 w-4 accent-accent"
                  onChange={(event) =>
                    setEngagementForm((current) => ({
                      ...current,
                      authorizationConfirmed: event.target.checked,
                    }))
                  }
                  type="checkbox"
                />
                Authorization confirmed for the explicit scope above.
              </label>
              <button
                className="rounded-2xl bg-accent px-5 py-3 text-sm font-semibold text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={interactionsDisabled}
                type="submit"
              >
                {busyAction === "create-engagement" ? "Creating..." : "Create Engagement"}
              </button>
            </form>

            <div className="mt-6 grid gap-3">
              {engagements.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No engagement records yet.
                </div>
              ) : (
                engagements.map((engagement) => (
                  <button
                    className={`rounded-2xl border px-4 py-4 text-left transition ${
                      engagement.id === selectedEngagementId
                        ? "border-accent/40 bg-accent/10"
                        : "border-white/10 bg-black/15 hover:border-white/20"
                    }`}
                    key={engagement.id}
                    onClick={() => setSelectedEngagementId(engagement.id)}
                    type="button"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-white">{engagement.name}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.24em] text-white/48">
                          {engagement.scope_cidrs.join(", ")}
                        </div>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${
                          engagement.status === "active"
                            ? pillClassName("accent")
                            : engagement.status === "archived" || engagement.status === "aborted"
                              ? pillClassName("danger")
                              : pillClassName("neutral")
                        }`}
                      >
                        {engagement.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-7 text-white/72">
                      {engagement.description ?? "No description provided."}
                    </p>
                  </button>
                ))
              )}
            </div>
          </article>

          <div className="grid gap-6">
            <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-[0.3em] text-caution">Selected Engagement</p>
                  <h2 className="mt-2 text-2xl font-semibold">
                    {selectedEngagement?.name ?? "Choose an engagement"}
                  </h2>
                </div>
                {selectedEngagement ? (
                  <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                    {selectedEngagement.id}
                  </span>
                ) : null}
              </div>

              {selectedEngagement ? (
                <>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-white/72">
                    {selectedEngagement.description ?? "No description provided for this engagement."}
                  </p>
                  <div className="mt-5 flex flex-wrap gap-3">
                    {engagementStatuses.map((status) => (
                      <button
                        className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.22em] transition ${
                          selectedEngagement.status === status
                            ? `${pillClassName("accent")} cursor-default`
                            : "border border-white/10 bg-black/15 text-white/70 hover:border-accent/30 hover:text-accent"
                        }`}
                        disabled={interactionsDisabled || selectedEngagement.status === status}
                        key={status}
                        onClick={() => void handleStatusUpdate(status)}
                        type="button"
                      >
                        {busyAction === `status-${status}` ? "Applying..." : status}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <p className="mt-3 text-sm leading-7 text-white/60">
                  Select an engagement to open approvals, findings, and live validation controls.
                </p>
              )}
            </article>

            <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-[0.3em] text-danger">Tool Validation</p>
                  <p className="mt-2 text-sm leading-7 text-white/72">
                    Build a typed invocation and send it through backend scope checks and the remote gateway.
                  </p>
                </div>
                <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${selectedOperation.requiresApproval ? pillClassName("danger") : pillClassName("accent")}`}>
                  {selectedOperation.riskLevel} risk
                </span>
              </div>

              <div className="mt-6 grid gap-4">
                <label className="grid gap-2 text-sm text-white/76">
                  Operation
                  <select
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                    onChange={(event) => setToolForm((current) => ({ ...current, operationKey: event.target.value }))}
                    value={toolForm.operationKey}
                  >
                    {operationOptions.map((operation) => (
                      <option key={`${operation.toolName}.${operation.operationName}`} value={`${operation.toolName}.${operation.operationName}`}>
                        {operation.label}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedOperation.argumentKind === "url" ? (
                  <label className="grid gap-2 text-sm text-white/76">
                    Target URL
                    <input
                      className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                      onChange={(event) => setToolForm((current) => ({ ...current, url: event.target.value }))}
                      value={toolForm.url}
                    />
                  </label>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="grid gap-2 text-sm text-white/76">
                      Target IP
                      <input
                        className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                        onChange={(event) => setToolForm((current) => ({ ...current, target: event.target.value }))}
                        value={toolForm.target}
                      />
                    </label>
                    <label className="grid gap-2 text-sm text-white/76">
                      Ports
                      <input
                        className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                        onChange={(event) => setToolForm((current) => ({ ...current, ports: event.target.value }))}
                        value={toolForm.ports}
                      />
                    </label>
                  </div>
                )}
                <div className="rounded-2xl border border-white/8 bg-black/15 px-4 py-3 text-sm leading-7 text-white/68">
                  {selectedOperation.help}
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    className="rounded-2xl bg-accent px-5 py-3 text-sm font-semibold text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={interactionsDisabled || !selectedEngagement}
                    onClick={() => void handleValidate()}
                    type="button"
                  >
                    {busyAction === "validate-tool" ? "Validating..." : "Validate Tool Request"}
                  </button>
                  <button
                    className="rounded-2xl border border-caution/35 bg-caution/10 px-5 py-3 text-sm font-semibold text-caution transition hover:border-caution/60 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={interactionsDisabled || !selectedEngagement || !selectedOperation.requiresApproval}
                    onClick={() => void handleCreateApproval()}
                    type="button"
                  >
                    {busyAction === "create-approval" ? "Requesting..." : "Create Matching Approval"}
                  </button>
                </div>
              </div>

              <div className="mt-6 rounded-[24px] border border-white/10 bg-black/20 p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.28em] text-white/48">Last Validation Result</p>
                    <h3 className="mt-2 text-lg font-semibold">
                      {validationResult
                        ? formatOperationLabel(validationResult.tool, validationResult.operation)
                        : "No validation yet"}
                    </h3>
                  </div>
                  {validationResult ? (
                    <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.22em] ${pillClassName("accent")}`}>
                      {validationResult.status}
                    </span>
                  ) : null}
                </div>
              {validationResult ? (
                <div className="mt-4 grid gap-3 text-sm text-white/74 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/8 bg-white/3 px-4 py-3">
                    <div className="text-white/48">Targets</div>
                    <div className="mt-2 font-mono">{validationResult.targets.join(", ")}</div>
                    </div>
                    <div className="rounded-2xl border border-white/8 bg-white/3 px-4 py-3">
                      <div className="text-white/48">Command Preview</div>
                      <div className="mt-2 font-mono break-all">
                        {validationResult.command_preview.join(" ")}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-white/8 bg-white/3 px-4 py-3 md:col-span-2">
                      <div className="text-white/48">Evidence Reference</div>
                      <div className="mt-2 font-mono break-all">
                        {validationResult.invocation_id ?? "Not persisted"}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 text-sm leading-7 text-white/58">
                    Successful validations will show the gateway-confirmed command preview here.
                  </p>
                )}
              </div>
            </article>

            <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-[0.3em] text-caution">Approvals</p>
                  <p className="mt-2 text-sm leading-7 text-white/72">
                    High-risk requests need an exact approval match before the backend will forward them.
                  </p>
                </div>
                <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                  {approvals.length} records
                </span>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <label className="grid gap-2 text-sm text-white/76">
                  Requested By
                  <input
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                    onChange={(event) => setApprovalForm((current) => ({ ...current, requestedBy: event.target.value }))}
                    value={approvalForm.requestedBy}
                  />
                </label>
                <label className="grid gap-2 text-sm text-white/76">
                  Approved By
                  <input
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                    onChange={(event) => setApprovalForm((current) => ({ ...current, approvedBy: event.target.value }))}
                    value={approvalForm.approvedBy}
                  />
                </label>
              </div>
              <label className="mt-4 grid gap-2 text-sm text-white/76">
                Requested Action
                <input
                  className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) => setApprovalForm((current) => ({ ...current, requestedAction: event.target.value }))}
                  value={approvalForm.requestedAction}
                />
              </label>
              <label className="mt-4 grid gap-2 text-sm text-white/76">
                Decision Reason
                <textarea
                  className="min-h-24 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) => setApprovalForm((current) => ({ ...current, decisionReason: event.target.value }))}
                  value={approvalForm.decisionReason}
                />
              </label>

              <div className="mt-6 grid gap-3">
                {approvals.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                    No approval records yet for the selected engagement.
                  </div>
                ) : (
                  approvals.map((approval) => (
                    <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4" key={approval.id}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-base font-semibold text-white">{approval.requested_action}</div>
                          <div className="mt-1 text-xs uppercase tracking-[0.24em] text-white/46">
                            {formatOperationLabel(approval.tool_name, approval.operation_name)}
                          </div>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${approval.approved ? pillClassName("accent") : pillClassName("caution")}`}>
                          {approval.approved ? "approved" : "pending"}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-3 text-sm text-white/72 md:grid-cols-2">
                        <div>
                          <div className="text-white/46">Requested By</div>
                          <div className="mt-1">{approval.requested_by}</div>
                        </div>
                        <div>
                          <div className="text-white/46">Created</div>
                          <div className="mt-1">{formatTimestamp(approval.created_at)}</div>
                        </div>
                        <div>
                          <div className="text-white/46">Risk</div>
                          <div className="mt-1 uppercase">{approval.risk_level}</div>
                        </div>
                        <div>
                          <div className="text-white/46">Args</div>
                          <div className="mt-1 font-mono break-all">{JSON.stringify(approval.args)}</div>
                        </div>
                      </div>
                      {approval.approved ? (
                        <div className="mt-4 rounded-2xl border border-accent/20 bg-accent/10 px-4 py-3 text-sm text-white/74">
                          Approved by {approval.approved_by ?? "unknown"} at {formatTimestamp(approval.decided_at)}.
                        </div>
                      ) : (
                        <div className="mt-4 flex flex-wrap gap-3">
                          <button
                            className="rounded-full bg-accent px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={interactionsDisabled}
                            onClick={() => void handleApprovalDecision(approval.id, true)}
                            type="button"
                          >
                            {busyAction === `approval-${approval.id}` ? "Applying..." : "Approve"}
                          </button>
                          <button
                            className="rounded-full border border-danger/35 bg-danger/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-danger transition hover:border-danger/60 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={interactionsDisabled}
                            onClick={() => void handleApprovalDecision(approval.id, false)}
                            type="button"
                          >
                            {busyAction === `approval-${approval.id}` ? "Applying..." : "Deny"}
                          </button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </article>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-accent">Derived Inventory</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Hosts, services, and banners are derived from executed evidence first, with validated requests used as fallback coverage.
                </p>
              </div>
              <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                {inventory.hosts.length} hosts / {inventory.services.length} services
              </span>
            </div>

            <div className="mt-6 grid gap-6 xl:grid-cols-2">
              <div className="grid gap-3">
                <div className="text-xs uppercase tracking-[0.24em] text-white/46">Hosts</div>
                {inventory.hosts.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                    No hosts derived yet for this engagement.
                  </div>
                ) : (
                  inventory.hosts.map((host) => (
                    <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4" key={host.target}>
                      <div className="font-mono text-sm text-white">{host.target}</div>
                      <div className="mt-2 text-xs uppercase tracking-[0.22em] text-white/44">
                        {formatTimestamp(host.last_validated_at)}
                      </div>
                      {host.os_guess ? (
                        <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-3 py-2 text-xs text-white/70">
                          OS fingerprint: {host.os_guess}
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {host.operations.map((operation) => (
                          <span
                            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/68"
                            key={`${host.target}-${operation}`}
                          >
                            {operation}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="grid gap-3">
                <div className="text-xs uppercase tracking-[0.24em] text-white/46">Services</div>
                {inventory.services.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                    No service candidates derived yet.
                  </div>
                ) : (
                  inventory.services.map((service) => (
                    <div
                      className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4"
                      key={`${service.target}-${service.port}-${service.protocol}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-mono text-sm text-white">
                          {service.target}:{service.port}/{service.protocol}
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName("accent")}`}>
                          evidence-backed
                        </span>
                      </div>
                      <div className="mt-2 text-xs uppercase tracking-[0.22em] text-white/44">
                        {formatTimestamp(service.last_validated_at)}
                      </div>
                      {service.service_name || service.details ? (
                        <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-3 py-2 text-xs text-white/70">
                          {[service.service_name, service.details].filter(Boolean).join(" • ")}
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {service.operations.map((operation) => (
                          <span
                            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/68"
                            key={`${service.target}-${service.port}-${operation}`}
                          >
                            {operation}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </article>

          <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-caution">Validated Evidence</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  These persisted validation records can be linked directly into findings as evidence references.
                </p>
              </div>
              <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                {toolInvocations.length} records
              </span>
            </div>

            <div className="mt-6 grid gap-3">
              {toolInvocations.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No validated evidence records yet for the selected engagement.
                </div>
              ) : (
                toolInvocations.map((invocation) => {
                  const selected = findingForm.evidenceRefs.includes(invocation.id);
                  return (
                    <button
                      className={`rounded-2xl border px-4 py-4 text-left transition ${
                        selected
                          ? "border-accent/40 bg-accent/10"
                          : "border-white/10 bg-black/15 hover:border-white/20"
                      }`}
                      key={invocation.id}
                      onClick={() => toggleEvidenceRef(invocation.id)}
                      type="button"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-base font-semibold text-white">
                            {formatOperationLabel(invocation.tool_name, invocation.operation_name)}
                          </div>
                          <div className="mt-1 font-mono text-xs text-white/46">
                            {invocation.targets.join(", ")}
                          </div>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName(selected ? "accent" : "neutral")}`}>
                          {selected ? "linked" : invocation.risk_level}
                        </span>
                      </div>
                      <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                        {invocation.command_preview.join(" ")}
                      </div>
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs uppercase tracking-[0.22em] text-white/44">
                        <span>{formatTimestamp(invocation.created_at)}</span>
                        <span>{invocation.id}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-danger">Live Execution</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Execute a previously validated request and stream the gateway output back into the console.
                </p>
              </div>
              <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                {executionEvents.length} events
              </span>
            </div>

            <div className="mt-6 grid gap-3">
              {toolInvocations.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  Validate a request first. Execution only runs from an existing validated invocation.
                </div>
              ) : (
                toolInvocations.map((invocation) => (
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4" key={`exec-${invocation.id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-white">
                          {formatOperationLabel(invocation.tool_name, invocation.operation_name)}
                        </div>
                        <div className="mt-1 font-mono text-xs text-white/46">
                          {invocation.targets.join(", ")}
                        </div>
                      </div>
                      <button
                        className="rounded-full bg-accent px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={interactionsDisabled}
                        onClick={() => void handleExecuteInvocation(invocation.id)}
                        type="button"
                      >
                        {busyAction === `execute-${invocation.id}` ? "Streaming..." : "Execute"}
                      </button>
                    </div>
                    <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                      {invocation.command_preview.join(" ")}
                    </div>
                    <div className="mt-3 text-xs uppercase tracking-[0.22em] text-white/44">
                      {formatTimestamp(invocation.created_at)} • {invocation.id}
                    </div>
                  </div>
                ))
              )}
            </div>
          </article>

          <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-caution">Execution Stream</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Streaming events from the weapon node are shown here as the command runs.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {executionInvocationId ? (
                  <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                    {executionInvocationId}
                  </span>
                ) : null}
                {activeExecutionId ? (
                  <button
                    className="rounded-full border border-danger/30 bg-danger/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-danger transition hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={cancellingExecutionId === activeExecutionId}
                    onClick={() => void handleCancelExecution(activeExecutionId)}
                    type="button"
                  >
                    {cancellingExecutionId === activeExecutionId ? "Cancelling..." : "Cancel Execution"}
                  </button>
                ) : null}
              </div>
            </div>

            <div className="mt-6">
              <LiveTerminal events={executionEvents} />
            </div>

            <div className="mt-6 grid gap-3">
              {executionEvents.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No live execution stream yet for this engagement.
                </div>
              ) : (
                executionEvents.map((event, index) => (
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4" key={`${event.timestamp}-${index}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm font-semibold capitalize text-white">{event.type}</div>
                      <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName(event.type === "stderr" || event.type === "failed" ? "danger" : event.type === "completed" ? "accent" : "neutral")}`}>
                        {event.status ?? "event"}
                      </span>
                    </div>
                    <div className="mt-2 text-xs uppercase tracking-[0.22em] text-white/44">
                      {formatTimestamp(event.timestamp)}
                    </div>
                    {typeof event.timeout_seconds === "number" ? (
                      <div className="mt-3 text-xs uppercase tracking-[0.22em] text-white/44">
                        timeout budget {event.timeout_seconds}s
                      </div>
                    ) : null}
                    {event.line ? (
                      <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                        {event.line}
                      </div>
                    ) : null}
                    {event.error ? (
                      <div className="mt-3 rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 font-mono text-xs leading-6 text-danger">
                        {event.error}
                      </div>
                    ) : null}
                    {typeof event.exit_code === "number" ? (
                      <div className="mt-3 text-xs uppercase tracking-[0.22em] text-white/44">
                        exit {event.exit_code} • stdout {event.stdout_lines ?? 0} • stderr {event.stderr_lines ?? 0}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-accent">Execution History</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Persisted execution runs are stored as evidence artifacts and can be reviewed after the live stream ends.
                </p>
              </div>
              <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                {toolExecutions.length} stored
              </span>
            </div>

            <div className="mt-6 grid gap-3">
              {toolExecutions.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No persisted execution evidence yet for the selected engagement.
                </div>
              ) : (
                toolExecutions.map((execution) => (
                  <button
                    className={`rounded-2xl border px-4 py-4 text-left transition ${
                      selectedExecutionArtifact?.execution.id === execution.id
                        ? "border-accent/40 bg-accent/10"
                        : "border-white/10 bg-black/15 hover:border-white/20"
                    }`}
                    key={execution.id}
                    onClick={() => void handleSelectExecution(execution.id)}
                    type="button"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-white">
                          {formatOperationLabel(execution.tool_name, execution.operation_name)}
                        </div>
                        <div className="mt-1 font-mono text-xs text-white/46">
                          invocation {execution.invocation_id}
                        </div>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName(executionTone(execution.status))}`}>
                        {execution.status}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs uppercase tracking-[0.22em] text-white/44 md:grid-cols-2">
                      <span>{formatTimestamp(execution.started_at)}</span>
                      <span>
                        exit {execution.exit_code ?? "pending"} • stdout {execution.stdout_lines} • stderr {execution.stderr_lines}
                      </span>
                    </div>
                    <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                      {execution.artifact_path ?? "Artifact will be written when execution completes."}
                    </div>
                  </button>
                ))
              )}
            </div>
          </article>

          <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-caution">Execution Artifact</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Stored execution metadata, raw output, and parser-derived observations are loaded from the backend artifact store.
                </p>
              </div>
              {selectedExecutionArtifact ? (
                <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName(executionTone(selectedExecutionArtifact.execution.status))}`}>
                  {selectedExecutionArtifact.execution.status}
                </span>
              ) : null}
            </div>

            {selectedExecutionArtifact ? (
              <div className="mt-6 grid gap-4">
                {getParsedWebObservations(selectedExecutionArtifact).length > 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">Web Observations</div>
                    <div className="mt-4 grid gap-3">
                      {getParsedWebObservations(selectedExecutionArtifact).map((item, index) => (
                        <div className="rounded-2xl border border-white/8 bg-white/3 px-4 py-4" key={`${item.url}-${index}`}>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="font-mono text-sm text-white">{item.url}</div>
                            <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName("accent")}`}>
                              {item.status_code ?? item.status_line ?? "observed"}
                            </span>
                          </div>
                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div className="rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Banner</div>
                              <div className="mt-2 font-mono">{[item.server, item.x_powered_by].filter(Boolean).join(" • ") || "none"}</div>
                            </div>
                            <div className="rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Missing Security Headers</div>
                              <div className="mt-2 font-mono">
                                {(item.missing_security_headers ?? []).length
                                  ? item.missing_security_headers?.join(", ")
                                  : "none"}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {getParsedFingerprints(selectedExecutionArtifact).length > 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">OS Fingerprints</div>
                    <div className="mt-4 grid gap-3">
                      {getParsedFingerprints(selectedExecutionArtifact).map((item, index) => (
                        <div className="rounded-2xl border border-white/8 bg-white/3 px-4 py-4" key={`${item.target}-${index}`}>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="font-mono text-sm text-white">{item.target}</div>
                            <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName("caution")}`}>
                              fingerprint
                            </span>
                          </div>
                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div className="rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Running</div>
                              <div className="mt-2 font-mono">{item.running ?? item.os_details ?? "unknown"}</div>
                            </div>
                            <div className="rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Device Type</div>
                              <div className="mt-2 font-mono">{item.device_type ?? "unknown"}</div>
                            </div>
                          </div>
                          {item.cpe && item.cpe.length > 0 ? (
                            <div className="mt-3 rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">CPE</div>
                              <div className="mt-2 font-mono">{item.cpe.join(", ")}</div>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {getParsedDiagnostics(selectedExecutionArtifact).length > 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">Execution Diagnostics</div>
                    <div className="mt-4 grid gap-3">
                      {getParsedDiagnostics(selectedExecutionArtifact).map((item, index) => (
                        <div className="rounded-2xl border border-white/8 bg-white/3 px-4 py-4" key={`${item.code}-${item.target ?? "global"}-${index}`}>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="text-sm font-semibold text-white">{item.summary}</div>
                            <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName(diagnosticTone(item.kind))}`}>
                              {item.kind}
                            </span>
                          </div>
                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div className="rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Code</div>
                              <div className="mt-2 font-mono">{item.code}</div>
                            </div>
                            <div className="rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                              <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Scope</div>
                              <div className="mt-2 font-mono">
                                {item.target
                                  ? `${item.target}${item.port ? `:${item.port}` : ""}`
                                  : item.operation ?? "execution"}
                              </div>
                            </div>
                          </div>
                          <div className="mt-3 rounded-2xl border border-white/8 bg-black/20 px-3 py-3 text-xs text-white/70">
                            <div className="text-[11px] uppercase tracking-[0.22em] text-white/44">Observed Detail</div>
                            <div className="mt-2 font-mono">{item.detail}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">Execution Summary</div>
                    <div className="mt-3 font-mono text-xs leading-6 text-white/70">
                      {previewJson({
                        execution_id: selectedExecutionArtifact.execution.id,
                        invocation_id: selectedExecutionArtifact.execution.invocation_id,
                        exit_code: selectedExecutionArtifact.execution.exit_code,
                        stdout_lines: selectedExecutionArtifact.execution.stdout_lines,
                        stderr_lines: selectedExecutionArtifact.execution.stderr_lines,
                        artifact_path: selectedExecutionArtifact.execution.artifact_path,
                      })}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">Artifact Snapshot</div>
                    <div className="mt-3 font-mono text-xs leading-6 text-white/70">
                      {previewJson(selectedExecutionArtifact.content)}
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.24em] text-white/46">Parsed Observations</div>
                  <div className="mt-3 font-mono text-xs leading-6 text-white/70">
                    {previewJson(getParsedExecutionContent(selectedExecutionArtifact) ?? {})}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                Execute a validated request, or select a stored execution from the history panel, to preview its artifact.
              </div>
            )}
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-accent">Reports</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Generate a stored engagement artifact from findings, approvals, inventory, evidence refs, and the audit chain.
                </p>
              </div>
              <button
                className="rounded-2xl bg-accent px-5 py-3 text-sm font-semibold text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={interactionsDisabled || !selectedEngagement}
                onClick={() => void handleGenerateReport()}
                type="button"
              >
                {busyAction === "generate-report" ? "Generating..." : "Generate Report"}
              </button>
            </div>

            <div className="mt-6 grid gap-3">
              {reports.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No reports generated yet for the selected engagement.
                </div>
              ) : (
                reports.map((report) => (
                  <button
                    className={`rounded-2xl border px-4 py-4 text-left transition ${
                      selectedReport?.report.id === report.id
                        ? "border-accent/40 bg-accent/10"
                        : "border-white/10 bg-black/15 hover:border-white/20"
                    }`}
                    key={report.id}
                    onClick={() => void handleSelectReport(report.id)}
                    type="button"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-white">
                          {report.report_format.toUpperCase()} report
                        </div>
                        <div className="mt-1 font-mono text-xs text-white/46">{report.id}</div>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName("neutral")}`}>
                        {formatTimestamp(report.created_at)}
                      </span>
                    </div>
                    <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                      {report.artifact_path}
                    </div>
                  </button>
                ))
              )}
            </div>
          </article>

          <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-caution">Report Preview</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Preview the generated artifact summary before handing it off or extending the report format.
                </p>
              </div>
              {selectedReport ? (
                <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("accent")}`}>
                  {selectedReport.report.report_format}
                </span>
              ) : null}
            </div>

            {selectedReport ? (
              <div className="mt-6 grid gap-4">
                <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.24em] text-white/46">Artifact Path</div>
                  <div className="mt-2 font-mono text-sm break-all text-white/76">
                    {selectedReport.report.artifact_path}
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">Summary</div>
                    <div className="mt-3 font-mono text-xs leading-6 text-white/70">
                      {previewJson(selectedReport.content.summary ?? {})}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.24em] text-white/46">Engagement Snapshot</div>
                    <div className="mt-3 font-mono text-xs leading-6 text-white/70">
                      {previewJson(selectedReport.content.engagement ?? {})}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-6 rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                Generate or select a report to preview its stored artifact content.
              </div>
            )}
          </article>
        </section>

        <section className="grid gap-6 2xl:grid-cols-[0.9fr_1.1fr]">
          <article className="rounded-[28px] border border-white/10 bg-panel/90 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-accent">Findings</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Record evidence-backed findings so the control plane and audit trail stay aligned. Parser-derived suggestions can prefill the form.
                </p>
              </div>
              <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                {findings.length} records
              </span>
            </div>

            <div className="mt-6 rounded-[24px] border border-white/10 bg-black/15 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.24em] text-white/46">Finding Suggestions</div>
                  <div className="mt-2 text-sm text-white/68">
                    Suggestions are derived from execution-artifact parsers and from agent vuln-mapper runs. They still require operator review before they become real findings.
                  </div>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName("neutral")}`}>
                  {findingSuggestions.length} suggestions
                </span>
              </div>

              <div className="mt-4 grid gap-3">
                {findingSuggestions.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 px-4 py-5 text-sm text-white/58">
                    No suggestions yet. Execute a validated request or run the agent vuln-mapper to populate this panel.
                  </div>
                ) : (
                  findingSuggestions.map((suggestion) => (
                    <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-4" key={suggestion.suggestion_id}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <div className="text-sm font-semibold text-white">{suggestion.title}</div>
                            {suggestion.suggestion_id.startsWith("agent-run:") ? (
                              <span className="rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-accent">
                                Agent
                              </span>
                            ) : (
                              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/64">
                                Parser
                              </span>
                            )}
                          </div>
                          <div className="mt-1 text-xs uppercase tracking-[0.22em] text-white/44">
                            execution {suggestion.execution_id}
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName(severityTone(suggestion.severity))}`}>
                            {suggestion.severity}
                          </span>
                          <button
                            className="rounded-full bg-accent px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={interactionsDisabled}
                            onClick={() => handleApplyFindingSuggestion(suggestion)}
                            type="button"
                          >
                            Use
                          </button>
                        </div>
                      </div>
                      <div className="mt-3 text-sm leading-7 text-white/70">{suggestion.summary}</div>
                      {suggestion.evidence.length > 0 ? (
                        <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                          {suggestion.evidence.join("\n")}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm text-white/76">
                Title
                <input
                  className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) => setFindingForm((current) => ({ ...current, title: event.target.value }))}
                  value={findingForm.title}
                />
              </label>
              <label className="grid gap-2 text-sm text-white/76">
                Severity
                <select
                  className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) =>
                    setFindingForm((current) => ({
                      ...current,
                      severity: event.target.value as FindingSeverity,
                    }))
                  }
                  value={findingForm.severity}
                >
                  {findingSeverities.map((severity) => (
                    <option key={severity} value={severity}>
                      {severity}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="grid gap-2 text-sm text-white/76">
                ATT&CK Technique
                <input
                  className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) => setFindingForm((current) => ({ ...current, attackTechnique: event.target.value }))}
                  value={findingForm.attackTechnique}
                />
              </label>
              <label className="grid gap-2 text-sm text-white/76">
                Reported By
                <input
                  className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                  onChange={(event) => setFindingForm((current) => ({ ...current, reportedBy: event.target.value }))}
                  value={findingForm.reportedBy}
                />
              </label>
            </div>

            <label className="mt-4 grid gap-2 text-sm text-white/76">
              Summary
              <textarea
                className="min-h-28 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/40"
                onChange={(event) => setFindingForm((current) => ({ ...current, summary: event.target.value }))}
                value={findingForm.summary}
              />
            </label>
            <label className="mt-4 grid gap-2 text-sm text-white/76">
              Evidence Items
              <textarea
                className="min-h-28 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 font-mono text-sm text-white outline-none transition focus:border-accent/40"
                onChange={(event) => setFindingForm((current) => ({ ...current, evidenceText: event.target.value }))}
                value={findingForm.evidenceText}
              />
            </label>
            <div className="mt-4 rounded-2xl border border-white/10 bg-black/15 px-4 py-4 text-sm text-white/74">
              <div className="text-xs uppercase tracking-[0.24em] text-white/46">
                Linked Evidence References
              </div>
              {findingForm.evidenceRefs.length === 0 ? (
                <div className="mt-2 text-white/58">
                  No persisted validation records linked yet. Select entries from the Validated Evidence panel.
                </div>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  {findingForm.evidenceRefs.map((evidenceRef) => (
                    <span
                      className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 font-mono text-xs text-accent"
                      key={evidenceRef}
                    >
                      {evidenceRef}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <button
              className="mt-4 rounded-2xl bg-accent px-5 py-3 text-sm font-semibold text-canvas transition hover:bg-[#e1ff7f] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={interactionsDisabled || !selectedEngagement}
              onClick={() => void handleCreateFinding()}
              type="button"
            >
              {busyAction === "create-finding" ? "Recording..." : "Record Finding"}
            </button>

            <div className="mt-6 grid gap-3">
              {findings.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No findings yet for the selected engagement.
                </div>
              ) : (
                findings.map((finding) => (
                  <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4" key={finding.id}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-white">{finding.title}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.24em] text-white/46">
                          {finding.attack_technique ?? "No ATT&CK mapping"}
                        </div>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName(severityTone(finding.severity))}`}>
                        {finding.severity}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-7 text-white/74">{finding.summary}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {finding.evidence.map((item, index) => (
                        <span
                          className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/68"
                          key={`${finding.id}-${index}`}
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                    {finding.evidence_refs.length > 0 ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {finding.evidence_refs.map((evidenceRef) => (
                          <span
                            className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 font-mono text-xs text-accent"
                            key={`${finding.id}-${evidenceRef}`}
                          >
                            {evidenceRef}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-4 text-xs uppercase tracking-[0.22em] text-white/44">
                      {finding.reported_by} • {formatTimestamp(finding.created_at)}
                    </div>
                  </div>
                ))
              )}
            </div>
          </article>

          <article className="rounded-[28px] border border-white/10 bg-white/5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-caution">Audit Timeline</p>
                <p className="mt-2 text-sm leading-7 text-white/72">
                  Review the tamper-evident sequence of approvals, validations, and findings for the selected engagement.
                </p>
              </div>
              <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.24em] ${pillClassName("neutral")}`}>
                {auditEvents.length} events
              </span>
            </div>

            <div className="mt-6 grid gap-3">
              {auditEvents.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/15 px-4 py-6 text-sm text-white/58">
                  No audit events yet for the selected engagement.
                </div>
              ) : (
                auditEvents
                  .slice()
                  .reverse()
                  .map((event) => (
                    <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-4" key={event.evidence_hash}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-base font-semibold capitalize text-white">
                            {formatEventLabel(event.event_type)}
                          </div>
                          <div className="mt-1 text-xs uppercase tracking-[0.24em] text-white/46">
                            {event.actor ?? "System"} • {formatTimestamp(event.occurred_at)}
                          </div>
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.22em] ${pillClassName("neutral")}`}>
                          {truncateHash(event.evidence_hash)}
                        </span>
                      </div>
                      <div className="mt-3 rounded-2xl border border-white/8 bg-white/3 px-4 py-3 font-mono text-xs leading-6 text-white/70">
                        {previewPayload(event.payload)}
                      </div>
                    </div>
                  ))
              )}
            </div>
          </article>
        </section>

        <section className="rounded-[28px] border border-white/10 bg-black/20 px-6 py-4 text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.22em] ${error ? pillClassName("danger") : pillClassName("accent")}`}>
              {error ? "Operator Error" : "Operator Status"}
            </span>
            <span className="text-white/78">{error ?? notice}</span>
          </div>
        </section>
      </section>
    </div>
  );
}
