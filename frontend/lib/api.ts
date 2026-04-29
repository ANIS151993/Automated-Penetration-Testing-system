const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

type ApiErrorPayload = {
  detail?: string;
  error?: string;
};

export type HealthResponse = {
  status: string;
  environment: string;
  allowed_network: string;
  weapon_node_url: string;
  database_status: string;
  ollama_status: string;
  ollama_models: string[];
};

export type EngagementStatus = "draft" | "active" | "paused" | "aborted" | "archived";

export type Engagement = {
  id: string;
  name: string;
  description: string | null;
  scope_cidrs: string[];
  authorization_confirmed: boolean;
  authorizer_name: string;
  operator_name: string;
  status: EngagementStatus;
  created_at: string;
  updated_at: string;
};

export type Approval = {
  id: string;
  engagement_id: string;
  requested_action: string;
  risk_level: string;
  requested_by: string;
  approved: boolean;
  approved_by: string | null;
  decision_reason: string | null;
  tool_name: string;
  operation_name: string;
  args: Record<string, string>;
  created_at: string;
  decided_at: string | null;
  agent_run_id: string | null;
};

export type FindingSeverity = "info" | "low" | "medium" | "high" | "critical";

export type Finding = {
  id: string;
  engagement_id: string;
  title: string;
  severity: FindingSeverity;
  attack_technique: string | null;
  summary: string;
  evidence: string[];
  evidence_refs: string[];
  reported_by: string;
  created_at: string;
};

export type FindingSuggestion = {
  suggestion_id: string;
  execution_id: string;
  invocation_id: string;
  title: string;
  severity: FindingSeverity;
  attack_technique: string | null;
  summary: string;
  evidence: string[];
  evidence_refs: string[];
};

export type AuditEvent = {
  event_type: string;
  engagement_id: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  evidence_hash: string;
  occurred_at: string;
  actor: string | null;
};

export type ToolValidationResponse = {
  invocation_id: string | null;
  status: string;
  tool: string;
  operation: string;
  risk_level: string;
  command_preview: string[];
  targets: string[];
};

export type ToolInvocation = {
  id: string;
  engagement_id: string;
  tool_name: string;
  operation_name: string;
  risk_level: string;
  args: Record<string, string>;
  command_preview: string[];
  targets: string[];
  created_at: string;
};

export type ExecutionEvent = {
  type: string;
  timestamp: string;
  execution_id?: string;
  status?: string;
  line?: string;
  error?: string;
  exit_code?: number;
  stdout_lines?: number;
  stderr_lines?: number;
  timeout_seconds?: number;
  tool?: string;
  operation?: string;
  targets?: string[];
  command_preview?: string[];
};

export type ToolExecution = {
  id: string;
  engagement_id: string;
  invocation_id: string;
  tool_name: string;
  operation_name: string;
  status: string;
  exit_code: number | null;
  stdout_lines: number;
  stderr_lines: number;
  artifact_path: string | null;
  started_at: string;
  completed_at: string | null;
};

export type ToolExecutionArtifact = {
  execution: ToolExecution;
  content: Record<string, unknown>;
};

export type ToolExecutionCancelResponse = {
  execution_id: string;
  status: string;
  detail: string;
};

export type ParsedFingerprint = {
  target: string;
  running?: string | null;
  os_details?: string | null;
  device_type?: string | null;
  cpe?: string[];
  operation?: string;
  last_observed_at?: string | null;
};

export type ParsedWebObservation = {
  url: string;
  status_line?: string | null;
  status_code?: number | null;
  headers: Record<string, string>;
  server?: string | null;
  x_powered_by?: string | null;
  missing_security_headers?: string[];
  operation?: string;
  last_observed_at?: string | null;
};

export type ParsedDiagnostic = {
  target?: string | null;
  port?: number | null;
  kind: string;
  code: string;
  summary: string;
  detail: string;
  tool_name?: string | null;
  operation_name?: string | null;
  operation?: string | null;
  last_observed_at?: string | null;
};

export type ParsedExecutionContent = {
  hosts?: InventoryHost[];
  services?: InventoryService[];
  web?: ParsedWebObservation[];
  fingerprints?: ParsedFingerprint[];
  suggested_findings?: FindingSuggestion[];
  diagnostics?: ParsedDiagnostic[];
};

export type InventoryHost = {
  target: string;
  operations: string[];
  last_validated_at: string;
  os_guess: string | null;
};

export type InventoryService = {
  target: string;
  port: number;
  protocol: string;
  operations: string[];
  last_validated_at: string;
  service_name: string | null;
  details: string | null;
};

export type Inventory = {
  hosts: InventoryHost[];
  services: InventoryService[];
};

export type Report = {
  id: string;
  engagement_id: string;
  report_format: string;
  artifact_path: string;
  created_at: string;
};

export type ReportDocument = {
  report: Report;
  content: Record<string, unknown>;
};

export type EngagementCreatePayload = {
  name: string;
  description: string;
  scope_cidrs: string[];
  authorization_confirmed: boolean;
  authorizer_name: string;
  operator_name: string;
};

export type ApprovalCreatePayload = {
  requested_action: string;
  requested_by: string;
  tool_name: string;
  operation_name: string;
  args: Record<string, string>;
};

export type ApprovalDecisionPayload = {
  approved: boolean;
  approved_by: string;
  decision_reason: string;
};

export type FindingCreatePayload = {
  title: string;
  severity: FindingSeverity;
  attack_technique: string;
  summary: string;
  evidence: string[];
  evidence_refs: string[];
  reported_by: string;
};

export type ToolInvocationPayload = {
  tool_name: string;
  operation_name: string;
  args: Record<string, string>;
};

export type ReportCreatePayload = {
  report_format?: "json";
};

function handleUnauthorized() {
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`/login?next=${next}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("not_authenticated");
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      detail = payload.detail ?? payload.error ?? detail;
    } catch {
      // Ignore non-JSON errors and keep the fallback message.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
};

export type LoginResponse = {
  user: AuthUser;
  expires_at: string;
};

export function login(email: string, password: string) {
  return request<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout() {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

export type KnowledgeIngestResponse = {
  source_path: string;
  chunks_written: number;
  skipped: boolean;
};

export type KnowledgeHit = {
  source_path: string;
  title: string;
  content: string;
  score: number;
};

export type KnowledgeSearchResponse = {
  query: string;
  hits: KnowledgeHit[];
};

export function ingestKnowledgeSource(
  filename: string,
  content: string,
  metadata?: Record<string, unknown>,
) {
  return request<KnowledgeIngestResponse>("/api/v1/knowledge/sources", {
    method: "POST",
    body: JSON.stringify({ filename, content, metadata }),
  });
}

export type KnowledgeSource = {
  source_path: string;
  source_kind: string;
  embedding_model: string;
  chunk_count: number;
  updated_at: string | null;
};

export function listKnowledgeSources() {
  return request<KnowledgeSource[]>("/api/v1/knowledge/sources");
}

export function deleteKnowledgeSource(sourcePath: string) {
  const params = new URLSearchParams({ source_path: sourcePath });
  return request<{ source_path: string; chunks_deleted: number }>(
    `/api/v1/knowledge/sources?${params.toString()}`,
    { method: "DELETE" },
  );
}

export function searchKnowledge(query: string, topK = 5, minScore = 0) {
  const params = new URLSearchParams({
    q: query,
    top_k: String(topK),
    min_score: String(minScore),
  });
  return request<KnowledgeSearchResponse>(
    `/api/v1/knowledge/search?${params.toString()}`,
  );
}

export function getCurrentUser() {
  return request<AuthUser>("/api/v1/auth/me");
}

export function listUsers() {
  return request<AuthUser[]>("/api/v1/auth/users");
}

export function createUser(payload: {
  email: string;
  password: string;
  display_name: string;
  role: string;
}) {
  return request<AuthUser>("/api/v1/auth/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function setUserPassword(userId: string, newPassword: string) {
  return request<void>(`/api/v1/auth/users/${userId}/password`, {
    method: "PATCH",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export function setUserActive(userId: string, active: boolean) {
  return request<AuthUser>(`/api/v1/auth/users/${userId}/active`, {
    method: "PATCH",
    body: JSON.stringify({ active }),
  });
}

export function getHealth() {
  return request<HealthResponse>("/api/v1/healthz");
}

export function listEngagements() {
  return request<Engagement[]>("/api/v1/engagements");
}

export type AgentPlannedStep = {
  tool_name: string;
  operation_name: string;
  args: Record<string, unknown>;
  reason: string;
  phase: string;
  citations: string[];
};

export type AgentStepResult = {
  tool_name: string;
  operation_name: string;
  args: Record<string, unknown>;
  status: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  invocation_id: string | null;
  execution_id: string | null;
  error: string | null;
};

export type AgentFinding = {
  title: string;
  severity: FindingSeverity;
  attack_technique: string;
  summary: string;
  evidence_refs: string[];
  citations: string[];
};

export type AgentRunResponse = {
  id: string;
  engagement_id: string;
  operator_goal: string;
  created_at: string;
  intent: string;
  current_phase: string;
  planned_steps: AgentPlannedStep[];
  step_results: AgentStepResult[];
  executed_step_ids: string[];
  findings: AgentFinding[];
  errors: string[];
};

export type AgentRunSummary = {
  id: string;
  engagement_id: string;
  operator_goal: string;
  intent: string;
  current_phase: string;
  created_at: string;
  planned_steps_count: number;
  step_results_count: number;
  findings_count: number;
  errors_count: number;
};

export function listAgentRuns(engagementId: string) {
  return request<AgentRunSummary[]>(
    `/api/v1/engagements/${engagementId}/agent-runs`,
  );
}

export function getAgentRun(runId: string) {
  return request<AgentRunResponse>(`/api/v1/agent-runs/${runId}`);
}

export function runAgent(engagementId: string, operatorGoal: string) {
  return request<AgentRunResponse>(
    `/api/v1/engagements/${engagementId}/agent-runs`,
    {
      method: "POST",
      body: JSON.stringify({ operator_goal: operatorGoal }),
    },
  );
}

export function createEngagement(payload: EngagementCreatePayload) {
  return request<Engagement>("/api/v1/engagements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateEngagementStatus(engagementId: string, status: EngagementStatus) {
  return request<Engagement>(`/api/v1/engagements/${engagementId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function listApprovals(
  engagementId: string,
  options?: { status?: "pending" | "decided" },
) {
  const qs = options?.status ? `?status=${options.status}` : "";
  return request<Approval[]>(
    `/api/v1/engagements/${engagementId}/approvals${qs}`,
  );
}

export function createApproval(
  engagementId: string,
  payload: ApprovalCreatePayload,
) {
  return request<Approval>(`/api/v1/engagements/${engagementId}/approvals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listFindings(engagementId: string) {
  return request<Finding[]>(`/api/v1/engagements/${engagementId}/findings`);
}

export function listFindingSuggestions(engagementId: string) {
  return request<FindingSuggestion[]>(
    `/api/v1/engagements/${engagementId}/finding-suggestions`,
  );
}

export function createFinding(
  engagementId: string,
  payload: FindingCreatePayload,
) {
  return request<Finding>(`/api/v1/engagements/${engagementId}/findings`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAuditEvents(engagementId: string) {
  return request<AuditEvent[]>(`/api/v1/engagements/${engagementId}/audit-events`);
}

export function listToolInvocations(engagementId: string) {
  return request<ToolInvocation[]>(`/api/v1/engagements/${engagementId}/tool-invocations`);
}

export function listToolExecutions(engagementId: string) {
  return request<ToolExecution[]>(`/api/v1/engagements/${engagementId}/tool-executions`);
}

export function getToolExecutionArtifact(engagementId: string, executionId: string) {
  return request<ToolExecutionArtifact>(
    `/api/v1/engagements/${engagementId}/tool-executions/${executionId}`,
  );
}

export function cancelToolExecution(engagementId: string, executionId: string) {
  return request<ToolExecutionCancelResponse>(
    `/api/v1/engagements/${engagementId}/tool-executions/${executionId}/cancel`,
    {
      method: "POST",
    },
  );
}

export function getInventory(engagementId: string) {
  return request<Inventory>(`/api/v1/engagements/${engagementId}/inventory`);
}

export function listReports(engagementId: string) {
  return request<Report[]>(`/api/v1/engagements/${engagementId}/reports`);
}

export function generateReport(
  engagementId: string,
  payload: ReportCreatePayload = { report_format: "json" },
) {
  return request<Report>(`/api/v1/engagements/${engagementId}/reports`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getReportDocument(reportId: string) {
  return request<ReportDocument>(`/api/v1/reports/${reportId}`);
}

export function decideApproval(
  approvalId: string,
  payload: ApprovalDecisionPayload,
) {
  return request<Approval>(`/api/v1/approvals/${approvalId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function validateToolInvocation(
  engagementId: string,
  payload: ToolInvocationPayload,
) {
  return request<ToolValidationResponse>(
    `/api/v1/engagements/${engagementId}/tool-validations`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export type ExecutionStreamTicket = {
  ticket: string;
  engagement_id: string;
  execution_id: string;
  expires_in_seconds: number;
};

export function issueExecutionStreamTicket(engagementId: string, executionId: string) {
  return request<ExecutionStreamTicket>(
    `/api/v1/engagements/${engagementId}/tool-executions/${executionId}/stream-ticket`,
    { method: "POST" },
  );
}

export type WsStreamHandle = { close: () => void };

export async function openExecutionStreamWS(
  engagementId: string,
  executionId: string,
  onEvent: (event: ExecutionEvent) => void,
  onClose?: (info: { reason: string; clean: boolean }) => void,
): Promise<WsStreamHandle> {
  const { ticket } = await issueExecutionStreamTicket(engagementId, executionId);
  const httpBase = apiBaseUrl || (typeof window !== "undefined" ? window.location.origin : "");
  const wsBase = httpBase.replace(/^http/i, "ws");
  const url = `${wsBase}/api/v1/ws/engagements/${engagementId}/tool-executions/${executionId}/stream?ticket=${encodeURIComponent(
    ticket,
  )}`;
  const socket = new WebSocket(url);
  socket.addEventListener("message", (evt) => {
    try {
      onEvent(JSON.parse(evt.data) as ExecutionEvent);
    } catch {
      /* non-JSON frame — ignore */
    }
  });
  socket.addEventListener("close", (evt) => {
    onClose?.({ reason: evt.reason || "", clean: evt.wasClean });
  });
  return {
    close: () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, "client-closed");
      }
    },
  };
}

export async function streamToolExecution(
  engagementId: string,
  invocationId: string,
  onEvent: (event: ExecutionEvent) => void,
) {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/engagements/${engagementId}/tool-invocations/${invocationId}/execute-stream`,
    {
      method: "POST",
      cache: "no-store",
      credentials: "include",
    },
  );

  if (response.status === 401) {
    handleUnauthorized();
    throw new Error("not_authenticated");
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      detail = payload.detail ?? payload.error ?? detail;
    } catch {
      // Ignore non-JSON errors and keep the fallback message.
    }
    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error("Execution stream is not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line) {
        continue;
      }
      onEvent(JSON.parse(line) as ExecutionEvent);
    }
  }

  const tail = buffer.trim();
  if (tail) {
    onEvent(JSON.parse(tail) as ExecutionEvent);
  }
}
