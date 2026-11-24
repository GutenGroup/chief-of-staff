---
description: Answer a question about Chief of Staff from its own documentation
argument-hint: "[question]"
---
Answer the user's question about the Chief of Staff system: "$ARGUMENTS".

Answer only from these files (read the ones that fit; start with FAQ.md):
`~/.claude/chief-of-staff/docs/FAQ.md`, `GETTING-STARTED.md`, `SETTING-UP-COOS.md`, `HOW-IT-WORKS.md`,
`OPERATING.md`, `PRODUCTION-VP.md`, `COMMUNICATION-VP.md`, `HOW-IT-LEARNS.md`, `OVERLAY.md`, `MODELS-AND-COSTS.md`, `JEV.md`, `TROUBLESHOOTING.md`, `REFERENCE.md`.

Give the short answer first, then the exact command or step. Name the doc it came from. If the docs do not cover it,
say so and point to https://guten.group/ai/chief-of-staff/ and the GitHub issues page. With no question, list
the docs with one line each.
