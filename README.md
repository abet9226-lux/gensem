# GSE-One — Plugin Publication Guide

This repository contains the specification (`gse-one-spec-v0.8.md`), the design document (`gse-one-implementation-design-v0.8.md`) and the complete plugin implementation (`gse-one/`).

This guide describes all the steps to publish the GSE-One plugin and make it installable by Claude Code and Cursor users.

---

## Table of Contents

1. [Mono-plugin Architecture](#1-mono-plugin-architecture)
2. [Develop and Generate](#2-develop-and-generate)
3. [Publish the Plugin](#3-publish-the-plugin)
4. [Command Reference](#4-command-reference)

---

## 1. Mono-plugin Architecture

GSE-One uses a **single deployable directory** (`plugin/`) that works on both platforms:

```
gse-one/
├── src/                              # Single source of truth (62 files)
│   ├── principles/                   # 16 principles (P1-P16)
│   ├── activities/                   # 22 skills SKILL.md
│   ├── agents/                       # 9 agents (8 specialized + orchestrator)
│   └── templates/                    # 15 templates
│
├── plugin/                           # Deployable directory (52 files)
│   ├── .claude-plugin/plugin.json    # Claude Code manifest
│   ├── .cursor-plugin/plugin.json    # Cursor manifest
│   ├── skills/                       # 22 skills (shared)
│   ├── agents/                       # 9 agents (shared)
│   ├── templates/                    # 15 templates (shared)
│   ├── rules/000-gse-methodology.mdc # Cursor only (ignored by Claude)
│   ├── hooks/hooks.claude.json       # Claude Code format
│   ├── hooks/hooks.cursor.json       # Cursor format
│   └── settings.json                 # Claude only (ignored by Cursor)
│
├── marketplace/
│   └── .claude-plugin/marketplace.json
│
└── gse_generate.py                   # Generator: src/ → plugin/
```

**Shared files (46):** skills, agents, templates — single copy, zero divergence.
**Platform-specific files (6):** 2 manifests + 2 hooks + 1 settings + 1 .mdc — generated as equivalent pairs.

---

## 2. Develop and Generate

### Edit the Sources

All changes are made in `src/`. Never modify `plugin/` directly — it is regenerated.

### Regenerate the Plugin

After any modification:

```bash
cd gse-one/
python3 gse_generate.py --clean --verify
```

The generator:
1. Copies skills, specialized agents and templates (shared)
2. Generates the orchestrator (`agents/gse-orchestrator.md`) and the Cursor rule (`rules/000-gse-methodology.mdc`) from the **same source** — verifies that the body is identical
3. Generates the 2 hooks (Claude PascalCase / Cursor camelCase) from the same commands
4. Generates the 2 manifests and `settings.json`

### Create the GitHub Repository

```bash
cd gse-one/
git init
git add .
git commit -m "feat: GSE-One v0.8.0 — initial release"
gh repo create gse-one/gse-one --public --source=. --push
```

> **Important:** Update the `repository` field in `plugin/.claude-plugin/plugin.json`, `plugin/.cursor-plugin/plugin.json` and `marketplace/.claude-plugin/marketplace.json` with the actual repository URL.

---

## 3. Publish the Plugin

Plugin visibility depends entirely on the distribution method chosen and the GitHub repository visibility:

| Method | Visibility | Prerequisites |
|--------|-----------|---------------|
| A — Local test | You only, on your machine | None |
| B — GitHub distribution (private repo) | You + invited collaborators | Private GitHub repo |
| B — GitHub distribution (public repo) | Anyone with the link | Public GitHub repo |
| C — Official marketplace | Everyone (public catalog) | Submission and approval by Anthropic/Cursor |

> **Important:** As long as the GitHub repository remains **private**, no one can view the code or install the plugin without being explicitly invited as a collaborator. Method B with a private repo is suitable for personal use or small teams.

### For Claude Code

#### Method A — Local Test

```bash
claude --plugin-dir ./plugin/
```

Loads the plugin for the current session. Use `/reload-plugins` to reload after modifications.

#### Method B — Personal Marketplace

1. **Verify** `marketplace/.claude-plugin/marketplace.json`:
   ```json
   {
     "plugins": [{
       "id": "gse-one",
       "name": "GSE-One",
       "description": "AI engineering companion for structured SDLC management",
       "source": {
         "type": "github",
         "repo": "gse-one/gse-one",
         "path": "plugin"
       },
       "version": "0.8.0"
     }]
   }
   ```

2. **Push** the repository: `git push origin main`

3. **Users** install:
   ```bash
   /plugin marketplace add gse-one/gse-one
   /plugin install gse-one@gse-one
   ```

   Available scopes:
   | Scope | File | Usage |
   |-------|------|-------|
   | `--scope user` | `~/.claude/settings.json` | Personal (default) |
   | `--scope project` | `.claude/settings.json` | Team (committed to repo) |
   | `--scope local` | `.claude/settings.local.json` | Personal, gitignored |

#### Method C — Official Anthropic Marketplace

1. Submit via [claude.ai/settings/plugins/submit](https://claude.ai/settings/plugins/submit) or [platform.claude.com/plugins/submit](https://platform.claude.com/plugins/submit)
2. Plugin path: `plugin`
3. After approval: `claude plugin install gse-one`

### For Cursor

#### Method A — Local Test

```bash
# Copy the plugin into the project
cp -r gse-one/plugin/ ./gse-one-plugin/
# In Cursor: /add-plugin > Local > select ./gse-one-plugin/
```

#### Method B — Cursor Marketplace

1. Submit via [cursor.com/marketplace/publish](https://cursor.com/marketplace/publish)
2. The plugin already contains `.cursor-plugin/plugin.json` with the correct paths
3. After approval: users install via `/add-plugin`

#### Method C — GitHub Distribution

Users clone and install locally:
```bash
git clone --depth 1 https://github.com/gse-one/gse-one.git /tmp/gse
cp -r /tmp/gse/plugin/ ./gse-one-plugin/
rm -rf /tmp/gse
# In Cursor: /add-plugin > Local > select ./gse-one-plugin/
```

---

## 4. Command Reference

### Developer

```bash
# Regenerate after modification
python3 gse_generate.py --clean --verify

# Publish a new version
# 1. Update version in gse_generate.py (VERSION constant)
# 2. Regenerate
python3 gse_generate.py --clean --verify
# 3. Commit + tag + push
git add .
git commit -m "feat: GSE-One v0.8.1 — description"
git tag v0.8.1
git push origin main --tags
```

### Claude Code User

```bash
# Personal marketplace
/plugin marketplace add gse-one/gse-one
/plugin install gse-one@gse-one

# Official marketplace
/plugin install gse-one

# Local test
claude --plugin-dir ./plugin/
```

### Cursor User

```bash
# Official marketplace
# /add-plugin > search "gse-one"

# Local
# /add-plugin > Local > select the plugin/ directory
```

### Verification

Regardless of the method, type:

```
/gse:go
```

The GSE-One agent should respond, detect the project state and propose the next activity.

---

## Versioning

See [CHANGELOG.md](CHANGELOG.md) for version history.

To publish a new version:

1. Update the `VERSION` constant in `gse_generate.py`
2. Regenerate: `python3 gse_generate.py --clean --verify`
3. Update `CHANGELOG.md`
4. Commit + tag: `git tag vX.Y.Z && git push origin main --tags`
