#!/bin/bash
# Chief of Staff installer (macOS; Linux works for the job runner and scripts, without the desktop panel).
# Safe to run again: it never overwrites your config, your data or a skill folder it did not create.
#
#   ./install.sh                                  interactive (asks for your name and projects)
#   ./install.sh --yes --owner Alex                (COOs are chosen later, in the Chief of Staff's first-run interview)
#   ./install.sh --yes --owner Alex --projects "Acme,Side Project"   (scripted: create these COOs' starter files now)
#   ./install.sh --runner                         fleet member: also install the background job runner (launchd)
#   ./install.sh --no-settings                    do not touch ~/.claude/settings.json (mod + hook)
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
CONFIG="$CLAUDE_DIR/cos-config.yaml"
FLAGS="$CLAUDE_DIR/needs-input"
YES=0; RUNNER=0; SETTINGS=1; OWNER=""; PROJECTS=""; DATA_ROOT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --runner) RUNNER=1 ;;
    --no-settings) SETTINGS=0 ;;
    --owner) OWNER="${2:-}"; shift ;;
    --projects) PROJECTS="${2:-}"; shift ;;
    --data-root) DATA_ROOT="${2:-}"; shift ;;
    -h|--help) sed -n 2,9p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '%s\n' "$*"; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v claude >/dev/null || say "note: the 'claude' CLI is not on PATH; the desktop app works without it, job runners need it."

mkdir -p "$CLAUDE_DIR/skills" "$FLAGS"

# 1. The release itself at a fixed path, so skills and the mod can name it.
if [ -L "$CLAUDE_DIR/chief-of-staff" ] || [ ! -e "$CLAUDE_DIR/chief-of-staff" ]; then
  ln -sfn "$REPO" "$CLAUDE_DIR/chief-of-staff"
  say "linked ~/.claude/chief-of-staff -> $REPO"
else
  echo "~/.claude/chief-of-staff exists and is not a link; move it away and run again" >&2; exit 1
fi

# 2. Skills. A skill folder that is not our link is left alone (yours wins).
for s in chief-of-staff project-coo helm; do
  dest="$CLAUDE_DIR/skills/$s"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$REPO/skills/$s" ]; then
    say "skill $s: already linked"
  elif [ -e "$dest" ] || [ -L "$dest" ]; then
    say "skill $s: SKIPPED, $dest already exists and is not this release (remove it to use this one)"
  else
    ln -s "$REPO/skills/$s" "$dest"
    say "skill $s: linked"
  fi
done

# 3. Config (written once).
if [ ! -f "$CONFIG" ]; then
  if [ "$YES" -eq 0 ] && [ -t 0 ]; then
    [ -n "$OWNER" ] || read -r -p "Your first name (the agents will call you this): " OWNER
    [ -n "$DATA_ROOT" ] || read -r -p "Data folder [~/ChiefOfStaff]: " DATA_ROOT
  fi
  COS_OWNER="$OWNER" COS_PROJECTS="$PROJECTS" COS_ROOT="${DATA_ROOT:-~/ChiefOfStaff}" \
  python3 - "$REPO/config.example.yaml" "$CONFIG" <<'PY'
import os, sys, re
src, dst = sys.argv[1:3]
text = open(src).read()
owner = os.environ["COS_OWNER"].strip().replace('"', "")
projects = [p.strip() for p in os.environ["COS_PROJECTS"].split(",") if p.strip()]
text = re.sub(r'^owner_name: ""', 'owner_name: "%s"' % owner, text, flags=re.M)
text = re.sub(r'^data_root: \S+', 'data_root: %s' % os.environ["COS_ROOT"].strip(), text, flags=re.M)
if projects:
    text = re.sub(r'^projects: \[\]\n', "projects:\n" + "".join("  - %s\n" % p for p in projects), text, flags=re.M)
open(dst, "w").write(text)
PY
  say "wrote $CONFIG"
else
  say "config: $CONFIG already exists (kept)"
fi

# 4. Panel files the Workspace mod and the Chief of Staff read.
[ -f "$FLAGS/index.json" ] || echo '{}' > "$FLAGS/index.json"
[ -f "$FLAGS/cos-state.json" ] || echo '{}' > "$FLAGS/cos-state.json"
[ -f "$FLAGS/cos-brief.json" ] || printf '{"generatedAt":"","headline":"Chief of Staff not started yet","cooking":[],"needsOwner":[]}\n' > "$FLAGS/cos-brief.json"

# 5. Data folders, per-project starter files, sidebar tiers.
python3 "$REPO/bin/cos.py" init

# 6. Command on PATH.
mkdir -p "$HOME/.local/bin"
cosbin="$HOME/.local/bin/cos"
if [ -L "$cosbin" ] && [ "$(readlink "$cosbin")" = "$REPO/bin/cos.py" ]; then
  say "command cos: already linked"
elif [ -e "$cosbin" ] || [ -L "$cosbin" ]; then
  say "command cos: SKIPPED, $cosbin already exists and is not this release (run bin/cos.py directly)"
else
  ln -s "$REPO/bin/cos.py" "$cosbin"; say "command cos: linked"
fi
chmod u+x "$REPO/bin/"*.py "$REPO/hooks/"*.sh
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) say "note: add ~/.local/bin to PATH to use the 'cos' command" ;; esac

# 7. Settings: the Workspace mod (directory marketplace) and the peer-message hook. Backed up first.
if [ "$SETTINGS" -eq 1 ]; then
  python3 - "$CLAUDE_DIR/settings.json" "$REPO" <<'PY'
import json, os, shutil, sys, time
path, repo = sys.argv[1:3]
data = {}
if os.path.exists(path):
    data = json.load(open(path))
    shutil.copy2(path, "%s.bak-cos-%s" % (path, time.strftime("%Y%m%d-%H%M%S")))
changed = False
mk = data.setdefault("extraKnownMarketplaces", {})
want = {"source": {"source": "directory", "path": os.path.join(repo, "mods")}}
if mk.get("cos-mods") != want:
    mk["cos-mods"] = want; changed = True
ep = data.setdefault("enabledPlugins", {})
if ep.get("workspace-sidebar@cos-mods") is not True:
    ep["workspace-sidebar@cos-mods"] = True; changed = True
hook = os.path.join(repo, "hooks", "peer-bare-command-drop.sh")
ups = data.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
have = [h.get("command", "") for e in ups for h in e.get("hooks", [])]
if not any(c.endswith("peer-bare-command-drop.sh") for c in have):
    ups.append({"matcher": "", "hooks": [{"type": "command", "command": hook, "timeout": 5}]}); changed = True
if changed:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2); f.write("\n")
    os.replace(tmp, path)
    print("settings: Workspace mod and hook registered (backup next to settings.json)")
else:
    print("settings: already set")
PY
fi

# 8. Training schedule: once a day `cos learn-due` runs whatever is due (weekly review on Sunday, monthly knowledge
#    test). Idempotent; the Chief of Staff also calls it on every pass. COS_NO_LAUNCHD=1 skips the scheduler.
if [ "${COS_NO_LAUNCHD:-0}" != "1" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    lplist="$HOME/Library/LaunchAgents/com.chiefofstaff.learning.plist"
    mkdir -p "$(dirname "$lplist")" "$HOME/Library/Logs"
    sed "s|__HOME__|$HOME|g" "$REPO/launchd/com.chiefofstaff.learning.plist" > "$lplist.new"
    if ! cmp -s "$lplist.new" "$lplist"; then
      mv "$lplist.new" "$lplist"
      launchctl bootout "gui/$(id -u)/com.chiefofstaff.learning" 2>/dev/null || true
      launchctl bootstrap "gui/$(id -u)" "$lplist" 2>/dev/null || true
      say "training schedule: loaded (daily 18:05, runs what is due)"
    else
      rm -f "$lplist.new"; say "training schedule: already loaded"
    fi
  elif command -v crontab >/dev/null 2>&1; then
    line="5 18 * * * python3 $REPO/bin/cos.py learn-due"
    if crontab -l 2>/dev/null | grep -qF "cos.py learn-due"; then say "training schedule: already in crontab"
    else (crontab -l 2>/dev/null; echo "$line") | crontab - && say "training schedule: added to crontab (daily 18:05)"; fi
  fi
fi

# 9. Optional background job runner (fleet member).
if [ "$RUNNER" -eq 1 ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    plist="$HOME/Library/LaunchAgents/com.chiefofstaff.job-runner.plist"
    mkdir -p "$(dirname "$plist")" "$HOME/Library/Logs"
    [ -f "$plist" ] && cp -p "$plist" "$plist.bak-cos-$(date +%Y%m%d-%H%M%S)"
    sed "s|__HOME__|$HOME|g" "$REPO/launchd/com.chiefofstaff.job-runner.plist" > "$plist"
    launchctl bootout "gui/$(id -u)/com.chiefofstaff.job-runner" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$plist"
    say "job runner: loaded (every 5 min; kill switch: touch ~/.claude/cos-jobs-off)"
  else
    say "job runner on Linux: add to crontab ->  */5 * * * * python3 $REPO/bin/cos.py run-jobs"
  fi
fi

cat <<EOF

Installed Chief of Staff $(cat "$REPO/VERSION").

The Production VP and the Communication VP come standard (charters and five training files are in place).
Your COOs are yours to choose: the Chief of Staff guides you through it on its first run.

First run:
  1. Restart the Claude desktop app so it loads the Workspace panel (enable "workspace-sidebar" if asked).
  2. Start a new Code session (Opus, medium effort), title it exactly:  Chief of Staff
     and type:  /chief-of-staff
     It runs a short interview (your businesses, products, recurring areas), recommends a COO list for you to edit,
     then sets up and starts the COOs you pick. Then it arms its own 30-minute loop.
  3. Read docs/SETTING-UP-COOS.md for how to choose COOs. Add one any time: tell the Chief of Staff "add a COO".
EOF
