# Chief of Staff (Markdown edition)

**Built to run unattended in bypass permissions mode.** Sessions act without permission prompts; you turn that mode on
yourself (the app's permission-mode picker, or `"permissions": {"defaultMode": "bypassPermissions"}` in your own
`~/.claude/settings.json`). This plugin never changes your permission mode. Two hard stops always reach you, in any mode:
`[legal]` (signing, accepting terms, attesting) and `[money]` (paying, buying, moving money). Each arrives as a ready
packet with a recommendation, the values to verify and one link to the final step.

The role instructions of the Chief of Staff plugin: the Chief of Staff, the Production VP, the Communication VP, the
project COO and the Helm operating model, three commands and the cheap `coo-worker` agent.

## Hooks in this edition

Three hooks ship in `hooks/hooks.json`. They only deny and inform; they never change permissions, and each fails open,
finishes within 5 seconds and stops when `~/.claude/cos-autonomy-off` exists.

| Hook | Event | What it does |
|---|---|---|
| Ask gate | `PreToolUse` on `AskUserQuestion` | Lets a `[legal]` or `[money]` packet through; sends back every other question with the reason. |
| Stop guard | `Stop` | Blocks, once, a turn that ends on an offer or a question with no `[legal]`/`[money]` tag. |
| Pushback catcher | `UserPromptSubmit` | When you type "just do it" or "stop asking", tells the session to do it now. |

The hooks apply to the role sessions the Chief of Staff lists in `~/.claude/needs-input/roles.json`, the same as in the
full install (set `autonomy_scope: all` in `~/.claude/cos-config.yaml` to cover every session). Until the Chief of Staff
has written that list, they do nothing.

The scripts (the `cos` command, the job runner and the optional Workspace panel) are installed from the main
repository: https://github.com/GutenGroup/chief-of-staff#readme.

Version 1.7.0. License: MIT. Made by Guten Group, https://guten.group/ai/chief-of-staff/
