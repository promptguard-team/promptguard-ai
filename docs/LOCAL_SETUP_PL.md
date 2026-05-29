# 🛠️ Local Environment Setup

Welcome to the PromptGuard AI team! This document describes step-by-step how to prepare your local environment for writing code. This document complements our workflow described in `CONTRIBUTING.md`.

Our repository is protected by strict CI/CD pipelines (DevSecOps). To avoid frustration and having your code rejected by GitHub, you must install local Git Hooks, which will automatically format and check your code before pushing it to the repository.

## 📦 1. Installing the Guards (Pre-commit)

We use the `pre-commit` framework, which binds all our linters and formatters together (Ruff for Python, Prettier for JS, and security scanners).

**Step by step:**

1. Ensure you have Python installed on your system.
2. Install the main tool globally or in your virtual environment:

```bash
pip install pre-commit
```

3. While in the root directory of the project (where the hidden `.git` folder is located), install the git hook scripts:

```bash
pre-commit install
```

From now on, every time you run `git commit`, the tool will automatically analyze your files.

---

## 🔧 2. Manual Execution and Troubleshooting

Sometimes automated tools can get confused, block your commit, or you might just want to format the code before staging it. Below is a cheat sheet for the most common issues and useful commands.

### 🛡️ Pre-commit (General)

- **Problem:** You want to check the entire project, not just the files you are currently modifying.
  - **Solution:** Force scanning of all files:

```bash
pre-commit run --all-files
```

- **Problem:** The tool blocked your commit, and you absolutely need to push it (Use ONLY in emergencies!).
  - **Solution:**

```bash
git commit --no-verify -m "your commit message"
```

### 🐍 Ruff (Python - Linter and Formatter)

Used in the `api-gateway/` and `ml-classifier/` directories.

- **Problem:** You want to see code errors (e.g., unused variables) before committing.
  - **Command:**

```bash
ruff check .
```

- **Problem:** You have many minor errors (e.g., missing imports) and want Ruff to fix them automatically.
  - **Command:**

```bash
ruff check --fix .
```

- **Problem:** The code has bad indentation or looks messy.
  - **Command:**

```bash
ruff format .
```

### ⚛️ Prettier (JavaScript / React - Formatter)

Used in the `frontend-chat/` and `frontend-ciso/` directories.

- **Problem:** You want to force formatting of the entire frontend codebase.
  - **Command:**

```bash
npx prettier --write .
```

### 🔐 Detect-secrets (Secret Leak Prevention)

- **Problem:** Pre-commit blocks a file, claiming it contains a password or token, but it is a false-positive (e.g., a fake hash in unit tests).
  - **Solution:** Add a special bypass comment on the same line in your code:

```python
fake_token = "12345ABCD"  # pragma: allowlist secret
```

- _Note:_ If it is a real token, DELETE IT immediately and move it to your local `.env` file.
