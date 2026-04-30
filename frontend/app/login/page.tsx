"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { FormEvent, Suspense, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  return (
    <Suspense>
      <AuthScreen />
    </Suspense>
  );
}

type Tab = "signin" | "signup";

function AuthScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>("signin");

  function onSignInSuccess() {
    const next = searchParams.get("next") || "/";
    router.push(next as never);
    router.refresh();
  }

  return (
    <main className="flex min-h-screen w-full bg-bg-primary text-text-primary font-sans overflow-hidden">
      <TacticalPanel />

      <section className="w-full lg:w-2/5 bg-surface-secondary flex flex-col items-center justify-center p-8 relative border-l border-border-subtle">
        <div className="w-full max-w-sm space-y-6">
          {/* Heading */}
          <div className="space-y-1">
            <h3 className="font-display text-h3 text-text-primary uppercase tracking-wider">
              System Entry
            </h3>
            <p className="text-body-sm text-text-tertiary">
              Verify credentials to decrypt terminal.
            </p>
          </div>

          {/* Tab switcher */}
          <div className="flex border border-border-subtle">
            <TabButton active={tab === "signin"} onClick={() => setTab("signin")}>
              Sign In
            </TabButton>
            <TabButton active={tab === "signup"} onClick={() => setTab("signup")}>
              Register
            </TabButton>
          </div>

          {tab === "signin" ? (
            <SignInForm onSuccess={onSignInSuccess} />
          ) : (
            <SignUpForm onSuccess={() => setTab("signin")} />
          )}

          <div className="pt-4 text-center border-t border-border-subtle">
            <p className="font-mono text-[10px] text-text-tertiary uppercase leading-tight">
              APTS Version: 1.1.0-STABLE
              <br />© 2026 Automated-Penetration-Testing-system
            </p>
          </div>
        </div>

        {/* Corner decoration */}
        <div className="absolute bottom-4 right-4 flex flex-col items-end opacity-60 border-r border-b border-border-subtle p-1">
          <div className="font-mono text-[9px] text-text-tertiary uppercase leading-none">
            Node: DC-EAST-01
          </div>
          <div className="font-mono text-[9px] text-primary leading-none mt-1 uppercase">
            PentAI Shield Active
          </div>
        </div>
      </section>
    </main>
  );
}

/* ─── Sign In ─── */

function SignInForm({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = createClient();
    const { error: err } = await supabase.auth.signInWithPassword({ email, password });
    if (err) {
      setError(
        err.message === "Invalid login credentials"
          ? "Invalid email or access key."
          : err.message,
      );
      setBusy(false);
      return;
    }
    onSuccess();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormField label="Agent Identifier" icon="fingerprint">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="operator@pentai.local"
          autoComplete="username"
          className={inputCls}
        />
      </FormField>

      <FormField
        label="Access Key"
        icon="lock"
        rightSlot={
          <button
            type="button"
            className="font-mono text-label-caps text-primary hover:text-text-primary transition-colors"
          >
            Forgot Key?
          </button>
        }
      >
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••••••"
          autoComplete="current-password"
          className={inputCls}
        />
      </FormField>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      <SubmitButton busy={busy} busyLabel="Authenticating…" icon="terminal">
        INITIATE DEPLOYMENT
      </SubmitButton>
    </form>
  );
}

/* ─── Sign Up ─── */

function SignUpForm({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 8) { setError("Access key must be at least 8 characters."); return; }
    setBusy(true);
    setError(null);
    const supabase = createClient();
    const { error: err } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { display_name: displayName } },
    });
    if (err) { setError(err.message); setBusy(false); return; }
    setDone(true);
  }

  if (done) {
    return (
      <div className="space-y-4">
        <div className="border border-primary/40 bg-primary/5 px-4 py-3 space-y-1">
          <p className="font-mono text-[11px] text-primary uppercase tracking-wider">
            Access Request Submitted
          </p>
          <p className="text-body-sm text-text-secondary">
            Check <span className="text-text-primary font-mono">{email}</span> for
            a confirmation link, then sign in.
          </p>
        </div>
        <button
          type="button"
          onClick={onSuccess}
          className="w-full border border-border-subtle py-2.5 font-mono text-label-caps uppercase tracking-wider text-text-secondary hover:text-text-primary hover:border-primary transition-colors"
        >
          Back to Sign In
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormField label="Agent Identifier" icon="fingerprint">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="operator@pentai.local"
          autoComplete="username"
          className={inputCls}
        />
      </FormField>

      <FormField label="Display Name" icon="badge">
        <input
          type="text"
          required
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Operator Alpha"
          autoComplete="name"
          className={inputCls}
        />
      </FormField>

      <FormField label="Access Key" icon="lock">
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="min. 8 characters"
          autoComplete="new-password"
          className={inputCls}
        />
      </FormField>

      <FormField label="Confirm Access Key" icon="lock_reset">
        <input
          type="password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="••••••••••••"
          autoComplete="new-password"
          className={inputCls}
        />
      </FormField>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      <SubmitButton busy={busy} busyLabel="Processing…" icon="shield_person">
        REQUEST ACCESS
      </SubmitButton>
    </form>
  );
}

/* ─── Tactical left panel ─── */

function TacticalPanel() {
  const lineRef = useRef<HTMLDivElement>(null);

  return (
    <section className="hidden lg:flex lg:w-3/5 relative flex-col justify-between p-8 bg-bg-primary border-r border-border-subtle overflow-hidden">
      {/* Grid overlay */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(#4F8EF7 1px, transparent 1px), linear-gradient(90deg, #4F8EF7 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Branding */}
      <div className="relative z-10 flex items-center gap-4">
        <div className="w-10 h-10 bg-surface-secondary border border-border-subtle flex items-center justify-center relative">
          <span
            className="material-symbols-outlined text-primary"
            style={{ fontVariationSettings: "'FILL' 1", fontSize: "20px" }}
          >
            security
          </span>
          <span className="absolute top-0 left-0 w-2 h-2 border-t border-l border-primary" />
          <span className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-primary" />
        </div>
        <div>
          <h1 className="font-display text-h2 text-text-primary tracking-tight uppercase leading-none">
            PentAI Pro
          </h1>
          <p className="font-mono text-label-caps text-text-tertiary mt-1 tracking-widest">
            Advanced Intelligence Systems
          </p>
        </div>
      </div>

      {/* Central messaging */}
      <div className="relative z-10 max-w-lg">
        <div className="inline-flex items-center gap-2 px-2 py-1 border border-severity-critical mb-6 bg-severity-critical/5">
          <span className="w-1.5 h-1.5 bg-severity-critical flex-shrink-0" />
          <span className="font-mono text-label-caps text-severity-critical uppercase">
            Protocol 88-Alpha: Secure Zone
          </span>
        </div>
        <h2 className="font-display text-[28px] font-bold text-text-primary mb-4 leading-none uppercase">
          Authorized Personnel
          <br />
          <span className="text-primary">Access Only</span>
        </h2>
        <p className="text-body-md text-text-secondary max-w-md leading-relaxed">
          Secure node access. Activity monitored and logged.
          Unauthorized attempts trigger immediate defensive lockout.
        </p>
      </div>

      {/* Stats row */}
      <div className="relative z-10 grid grid-cols-3 gap-8 pt-8 border-t border-border-subtle">
        <div>
          <p className="font-mono text-label-caps text-text-tertiary mb-2 uppercase tracking-widest">
            Node Status
          </p>
          <div className="flex items-center gap-2">
            <span className="font-mono text-body-sm text-primary">ACTIVE</span>
            <div className="w-20 h-1 bg-surface-container">
              <div className="h-full bg-primary w-3/4" />
            </div>
          </div>
        </div>
        <div>
          <p className="font-mono text-label-caps text-text-tertiary mb-2 uppercase tracking-widest">
            Encryption
          </p>
          <p className="font-mono text-body-sm text-text-primary">AES-256-GCM</p>
        </div>
        <div>
          <p className="font-mono text-label-caps text-text-tertiary mb-2 uppercase tracking-widest">
            System Load
          </p>
          <p className="font-mono text-body-sm text-text-primary">1.24 MS / 0.02%</p>
        </div>
      </div>

      {/* Scanner line */}
      <div
        ref={lineRef}
        className="absolute inset-x-0 h-px bg-primary opacity-0 pointer-events-none"
        style={{ animation: "pentai-scan 5s linear infinite" }}
      />
      <style>{`
        @keyframes pentai-scan {
          0%   { top: 0%;   opacity: 0; }
          5%   { opacity: 0.35; }
          95%  { opacity: 0.35; }
          100% { top: 100%; opacity: 0; }
        }
      `}</style>
    </section>
  );
}

/* ─── Shared primitives ─── */

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 py-2 font-mono text-label-caps uppercase tracking-wider transition-colors ${
        active
          ? "bg-primary text-white"
          : "bg-transparent text-text-tertiary hover:text-text-primary"
      }`}
    >
      {children}
    </button>
  );
}

function FormField({
  label,
  icon,
  rightSlot,
  children,
}: {
  label: string;
  icon: string;
  rightSlot?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center">
        <label className="font-mono text-label-caps text-text-tertiary uppercase tracking-widest">
          {label}
        </label>
        {rightSlot}
      </div>
      <div className="relative">
        <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
          <span
            className="material-symbols-outlined text-text-tertiary"
            style={{ fontSize: "16px" }}
          >
            {icon}
          </span>
        </div>
        <div className="[&>input]:pl-9">{children}</div>
      </div>
    </div>
  );
}

function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="border border-severity-critical/40 bg-severity-critical/5 px-3 py-2 font-mono text-[11px] text-severity-critical">
      {children}
    </div>
  );
}

function SubmitButton({
  busy,
  busyLabel,
  icon,
  children,
}: {
  busy: boolean;
  busyLabel: string;
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full h-10 bg-primary text-white font-mono text-label-caps uppercase tracking-wider flex items-center justify-center gap-2 hover:brightness-110 disabled:opacity-40 transition-all"
    >
      {busy ? (
        busyLabel
      ) : (
        <>
          {children}
          <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>
            {icon}
          </span>
        </>
      )}
    </button>
  );
}

const inputCls =
  "block w-full h-10 px-3 bg-surface-secondary border border-border-subtle text-text-primary font-mono text-body-sm placeholder:text-text-tertiary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors";
