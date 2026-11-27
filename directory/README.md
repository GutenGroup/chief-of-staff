# Chief of Staff (Markdown edition)

**Built to run unattended in bypass permissions mode.** Sessions act without permission prompts; you turn that mode on
yourself (the app's permission-mode picker, or `"permissions": {"defaultMode": "bypassPermissions"}` in your own
`~/.claude/settings.json`). This plugin never changes your permission mode. Two hard stops always reach you, in any mode:
`[legal]` (signing, accepting terms, attesting) and `[money]` (paying, buying, moving money). Each arrives as a ready
packet with a recommendation, the values to verify and one link to the final step.

The role instructions of the Chief of Staff plugin: the Chief of Staff, the Production VP, the Communication VP, the
project COO and the Helm operating model, three commands and the cheap `coo-worker` agent.

## What the full install adds

The full install adds three autonomy hooks that enforce the two hard stops: an ask gate (`PreToolUse` on
`AskUserQuestion`), a stop guard (`Stop`) and a pushback catcher (`UserPromptSubmit`). They only deny and inform, never
change permissions, fail open and stop when `~/.claude/cos-autonomy-off` exists. This edition has no hooks and no
scripts; follow the rules in the skills by hand.

The scripts (the `cos` command, the job runner, the hooks and the optional Workspace panel) are installed from the main
repository: https://github.com/GutenGroup/chief-of-staff#readme.

Version 1.7.2. License: MIT. Made by Guten Group, https://guten.group/ai/chief-of-staff/
