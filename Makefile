.PHONY: db db-local parse ingest api web eval-retrieval eval-answers deploy-api

db:              ## Postgres + pgvector via Docker on :5433
	docker compose up -d --wait db

db-local:        ## ...or without Docker (Homebrew postgresql@17 + pgvector)
	./scripts/local_pg.sh start

parse:           ## PDFs -> backend/data/processed/sections.jsonl
	cd backend && uv run python -m ingest.parse

ingest: parse    ## chunk + embed + load into Postgres
	cd backend && uv run python -m ingest.load

api:             ## FastAPI on :8000
	cd backend && uv run uvicorn app.main:app --port 8000 --reload

web:             ## Next.js on :3000
	cd frontend && npm run dev

eval-retrieval:  ## Recall@k / MRR for all retrieval modes
	cd backend && uv run python -m eval.retrieval_eval

eval-answers:    ## LLM-judged faithfulness / correctness (needs GROQ_API_KEY)
	cd backend && uv run python -m eval.answer_eval

deploy-api:      ## build + deploy backend to Cloud Run (needs gcloud login and deploy/env.yaml)
	gcloud run deploy nyaya-api --source backend --region us-east4 \
	  --allow-unauthenticated --memory 2Gi --cpu 2 --cpu-boost \
	  --min-instances 0 --max-instances 2 --concurrency 20 --timeout 300 \
	  --env-vars-file deploy/env.yaml
