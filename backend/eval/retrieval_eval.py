"""Retrieval evaluation: compare vector / keyword / hybrid / hybrid+rerank.

Metrics are computed at the *section* level (the unit a lawyer cites), after
de-duplicating chunks from the same section:
  Recall@k  fraction of a question's gold sections found in the top k
  Hit@k     1 if any gold section is in the top k
  MRR@10    1 / rank of the first gold section (0 if not in top 10)

Usage:  uv run python -m eval.retrieval_eval [--modes vector hybrid_rerank]
"""

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from app.retrieval import MODES, dedupe_sections, retrieve
from eval.summary import write_summary

HERE = Path(__file__).resolve().parent
KS = (1, 3, 5, 10)
FETCH_CHUNKS = 30  # enough chunks to fill 10 distinct sections


def split(q: dict) -> str:
    """dev = odd ids (used to choose configs), test = even ids (held out)."""
    return "dev" if int(q["id"][1:]) % 2 else "test"


def load_dataset() -> list[dict]:
    return [json.loads(l) for l in (HERE / "dataset.jsonl").open() if l.strip()]


def score(ranked: list[str], gold: list[str]) -> dict[str, float]:
    out = {}
    for k in KS:
        top = set(ranked[:k])
        out[f"recall@{k}"] = len(top & set(gold)) / len(gold)
        out[f"hit@{k}"] = float(bool(top & set(gold)))
    rr = next((1 / i for i, s in enumerate(ranked[:10], start=1) if s in gold), 0.0)
    out["mrr@10"] = rr
    return out


def mean(rows: list[dict], key: str) -> float:
    return round(statistics.mean(r[key] for r in rows), 4) if rows else 0.0


def evaluate(modes: list[str]) -> dict:
    qs = [q for q in load_dataset() if q["gold"]]
    for mode in modes:  # warm-up: load models before timing
        retrieve(qs[0]["question"], mode)

    report: dict = {"n_questions": len(qs), "modes": {}, "per_question": defaultdict(dict)}
    for mode in modes:
        rows, latencies = [], []
        for q in qs:
            t0 = time.perf_counter()
            res = retrieve(q["question"], mode, FETCH_CHUNKS)
            latencies.append((time.perf_counter() - t0) * 1000)
            ranked = dedupe_sections(res.hits)
            s = score(ranked, q["gold"])
            rows.append({**s, "type": q["type"], "split": split(q)})
            report["per_question"][q["id"]][mode] = {"top5": ranked[:5], **{k: s[k] for k in ("recall@5", "mrr@10")}}

        by_type = defaultdict(list)
        for r in rows:
            by_type[r["type"]].append(r)
        report["modes"][mode] = {
            **{m: mean(rows, m) for m in [f"recall@{k}" for k in KS] + [f"hit@{k}" for k in KS] + ["mrr@10"]},
            "latency_ms_p50": round(statistics.median(latencies), 1),
            "latency_ms_p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
            "by_split": {sp: {"n": len(v), "recall@1": mean(v, "recall@1"), "recall@5": mean(v, "recall@5"), "mrr@10": mean(v, "mrr@10")}
                         for sp in ("dev", "test") for v in [[r for r in rows if r["split"] == sp]]},
            "by_type": {t: {"n": len(v), "recall@5": mean(v, "recall@5"), "mrr@10": mean(v, "mrr@10")} for t, v in sorted(by_type.items())},
        }
        m = report["modes"][mode]
        print(f"{mode:14s} R@1 {m['recall@1']:.3f}  R@3 {m['recall@3']:.3f}  R@5 {m['recall@5']:.3f}  "
              f"R@10 {m['recall@10']:.3f}  MRR {m['mrr@10']:.3f}  p50 {m['latency_ms_p50']}ms")
    return report


def to_markdown(report: dict) -> str:
    modes = list(report["modes"])
    lines = [
        f"# Retrieval evaluation ({report['n_questions']} answerable questions)",
        "",
        "Section-level metrics. Gold labels in `eval/dataset.jsonl`.",
        "",
        "| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | p50 latency |",
        "|---|---|---|---|---|---|---|",
    ]
    for mode in modes:
        m = report["modes"][mode]
        lines.append(f"| {mode} | {m['recall@1']:.1%} | {m['recall@3']:.1%} | {m['recall@5']:.1%} | "
                     f"{m['recall@10']:.1%} | {m['mrr@10']:.3f} | {m['latency_ms_p50']:.0f} ms |")
    lines += ["", "## Held-out test split (even ids; configs were chosen on dev)", "",
              "| Mode | test Recall@1 | test Recall@5 | test MRR@10 |", "|---|---|---|---|"]
    for mode in modes:
        t = report["modes"][mode]["by_split"]["test"]
        lines.append(f"| {mode} | {t['recall@1']:.1%} | {t['recall@5']:.1%} | {t['mrr@10']:.3f} |")
    types = sorted({t for m in report["modes"].values() for t in m["by_type"]})
    lines += ["", "## Recall@5 by question type", "", "| Mode | " + " | ".join(
        f"{t} (n={report['modes'][modes[0]]['by_type'][t]['n']})" for t in types) + " |",
        "|---|" + "---|" * len(types)]
    for mode in modes:
        bt = report["modes"][mode]["by_type"]
        lines.append(f"| {mode} | " + " | ".join(f"{bt[t]['recall@5']:.1%}" for t in types) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=MODES)
    args = ap.parse_args()

    report = evaluate(args.modes)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "retrieval.json").write_text(json.dumps(report, indent=2))
    (out / "retrieval.md").write_text(to_markdown(report))
    write_summary()
    print(f"\nwrote {out / 'retrieval.md'}")


if __name__ == "__main__":
    main()
