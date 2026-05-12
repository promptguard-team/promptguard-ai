# Contributing Guidelines

Hello Team! 👋 To ensure smooth collaboration and keep our code secure and organized, please adhere to the following rules. 
**The `main` branch is protected. Direct `git push` is not allowed.**

## 🚀 The Automated Workflow (Step-by-Step)

### Step 1: It all starts with an Issue
Before writing any code, there must be a registered ticket.
1. Go to the **Issues** tab.
2. Click **New Issue** and select the appropriate template (Bug or Feature).
3. Fill it out comprehensively. Once created, our GitHub automation will automatically add this Issue to the **Backlog** column on our Kanban board.

### Step 2: The Kanban Board (GitHub Projects)
1. Go to our Kanban board in the **Projects** tab.
2. Find the Issue you want to work on in the **Backlog** or **Ready** column.
3. Assign it to yourself (Assignees).
4. Move the card to the **In progress** column. This signals the team that you are actively working on it and prevents duplicated effort.

### Step 3: Local Development (Git & Docker)
Always create a new, isolated branch based on the latest `main`:
```bash
git checkout main
git pull origin main
git checkout -b type/short-description
```

**Branch Naming Convention:**
* `feature/...` - New functionality (e.g., `feature/login-ui`)
* `fix/...` - Bug fix (e.g., `fix/db-connection`)
* `docs/...` - Documentation changes (e.g., `docs/api-endpoints`)

Write your code and test it locally using our Docker environment:
```bash
docker compose up --build
```

### Step 4: Committing Changes
Write clear, descriptive commit messages in English. We use standard prefixes:
* `feat: add JWT authorization`
* `fix: resolve CORS issue in FastAPI`
* `refactor: simplify ML classifier`

### Step 5: The Pull Request & Automation Magic
When your code works locally and is ready for review:
1. Push the branch to GitHub: `git push origin your-branch-name`
2. Go to GitHub and click **Compare & pull request**.
3. **CRITICAL STEP:** In the PR description, you must write `Resolves #X` (where X is the number of your original Issue). 
*Why? This triggers our automation. GitHub will link the PR to the Issue. When the PR is merged, the Issue will automatically close, and the project card will automatically move to the "Done" column!*

### Step 6: Code Review & Merge
1. Once the PR is open, our Discord Webhook will notify the team.
2. GitHub Actions (CodeQL) will automatically scan your code for security vulnerabilities.
3. Request a **Code Review** from a teammate.
4. Once you receive at least 1 approving review (Approve) and all automated checks turn green, click **Squash and merge**.