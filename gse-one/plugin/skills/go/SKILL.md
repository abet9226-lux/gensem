---
description: "Detect project state, propose next activity. Triggered by /gse:go. Includes --adopt mode for existing projects."
---

# GSE-One Go — Orchestrate

Arguments: $ARGUMENTS

## Options

| Flag / Sub-command | Description |
|--------------------|-------------|
| (no args)          | Detect current project state and propose the next activity |
| `--adopt`          | Adopt an existing project that was not created with GSE-One |
| `--status`         | Display current state without proposing an action |
| `--help`           | Show this command's usage summary |

## Prerequisites

Before executing, read:
1. `.gse/status.yaml` — current sprint and lifecycle state (if it exists)
2. `.gse/config.yaml` — project configuration (if it exists)
3. `.gse/backlog.yaml` — work items and their statuses (if it exists)
4. `.gse/profile.yaml` — user profile (if it exists)
5. `.gse/plan.yaml` — living sprint plan (workflow, budget, coherence) — primary source for decision tree (if it exists)


## Workflow

### Step 1 — Detect Project State

Examine the working directory to classify the situation.

**"Project files" definition:** Only count files that belong to the actual project. **Exclude** the following directories from the file count — they are tool/IDE configuration, not project content:
- `.cursor/`, `.claude/`, `.gse/` — agent/plugin artifacts
- `.git/` — version control internals
- `.vscode/`, `.idea/`, `.fleet/` — IDE settings
- `node_modules/`, `__pycache__/`, `.venv/`, `target/`, `dist/`, `build/` — generated/dependency directories

| Condition | State | Action |
|-----------|-------|--------|
| No `.gse/` directory AND project files exist (after exclusions) | **Adopt candidate** | Transition to Adopt mode (Step 8) |
| No `.gse/` directory AND directory is empty/near-empty (only excluded dirs) | **New project** | **Automatically execute** `/gse:hug` (do NOT just propose it — run it directly). No preamble, no table, no technical explanation. |
| `.gse/` exists | **Existing project** | Read `status.yaml` and proceed to Step 2 |

**New project auto-start rule:** When the project is empty, the user's intent is clear — they want to get started. The agent MUST immediately execute the HUG skill inline (language question first, then profile interview) without asking for confirmation or displaying diagnostic output. The user should see the HUG language question as the very first interaction, not a status table.

### Step 2 — Recovery Check (Unsaved Work Detection)

If `.gse/` exists, scan for unsaved work before proceeding:

1. **Check worktrees** — For each worktree listed in `config.yaml → git.worktree_dir` (default `.worktrees/`), run `git status`. Detect uncommitted changes.
2. **Check main working directory** — Run `git status` on the project root.
3. **If uncommitted changes are found:**
   - Report clearly: *"I found unsaved changes in N worktree(s). This usually means the previous session ended without `/gse:pause`."*
   - List each worktree with changes (branch name, number of modified files)
   - Present Gate decision:
     - **Recover** (default) — Auto-commit changes with message `gse(recovery): checkpoint — unsaved work from previous session`
     - **Review first** — Show the diff before committing
     - **Discard** — Discard uncommitted changes (confirm twice — destructive)
     - **Skip** — Continue without committing (changes remain uncommitted)
4. **If no uncommitted changes** — Proceed to Step 2.5.

### Step 2.5 — Dependency Vulnerability Check

If `config.yaml → dependency_audit: true` (default for projects with package manifests):

1. **Detect package manager** — Look for `package-lock.json` / `yarn.lock` (npm audit), `requirements.txt` / `pyproject.toml` (pip-audit), `Cargo.lock` (cargo audit), `go.sum` (govulncheck).
2. **Run audit** — Execute the appropriate audit command.
3. **If critical vulnerabilities found** — Soft guardrail: report the vulnerability and suggest updating. For beginners: "I found a security issue in one of the tools this project uses. I recommend updating it before we continue."
4. **If no vulnerabilities or low-severity only** — Proceed to Step 2.6.

### Step 2.6 — Dashboard Refresh

1. **Validate tool registry** — Run `cat ~/.gse-one`. If the file is missing or the path it contains does not exist, warn the user: "GSE-One registry not found. Run `python3 install.py` to fix." and skip dashboard generation.
2. **Regenerate `docs/dashboard.html`** — Run `python3 "$(cat ~/.gse-one)/tools/dashboard.py"` to update the dashboard with current state.
3. This runs silently — no message to the user unless it's the first generation (in which case, inform per HUG Step 5.5 rules).

### Step 2.7 — Git Baseline Verification

If `.gse/config.yaml` → `git.strategy` is `worktree` or `branch-only`:

1. **Verify `main` has at least one commit:**
   ```bash
   git rev-parse --verify main
   ```
2. **If this fails** (no commits on `main`) — **Hard guardrail**: the repository was initialized but has no foundational commit. This blocks all branching operations.
   - If `.gitignore` exists but is not committed: auto-fix by committing it: `git add .gitignore && git commit -m "chore: initialize repository"`.
   - If no files exist to commit: create `.gitignore` and commit it.
   - For beginners: "I need to save a first checkpoint in version control before we can organize the work properly. I'll do it now."
3. **If `main` exists** — proceed to Step 3.

This step is a **safety net** for cases where HUG Step 4 was interrupted or the foundational commit was not created.

### Step 3 — Determine Next Action (Decision Tree)

Read `status.yaml` fields: `current_sprint`, `lifecycle_phase`, `last_activity`, `last_activity_timestamp`, AND `.gse/plan.yaml` when it exists.

**Primary source — `.gse/plan.yaml`:** When `plan.yaml` exists with `status: active`, use `workflow.active` and `workflow.pending` to decide the next activity. This is more robust than checking for individual artefact files.

**Fallback:** If `plan.yaml` is absent (Micro mode or pre-v0.20 projects), fall back to file-existence checks against sprint artefacts (`reqs.md`, `design.md`, `test-strategy.md`, …) in `docs/sprints/sprint-{NN}/`.

Evaluate states **in order** — the first matching row wins.

| Current State | Proposed Action |
|---------------|-----------------|
| No sprint defined | Sub-decision below |
| `plan.yaml` exists, `status: draft` | Resume PLAN — present plan summary, ask for approval Gate |
| `plan.yaml.workflow.active == reqs` | Start REQS — **test-driven requirements**: every REQ MUST include testable acceptance criteria (Given/When/Then or equivalent) and identify open technical questions. These criteria become the spec for validation tests. **Hard guardrail: PRODUCE MUST NOT start until REQS exist.** |
| `plan.yaml.workflow.active == design` | Start DESIGN. If tasks do not involve architecture decisions (new data model, API design, component structure), record `design` in `workflow.skipped` and advance. |
| `plan.yaml.workflow.active == preview` | Start PREVIEW — show mockup/prototype for user validation before coding. For CLI/API/data/embedded: `preview` should already be in `workflow.skipped`. |
| `plan.yaml.workflow.active == tests` | Start TESTS `--strategy` — define test pyramid: verification tests (from DESIGN) + validation tests (from REQS acceptance criteria). |
| `plan.yaml.workflow.active == produce`, none in-progress | Start PRODUCE on first planned TASK |
| `plan.yaml.workflow.active == produce`, tasks `in-progress` | Resume PRODUCE — show current task, propose continuation |
| `plan.yaml.workflow.active == review` | Start REVIEW — propose `/gse:review` (requires test evidence — will block if tests were skipped) |
| `plan.yaml.workflow.active == fix` | Start FIX — propose `/gse:fix` |
| `plan.yaml.workflow.active == deliver` | Start DELIVER — propose `/gse:deliver` (requires REQ→TST coverage for must-priority requirements) |
| `plan.yaml.status == completed`, no compound | Start LC03 — propose `/gse:compound` |
| Compound done | Propose next sprint — increment sprint number, transition to LC01 (`COLLECT` > `ASSESS` > `PLAN`) |

**Post-activity protocol:** After each activity completes, the orchestrator updates `.gse/plan.yaml` per the **Sprint Plan Maintenance** protocol in the orchestrator (workflow transition, coherence evaluation, alerts by mode). See the orchestrator document for the full protocol.

**"No sprint defined" sub-decision** (evaluated in order):
1. If `it_expertise: beginner` and `current_sprint: 0` (first time) → start **Intent-First mode** (Step 7). After intent is captured, proceed to step 2 (do NOT skip directly to LC01).
2. **Complexity assessment** (Step 6) — Scan structural signals and recommend a mode (Gate). Based on chosen mode:
   - **Micro** → start PRODUCE
   - **Lightweight** → start PLAN
   - **Full** → start LC01: `/gse:collect` > `/gse:assess` > `/gse:plan --strategic`

**Lifecycle guardrails (mode-differentiated):**
1. **No PRODUCE without REQS (Full and Lightweight)** — No TASK can move to `in-progress` unless at least one REQ- artefact with testable acceptance criteria is traced to it. REQS is test-driven: acceptance criteria ARE the future validation test specs. For beginners: "Before I start building, I need to write down exactly what the app should do and how we'll check it works — and have you confirm." **Exception:** Micro mode and `artefact_type: spike`.
2. **No PRODUCE without test strategy (Full only)** — The test approach (verification from DESIGN + validation from REQS acceptance criteria) must be defined before coding starts. Test strategy comes AFTER DESIGN and PREVIEW. In Lightweight mode, a minimal test strategy is auto-generated at PRODUCE time (Soft guardrail — Inform tier). For beginners: "Before I build, I'll describe how we'll verify each feature works correctly." **Exception:** Micro mode and `artefact_type: spike`.

**Decision tier override:**
3. **Supervised mode** — When `decision_involvement: supervised`, ALL technical choices during PRODUCE are escalated to **Gate-tier** decisions. The agent presents options and waits for user confirmation.

Present the proposal and wait for user confirmation before executing.

### Step 4 — Stale Sprint Detection

Read `config.yaml → lifecycle.stale_sprint_sessions` (default: 3 sessions).

Track the number of sessions (invocations of `/gse:go` or `/gse:resume`) where no TASK has progressed to a new status. A "progression" is any TASK moving from one status to the next (open→planned, planned→in-progress, in-progress→review, review→fixing, fixing→done, done→delivered, etc.).

If the session-without-progress count reaches the configured threshold:

1. Report: "Sprint {NN} has had {N} sessions without progress."
2. Present Gate decision:
   - **Resume** — Continue where we left off (default)
   - **Partial delivery** — Deliver completed tasks, move remaining to pool
   - **Discard** — Abandon sprint, return all tasks to pool
   - **Discuss** — Explain the situation and help decide

### Step 5 — Failure Handling

If the last activity ended with an error or incomplete state:

1. Create a checkpoint of current state
2. Report what failed and why (if determinable)
3. Present Gate decision:
   - **Retry** — Re-attempt the failed activity
   - **Skip** — Mark as skipped, proceed to next activity
   - **Pause** — Save state and stop (user will return later)
   - **Discuss** — Explore alternatives

### Step 6 — Mode Selection (Complexity Assessment)

**Trigger:** Reached from Step 3 when no sprint is defined (after Intent-First if applicable). At this point `.gse/` already exists (created by HUG or adopt).

#### Step 6.1 — Scan Structural Signals

Evaluate the project using these 7 complexity signals (each takes <1 second):

| Signal | How to detect | Result |
|--------|--------------|--------|
| **Dependencies** | Read package manifest (`package.json` → dependencies, `pyproject.toml` → `[project.dependencies]`, `Cargo.toml`, `go.mod`) | count of direct deps |
| **Persistence** | Search for: ORM imports (sqlalchemy, prisma, typeorm, mongoose), SQL files (`*.sql`), docker-compose with db service, `.env` with `DB_URL`/`DATABASE_URL` | yes / no |
| **Entry points** | Scan for: route definitions, page components, CLI command registrations, main entry files | count |
| **Multi-component** | Multiple package manifests, workspace config (`nx.json`, `turbo.json`, `pnpm-workspace.yaml`), presence of `frontend/` + `backend/` | yes / no |
| **Existing tests** | Test directories (`tests/`, `__tests__/`, `test/`), test files (`*.test.*`, `test_*.*`) | yes / no |
| **CI/CD** | `.github/workflows/`, `.gitlab-ci.yml`, `Dockerfile`, `Jenkinsfile` | yes / no |
| **Git maturity** | `git rev-list --count HEAD`, `git branch --list`, `git shortlog -sn` | commits, branches, contributors |

#### Step 6.2 — Determine Recommended Mode

Apply these rules (first match wins). The first rule uses source file count as a **trivialiy pre-filter** (not a complexity signal):

| Condition | Recommended mode |
|-----------|-----------------|
| No manifest AND no git history AND ≤ 2 source files (excluding deps/generated/IDE per Step 1 rules) | **Micro** |
| Persistence OR multi-component OR CI/CD OR dependencies > 10 OR entry points > 10 | **Full** |
| Existing tests AND (dependencies > 3 OR entry points > 3) | **Full** |
| Otherwise | **Lightweight** |

Confidence level:
- **High** — 3+ signals clearly point to one mode
- **Moderate** — signals are mixed → present both options prominently
- **Low** — project is empty or signals are ambiguous → ask the user

#### Step 6.3 — Present Mode Decision (Gate)

Present the recommendation with rationale adapted to user expertise:

**Beginner:**
"I've looked at your project. It's [simple / moderately complex / complex]. I recommend working in [mode description — no mode name]. This means: [1-2 sentences describing what happens]. Does that sound right?"

**Intermediate/Expert:**
"Complexity assessment: [signal summary]. Recommended mode: [Micro/Lightweight/Full] — [rationale]."
1. Accept [recommended]
2. Use [alternative] instead
3. Discuss

After the user confirms, set `config.yaml → lifecycle.mode` and proceed:
- **Micro** → start PRODUCE
- **Lightweight** → start PLAN
- **Full** → start LC01 (`COLLECT` > `ASSESS` > `PLAN`)

#### Mode comparison

| Aspect | Full Mode | Lightweight Mode | Micro Mode |
|--------|-----------|-----------------|------------|
| Selection | Complex project (persistence, multi-component, CI, many deps) | Simple project (few deps, single component, no persistence) | Trivial project (script, one-off, experiment) |
| Lifecycle | LC01 > LC02 > LC03 | PLAN > REQS > PRODUCE > DELIVER | PRODUCE > DELIVER |
| `.gse/` state | 4 files (config, profile, status, backlog) + plan.yaml | 4 files + plan.yaml | 1 file (`status.yaml` with inline profile + task list) |
| Git strategy | `worktree` (sprint + feature branches) | `branch-only` (single feature branch from main) | direct commit (no branch creation) |
| Sprint artefacts | Full set (plan-summary, reqs, design, tests, review, compound) | reqs.md only | None |
| Health dashboard | 8 dimensions | 3 (test_pass_rate, review_findings, git_hygiene) | None |
| Complexity budget | Tracked | Not tracked | Not tracked |
| Decision tiers | Full P7 assessment (Auto + Inform + Gate) | Simplified (Auto + Gate only) | Gate only (security/destructive) |
| REQS guardrail | Hard (mandatory) | Hard (mandatory, reduced ceremony) | Not enforced |
| TESTS guardrail | Hard (formal strategy required) | Soft (auto-generated strategy, Inform) | Not enforced |
| REQS ceremony | Full: elicitation + REQs + quality checklist + coverage analysis | Reduced: elicitation + REQs (no quality checklist, no coverage analysis) | None |
| DESIGN / PREVIEW | Yes (conditional) | No | No |
| REVIEW / COMPOUND | Yes | No | No |

User can upgrade from Micro → Lightweight → Full at any time via `/gse:go` — the agent scaffolds the missing structure.

### Step 7 — Intent-First Mode (Beginner + First Sprint)

**Trigger:** Reached from Step 3 when `it_expertise: beginner` and `current_sprint: 0` (first time). At this point `.gse/` exists with a profile from HUG.

The orchestrator enters a conversational mode to clarify the user's intent before determining the project mode:

1. **Elicit intent** — Ask in simple terms:
   *"Describe in a few sentences what you'd like to build or achieve."*
   Let the user express freely. Do not ask for technical details.

2. **Reformulate and validate** — Translate the intent into a structured summary using the user's vocabulary (no jargon):
   *"If I understand correctly, you want: [bulleted list in plain language]. Is that right?"*
   Iterate until the user confirms.

3. **Translate to backlog** — Convert the validated intent into initial TASK items in `backlog.yaml`. Present them as concrete goals, not technical work items:
   *"Here's what we'll work on: [list of goals]. I'll guide you through each step."*

4. **Transition to complexity assessment** — Proceed to **Step 6 (Mode Selection)** to determine the appropriate mode based on project complexity. The mode determines the lifecycle path:
   - **Micro** → PRODUCE (for a quick script, the agent starts building immediately)
   - **Lightweight** → PLAN > REQS > PRODUCE > DELIVER (for a simple app)
   - **Full** → COLLECT > ASSESS > PLAN > ... (for a complex project)
   Present each activity in plain language for the beginner:
   - PLAN → *"Let me organize the work into manageable steps"*
   - REQS → *"Let me write down exactly what the application should do"*
   - PRODUCE → *"Now I'll build it"*
   - DELIVER → *"Let me finalize and package the result"*

5. **Exit condition** — The user can say *"I know the process, let's skip ahead"* at any point. The agent switches to normal orchestration immediately and updates the profile: `it_expertise: intermediate`.

### Step 8 — Adopt Mode (`--adopt`)

**Trigger:** Reached from Step 1 (auto-detected: no `.gse/` + project files exist) or via explicit `--adopt` flag.

**Guard:** If `--adopt` is used but `.gse/` already exists, warn: "This project already has GSE-One state. Use `/gse:go` without `--adopt` to continue, or delete `.gse/` first to re-adopt from scratch." Do NOT proceed.

**Non-destructive guarantee:** The adopt flow NEVER modifies existing files without explicit user approval. It can be interrupted and resumed at any point.

1. **Identify** — Detect language/framework from manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.)
2. **Scan** — Run `/gse:collect` (internal mode) to inventory all existing artefacts
3. **Infer state** — Analyze git history to estimate:
   - How many sprints of work exist (commits, age, tags)
   - What was the last stable release (latest tag)
   - Are there lingering branches
   - Project domain from dependencies
   - Git strategy from existing branch patterns
   - Team context from git log (multiple committers?)
4. **Initialize** — Create `.gse/` directory with:
   - `config.yaml` — populated with inferred domain and git strategy
   - `status.yaml` — set to `current_sprint: 0`, `current_phase: LC01`
   - `backlog.yaml` — empty, ready for population
   - `profile.yaml` — trigger `/gse:hug` if no profile exists
5. **Set baseline** — Record current state as **sprint 0** — the starting point for the first GSE-managed sprint. Current `main` HEAD is the baseline.
6. **Propose annotation** (Gate decision):
   ```
   I found N existing artefacts. Add GSE-One traceability metadata?
   1. Yes, annotate all — add YAML frontmatter to existing .md files
   2. Annotate new artefacts only — leave existing files untouched
   3. Skip annotation entirely
   4. Discuss
   ```
7. **Transition** — Proceed to normal LC01 for sprint 1: `COLLECT` > `ASSESS` > `PLAN`
