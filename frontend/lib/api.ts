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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

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

  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>("/api/v1/healthz");
}

export function listEngagements() {
  return request<Engagement[]>("/api/v1/engagements");
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

export function listApprovals(engagementId: string) {
  return request<Approval[]>(`/api/v1/engagements/${engagementId}/approvals`);
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
    },
  );

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
