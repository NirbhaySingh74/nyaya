"""Merge retrieval + answer eval results into results/summary.json (served by /api/meta)."""

import json
from datetime import date
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def write_summary() -> dict:
    out: dict = {"updated": date.today().isoformat()}
    retrieval = RESULTS / "retrieval.json"
    if retrieval.exists():
        r = json.loads(retrieval.read_text())
        out["retrieval"] = {"n_questions": r["n_questions"], "modes": r["modes"]}
    answers = RESULTS / "answers_summary.json"
    if answers.exists():
        out["answers"] = json.loads(answers.read_text())
    (RESULTS / "summary.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    write_summary()
