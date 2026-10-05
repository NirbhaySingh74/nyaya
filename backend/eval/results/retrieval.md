# Retrieval evaluation (78 answerable questions)

Section-level metrics. Gold labels in `eval/dataset.jsonl`.

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | p50 latency |
|---|---|---|---|---|---|---|
| vector | 67.3% | 87.2% | 94.2% | 97.4% | 0.798 | 16 ms |
| fts | 23.7% | 56.4% | 66.0% | 84.6% | 0.442 | 1 ms |
| bm25 | 49.4% | 81.4% | 85.3% | 89.7% | 0.673 | 1 ms |
| hybrid | 69.9% | 87.8% | 91.7% | 96.2% | 0.812 | 19 ms |
| hybrid_rerank | 69.2% | 87.8% | 95.5% | 98.1% | 0.813 | 1538 ms |

## Held-out test split (even ids; configs were chosen on dev)

| Mode | test Recall@1 | test Recall@5 | test MRR@10 |
|---|---|---|---|
| vector | 74.4% | 93.6% | 0.830 |
| fts | 17.9% | 62.8% | 0.390 |
| bm25 | 61.5% | 87.2% | 0.721 |
| hybrid | 76.9% | 91.0% | 0.848 |
| hybrid_rerank | 74.4% | 93.6% | 0.838 |

## Recall@5 by question type

| Mode | direct (n=25) | keyword (n=10) | multi (n=5) | paraphrase (n=38) |
|---|---|---|---|---|
| vector | 96.0% | 90.0% | 90.0% | 94.7% |
| fts | 84.0% | 80.0% | 90.0% | 47.4% |
| bm25 | 96.0% | 90.0% | 90.0% | 76.3% |
| hybrid | 96.0% | 90.0% | 90.0% | 89.5% |
| hybrid_rerank | 96.0% | 100.0% | 90.0% | 94.7% |
