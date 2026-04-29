"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  KnowledgeHit,
  KnowledgeSource,
  deleteKnowledgeSource,
  ingestKnowledgeSource,
  listKnowledgeSources,
  searchKnowledge,
} from "@/lib/api";

export default function KnowledgeBasePage() {
  const [filename, setFilename] = useState("");
  const [content, setContent] = useState("");
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);

  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<KnowledgeHit[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [sourcesError, setSourcesError] = useState<string | null>(null);

  const refreshSources = useCallback(async () => {
    try {
      setSources(await listKnowledgeSources());
      setSourcesError(null);
    } catch (err) {
      setSourcesError(String(err));
    }
  }, []);

  useEffect(() => {
    refreshSources();
  }, [refreshSources]);

  async function onDeleteSource(sourcePath: string) {
    if (!window.confirm(`Delete all chunks from ${sourcePath}?`)) return;
    try {
      await deleteKnowledgeSource(sourcePath);
      await refreshSources();
    } catch (err) {
      setSourcesError(String(err));
    }
  }

  async function onIngest(e: React.FormEvent) {
    e.preventDefault();
    setIngestStatus(null);
    setIngestError(null);
    setIngesting(true);
    try {
      const res = await ingestKnowledgeSource(filename, content);
      setIngestStatus(
        res.skipped
          ? `Skipped ${res.source_path} (no extractable content).`
          : `Ingested ${res.source_path} — ${res.chunks_written} chunk(s) written.`,
      );
      setContent("");
      await refreshSources();
    } catch (err) {
      setIngestError(String(err));
    } finally {
      setIngesting(false);
    }
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearchError(null);
    setSearching(true);
    try {
      const res = await searchKnowledge(query, 5, 0);
      setHits(res.hits);
    } catch (err) {
      setSearchError(String(err));
    } finally {
      setSearching(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-gutter">
        <div>
          <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
            Operator Knowledge
          </div>
          <h1 className="font-display text-[24px] font-semibold text-text-primary uppercase tracking-tight">
            Knowledge Base · v1
          </h1>
          <p className="mt-2 font-mono text-[11px] text-text-tertiary max-w-2xl leading-relaxed">
            Ingest playbook markdown into the local vector store. Retrieved
            chunks ground the recon planner&apos;s tool selection and feed
            citation footnotes onto every PlannedStep.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-gutter">
          <section className="border border-border-subtle bg-surface-secondary p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                Upload Markdown Source
              </span>
              <span className="material-symbols-outlined text-[18px] text-text-tertiary">
                upload_file
              </span>
            </div>
            <form onSubmit={onIngest} className="space-y-3">
              <label className="block">
                <span className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary">
                  Filename (e.g. recon-playbook.md)
                </span>
                <input
                  type="text"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  pattern="[A-Za-z0-9._\-]+\.md"
                  required
                  placeholder="recon-playbook.md"
                  className="mt-1 w-full bg-bg-primary border border-border-subtle px-2 py-1 font-mono text-[12px] text-text-primary"
                />
              </label>
              <label className="block">
                <span className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary">
                  Markdown Content
                </span>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  required
                  rows={10}
                  placeholder="# Recon Playbook&#10;&#10;Use nmap service scan against..."
                  className="mt-1 w-full bg-bg-primary border border-border-subtle px-2 py-2 font-mono text-[12px] text-text-primary resize-y"
                />
              </label>
              <button
                type="submit"
                disabled={ingesting}
                className="px-3 py-1.5 bg-primary text-bg-primary font-display text-[11px] uppercase tracking-widest font-semibold disabled:opacity-50"
              >
                {ingesting ? "Ingesting…" : "Ingest"}
              </button>
              {ingestStatus && (
                <div className="border border-secondary/50 bg-secondary/10 p-2 font-mono text-[11px] text-secondary">
                  {ingestStatus}
                </div>
              )}
              {ingestError && (
                <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
                  {ingestError}
                </div>
              )}
            </form>
          </section>

          <section className="border border-border-subtle bg-surface-secondary p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
                Semantic Search
              </span>
              <span className="material-symbols-outlined text-[18px] text-text-tertiary">
                manage_search
              </span>
            </div>
            <form onSubmit={onSearch} className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                required
                placeholder="nmap service scan"
                className="flex-1 bg-bg-primary border border-border-subtle px-2 py-1 font-mono text-[12px] text-text-primary"
              />
              <button
                type="submit"
                disabled={searching}
                className="px-3 py-1.5 bg-primary text-bg-primary font-display text-[11px] uppercase tracking-widest font-semibold disabled:opacity-50"
              >
                {searching ? "…" : "Search"}
              </button>
            </form>
            {searchError && (
              <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
                {searchError}
              </div>
            )}
            <div className="space-y-2 max-h-[55vh] overflow-y-auto">
              {hits.length === 0 && !searching && (
                <div className="font-mono text-[11px] text-text-tertiary">
                  No hits yet. Submit a query above.
                </div>
              )}
              {hits.map((hit, i) => (
                <div
                  key={`${hit.source_path}-${i}`}
                  className="border border-border-subtle bg-bg-primary p-2 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-widest">
                      [{i + 1}] {hit.source_path}
                      {hit.title ? ` · ${hit.title}` : ""}
                    </span>
                    <span className="font-mono text-[10px] text-secondary">
                      {hit.score.toFixed(3)}
                    </span>
                  </div>
                  <pre className="font-mono text-[11px] text-text-primary whitespace-pre-wrap leading-relaxed">
                    {hit.content}
                  </pre>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="border border-border-subtle bg-surface-secondary p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-display text-[11px] uppercase tracking-widest text-text-primary font-semibold">
              Indexed Sources ({sources.length})
            </span>
            <button
              type="button"
              onClick={refreshSources}
              className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary hover:text-text-primary"
            >
              Refresh
            </button>
          </div>
          {sourcesError && (
            <div className="border border-severity-critical/50 bg-severity-critical/10 p-2 font-mono text-[11px] text-severity-critical">
              {sourcesError}
            </div>
          )}
          {sources.length === 0 ? (
            <div className="font-mono text-[11px] text-text-tertiary">
              No sources ingested yet.
            </div>
          ) : (
            <div className="border border-border-subtle">
              <div className="px-3 py-2 grid grid-cols-[1fr_auto_auto_auto] gap-4 border-b border-border-subtle bg-surface-tertiary font-display text-[10px] uppercase tracking-widest text-text-tertiary">
                <span>Source Path</span>
                <span>Chunks</span>
                <span>Updated</span>
                <span></span>
              </div>
              <div className="divide-y divide-border-subtle/50">
                {sources.map((s) => (
                  <div
                    key={s.source_path}
                    className="px-3 py-2 grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center"
                  >
                    <span className="font-mono text-[11px] text-text-primary truncate">
                      {s.source_path}
                    </span>
                    <span className="font-mono text-[11px] text-text-secondary">
                      {s.chunk_count}
                    </span>
                    <span className="font-mono text-[10px] text-text-tertiary">
                      {s.updated_at ? new Date(s.updated_at).toISOString().slice(0, 19) : "—"}
                    </span>
                    <button
                      type="button"
                      onClick={() => onDeleteSource(s.source_path)}
                      className="px-2 py-0.5 font-display text-[10px] uppercase tracking-widest text-severity-critical hover:bg-severity-critical/10"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
