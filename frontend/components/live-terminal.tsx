"use client";

import { useEffect, useRef } from "react";
import type { Terminal as XTermTerminal } from "@xterm/xterm";
import type { FitAddon as XTermFitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

import type { ExecutionEvent } from "../lib/api";

type LiveTerminalProps = {
  events: ExecutionEvent[];
};

const ANSI = {
  reset: "\x1b[0m",
  dim: "\x1b[2m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  gray: "\x1b[90m",
};

function formatHeader(event: ExecutionEvent): string | null {
  const stamp = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "";
  switch (event.type) {
    case "started":
      return `${ANSI.cyan}[${stamp}] ▶ started${event.tool ? ` ${event.tool} ${event.operation ?? ""}` : ""}${
        event.targets?.length ? ` → ${event.targets.join(", ")}` : ""
      }${ANSI.reset}`;
    case "completed":
      return `${ANSI.green}[${stamp}] ✔ completed (exit ${event.exit_code ?? 0})${ANSI.reset}`;
    case "failed":
      return `${ANSI.red}[${stamp}] ✖ failed${event.error ? `: ${event.error}` : ""}${ANSI.reset}`;
    case "cancelled":
      return `${ANSI.yellow}[${stamp}] ⏹ cancelled${ANSI.reset}`;
    case "timed_out":
      return `${ANSI.yellow}[${stamp}] ⏱ timed out (${event.timeout_seconds ?? "?"}s)${ANSI.reset}`;
    default:
      return null;
  }
}

function formatLine(event: ExecutionEvent): string | null {
  if (!event.line) return null;
  if (event.type === "stderr") return `${ANSI.red}${event.line}${ANSI.reset}`;
  return event.line;
}

export function LiveTerminal({ events }: LiveTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const termRef = useRef<XTermTerminal | null>(null);
  const fitRef = useRef<XTermFitAddon | null>(null);
  const writtenCountRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      const [{ Terminal }, { FitAddon }] = await Promise.all([
        import("@xterm/xterm"),
        import("@xterm/addon-fit"),
      ]);
      if (cancelled || !containerRef.current) return;

      const term = new Terminal({
        convertEol: true,
        cursorBlink: false,
        disableStdin: true,
        fontFamily:
          'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace',
        fontSize: 12,
        theme: {
          background: "#0b0d0f",
          foreground: "#e7f0e1",
          cursor: "#c8ff74",
          black: "#1d2125",
          brightBlack: "#59636b",
        },
        scrollback: 5000,
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(containerRef.current);
      try {
        fit.fit();
      } catch {
        /* container not sized yet */
      }
      termRef.current = term;
      fitRef.current = fit;

      const onResize = () => {
        try {
          fit.fit();
        } catch {
          /* ignore */
        }
      };
      window.addEventListener("resize", onResize);
      (term as unknown as { __onResize: () => void }).__onResize = onResize;
    }
    void boot();
    return () => {
      cancelled = true;
      const term = termRef.current;
      if (term) {
        const onResize = (term as unknown as { __onResize?: () => void }).__onResize;
        if (onResize) window.removeEventListener("resize", onResize);
        term.dispose();
      }
      termRef.current = null;
      fitRef.current = null;
      writtenCountRef.current = 0;
    };
  }, []);

  useEffect(() => {
    const term = termRef.current;
    if (!term) return;
    if (events.length < writtenCountRef.current) {
      term.reset();
      writtenCountRef.current = 0;
    }
    for (let i = writtenCountRef.current; i < events.length; i += 1) {
      const event = events[i];
      const header = formatHeader(event);
      if (header) term.writeln(header);
      const line = formatLine(event);
      if (line !== null) term.writeln(line);
    }
    writtenCountRef.current = events.length;
    try {
      fitRef.current?.fit();
    } catch {
      /* ignore */
    }
  }, [events]);

  return (
    <div
      ref={containerRef}
      className="h-[420px] w-full rounded-2xl border border-white/10 bg-black/60 p-2"
    />
  );
}
