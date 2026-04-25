"use client";

import { useState } from "react";

import {
  ExecutionEvent,
  ToolValidationResponse,
  streamToolExecution,
  validateToolInvocation,
} from "@/lib/api";

type OperationOption = {
  label: string;
  toolName: string;
  operationName: string;
  riskLevel: "low" | "high";
  requiresApproval: boolean;
  argumentKind: "target" | "url";
  help: string;
};

const OPERATION_OPTIONS: OperationOption[] = [
  {
    label: "Nmap Service Scan",
    toolName: "nmap",
    operationName: "service_scan",
    riskLevel: "low",
    requiresApproval: false,
    argumentKind: "target",
    help: "TCP service enumeration on a scoped host.",
  },
  {
    label: "HTTP Header Fetch",
    toolName: "http_probe",
    operationName: "fetch_headers",
    riskLevel: "low",
    requiresApproval: false,
    argumentKind: "url",
    help: "Probe response headers for a scoped HTTP endpoint.",
  },
  {
    label: "Nmap OS Detection",
    toolName: "nmap",
    operationName: "os_detection",
    riskLevel: "high",
    requiresApproval: true,
    argumentKind: "target",
    help: "High-risk OS fingerprinting. Requires a matching approval.",
  },
];

type ToolLaunchDrawerProps = {
  open: boolean;
  onClose: () => void;
  engagementId: string;
  onExecutionEvent: (event: ExecutionEvent) => void;
  onExecutionStart: () => void;
  onExecutionEnd: () => void;
};

function isTerminal(event: ExecutionEvent): boolean {
  return ["completed", "failed", "cancelled", "timed_out"].includes(event.status ?? "");
}

export function ToolLaunchDrawer({
  open,
  onClose,
  engagementId,
  onExecutionEvent,
  onExecutionStart,
  onExecutionEnd,
}: ToolLaunchDrawerProps) {
  const [operationKey, setOperationKey] = useState<string>(
    `${OPERATION_OPTIONS[0].toolName}.${OPERATION_OPTIONS[0].operationName}`,
  );
  const [target, setTarget] = useState("");
  const [validation, setValidation] = useState<ToolValidationResponse | null>(null);
  const [busy, setBusy] = useState<"validating" | "executing" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const operation =
    OPERATION_OPTIONS.find((o) => `${o.toolName}.${o.operationName}` === operationKey) ??
    OPERATION_OPTIONS[0];

  function reset() {
    setValidation(null);
    setError(null);
  }

  async function handleValidate() {
    if (!engagementId) {
      setError("Select an engagement first.");
      return;
    }
    if (!target.trim()) {
      setError(`Provide a ${operation.argumentKind === "url" ? "URL" : "target IP/host"}.`);
      return;
    }
    setBusy("validating");
    setError(null);
    try {
      const args: Record<string, string> =
        operation.argumentKind === "url"
          ? { url: target.trim() }
          : { target: target.trim() };
      const result = await validateToolInvocation(engagementId, {
        tool_name: operation.toolName,
        operation_name: operation.operationName,
        args,
      });
      setValidation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
      setValidation(null);
    } finally {
      setBusy(null);
    }
  }

  async function handleExecute() {
    if (!validation?.invocation_id) {
      setError("Validate the invocation first.");
      return;
    }
    setBusy("executing");
    setError(null);
    onExecutionStart();
    try {
      await streamToolExecution(engagementId, validation.invocation_id, (event) => {
        onExecutionEvent(event);
        if (isTerminal(event)) {
          onExecutionEnd();
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution stream failed.");
      onExecutionEnd();
    } finally {
      setBusy(null);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        role="presentation"
      />
      <aside className="absolute right-0 top-0 bottom-0 w-[420px] bg-bg-primary border-l border-border-subtle shadow-2xl flex flex-col">
        <header className="h-10 border-b border-border-subtle bg-surface-secondary flex items-center justify-between px-4">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-widest text-text-primary">
            Launch Tool · Tool Gateway
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="text-text-tertiary hover:text-text-primary"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <Field label="Operation">
            <select
              value={operationKey}
              onChange={(e) => {
                setOperationKey(e.target.value);
                reset();
              }}
              className="w-full bg-surface-secondary border border-border-subtle px-2 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
            >
              {OPERATION_OPTIONS.map((o) => (
                <option key={`${o.toolName}.${o.operationName}`} value={`${o.toolName}.${o.operationName}`}>
                  {o.label} {o.requiresApproval ? "(approval required)" : ""}
                </option>
              ))}
            </select>
            <p className="mt-1 font-sans text-[11px] text-text-secondary">{operation.help}</p>
          </Field>

          <Field label={operation.argumentKind === "url" ? "URL" : "Target IP / Host"}>
            <input
              type="text"
              value={target}
              onChange={(e) => {
                setTarget(e.target.value);
                reset();
              }}
              placeholder={operation.argumentKind === "url" ? "https://10.0.0.5/" : "10.0.0.5"}
              className="w-full bg-surface-secondary border border-border-subtle px-2 py-2 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
            />
          </Field>

          <div className="flex items-center gap-2 text-[10px] font-mono uppercase">
            <span
              className={`px-2 py-0.5 border ${
                operation.riskLevel === "high"
                  ? "border-severity-critical/50 text-severity-critical"
                  : "border-severity-low/50 text-severity-low"
              }`}
            >
              Risk: {operation.riskLevel}
            </span>
            <span className="px-2 py-0.5 border border-border-subtle text-text-secondary">
              {operation.requiresApproval ? "Approval Required" : "Auto-Approved"}
            </span>
          </div>

          {error && (
            <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
              {error}
            </div>
          )}

          {validation && (
            <ValidationPreview validation={validation} />
          )}

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={handleValidate}
              disabled={busy !== null}
              className="bg-surface-secondary border border-border-subtle h-9 font-display text-[11px] uppercase tracking-wider text-text-primary hover:border-primary disabled:opacity-40 transition-colors"
            >
              {busy === "validating" ? "Validating…" : "Validate"}
            </button>
            <button
              type="button"
              onClick={handleExecute}
              disabled={busy !== null || !validation?.invocation_id}
              className="bg-primary h-9 font-display text-[11px] uppercase tracking-wider text-white hover:opacity-80 disabled:opacity-30 transition-opacity"
            >
              {busy === "executing" ? "Streaming…" : "Execute"}
            </button>
          </div>

          <p className="font-mono text-[10px] text-text-tertiary leading-relaxed">
            Validate first to confirm the target is in scope and to mint an
            invocation ID. Execute streams stdout/stderr to the Tactical Terminal.
          </p>
        </div>
      </aside>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block font-display text-[10px] uppercase tracking-widest text-text-tertiary mb-1.5">
        {label}
      </label>
      {children}
    </div>
  );
}

function ValidationPreview({ validation }: { validation: ToolValidationResponse }) {
  return (
    <div className="border border-border-subtle bg-surface-secondary p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-display text-[10px] uppercase tracking-widest text-text-tertiary">
          Validation
        </span>
        <span className="font-mono text-[10px] uppercase text-secondary">{validation.status}</span>
      </div>
      <div className="font-mono text-[11px] text-text-secondary space-y-1">
        <div>
          <span className="text-text-tertiary">tool:</span>{" "}
          <span className="text-text-primary">{validation.tool}.{validation.operation}</span>
        </div>
        <div>
          <span className="text-text-tertiary">targets:</span>{" "}
          <span className="text-text-primary">{validation.targets.join(", ") || "—"}</span>
        </div>
        <div>
          <span className="text-text-tertiary">invocation:</span>{" "}
          <span className="text-text-primary">
            {validation.invocation_id ? validation.invocation_id.split("-")[0].toUpperCase() : "—"}
          </span>
        </div>
        <div className="pt-1 border-t border-border-subtle/50">
          <span className="text-text-tertiary">command:</span>
          <pre className="mt-1 whitespace-pre-wrap break-all text-[10px] text-text-primary">
            {validation.command_preview.join(" ")}
          </pre>
        </div>
      </div>
    </div>
  );
}
