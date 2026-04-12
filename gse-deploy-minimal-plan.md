# GSE-Deploy Minimal — Implementation Plan

**Date:** 2026-04-12
**Status:** Draft
**Approach:** Single skill `/gse:deploy` integrated into GSE-One plugin (no separate repo)
**Target:** Hetzner Cloud + Coolify v4, production only, single project
**Source:** Reuse of StreamTeX stx-deploy skills (streamtex-dev/.claude/commands/stx-deploy/)

---

## 1. Concept

Add a single `/gse:deploy` skill to GSE-One that handles the entire deployment flow in one guided pass. The agent walks the user through setup, provisioning, server hardening, Coolify installation, DNS configuration, and application deployment. Each phase is idempotent — if already completed, it is skipped silently.

**Hypothesis:** The user has a Hetzner account and a domain name.

**What it does:**
- Installs the `hcloud` CLI
- Guides the user to obtain a `HETZNER_API_TOKEN`
- Saves credentials in `.env` (gitignored)
- Provisions a Hetzner server
- Hardens the server (SSH, firewall, fail2ban)
- Installs Coolify v4
- Configures DNS and SSL
- Deploys the current project

**What it does NOT do (vs the full gse-deploy plan):**
- No staging environment (production only)
- No batch deployment (one project at a time)
- No scaling or load balancer
- No automated rollback (manual via Coolify dashboard)
- No promotion workflow
- No separate plugin

---

## 2. Files to Create

### 2.1 `src/activities/deploy.md` — The Skill (~300 lines)

```markdown
---
description: "Deploy the current project to a Hetzner server via Coolify.
Handles setup, provisioning, security, and deployment in a single guided flow.
Triggered by /gse:deploy."
---

# GSE-One Deploy — Hetzner Deployment

Arguments: $ARGUMENTS

## Options

| Flag | Description |
|------|-------------|
| (no args) | Deploy current project (resume from last completed phase) |
| --status | Show deployment status (server, app URL, health) |
| --destroy | Tear down server and all data (Gate, confirm twice) |
| --redeploy | Force rebuild and redeploy (skip setup phases) |
| --help | Show this command's usage summary |

## Prerequisites

Read before execution:
1. `.gse/config.yaml` — deploy section (provider, server type, datacenter)
2. `.gse/deploy.json` — infrastructure state (if exists)
3. `.env` — credentials (if exists)

## Workflow

### Phase 1 — Setup (skip if .env contains HETZNER_API_TOKEN)

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
   - Write `.env` at project root:
     ```
     HETZNER_API_TOKEN=<token>
     DEPLOY_DOMAIN=<domain>
     ```
   - Verify `.env` is in `.gitignore` — if not, add it and warn
   - Gate decision if `.gitignore` doesn't exist: create it

5. **Verify hcloud access**
   - Run `hcloud server list` to confirm token works
   - If it fails: ask user to check token

6. **Update state**
   - Create `.gse/deploy.json` with `phases_completed.setup` timestamp

### Phase 2 — Provision (skip if deploy.json has phases_completed.provision)

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
   - Allow ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (Coolify setup)
   - `hcloud firewall create --name gse-firewall`
   - Add rules + apply to server

7. **Verify SSH access**
   - `ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@<IP> "echo ok"`
   - Retry up to 3 times with 10s wait

8. **Update state**
   - Record server name, id, IP, type in deploy.json
   - Set `phases_completed.provision`

### Phase 3 — Secure (skip if deploy.json has phases_completed.secure)

1. **Create deploy user**
   - `ssh root@<IP> "adduser --disabled-password deploy && usermod -aG sudo deploy"`
   - Copy SSH key: `ssh root@<IP> "mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/ && chown -R deploy:deploy /home/deploy/.ssh"`

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
   - Set `phases_completed.secure`

### Phase 4 — Install Coolify (skip if deploy.json has phases_completed.coolify)

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
   - Save `COOLIFY_API_TOKEN` to `.env`
   - Save `COOLIFY_URL=http://<IP>:8000` to `.env`

4. **Verify Docker and Traefik**
   - `ssh deploy@<IP> "sudo docker ps"` — check Coolify, Traefik, PostgreSQL containers

5. **Update state**
   - Record Coolify URL and version
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
   - Set Coolify dashboard domain via API
   - `https://coolify.<domain>`

4. **Configure SSL**
   - Let's Encrypt via Coolify (automatic with Traefik)
   - Verify: `curl -I https://<domain>` — check for valid certificate

5. **Close port 8000**
   - Remove from UFW: `ufw delete allow 8000`
   - Remove from Hetzner firewall

6. **Update state**
   - Record domain, registrar
   - Set `phases_completed.dns`

### Phase 6 — Deploy Application

1. **Preflight checks**
   - Verify project has deployable content (Dockerfile, or Python project, or static files)
   - Verify git repo is clean (warn if uncommitted changes)
   - Verify GitHub remote exists (Coolify pulls from GitHub)

2. **Generate Dockerfile** (if not present)
   - Detect project type:
     - `requirements.txt` or `pyproject.toml` → Python
     - `streamlit` in dependencies → Streamlit template
     - `package.json` → Node.js (basic template)
     - Otherwise → ask user
   - Generate appropriate Dockerfile from template
   - Show to user for approval (Inform tier)

3. **Create Coolify application**
   - Via Coolify API:
     - Source: GitHub repo
     - Branch: current branch (or main)
     - Dockerfile path: `./Dockerfile`
     - Domain: `<project-name>.<domain>`
     - Health check: auto-detected (Streamlit: `/_stcore/health`, HTTP: `/`, custom)

4. **Trigger build**
   - Via Coolify API: trigger deployment
   - Monitor build logs (poll every 10s)
   - Show progress: "Building... (step N/M)"

5. **Health check**
   - Poll `https://<project-name>.<domain>` every 10s
   - Timeout: `deploy.health_check_timeout` (default: 120s)
   - If healthy: report success with URL
   - If timeout: report failure, show last build logs, suggest checking Coolify dashboard

6. **Report**
   - Display:
     "Your project is live at: https://<project-name>.<domain>
     Server: <IP> (<server-type>)
     Monthly cost: ~8.49 EUR"

7. **Update state**
   - Record app URL, deployed timestamp, status
   - Set or update application entry in deploy.json
```

### 2.2 `src/templates/deploy.json` — State Schema

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

### 2.3 `src/templates/Dockerfile` — Generic Python Template

```dockerfile
FROM python:3.13-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv pip install -r requirements.txt 2>/dev/null || true

# Copy application
COPY . .

# Default: assume Streamlit app (override CMD in project Dockerfile if different)
EXPOSE 8501
HEALTHCHECK CMD curl -f http://localhost:8501/_stcore/health || exit 1
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 2.4 `src/templates/deploy-env.example` — Credential Example

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

---

## 3. Files to Modify

### 3.1 `gse_generate.py` — Add "deploy" to ACTIVITY_NAMES

Add `"deploy"` to the `ACTIVITY_NAMES` list. Skills count goes from 22 to 23.

### 3.2 `src/templates/config.yaml` — Add Section 12: Deploy

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

## 4. Reuse from stx-deploy

| Phase | stx-deploy Source | Lines | Adaptations |
|-------|-------------------|:-----:|-------------|
| Setup | `setup.md` | 195 | `.stx-deploy.env` → `.env`; remove StreamTeX-specific options; add Windows hcloud install |
| Provision | `provision.md` | 150 | State in `.gse/deploy.json` instead of `.stx-deploy.json`; server name `gse-<project>` |
| Secure | `secure.md` | 176 | None — directly reusable |
| Coolify | `install-coolify.md` | 113 | None — directly reusable |
| DNS | `configure-domain.md` | 221 | Simplify: remove Cloudflare CDN setup, keep basic DNS + SSL |
| Deploy | `deploy.md` | 270 | Remove StreamTeX serve modes; generalize Dockerfile detection; keep Coolify API + health check |

**Total reuse: ~80% of stx-deploy content, adapted for generality.**

---

## 5. Implementation Sprint

| # | Task | Deliverable | Depends on |
|---|------|------------|------------|
| 1 | Write `src/activities/deploy.md` | The skill file (~300 lines) | — |
| 2 | Write `src/templates/deploy.json` | State schema | — |
| 3 | Write `src/templates/Dockerfile` | Generic Python template | — |
| 4 | Write `src/templates/deploy-env.example` | Credential example | — |
| 5 | Add deploy to `gse_generate.py` ACTIVITY_NAMES | 23rd skill | — |
| 6 | Add deploy section to `src/templates/config.yaml` | Section 12 | — |
| 7 | Regenerate plugin | All 23 skills + 16 templates | 1-6 |
| 8 | Update spec (see §6 below) | Aligned spec | 7 |
| 9 | Update design (see §6 below) | Aligned design | 7 |
| 10 | Update CHANGELOG.md | Version entry | 8-9 |
| 11 | Bump VERSION + regenerate + commit | Release | 10 |

---

## 6. Methodology Alignment — Spec and Design Modifications

### 6.1 Specification (`gse-one-spec.md`)

| Location | Current | Modification |
|----------|---------|-------------|
| **Activities table (§3)** | 22 commands across 8 categories | Add `/gse:deploy` as 23rd command. Either add to "Delivery" category alongside `/gse:deliver`, or create a new "Deployment" category. Description: "Deploy the current project to a Hetzner server. Handles provisioning, security, Coolify, DNS, and application deployment in a single guided flow." |
| **Command count** (§1.2, §3 header, TOC) | "22 commands" | Update to "23 commands" everywhere |
| **Config §13.1** | 11 sections (~50 keys) | Add section 12: `deploy:` with 5 keys (provider, server_type, datacenter, app_type, health_check_timeout). Update count to "12 sections". |
| **Artefact storage §12** | `.gse/` directory listing | Add `deploy.json` to the list of files in `.gse/`: "Infrastructure state — server, Coolify, deployment status" |
| **Lifecycle phases §14** | LC00 → LC01 → LC02 → LC03 | Add a note that `/gse:deploy` can be invoked after `/gse:deliver` (end of LC02) to deploy the tagged release. It does not create a new lifecycle phase — it extends the delivery step. |
| **P13 agent behaviors table** | 6 agent behaviors listed | No change needed — deploy is an explicit user-invoked activity, not an automatic behavior |
| **Glossary §15** | Current terms | Add: "Coolify — Self-hosted PaaS (Platform as a Service) used by GSE-One for application deployment on Hetzner servers." |
| **Appendix A** | 22-command quick reference | Add `/gse:deploy` row |
| **Mono-plugin table (§1.1.4)** | "Skills (22)" | Update to "Skills (23)" |
| **Agent Roles (§1.5)** | 9 agents | No change — deploy-operator is not a separate agent in the minimal solution; the orchestrator handles deploy |
| **Plugin description** | "22 commands" in multiple places | Update to "23 commands" |

### 6.2 Design (`gse-one-implementation-design.md`)

| Location | Current | Modification |
|----------|---------|-------------|
| **Spec-driven enrichments note (§4)** | Lists 5 activities without design + v0.10+ enrichments | Add `/gse:deploy` to the enrichments note: "Hetzner deployment skill (`/gse:deploy`) — single-command server provisioning and application deployment. See the specification for the complete workflow." |
| **File inventory (§12)** | "22 skills, 15 templates, 52 total files" | Update to "23 skills, 18 templates (added deploy.json, Dockerfile, deploy-env.example), 55 total files" |
| **Generator steps (§11)** | ACTIVITY_NAMES: 22 | Update count to 23 |
| **Changelog (§1)** | v0.7 → v0.8 entry | Add to v0.8 entry or create v0.8.1: "Added `/gse:deploy` skill (23rd command). Hetzner Cloud provisioning, Coolify v4, single-project deployment." |

### 6.3 Production (`gse-one/`)

| File | Action |
|------|--------|
| `src/activities/deploy.md` | **Create** — ~300 lines, 6 phases |
| `src/templates/deploy.json` | **Create** — state schema (~30 lines) |
| `src/templates/Dockerfile` | **Create** — generic Python template (~15 lines) |
| `src/templates/deploy-env.example` | **Create** — credential example (~8 lines) |
| `gse_generate.py` | **Modify** — add `"deploy"` to ACTIVITY_NAMES |
| `src/templates/config.yaml` | **Modify** — add section 12: deploy |
| `gse-one/README.md` | **Modify** — update "22 commands" to "23 commands" in description |

### 6.4 Root files

| File | Action |
|------|--------|
| `CHANGELOG.md` | **Modify** — add version entry with deploy skill |
| `VERSION` | **Modify** — bump |
| `README.md` | **Modify** — update "22 commands" to "23 commands" if mentioned |

---

## 7. Verification Checklist

After implementation, verify:

- [ ] `python3 gse_generate.py --clean --verify` passes (23 skills, 18 templates)
- [ ] `plugin/skills/deploy/SKILL.md` exists and contains 6 phases
- [ ] `plugin/templates/deploy.json` exists
- [ ] `plugin/templates/Dockerfile` exists
- [ ] `plugin/templates/deploy-env.example` exists
- [ ] Spec mentions 23 commands everywhere (grep for "22 commands" should return 0)
- [ ] Spec config.yaml has deploy section (12 sections)
- [ ] Spec artefact storage lists deploy.json
- [ ] Design file inventory updated (23 skills, 18 templates)
- [ ] CHANGELOG.md has entry
- [ ] install.py shows correct version
