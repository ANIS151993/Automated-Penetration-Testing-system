"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  AuditEvent,
  Engagement,
  listAuditEvents,
  listEngagements,
} from "@/lib/api";

type Status = "SUCCESS" | "BLOCKED" | "WARNING";

const STATUS_TONE: Record<Status, { bg: string; fg: string }> = {
  SUCCESS: { bg: "bg-secondary/15", fg: "text-secondary" },
  BLOCKED: { bg: "bg-severity-critical/15", fg: "text-severity-critical" },
  WARNING: { bg: "bg-severity-medium/15", fg: "text-severity-medium" },
};

function classify(eventType: string): Status {
  if (eventType.includes("blocked") || eventType.includes("denied") || eventType.includes("rejected"))
    return "BLOCKED";
  if (eventType.includes("warn") || eventType.includes("paused") || eventType.includes("aborted"))
    return "WARNING";
  return "SUCCESS";
}

function shortHash(h: string): string {
  if (!h) return "—";
  return `${h.slice(0, 4)}…${h.slice(-4)}`;
}

export default function AuditPage() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  useEffect(() => {
    listEngagements()
      .then((rows) => {
        setEngagements(rows);
        if (rows.length > 0) setSelectedId(rows[0].id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const fetcher = () =>
      listAuditEvents(selectedId)
        .then(setEvents)
        .catch((e) => setError(String(e)));
    fetcher();
    const t = setInterval(fetcher, 5000);
    return () => clearInterval(t);
  }, [selectedId]);

  const integrityValid = useMemo(() => {
    for (let i = 1; i < events.length; i++) {
      if (events[i - 1].evidence_hash !== events[i].prev_hash) return false;
    }
    return true;
  }, [events]);

  const recentChain = useMemo(() => events.slice(-6), [events]);

  const eventTypes = useMemo(() => {
    const set = new Set<string>();
    events.forEach((e) => set.add(e.event_type));
    return Array.from(set).sort();
  }, [events]);

  const filteredEvents = useMemo(() => {
    if (typeFilter === "all") return events;
    if (typeFilter === "agent_runs") {
      return events.filter((e) => e.event_type === "agent_run_completed");
    }
    return events.filter((e) => e.event_type === typeFilter);
  }, [events, typeFilter]);

  return (
    <AppShell>
      <div className="space-y-gutter">
        <div>
          <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
            System Audit
          </div>
          <h1 className="font-display text-[24px] font-semibold text-text-primary uppercase tracking-tight">
            Log Explorer · v1
          </h1>
          <div className="mt-2 flex items-center gap-4">
            <div className="flex items-center gap-2 px-2 py-1 bg-surface-secondary border border-border-subtle">
              <span className="w-1.5 h-1.5 bg-secondary animate-pulse" />
              <span className="font-display text-[10px] uppercase tracking-widest text-secondary">
                Live Monitoring
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
                Engagement:
              </span>
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="bg-surface-secondary border border-border-subtle px-2 py-1 font-mono text-[11px] text-text-primary"
              >
                {engagements.length === 0 && <option value="">— None —</option>}
                {engagements.map((eg) => (
                  <option key={eg.id} value={eg.id}>
                    {eg.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
                Event:
              </span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="bg-surface-secondary border border-border-subtle px-2 py-1 font-mono text-[11px] text-text-primary"
              >
                <option value="all">all</option>
                <option value="agent_runs">agent_run_completed</option>
                {eventTypes
                  .filter((t) => t !== "agent_run_completed")
                  .map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
              </select>
            </div>
          </div>
        </div>

        {error && (
          <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
            {error}
          </div>
        )}

        <div className="border border-border-subtle bg-surface-secondary">
          <div className="px-4 py-2 grid grid-cols-[1fr_auto_auto] gap-4 border-b border-border-subtle bg-surface-tertiary font-display text-[10px] uppercase tracking-widest text-text-tertiary">
            <span>Timestamp / Actor</span>
            <span>Result</span>
            <span className="w-24 text-right">Hash</span>
          </div>
          <div className="divide-y divide-border-subtle/50 max-h-[55vh] overflow-y-auto">
            {filteredEvents.length === 0 && (
              <div className="px-4 py-8 font-mono text-[11px] text-text-tertiary text-center">
                {events.length === 0
                  ? "No audit events for this engagement yet."
                  : "No events match this filter."}
              </div>
            )}
            {[...filteredEvents].reverse().map((ev) => {
              const status = classify(ev.event_type);
              const tone = STATUS_TONE[status];
              return (
                <div
                  key={ev.evidence_hash}
                  className="px-4 py-3 grid grid-cols-[1fr_auto_auto] gap-4 items-center hover:bg-surface-tertiary/40"
                >
                  <div>
                    <div className="font-mono text-[11px] text-text-primary">
                      {new Date(ev.occurred_at).toISOString()}
                    </div>
                    <div className="font-mono text-[10px] text-text-tertiary uppercase mt-0.5">
                      Actor: {ev.actor ?? "SYS_DAEMON"} · {ev.event_type}
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 font-display text-[10px] uppercase tracking-widest font-bold ${tone.bg} ${tone.fg}`}
                  >
                    {status}
                  </span>
                  <span className="font-mono text-[10px] text-text-secondary w-24 text-right">
                    {shortHash(ev.evidence_hash)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="border border-border-subtle bg-surface-secondary p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
              Integrity Chain
            </span>
            <span
              className={`material-symbols-outlined text-[18px] ${
                integrityValid ? "text-secondary" : "text-severity-critical"
              }`}
            >
              {integrityValid ? "lock" : "lock_open"}
            </span>
          </div>
          <div className="flex items-center gap-1 overflow-x-auto pb-1">
            {recentChain.length === 0 && (
              <span className="font-mono text-[11px] text-text-tertiary">No chain yet.</span>
            )}
            {recentChain.map((ev, i) => (
              <span key={ev.evidence_hash} className="flex items-center gap-1 shrink-0">
                <span className="px-2 py-1 border border-primary/40 font-mono text-[10px] text-primary uppercase">
                  {ev.evidence_hash.slice(0, 4)}
                </span>
                {i < recentChain.length - 1 && (
                  <span className="text-text-tertiary font-mono">→</span>
                )}
              </span>
            ))}
            {recentChain.length > 0 && (
              <>
                <span className="text-text-tertiary font-mono ml-1">→</span>
                <span className="px-2 py-1 border border-secondary font-mono text-[10px] text-secondary uppercase">
                  CUR
                </span>
              </>
            )}
          </div>
          <p className="mt-3 font-mono text-[10px] text-text-tertiary leading-relaxed">
            Cryptographic verification {integrityValid ? "active" : "FAILED"}. All log entries are
            immutable and SHA-256 hash-chained from genesis.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
