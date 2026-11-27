---
description: "Add one COO for a new product or area, through a short guided interview"
argument-hint: "[name]"
---
First run `mkdir -p ~/.claude/needs-input && touch ~/.claude/needs-input/interview-active` (the ask gate allows
interview dialogs while that file exists) and remove it with `rm -f ~/.claude/needs-input/interview-active` at the end.
Load the `chief-of-staff` skill and run its guided interview for ONE new COO only (steps 4-5), named "$ARGUMENTS" if
given. Ask in dialogs whether it is a product COO (reports to the Production VP) or another COO (reports to the Chief of
Staff), what winning looks like this month, then create, onboard and start it: title `<Name> COO`, pinned, and moved into the `⭐ Chief of Staff` sidebar group (the skill's "Sidebar layout"). Never remove or restart an existing COO.

The full install (scripts, hooks, panel) is in https://github.com/GutenGroup/chief-of-staff#readme.
