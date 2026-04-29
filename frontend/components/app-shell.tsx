"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createClient } from "@/lib/supabase/client";

type NavItem = {
  href: string;
  label: string;
  icon: string;
  match?: (pathname: string) => boolean;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", icon: "dashboard", match: (p) => p === "/" },
  { href: "/engagements", label: "Engagements", icon: "security", match: (p) => p === "/engagements" },
  { href: "/engagements/new", label: "New Engagement", icon: "add_circle" },
  { href: "/audit", label: "Audit Log", icon: "receipt_long" },
  { href: "/engagements/console", label: "Op Console", icon: "terminal" },
  { href: "/engagements/agent", label: "Agent Run", icon: "smart_toy" },
  { href: "/knowledge", label: "Knowledge Base", icon: "library_books" },
  { href: "/reports", label: "Reports", icon: "summarize" },
  { href: "/users", label: "Users", icon: "manage_accounts" },
];

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const [search, setSearch] = useState("");
  const pathname = usePathname() ?? "/";

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <TopBar search={search} onSearchChange={setSearch} />
      <SideNav pathname={pathname} />
      <main className="ml-[240px] mt-14 px-gutter py-gutter space-y-gutter">
        {children}
      </main>
    </div>
  );
}

type TopBarProps = {
  search: string;
  onSearchChange: (value: string) => void;
};

function TopBar({ search, onSearchChange }: TopBarProps) {
  const router = useRouter();
  const [userInitial, setUserInitial] = useState("?");
  const [userEmail, setUserEmail] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) return;
      const name: string =
        user.user_metadata?.display_name ||
        user.email ||
        "?";
      setUserInitial(name[0].toUpperCase());
      setUserEmail(user.email ?? "");
    });
  }, []);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="fixed top-0 inset-x-0 h-14 border-b border-border-subtle bg-bg-primary z-50 flex items-center justify-between px-4">
      <div className="flex items-center gap-6">
        <span className="font-display font-bold text-lg tracking-tight text-text-primary">
          PentAI Pro
        </span>
        <div className="hidden md:flex items-center bg-surface-secondary border border-border-subtle px-3 py-1 w-80 gap-2">
          <span className="material-symbols-outlined text-text-tertiary text-base">
            search
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search infrastructure..."
            className="bg-transparent border-none outline-none focus:ring-0 text-xs text-text-secondary w-full placeholder:text-text-tertiary font-mono"
          />
          <span className="text-[9px] text-text-tertiary border border-border-subtle px-1 font-mono">
            ⌘K
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-2 py-1 bg-surface-secondary border border-border-subtle">
          <div className="w-1.5 h-1.5 bg-secondary" />
          <span className="font-display font-bold text-[10px] uppercase tracking-wider text-primary">
            System Online
          </span>
        </div>

        <Link
          href="/engagements/new"
          className="bg-primary text-white px-3 py-1 font-display font-bold text-[11px] uppercase tracking-wider hover:brightness-110 active:brightness-95 transition"
        >
          Deploy Agent
        </Link>

        <div className="flex items-center gap-3 ml-1 border-l border-border-subtle pl-3">
          <button
            type="button"
            aria-label="Notifications"
            className="text-text-secondary hover:text-text-primary transition"
          >
            <span className="material-symbols-outlined">notifications</span>
          </button>
          <Link
            href={"/users" as Route}
            aria-label="Settings"
            className="text-text-secondary hover:text-text-primary transition"
          >
            <span className="material-symbols-outlined">settings</span>
          </Link>

          {/* User avatar + dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              aria-label="Account menu"
              onClick={() => setMenuOpen((o) => !o)}
              className="w-6 h-6 border border-primary bg-surface-tertiary flex items-center justify-center text-[10px] font-display font-bold text-primary hover:brightness-125 transition"
            >
              {userInitial}
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-8 w-48 bg-surface-secondary border border-border-subtle z-50 shadow-lg">
                <div className="px-3 py-2 border-b border-border-subtle">
                  <p className="font-mono text-[9px] text-text-tertiary uppercase tracking-widest">
                    Signed in as
                  </p>
                  <p className="font-mono text-[10px] text-text-primary truncate mt-0.5">
                    {userEmail || "—"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2 px-3 py-2 font-mono text-[10px] text-text-secondary hover:text-severity-critical hover:bg-severity-critical/5 transition uppercase tracking-wider"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
                    logout
                  </span>
                  Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

type SideNavProps = {
  pathname: string;
};

function isActive(item: NavItem, pathname: string): boolean {
  if (item.match) return item.match(pathname);
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

function SideNav({ pathname }: SideNavProps) {
  return (
    <aside className="fixed left-0 top-0 h-full w-[240px] border-r border-border-subtle bg-bg-primary flex flex-col z-40 mt-14 py-4">
      <div className="mb-4 px-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-surface-tertiary border border-border-accent flex items-center justify-center">
            <span
              className="material-symbols-outlined text-primary text-base"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              security
            </span>
          </div>
          <div>
            <div className="font-display font-black text-primary text-[10px] uppercase tracking-wider">
              PentAI Pro
            </div>
            <div className="text-[9px] text-text-tertiary uppercase tracking-widest font-medium">
              Ops-Command
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto custom-scrollbar">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item, pathname);
          return (
            <Link
              key={item.href}
              href={item.href as Route}
              className={`flex items-center gap-3 px-4 py-2 border-r-2 transition-none ${
                active
                  ? "bg-surface-secondary text-primary border-primary"
                  : "text-text-tertiary border-transparent hover:bg-surface-secondary hover:text-text-primary"
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">
                {item.icon}
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider">
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-border-subtle pt-2">
        <Link
          href={"/audit" as Route}
          className="flex items-center gap-3 px-4 py-1.5 text-text-tertiary hover:text-text-primary transition"
        >
          <span className="material-symbols-outlined text-[16px]">receipt_long</span>
          <span className="text-[9px] font-medium uppercase tracking-widest">SysLogs</span>
        </Link>
      </div>
    </aside>
  );
}
