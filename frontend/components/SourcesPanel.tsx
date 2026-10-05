"use client";

import { useEffect, useRef, useState } from "react";
import { fetchSection, sectionLabel, type Section, type Source } from "@/lib/api";

const RANK_LABELS: Record<string, string> = { vector: "vector", bm25: "BM25", fused: "hybrid", rerank: "rerank" };

export function SourcesPanel({
  sources,
  cited,
  active,
  query,
  timings,
}: {
  sources: Source[];
  cited: Set<number>;
  active: number | null;
  query?: string;
  timings?: Record<string, number>;
}) {
  const refs = useRef<Record<number, HTMLLIElement | null>>({});
  const [open, setOpen] = useState<Section | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    if (active != null) refs.current[active]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  async function openSection(id: string) {
    setLoading(id);
    try {
      setOpen(await fetchSection(id));
    } finally {
      setLoading(null);
    }
  }

  if (!sources.length) {
    return <p className="p-4 text-sm text-muted">Sources for the selected answer appear here.</p>;
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="text-xs text-muted">
        {query && (
          <p className="mb-1">
            Searched for: <span className="text-foreground">{query}</span>
          </p>
        )}
        {timings && <Timings timings={timings} />}
      </div>
      <ol className="flex flex-col gap-3">
        {sources.map((s) => {
          const isCited = cited.has(s.n);
          return (
            <li
              key={s.chunk_id}
              ref={(el) => {
                refs.current[s.n] = el;
              }}
              className={`rounded-lg border bg-surface p-3 transition ${
                active === s.n ? "border-accent ring-1 ring-accent" : "border-border"
              } ${!isCited && cited.size ? "opacity-70" : ""}`}
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-accent-soft px-1 font-mono text-[11px] font-medium text-accent">
                  {s.n}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{sectionLabel(s)}</p>
                  <p className="text-sm text-muted">{s.title}</p>
                </div>
                {isCited && <span className="rounded bg-emerald-600/10 px-1.5 py-0.5 text-[11px] text-emerald-700 dark:text-emerald-400">cited</span>}
              </div>
              <p className="statute mt-2 line-clamp-6 text-[13px] text-foreground/85">{s.content}</p>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
                {Object.entries(s.ranks).map(([k, v]) => (
                  <span key={k}>
                    {RANK_LABELS[k] ?? k} #{v}
                  </span>
                ))}
                <span>score {s.score.toFixed(3)}</span>
                <span className="flex-1" />
                <button onClick={() => openSection(s.section_id)} className="text-accent hover:underline">
                  {loading === s.section_id ? "Loading…" : "Full section"}
                </button>
                <a href={s.source_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  India Code ↗
                </a>
              </div>
            </li>
          );
        })}
      </ol>
      {open && <SectionModal section={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function Timings({ timings }: { timings: Record<string, number> }) {
  const order = ["rewrite", "vector", "bm25", "rerank", "first_token", "total"];
  const label: Record<string, string> = { first_token: "first token", total: "total", rerank: "rerank" };
  return (
    <p className="flex flex-wrap gap-x-3 font-mono">
      {order
        .filter((k) => timings[k] != null)
        .map((k) => (
          <span key={k}>
            {label[k] ?? k} {Math.round(timings[k])}ms
          </span>
        ))}
    </p>
  );
}

function SectionModal({ section, onClose }: { section: Section; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl border border-border bg-surface shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border p-4">
          <div>
            <p className="text-xs text-muted">
              {section.act_name} · {section.chapter}
            </p>
            <h2 className="font-serif text-lg font-semibold">
              {/^\d/.test(section.section) ? `Section ${section.section}. ` : ""}
              {section.title}
            </h2>
          </div>
          <button onClick={onClose} className="rounded px-2 text-xl leading-none text-muted hover:text-foreground" aria-label="Close">
            ×
          </button>
        </div>
        <div className="statute overflow-y-auto p-4 text-[14px]">{section.text}</div>
      </div>
    </div>
  );
}
