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

  // create form
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");

  // password reset
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
        <div className="mx-auto max-w-2xl p-6">
          <p className="text-rose-400 text-sm">Admin access required.</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-6 p-6">
        <header>
          <h1 className="text-2xl font-semibold text-white">User Management</h1>
          <p className="mt-1 text-sm text-white/60">Admin-only. Create operators and manage access.</p>
        </header>

        {error ? <p className="text-sm text-rose-400">{error}</p> : null}

        {/* Create user */}
        <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
          <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72 mb-4">
            Create user
          </h2>
          <form onSubmit={onCreateSubmit} className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs uppercase tracking-[0.3em] text-white/48 mb-1">Email</label>
              <input
                type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-[0.3em] text-white/48 mb-1">Display name</label>
              <input
                type="text" required value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-[0.3em] text-white/48 mb-1">Password</label>
              <input
                type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-[0.3em] text-white/48 mb-1">Role</label>
              <select
                value={role} onChange={(e) => setRole(e.target.value)}
                className="w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
              >
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="col-span-2">
              <button
                type="submit" disabled={busy}
                className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-50"
              >
                {busy ? "Creating…" : "Create user"}
              </button>
            </div>
          </form>
        </section>

        {/* User list */}
        <section className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
          <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/72 mb-4">
            Users ({users.length})
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-white/48">
                <th className="pb-2 pr-4">Email</th>
                <th className="pb-2 pr-4">Name</th>
                <th className="pb-2 pr-4">Role</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {users.map((u) => (
                <tr key={u.id} className="text-white/80">
                  <td className="py-2 pr-4 font-mono text-xs">{u.email}</td>
                  <td className="py-2 pr-4">{u.display_name}</td>
                  <td className="py-2 pr-4">
                    <span className={`font-mono text-xs uppercase ${u.role === "admin" ? "text-accent" : "text-white/48"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <span className={u.is_active ? "text-emerald-400 text-xs" : "text-rose-400 text-xs"}>
                      {u.is_active ? "active" : "inactive"}
                    </span>
                  </td>
                  <td className="py-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => { setResetTarget(u.id); setResetPw(""); }}
                      className="text-xs border border-white/10 px-2 py-1 hover:border-accent/60 hover:text-accent rounded"
                    >
                      Reset PW
                    </button>
                    {u.id !== me?.id ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => onToggleActive(u)}
                        className={`text-xs border px-2 py-1 rounded disabled:opacity-50 ${
                          u.is_active
                            ? "border-rose-400/40 text-rose-300 hover:bg-rose-400/10"
                            : "border-emerald-400/40 text-emerald-300 hover:bg-emerald-400/10"
                        }`}
                      >
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Password reset modal */}
        {resetTarget ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="w-full max-w-sm rounded-[24px] border border-white/10 bg-[#0d0f1a] p-6 shadow-xl">
              <h3 className="text-sm font-semibold text-white mb-4">Reset password</h3>
              <form onSubmit={onResetPassword} className="space-y-4">
                <div>
                  <label className="block text-xs uppercase tracking-[0.3em] text-white/48 mb-1">New password</label>
                  <input
                    type="password" required minLength={8} autoFocus
                    value={resetPw} onChange={(e) => setResetPw(e.target.value)}
                    className="w-full rounded-md border border-white/10 bg-black/30 p-2 text-sm text-white"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="submit" disabled={busy}
                    className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-black disabled:opacity-50"
                  >
                    {busy ? "Saving…" : "Set password"}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setResetTarget(null); setResetPw(""); }}
                    className="rounded-md border border-white/10 px-4 py-2 text-sm text-white/60 hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
