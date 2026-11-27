#!/bin/bash
# Remove the Chief of Staff links, panel mod, hook and job runner. Your config and data stay unless --purge.
#   ./uninstall.sh            keep ~/.claude/cos-config.yaml, ~/.claude/needs-input and the data folder
#   ./uninstall.sh --purge    also delete the config and ~/.claude/needs-input (never the data folder)
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
PURGE=0; [ "${1:-}" = "--purge" ] && PURGE=1

for s in chief-of-staff project-coo helm; do
  d="$CLAUDE_DIR/skills/$s"
  if [ -L "$d" ] && [ "$(readlink "$d")" = "$REPO/skills/$s" ]; then rm "$d"; echo "removed skill link $s"; fi
done
[ -L "$CLAUDE_DIR/chief-of-staff" ] && rm "$CLAUDE_DIR/chief-of-staff" && echo "removed ~/.claude/chief-of-staff"
[ -L "$HOME/.local/bin/cos" ] && [ "$(readlink "$HOME/.local/bin/cos")" = "$REPO/bin/cos.py" ] && rm "$HOME/.local/bin/cos"

lplist="$HOME/Library/LaunchAgents/com.chiefofstaff.learning.plist"
if [ -f "$lplist" ]; then
  launchctl bootout "gui/$(id -u)/com.chiefofstaff.learning" 2>/dev/null || true
  rm "$lplist"; echo "removed training schedule"
fi
if command -v crontab >/dev/null 2>&1 && crontab -l 2>/dev/null | grep -qF "cos.py learn-due"; then
  crontab -l 2>/dev/null | grep -vF "cos.py learn-due" | crontab - && echo "removed training schedule from crontab"
fi

plist="$HOME/Library/LaunchAgents/com.chiefofstaff.job-runner.plist"
if [ -f "$plist" ]; then
  launchctl bootout "gui/$(id -u)/com.chiefofstaff.job-runner" 2>/dev/null || true
  rm "$plist"; echo "removed job runner"
fi

if [ -f "$CLAUDE_DIR/settings.json" ]; then
  python3 - "$CLAUDE_DIR/settings.json" "$REPO" <<'PY'
import json, os, shutil, sys, time
path, repo = sys.argv[1:3]
d = json.load(open(path))
shutil.copy2(path, "%s.bak-cos-%s" % (path, time.strftime("%Y%m%d-%H%M%S")))
d.get("extraKnownMarketplaces", {}).pop("cos-mods", None)
d.get("enabledPlugins", {}).pop("workspace-sidebar@cos-mods", None)
hook = os.path.join(repo, "hooks", "peer-bare-command-drop.sh")
ours = {hook} | {"python3 " + os.path.join(repo, "hooks", n) for n in ("ask-gate.py", "stop-guard.py", "pushback-catcher.py")}
for event in ("UserPromptSubmit", "PreToolUse", "Stop"):
    entries = d.get("hooks", {}).get(event)
    if entries is not None:
        entries[:] = [e for e in entries if not any(h.get("command") in ours for h in e.get("hooks", []))]
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(d, f, indent=2); f.write("\n")
os.replace(tmp, path)
print("settings: mod and hooks removed (backup next to settings.json)")
PY
fi

if [ "$PURGE" -eq 1 ]; then
  rm -f "$CLAUDE_DIR/cos-config.yaml"; rm -rf "$CLAUDE_DIR/needs-input"
  echo "purged config and ~/.claude/needs-input (your data folder was kept)"
fi
echo "Uninstalled. Restart the Claude desktop app to drop the panel."
