# PromptGuard AI 🛡️

Secure AI TRiSM-inspired proxy platform featuring an LLM gateway, CISO analytics, and a safe chat interface. Engineering project.

## 🏗️ Architecture
The project is based on a microservices architecture (Monorepo) targeted for deployment on a **k3s** cluster.
* **Frontend Chat:** React (User interface for prompts)
* **Frontend CISO:** React (Analytics dashboard for security)
* **API Gateway Proxy:** FastAPI (Authorization gateway and LLM proxy)
* **ML Classifier:** FastAPI + PyTorch (Query/response classifier)
* **Database:** PostgreSQL

## 📂 Repository Structure
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

## 🚀 How to Run Locally
You do not need a local k8s cluster for development. We use Docker.

1. Copy the environment variables file:
   `cp .env.example .env` (and fill in the keys)
2. Run the entire environment with:
   `docker compose up --build`
3. Applications will be available on their respective ports (details in the terminal).

## 🤝 How to Contribute
Please read the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file before writing your first line of code!