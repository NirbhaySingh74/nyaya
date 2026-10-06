import type { Metadata } from "next";
import { connection } from "next/server";
import { API_URL, MODE_LABELS, type Mode } from "@/lib/api";

export const metadata: Metadata = { title: "Evaluation — Nyaya" };

type ModeMetrics = {
  "recall@1": number;
  "recall@3": number;
  "recall@5": number;
  "recall@10": number;
  "mrr@10": number;
  latency_ms_p50: number;
  by_split?: Record<"dev" | "test", { n: number; "recall@5": number; "mrr@10": number }>;
  by_type: Record<string, { n: number; "recall@5": number; "mrr@10": number }>;
};

type Meta = {
  acts: { act_id: string; act_name: string; sections: number; chunks: number; source_url: string }[];
  models: Record<string, string>;
  eval: {
    updated: string;
    retrieval?: { n_questions: number; modes: Partial<Record<Mode, ModeMetrics>> };
    answers?: {
      n: number;
      answer_model: string;
      judge_model: string;
      faithfulness: number | null;
      fully_faithful_rate: number | null;
      correctness: number | null;
      citation_valid_rate: number | null;
      citation_gold_rate: number | null;
      answer_rate_in_scope: number | null;
      refusal_rate_out_of_scope: number | null;
      latency_ms_p50: number | null;
    };
  } | null;
};

const MODE_ORDER: Mode[] = ["fts", "bm25", "vector", "hybrid", "hybrid_rerank"];
const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);

async function getMeta(): Promise<Meta | null> {
  await connection();
  // The API scales to zero; the first request after idle can take ~30 s while it wakes.
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(`${process.env.API_URL ?? API_URL}/api/meta`, {
        cache: "no-store",
        signal: AbortSignal.timeout(45_000),
      });
      if (res.ok) return res.json();
    } catch {}
  }
  return null;
}

export default async function EvalPage() {
  const meta = await getMeta();
  if (!meta) {
    return (
      <main className="mx-auto max-w-4xl p-6 text-muted">
        Could not reach the API at {API_URL}. Start the backend to see evaluation results.
      </main>
    );
  }
  const r = meta.eval?.retrieval;
  const a = meta.eval?.answers;
  const modes = MODE_ORDER.filter((m) => r?.modes[m]);
  const best = modes.length ? Math.max(...modes.map((m) => r!.modes[m]!["recall@5"])) : 0;
  const types = r && modes.length ? Object.keys(r.modes[modes[0]]!.by_type) : [];

  return (
    <main className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-5xl flex-col gap-10 px-4 py-8">
        <header>
          <h1 className="font-serif text-3xl font-semibold tracking-tight">Evaluation</h1>
          <p className="mt-2 max-w-2xl text-muted">
            A hand-labelled set of {r?.n_questions ?? "—"} answerable questions (plus out-of-scope ones), each tagged with
            the section(s) that contain the answer. Retrieval is scored at the section level, and answers are graded by an
            LLM judge against the retrieved text and a reference answer.
            {meta.eval?.updated && <span> Last run {meta.eval.updated}.</span>}
          </p>
        </header>

        {r && (
          <section className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold">Retrieval</h2>
            <div className="overflow-x-auto rounded-lg border border-border bg-surface">
              <table className="w-full text-sm">
                <thead className="text-left text-muted">
                  <tr className="border-b border-border">
                    <th className="p-3 font-medium">Mode</th>
                    <th className="p-3 font-medium">Recall@1</th>
                    <th className="p-3 font-medium">Recall@3</th>
                    <th className="p-3 font-medium">Recall@5</th>
                    <th className="p-3 font-medium">Recall@10</th>
                    <th className="p-3 font-medium">MRR@10</th>
                    <th className="p-3 font-medium" title="Even-numbered questions, not used to choose the reranker config">
                      Recall@5 held-out
                    </th>
                    <th className="p-3 font-medium">p50 latency</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {modes.map((m) => {
                    const x = r.modes[m]!;
                    return (
                      <tr key={m} className="border-b border-border last:border-0">
                        <td className="p-3 font-sans">{MODE_LABELS[m]}</td>
                        <td className="p-3">{pct(x["recall@1"])}</td>
                        <td className="p-3">{pct(x["recall@3"])}</td>
                        <td className={`p-3 ${x["recall@5"] === best ? "font-semibold text-accent" : ""}`}>{pct(x["recall@5"])}</td>
                        <td className="p-3">{pct(x["recall@10"])}</td>
                        <td className="p-3">{x["mrr@10"].toFixed(3)}</td>
                        <td className="p-3">{pct(x.by_split?.test["recall@5"])}</td>
                        <td className="p-3">{Math.round(x.latency_ms_p50)} ms</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted">
              The reranker setup (model, candidate count, fusion with the hybrid rank) was chosen on odd-numbered questions only;
              &ldquo;held-out&rdquo; is the even-numbered half it was never tuned on.
            </p>

            <div className="rounded-lg border border-border bg-surface p-4">
              <h3 className="mb-3 text-sm font-medium">Recall@5 by question type</h3>
              <div className="flex flex-col gap-4">
                {types.map((t) => (
                  <div key={t}>
                    <p className="mb-1 text-xs text-muted">
                      {t} <span className="font-mono">(n={r.modes[modes[0]]!.by_type[t].n})</span>
                    </p>
                    <div className="flex flex-col gap-1">
                      {modes.map((m) => {
                        const v = r.modes[m]!.by_type[t]["recall@5"];
                        return (
                          <div key={m} className="flex items-center gap-2 text-xs">
                            <span className="w-28 shrink-0 text-muted">{MODE_LABELS[m]}</span>
                            <div className="h-3 flex-1 rounded-sm bg-border/60">
                              <div className="h-3 rounded-sm bg-accent" style={{ width: `${v * 100}%` }} />
                            </div>
                            <span className="w-12 text-right font-mono">{pct(v)}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">Answer quality</h2>
          {a ? (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Faithfulness" value={pct(a.faithfulness)} hint="claims supported by retrieved text" />
                <Stat label="Correctness" value={pct(a.correctness)} hint="vs reference answer" />
                <Stat label="Cites a gold section" value={pct(a.citation_gold_rate)} hint="answers citing the right section" />
                <Stat label="Out-of-scope refused" value={pct(a.refusal_rate_out_of_scope)} hint="declines to answer instead of guessing" />
              </div>
              <p className="text-xs text-muted">
                {a.n} questions · answers by <code>{a.answer_model}</code>, judged by <code>{a.judge_model}</code> · fully
                faithful answers {pct(a.fully_faithful_rate)} · valid citations {pct(a.citation_valid_rate)} · in-scope
                answered {pct(a.answer_rate_in_scope)}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted">
              Not run yet. Set <code>GROQ_API_KEY</code> and run <code>uv run python -m eval.answer_eval</code>.
            </p>
          )}
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Corpus and models</h2>
          <ul className="text-sm">
            {meta.acts.map((act) => (
              <li key={act.act_id}>
                <a href={act.source_url} className="text-accent hover:underline" target="_blank" rel="noreferrer">
                  {act.act_name}
                </a>{" "}
                <span className="text-muted">
                  — {act.sections} sections/schedules, {act.chunks} chunks
                </span>
              </li>
            ))}
          </ul>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(meta.models).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted capitalize">{k}</dt>
                <dd className="font-mono">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </main>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-[11px] text-muted">{hint}</p>
    </div>
  );
}
