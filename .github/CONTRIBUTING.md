# Contributing Guidelines

Hello Team! 👋 To ensure smooth collaboration and keep our code secure and organized, please adhere to the following rules. 
**The `main` branch is protected. Direct `git push` is not allowed.**

## 🗺️ Task Lifecycle (GitHub Projects)
1. Go to our Kanban board in the **Projects** tab.
2. Pick a task from the **Ready** column and assign it to yourself.
3. Move the task to the **In progress** column.

## 🌿 Branching Strategy (Git)
For every task, create a new branch based on the latest `main`:
1. `git checkout main`
2. `git pull origin main`
3. Create a new branch: `git checkout -b type/short-description`

**Branch Naming Convention:**
* `feature/...` - New functionality (e.g., `feature/login-ui`)
* `fix/...` - Bug fix (e.g., `fix/db-connection`)
* `docs/...` - Documentation changes (e.g., `docs/api-endpoints`)

## 📝 Committing Changes
Write clear commit messages in English. Use the following convention:
* `feat: add JWT authorization`
* `fix: resolve CORS issue in FastAPI`
* `refactor: simplify ML classifier`

## 🚀 Pull Requests (PR)
When your code works locally and is ready:
1. Push the branch to GitHub: `git push origin your-branch-name`
2. Go to GitHub and create a **Pull Request** from your branch to `main`.
3. **Important:** In the PR description, include `Resolves #X` (where X is the number of your Issue). GitHub will close it automatically!
4. Ask someone from the team for a **Code Review** via Discord.
5. Once approved (Approve) and all automated checks (CodeQL) pass, you can click **Squash and merge**.