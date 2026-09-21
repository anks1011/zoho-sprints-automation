# Zoho Sprints AI Story-to-Tasks Automation Suite (Web UI & CLI)

A production-ready application and CLI suite that automates breaking down Zoho Sprints parent stories into high-quality, structured frontend (FE) and backend (BE) subtasks using an OpenAI-compatible LLM, complete with duplicate detection, editable review UI, dry-run simulation, explicit confirmation safety locks, and failure-resilient execution tracking.

---

## 🚀 How to Run the Project

### Option A: Running the Web Application (Recommended)

The project includes a FastAPI backend (`src/api`) and a Next.js 16 + TypeScript web frontend (`frontend/`).

#### 1. Start the FastAPI Backend Server
In the project root directory, ensure your Python virtual environment is activated:
```bash
# Activate virtual environment
source .venv/bin/activate

# Start FastAPI server on port 8000
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```
The backend API is now running at `http://127.0.0.1:8000` (Swagger docs available at `http://127.0.0.1:8000/docs`).

#### 2. Start the Next.js Frontend
In a second terminal window:
```bash
cd frontend

# Install dependencies (if not already done)
npm install

# Start in development mode (or 'npm run build && npm start' for production)
npm run dev
```
Open your browser and navigate to:
**👉 http://localhost:3000**

#### 3. Web UI Workflow:
1. **Enter Story ID**: Type your Story ID (e.g. `39713000007827664`) in the search bar or on the dashboard.
2. **Inspect Story**: View story details, existing subtasks, and acceptance criteria.
3. **Generate Plan**: Click **"Generate Task Plan"** to run the AI requirement analyzer.
4. **Edit Tasks**: Review FE/BE task cards, edit titles/descriptions, and inspect duplicate overlap warnings.
5. **Dry-Run Preview**: Click **"Dry-Run Preview"** to inspect simulated Zoho Sprints API payloads with zero writes.
6. **Create in Zoho**: Click **"Create Tasks in Zoho"**, review the safety confirmation modal, check the acknowledgment, and create tasks.
7. **Audit & Resume**: View history and resume any interrupted runs at `http://localhost:3000/executions`.

---

### Option B: Running via the CLI

You can also run all workflows directly in your terminal using the Python CLI:

```bash
# Activate virtual environment
source .venv/bin/activate

# 1. Check Zoho OAuth authorization status
python -m src.main auth-status

# 2. Inspect a story and existing subtasks
python -m src.main story --story-id 39713000007827664

# 3. Generate a task plan with AI
python -m src.main generate --story-id 39713000007827664

# 4. Preview dry-run API calls without creating subtasks
python -m src.main create --story-id 39713000007827664 --dry-run

# 5. Live task creation (prompts for explicit 'YES' confirmation)
python -m src.main create --story-id 39713000007827664

# 6. Resume an interrupted execution
python -m src.main resume --execution-id <EXECUTION_ID>
```

---

### Option C: Running the Automated Tests

Run the full pytest suite (74 unit and integration tests):
```bash
source .venv/bin/activate
pytest
```

## Architecture Overview

```
zoho-sprints-automation/
├── .env.example             # Configuration template (no credentials)
├── .gitignore               # Ignores .env, .runtime/, .venv/, etc.
├── pyproject.toml           # Project dependencies & packaging
├── README.md                # Exhaustive documentation & CLI usage guide
├── src/
│   ├── main.py              # Typer CLI entrypoint & commands
│   ├── config.py            # Pydantic Settings & environment validation
│   ├── logging_config.py    # Structured logging with SecretMaskingFilter
│   ├── auth/
│   │   ├── oauth_client.py  # Zoho OAuth 2.0 authorization, code exchange & refresh
│   │   └── token_store.py   # Secure local token persistence (.runtime/tokens/)
│   ├── client/
│   │   ├── models.py        # Entity schemas (Team, Project, Sprint, Item, Subitem)
│   │   ├── zoho_client.py   # HTTP client with retries, 401 refresh & 429 backoff
│   │   └── sprints_api.py   # Zoho Sprints REST endpoints
│   ├── services/
│   │   ├── story_service.py # Story fetching & context auto-discovery
│   │   ├── task_models.py   # Pydantic schemas for analysis & tasks
│   │   ├── ai_analyzer.py   # Structured OpenAI LLM story analysis
│   │   ├── task_generator.py# FE/BE task synthesis & formatting rules
│   │   ├── duplicate_detector.py # Normalized fuzzy overlap detection
│   │   ├── plan_store.py    # Local task plan persistence (.runtime/plans/)
│   │   ├── execution_tracker.py # Execution state tracking (.runtime/executions/)
│   │   └── task_creator.py  # Task creation, dry-run & resume logic
│   └── utils/
│       ├── security.py      # Secret masking & payload sanitization helpers
│       └── formatting.py    # Rich terminal tables, panels & alerts
└── tests/                   # 55+ automated unit and integration tests
```

---

## Requirements & Installation

### Python Version
- **Python 3.11+** required.

### Setup Virtual Environment

```bash
# 1. Clone repository & navigate to directory
cd zoho-sprints-automation

# 2. Create Python 3.11 virtual environment
python3.11 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Upgrade pip and install package with development dependencies
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## Configuration & Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```ini
# Zoho OAuth Configuration
ZOHO_CLIENT_ID=your_zoho_client_id
ZOHO_CLIENT_SECRET=your_zoho_client_secret
ZOHO_REDIRECT_URI=http://localhost:8080/callback
ZOHO_ACCOUNTS_URL=https://accounts.zoho.in
ZOHO_API_BASE_URL=https://sprintsapi.zoho.in/zsapi

# AI Provider Configuration (OpenAI or compatible endpoint)
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

# Optional Defaults (helpful if you work primarily in one project)
ZOHO_TEAM_ID=
ZOHO_PROJECT_ID=
ZOHO_SPRINT_ID=
ZOHO_DEFAULT_ITEM_TYPE_ID=
ZOHO_DEFAULT_PRIORITY_ID=

# Application Settings
LOG_LEVEL=INFO
```

### Supported Data Centers
Zoho hosts accounts across different regions. Set `ZOHO_ACCOUNTS_URL` and `ZOHO_API_BASE_URL` according to your organization's region:

| Data Center | `ZOHO_ACCOUNTS_URL` | `ZOHO_API_BASE_URL` |
| :--- | :--- | :--- |
| **India (.in)** *(default)* | `https://accounts.zoho.in` | `https://sprintsapi.zoho.in/zsapi` |
| **United States (.com)** | `https://accounts.zoho.com` | `https://sprintsapi.zoho.com/zsapi` |
| **Europe (.eu)** | `https://accounts.zoho.eu` | `https://sprintsapi.zoho.eu/zsapi` |
| **Australia (.com.au)** | `https://accounts.zoho.com.au` | `https://sprintsapi.zoho.com.au/zsapi` |
| **Canada (.zohocloud.ca)** | `https://accounts.zohocloud.ca` | `https://sprintsapi.zohocloud.ca/zsapi` |

---

## Zoho OAuth 2.0 Setup Guide

### 1. Register Client in Zoho API Console
1. Visit the [Zoho API Console](https://api-console.zoho.com/).
2. Click **Add Client** and select **Server-based Applications**.
3. Fill in:
   - **Client Name:** `Zoho Sprints Automation`
   - **Homepage URL:** `http://localhost:8080`
   - **Authorized Redirect URIs:** `http://localhost:8080/callback`
4. Copy the generated **Client ID** and **Client Secret** into `.env`.

### 2. Required Scopes
The default scope configured is:
```text
ZohoSprints.fullaccess.ALL
```
Or granular scopes:
```text
ZohoSprints.items.ALL,ZohoSprints.projects.READ,ZohoSprints.teams.READ,ZohoSprints.sprints.READ
```

### 3. Authorize CLI

Run the interactive authorization command:

```bash
python -m src.main auth
```

1. The CLI displays the authorization URL. Open it in your web browser.
2. Log in to your Zoho account and click **Accept**.
3. You will be redirected to `http://localhost:8080/callback?code=...`.
4. Copy the value of the `code` parameter from your browser address bar and paste it into the CLI prompt.
5. The CLI securely stores your access and refresh tokens under `.runtime/tokens/token.json` (mode `0600`).

### Check Auth Status

```bash
python -m src.main auth-status
```

### Refresh Access Token

```bash
python -m src.main refresh-token
```

---

## Exploring Zoho Sprints Workspace

Discover your team, project, and sprint IDs if needed:

```bash
# List all teams / workspaces
python -m src.main list-teams

# List projects within a team
python -m src.main list-projects --team-id <TEAM_ID>

# List sprints within a project
python -m src.main list-sprints --team-id <TEAM_ID> --project-id <PROJECT_ID>
```

---

## Step-by-Step CLI Usage Workflow

### 1. Inspect Story Details
Fetch and inspect the parent story, acceptance criteria, and any existing subtasks:

```bash
python -m src.main story --story-id <STORY_ID>
```

*Optional flags:* `--team-id`, `--project-id`, `--sprint-id` (if not auto-discoverable).

---

### 2. Generate Task Plan
Analyze the story and generate a validated FE and BE task plan. **This makes zero writes to Zoho Sprints:**

```bash
python -m src.main generate --story-id <STORY_ID>
```

**What this does:**
1. Fetches the parent story and existing subtasks.
2. Invokes the AI model to perform architectural breakdown.
3. Generates exactly one `FE - <title>` task (if frontend work is needed).
4. Generates sequential `BE - 01 - <title>`, `BE - 02 - <title>` tasks (if backend work is needed).
5. Runs duplicate detection against existing subtasks.
6. Saves the plan locally to `.runtime/plans/plan_<ID>.json`.
7. Displays a Rich preview in your terminal.

---

### 3. Preview Saved Plan
Review the latest generated plan at any time:

```bash
python -m src.main preview --story-id <STORY_ID>
```

---

### 4. Dry-Run Simulation
Simulate subtask creation to inspect the exact HTTP endpoints, methods, and sanitized JSON/form payloads that would be sent to Zoho Sprints:

```bash
python -m src.main create --story-id <STORY_ID> --dry-run
```

No tasks are created during dry-run.

---

### 5. Explicit Confirmation & Task Creation
To create the subtasks under the parent story in Zoho Sprints:

```bash
python -m src.main create --story-id <STORY_ID>
```

The CLI will display the task preview and prompt:
```text
Do you want to create these tasks under Story ID <STORY_ID>? Type YES to continue:
```

- Type `YES` to proceed.
- Any other input cancels execution immediately with zero API calls.

For automated environments (CI/CD), pass `--confirm`:

```bash
python -m src.main create --story-id <STORY_ID> --confirm
```

---

### 6. Resuming Partial Failures
If network disruption or rate limits cause a task creation to fail midway:
1. Each task state is persisted immediately in `.runtime/executions/exec_<ID>.json`.
2. The CLI reports the `execution-id`.
3. To resume without creating duplicate tasks:

```bash
python -m src.main resume --execution-id <EXECUTION_ID>
```

The tool checks the execution record, skips all tasks already marked `CREATED`, and creates only pending/failed tasks.

---

## Task Formatting Rules

### Title Rules
- **Frontend:**
  `FE - <clear and concise frontend implementation title>`
  - Exactly 1 task when UI/client work is needed.
  - Consolidates state, UI, form validation, error states, and API integration.
- **Backend:**
  `BE - 01 - <clear and concise backend implementation title>`
  `BE - 02 - <clear and concise backend implementation title>`
  - Sequential 2-digit numbering (`01`, `02`, ...).
  - Split along architectural boundaries (API contracts, DB migrations, business logic, asynchronous workers).

### Description Structure
Every generated subtask includes 4 mandatory Markdown sections in exact order:
```markdown
## Objective
A clear and concise description of the task objective.

## Scope
- Specific implementation responsibility 1
- Specific implementation responsibility 2

## Expected Behavior
- Expected system behavior under normal conditions
- Expected system behavior under failure/edge conditions

## Dependencies
- Required services, configurations, permissions, APIs, or None identified
```

---

## Duplicate Detection Mechanism

Before tasks are approved for creation, `DuplicateDetector`:
1. Strips common prefixes (`FE - `, `BE - 01 - `, `[FE]`, etc.).
2. Normalizes case, removes punctuation, and collapses whitespace.
3. Performs exact match checking and fuzzy token-set similarity comparison against all existing subtasks under the parent story.
4. Categorizes matches:
   - `DUPLICATE_EXACT`: Normalized title matches an existing subtask 100%.
   - `DUPLICATE_LIKELY`: Fuzzy similarity score $\ge 75\%$.
   - `NO_OVERLAP`: Safe to proceed.
5. Overlap warnings are displayed in a prominent warning table in the preview. Existing subtasks are never modified or deleted automatically.

---

## Security Guidelines

- **Zero Secrets Committed:** `.env`, `.runtime/` (plans, tokens, executions, caches), and log files are excluded in `.gitignore`.
- **Automatic Masking Filter:** All logging through `SecretMaskingFilter` masks Zoho access tokens, refresh tokens, client secrets, and OpenAI API keys.
- **Local Token Protection:** Tokens saved in `.runtime/tokens/token.json` are written with restricted file permissions (`0o600`).
- **Sanitized Outputs:** Dry-run summaries and CLI error outputs pass payloads through `sanitize_payload()` before printing.

---

## Running the Automated Test Suite

The test suite runs with 100% mocked external API calls (zero real requests to Zoho or OpenAI):

```bash
# Run all tests
pytest -v

# Run specific test modules
pytest tests/test_security.py
pytest tests/test_auth.py
pytest tests/test_sprints_client.py
pytest tests/test_story_service.py
pytest tests/test_ai_analyzer.py
pytest tests/test_task_generator.py
pytest tests/test_duplicate_detector.py
pytest tests/test_task_creator.py
pytest tests/test_cli.py
```

---

## Known API Limitations & Troubleshooting

1. **Hierarchical Endpoint Structure:**
   - Zoho Sprints API requires `teamId`, `projectId`, and `sprintId` in paths.
   - When only `--story-id` is provided, the tool automatically discovers these IDs using project and sprint searches. If your account contains multiple active teams or projects, set `ZOHO_TEAM_ID` and `ZOHO_PROJECT_ID` in `.env` or pass `--team-id` / `--project-id` on the CLI.
2. **Rate Limits (30 req/min):**
   - Zoho Sprints enforces a rate limit of approximately 30 requests per minute.
   - The HTTP client includes automatic backoff and retry handling on HTTP 429 status codes.
3. **HTTP 200 with Error JSON:**
   - Zoho occasionally returns HTTP 200 with `{"status": "error", "message": "..."}`. The client validates payload contents and raises `SprintsAPIError`.
4. **Token Expiry (HTTP 401):**
   - Access tokens expire after 1 hour. The client automatically catches HTTP 401, refreshes the access token using the stored refresh token, and retries the original request seamlessly.
