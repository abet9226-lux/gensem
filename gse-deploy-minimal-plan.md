# GSE-Deploy Minimal — Implementation Plan

**Date:** 2026-04-12
**Status:** Draft v2
**Approach:** Single skill `/gse:deploy` integrated into GSE-One plugin (no separate repo)
**Target:** Hetzner Cloud + Coolify v4, production only, single project
**Source:** Reuse of StreamTeX stx-deploy skills (streamtex-dev/.claude/commands/stx-deploy/)

---

## 1. Concept

Add a single `/gse:deploy` skill to GSE-One that handles application deployment on Hetzner Cloud via Coolify. The skill adapts to the user's starting situation — from zero infrastructure to a pre-configured shared server.

### 1.1 Flexible Starting Points

The skill detects what is already configured via the `.env` file and skips phases accordingly:

| Starting situation | Variables in `.env` | Phases executed |
|--------------------|---------------------|-----------------|
| **From scratch** (solo user) | Nothing | 1→2→3→4→5→6 |
| **Hetzner token provided** | `HETZNER_API_TOKEN` | 2→3→4→5→6 |
| **Server provided, no Coolify** | `HETZNER_API_TOKEN`, `SERVER_IP`, `SSH_USER` | 3→4→5→6 |
| **Server + Coolify provided** | `SERVER_IP`, `COOLIFY_URL`, `COOLIFY_API_TOKEN`, `DEPLOY_DOMAIN` | 6 only |
| **Training mode** (shared server) | `COOLIFY_URL`, `COOLIFY_API_TOKEN`, `DEPLOY_DOMAIN`, `DEPLOY_USER` | 6 only |
| **Everything pre-configured** | All variables | 6 only |

### 1.2 Training Scenario

An instructor provisions and configures a shared server once, then distributes a `.env.training` file to participants:

```
Instructor (once)                    Learners (N participants)
─────────────────                    ────────────────────────
/gse:deploy (full flow)              Copy .env.training → .env
  → provision server                 Set DEPLOY_USER=learnerXX
  → secure                           /gse:deploy
  → install Coolify                    → Phase 6 only (deploy app)
  → configure DNS                      → learner01.training.streamtex.org
  → extract .env.training             → learner02.training.streamtex.org
  → distribute to learners            → ...
```

Each learner's project is deployed as a separate Coolify application on the shared server, with a unique subdomain based on `DEPLOY_USER`.

### 1.3 What it does NOT do (vs the full gse-deploy plan)

- No staging environment (production only)
- No batch deployment (one project at a time)
- No scaling or load balancer
- No automated rollback (manual via Coolify dashboard)
- No promotion workflow
- No separate plugin

---

## 2. `.env` Variables — Complete Reference

All variables are optional. The skill detects which are present and adapts.

```bash
# ─── Level 1: Infrastructure (needed for server provisioning) ───
# If present: the skill can create and manage Hetzner servers
# If absent: the skill assumes infrastructure is pre-configured
HETZNER_API_TOKEN=xxxx

# ─── Level 2: Existing Server (skips provisioning) ───
# If present: the skill skips server creation, connects to this server
# If absent: the skill provisions a new server (needs HETZNER_API_TOKEN)
SERVER_IP=1.2.3.4
SSH_USER=deploy
SSH_KEY=~/.ssh/gse-deploy

# ─── Level 3: Existing Coolify (skips installation) ───
# If present: the skill skips Coolify installation, uses this instance
# If absent: the skill installs Coolify on the server
COOLIFY_URL=https://coolify.training.streamtex.org
COOLIFY_API_TOKEN=xxxx

# ─── Level 4: Domain (skips DNS configuration) ───
# If present: the skill uses this domain for subdomains
# If absent: the skill asks the user for a domain
DEPLOY_DOMAIN=training.streamtex.org

# ─── Level 5: User Identity (for shared servers) ───
# If present: used as subdomain prefix (learner01.training.streamtex.org)
# If absent: derived from project name (my-app.domain.com) or git user
DEPLOY_USER=learner01
```

### 2.1 Detection Logic

```
Read .env file (if exists)

If COOLIFY_URL AND COOLIFY_API_TOKEN AND DEPLOY_DOMAIN are present:
  → Skip to Phase 6 (deploy application only)
  → Subdomain: {DEPLOY_USER or project-name}.{DEPLOY_DOMAIN}

Else if SERVER_IP is present but no COOLIFY_URL:
  → Skip to Phase 3 (secure) or Phase 4 (install Coolify)
  → Depending on whether SSH_USER suggests server is already secured

Else if HETZNER_API_TOKEN is present but no SERVER_IP:
  → Skip to Phase 2 (provision server)

Else (nothing in .env):
  → Start at Phase 1 (setup — guide user to get credentials)
```

### 2.2 Template Files for Distribution

**`deploy-env.example`** — For solo users starting from scratch:
```bash
# GSE-One Deploy credentials
# Copy this file to .env and fill in your values
# NEVER commit .env to git

HETZNER_API_TOKEN=your-token-here
DEPLOY_DOMAIN=your-domain.com

# Filled automatically after Coolify installation:
# COOLIFY_URL=https://coolify.your-domain.com
# COOLIFY_API_TOKEN=your-coolify-token
```

**`deploy-env-training.example`** — For instructors to distribute to learners:
```bash
# GSE-One Deploy — Training Configuration
# Provided by your instructor. Copy to .env and set your DEPLOY_USER.
# NEVER commit .env to git

COOLIFY_URL=https://coolify.training.example.com
COOLIFY_API_TOKEN=instructor-provided-token
DEPLOY_DOMAIN=training.example.com

# === SET YOUR LEARNER ID BELOW ===
DEPLOY_USER=learnerXX
```

---

## 3. Files to Create

### 3.1 `src/activities/deploy.md` — The Skill

```markdown
---
description: "Deploy the current project to a Hetzner server via Coolify.
Adapts to the user's starting situation: from zero infrastructure to a
pre-configured shared server. Triggered by /gse:deploy."
---

# GSE-One Deploy — Hetzner Deployment

Arguments: $ARGUMENTS

## Options

| Flag | Description |
|------|-------------|
| (no args) | Deploy current project (detect situation, resume from last phase) |
| --status | Show deployment status (server, app URL, health) |
| --destroy | Tear down server and all data (Gate, confirm twice) |
| --redeploy | Force rebuild and redeploy (skip infrastructure phases) |
| --help | Show this command's usage summary |

## Prerequisites

Read before execution:
1. `.gse/config.yaml` — deploy section (provider, server type, datacenter)
2. `.gse/deploy.json` — infrastructure state (if exists)
3. `.env` — credentials and configuration (if exists)

## Workflow

### Step 0 — Situation Detection

Read `.env` and `.gse/deploy.json` (if they exist). Determine starting point:

| Variables present | Starting phase | Mode |
|-------------------|:-------------:|------|
| Nothing | Phase 1 | Full (solo) |
| HETZNER_API_TOKEN only | Phase 2 | Full (solo, token provided) |
| SERVER_IP + SSH_USER (no Coolify) | Phase 3 or 4 | Partial (server provided) |
| COOLIFY_URL + COOLIFY_API_TOKEN + DEPLOY_DOMAIN | Phase 6 | App-only (training or pre-configured) |
| All of the above | Phase 6 | App-only |

Also check `.gse/deploy.json → phases_completed` for already-completed phases.

Display the detected situation to the user:
- Full mode: "No deployment configuration found. I'll guide you through the complete setup."
- Partial: "I found a server at {IP}. Coolify is not installed yet. Starting from there."
- App-only: "Deployment infrastructure is ready ({COOLIFY_URL}). I'll deploy your application."

### Phase 1 — Setup (skip if HETZNER_API_TOKEN in .env)

1. **Check hcloud CLI**
   - Run `hcloud version`
   - If not found:
     - macOS: `brew install hcloud`
     - Linux: install via package manager or official binary
     - Windows: `winget install hetznercloud.cli` or direct download
   - Verify: `hcloud version`

2. **Obtain Hetzner API token**
   - Guide the user:
     "Go to https://console.hetzner.cloud → select or create a project →
     Security → API Tokens → Generate API Token (Read & Write).
     Copy the token — it is shown only once."
   - Ask the user to paste the token
   - Never display the token back in chat

3. **Domain name**
   - Ask: "What domain will you use? (e.g., my-project.com)"
   - Record for DNS configuration

4. **Save credentials**
   - Write or update `.env` at project root
   - Verify `.env` is in `.gitignore` — if not, add it and warn
   - Gate decision if `.gitignore` doesn't exist: create it

5. **Verify hcloud access**
   - Run `hcloud server list` to confirm token works
   - If it fails: ask user to check token

6. **Update state**
   - Create `.gse/deploy.json` with `phases_completed.setup` timestamp

### Phase 2 — Provision (skip if SERVER_IP in .env or deploy.json has phases_completed.provision)

1. **Read configuration**
   - Server type from `config.yaml → deploy.server_type` (default: cax21)
   - Datacenter from `config.yaml → deploy.datacenter` (default: fsn1)
   - Server name: `gse-<project-name>` (sanitized)

2. **Check for existing server**
   - Run `hcloud server list -o columns=name,ipv4`
   - If server already exists: skip provision, record IP

3. **Gate decision: server creation**
   - Display:
     "Creating a Hetzner server:
     - Type: CAX21 (4 vCPU ARM, 8 GB RAM, 80 GB SSD)
     - Location: Falkenstein (fsn1)
     - Monthly cost: ~8.49 EUR
     Proceed?"
   - Wait for explicit confirmation

4. **Generate SSH key** (if none exists)
   - `ssh-keygen -t ed25519 -f ~/.ssh/gse-deploy -N ""`
   - Upload to Hetzner: `hcloud ssh-key create --name gse-deploy --public-key-from-file ~/.ssh/gse-deploy.pub`

5. **Create server**
   - `hcloud server create --name <name> --type <type> --location <datacenter> --image ubuntu-24.04 --ssh-key gse-deploy`
   - Record IP address

6. **Create firewall**
   - Allow ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (Coolify setup, temporary)
   - `hcloud firewall create --name gse-firewall`
   - Add rules + apply to server

7. **Verify SSH access**
   - `ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@<IP> "echo ok"`
   - Retry up to 3 times with 10s wait

8. **Update state**
   - Record server name, id, IP, type in deploy.json
   - Add SERVER_IP and SSH_USER=root to `.env`
   - Set `phases_completed.provision`

### Phase 3 — Secure (skip if deploy.json has phases_completed.secure)

1. **Create deploy user**
   - `ssh root@<IP> "adduser --disabled-password deploy && usermod -aG sudo deploy"`
   - Copy SSH key to deploy user

2. **Verify deploy user SSH**
   - `ssh -o ConnectTimeout=10 deploy@<IP> "sudo echo ok"`
   - CRITICAL: do not proceed if this fails

3. **Harden SSH**
   - Disable root login: `PermitRootLogin no`
   - Disable password auth: `PasswordAuthentication no`
   - Restart sshd

4. **Install UFW**
   - `apt install -y ufw`
   - Allow 22, 80, 443, 8000
   - `ufw --force enable`

5. **Install fail2ban**
   - `apt install -y fail2ban`
   - Configure SSH jail (maxretry: 5, bantime: 3600)
   - Start and enable

6. **Automatic security updates**
   - `apt install -y unattended-upgrades`
   - Enable automatic security patches

7. **Update state**
   - Update SSH_USER=deploy in `.env`
   - Set `phases_completed.secure`

### Phase 4 — Install Coolify (skip if COOLIFY_URL in .env or deploy.json has phases_completed.coolify)

1. **Install Coolify**
   - `ssh deploy@<IP> "curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash"`

2. **Wait for readiness**
   - Poll `http://<IP>:8000` every 15s, timeout 5 minutes
   - Show progress: "Waiting for Coolify to start..."

3. **Guide browser setup**
   - "Open http://<IP>:8000 in your browser.
     Create your admin account.
     Then go to Keys & Tokens → API Tokens → create a token.
     Paste it here."
   - Save `COOLIFY_API_TOKEN` and `COOLIFY_URL` to `.env`

4. **Verify Docker and Traefik**
   - `ssh deploy@<IP> "sudo docker ps"` — check Coolify, Traefik, PostgreSQL containers

5. **Update state**
   - Record Coolify URL and version in deploy.json
   - Set `phases_completed.coolify`

### Phase 5 — Configure DNS (skip if deploy.json has phases_completed.dns)

1. **Guide DNS configuration**
   - "Add these DNS records at your domain registrar:
     - Type A, Name: @, Value: <IP>
     - Type A, Name: *, Value: <IP> (wildcard)
     TTL: 300 (5 min)"
   - Provide registrar-specific links if domain registrar is known

2. **Verify DNS propagation**
   - `dig +short <domain>` — check it resolves to server IP
   - If not resolved: "DNS not propagated yet. This can take 5-30 minutes. Run /gse:deploy again when ready."
   - Exit gracefully (phase not marked complete)

3. **Configure Coolify domain**
   - Set Coolify dashboard domain via API: `https://coolify.<domain>`

4. **Configure SSL**
   - Let's Encrypt via Coolify (automatic with Traefik)
   - Verify: `curl -I https://<domain>` — check for valid certificate

5. **Close port 8000**
   - Remove from UFW and Hetzner firewall

6. **Update state**
   - Record domain in deploy.json
   - Set `phases_completed.dns`

### Phase 6 — Deploy Application

1. **Determine subdomain**
   - If `DEPLOY_USER` is set: subdomain = `{DEPLOY_USER}.{DEPLOY_DOMAIN}`
   - Else: subdomain = `{project-name}.{DEPLOY_DOMAIN}`
   - `project-name` is derived from the current directory name (sanitized)

2. **Preflight checks**
   - Verify project has deployable content (Dockerfile, or Python project, or static files)
   - Verify git repo exists and has a remote (Coolify pulls from GitHub)
   - If uncommitted changes: warn and offer to commit first

3. **Generate Dockerfile** (if not present)
   - Detect project type:
     - `streamlit` in dependencies → Streamlit template
     - `pyproject.toml` or `requirements.txt` → Python generic template
     - `package.json` → Node.js (basic template)
     - Otherwise → ask user
   - Generate appropriate Dockerfile from template
   - Show to user for approval (Inform tier)

4. **Create Coolify application**
   - Via Coolify API:
     - Source: GitHub repo (detected from git remote)
     - Branch: current branch (or main)
     - Dockerfile path: `./Dockerfile`
     - Domain: subdomain determined in step 1
     - Health check: auto-detected by app type

5. **Trigger build**
   - Via Coolify API: trigger deployment
   - Monitor build status (poll every 10s)
   - Show progress

6. **Health check**
   - Poll `https://{subdomain}` every 10s
   - Timeout: `deploy.health_check_timeout` (default: 120s)
   - If healthy: report success with URL
   - If timeout: report failure, suggest checking Coolify dashboard

7. **Report**
   - Display:
     "Your project is live at: https://{subdomain}"
   - If solo mode: "Server: {IP} ({server-type}), monthly cost: ~8.49 EUR"
   - If training mode: "Deployed on shared server provided by instructor"

8. **Update state**
   - Record app URL, deployed timestamp, status in deploy.json
```

### 3.2 `src/templates/deploy.json` — State Schema

```json
{
  "version": "1.0",
  "plugin": "gse-one",
  "created_at": "",

  "phases_completed": {
    "setup": "",
    "provision": "",
    "secure": "",
    "coolify": "",
    "dns": ""
  },

  "server": {
    "name": "",
    "id": null,
    "ipv4": "",
    "type": "cax21",
    "datacenter": "fsn1"
  },

  "coolify": {
    "url": "",
    "app_uuid": ""
  },

  "domain": {
    "base": "",
    "registrar": ""
  },

  "app": {
    "name": "",
    "url": "",
    "github_repo": "",
    "type": "",
    "deployed_at": "",
    "status": ""
  }
}
```

### 3.3 `src/templates/Dockerfile` — Generic Python Template

```dockerfile
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv pip install -r requirements.txt 2>/dev/null || true

COPY . .

# Default: Streamlit app (override CMD in project Dockerfile if different)
EXPOSE 8501
HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health || exit 1
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 3.4 `src/templates/deploy-env.example` — Solo User Template

```bash
# GSE-One Deploy credentials (solo mode)
# Copy this file to .env and fill in your values
# NEVER commit .env to git

HETZNER_API_TOKEN=your-token-here
DEPLOY_DOMAIN=your-domain.com

# Filled automatically after Coolify installation:
# COOLIFY_URL=https://coolify.your-domain.com
# COOLIFY_API_TOKEN=your-coolify-token
```

### 3.5 `src/templates/deploy-env-training.example` — Training Template

```bash
# GSE-One Deploy — Training Configuration
# Provided by your instructor. Copy to .env and set your DEPLOY_USER.
# NEVER commit .env to git

COOLIFY_URL=https://coolify.training.example.com
COOLIFY_API_TOKEN=instructor-provided-token
DEPLOY_DOMAIN=training.example.com

# === SET YOUR LEARNER ID BELOW ===
DEPLOY_USER=learnerXX
```

---

## 4. Files to Modify

### 4.1 `gse_generate.py` — Add "deploy" to ACTIVITY_NAMES

Add `"deploy"` to the `ACTIVITY_NAMES` list. Skills count goes from 22 to 23.

### 4.2 `src/templates/config.yaml` — Add Section 12: Deploy

```yaml
# --- Section 12: Deploy ---
deploy:
  provider: hetzner                    # only supported provider
  server_type: cax21                   # cax21 | cax31 | cax41
  datacenter: fsn1                     # fsn1 | nbg1 | hel1
  app_type: auto                       # auto | python | streamlit | static
  health_check_timeout: 120            # seconds
```

---

## 5. Reuse from stx-deploy

| Phase | stx-deploy Source | Lines | Adaptations |
|-------|-------------------|:-----:|-------------|
| Setup | `setup.md` | 195 | `.stx-deploy.env` → `.env`; add Windows hcloud; remove StreamTeX-specific options |
| Provision | `provision.md` | 150 | State in `.gse/deploy.json`; server name `gse-<project>`; save SERVER_IP to `.env` |
| Secure | `secure.md` | 176 | None — directly reusable |
| Coolify | `install-coolify.md` | 113 | None — directly reusable |
| DNS | `configure-domain.md` | 221 | Simplify: remove Cloudflare CDN, keep basic DNS + SSL |
| Deploy | `deploy.md` | 270 | Remove serve modes; add DEPLOY_USER subdomain logic; generalize Dockerfile detection |

**Total reuse: ~75% of stx-deploy content, adapted for generality and training mode.**

---

## 6. Implementation Sprint

| # | Task | Deliverable | Depends on |
|---|------|------------|------------|
| 1 | Write `src/activities/deploy.md` | Skill file (~400 lines, Step 0 + 6 phases) | — |
| 2 | Write `src/templates/deploy.json` | State schema | — |
| 3 | Write `src/templates/Dockerfile` | Generic Python template | — |
| 4 | Write `src/templates/deploy-env.example` | Solo credential template | — |
| 5 | Write `src/templates/deploy-env-training.example` | Training credential template | — |
| 6 | Add deploy to `gse_generate.py` ACTIVITY_NAMES | 23rd skill | — |
| 7 | Add deploy section to `src/templates/config.yaml` | Section 12 | — |
| 8 | Regenerate plugin | All 23 skills + 18 templates | 1-7 |
| 9 | Update spec (see §7 below) | Aligned spec | 8 |
| 10 | Update design (see §7 below) | Aligned design | 8 |
| 11 | Update CHANGELOG.md | Version entry | 9-10 |
| 12 | Bump VERSION + regenerate + commit + push | Release | 11 |

---

## 7. Methodology Alignment — Spec and Design Modifications

### 7.1 Specification (`gse-one-spec.md`)

| Location | Current | Modification |
|----------|---------|-------------|
| **Activities table** | 22 commands across 8 categories | Add `/gse:deploy` as 23rd command in a new "Deployment" category. Description: "Deploy the current project to a Hetzner server via Coolify. Adapts to the user's situation: from zero infrastructure (solo) to a pre-configured shared server (training). Handles provisioning, security, DNS, and application deployment." |
| **Command count** (all occurrences) | "22 commands" | Update to "23 commands" |
| **Config section** | 11 sections | Add section 12: `deploy:` with 5 keys. Update count to "12 sections". |
| **Artefact storage** | `.gse/` directory listing | Add `deploy.json`: "Infrastructure state — server, Coolify, deployment status" |
| **Lifecycle phases** | LC00 → LC01 → LC02 → LC03 | Add note: `/gse:deploy` is invoked after `/gse:deliver` to deploy the tagged release. Does not create a new phase — extends delivery. |
| **Glossary** | Current terms | Add: "Coolify — Self-hosted PaaS used for deployment on Hetzner servers." |
| **Appendix A** | 22-command quick reference | Add `/gse:deploy` row |
| **Mono-plugin table** | "Skills (22)" | Update to "Skills (23)" |
| **Plugin description** | "22 commands" | Update to "23 commands" |

### 7.2 Design (`gse-one-implementation-design.md`)

| Location | Current | Modification |
|----------|---------|-------------|
| **Spec-driven enrichments note** | v0.10+ enrichments list | Add: "Hetzner deployment skill (`/gse:deploy`) — single-command deployment with flexible starting points (solo/training). See the specification." |
| **File inventory** | "22 skills, 15 templates, 52 files" | Update to "23 skills, 19 templates (added deploy.json, Dockerfile, deploy-env.example, deploy-env-training.example), 56 total files" |
| **Generator steps** | ACTIVITY_NAMES: 22 | Update to 23 |

### 7.3 Production (`gse-one/`)

| File | Action |
|------|--------|
| `src/activities/deploy.md` | **Create** — ~400 lines, Step 0 + 6 phases |
| `src/templates/deploy.json` | **Create** — state schema |
| `src/templates/Dockerfile` | **Create** — generic Python template |
| `src/templates/deploy-env.example` | **Create** — solo template |
| `src/templates/deploy-env-training.example` | **Create** — training template |
| `gse_generate.py` | **Modify** — add `"deploy"` to ACTIVITY_NAMES |
| `src/templates/config.yaml` | **Modify** — add section 12: deploy |
| `gse-one/README.md` | **Modify** — update command count to 23 |

### 7.4 Root files

| File | Action |
|------|--------|
| `CHANGELOG.md` | **Modify** — add version entry |
| `VERSION` | **Modify** — bump |
| `README.md` | **Modify** — update command count if mentioned |

---

## 8. Verification Checklist

After implementation, verify:

- [ ] `python3 gse_generate.py --clean --verify` passes (23 skills, 19 templates)
- [ ] `plugin/skills/deploy/SKILL.md` exists and contains Step 0 + 6 phases
- [ ] `plugin/templates/deploy.json` exists
- [ ] `plugin/templates/Dockerfile` exists
- [ ] `plugin/templates/deploy-env.example` exists
- [ ] `plugin/templates/deploy-env-training.example` exists
- [ ] Spec mentions 23 commands everywhere (grep for "22 commands" returns 0)
- [ ] Spec config.yaml has deploy section (12 sections)
- [ ] Spec artefact storage lists deploy.json
- [ ] Design file inventory updated (23 skills, 19 templates)
- [ ] CHANGELOG.md has entry
- [ ] install.py shows correct version
- [ ] **Training mode test**: with COOLIFY_URL + COOLIFY_API_TOKEN + DEPLOY_DOMAIN + DEPLOY_USER in .env, the skill skips to Phase 6
- [ ] **Solo mode test**: with empty .env, the skill starts at Phase 1
- [ ] **Partial mode test**: with SERVER_IP only, the skill starts at Phase 3/4
