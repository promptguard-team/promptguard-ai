# PromptGuard AI 🛡️

Secure AI TRiSM-inspired proxy platform featuring an LLM gateway, CISO analytics, and a safe chat interface. Engineering project.

## Architecture
The project is based on a microservices architecture (Monorepo) targeted for deployment on a **k3s** cluster.
* **Frontend Chat:** React (User interface for prompts)
* **Frontend CISO:** React (Analytics dashboard for security)
* **API Gateway Proxy:** FastAPI (Authorization gateway and LLM proxy)
* **ML Classifier:** FastAPI + scikit-learn (prompt injection scoring; PyTorch arrives with the stage 2 transformer)
* **Database:** PostgreSQL

## Repository Structure
```text
promptguard-ai/
├── .github/                # CI/CD configuration and Issue templates
├── docs/                   # Project documentation
├── frontend-chat/          # Chat application code
├── frontend-ciso/          # CISO dashboard code
├── api-gateway/            # Proxy gateway code
├── ml-classifier/          # ML model code
├── k8s/                    # Kubernetes deployment manifests
└── docker-compose.yml      # Local development environment
```

## How to Run Locally
You do not need a local k8s cluster for development. We use Docker.

1. Copy the environment variables file:
   `cp .env.example .env` (and fill in the keys)
   - `PROXY_SECRET_KEY` is required and must be at least 32 characters — it
     signs every JWT the gateway issues. Generate one with:
     `openssl rand -hex 32`
2. Run the entire environment with:
   `docker compose up --build`
3. Applications will be available on their respective ports (details in the terminal).

### Database schema (Alembic)

Alembic owns the schema. The `api` container runs `alembic upgrade head` before
uvicorn starts (the production image does the same through its entrypoint), and
the gateway refuses to start if the database is not at the migrations' head —
a running gateway with no schema would pass every health check while failing to
audit the prompts it forwards.

* **Fresh database** — nothing to do. The first `docker compose up` creates the
  schema from the migrations.
* **Database created before Alembic was introduced** — the old startup code
  built the tables with `create_all`, and `db_data` survives
  `docker compose down`, so such a volume still exists on most dev machines.
  Its tables are there but unstamped, so the baseline revision fails
  (`type "userrole" already exists`) and the `api` container restarts in a
  loop: compose chains the migration and uvicorn with `&&`.
  Record the baseline as already applied, once, then start normally:

  ```bash
  docker compose run --rm api alembic stamp 0001
  docker compose up -d api
  ```

  `alembic stamp` only writes the revision marker; it changes no tables. Later
  revisions then apply on top of it as usual. To throw the old data away
  instead, run `docker compose down -v` and start again.

## API Gateway Endpoints
* `POST /auth/register` — create an account (email, password).
* `POST /auth/login` — exchange credentials for a JWT access token.
* `GET /auth/me` — return the authenticated user's own account.
* `POST /chat` — proxy a prompt to the LLM provider; blocks and audits any
  request or reply containing a detected credential or PESEL. After the rule
  engine, the prompt is scored by the ML Classifier (Layer 2): at or above
  `CLASSIFIER_BLOCK_THRESHOLD` it is blocked, at or above
  `CLASSIFIER_REVIEW_THRESHOLD` it is allowed but flagged for review. If the
  classifier is unavailable the request fails open and the audit row records
  `ml_status = unavailable`.
* `GET /health` — liveness check.
* `GET /health/db` — database connectivity check.

## ML Classifier Endpoints
* `POST /classify` — score one prompt; returns `label`, `score` (P(injection))
  and `model_version`. It returns a measurement, never a verdict.
* `GET /health` — readiness probe; reports `model_version` and whether the
  served artifact is a stub.

The shipped model is a labelled stub, not a security control. See
[ml-classifier/README.md](ml-classifier/README.md) for the artifact contract
and how to deliver a real model.

## How to Contribute
Please read the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file before writing your first line of code!