#!/bin/sh
# SessionStart wrapper: the work is in bin/plugin_bootstrap.py. Always exits 0.
python3 "$CLAUDE_PLUGIN_ROOT/bin/plugin_bootstrap.py"
exit 0
