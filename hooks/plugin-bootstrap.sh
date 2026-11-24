#!/bin/bash
# SessionStart (plugin install only). Points ~/.claude/chief-of-staff at this plugin version, so the skills' paths
# work after every update, and on the first session creates the config, the panel files and the Production VP.
# Never overwrites a config, data or a ~/.claude/chief-of-staff folder that is not a link. Silent; never blocks.
root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$HOME" 2>/dev/null || exit 0
link="$HOME/.claude/chief-of-staff"
mkdir -p "$HOME/.claude/needs-input" 2>/dev/null || exit 0
if [ -L "$link" ] || [ ! -e "$link" ]; then
  [ "$(readlink "$link" 2>/dev/null)" = "$root" ] || ln -sfn "$root" "$link"
fi
flags="$HOME/.claude/needs-input"
[ -f "$flags/index.json" ] || echo '{}' > "$flags/index.json"
[ -f "$flags/cos-state.json" ] || echo '{}' > "$flags/cos-state.json"
[ -f "$flags/cos-brief.json" ] || printf '{"generatedAt":"","headline":"Chief of Staff not started yet","cooking":[],"needsOwner":[]}\n' > "$flags/cos-brief.json"
cfg="$HOME/.claude/cos-config.yaml"
done_mark="$HOME/.claude/needs-input/.cos-init-done"
[ -f "$cfg" ] || cp "$root/config.example.yaml" "$cfg" 2>/dev/null
# init is idempotent; a run cut off by the hook timeout is finished on the next session.
if [ -f "$cfg" ] && [ ! -f "$done_mark" ]; then
  python3 "$root/bin/cos.py" init >/dev/null 2>&1 && touch "$done_mark"
fi
# The `cos` command, unless something else already owns that name.
cosbin="$HOME/.local/bin/cos"
if [ ! -e "$cosbin" ] && [ ! -L "$cosbin" ]; then
  mkdir -p "$HOME/.local/bin" 2>/dev/null && ln -s "$HOME/.claude/chief-of-staff/bin/cos.py" "$cosbin" 2>/dev/null
fi
exit 0
