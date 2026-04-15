---
name: "gse-deploy"
description: "Deploy the current project to a Hetzner server via Coolify. Adapts to the user's situation: from zero infrastructure (solo) to a pre-configured shared server (training). Triggered by /gse:deploy."
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
4. `.gse/profile.yaml` — user profile (apply P9 Adaptive Communication to all output)

## Workflow

### Step 0 — Situation Detection

Read `.env` and `.gse/deploy.json` (if they exist). Determine starting point based on which variables are present:

**`.env` variables (all optional):**

| Variable | Purpose | Level |
|----------|---------|-------|
| `HETZNER_API_TOKEN` | Hetzner Cloud API access | Infrastructure |
| `SERVER_IP` | Pre-existing server IP address | Server |
| `SSH_USER` | SSH username (default: deploy) | Server |
| `SSH_KEY` | Path to SSH private key | Server |
| `COOLIFY_URL` | Coolify dashboard URL | Coolify |
| `COOLIFY_API_TOKEN` | Coolify API access | Coolify |
| `DEPLOY_DOMAIN` | Base domain for subdomains | Domain |
| `DEPLOY_USER` | User identity for subdomain prefix (training mode) | Identity |

**Detection logic:**

| Variables present | Starting phase | Mode |
|-------------------|:-------------:|------|
| Nothing | Phase 1 | Full (solo) |
| `HETZNER_API_TOKEN` only | Phase 2 | Full (token provided) |
| `SERVER_IP` + `SSH_USER` (no Coolify) | Phase 3 or 4 | Partial (server provided) |
| `COOLIFY_URL` + `COOLIFY_API_TOKEN` + `DEPLOY_DOMAIN` | Phase 6 | App-only (training or pre-configured) |
| All variables | Phase 6 | App-only |

Also check `.gse/deploy.json → phases_completed` for already-completed phases (idempotence).

**Display the detected situation to the user:**
- Full mode: *"No deployment configuration found. I'll guide you through the complete setup."*
- Partial: *"I found a server at {IP}. Starting from there."*
- App-only: *"Deployment infrastructure is ready ({COOLIFY_URL}). I'll deploy your application."*
- Training: *"Training mode detected. I'll deploy your project as {DEPLOY_USER}.{DEPLOY_DOMAIN}."*

---

### Phase 1 — Setup (skip if `HETZNER_API_TOKEN` in `.env`)

**Purpose:** Install CLI tools, obtain credentials, save configuration.

1. **Check hcloud CLI**
   - Run `hcloud version`
   - If not found, install:
     - macOS: `brew install hcloud`
     - Linux: download from https://github.com/hetznercloud/cli/releases
     - Windows: `winget install hetznercloud.cli` or direct download
   - Verify: `hcloud version`

2. **Obtain Hetzner API token**
   - Guide the user step by step:
     *"Go to https://console.hetzner.cloud → select or create a project → Security → API Tokens → Generate API Token (Read & Write). Copy the token — it is shown only once."*
   - Ask the user to paste the token
   - **Never display the token back in chat**

3. **Domain name**
   - Ask: *"What domain will you use for deployment? (e.g., my-project.com)"*

4. **Save credentials**
   - Write or update `.env` at project root:
     ```
     HETZNER_API_TOKEN=<token>
     DEPLOY_DOMAIN=<domain>
     ```
   - Check `.gitignore` contains `.env` — if not, add it and warn the user
   - If no `.gitignore` exists: Gate decision to create one

5. **Verify hcloud access**
   - Run `hcloud server list` to confirm the token works
   - If it fails: ask user to verify the token

6. **Update state**
   - Create `.gse/deploy.json` with `phases_completed.setup` timestamp

---

### Phase 2 — Provision (skip if `SERVER_IP` in `.env` or `deploy.json` has `phases_completed.provision`)

**Purpose:** Create a Hetzner server with firewall.

1. **Read configuration**
   - Server type: `config.yaml → deploy.server_type` (default: `cax21`)
   - Datacenter: `config.yaml → deploy.datacenter` (default: `fsn1`)
   - Server name: `gse-<project-name>` (sanitized, lowercase, hyphens only)

2. **Check for existing server**
   - `hcloud server list -o columns=name,ipv4`
   - If a server with this name exists: skip provision, record IP

3. **Gate decision: server creation**
   - Display cost and configuration:
     *"Creating a Hetzner server:*
     *- Type: CAX21 (4 vCPU ARM, 8 GB RAM, 80 GB SSD)*
     *- Location: Falkenstein (fsn1)*
     *- Monthly cost: ~8.49 EUR*
     *Proceed?"*
   - Wait for explicit user confirmation

4. **Generate SSH key** (if `~/.ssh/gse-deploy` does not exist)
   - `ssh-keygen -t ed25519 -f ~/.ssh/gse-deploy -N ""`
   - Upload: `hcloud ssh-key create --name gse-deploy --public-key-from-file ~/.ssh/gse-deploy.pub`

5. **Create server**
   - `hcloud server create --name <name> --type <type> --location <datacenter> --image ubuntu-24.04 --ssh-key gse-deploy`
   - Record IP address from output

6. **Create firewall**
   - `hcloud firewall create --name gse-fw-<name>`
   - Add rules: allow TCP 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (Coolify setup, temporary)
   - Apply to server: `hcloud firewall apply-to-resource gse-fw-<name> --type server --server <name>`

7. **Verify SSH access**
   - `ssh -i ~/.ssh/gse-deploy -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@<IP> "echo ok"`
   - Retry up to 3 times with 10s wait between attempts

8. **Update state**
   - Record server name, id, IP, type in `deploy.json`
   - Add `SERVER_IP=<IP>` and `SSH_USER=root` and `SSH_KEY=~/.ssh/gse-deploy` to `.env`
   - Set `phases_completed.provision`

---

### Phase 3 — Secure (skip if `deploy.json` has `phases_completed.secure`)

**Purpose:** Harden the server — non-root user, SSH hardening, firewall, intrusion detection.

1. **Create deploy user**
   - ```
     ssh root@<IP> "adduser --disabled-password --gecos '' deploy && \
       usermod -aG sudo deploy && \
       echo 'deploy ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/deploy"
     ```
   - Copy SSH key:
     ```
     ssh root@<IP> "mkdir -p /home/deploy/.ssh && \
       cp /root/.ssh/authorized_keys /home/deploy/.ssh/ && \
       chown -R deploy:deploy /home/deploy/.ssh && \
       chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys"
     ```

2. **Verify deploy user SSH**
   - `ssh -i ~/.ssh/gse-deploy -o ConnectTimeout=10 deploy@<IP> "sudo echo ok"`
   - **CRITICAL: do not proceed if this fails** — root access will be disabled next

3. **Harden SSH**
   - Edit `/etc/ssh/sshd_config`:
     - `PermitRootLogin no`
     - `PasswordAuthentication no`
     - `PubkeyAuthentication yes`
   - `ssh deploy@<IP> "sudo systemctl restart sshd"`

4. **Install UFW firewall**
   - ```
     ssh deploy@<IP> "sudo apt-get update -qq && sudo apt-get install -y -qq ufw && \
       sudo ufw default deny incoming && sudo ufw default allow outgoing && \
       sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && \
       sudo ufw allow 443/tcp && sudo ufw allow 8000/tcp && \
       sudo ufw --force enable"
     ```

5. **Install fail2ban**
   - ```
     ssh deploy@<IP> "sudo apt-get install -y -qq fail2ban && \
       sudo systemctl enable fail2ban && sudo systemctl start fail2ban"
     ```

6. **Automatic security updates**
   - ```
     ssh deploy@<IP> "sudo apt-get install -y -qq unattended-upgrades && \
       sudo dpkg-reconfigure -plow unattended-upgrades"
     ```

7. **Update state**
   - Update `SSH_USER=deploy` in `.env`
   - Set `phases_completed.secure`

---

### Phase 4 — Install Coolify (skip if `COOLIFY_URL` in `.env` or `deploy.json` has `phases_completed.coolify`)

**Purpose:** Install Coolify v4 (self-hosted PaaS with Traefik reverse proxy).

1. **Install Coolify**
   - `ssh deploy@<IP> "curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash"`

2. **Wait for readiness**
   - Poll `http://<IP>:8000` every 15 seconds, timeout 5 minutes
   - Show progress: *"Waiting for Coolify to start..."*

3. **Guide browser setup**
   - Tell the user:
     *"Coolify is ready. Open http://<IP>:8000 in your browser.*
     *1. Create your admin account*
     *2. Go to Keys & Tokens → API Tokens → create a token with full access*
     *3. Copy and paste the token here"*
   - Save `COOLIFY_API_TOKEN` to `.env`
   - Save `COOLIFY_URL=http://<IP>:8000` to `.env`

4. **Verify containers**
   - `ssh deploy@<IP> "sudo docker ps --format 'table {{.Names}}\t{{.Status}}'"` 
   - Check: coolify, traefik, postgres containers running

5. **Update state**
   - Record Coolify URL in `deploy.json`
   - Set `phases_completed.coolify`

---

### Phase 5 — Configure DNS (skip if `deploy.json` has `phases_completed.dns`)

**Purpose:** Point the domain to the server and enable SSL.

1. **Guide DNS configuration**
   - Tell the user:
     *"Add these DNS records at your domain registrar:*
     *- Type: A, Name: @, Value: <IP>*
     *- Type: A, Name: *, Value: <IP> (wildcard for subdomains)*
     *TTL: 300 seconds (5 minutes)"*
   - If domain registrar is known, provide direct link to DNS settings

2. **Verify DNS propagation**
   - `dig +short <domain>` — check it resolves to server IP
   - If not resolved:
     *"DNS is not propagated yet. This can take 5-30 minutes. Run `/gse:deploy` again when ready."*
   - Exit gracefully — **do not mark phase complete**

3. **Configure Coolify domain**
   - Via Coolify API: set dashboard domain to `coolify.<domain>`
   - Update `COOLIFY_URL=https://coolify.<domain>` in `.env`

4. **Verify SSL**
   - Coolify + Traefik handle Let's Encrypt automatically
   - `curl -sI https://<domain>` — check for valid certificate
   - If SSL not ready: wait 30s and retry (up to 3 times)

5. **Close temporary port 8000**
   - `ssh deploy@<IP> "sudo ufw delete allow 8000/tcp"`
   - `hcloud firewall delete-rule gse-fw-<name> --direction in --protocol tcp --port 8000`

6. **Update state**
   - Record domain in `deploy.json`
   - Set `phases_completed.dns`

---

### Phase 6 — Deploy Application

**Purpose:** Deploy the current project as a Coolify application.

1. **Determine subdomain**
   - If `DEPLOY_USER` is set in `.env`: subdomain = `{DEPLOY_USER}.{DEPLOY_DOMAIN}`
   - Else: subdomain = `{project-name}.{DEPLOY_DOMAIN}`
   - `project-name` is the current directory name (sanitized: lowercase, hyphens, no special chars)

2. **Preflight checks**
   - Project has deployable content: Dockerfile, or `pyproject.toml`, or `requirements.txt`, or `package.json`, or static HTML
   - Git repo exists with at least one commit
   - Git remote exists (Coolify pulls from GitHub): check `git remote get-url origin`
   - If uncommitted changes: warn and offer to commit first (Inform tier)
   - If no remote: warn — Coolify needs a GitHub repo to pull from

3. **Generate Dockerfile** (if not present in project root)
   - Detect project type:
     - `streamlit` in dependencies (pyproject.toml or requirements.txt) → Streamlit template
     - `pyproject.toml` or `requirements.txt` without Streamlit → Python generic template
     - `package.json` → Node.js basic template
     - Static HTML files only → Nginx static template
     - Otherwise → ask the user what type of application this is
   - Generate the Dockerfile from the appropriate template
   - Show to user for approval (Inform tier)
   - Commit the Dockerfile if user approves

4. **Create Coolify application**
   - Via Coolify API (`POST /api/v1/applications`):
     - Source: GitHub repository (from `git remote get-url origin`)
     - Branch: current branch or `main`
     - Dockerfile path: `./Dockerfile`
     - Domain: `https://{subdomain}`
     - Port: auto-detected (8501 for Streamlit, 3000 for Node.js, 80 for static)
   - Record the application UUID

5. **Trigger build**
   - Via Coolify API: trigger deployment
   - Poll deployment status every 10 seconds
   - Show progress: *"Building your application..."*

6. **Health check**
   - Poll `https://{subdomain}` every 10 seconds
   - Timeout: `config.yaml → deploy.health_check_timeout` (default: 120 seconds)
   - Health check URL by app type:
     - Streamlit: `/_stcore/health`
     - HTTP apps: `/`
     - Custom: from `config.yaml → deploy.health_check_url` if set
   - If healthy: proceed to report
   - If timeout: report failure with last build logs, suggest checking Coolify dashboard at `{COOLIFY_URL}`

7. **Report**
   - If successful:
     *"Your project is live at: https://{subdomain}"*
   - If solo mode (server provisioned by this user):
     *"Server: {IP} ({server-type}), monthly cost: ~8.49 EUR"*
   - If training mode:
     *"Deployed on shared training server."*

8. **Update state**
   - Record in `deploy.json`:
     - `app.name`, `app.url`, `app.github_repo`, `app.type`
     - `app.deployed_at` (timestamp)
     - `app.status` ("healthy" or "unhealthy")
     - `coolify.app_uuid`

---

### --status Option

When invoked with `--status`:

1. Read `.gse/deploy.json`
2. If no deploy.json: *"No deployment found. Run `/gse:deploy` to deploy."*
3. Display:
   - Phases completed (with timestamps)
   - Server info (IP, type) if applicable
   - Application URL and health status
   - Last deployment timestamp
4. If app URL exists: run a live health check and report current status

### --destroy Option

When invoked with `--destroy`:

1. Gate decision (first confirmation):
   *"This will permanently destroy the server and all deployed applications. Are you sure?"*
2. Gate decision (second confirmation):
   *"Type the server name to confirm: {server-name}"*
3. If confirmed:
   - Delete all Coolify applications via API
   - `hcloud server delete <name>`
   - `hcloud firewall delete gse-fw-<name>`
   - Remove infrastructure entries from `.gse/deploy.json`
   - Remove server-related variables from `.env`
   - Report: *"Server destroyed. Deployment configuration cleared."*

### --redeploy Option

When invoked with `--redeploy`:

1. Skip to Phase 6
2. Trigger a new build via Coolify API
3. Monitor and health check as usual
