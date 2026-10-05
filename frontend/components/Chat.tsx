"use client";

import { useEffect, useRef, useState } from "react";
import { Answer, citedNumbers } from "@/components/Answer";
import { SourcesPanel } from "@/components/SourcesPanel";
import { MODE_LABELS, streamChat, type Mode, type Source, type Turn } from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  query?: string;
  timings?: Record<string, number>;
  error?: string;
  pending?: boolean;
};

const EXAMPLES = [
  { act: "DPDP", q: "What is the maximum penalty if a company fails to protect personal data from a breach?" },
  { act: "DPDP", q: "Can an app show targeted ads to children?" },
  { act: "RTI", q: "How many days does a government office have to answer my RTI application?" },
  { act: "RTI", q: "Does the RTI Act apply to the CBI?" },
  { act: "CPA", q: "Can a celebrity who endorses a misleading ad be penalised?" },
  { act: "CPA", q: "How long after a problem with a product do I have to file a consumer case?" },
];

const uid = () => Math.random().toString(36).slice(2);

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("hybrid_rerank");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeCite, setActiveCite] = useState<number | null>(null);
  const [showSourcesMobile, setShowSourcesMobile] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const update = (id: string, fn: (m: Message) => Message) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)));

  async function ask(question: string) {
    question = question.trim();
    if (!question || busy) return;
    const history: Turn[] = messages
      .filter((m) => !m.error && m.content)
      .map((m) => ({ role: m.role, content: m.content }));
    const aid = uid();
    setMessages((ms) => [
      ...ms,
      { id: uid(), role: "user", content: question },
      { id: aid, role: "assistant", content: "", pending: true },
    ]);
    setSelected(aid);
    setActiveCite(null);
    setInput("");
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await streamChat(
        { question, history, mode },
        {
          onSources: (query, sources) => update(aid, (m) => ({ ...m, sources, query })),
          onToken: (t) => update(aid, (m) => ({ ...m, content: m.content + t })),
          onDone: ({ timings_ms }) => update(aid, (m) => ({ ...m, timings: timings_ms, pending: false })),
          onError: (message) => update(aid, (m) => ({ ...m, error: message, pending: false })),
        },
        ctrl.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        update(aid, (m) => ({ ...m, error: "Could not reach the API. Is the backend running on :8000?", pending: false }));
      }
    } finally {
      update(aid, (m) => ({ ...m, pending: false }));
      setBusy(false);
    }
  }

  const current = messages.find((m) => m.id === selected);
  const cited = current ? citedNumbers(current.content) : new Set<number>();

  function cite(msgId: string, n: number) {
    setSelected(msgId);
    setActiveCite(n);
    setShowSourcesMobile(true);
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-4">
          {messages.length === 0 ? (
            <EmptyState onPick={ask} />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-6 py-6">
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="self-end rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-[15px] text-background">
                    {m.content}
                  </div>
                ) : (
                  <div
                    key={m.id}
                    onClick={() => setSelected(m.id)}
                    className={`rounded-xl border bg-surface p-4 ${selected === m.id ? "border-accent/40" : "border-border"}`}
                  >
                    {m.pending && !m.content && (
                      <p className="text-sm text-muted">{m.sources ? "Reading the sections…" : "Searching the Acts…"}</p>
                    )}
                    {m.content && <Answer content={m.content} streaming={m.pending} onCite={(n) => cite(m.id, n)} />}
                    {m.error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{m.error}</p>}
                    {m.sources && !m.pending && (
                      <button
                        onClick={() => {
                          setSelected(m.id);
                          setShowSourcesMobile(true);
                        }}
                        className="mt-3 text-xs text-accent hover:underline lg:hidden"
                      >
                        View {m.sources.length} sources
                      </button>
                    )}
                  </div>
                ),
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="shrink-0 border-t border-border bg-background px-4 py-3"
        >
          <div className="mx-auto flex max-w-3xl flex-col gap-2">
            <div className="flex items-end gap-2 rounded-xl border border-border bg-surface p-2 focus-within:border-accent">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask(input);
                  }
                }}
                rows={1}
                placeholder="Ask about the DPDP, RTI or Consumer Protection Act…"
                className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted"
              />
              {busy ? (
                <button type="button" onClick={() => abortRef.current?.abort()} className="rounded-lg border border-border px-4 py-2 text-sm">
                  Stop
                </button>
              ) : (
                <button type="submit" disabled={!input.trim()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-background disabled:opacity-40">
                  Ask
                </button>
              )}
            </div>
            <div className="flex items-center justify-between gap-2 text-xs text-muted">
              <label className="flex items-center gap-2">
                Retrieval
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as Mode)}
                  className="rounded border border-border bg-surface px-1.5 py-1 text-foreground"
                >
                  {(Object.keys(MODE_LABELS) as Mode[]).map((m) => (
                    <option key={m} value={m}>
                      {MODE_LABELS[m]}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-right">Legal information, not legal advice.</span>
            </div>
          </div>
        </form>
      </section>

      <aside
        className={`${
          showSourcesMobile ? "fixed inset-0 z-40 flex" : "hidden"
        } flex-col bg-background lg:static lg:flex lg:w-[420px] lg:shrink-0 lg:border-l lg:border-border`}
      >
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4">
          <h2 className="text-sm font-medium">Sources</h2>
          <button onClick={() => setShowSourcesMobile(false)} className="text-sm text-accent lg:hidden">
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <SourcesPanel
            sources={current?.sources ?? []}
            cited={cited}
            active={activeCite}
            query={current?.query}
            timings={current?.timings}
          />
        </div>
      </aside>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 py-12">
      <div>
        <h1 className="font-serif text-3xl font-semibold tracking-tight">Ask the statute.</h1>
        <p className="mt-2 max-w-xl text-muted">
          Answers are grounded in the official text of the DPDP Act 2023, RTI Act 2005 and Consumer Protection Act 2019,
          and every claim cites the section it came from.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {EXAMPLES.map((e) => (
          <button
            key={e.q}
            onClick={() => onPick(e.q)}
            className="rounded-lg border border-border bg-surface p-3 text-left text-sm hover:border-accent"
          >
            <span className="mb-1 block font-mono text-[11px] text-accent">{e.act}</span>
            {e.q}
          </button>
        ))}
      </div>
    </div>
  );
}
