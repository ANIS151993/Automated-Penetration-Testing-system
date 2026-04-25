"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [operatorId, setOperatorId] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [persist, setPersist] = useState(false);
  const [busy, setBusy] = useState(false);
  const [bootClock, setBootClock] = useState("00:00:00:00");

  useEffect(() => {
    const start = Date.now();
    const tick = setInterval(() => {
      const ms = Date.now() - start;
      const s = Math.floor(ms / 1000);
      const hh = String(Math.floor(s / 3600)).padStart(2, "0");
      const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
      const ss = String(s % 60).padStart(2, "0");
      const cs = String(Math.floor((ms % 1000) / 10)).padStart(2, "0");
      setBootClock(`${hh}:${mm}:${ss}:${cs}`);
    }, 50);
    return () => clearInterval(tick);
  }, []);

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    if (persist && typeof window !== "undefined") {
      window.localStorage.setItem("pentai.operator", operatorId);
    }
    setTimeout(() => router.push("/"), 400);
  }

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary grid grid-cols-2 font-sans">
      <BootLoaderPanel clock={bootClock} />
      <section className="flex items-center justify-center px-12 relative">
        <div className="absolute top-4 right-4 font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
          v2.4.0-STABLE {"//"} BUILD_ID: 99x-AF
        </div>
        <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-6">
          <div className="flex items-center gap-2 text-primary">
            <span className="material-symbols-outlined text-[22px]">verified_user</span>
            <span className="font-display text-[12px] uppercase tracking-widest font-bold">
              Secure Gateway
            </span>
          </div>
          <div>
            <h1 className="font-display text-[32px] font-bold tracking-tight text-text-primary uppercase">
              Authentication Required
            </h1>
            <div className="mt-2 h-0.5 w-16 bg-primary" />
          </div>

          <Field label="Operator ID">
            <input
              type="text"
              required
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="NODE_ID_..."
              className="w-full bg-surface-secondary border border-border-subtle px-3 py-2.5 font-mono text-[13px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
            />
          </Field>

          <Field label="Access Key">
            <input
              type="password"
              required
              value={accessKey}
              onChange={(e) => setAccessKey(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-surface-secondary border border-border-subtle px-3 py-2.5 font-mono text-[13px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
            />
          </Field>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={persist}
                onChange={(e) => setPersist(e.target.checked)}
                className="bg-surface-secondary border border-border-subtle text-primary focus:ring-primary"
              />
              <span className="font-display text-[10px] uppercase tracking-widest text-text-secondary">
                Persist Session
              </span>
            </label>
            <a
              href="#"
              className="font-display text-[10px] uppercase tracking-widest text-primary hover:underline"
            >
              Forgot?
            </a>
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-primary py-3.5 font-display text-[12px] uppercase tracking-[0.2em] font-bold text-white hover:opacity-80 disabled:opacity-40 transition-opacity"
          >
            {busy ? "Authenticating…" : "Initiate Sequence"}
          </button>

          <div className="border-t border-border-subtle pt-4 space-y-1.5 font-mono text-[10px]">
            <Row label="NODE ID:" value="PAI-PR-8829-X" />
            <Row label="SESSION TOKEN:" value="NULL_PENDING_AUTH" />
            <Row
              label="SYSTEM STATE:"
              value={
                <span className="text-secondary">■ NOMINAL</span>
              }
            />
          </div>
        </form>
      </section>
    </div>
  );
}

function BootLoaderPanel({ clock }: { clock: string }) {
  return (
    <section className="border-r border-border-subtle relative overflow-hidden bg-bg-primary">
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "repeating-linear-gradient(135deg, transparent 0 12px, #141620 12px 13px)",
        }}
      />
      <div className="absolute top-4 left-4 font-mono text-[10px] text-text-secondary uppercase tracking-widest">
        {clock} {"//"} PENTAI_BOOT_LOADER
      </div>
      <div className="absolute top-12 left-12 right-12 bottom-12 border border-primary/40">
        <span className="absolute -top-px -left-px w-4 h-4 border-t-2 border-l-2 border-primary" />
        <span className="absolute -top-px -right-px w-4 h-4 border-t-2 border-r-2 border-primary" />
        <span className="absolute -bottom-px -left-px w-4 h-4 border-b-2 border-l-2 border-primary" />
        <span className="absolute -bottom-px -right-px w-4 h-4 border-b-2 border-r-2 border-primary" />
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
        <span
          className="material-symbols-outlined text-[120px] text-surface-tertiary"
          style={{ fontVariationSettings: "'FILL' 1" }}
        >
          schema
        </span>
        <span className="font-display text-[11px] uppercase tracking-[0.3em] text-text-tertiary">
          System Topology: Active
        </span>
      </div>
      <div className="absolute bottom-4 left-4 font-mono text-[10px] text-text-secondary space-y-1">
        <div>LATENCY: 12ms</div>
        <div>ENCRYPTION: AES-256-GCM</div>
        <div>CORE: PENTAI-NODE-ALPHA</div>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block font-display text-[10px] uppercase tracking-widest text-text-secondary mb-1.5">
        {label}
      </label>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-tertiary uppercase tracking-wider">{label}</span>
      <span className="text-text-primary uppercase tracking-wider">{value}</span>
    </div>
  );
}
