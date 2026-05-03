"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { ChatMessage, streamChat } from "@/lib/api";

const SUGGESTIONS = [
  "How do I create my first engagement?",
  "What is SQL injection and how to prevent it?",
  "Explain the 3-layer scope enforcement in PentAI Pro.",
  "How do I approve an exploit action?",
  "What does a critical finding mean?",
  "How does mTLS protect the Weapon Node?",
];

type Message = ChatMessage & { id: string; streaming?: boolean };

function uid() {
  return Math.random().toString(36).slice(2);
}

export default function ChatWidget() {
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      setAuthed(!!session);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthed(!!session);
    });
    return () => subscription.unsubscribe();
  }, []);

  if (!authed) return null;

  return <ChatWidgetInner />;
}

function ChatWidgetInner() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 120);
  }, [open]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;

      setError(null);
      const userMsg: Message = { id: uid(), role: "user", content: trimmed };
      const assistantId = uid();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInput("");
      setBusy(true);

      const history: ChatMessage[] = [
        ...messages.map(({ role, content }) => ({ role, content })),
        { role: "user", content: trimmed },
      ];

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await streamChat(
          history,
          (chunk) => {
            if (chunk.error) {
              setError(chunk.error);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: "Sorry, an error occurred. Please try again.", streaming: false }
                    : m,
                ),
              );
              return;
            }
            if (chunk.delta) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + chunk.delta }
                    : m,
                ),
              );
            }
            if (chunk.done) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, streaming: false } : m,
                ),
              );
            }
          },
          ctrl.signal,
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          const msg = err instanceof Error ? err.message : "Connection failed.";
          setError(msg);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: "Unable to get a response. Check that Ollama is running.", streaming: false }
                : m,
            ),
          );
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, messages],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  }

  function stopStream() {
    abortRef.current?.abort();
    setBusy(false);
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    );
  }

  function clearChat() {
    abortRef.current?.abort();
    setBusy(false);
    setMessages([]);
    setError(null);
  }

  const isEmpty = messages.length === 0;

  return (
    <>
      <style>{`
        /* ── Widget container ── */
        .cw-root {
          position: fixed;
          bottom: 80px;
          left: 20px;
          z-index: 9999;
          font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
        }
        @media (max-width: 480px) {
          .cw-root { bottom: 0; left: 0; right: 0; }
        }

        /* ── FAB trigger button ── */
        .cw-fab {
          width: 52px; height: 52px;
          background: #4F8EF7;
          border: none; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          box-shadow: 0 4px 20px rgba(79,142,247,0.4);
          transition: filter 0.2s, transform 0.2s;
          position: relative;
        }
        .cw-fab:hover { filter: brightness(1.15); transform: scale(1.05); }
        .cw-fab .material-symbols-outlined { font-size: 22px; color: #fff; }
        .cw-fab-badge {
          position: absolute; top: -4px; right: -4px;
          width: 16px; height: 16px;
          background: #00D9A3;
          display: flex; align-items: center; justify-content: center;
          font-family: 'JetBrains Mono', monospace;
          font-size: 9px; font-weight: 700; color: #0A0B0F;
        }
        .cw-fab-tooltip {
          position: absolute;
          left: calc(100% + 10px); bottom: 50%; transform: translateY(50%);
          background: #1C1F2E;
          border: 1px solid #252836;
          padding: 5px 10px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px; color: #9AA0B4;
          white-space: nowrap;
          pointer-events: none; opacity: 0;
          transition: opacity 0.15s;
        }
        .cw-fab:hover .cw-fab-tooltip { opacity: 1; }
        @media (max-width: 480px) {
          .cw-fab { display: none; }
        }

        /* ── Panel ── */
        .cw-panel {
          position: absolute;
          bottom: 64px; left: 0;
          width: 380px;
          max-height: min(560px, calc(100svh - 120px));
          background: #141620;
          border: 1px solid #252836;
          display: flex; flex-direction: column;
          box-shadow: 0 8px 40px rgba(0,0,0,0.6);
          animation: cw-slide-up 0.18s ease;
        }
        @keyframes cw-slide-up {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @media (max-width: 480px) {
          .cw-panel {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            width: 100%; max-height: 80svh;
            border-bottom: none;
          }
        }

        /* Panel header */
        .cw-header {
          display: flex; align-items: center; gap: 10px;
          padding: 12px 14px;
          border-bottom: 1px solid #252836;
          flex-shrink: 0;
          background: #0A0B0F;
        }
        .cw-header-icon {
          width: 30px; height: 30px;
          background: rgba(79,142,247,0.12);
          border: 1px solid rgba(79,142,247,0.25);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .cw-header-icon .material-symbols-outlined { font-size: 16px; color: #4F8EF7; }
        .cw-header-info { flex: 1; min-width: 0; }
        .cw-header-title {
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px; font-weight: 700;
          color: #E8EAED;
          text-transform: uppercase; letter-spacing: 1px;
          margin: 0;
        }
        .cw-header-sub {
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px; color: #5C6378;
          text-transform: uppercase; letter-spacing: 1px;
          margin: 2px 0 0;
        }
        .cw-header-sub .dot { color: #00D9A3; }
        .cw-header-actions { display: flex; gap: 4px; }
        .cw-icon-btn {
          width: 28px; height: 28px;
          background: transparent; border: 1px solid transparent;
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          color: #5C6378; transition: all 0.15s;
        }
        .cw-icon-btn:hover { color: #E8EAED; border-color: #252836; background: #1C1F2E; }
        .cw-icon-btn .material-symbols-outlined { font-size: 16px; }

        /* Messages */
        .cw-messages {
          flex: 1; overflow-y: auto;
          padding: 14px;
          display: flex; flex-direction: column; gap: 14px;
          scrollbar-width: thin; scrollbar-color: #252836 transparent;
        }
        .cw-messages::-webkit-scrollbar { width: 4px; }
        .cw-messages::-webkit-scrollbar-thumb { background: #252836; }

        /* Empty / suggestions */
        .cw-empty {
          display: flex; flex-direction: column; align-items: center;
          gap: 14px; padding: 8px 0;
        }
        .cw-empty-icon {
          width: 48px; height: 48px;
          background: rgba(79,142,247,0.08);
          border: 1px solid rgba(79,142,247,0.2);
          display: flex; align-items: center; justify-content: center;
        }
        .cw-empty-icon .material-symbols-outlined { font-size: 24px; color: #4F8EF7; }
        .cw-empty-title {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px; font-weight: 700;
          color: #E8EAED; text-transform: uppercase; letter-spacing: 1px;
          text-align: center; margin: 0;
        }
        .cw-empty-sub {
          font-size: 12px; color: #5C6378;
          text-align: center; max-width: 260px;
          line-height: 1.5; margin: 0;
        }
        .cw-suggestions { width: 100%; display: flex; flex-direction: column; gap: 6px; }
        .cw-suggestion {
          width: 100%; text-align: left;
          padding: 9px 12px;
          background: #1C1F2E;
          border: 1px solid #252836;
          color: #9AA0B4; font-size: 12px; line-height: 1.4;
          cursor: pointer; transition: all 0.15s;
        }
        .cw-suggestion:hover { border-color: #4F8EF7; color: #E8EAED; background: rgba(79,142,247,0.06); }

        /* Message bubbles */
        .cw-msg { display: flex; flex-direction: column; gap: 4px; }
        .cw-msg-user { align-items: flex-end; }
        .cw-msg-assistant { align-items: flex-start; }

        .cw-bubble {
          max-width: 88%;
          padding: 10px 13px;
          font-size: 13px; line-height: 1.6;
          word-break: break-word;
        }
        .cw-bubble-user {
          background: #4F8EF7;
          color: #fff;
          border: 1px solid transparent;
        }
        .cw-bubble-assistant {
          background: #1C1F2E;
          color: #E8EAED;
          border: 1px solid #252836;
        }
        .cw-bubble-assistant code {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          background: #0A0B0F;
          border: 1px solid #252836;
          padding: 1px 5px;
          color: #00D9A3;
        }
        .cw-bubble-assistant pre {
          background: #0A0B0F;
          border: 1px solid #252836;
          padding: 10px 12px;
          overflow-x: auto;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #00D9A3;
          margin: 6px 0;
        }
        .cw-bubble-assistant pre code {
          background: none; border: none; padding: 0;
        }

        /* Cursor blink when streaming */
        .cw-cursor::after {
          content: '▋';
          color: #4F8EF7;
          animation: cw-blink 0.8s step-start infinite;
          margin-left: 1px;
        }
        @keyframes cw-blink { 0%,100%{opacity:1} 50%{opacity:0} }

        /* Timestamp */
        .cw-meta {
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px; color: #5C6378;
          padding: 0 2px;
        }

        /* Error banner */
        .cw-error {
          margin: 0 14px 8px;
          padding: 8px 12px;
          border: 1px solid rgba(255,51,102,0.3);
          background: rgba(255,51,102,0.06);
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px; color: #FF3366;
          display: flex; align-items: center; gap: 8px;
          flex-shrink: 0;
        }
        .cw-error .material-symbols-outlined { font-size: 14px; flex-shrink: 0; }

        /* Input area */
        .cw-input-area {
          border-top: 1px solid #252836;
          padding: 10px 12px;
          flex-shrink: 0;
          background: #0A0B0F;
        }
        .cw-input-row {
          display: flex; gap: 8px; align-items: flex-end;
        }
        .cw-textarea {
          flex: 1;
          min-height: 40px; max-height: 120px;
          padding: 10px 12px;
          background: #141620;
          border: 1px solid #252836;
          color: #E8EAED;
          font-family: 'Inter', sans-serif;
          font-size: 13px; line-height: 1.5;
          resize: none; outline: none;
          transition: border-color 0.15s;
          -webkit-appearance: none; appearance: none;
          overflow-y: auto;
          scrollbar-width: thin; scrollbar-color: #252836 transparent;
        }
        .cw-textarea::placeholder { color: #5C6378; }
        .cw-textarea:focus { border-color: #4F8EF7; }

        .cw-send-btn {
          width: 40px; height: 40px; flex-shrink: 0;
          background: #4F8EF7; border: none; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: filter 0.15s;
        }
        .cw-send-btn:hover:not(:disabled) { filter: brightness(1.15); }
        .cw-send-btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .cw-send-btn .material-symbols-outlined { font-size: 18px; color: #fff; }

        .cw-stop-btn {
          width: 40px; height: 40px; flex-shrink: 0;
          background: transparent;
          border: 1px solid rgba(255,51,102,0.4);
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: all 0.15s;
        }
        .cw-stop-btn:hover { background: rgba(255,51,102,0.08); border-color: #FF3366; }
        .cw-stop-btn .material-symbols-outlined { font-size: 18px; color: #FF3366; }

        .cw-hint {
          margin-top: 6px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px; color: #5C6378;
          text-align: right;
        }

        /* Mobile open button */
        .cw-mobile-bar {
          display: none;
          position: fixed; bottom: 0; left: 0; right: 0;
          height: 52px;
          background: #4F8EF7;
          align-items: center; justify-content: center; gap: 10px;
          cursor: pointer; z-index: 9998;
          border: none;
        }
        .cw-mobile-bar .material-symbols-outlined { font-size: 20px; color: #fff; }
        .cw-mobile-bar span.label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px; font-weight: 700;
          color: #fff; text-transform: uppercase; letter-spacing: 1.5px;
        }
        @media (max-width: 480px) {
          .cw-mobile-bar { display: flex; }
        }
      `}</style>

      <div className="cw-root">
        {/* Desktop FAB */}
        {!open && (
          <button
            className="cw-fab"
            onClick={() => setOpen(true)}
            aria-label="Open AI assistant"
            type="button"
          >
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
              smart_toy
            </span>
            <span className="cw-fab-badge">AI</span>
            <span className="cw-fab-tooltip">PentAI Assistant</span>
          </button>
        )}

        {/* Chat panel */}
        {open && (
          <div className="cw-panel" role="dialog" aria-label="PentAI AI Assistant">
            {/* Header */}
            <div className="cw-header">
              <div className="cw-header-icon">
                <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
                  smart_toy
                </span>
              </div>
              <div className="cw-header-info">
                <p className="cw-header-title">PentAI Assistant</p>
                <p className="cw-header-sub">
                  <span className="dot">●</span> qwen2.5:14b · Local LLM
                </p>
              </div>
              <div className="cw-header-actions">
                {messages.length > 0 && (
                  <button
                    className="cw-icon-btn"
                    onClick={clearChat}
                    title="Clear conversation"
                    type="button"
                    aria-label="Clear conversation"
                  >
                    <span className="material-symbols-outlined">delete_sweep</span>
                  </button>
                )}
                <button
                  className="cw-icon-btn"
                  onClick={() => setOpen(false)}
                  title="Close"
                  type="button"
                  aria-label="Close assistant"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="cw-messages">
              {isEmpty ? (
                <div className="cw-empty">
                  <div className="cw-empty-icon">
                    <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
                      security
                    </span>
                  </div>
                  <p className="cw-empty-title">Cybersecurity AI</p>
                  <p className="cw-empty-sub">
                    Ask anything about PentAI Pro or cybersecurity. Running locally — no data leaves your server.
                  </p>
                  <div className="cw-suggestions">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        className="cw-suggestion"
                        onClick={() => void sendMessage(s)}
                        type="button"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`cw-msg ${msg.role === "user" ? "cw-msg-user" : "cw-msg-assistant"}`}
                  >
                    <div
                      className={`cw-bubble ${
                        msg.role === "user" ? "cw-bubble-user" : "cw-bubble-assistant"
                      }${msg.streaming ? " cw-cursor" : ""}`}
                    >
                      <FormattedMessage content={msg.content} isUser={msg.role === "user"} />
                    </div>
                  </div>
                ))
              )}
              <div ref={bottomRef} />
            </div>

            {/* Error */}
            {error && (
              <div className="cw-error">
                <span className="material-symbols-outlined">error</span>
                {error}
              </div>
            )}

            {/* Input */}
            <div className="cw-input-area">
              <div className="cw-input-row">
                <textarea
                  ref={inputRef}
                  className="cw-textarea"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about PentAI Pro or cybersecurity…"
                  rows={1}
                  disabled={busy}
                  aria-label="Message input"
                />
                {busy ? (
                  <button
                    className="cw-stop-btn"
                    onClick={stopStream}
                    type="button"
                    aria-label="Stop generating"
                  >
                    <span className="material-symbols-outlined">stop</span>
                  </button>
                ) : (
                  <button
                    className="cw-send-btn"
                    onClick={() => void sendMessage(input)}
                    disabled={!input.trim()}
                    type="button"
                    aria-label="Send message"
                  >
                    <span className="material-symbols-outlined">send</span>
                  </button>
                )}
              </div>
              <p className="cw-hint">Enter to send · Shift+Enter for new line</p>
            </div>
          </div>
        )}
      </div>

      {/* Mobile bottom bar */}
      <button
        className="cw-mobile-bar"
        onClick={() => setOpen((v) => !v)}
        type="button"
        aria-label="Toggle AI assistant"
      >
        <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
          smart_toy
        </span>
        <span className="label">PentAI Assistant</span>
        <span className="material-symbols-outlined" style={{ fontSize: "16px", color: "rgba(255,255,255,0.7)" }}>
          {open ? "expand_more" : "expand_less"}
        </span>
      </button>
    </>
  );
}

/* Renders assistant message with basic markdown-like formatting */
function FormattedMessage({ content, isUser }: { content: string; isUser: boolean }) {
  if (isUser) return <>{content}</>;
  if (!content) return null;

  // Split on code blocks first
  const parts = content.split(/(```[\s\S]*?```)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("```")) {
          const lines = part.slice(3, -3).split("\n");
          const lang = lines[0]?.trim() || "";
          const code = (lang ? lines.slice(1) : lines).join("\n").trim();
          return (
            <pre key={i}>
              <code>{code}</code>
            </pre>
          );
        }
        // Inline formatting: **bold**, `code`, line breaks
        const segments = part.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
        return (
          <span key={i}>
            {segments.map((seg, j) => {
              if (seg.startsWith("`") && seg.endsWith("`"))
                return <code key={j}>{seg.slice(1, -1)}</code>;
              if (seg.startsWith("**") && seg.endsWith("**"))
                return <strong key={j}>{seg.slice(2, -2)}</strong>;
              return seg.split("\n").map((line, k) => (
                <span key={k}>
                  {line}
                  {k < seg.split("\n").length - 1 && <br />}
                </span>
              ));
            })}
          </span>
        );
      })}
    </>
  );
}
