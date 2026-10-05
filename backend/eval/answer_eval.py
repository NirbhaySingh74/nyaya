"""End-to-end answer evaluation with an LLM judge (RAGAS-style faithfulness).

For each question: retrieve (hybrid_rerank) -> expand to sections -> generate -> judge.
  faithfulness      supported claims / total claims, judged against the
                    retrieved sources only (catches hallucination)
  correctness       1 / 0.5 / 0 vs the reference answer (catches wrong or
                    incomplete answers even if they are "faithful")
  citation_valid    answer cites >=1 source and every [n] exists
  citation_gold     some cited source belongs to a gold section
  refusal           out-of-scope questions should be refused, in-scope ones answered

Results are appended per question to results/answers.jsonl so a run can be
resumed after a rate-limit stop. Use --fresh to start over.

Usage:  uv run python -m eval.answer_eval [--limit 20] [--fresh]
"""

import argparse
import json
import re
import statistics
import time
from pathlib import Path

from groq import RateLimitError

from app.config import get_settings
from app.llm import NOT_FOUND, build_messages, complete, format_sources, llm_configured
from app.retrieval import retrieve, section_context
from eval.summary import write_summary

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "answers.jsonl"

JUDGE_PROMPT = """You are grading an answer produced by a legal RAG assistant.

SOURCES (the only context the assistant was given):
{sources}

QUESTION: {question}

REFERENCE ANSWER (written by a human from the statute): {reference}

ASSISTANT ANSWER: {answer}

Tasks:
1. Split the ASSISTANT ANSWER into atomic factual claims (ignore citations, hedges and
   "this is not legal advice"). For each claim decide if it is directly supported by the SOURCES.
2. Grade correctness against the REFERENCE ANSWER: "correct" if it states the key facts
   (numbers, conditions, who/what) correctly; "partial" if it is incomplete or partly wrong;
   "incorrect" if it is wrong, contradicts the reference, or fails to answer.

Return JSON only:
{{"claims": [{{"claim": "...", "supported": true}}], "correctness": "correct|partial|incorrect", "reason": "one sentence"}}"""

CORRECTNESS = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


def cited_numbers(answer: str) -> set[int]:
    return {int(n) for n in re.findall(r"\[(\d+)\]", answer)}


def run_one(q: dict) -> dict:
    s = get_settings()
    t0 = time.perf_counter()
    hits = section_context(retrieve(q["question"], "hybrid_rerank", s.context_fetch_chunks).hits)
    answer = complete(build_messages(q["question"], hits), model=s.answer_model)
    latency = (time.perf_counter() - t0) * 1000
    refused = NOT_FOUND.lower() in answer.lower()

    cites = cited_numbers(answer)
    result = {
        "id": q["id"],
        "type": q["type"],
        "question": q["question"],
        "answer": answer,
        "retrieved": [h.section_id for h in hits],
        "refused": refused,
        "latency_ms": round(latency),
        "citation_valid": bool(cites) and all(1 <= n <= len(hits) for n in cites),
        "citation_gold": any(hits[n - 1].section_id in q["gold"] for n in cites if 1 <= n <= len(hits)),
    }
    if not q["gold"]:  # out-of-scope: only refusal matters
        result["correctness"] = 1.0 if refused else 0.0
        return result
    if refused:
        result.update(faithfulness=None, correctness=0.0, judge_reason="refused an answerable question")
        return result

    raw = complete(
        [{"role": "user", "content": JUDGE_PROMPT.format(
            sources=format_sources(hits), question=q["question"], reference=q["answer"], answer=answer)}],
        model=s.judge_model,
        json_mode=True,
        max_tokens=1500,
    )
    verdict = json.loads(raw)
    claims = verdict.get("claims") or []
    result.update(
        claims=claims,
        faithfulness=(sum(bool(c.get("supported")) for c in claims) / len(claims)) if claims else None,
        correctness=CORRECTNESS.get(str(verdict.get("correctness", "")).lower(), 0.0),
        judge_reason=verdict.get("reason", ""),
    )
    return result


def summarize(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["type"] != "unanswerable"]
    oos = [r for r in rows if r["type"] == "unanswerable"]
    faith = [r["faithfulness"] for r in answerable if r.get("faithfulness") is not None]

    def avg(xs):
        return round(statistics.mean(xs), 4) if xs else None

    s = get_settings()
    return {
        "n": len(rows),
        "answer_model": s.answer_model,
        "judge_model": s.judge_model,
        "faithfulness": avg(faith),
        "fully_faithful_rate": avg([1.0 if f == 1.0 else 0.0 for f in faith]),
        "correctness": avg([r["correctness"] for r in answerable]),
        "citation_valid_rate": avg([float(r["citation_valid"]) for r in answerable if not r["refused"]]),
        "citation_gold_rate": avg([float(r["citation_gold"]) for r in answerable if not r["refused"]]),
        "answer_rate_in_scope": avg([0.0 if r["refused"] else 1.0 for r in answerable]),
        "refusal_rate_out_of_scope": avg([1.0 if r["refused"] else 0.0 for r in oos]),
        "latency_ms_p50": statistics.median([r["latency_ms"] for r in rows]) if rows else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only run the first N pending questions")
    ap.add_argument("--fresh", action="store_true", help="discard previous results")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between questions (rate limits)")
    args = ap.parse_args()

    if not llm_configured():
        raise SystemExit("Set GROQ_API_KEY in backend/.env first.")

    OUT.parent.mkdir(exist_ok=True)
    if args.fresh and OUT.exists():
        OUT.unlink()
    done = {json.loads(l)["id"] for l in OUT.open()} if OUT.exists() else set()
    dataset = [json.loads(l) for l in (HERE / "dataset.jsonl").open() if l.strip()]
    pending = [q for q in dataset if q["id"] not in done]
    if args.limit:
        pending = pending[: args.limit]

    for i, q in enumerate(pending, start=1):
        try:
            r = run_one(q)
        except RateLimitError as e:
            if "per day" not in str(e):
                raise
            print(f"\nGroq daily token limit reached after {i - 1} new questions. "
                  "Re-run later to resume from where it stopped.\n")
            break
        with OUT.open("a") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(pending)}] {q['id']} {q['type']:12s} correct={r['correctness']} "
              f"faith={r.get('faithfulness')} refused={r['refused']}")
        time.sleep(args.sleep)

    rows = [json.loads(l) for l in OUT.open()]
    summary = summarize(rows)
    (HERE / "results" / "answers_summary.json").write_text(json.dumps(summary, indent=2))
    write_summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
