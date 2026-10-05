export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Mode = "hybrid_rerank" | "hybrid" | "vector" | "bm25" | "fts";

export const MODE_LABELS: Record<Mode, string> = {
  hybrid_rerank: "Hybrid + rerank",
  hybrid: "Hybrid (RRF)",
  vector: "Vector only",
  bm25: "BM25 only",
  fts: "Postgres FTS",
};

export type Source = {
  n: number;
  chunk_id: string;
  section_id: string;
  act_id: string;
  act_short: string;
  section: string;
  title: string;
  chapter: string;
  page: number;
  source_url: string;
  content: string;
  score: number;
  ranks: Record<string, number>;
};

export type Section = {
  id: string;
  act_name: string;
  act_short: string;
  section: string;
  title: string;
  chapter: string;
  source_url: string;
  text: string;
};

export type Turn = { role: "user" | "assistant"; content: string };

export type StreamHandlers = {
  onSources: (query: string, sources: Source[]) => void;
  onToken: (t: string) => void;
  onDone: (info: { timings_ms: Record<string, number>; model: string }) => void;
  onError: (message: string) => void;
};

/** POST /api/chat and parse the Server-Sent Events stream. */
export async function streamChat(
  body: { question: string; history: Turn[]; mode: Mode },
  h: StreamHandlers,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let message = `Server returned ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {}
    h.onError(message);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (!data.length) continue;
      const payload = JSON.parse(data.join("\n"));
      if (event === "sources") h.onSources(payload.query, payload.sources);
      else if (event === "token") h.onToken(payload.t);
      else if (event === "done") h.onDone(payload);
      else if (event === "error") h.onError(payload.message);
    }
  }
}

export async function fetchSection(id: string): Promise<Section> {
  const res = await fetch(`${API_URL}/api/sections/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Section ${id} not found`);
  return res.json();
}

export function sectionLabel(s: { act_short: string; section: string }) {
  const sec = /^\d/.test(s.section) ? `s. ${s.section}` : s.section;
  return `${s.act_short} · ${sec}`;
}
