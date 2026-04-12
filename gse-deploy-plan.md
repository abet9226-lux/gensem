# GSE-Deploy — Production Plan

**Date:** 2026-04-12
**Status:** Draft
**Input:** StreamTeX stx-deploy skills analysis, GSE-One plugin architecture (v0.11.0)

---

## 1. Vision

A cross-platform plugin (Claude Code + Cursor) that manages application deployment on Hetzner Cloud servers, usable:
- **With GSE-One**: triggered after `/gse:deliver`, integrated with backlog and guardrails
- **Without GSE-One**: standalone, usable in any project (e.g., StreamTeX)
- **As stx-deploy successor**: progressive migration from the existing StreamTeX deployment skills

### 1.1 Scope v1

- Provider: Hetzner Cloud only (architecture supports future providers)
- PaaS: Coolify v4 (self-hosted)
- Environments: staging + production with promotion workflow
- Applications: any project with a Dockerfile (not limited to Streamlit)

### 1.2 Origin

The plugin is based on the 13 stx-deploy skills currently located in `streamtex/.claude/commands/stx-deploy/`. These skills are mature and production-tested but:
- Not structured as a plugin (no manifest, no frontmatter, no cross-platform support)
- Specific to StreamTeX/Streamlit (health checks, serve modes)
- No staging/production environment distinction
- No rollback capability
- State files named `.stx-deploy.*` (StreamTeX-specific)

---

## 2. Architecture

### 2.1 Repository Structure

```
gse-deploy/
├── src/                              # Source of truth
│   ├── activities/                   # 13 activity definitions → skills
│   │   ├── go.md                    # Orchestrator (zero-to-live)
│   │   ├── setup.md                 # Local environment setup
│   │   ├── provision.md             # Hetzner server provisioning
│   │   ├── secure.md                # Server hardening
│   │   ├── install-coolify.md       # Coolify v4 installation
│   │   ├── configure-domain.md      # DNS + SSL configuration
│   │   ├── deploy.md               # Single application deployment
│   │   ├── deploy-batch.md          # Multiple application deployment
│   │   ├── promote.md              # Staging → production promotion (NEW)
│   │   ├── rollback.md             # Rollback to previous version (NEW)
│   │   ├── update.md               # Rebuild deployed application
│   │   ├── status.md               # Infrastructure and app monitoring
│   │   └── scale.md                # Scaling operations
│   ├── agents/
│   │   └── deploy-operator.md       # Specialized deployment agent
│   ├── templates/
│   │   ├── deploy-config.yaml       # Deployment configuration schema
│   │   ├── deploy-state.json        # Infrastructure state schema
│   │   ├── Dockerfile.streamlit     # Dockerfile template: Streamlit apps
│   │   ├── Dockerfile.nextjs        # Dockerfile template: Next.js apps
│   │   └── Dockerfile.python        # Dockerfile template: generic Python
│   └── references/
│       ├── hetzner-infrastructure.md # Server types, pricing, datacenters
│       └── ssh-conventions.md        # SSH operations conventions
│
├── plugin/                           # Generated (mono-plugin, both platforms)
│   ├── .claude-plugin/plugin.json
│   ├── .cursor-plugin/plugin.json
│   ├── skills/                       # 13 skills (shared)
│   ├── agents/                       # 1 agent (shared)
│   ├── templates/                    # 5 templates (shared)
│   ├── references/                   # 2 references (shared)
│   ├── hooks/
│   │   ├── hooks.claude.json
│   │   └── hooks.cursor.json
│   ├── rules/
│   │   └── 000-deploy-methodology.mdc
│   └── settings.json
│
├── VERSION
├── CHANGELOG.md
├── README.md
├── install.py                        # Cross-platform installer
└── gse_deploy_generate.py            # Generator: src/ → plugin/
```

### 2.2 Design Choice: Mono-repo or Separate Repo?

**Alternative A — Inside the gensem repo (as `gse-deploy/` alongside `gse-one/`):**

| | |
|---|---|
| *Advantages* | Single repo, shared VERSION and CHANGELOG, shared install.py could handle both plugins, generator patterns reusable. |
| *Disadvantages* | Couples two independent plugins. Users who want only deploy must clone the full gensem repo. Version bumps affect both plugins even when only one changed. |

**Alternative B — Separate repo (`gse-deploy/`):**

| | |
|---|---|
| *Advantages* | Independent lifecycle, independent versioning, independent installation. Users install only what they need. Clean separation of concerns. |
| *Disadvantages* | Two repos to maintain. Cannot share generator code directly (must copy or extract a shared library). |

**Recommendation:** B — separate repo. The two plugins have different lifecycles (GSE-One evolves with methodology, gse-deploy evolves with infrastructure). Shared patterns (generator structure, install.py template) are copied, not linked.

---

## 3. Skill Conversion Plan

### 3.1 Conversion from stx-deploy to gse-deploy

Each stx-deploy skill is converted following these rules:

| Aspect | stx-deploy (current) | gse-deploy (target) |
|--------|---------------------|---------------------|
| Location | `.claude/commands/stx-deploy/` | `plugin/skills/<name>/SKILL.md` |
| Frontmatter | None | YAML frontmatter (description, trigger) |
| Arguments | `$ARGUMENTS` raw text | `$ARGUMENTS` with documented parsing |
| Agent loading | Manual: "Read deploy-operator.md" | Automatic via settings.json / .mdc rule |
| State files | `.stx-deploy.env`, `.stx-deploy.json` | `.deploy.env`, `.deploy.json` |
| Health check | Hardcoded `/_stcore/health` (Streamlit) | Configurable per app type |
| Environments | None (single deployment) | staging + production with promotion |
| Naming | `/stx-deploy:command` | `/deploy:command` |

### 3.2 Design Choice: Plugin Prefix

**Alternative A — `/deploy:command`:**

| | |
|---|---|
| *Advantages* | Short, generic, works with or without GSE-One. |
| *Disadvantages* | Could conflict with other deploy plugins. |

**Alternative B — `/gse-deploy:command`:**

| | |
|---|---|
| *Advantages* | Clearly part of the GSE ecosystem. No conflict risk. |
| *Disadvantages* | Longer to type. Implies dependency on GSE-One (which doesn't exist). |

**Alternative C — `/hetzner:command`:**

| | |
|---|---|
| *Advantages* | Explicit about the target provider. |
| *Disadvantages* | Too specific. Cannot be reused for other providers. |

**Recommendation:** A — `/deploy:command`. Short, generic, and the plugin manifest `name` field handles namespacing.

### 3.3 New Skills (not in stx-deploy)

| Skill | Purpose | Rationale |
|-------|---------|-----------|
| `promote.md` | Staging → production promotion | Staging/production is new. Needs its own workflow: verify staging, Gate decision, deploy to production, verify, rollback if failed. |
| `rollback.md` | Revert to previous deployment | stx-deploy has no rollback. Critical for production safety. Uses Coolify's Docker image tags to revert. |

### 3.4 Removed Skills (merged or dropped)

| stx-deploy skill | Decision | Rationale |
|-----------------|----------|-----------|
| `preflight.md` | Merged into `deploy.md` Step 1 | Preflight is always run before deploy — no reason for a separate command. |
| `setup-loadbalancer.md` | Kept as `scale.md` advanced option | Load balancing is a scaling concern, not a separate workflow. |

---

## 4. State Management

### 4.1 Credentials: `.deploy.env`

```bash
# GSE-Deploy credentials (gitignored)
# Generated by /deploy:setup

HETZNER_API_TOKEN=xxxx
DEPLOY_DOMAIN=example.com
COOLIFY_URL=https://coolify.example.com
COOLIFY_API_TOKEN=xxxx

# Optional
CLOUDFLARE_API_TOKEN=xxxx
```

### 4.2 Infrastructure State: `.deploy.json`

```json
{
  "version": "2.0",
  "plugin": "gse-deploy",
  "created_at": "2026-04-12T10:00:00Z",

  "infrastructure": {
    "provider": "hetzner",
    "server": {
      "name": "my-server",
      "id": 12345,
      "type": "cax21",
      "ipv4": "1.2.3.4",
      "datacenter": "fsn1"
    },
    "coolify": {
      "version": "4.x",
      "url": "https://coolify.example.com",
      "server_uuid": "..."
    },
    "security": {
      "firewall_id": 67890,
      "ssh_user": "deploy",
      "fail2ban": true
    }
  },

  "phases_completed": {
    "setup": "2026-04-12T10:00:00Z",
    "provision": "2026-04-12T10:05:00Z",
    "secure": "2026-04-12T10:10:00Z",
    "install_coolify": "2026-04-12T10:15:00Z",
    "configure_domain": "2026-04-12T10:20:00Z"
  },

  "applications": [
    {
      "name": "my-app",
      "uuid": "coolify-uuid",
      "github_repo": "user/repo",
      "type": "streamlit",
      "resources": {
        "memory": "512m",
        "cpu": "0.5",
        "replicas": 1
      },
      "environments": {
        "staging": {
          "url": "https://staging-my-app.example.com",
          "version": "1.2.0",
          "deployed_at": "2026-04-12T11:00:00Z",
          "status": "healthy",
          "coolify_uuid": "..."
        },
        "production": {
          "url": "https://my-app.example.com",
          "version": "1.1.0",
          "deployed_at": "2026-04-10T14:00:00Z",
          "status": "healthy",
          "coolify_uuid": "...",
          "previous_version": "1.0.0"
        }
      }
    }
  ]
}
```

### 4.3 Design Choice: State File Names

**Alternative A — `.deploy.env` / `.deploy.json` (generic):**

| | |
|---|---|
| *Advantages* | Provider-agnostic. Clean. Works for any future provider. |
| *Disadvantages* | Could conflict with other tools that use `.deploy.*`. |

**Alternative B — `.gse-deploy.env` / `.gse-deploy.json` (namespaced):**

| | |
|---|---|
| *Advantages* | No conflict risk. Clearly identified as GSE ecosystem. |
| *Disadvantages* | Longer filenames. Implies GSE dependency. |

**Alternative C — `.stx-deploy.env` / `.stx-deploy.json` (backward compatible):**

| | |
|---|---|
| *Advantages* | Zero migration for StreamTeX users. Existing state files work immediately. |
| *Disadvantages* | StreamTeX-specific naming in a generic plugin. Confusing for non-StreamTeX users. |

**Recommendation:** A with migration support — use `.deploy.*` as default, but the setup skill detects and offers to migrate existing `.stx-deploy.*` files.

---

## 5. Environment Management (Staging / Production)

### 5.1 Configuration (`deploy-config.yaml`)

```yaml
# GSE-Deploy Configuration
# Generated by /deploy:setup

provider: hetzner

project:
  name: ""
  type: auto                           # auto | streamlit | nextjs | python | static

environments:
  staging:
    server: auto                       # same server, subdomain staging-*
    auto_deploy: true                  # deploy automatically after tag/push
    health_check:
      url: auto                        # auto-detected based on app type
      timeout: 120                     # seconds
    promotion_gate: false              # no Gate for staging deployment

  production:
    server: auto                       # same server or dedicated
    auto_deploy: false                 # always Gate decision
    health_check:
      url: auto
      timeout: 180
    promotion_gate: true               # Gate required for production
    requires_staging: true             # must be deployed to staging first
    rollback_on_failure: true          # auto-rollback if health check fails

domain:
  base: ""                             # e.g., example.com
  registrar: auto                      # auto | cloudflare | manual
  staging_prefix: "staging-"           # staging-app.example.com
  production_prefix: ""                # app.example.com

security:
  ssh_key: auto                        # auto-detected or explicit path
  non_root_user: deploy
  firewall: true
  fail2ban: true

resources:
  default_memory: 512m
  default_cpu: "0.5"
  profiles:
    documentation: {memory: 256m, cpu: "0.25"}
    webapp: {memory: 512m, cpu: "0.5"}
    ai: {memory: 2g, cpu: "2.0"}
```

### 5.2 Promotion Workflow

```
/deploy:deploy my-app                    # deploys to staging (default)
  → Preflight checks
  → Build + deploy to staging-my-app.example.com
  → Health check (120s timeout)
  → Status: staging healthy

/deploy:promote my-app                   # promotes staging → production
  → Verify staging is healthy
  → Gate decision: "Deploy v1.2.0 to production?"
  → Deploy to my-app.example.com
  → Health check (180s timeout)
  → If healthy: update state, report success
  → If unhealthy: auto-rollback to previous version, report failure
```

### 5.3 Design Choice: Default Environment for `/deploy:deploy`

**Alternative A — Default to staging:**

| | |
|---|---|
| *Advantages* | Safe by default. Production requires explicit promotion. Prevents accidental production deployments. |
| *Disadvantages* | Extra step for simple projects that don't need staging. |

**Alternative B — Default to production (with Gate):**

| | |
|---|---|
| *Advantages* | Simpler for small projects. One command to deploy. |
| *Disadvantages* | Production deployment as default is risky. Contradicts safety-first principles. |

**Alternative C — Configurable default:**

| | |
|---|---|
| *Advantages* | User chooses. Small projects can set `default_env: production`, mature projects use staging. |
| *Disadvantages* | One more config key. The "safe default" is diluted if the user overrides it. |

**Recommendation:** A — default to staging. The `--env production` flag is available for explicit override. `/deploy:promote` is the formal path to production.

---

## 6. GSE-One Integration

### 6.1 Detection and Adaptation

When gse-deploy detects `.gse/config.yaml` in the project, it adapts:

| Without GSE-One | With GSE-One |
|----------------|-------------|
| Standalone operation | Reads user profile for communication calibration |
| No backlog integration | Can create TASK items of type `deploy` in backlog.yaml |
| Simple confirmations | Uses GSE-One decision tiers (Auto/Inform/Gate) |
| No health dashboard | Reports deploy status to status.yaml `deploy` dimension |
| Own progress display | Follows P9 output formatting rules |

### 6.2 Post-Deliver Hook

When both plugins are installed, the user can configure GSE-One to trigger deployment after delivery:

```yaml
# .gse/config.yaml
git:
  post_tag_hook: "echo 'deploy:staging'"    # Signal for gse-deploy
```

The deploy-operator agent detects the signal and runs the staging deployment workflow.

### 6.3 Design Choice: Integration Coupling

**Alternative A — Loose coupling (detect and adapt):**

| | |
|---|---|
| *Advantages* | Each plugin works independently. No import/require relationship. Integration is optional and graceful. |
| *Disadvantages* | Integration features are limited to what can be detected at runtime. No compile-time guarantee. |

**Alternative B — Formal dependency (gse-deploy declares GSE-One as optional dependency):**

| | |
|---|---|
| *Advantages* | Manifest declares the relationship. Plugin manager could resolve dependencies. Richer integration possible. |
| *Disadvantages* | Plugin dependency management doesn't exist yet in Claude Code or Cursor. Over-engineering for current state. |

**Recommendation:** A — loose coupling. The plugin ecosystem is too young for formal dependencies. Detection-based adaptation is pragmatic and robust.

---

## 7. Hooks

### 7.1 System Hooks (2)

| Hook | Event | Trigger | Action | Exit |
|------|-------|---------|--------|------|
| Block unverified production deploy | PreToolUse / Bash | `ssh` or `curl` command targeting production server while staging is unhealthy | Block and warn | 2 |
| Health check after deploy | PostToolUse / Bash | `curl` command to Coolify deploy API | Read response, warn if deployment status is not "running" | 0 |

### 7.2 Design Choice: Hook Count

**Alternative A — Minimal (2 hooks as above):**

| | |
|---|---|
| *Advantages* | Follows GSE-One principle: hooks only for deterministic critical guardrails. Everything else is agent behavior. |
| *Disadvantages* | Limited automated protection. |

**Alternative B — Rich (5+ hooks: pre-deploy check, post-deploy health, cost alert, SSH guard, credential leak detection):**

| | |
|---|---|
| *Advantages* | More automated safety nets. |
| *Disadvantages* | Violates the principle established in GSE-One: hooks are for non-negotiable constraints, not for things the agent can handle adaptively. Maintenance burden. |

**Recommendation:** A — minimal hooks. The deploy-operator agent handles health checks, cost awareness, and credential safety through its reasoning, not through rigid hooks.

---

## 8. Agent: deploy-operator

### 8.1 Role Definition

Based on the existing stx-deploy deploy-operator agent, generalized:

**Core principles:**
- **Safety first** — Never skip security phases. Never expose credentials in logs.
- **Idempotence** — Every phase can be re-run safely. State file tracks completion.
- **Confirm costly operations** — Server creation, domain changes, production deployment are Gate decisions with cost display.
- **Progressive disclosure** — Show progress (`[N/M] Step...`), not implementation details.
- **Infrastructure as documentation** — The state file IS the documentation. No separate infra docs needed.

**Behavioral rules:**
- Always read `.deploy.env` and `.deploy.json` before any operation
- Never display API tokens, SSH keys, or passwords in chat output
- Always show cost impact before server creation or scaling
- Always verify SSH connectivity before remote operations
- Always run health checks after deployment
- Update `.deploy.json` after every successful phase

### 8.2 Design Choice: Agent Activation

**Alternative A — Default agent (always active):**

| | |
|---|---|
| *Advantages* | Deploy-operator is always available. No activation step. |
| *Disadvantages* | Conflicts with GSE-One's gse-orchestrator if both plugins are installed — only one can be the default agent. |

**Alternative B — Skill-activated (loaded when a /deploy: command is invoked):**

| | |
|---|---|
| *Advantages* | No conflict with other plugins. The agent is loaded contextually when needed. |
| *Disadvantages* | The agent body must be loaded by each skill (less automatic than default). |

**Alternative C — Cursor rule (alwaysApply) + Claude contextual:**

| | |
|---|---|
| *Advantages* | On Cursor, the rule is always active. On Claude, the agent is loaded contextually by skills. Cross-platform parity through different mechanisms (same pattern as GSE-One). |
| *Disadvantages* | The Cursor rule adds to context even when not deploying. |

**Recommendation:** B — skill-activated. This avoids conflict with GSE-One's orchestrator. Each deploy skill declares in its instructions: "Adopt the deploy-operator role." The Cursor .mdc rule uses `alwaysApply: false` with a description so the agent loads it when relevant.

---

## 9. Cross-Platform Support

### 9.1 Platform-Specific Files

| File | Claude Code | Cursor |
|------|:-----------:|:------:|
| `.claude-plugin/plugin.json` | Loaded | Ignored |
| `.cursor-plugin/plugin.json` | Ignored | Loaded |
| `hooks/hooks.claude.json` | Loaded | Ignored |
| `hooks/hooks.cursor.json` | Ignored | Loaded |
| `rules/000-deploy-methodology.mdc` | Ignored | Loaded |
| `settings.json` | Loaded | Ignored |
| `skills/`, `agents/`, `templates/`, `references/` | Shared | Shared |

### 9.2 SSH Operations on Windows

All SSH commands in skills use `ssh` which is available natively on:
- macOS: built-in
- Linux: built-in
- Windows 10+: built-in (OpenSSH client)

The `hcloud` CLI (Hetzner Cloud) is available on all three platforms via package managers.

No platform-specific SSH handling is needed — the same commands work everywhere.

---

## 10. Commands Reference

| Command | Description | Default Env |
|---------|-------------|:-----------:|
| `/deploy:go` | Zero-to-live — detect state, execute missing phases | staging |
| `/deploy:setup` | Configure local environment (tokens, SSH keys) | — |
| `/deploy:provision` | Create Hetzner server + firewall | — |
| `/deploy:secure` | Harden server (SSH, UFW, fail2ban) | — |
| `/deploy:install-coolify` | Install Coolify v4 | — |
| `/deploy:configure-domain` | Configure DNS and SSL | — |
| `/deploy:deploy [path]` | Deploy application to environment | staging |
| `/deploy:deploy-batch [dir]` | Deploy multiple applications | staging |
| `/deploy:promote [app]` | Promote staging to production (Gate) | staging → production |
| `/deploy:rollback [app]` | Rollback to previous version | production |
| `/deploy:update [app]` | Rebuild and redeploy | same env |
| `/deploy:status` | Show infrastructure and application status | all |
| `/deploy:scale [app]` | Scale application or server | production |

---

## 11. Production Sprints

### Sprint 1 — Foundations

**Goal:** Plugin skeleton, setup, provision, secure. The infrastructure can be created.

| Task | Deliverable |
|------|------------|
| Create repo structure (`gse-deploy/src/`, `plugin/`) | Directory skeleton |
| Write `gse_deploy_generate.py` | Generator (reuse GSE-One pattern) |
| Write `install.py` | Cross-platform installer (reuse GSE-One pattern) |
| Convert `setup.md` | Skill with frontmatter, `.deploy.env` |
| Convert `provision.md` | Skill with frontmatter, `.deploy.json` |
| Convert `secure.md` | Skill with frontmatter |
| Write `deploy-config.yaml` template | Full schema with environments |
| Write `deploy-state.json` template | Full schema with environments |
| Write `deploy-operator.md` agent | Generalized from stx-deploy-operator |
| Write `hetzner-infrastructure.md` reference | Adapted from stx-deploy |
| Write `ssh-conventions.md` reference | Adapted from stx-deploy |
| Write `README.md` | Installation, quick start |
| First generator run + verification | `plugin/` with 3 skills, 1 agent, 4 templates, 2 refs |

### Sprint 2 — Coolify + Deploy + Rollback

**Goal:** Applications can be deployed, health-checked, and rolled back.

| Task | Deliverable |
|------|------------|
| Convert `install-coolify.md` | Skill with frontmatter |
| Convert `configure-domain.md` | Skill with frontmatter |
| Convert `deploy.md` | Skill generalized (not Streamlit-only), staging/production |
| Write `promote.md` | New skill: staging → production with Gate |
| Write `rollback.md` | New skill: revert to previous Docker image |
| Write Dockerfile templates | Streamlit, Next.js, Python generic |
| Implement configurable health checks | Auto-detect by app type |
| Write hooks (2) | Production guard + post-deploy health |
| Generator run + full verification | `plugin/` with 8 skills |

### Sprint 3 — Orchestration + Batch + Monitoring

**Goal:** Full deployment lifecycle works end-to-end.

| Task | Deliverable |
|------|------------|
| Convert `go.md` | Orchestrator with state detection + staging/production |
| Convert `deploy-batch.md` | Skill generalized |
| Convert `update.md` | Skill with health check |
| Convert `status.md` | Skill with staging vs production view |
| Convert `scale.md` | Skill with recommendations + load balancer |
| Write Cursor `.mdc` rule | `alwaysApply: false`, description-based activation |
| Generator run + full verification | `plugin/` with 13 skills, all components |

### Sprint 4 — Integration + Documentation + Release

**Goal:** GSE-One integration works. StreamTeX migration documented. v1.0.0 released.

| Task | Deliverable |
|------|------------|
| GSE-One integration (optional, detection-based) | Detect `.gse/`, adapt behavior |
| Test with GSE-One post_tag_hook | End-to-end: deliver → deploy staging → promote |
| Test without GSE-One (standalone) | End-to-end: setup → go → deploy → promote |
| StreamTeX migration guide | Step-by-step: stx-deploy → gse-deploy |
| stx-deploy state migration | Auto-detect and convert `.stx-deploy.*` → `.deploy.*` |
| Cross-platform testing | macOS, Linux, Windows (SSH, hcloud) |
| CHANGELOG + VERSION v1.0.0 | Release |
| Git tag v1.0.0 | Publication |

---

## 12. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|:-----------:|-----------|
| Coolify API breaks between versions | Skills fail silently | Medium | Pin Coolify API version in deploy-config.yaml. Test before each release. |
| Credential exposure in chat logs | Security breach | Low | deploy-operator agent explicitly prohibits token display. No credentials in hooks. |
| Rollback fails (Docker image pruned) | Downtime | Low | State file records last 3 versions. Coolify retains images by default. |
| Divergence with stx-deploy during migration | Two systems to maintain | High | Migration guide + deprecation timeline. Sprint 4 focus. |
| Plugin too coupled to Hetzner | Not portable | Low (by design) | Provider-specific code isolated in references/. Skills use generic commands. |
| Conflict with GSE-One orchestrator | Both try to be default agent | Medium | deploy-operator is skill-activated, not default. No conflict. |
| Health check false positives | Unnecessary rollbacks | Medium | Configurable timeout and retry count. Gate decision before rollback in production. |

---

## 13. Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| Full pipeline works standalone | `/deploy:go` from zero to live app in staging + production |
| GSE-One integration works | `/gse:deliver` → automatic staging deploy → manual production promote |
| StreamTeX migration works | Existing `.stx-deploy.*` state migrated without data loss |
| Cross-platform | Tested on macOS and Linux (Windows: SSH + hcloud verified) |
| No credential leaks | No token or key visible in any chat output during full pipeline |
| Rollback works | `/deploy:rollback` restores previous version in under 60 seconds |
| Health checks reliable | No false positive rollbacks during normal deployment |

---

## 14. Open Questions

| # | Question | Options | Current Leaning |
|---|----------|---------|-----------------|
| 1 | Should the plugin support multiple Hetzner servers per project? | Single server (v1) vs multi-server (v1) | Single server for v1, multi-server via scale skill |
| 2 | Should Dockerfile templates be extensible by the user? | Fixed templates vs user-provided templates in `.deploy/templates/` | User-provided override if exists, otherwise plugin template |
| 3 | Should the plugin manage database deployments (PostgreSQL, Redis)? | v1 scope vs future | Future — Coolify handles databases natively, skills can reference them |
| 4 | Should auto-deploy (GitHub webhook) be configured by the plugin? | Yes (via Coolify API) vs manual Coolify dashboard | Yes for staging, manual for production |
| 5 | How to handle secrets/env vars per environment? | In `.deploy.env` vs in deploy-config.yaml vs in Coolify dashboard | Coolify dashboard for app secrets, `.deploy.env` for infrastructure tokens only |
