# Reranker experiment (dev n=39, test n=39)

Sorted by dev Recall@5. Choose on dev, read test.

| Config | dev R@1 | dev R@5 | dev MRR | test R@1 | test R@5 | test MRR | rerank p50 |
|---|---|---|---|---|---|---|---|
| bge-reranker-base top20 prior | 64.1% | 97.4% | 0.788 | 74.4% | 93.6% | 0.838 | 2408 ms |
| bge-reranker-base top30 prior | 64.1% | 96.2% | 0.787 | 74.4% | 93.6% | 0.836 | 4640 ms |
| ms-marco-MiniLM-L-12-v2 top30 prior | 73.1% | 93.6% | 0.838 | 79.5% | 93.6% | 0.870 | 1503 ms |
| ms-marco-MiniLM-L-12-v2 top20 prior | 73.1% | 92.3% | 0.838 | 82.0% | 93.6% | 0.883 | 964 ms |
| jina-reranker-v1-turbo-en top20 rerank | 62.8% | 92.3% | 0.784 | 76.9% | 93.6% | 0.827 | 624 ms |
| hybrid (no rerank) | 62.8% | 92.3% | 0.777 | 76.9% | 91.0% | 0.848 | 0 ms |
| ms-marco-MiniLM-L-12-v2 top30 rerank | 69.2% | 91.0% | 0.829 | 71.8% | 93.6% | 0.832 | 1503 ms |
| jina-reranker-v1-turbo-en top30 prior | 68.0% | 91.0% | 0.808 | 79.5% | 93.6% | 0.846 | 1121 ms |
| jina-reranker-v1-turbo-en top30 rerank | 62.8% | 91.0% | 0.781 | 71.8% | 91.0% | 0.799 | 1121 ms |
| ms-marco-MiniLM-L-12-v2 top20 rerank | 69.2% | 89.7% | 0.829 | 71.8% | 96.2% | 0.834 | 964 ms |
| jina-reranker-v1-turbo-en top20 prior | 68.0% | 89.7% | 0.811 | 79.5% | 93.6% | 0.851 | 624 ms |
| bge-reranker-base top30 rerank | 66.7% | 89.7% | 0.803 | 71.8% | 88.5% | 0.799 | 4640 ms |
| bge-reranker-base top20 rerank | 65.4% | 88.5% | 0.792 | 74.4% | 91.0% | 0.815 | 2408 ms |
