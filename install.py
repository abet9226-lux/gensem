#!/usr/bin/env python3
"""GSE-One Installer — Cross-platform interactive installation for Claude Code and Cursor.

Usage:
    python3 install.py                        # Interactive mode
    python3 install.py --platform claude --mode plugin --scope project
    python3 install.py --platform cursor --mode plugin
    python3 install.py --platform both --mode plugin --scope user
    python3 install.py --uninstall --platform claude
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent
VERSION_FILE = REPO_ROOT / "VERSION"
PLUGIN_DIR = REPO_ROOT / "gse-one" / "plugin"

if VERSION_FILE.exists():
    VERSION = VERSION_FILE.read_text().strip()
else:
    VERSION = "unknown"


# ---------------------------------------------------------------------------
# Colors (ANSI, with Windows support)
# ---------------------------------------------------------------------------

def _supports_color():
    """Detect whether the terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if platform.system() == "Windows":
        # Enable ANSI on Windows 10+
        try:
            os.system("")  # enables ANSI escape processing
            return True
        except Exception:
            return False
    return True


USE_COLOR = _supports_color()


def _c(code, text):
    """Apply ANSI color code to text if supported."""
    if USE_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text


def green(t):   return _c("32", t)
def red(t):     return _c("31", t)
def yellow(t):  return _c("33", t)
def cyan(t):    return _c("36", t)
def bold(t):    return _c("1", t)
def dim(t):     return _c("2", t)


BANNER = f"""
  {bold(cyan('GSE-One Installer'))}  v{VERSION}
  {dim('Cross-platform setup for Claude Code and Cursor')}
  {'─' * 50}
"""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def info(msg):  print(f"  {dim('[INFO]')}  {msg}")
def ok(msg):    print(f"  {green('[ OK ]')}  {msg}")
def warn(msg):  print(f"  {yellow('[WARN]')}  {msg}")
def err(msg):   print(f"  {red('[ERR ]')}  {msg}", file=sys.stderr)
def step(msg):  print(f"\n  {bold(msg)}\n  {'─' * len(msg)}")


# ---------------------------------------------------------------------------
# Installation tracker (for summary table)
# ---------------------------------------------------------------------------

class InstallTracker:
    """Tracks installation actions and their results for the summary."""

    def __init__(self):
        self.rows = []  # list of (platform, mode, scope, location, status, detail)

    def add(self, plat, mode, scope, location, status, detail=""):
        self.rows.append((plat, mode, scope, str(location), status, detail))

    def display(self):
        """Print the final summary."""
        if not self.rows:
            return

        print()
        step("Summary")
        print()

        for plat, mode, scope, location, status, detail in self.rows:
            if status == "OK":
                status_str = green("OK")
            elif status == "WARN":
                status_str = yellow("WARN")
            else:
                status_str = red("FAIL")

            print(f"  {status_str}  {bold(plat)} — {mode} ({scope})")
            if detail:
                print(f"       {dim(detail)}")
            if location and location != "-":
                loc_short = location
                if len(loc_short) > 70:
                    loc_short = "..." + loc_short[-67:]
                print(f"       {dim(loc_short)}")
            print()

        all_ok = all(s == "OK" for _, _, _, _, s, _ in self.rows)
        if all_ok:
            print(f"  {green('All installations succeeded.')}")
        else:
            has_fail = any(s == "FAIL" for _, _, _, _, s, _ in self.rows)
            if has_fail:
                print(f"  {red('Some installations failed. See details above.')}")
            else:
                print(f"  {yellow('Completed with warnings. See details above.')}")

        print()
        print(f"  {cyan('Next step:')} Type {bold('/gse:go')} in your coding agent to start.")
        print()


tracker = InstallTracker()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def ask(prompt, choices):
    """Ask the user to pick from a numbered list. Returns the chosen value."""
    print()
    for i, (label, _) in enumerate(choices, 1):
        print(f"    {bold(f'[{i}]')} {label}")
    print()
    while True:
        try:
            raw = input(f"  {prompt} [1-{len(choices)}]: ").strip()
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return choices[idx - 1][1]
        except (ValueError, EOFError):
            pass
        warn(f"Please enter a number between 1 and {len(choices)}.")


def confirm(prompt):
    """Ask yes/no. Returns True for yes."""
    while True:
        raw = input(f"  {prompt} [{green('y')}/{red('n')}]: ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False


def command_exists(cmd):
    """Check if a command is available on PATH."""
    return shutil.which(cmd) is not None


def remove_path(path):
    """Remove a file, symlink, or directory tree."""
    path = Path(path)
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def copy_tree(src, dst):
    """Copy a directory tree, overwriting destination if it exists."""
    dst = Path(dst)
    remove_path(dst)
    shutil.copytree(src, dst)


def ensure_dir(path):
    """Create directory and parents if needed."""
    Path(path).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Post-install verification
# ---------------------------------------------------------------------------

def verify_plugin(location, platform_name):
    """Verify a plugin installation is valid. Returns (ok, detail)."""
    location = Path(location)

    # 1. Directory exists
    if not location.is_dir():
        return False, "directory not found"

    # 2. Find and parse manifest
    if platform_name == "claude":
        manifest = location / ".claude-plugin" / "plugin.json"
    else:
        manifest = location / ".cursor-plugin" / "plugin.json"

    if not manifest.exists():
        return False, "manifest not found"

    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError):
        return False, "manifest is not valid JSON"

    # 3. Version present and matches
    manifest_version = data.get("version", "")
    if manifest_version == VERSION:
        return True, f"v{manifest_version}"
    elif manifest_version:
        return True, f"v{manifest_version} (expected {VERSION})"
    else:
        return False, "no version in manifest"


def verify_no_plugin(location, platform_name):
    """Verify a non-plugin installation. Returns (ok, detail)."""
    location = Path(location)

    if platform_name == "claude":
        base = location / ".claude"
    else:
        base = location / ".cursor"

    if not base.is_dir():
        return False, f"{base.name}/ not found"

    skills = base / "skills"
    agents = base / "agents"

    if not skills.is_dir():
        return False, "skills/ not found"
    if not agents.is_dir():
        return False, "agents/ not found"

    skill_count = sum(1 for d in skills.iterdir() if d.is_dir())
    agent_count = sum(1 for f in agents.glob("*.md"))

    return True, f"{skill_count} skills, {agent_count} agents"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_environment():
    """Detect OS, Claude Code CLI, and Cursor availability."""
    os_name = platform.system()
    os_display = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(os_name, os_name)

    has_claude = command_exists("claude")
    has_cursor = _detect_cursor(os_name)

    home = Path.home()
    claude_dir = home / ".claude"
    cursor_dir = home / ".cursor"

    return {
        "os": os_display,
        "os_raw": os_name,
        "has_claude": has_claude,
        "has_cursor": has_cursor,
        "home": home,
        "claude_dir": claude_dir,
        "cursor_dir": cursor_dir,
    }


def _detect_cursor(os_name):
    """Detect if Cursor is installed."""
    home = Path.home()
    if os_name == "Darwin":
        return (Path("/Applications/Cursor.app").exists()
                or (home / "Applications" / "Cursor.app").exists()
                or (home / ".cursor").exists())
    elif os_name == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        return (local / "Programs" / "cursor").exists() or (home / ".cursor").exists()
    else:  # Linux
        return (command_exists("cursor")
                or (home / ".cursor").exists())


def display_environment(env):
    """Print detected environment."""
    step("Environment")
    info(f"Operating system : {bold(env['os'])}")
    info(f"Home directory   : {env['home']}")
    info(f"Claude Code CLI  : {green('found') if env['has_claude'] else yellow('not found')}")
    info(f"Cursor           : {green('found') if env['has_cursor'] else yellow('not found')}")
    info(f"Plugin source    : {PLUGIN_DIR}")
    info(f"Version          : {bold(VERSION)}")

    if not PLUGIN_DIR.exists():
        err(f"Plugin directory not found: {PLUGIN_DIR}")
        err("Make sure you run this script from the gensem repository root.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Claude Code — Plugin mode
# ---------------------------------------------------------------------------

def install_claude_plugin(scope):
    """Install GSE-One as a Claude Code plugin using the CLI."""
    step(f"Claude Code — Plugin install (scope: {scope})")

    if not command_exists("claude"):
        err("Claude Code CLI not found on PATH.")
        err("Install it from https://claude.ai/download and try again.")
        tracker.add("Claude Code", "plugin", scope, "-", "FAIL", "CLI not found")
        return False

    plugin_path = str(PLUGIN_DIR)
    cmd = ["claude", "plugin", "install", plugin_path, "--scope", scope]
    info(f"Running: {dim(' '.join(cmd))}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            ok(f"Plugin installed (scope: {scope})")
            if result.stdout.strip():
                info(result.stdout.strip())
            tracker.add("Claude Code", "plugin", scope, plugin_path, "OK", f"v{VERSION}")
            return True
        else:
            err(f"Installation failed (exit {result.returncode})")
            if result.stderr.strip():
                err(result.stderr.strip())
            tracker.add("Claude Code", "plugin", scope, plugin_path, "FAIL", f"exit {result.returncode}")
            return False
    except FileNotFoundError:
        err("Claude Code CLI not found.")
        tracker.add("Claude Code", "plugin", scope, "-", "FAIL", "CLI not found")
        return False
    except subprocess.TimeoutExpired:
        err("Installation timed out.")
        tracker.add("Claude Code", "plugin", scope, "-", "FAIL", "timeout")
        return False


def uninstall_claude_plugin():
    """Uninstall GSE-One from Claude Code."""
    step("Claude Code — Plugin uninstall")

    if not command_exists("claude"):
        err("Claude Code CLI not found on PATH.")
        tracker.add("Claude Code", "plugin", "-", "-", "FAIL", "CLI not found")
        return False

    cmd = ["claude", "plugin", "uninstall", "gse"]
    info(f"Running: {dim(' '.join(cmd))}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            ok("Plugin uninstalled from Claude Code")
            tracker.add("Claude Code", "uninstall", "-", "-", "OK", "removed")
            return True
        else:
            warn(f"Uninstall returned exit {result.returncode}")
            if result.stderr.strip():
                warn(result.stderr.strip())
            tracker.add("Claude Code", "uninstall", "-", "-", "WARN", f"exit {result.returncode}")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        err("Could not run claude CLI.")
        tracker.add("Claude Code", "uninstall", "-", "-", "FAIL", "CLI error")
        return False


# ---------------------------------------------------------------------------
# Claude Code — Non-plugin mode
# ---------------------------------------------------------------------------

def install_claude_no_plugin(project_dir):
    """Install GSE-One artifacts directly into .claude/ of a project."""
    step("Claude Code — Non-plugin install")

    claude_dir = Path(project_dir) / ".claude"
    ensure_dir(claude_dir)

    # Skills
    skills_dst = claude_dir / "skills"
    ensure_dir(skills_dst)
    skills_src = PLUGIN_DIR / "skills"
    count = 0
    for skill_dir in sorted(skills_src.iterdir()):
        if skill_dir.is_dir():
            copy_tree(skill_dir, skills_dst / skill_dir.name)
            count += 1
    ok(f"Copied {count} skills to {skills_dst}")
    warn("Commands will be /name (e.g., /plan) instead of /gse:name")

    # Agents
    agents_dst = claude_dir / "agents"
    ensure_dir(agents_dst)
    agents_src = PLUGIN_DIR / "agents"
    agent_count = 0
    for agent_file in sorted(agents_src.glob("*.md")):
        shutil.copy2(agent_file, agents_dst / agent_file.name)
        agent_count += 1
    ok(f"Copied {agent_count} agents to {agents_dst}")

    # Templates
    templates_dst = claude_dir / "templates"
    copy_tree(PLUGIN_DIR / "templates", templates_dst)
    ok(f"Copied templates to {templates_dst}")

    # Hooks
    hooks_file = PLUGIN_DIR / "hooks" / "hooks.claude.json"
    settings_file = claude_dir / "settings.json"
    _merge_hooks_into_settings(hooks_file, settings_file)
    ok(f"Merged hooks into {settings_file}")

    # Default agent
    _set_default_agent(settings_file, "gse-orchestrator")
    ok(f"Set default agent to gse-orchestrator")

    # Verify
    is_ok, detail = verify_no_plugin(project_dir, "claude")
    if is_ok:
        tracker.add("Claude Code", "no-plugin", "project", str(claude_dir), "OK", detail)
    else:
        tracker.add("Claude Code", "no-plugin", "project", str(claude_dir), "WARN", detail)

    return True


def uninstall_claude_no_plugin(project_dir):
    """Remove GSE-One artifacts from .claude/."""
    step("Claude Code — Non-plugin uninstall")

    claude_dir = Path(project_dir) / ".claude"

    skills_dir = claude_dir / "skills"
    if skills_dir.exists():
        for name in _get_skill_names():
            d = skills_dir / name
            if d.exists():
                shutil.rmtree(d)
        ok(f"Removed GSE-One skills from {skills_dir}")

    agents_dir = claude_dir / "agents"
    if agents_dir.exists():
        for f in (PLUGIN_DIR / "agents").glob("*.md"):
            target = agents_dir / f.name
            if target.exists():
                target.unlink()
        ok(f"Removed GSE-One agents from {agents_dir}")

    templates_dir = claude_dir / "templates"
    if templates_dir.exists():
        shutil.rmtree(templates_dir)
        ok(f"Removed {templates_dir}")

    info("Hooks and settings.json were not modified (manual cleanup if needed)")
    tracker.add("Claude Code", "uninstall", "project", str(claude_dir), "OK", "removed")
    return True


# ---------------------------------------------------------------------------
# Cursor — Plugin mode
# ---------------------------------------------------------------------------

def install_cursor_plugin(env):
    """Install GSE-One as a Cursor plugin by copying to ~/.cursor/plugins/."""
    step("Cursor — Plugin install")

    plugins_dir = env["cursor_dir"] / "plugins" / "local"
    ensure_dir(plugins_dir)

    dst = plugins_dir / "gse-one"
    if dst.exists() or dst.is_symlink():
        info(f"Removing previous installation at {dst}")
        remove_path(dst)

    copy_tree(PLUGIN_DIR, dst)
    ok(f"Plugin copied to {dst}")

    # Verify
    is_ok, detail = verify_plugin(dst, "cursor")
    if is_ok:
        ok(f"Verified: {detail}")
        tracker.add("Cursor", "plugin", "global", str(dst), "OK", detail)
    else:
        warn(f"Verification issue: {detail}")
        tracker.add("Cursor", "plugin", "global", str(dst), "WARN", detail)

    return True


def uninstall_cursor_plugin(env):
    """Remove GSE-One from Cursor plugins."""
    step("Cursor — Plugin uninstall")

    dst = env["cursor_dir"] / "plugins" / "local" / "gse-one"
    if dst.exists() or dst.is_symlink():
        remove_path(dst)
        ok(f"Removed {dst}")
        tracker.add("Cursor", "uninstall", "global", str(dst), "OK", "removed")
    else:
        info("No Cursor plugin installation found.")
        tracker.add("Cursor", "uninstall", "global", str(dst), "WARN", "not found")
    return True


# ---------------------------------------------------------------------------
# Cursor — Non-plugin mode
# ---------------------------------------------------------------------------

def install_cursor_no_plugin(project_dir):
    """Install GSE-One artifacts directly into .cursor/ of a project."""
    step("Cursor — Non-plugin install")

    cursor_dir = Path(project_dir) / ".cursor"
    ensure_dir(cursor_dir)

    # Skills
    skills_dst = cursor_dir / "skills"
    ensure_dir(skills_dst)
    skills_src = PLUGIN_DIR / "skills"
    count = 0
    for skill_dir in sorted(skills_src.iterdir()):
        if skill_dir.is_dir():
            copy_tree(skill_dir, skills_dst / skill_dir.name)
            count += 1
    ok(f"Copied {count} skills to {skills_dst}")
    warn("Commands will be /name (e.g., /plan) instead of /gse:name")

    # Agents
    agents_dst = cursor_dir / "agents"
    ensure_dir(agents_dst)
    agents_src = PLUGIN_DIR / "agents"
    agent_count = 0
    for agent_file in sorted(agents_src.glob("*.md")):
        shutil.copy2(agent_file, agents_dst / agent_file.name)
        agent_count += 1
    ok(f"Copied {agent_count} agents to {agents_dst}")

    # Rules (.mdc)
    rules_dst = cursor_dir / "rules"
    ensure_dir(rules_dst)
    rules_src = PLUGIN_DIR / "rules"
    for rule_file in sorted(rules_src.glob("*.mdc")):
        shutil.copy2(rule_file, rules_dst / rule_file.name)
    ok(f"Copied rule(s) to {rules_dst}")

    # Templates
    templates_dst = cursor_dir / "templates"
    copy_tree(PLUGIN_DIR / "templates", templates_dst)
    ok(f"Copied templates to {templates_dst}")

    # Hooks
    hooks_src = PLUGIN_DIR / "hooks" / "hooks.cursor.json"
    hooks_dst = cursor_dir / "hooks.json"
    if hooks_src.exists():
        shutil.copy2(hooks_src, hooks_dst)
        ok(f"Copied hooks to {hooks_dst}")

    # Verify
    is_ok, detail = verify_no_plugin(project_dir, "cursor")
    if is_ok:
        tracker.add("Cursor", "no-plugin", "project", str(cursor_dir), "OK", detail)
    else:
        tracker.add("Cursor", "no-plugin", "project", str(cursor_dir), "WARN", detail)

    return True


def uninstall_cursor_no_plugin(project_dir):
    """Remove GSE-One artifacts from .cursor/."""
    step("Cursor — Non-plugin uninstall")

    cursor_dir = Path(project_dir) / ".cursor"

    for subdir in ("skills", "agents", "templates"):
        d = cursor_dir / subdir
        if d.exists():
            shutil.rmtree(d)
            ok(f"Removed {d}")

    rules_dir = cursor_dir / "rules"
    if rules_dir.exists():
        for f in rules_dir.glob("*gse*"):
            f.unlink()
            ok(f"Removed {f}")

    hooks_file = cursor_dir / "hooks.json"
    if hooks_file.exists():
        hooks_file.unlink()
        ok(f"Removed {hooks_file}")

    tracker.add("Cursor", "uninstall", "project", str(cursor_dir), "OK", "removed")
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_skill_names():
    """Return the list of skill directory names."""
    skills_src = PLUGIN_DIR / "skills"
    return [d.name for d in sorted(skills_src.iterdir()) if d.is_dir()]


def _merge_hooks_into_settings(hooks_file, settings_file):
    """Merge hooks from a hooks JSON file into a settings.json file."""
    if not hooks_file.exists():
        return

    hooks_data = json.loads(hooks_file.read_text())

    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    else:
        settings = {}

    if "hooks" not in settings:
        settings["hooks"] = {}

    src_hooks = hooks_data.get("hooks", {})
    for event, groups in src_hooks.items():
        if event == "version":
            continue
        if event not in settings["hooks"]:
            settings["hooks"][event] = []
        settings["hooks"][event].extend(groups)

    settings_file.write_text(json.dumps(settings, indent=2) + "\n")


def _set_default_agent(settings_file, agent_name):
    """Set the default agent in settings.json."""
    if settings_file.exists():
        settings = json.loads(settings_file.read_text())
    else:
        settings = {}

    settings["agent"] = agent_name
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

def interactive_menu(env):
    """Run the interactive installation menu."""

    platform_choices = []
    if env["has_claude"]:
        platform_choices.append(("Claude Code", "claude"))
    if env["has_cursor"]:
        platform_choices.append(("Cursor", "cursor"))
    if env["has_claude"] and env["has_cursor"]:
        platform_choices.append(("Both (Claude Code + Cursor)", "both"))
    if not env["has_claude"]:
        platform_choices.append(("Claude Code (not detected — install anyway)", "claude"))
    if not env["has_cursor"]:
        platform_choices.append(("Cursor (not detected — install anyway)", "cursor"))

    chosen_platform = ask("Install for which platform?", platform_choices)

    platforms = ["claude", "cursor"] if chosen_platform == "both" else [chosen_platform]
    results = []

    for plat in platforms:
        if plat == "claude":
            mode = ask(
                "Installation mode for Claude Code?",
                [
                    ("Plugin — project scope (recommended)", "plugin-project"),
                    ("Plugin — personal scope (gitignored)", "plugin-local"),
                    ("Plugin — global scope (all projects)", "plugin-user"),
                    ("Non-plugin — copy artifacts to .claude/", "no-plugin"),
                ],
            )
            if mode == "no-plugin":
                project_dir = _ask_project_dir()
                results.append(install_claude_no_plugin(project_dir))
            else:
                scope = mode.split("-")[1]
                results.append(install_claude_plugin(scope))

        elif plat == "cursor":
            mode = ask(
                "Installation mode for Cursor?",
                [
                    ("Plugin — global (copy to ~/.cursor/plugins/)", "plugin"),
                    ("Non-plugin — copy artifacts to .cursor/", "no-plugin"),
                ],
            )
            if mode == "no-plugin":
                project_dir = _ask_project_dir()
                results.append(install_cursor_no_plugin(project_dir))
            else:
                results.append(install_cursor_plugin(env))

    return all(results)


def interactive_uninstall(env):
    """Run the interactive uninstall menu."""
    chosen = ask(
        "Uninstall from which platform?",
        [
            ("Claude Code — plugin", "claude-plugin"),
            ("Claude Code — non-plugin (current project)", "claude-no-plugin"),
            ("Cursor — plugin", "cursor-plugin"),
            ("Cursor — non-plugin (current project)", "cursor-no-plugin"),
        ],
    )

    if chosen == "claude-plugin":
        return uninstall_claude_plugin()
    elif chosen == "claude-no-plugin":
        return uninstall_claude_no_plugin(_ask_project_dir())
    elif chosen == "cursor-plugin":
        return uninstall_cursor_plugin(env)
    elif chosen == "cursor-no-plugin":
        return uninstall_cursor_no_plugin(_ask_project_dir())


def _ask_project_dir():
    """Ask the user for the project directory."""
    cwd = Path.cwd()
    print(f"\n  Current directory: {bold(str(cwd))}")
    if confirm("Use current directory as the project?"):
        return cwd
    raw = input("  Enter project path: ").strip()
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        err(f"Directory not found: {p}")
        sys.exit(1)
    return p


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=f"GSE-One Installer v{VERSION} — Cross-platform setup for Claude Code and Cursor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 install.py                                          # Interactive
  python3 install.py --platform claude --mode plugin --scope project
  python3 install.py --platform cursor --mode plugin
  python3 install.py --platform both --mode plugin --scope user
  python3 install.py --uninstall --platform claude --mode plugin
""",
    )
    parser.add_argument("--platform", choices=["claude", "cursor", "both"], help="Target platform")
    parser.add_argument("--mode", choices=["plugin", "no-plugin"], help="Installation mode")
    parser.add_argument("--scope", choices=["project", "local", "user"], default="project",
                        help="Plugin scope for Claude Code (default: project)")
    parser.add_argument("--project-dir", type=str,
                        help="Project directory for non-plugin mode (default: current directory)")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall GSE-One")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(BANNER)

    env = detect_environment()
    display_environment(env)
    args = parse_args()

    # Interactive mode
    if args.platform is None:
        if args.uninstall:
            success = interactive_uninstall(env)
        else:
            success = interactive_menu(env)

        tracker.display()
        sys.exit(0 if success else 1)

    # Non-interactive mode
    project_dir = Path(args.project_dir).resolve() if args.project_dir else Path.cwd()
    platforms = ["claude", "cursor"] if args.platform == "both" else [args.platform]
    mode = args.mode or "plugin"
    results = []

    for plat in platforms:
        if args.uninstall:
            if mode == "plugin":
                results.append(uninstall_claude_plugin() if plat == "claude" else uninstall_cursor_plugin(env))
            else:
                results.append(uninstall_claude_no_plugin(project_dir) if plat == "claude"
                               else uninstall_cursor_no_plugin(project_dir))
        else:
            if mode == "plugin":
                results.append(install_claude_plugin(args.scope) if plat == "claude"
                               else install_cursor_plugin(env))
            else:
                results.append(install_claude_no_plugin(project_dir) if plat == "claude"
                               else install_cursor_no_plugin(project_dir))

    tracker.display()
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
