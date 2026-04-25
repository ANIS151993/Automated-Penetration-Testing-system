"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { createEngagement } from "@/lib/api";

type Mode = "BLACK_BOX" | "WHITE_BOX";

export default function NewEngagementPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);

  const [name, setName] = useState("");
  const [scopeCidr, setScopeCidr] = useState("");
  const [scopeValidated, setScopeValidated] = useState(false);
  const [mode, setMode] = useState<Mode>("BLACK_BOX");

  const [description, setDescription] = useState("");
  const [operatorName, setOperatorName] = useState("");
  const [authorizerName, setAuthorizerName] = useState("");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function validateCidr() {
    setError(null);
    const m = scopeCidr.trim().match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/);
    if (!m) {
      setError("Invalid CIDR format. Use e.g. 192.168.1.0/24");
      setScopeValidated(false);
      return;
    }
    const [, a, b, c, d, prefix] = m;
    const octets = [a, b, c, d].map(Number);
    if (octets.some((o) => o > 255) || Number(prefix) > 32) {
      setError("CIDR out of range.");
      setScopeValidated(false);
      return;
    }
    setScopeValidated(true);
  }

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    try {
      const created = await createEngagement({
        name: name.trim(),
        description: description.trim(),
        scope_cidrs: [scopeCidr.trim()],
        authorization_confirmed: authorizationConfirmed,
        authorizer_name: authorizerName.trim(),
        operator_name: operatorName.trim(),
      });
      router.push(`/engagements?selected=${created.id}` as never);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create engagement.");
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="flex items-start justify-center pt-6">
        <div className="w-[640px] bg-surface-secondary border border-border-subtle">
          <header className="px-6 py-4 border-b border-border-subtle flex items-center justify-between">
            <div>
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
                Initiate Protocol
              </div>
              <h1 className="font-display text-[20px] font-semibold text-text-primary mt-1">
                New Engagement Wizard
              </h1>
            </div>
            <StepIndicator current={step} />
          </header>

          <div className="bg-severity-medium/15 border-y border-severity-medium/40 px-6 py-2 font-mono text-[10px] uppercase tracking-wider text-severity-medium">
            Notice: All actions logged under SOX Compliance Protocol 4.2. Authorized access only.
          </div>

          <div className="p-6 space-y-5">
            {step === 1 && (
              <>
                <Field label="ENGAGEMENT_ID">
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. ALPHA-SIERRA-2024"
                    className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2.5 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
                  />
                </Field>

                <div>
                  <div className="flex justify-between items-end mb-1.5">
                    <span className="font-display text-[10px] uppercase tracking-widest text-text-secondary">
                      TARGET_CIDR_SCOPE
                    </span>
                    <span className="font-mono text-[10px] text-text-tertiary uppercase">
                      Syntax: IP/MASK
                    </span>
                  </div>
                  <div className="grid grid-cols-[1fr_auto] gap-2">
                    <input
                      type="text"
                      value={scopeCidr}
                      onChange={(e) => {
                        setScopeCidr(e.target.value);
                        setScopeValidated(false);
                      }}
                      placeholder="192.168.1.0/24"
                      className="bg-surface-tertiary border border-border-subtle px-3 py-2.5 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
                    />
                    <button
                      type="button"
                      onClick={validateCidr}
                      className="bg-surface-tertiary border border-border-subtle px-4 font-display text-[11px] uppercase tracking-widest text-text-primary hover:border-primary"
                    >
                      Validate
                    </button>
                  </div>
                </div>

                {scopeValidated && <CidrParseLog cidr={scopeCidr} />}

                <div className="grid grid-cols-2 gap-3">
                  <ModeCard
                    icon="track_changes"
                    label="BLACK_BOX"
                    description="No prior internal knowledge. Pure external reconnaissance and exploitation."
                    selected={mode === "BLACK_BOX"}
                    onSelect={() => setMode("BLACK_BOX")}
                  />
                  <ModeCard
                    icon="account_tree"
                    label="WHITE_BOX"
                    description="Full architecture documentation provided. Focus on logic and credentialed access."
                    selected={mode === "WHITE_BOX"}
                    onSelect={() => setMode("WHITE_BOX")}
                  />
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <Field label="DESCRIPTION">
                  <textarea
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Mission brief, target environment notes, exclusions…"
                    className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2.5 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary resize-none"
                  />
                </Field>
                <Field label="OPERATOR_NAME">
                  <input
                    type="text"
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    placeholder="UID-8829-X"
                    className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2.5 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
                  />
                </Field>
                <Field label="MODE">
                  <div className="font-mono text-[12px] text-text-secondary px-3 py-2 bg-surface-tertiary border border-border-subtle">
                    {mode}
                  </div>
                </Field>
              </>
            )}

            {step === 3 && (
              <>
                <Field label="AUTHORIZER_NAME">
                  <input
                    type="text"
                    value={authorizerName}
                    onChange={(e) => setAuthorizerName(e.target.value)}
                    placeholder="Name of person who authorized this engagement"
                    className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2.5 font-mono text-[12px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary"
                  />
                </Field>
                <label className="flex items-start gap-3 cursor-pointer p-3 border border-border-subtle bg-surface-tertiary">
                  <input
                    type="checkbox"
                    checked={authorizationConfirmed}
                    onChange={(e) => setAuthorizationConfirmed(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span className="font-mono text-[11px] text-text-secondary leading-relaxed">
                    I confirm written authorization is on file for this engagement, the scope above
                    is correct, and all activity is logged under SOX Compliance Protocol 4.2.
                  </span>
                </label>

                <SummaryBlock
                  rows={[
                    ["ENGAGEMENT_ID", name || "—"],
                    ["SCOPE", scopeCidr || "—"],
                    ["MODE", mode],
                    ["OPERATOR", operatorName || "—"],
                    ["AUTHORIZER", authorizerName || "—"],
                  ]}
                />
              </>
            )}

            {error && (
              <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
                {error}
              </div>
            )}
          </div>

          <footer className="px-6 py-4 border-t border-border-subtle flex justify-between items-center bg-surface-secondary">
            <button
              type="button"
              onClick={() => (step === 1 ? router.back() : setStep((s) => (s - 1) as 1 | 2 | 3))}
              className="px-4 py-2 border border-border-subtle font-display text-[11px] uppercase tracking-widest text-text-primary hover:bg-surface-tertiary"
            >
              {step === 1 ? "Cancel" : "Back"}
            </button>

            {step < 3 ? (
              <button
                type="button"
                disabled={
                  step === 1
                    ? !name.trim() || !scopeValidated
                    : step === 2
                      ? !operatorName.trim()
                      : false
                }
                onClick={() => setStep((s) => (s + 1) as 1 | 2 | 3)}
                className="bg-primary px-5 py-2 font-display text-[11px] uppercase tracking-widest text-white hover:opacity-80 disabled:opacity-30"
              >
                {step === 1 ? "Continue → Scan Config" : "Continue → Authorization"}
              </button>
            ) : (
              <button
                type="button"
                disabled={busy || !authorizationConfirmed || !authorizerName.trim()}
                onClick={handleSubmit}
                className="bg-secondary px-5 py-2 font-display text-[11px] uppercase tracking-widest text-bg-primary font-bold hover:opacity-80 disabled:opacity-30"
              >
                {busy ? "Provisioning…" : "Initiate Engagement"}
              </button>
            )}
          </footer>
        </div>
      </div>
    </AppShell>
  );
}

function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  return (
    <div className="flex items-center gap-1 px-3 py-1.5 bg-surface-tertiary border border-border-subtle font-mono text-[11px]">
      {[1, 2, 3].map((s, i) => (
        <span key={s} className="flex items-center gap-1">
          <span className={s === current ? "text-primary font-bold" : "text-text-tertiary"}>
            0{s}
          </span>
          {i < 2 && <span className="text-text-tertiary">/</span>}
        </span>
      ))}
    </div>
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

function CidrParseLog({ cidr }: { cidr: string }) {
  const [base, prefix] = cidr.split("/");
  const prefixNum = Number(prefix);
  const totalHosts = Math.max(0, Math.pow(2, 32 - prefixNum) - 2);
  const mask =
    prefixNum >= 24
      ? `255.255.255.${(256 - Math.pow(2, 32 - prefixNum)) & 0xff}`
      : prefixNum >= 16
        ? "255.255.0.0"
        : prefixNum >= 8
          ? "255.0.0.0"
          : "0.0.0.0";
  return (
    <div className="bg-surface-tertiary/50 border border-border-subtle p-3 font-mono text-[11px] text-text-secondary leading-relaxed">
      <div className="text-secondary mb-1">◉ PARSING_LOGIC_ACTIVE</div>
      <div>{">"} Initializing subnet calculation…</div>
      <div>
        {">"} Base address: <span className="text-text-primary">{base}</span>
      </div>
      <div>
        {">"} Total Hosts: <span className="text-text-primary">{totalHosts}</span> [Usable]
      </div>
      <div>
        {">"} Network Mask: <span className="text-text-primary">{mask}</span>
      </div>
      <div className="text-secondary mt-1">{">"} Verification complete. Scope valid.</div>
    </div>
  );
}

function ModeCard({
  icon,
  label,
  description,
  selected,
  onSelect,
}: {
  icon: string;
  label: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`text-left p-4 border transition-colors ${
        selected
          ? "border-primary bg-primary/10"
          : "border-border-subtle bg-surface-tertiary hover:border-border-accent"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="material-symbols-outlined text-[20px] text-text-primary">{icon}</span>
        {selected && (
          <span className="font-mono text-[9px] uppercase tracking-widest bg-primary text-white px-1.5 py-0.5">
            Selected
          </span>
        )}
      </div>
      <div className="font-mono text-[12px] text-text-primary mb-1">{label}</div>
      <p className="font-sans text-[11px] text-text-secondary leading-snug">{description}</p>
    </button>
  );
}

function SummaryBlock({ rows }: { rows: [string, string][] }) {
  return (
    <div className="border border-border-subtle bg-surface-tertiary/50 p-3 space-y-1.5 font-mono text-[11px]">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between">
          <span className="text-text-tertiary uppercase tracking-wider">{k}</span>
          <span className="text-text-primary">{v}</span>
        </div>
      ))}
    </div>
  );
}
