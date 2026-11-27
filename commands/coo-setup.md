---
description: The guided interview that chooses your COOs (dialogs only; recommends, you decide)
---
First run `mkdir -p ~/.claude/needs-input && touch ~/.claude/needs-input/interview-active` (the ask gate allows
interview dialogs while that file exists) and remove it with `rm -f ~/.claude/needs-input/interview-active` at the end.
Load the `chief-of-staff` skill and run its section "First run and 'add a COO': the guided interview" from step 1,
even if setup was done before. Every question is an AskUserQuestion dialog with the recommended answer first.
The owner decides which COOs exist; you only recommend. Recommend bypass permissions mode and show how the owner turns it
on themselves (the app's permission-mode picker, or `"permissions": {"defaultMode": "bypassPermissions"}` in their own
`~/.claude/settings.json`); never change it yourself. Add a step: set `knowledge_sources` in `~/.claude/cos-config.yaml` to
the folders the system searches before deciding (see `docs/AUTONOMY.md` section 3). Read `~/.claude/chief-of-staff/docs/SETTING-UP-COOS.md` first.
