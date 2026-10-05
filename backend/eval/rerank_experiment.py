"""Which reranker (if any) helps, and how should it be combined with first-stage ranks?

Configs are chosen on the DEV split (odd question ids) and reported on the
held-out TEST split (even ids), so the chosen setting isn't tuned to the
numbers it is judged on.

Strategies per reranker:
  rerank  order candidates by cross-encoder score alone
  prior   RRF of the cross-encoder rank and the hybrid (RRF) rank, i.e. the
          reranker can move a candidate but not override strong agreement
          between vector and BM25

Usage:  uv run python -m eval.rerank_experiment
"""

import json
import statistics
import time
from pathlib import Path

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import get_settings
from app.models import CACHE_DIR
from app.retrieval import bm25_search, dedupe_sections, rrf_fuse, vector_search
from eval.retrieval_eval import load_dataset, score, split

HERE = Path(__file__).resolve().parent
RERANKERS = ["BAAI/bge-reranker-base", "jinaai/jina-reranker-v1-turbo-en", "Xenova/ms-marco-MiniLM-L-12-v2"]
CANDIDATES = (20, 30)


def main() -> None:
    s = get_settings()
    qs = [q for q in load_dataset() if q["gold"]]
    fused = {}
    for q in qs:
        lists = {"vector": vector_search(q["question"], 30), "bm25": bm25_search(q["question"], 30)}
        fused[q["id"]] = rrf_fuse(lists, s.rrf_k)

    configs: dict[str, dict[str, list[dict]]] = {}
    latency: dict[str, list[float]] = {}

    def record(name: str, q: dict, ranked_hits):
        configs.setdefault(name, {"dev": [], "test": []})[split(q)].append(score(dedupe_sections(ranked_hits), q["gold"]))

    for q in qs:
        record("hybrid (no rerank)", q, fused[q["id"]])

    for model in RERANKERS:
        enc = TextCrossEncoder(model, cache_dir=CACHE_DIR)
        for n in CANDIDATES:
            key = f"{model.split('/')[-1]} top{n}"
            latency[key] = []
            for q in qs:
                cands = fused[q["id"]][:n]
                t0 = time.perf_counter()
                sc = list(enc.rerank(q["question"], [f"{h.header}\n{h.content}" for h in cands], batch_size=16))
                latency[key].append((time.perf_counter() - t0) * 1000)
                by_rr = sorted(range(len(cands)), key=lambda i: sc[i], reverse=True)
                rr_rank = {i: r for r, i in enumerate(by_rr, start=1)}
                record(f"{key} rerank", q, [cands[i] for i in by_rr])
                prior = sorted(range(len(cands)), key=lambda i: 1 / (s.rrf_k + rr_rank[i]) + 1 / (s.rrf_k + i + 1), reverse=True)
                record(f"{key} prior", q, [cands[i] for i in prior])
            print(f"done {key}  p50 {statistics.median(latency[key]):.0f} ms", flush=True)

    def agg(rows, m):
        return statistics.mean(r[m] for r in rows)

    rows = []
    for name, sp in configs.items():
        lat_key = " ".join(name.split(" ")[:2])
        rows.append({
            "config": name,
            **{f"dev_{m}": round(agg(sp["dev"], m), 4) for m in ("recall@1", "recall@5", "mrr@10")},
            **{f"test_{m}": round(agg(sp["test"], m), 4) for m in ("recall@1", "recall@5", "mrr@10")},
            "rerank_ms_p50": round(statistics.median(latency[lat_key]), 1) if lat_key in latency else 0.0,
        })
    rows.sort(key=lambda r: (r["dev_recall@5"], r["dev_mrr@10"]), reverse=True)

    n_dev = len(next(iter(configs.values()))["dev"])
    lines = [
        f"# Reranker experiment (dev n={n_dev}, test n={len(qs) - n_dev})",
        "",
        "Sorted by dev Recall@5. Choose on dev, read test.",
        "",
        "| Config | dev R@1 | dev R@5 | dev MRR | test R@1 | test R@5 | test MRR | rerank p50 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['config']} | {r['dev_recall@1']:.1%} | {r['dev_recall@5']:.1%} | {r['dev_mrr@10']:.3f} | "
                     f"{r['test_recall@1']:.1%} | {r['test_recall@5']:.1%} | {r['test_mrr@10']:.3f} | {r['rerank_ms_p50']:.0f} ms |")
    (HERE / "results" / "rerank_experiment.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
