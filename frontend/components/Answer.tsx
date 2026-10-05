"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders answer markdown, turning [n] citations into clickable chips. */
export function Answer({
  content,
  onCite,
  streaming,
}: {
  content: string;
  onCite: (n: number) => void;
  streaming?: boolean;
}) {
  const linked = normalizeCitations(content).replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)");
  return (
    <div className="prose-answer text-[15px]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const m = href?.match(/^#cite-(\d+)$/);
            if (!m) {
              return (
                <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">
                  {children}
                </a>
              );
            }
            const n = Number(m[1]);
            return (
              <button
                type="button"
                onClick={() => onCite(n)}
                className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-accent-soft px-1 align-text-top font-mono text-[11px] font-medium text-accent hover:ring-1 hover:ring-accent"
                aria-label={`Show source ${n}`}
              >
                {n}
              </button>
            );
          },
        }}
      >
        {linked}
      </ReactMarkdown>
      {streaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/60 align-middle" />}
    </div>
  );
}

/** gpt-oss sometimes emits its native 【1†L1-L3】 citation style; map it to [1]. */
function normalizeCitations(content: string) {
  return content.replace(/【(\d+)(?:†[^】]*)?】/g, "[$1]");
}

export function citedNumbers(content: string): Set<number> {
  return new Set([...normalizeCitations(content).matchAll(/\[(\d{1,2})\]/g)].map((m) => Number(m[1])));
}
