---
description: "View and manage project backlog. Triggered when user asks about tasks, work items, what's left to do."
---

# GSE-One Backlog — Unified Work Item Management

Arguments: $ARGUMENTS

## Options

| Flag / Sub-command | Description |
|--------------------|-------------|
| (no args)          | Display the full backlog grouped by sprint and pool |
| `add <description>` | Add a new work item to the pool |
| `sprint`           | Show only items in the current sprint |
| `pool`             | Show only items in the unassigned pool |
| `--type <type>`    | Filter by artefact type (code, requirement, design, test, doc, config, import) |
| `sync`             | Synchronize backlog with GitHub Issues (bidirectional) |
| `--help`           | Show this command's usage summary |

## Prerequisites

Before executing, read:
1. `.gse/backlog.yaml` — current backlog state
2. `.gse/status.yaml` — current sprint number
3. `.gse/config.yaml` — GitHub integration settings (if enabled)
4. `.gse/profile.yaml` — user profile (apply P9 Adaptive Communication to all output)

## Workflow

### Display Mode (No Args / `sprint` / `pool`)

#### Step 1 — Load Backlog

Read `.gse/backlog.yaml` and parse all work items.

#### Step 2 — Group and Format

Display items grouped by assignment:

```
Sprint S02 (current)
─────────────────────
  TASK-007 [code]     ● in-progress  feat/user-auth       Implement JWT authentication
  TASK-008 [test]     ○ planned      feat/user-auth-test   Write auth endpoint tests
  TASK-009 [doc]      ○ planned      —                     Document auth API

Sprint S01 (delivered)
─────────────────────
  TASK-001 [code]     ✓ done         feat/project-init     Initialize project structure
  TASK-002 [design]   ✓ done         feat/db-schema        Design database schema
  TASK-003 [test]     ✓ done         feat/db-schema-test   Write schema migration tests

Pool (unassigned)
─────────────────
  TASK-010 [code]     ◌ pool         —                     Add rate limiting middleware
  TASK-011 [design]   ◌ pool         —                     Design notification system
  TASK-012 [requirement] ◌ pool      —                     Define admin role permissions
```

Status symbols:
- `✓` done
- `●` in-progress
- `○` planned (assigned to sprint but not started)
- `◌` open (displayed as "Pool" — unassigned to any sprint)

#### Step 3 — Summary Line

Show totals: "12 items total: 3 done, 1 in-progress, 2 planned, 6 in pool"

### Add Mode (`add <description>`)

#### Step 1 — Auto-Increment ID

Read `.gse/backlog.yaml`, find the highest TASK-NNN ID, increment by 1.

#### Step 2 — Infer Artefact Type

From the description, infer the most likely type:

| Keywords | Inferred Type |
|----------|--------------|
| implement, build, create, add feature, code | `code` |
| test, verify, validate, check | `test` |
| design, architect, structure, schema | `design` |
| require, must, should, user story | `requirement` |
| document, write docs, README | `doc` |
| configure, setup, CI, deploy | `config` |

If ambiguous, default to `code` and note the assumption.

#### Step 3 — Create Entry

Add to `.gse/backlog.yaml`:

```yaml
- id: TASK-013
  artefact_type: code
  title: "Add rate limiting middleware"
  description: "Implement rate limiting for API endpoints using token bucket algorithm"
  sprint: null  # null = pool (unplanned)
  status: open  # open | planned | in-progress | review | fixing | done | delivered | deferred
  priority: should  # default, can be changed
  complexity: null  # set during planning
  created: 2026-01-20
  git:
    branch: null
    branch_status: null
  traces:
    derives_from: []
    github_issue: null
```

#### Step 4 — GitHub Issue (If Enabled)

If `.gse/config.yaml` has `github.issues_sync: true`:
- Create a GitHub Issue with matching title and description
- Store the issue number in `traces.github_issue`
- Apply labels based on artefact type

### Sync Mode (`sync`)

#### Step 1 — Pull from GitHub

Fetch all open GitHub Issues for the repository:
- For each issue NOT in backlog: create a new TASK entry in pool
- For each issue that matches an existing TASK: update status if changed

#### Step 2 — Push to GitHub

For each TASK with `github_issue: null` and `github.issues_sync: true`:
- Create a GitHub Issue
- Store the issue number

#### Step 3 — Bidirectional Status Sync

Map statuses between GSE-One and GitHub:

| GSE-One Status | GitHub State |
|---------------|-------------|
| `pool`        | open (label: `pool`) |
| `planned`     | open (label: `sprint-NN`) |
| `in-progress` | open (label: `in-progress`) |
| `done`        | closed |

Report sync summary: "Synced 15 items. 2 new from GitHub, 1 status updated, 12 unchanged."

### Auto-Creation by Other Skills

Other GSE-One activities create backlog items automatically:

| Source Skill | Created Items |
|-------------|---------------|
| REVIEW | Fix items from review findings (e.g., TASK-014 from RVW-002) |
| PLAN | Promotes pool items to sprint, may split large items |
| COLLECT | Import items from external sources (e.g., GitHub Issues from scanned repos) |
| DELIVER | Close items, create follow-up items for deferred scope |

These auto-created items always include `traces.derives_from` linking to the source artefact.
