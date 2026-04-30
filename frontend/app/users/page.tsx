"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  AuthUser,
  createUser,
  getCurrentUser,
  listUsers,
  setUserActive,
  setUserPassword,
} from "@/lib/api";

export default function UsersPage() {
  const [me, setMe] = useState<AuthUser | null>(null);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");

  const [resetTarget, setResetTarget] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState("");

  const refresh = useCallback(async () => {
    try {
      setUsers(await listUsers());
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    getCurrentUser()
      .then(setMe)
      .catch(() => null);
    refresh();
  }, [refresh]);

  const onCreateSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setBusy(true);
      setError(null);
      try {
        await createUser({ email, password, display_name: displayName, role });
        setEmail(""); setDisplayName(""); setPassword(""); setRole("operator");
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    },
    [email, password, displayName, role, refresh],
  );

  const onToggleActive = useCallback(
    async (user: AuthUser) => {
      setBusy(true);
      setError(null);
      try {
        await setUserActive(user.id, !user.is_active);
        await refresh();
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const onResetPassword = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!resetTarget || !resetPw) return;
      setBusy(true);
      setError(null);
      try {
        await setUserPassword(resetTarget, resetPw);
        setResetTarget(null);
        setResetPw("");
      } catch (err) {
        setError(String(err));
      } finally {
        setBusy(false);
      }
    },
    [resetTarget, resetPw],
  );

  if (me && me.role !== "admin") {
    return (
      <AppShell>
        <div className="space-y-gutter">
          <div className="border border-severity-critical/50 bg-severity-critical/10 p-3 font-mono text-[11px] text-severity-critical">
            Admin access required.
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-gutter">
        <div>
          <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
            Access Control
          </div>
          <h1 className="font-display text-[24px] font-semibold text-text-primary uppercase tracking-tight">
            User Management · v1
          </h1>
          <p className="mt-2 font-mono text-[11px] text-text-tertiary max-w-2xl leading-relaxed">
            Admin-only. Create operators and manage access credentials.
          </p>
        </div>

        {error && (
          <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
            {error}
          </div>
        )}

        {/* Create user */}
        <section className="border border-border-subtle bg-surface-secondary p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
              Create Operator
            </span>
            <span className="material-symbols-outlined text-[18px] text-text-tertiary">person_add</span>
          </div>
          <form onSubmit={onCreateSubmit} className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
                Email
              </label>
              <input
                type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
                Display Name
              </label>
              <input
                type="text" required value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
                Password
              </label>
              <input
                type="password" required minLength={8} value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
                Role
              </label>
              <select
                value={role} onChange={(e) => setRole(e.target.value)}
                className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
              >
                <option value="operator">OPERATOR</option>
                <option value="admin">ADMIN</option>
              </select>
            </div>
            <div className="col-span-2 pt-1">
              <button
                type="submit" disabled={busy}
                className="bg-primary px-4 py-2 font-display text-[11px] uppercase tracking-widest text-white hover:opacity-80 disabled:opacity-30"
              >
                {busy ? "Creating…" : "Create User"}
              </button>
            </div>
          </form>
        </section>

        {/* User list */}
        <section className="border border-border-subtle bg-surface-secondary">
          <div className="px-4 h-10 grid grid-cols-[1fr_80px_80px_auto] gap-4 border-b border-border-subtle bg-surface-tertiary font-mono text-[10px] uppercase tracking-widest text-text-tertiary items-center">
            <span>Email / Name</span>
            <span>Role</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          <div className="divide-y divide-border-subtle/50">
            {users.length === 0 && (
              <div className="px-4 py-8 font-mono text-[11px] text-text-tertiary text-center">
                No users found.
              </div>
            )}
            {users.map((u) => (
              <div
                key={u.id}
                className="px-4 py-3 grid grid-cols-[1fr_80px_80px_auto] gap-4 items-center"
              >
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="font-mono text-[11px] text-text-primary truncate">{u.email}</span>
                  <span className="font-mono text-[10px] text-text-tertiary truncate">{u.display_name}</span>
                </div>
                <span className={`font-mono text-[10px] uppercase font-bold ${u.role === "admin" ? "text-primary" : "text-text-secondary"}`}>
                  {u.role}
                </span>
                <span className={`font-mono text-[10px] uppercase font-bold ${u.is_active ? "text-secondary" : "text-severity-critical"}`}>
                  {u.is_active ? "active" : "inactive"}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => { setResetTarget(u.id); setResetPw(""); }}
                    className="px-2 py-1 border border-border-subtle font-display text-[10px] uppercase tracking-widest text-text-secondary hover:border-primary hover:text-primary"
                  >
                    Reset PW
                  </button>
                  {u.id !== me?.id && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onToggleActive(u)}
                      className={`px-2 py-1 border font-display text-[10px] uppercase tracking-widest disabled:opacity-30 ${
                        u.is_active
                          ? "border-severity-critical/40 text-severity-critical hover:bg-severity-critical/10"
                          : "border-secondary/40 text-secondary hover:bg-secondary/10"
                      }`}
                    >
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Password reset modal */}
      {resetTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg-primary/80">
          <div className="w-full max-w-sm border border-border-subtle bg-surface-secondary">
            <div className="px-5 py-4 border-b border-border-subtle">
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
                Security Operation
              </div>
              <h3 className="font-display text-[16px] font-semibold text-text-primary mt-1">
                Reset Password
              </h3>
            </div>
            <form onSubmit={onResetPassword} className="p-5 space-y-4">
              <div>
                <label className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary block mb-1.5">
                  New Password
                </label>
                <input
                  type="password" required minLength={8} autoFocus
                  value={resetPw} onChange={(e) => setResetPw(e.target.value)}
                  className="w-full bg-surface-tertiary border border-border-subtle px-3 py-2 font-mono text-[12px] text-text-primary focus:outline-none focus:border-primary"
                />
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  type="submit" disabled={busy}
                  className="bg-primary px-4 py-2 font-display text-[11px] uppercase tracking-widest text-white hover:opacity-80 disabled:opacity-30"
                >
                  {busy ? "Saving…" : "Set Password"}
                </button>
                <button
                  type="button"
                  onClick={() => { setResetTarget(null); setResetPw(""); }}
                  className="px-4 py-2 border border-border-subtle font-display text-[11px] uppercase tracking-widest text-text-secondary hover:text-text-primary"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
