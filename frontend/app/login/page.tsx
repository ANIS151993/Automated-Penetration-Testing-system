"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
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
    <>
      <style>{`
        /* Responsive viewport-safe layout */
        html, body { height: 100%; }

        .auth-root {
          min-height: 100svh;
          display: flex;
          flex-direction: column;
          background: #0A0B0F;
          color: #E8EAED;
          font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
        }

        /* ── Mobile header (visible < lg) ── */
        .auth-mobile-header {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 20px 24px 0;
        }
        @media (min-width: 1024px) { .auth-mobile-header { display: none; } }

        .auth-logo-icon {
          width: 44px; height: 44px;
          background: #141620;
          border: 1px solid #252836;
          display: flex; align-items: center; justify-content: center;
          position: relative; flex-shrink: 0;
        }
        .auth-logo-icon::before {
          content: '';
          position: absolute; top: 0; left: 0;
          width: 10px; height: 10px;
          border-top: 2px solid #4F8EF7; border-left: 2px solid #4F8EF7;
        }
        .auth-logo-icon::after {
          content: '';
          position: absolute; bottom: 0; right: 0;
          width: 10px; height: 10px;
          border-bottom: 2px solid #4F8EF7; border-right: 2px solid #4F8EF7;
        }
        .auth-logo-text h1 {
          font-family: 'Space Grotesk', sans-serif;
          font-size: clamp(18px, 4vw, 22px);
          font-weight: 700;
          color: #E8EAED;
          text-transform: uppercase;
          letter-spacing: 2px;
          line-height: 1;
          margin: 0;
        }
        .auth-logo-text p {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #5C6378;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          margin: 4px 0 0;
        }

        /* ── Main layout ── */
        .auth-body {
          flex: 1;
          display: flex;
          flex-direction: column;
        }
        @media (min-width: 1024px) {
          .auth-body { flex-direction: row; }
        }

        /* ── Tactical left panel ── */
        .auth-panel {
          display: none;
        }
        @media (min-width: 1024px) {
          .auth-panel {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            flex: 0 0 58%;
            padding: clamp(32px, 4vw, 56px);
            border-right: 1px solid #252836;
            position: relative;
            overflow: hidden;
          }
        }

        .auth-panel-grid {
          position: absolute; inset: 0;
          opacity: 0.04;
          background-image:
            linear-gradient(#4F8EF7 1px, transparent 1px),
            linear-gradient(90deg, #4F8EF7 1px, transparent 1px);
          background-size: 44px 44px;
          pointer-events: none;
        }

        .auth-panel-glow {
          position: absolute;
          top: -20%;  left: -10%;
          width: 60%;  height: 60%;
          background: radial-gradient(ellipse, rgba(79,142,247,0.08) 0%, transparent 70%);
          pointer-events: none;
        }

        .auth-panel-scan {
          position: absolute; left: 0; right: 0; height: 1px;
          background: linear-gradient(90deg, transparent, #4F8EF7, transparent);
          opacity: 0;
          animation: panel-scan 6s linear infinite;
          pointer-events: none;
        }
        @keyframes panel-scan {
          0%   { top: 0%;   opacity: 0; }
          5%   { opacity: 0.4; }
          95%  { opacity: 0.4; }
          100% { top: 100%; opacity: 0; }
        }

        .auth-panel-brand {
          position: relative; z-index: 2;
          display: flex; align-items: center; gap: 16px;
        }
        .auth-panel-brand-icon {
          width: 52px; height: 52px;
          background: #141620;
          border: 1px solid #252836;
          display: flex; align-items: center; justify-content: center;
          position: relative;
        }
        .auth-panel-brand-icon::before {
          content: '';
          position: absolute; top: 0; left: 0;
          width: 12px; height: 12px;
          border-top: 2px solid #4F8EF7; border-left: 2px solid #4F8EF7;
        }
        .auth-panel-brand-icon::after {
          content: '';
          position: absolute; bottom: 0; right: 0;
          width: 12px; height: 12px;
          border-bottom: 2px solid #4F8EF7; border-right: 2px solid #4F8EF7;
        }
        .auth-panel-brand h1 {
          font-family: 'Space Grotesk', sans-serif;
          font-size: clamp(20px, 2vw, 26px);
          font-weight: 700;
          color: #E8EAED;
          text-transform: uppercase;
          letter-spacing: 2px;
          line-height: 1;
          margin: 0;
        }
        .auth-panel-brand p {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          color: #5C6378;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          margin: 5px 0 0;
        }

        .auth-panel-body { position: relative; z-index: 2; }

        .auth-panel-alert {
          display: inline-flex; align-items: center; gap: 10px;
          padding: 8px 14px;
          border: 1px solid #FF3366;
          background: rgba(255,51,102,0.06);
          margin-bottom: 24px;
        }
        .auth-panel-alert-dot {
          width: 7px; height: 7px;
          background: #FF3366;
          flex-shrink: 0;
          animation: blink 1.4s ease-in-out infinite;
        }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
        .auth-panel-alert span {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          color: #FF3366;
          text-transform: uppercase;
          letter-spacing: 1.5px;
        }

        .auth-panel-heading {
          font-family: 'Space Grotesk', sans-serif;
          font-size: clamp(26px, 2.8vw, 38px);
          font-weight: 700;
          color: #E8EAED;
          text-transform: uppercase;
          line-height: 1.1;
          margin: 0 0 16px;
        }
        .auth-panel-heading .highlight { color: #4F8EF7; }

        .auth-panel-desc {
          font-size: clamp(14px, 1.3vw, 15px);
          color: #9AA0B4;
          line-height: 1.7;
          max-width: 420px;
          margin: 0;
        }

        /* Feature list */
        .auth-features {
          margin-top: 32px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .auth-feature-row {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .auth-feature-icon {
          width: 32px; height: 32px;
          background: rgba(79,142,247,0.08);
          border: 1px solid rgba(79,142,247,0.2);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .auth-feature-icon .material-symbols-outlined {
          font-size: 16px;
          color: #4F8EF7;
        }
        .auth-feature-text {
          font-size: 13px;
          color: #9AA0B4;
          line-height: 1.4;
        }

        .auth-panel-stats {
          position: relative; z-index: 2;
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 24px;
          padding-top: 24px;
          border-top: 1px solid #252836;
        }
        .auth-stat-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #5C6378;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          margin: 0 0 6px;
        }
        .auth-stat-value {
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          color: #E8EAED;
          margin: 0;
        }
        .auth-stat-value.ok { color: #00D9A3; }

        /* ── Right form panel ── */
        .auth-form-panel {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: clamp(24px, 5vw, 56px) clamp(20px, 6vw, 64px);
          background: #141620;
          position: relative;
        }
        @media (min-width: 1024px) {
          .auth-form-panel { border-left: 1px solid #252836; }
        }

        .auth-form-inner {
          width: 100%;
          max-width: min(460px, 100%);
        }

        .auth-form-heading {
          margin: 0 0 6px;
          font-family: 'Space Grotesk', sans-serif;
          font-size: clamp(20px, 4vw, 26px);
          font-weight: 700;
          color: #E8EAED;
          text-transform: uppercase;
          letter-spacing: 1px;
        }
        .auth-form-sub {
          margin: 0 0 28px;
          font-size: 14px;
          color: #5C6378;
          line-height: 1.5;
        }

        /* Tab switcher */
        .auth-tabs {
          display: flex;
          border: 1px solid #252836;
          margin-bottom: 28px;
        }
        .auth-tab {
          flex: 1;
          padding: 13px 16px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          color: #5C6378;
          background: transparent;
          border: none;
          cursor: pointer;
          transition: all 0.2s;
          line-height: 1;
        }
        .auth-tab.active {
          background: #4F8EF7;
          color: #ffffff;
        }
        .auth-tab:not(.active):hover {
          color: #E8EAED;
          background: rgba(79,142,247,0.06);
        }

        /* Form fields */
        .auth-field { margin-bottom: 20px; }
        .auth-field-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        .auth-field-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          font-weight: 600;
          color: #9AA0B4;
          text-transform: uppercase;
          letter-spacing: 1.5px;
        }
        .auth-field-link {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #4F8EF7;
          background: none; border: none; cursor: pointer;
          text-transform: uppercase; letter-spacing: 1px;
          padding: 0;
          transition: color 0.2s;
        }
        .auth-field-link:hover { color: #E8EAED; }

        .auth-input-wrap { position: relative; }
        .auth-input-icon {
          position: absolute;
          left: 14px; top: 50%; transform: translateY(-50%);
          pointer-events: none;
        }
        .auth-input-icon .material-symbols-outlined {
          font-size: 18px;
          color: #5C6378;
        }
        .auth-input {
          display: block; width: 100%;
          height: 52px;
          padding: 0 16px 0 44px;
          background: #0A0B0F;
          border: 1px solid #252836;
          color: #E8EAED;
          font-family: 'JetBrains Mono', monospace;
          font-size: 14px;
          transition: border-color 0.2s, box-shadow 0.2s;
          outline: none;
          -webkit-appearance: none;
          appearance: none;
        }
        .auth-input::placeholder { color: #5C6378; }
        .auth-input:focus {
          border-color: #4F8EF7;
          box-shadow: 0 0 0 3px rgba(79,142,247,0.12);
        }
        .auth-input:hover:not(:focus) { border-color: #2F3447; }

        /* Error */
        .auth-error {
          display: flex; align-items: flex-start; gap: 10px;
          padding: 12px 14px;
          border: 1px solid rgba(255,51,102,0.35);
          background: rgba(255,51,102,0.06);
          margin-bottom: 20px;
        }
        .auth-error .material-symbols-outlined { font-size: 16px; color: #FF3366; flex-shrink: 0; margin-top: 1px; }
        .auth-error-text {
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          color: #FF3366;
          line-height: 1.4;
        }

        /* Submit */
        .auth-submit {
          display: flex; align-items: center; justify-content: center; gap: 10px;
          width: 100%; height: 54px;
          background: #4F8EF7;
          color: #ffffff;
          border: none; cursor: pointer;
          font-family: 'JetBrains Mono', monospace;
          font-size: 14px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 2px;
          transition: filter 0.2s, transform 0.1s;
          margin-top: 4px;
        }
        .auth-submit:hover:not(:disabled) { filter: brightness(1.12); }
        .auth-submit:active:not(:disabled) { transform: scale(0.995); }
        .auth-submit:disabled { opacity: 0.45; cursor: not-allowed; }
        .auth-submit .material-symbols-outlined { font-size: 18px; }

        /* Spinner */
        .auth-spinner {
          width: 18px; height: 18px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
          flex-shrink: 0;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Success box */
        .auth-success {
          padding: 16px 18px;
          border: 1px solid rgba(79,142,247,0.35);
          background: rgba(79,142,247,0.06);
          margin-bottom: 20px;
        }
        .auth-success-title {
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          color: #4F8EF7;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          margin: 0 0 8px;
          display: flex; align-items: center; gap: 8px;
        }
        .auth-success-title .material-symbols-outlined { font-size: 16px; }
        .auth-success-body {
          font-size: 14px;
          color: #9AA0B4;
          line-height: 1.6;
          margin: 0;
        }
        .auth-success-body strong { color: #E8EAED; font-weight: 600; }

        .auth-back-btn {
          display: flex; align-items: center; justify-content: center; gap: 8px;
          width: 100%; height: 50px;
          border: 1px solid #252836;
          background: transparent;
          color: #9AA0B4;
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          text-transform: uppercase;
          letter-spacing: 1.5px;
          cursor: pointer;
          transition: all 0.2s;
        }
        .auth-back-btn:hover { color: #E8EAED; border-color: #4F8EF7; }

        /* Footer */
        .auth-footer {
          padding-top: 24px;
          margin-top: 4px;
          border-top: 1px solid #252836;
          text-align: center;
        }
        .auth-footer p {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #5C6378;
          text-transform: uppercase;
          letter-spacing: 1px;
          line-height: 1.8;
          margin: 0;
        }

        /* Corner tag */
        .auth-corner-tag {
          position: absolute; bottom: 16px; right: 16px;
          display: flex; flex-direction: column; align-items: flex-end;
          border-right: 1px solid #252836;
          border-bottom: 1px solid #252836;
          padding: 4px 8px;
          opacity: 0.6;
        }
        .auth-corner-tag span {
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 1px;
          line-height: 1.6;
        }
        .auth-corner-tag .ok { color: #00D9A3; }
        .auth-corner-tag .muted { color: #5C6378; }

        /* Password strength bar */
        .auth-strength { margin-top: 6px; display: flex; gap: 4px; }
        .auth-strength-bar {
          flex: 1; height: 3px; background: #252836;
          transition: background 0.3s;
        }
        .auth-strength-bar.s1 { background: #FF3366; }
        .auth-strength-bar.s2 { background: #FF8C42; }
        .auth-strength-bar.s3 { background: #FFB800; }
        .auth-strength-bar.s4 { background: #00D9A3; }

        /* Mobile bottom padding */
        @media (max-width: 1023px) {
          .auth-form-panel { padding-bottom: 40px; }
        }
      `}</style>

      <div className="auth-root">
        {/* Mobile-only header */}
        <header className="auth-mobile-header">
          <div className="auth-logo-icon">
            <span
              className="material-symbols-outlined"
              style={{ fontSize: "22px", color: "#4F8EF7", fontVariationSettings: "'FILL' 1" }}
            >
              security
            </span>
          </div>
          <div className="auth-logo-text">
            <h1>PentAI Pro</h1>
            <p>Advanced Intelligence Systems</p>
          </div>
        </header>

        <div className="auth-body">
          {/* ── Left tactical panel (desktop only) ── */}
          <section className="auth-panel">
            <div className="auth-panel-grid" />
            <div className="auth-panel-glow" />
            <div className="auth-panel-scan" />

            {/* Brand */}
            <div className="auth-panel-brand">
              <div className="auth-panel-brand-icon">
                <span
                  className="material-symbols-outlined"
                  style={{ fontSize: "24px", color: "#4F8EF7", fontVariationSettings: "'FILL' 1" }}
                >
                  security
                </span>
              </div>
              <div>
                <h1>PentAI Pro</h1>
                <p>Advanced Intelligence Systems</p>
              </div>
            </div>

            {/* Central message */}
            <div className="auth-panel-body">
              <div className="auth-panel-alert">
                <div className="auth-panel-alert-dot" />
                <span>Protocol 88-Alpha: Secure Zone</span>
              </div>
              <h2 className="auth-panel-heading">
                Authorized Personnel<br />
                <span className="highlight">Access Only</span>
              </h2>
              <p className="auth-panel-desc">
                All sessions are encrypted end-to-end and recorded in a
                tamper-evident audit chain. Unauthorized access attempts
                trigger immediate defensive lockout.
              </p>
              <div className="auth-features">
                {[
                  ["verified_user", "Three-layer scope enforcement on every tool invocation"],
                  ["lock", "AES-256-GCM encrypted session with mTLS inter-node transport"],
                  ["smart_toy", "Local LLM inference — zero data leaves your environment"],
                  ["history", "SHA-256 tamper-evident audit log for all agent actions"],
                ].map(([icon, text]) => (
                  <div className="auth-feature-row" key={text}>
                    <div className="auth-feature-icon">
                      <span className="material-symbols-outlined">{icon}</span>
                    </div>
                    <span className="auth-feature-text">{text}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Stats */}
            <div className="auth-panel-stats">
              <div>
                <p className="auth-stat-label">Node Status</p>
                <p className="auth-stat-value ok">● ACTIVE</p>
              </div>
              <div>
                <p className="auth-stat-label">Encryption</p>
                <p className="auth-stat-value">AES-256-GCM</p>
              </div>
              <div>
                <p className="auth-stat-label">Version</p>
                <p className="auth-stat-value">1.1.0-STABLE</p>
              </div>
            </div>
          </section>

          {/* ── Right form panel ── */}
          <section className="auth-form-panel">
            <div className="auth-form-inner">
              <h2 className="auth-form-heading">System Entry</h2>
              <p className="auth-form-sub">Verify credentials to access the terminal.</p>

              {/* Tabs */}
              <div className="auth-tabs" role="tablist">
                <button
                  role="tab"
                  aria-selected={tab === "signin"}
                  className={`auth-tab${tab === "signin" ? " active" : ""}`}
                  onClick={() => setTab("signin")}
                  type="button"
                >
                  Sign In
                </button>
                <button
                  role="tab"
                  aria-selected={tab === "signup"}
                  className={`auth-tab${tab === "signup" ? " active" : ""}`}
                  onClick={() => setTab("signup")}
                  type="button"
                >
                  Register
                </button>
              </div>

              {tab === "signin" ? (
                <SignInForm onSuccess={onSignInSuccess} />
              ) : (
                <SignUpForm onSuccess={() => setTab("signin")} />
              )}

              <div className="auth-footer">
                <p>
                  APTS v1.1.0-STABLE &nbsp;·&nbsp; © 2026 Automated-Penetration-Testing-System
                </p>
              </div>
            </div>

            {/* Corner decoration */}
            <div className="auth-corner-tag">
              <span className="muted">Node: DC-EAST-01</span>
              <span className="ok">PentAI Shield Active</span>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

/* ─── Sign In Form ─── */

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
          ? "Incorrect email or password. If you are new, use the Register tab to create an account."
          : err.message,
      );
      setBusy(false);
      return;
    }
    onSuccess();
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <AuthField label="Agent Identifier" icon="fingerprint">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="operator@pentai.local"
          autoComplete="username"
          className="auth-input"
        />
      </AuthField>

      <AuthField
        label="Access Key"
        icon="lock"
        rightSlot={
          <button type="button" className="auth-field-link">
            Forgot Key?
          </button>
        }
      >
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your access key"
          autoComplete="current-password"
          className="auth-input"
        />
      </AuthField>

      {error && <AuthError>{error}</AuthError>}

      <AuthSubmitButton busy={busy} busyLabel="Authenticating…" icon="terminal">
        Initiate Deployment
      </AuthSubmitButton>
    </form>
  );
}

/* ─── Sign Up Form ─── */

function SignUpForm({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alreadyExists, setAlreadyExists] = useState(false);
  const [done, setDone] = useState(false);

  const strength = getPasswordStrength(password);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email.trim()) { setError("Please enter your email address."); return; }
    if (!displayName.trim()) { setError("Please enter a display name."); return; }
    if (password.length < 8) { setError("Access key must be at least 8 characters."); return; }
    if (password !== confirm) { setError("Passwords do not match."); return; }
    setBusy(true);
    setError(null);
    setAlreadyExists(false);
    const supabase = createClient();
    const { error: err } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { display_name: displayName } },
    });
    if (err) {
      if (err.message.toLowerCase().includes("already") || err.status === 422) {
        setAlreadyExists(true);
      } else {
        setError(err.message);
      }
      setBusy(false);
      return;
    }
    setDone(true);
  }

  if (alreadyExists) {
    return (
      <>
        <div className="auth-error" style={{ marginBottom: "20px", alignItems: "flex-start" }}>
          <span className="material-symbols-outlined" style={{ marginTop: "2px" }}>info</span>
          <div>
            <div style={{ fontWeight: 700, marginBottom: "4px" }}>Account Already Exists</div>
            <div style={{ fontSize: "12px", lineHeight: "1.6", color: "#9AA0B4" }}>
              <strong style={{ color: "#E8EAED" }}>{email}</strong> is already registered.
              Please sign in with your existing password instead.
            </div>
          </div>
        </div>
        <button type="button" onClick={onSuccess} className="auth-submit" style={{ marginBottom: "10px" }}>
          <span className="material-symbols-outlined">login</span>
          Go to Sign In
        </button>
        <button type="button" onClick={() => setAlreadyExists(false)} className="auth-back-btn">
          Try a Different Email
        </button>
      </>
    );
  }

  if (done) {
    return (
      <>
        <div className="auth-success">
          <p className="auth-success-title">
            <span className="material-symbols-outlined">check_circle</span>
            Account Created
          </p>
          <p className="auth-success-body">
            Account for <strong>{email}</strong> is ready.
            Click below to sign in now.
          </p>
        </div>
        <button type="button" onClick={onSuccess} className="auth-submit">
          <span className="material-symbols-outlined">login</span>
          Sign In Now
        </button>
      </>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <AuthField label="Agent Identifier (Email)" icon="fingerprint">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="operator@pentai.local"
          autoComplete="username"
          className="auth-input"
        />
      </AuthField>

      <AuthField label="Display Name" icon="badge">
        <input
          type="text"
          required
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Operator Alpha"
          autoComplete="name"
          className="auth-input"
        />
      </AuthField>

      <AuthField label="Access Key" icon="lock">
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Min. 8 characters"
          autoComplete="new-password"
          className="auth-input"
        />
        {password.length > 0 && (
          <div className="auth-strength">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className={`auth-strength-bar${strength >= n ? ` s${strength}` : ""}`}
              />
            ))}
          </div>
        )}
      </AuthField>

      <AuthField label="Confirm Access Key" icon="lock_reset">
        <input
          type="password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Re-enter your access key"
          autoComplete="new-password"
          className="auth-input"
        />
      </AuthField>

      {error && <AuthError>{error}</AuthError>}

      <AuthSubmitButton busy={busy} busyLabel="Creating Account…" icon="shield_person">
        Request Access
      </AuthSubmitButton>
    </form>
  );
}

/* ─── Shared primitives ─── */

function AuthField({
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
    <div className="auth-field">
      <div className="auth-field-header">
        <label className="auth-field-label">{label}</label>
        {rightSlot}
      </div>
      <div className="auth-input-wrap">
        <div className="auth-input-icon">
          <span className="material-symbols-outlined">{icon}</span>
        </div>
        {children}
      </div>
    </div>
  );
}

function AuthError({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-error">
      <span className="material-symbols-outlined">error</span>
      <span className="auth-error-text">{children}</span>
    </div>
  );
}

function AuthSubmitButton({
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
    <button type="submit" disabled={busy} className="auth-submit">
      {busy ? (
        <>
          <div className="auth-spinner" />
          {busyLabel}
        </>
      ) : (
        <>
          {children}
          <span className="material-symbols-outlined">{icon}</span>
        </>
      )}
    </button>
  );
}

function getPasswordStrength(pw: string): number {
  if (pw.length === 0) return 0;
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw) && /[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  return Math.max(score, pw.length > 0 ? 1 : 0);
}
