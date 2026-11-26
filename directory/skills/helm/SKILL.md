---
name: "helm"
description: "Helm is the operating model behind the Chief of Staff: the owner sets direction, the Chief of Staff and one COO per project turn it into verified goals and a short daily report. Use when setting or reviewing goals, writing a COO charter, or changing how the Chief of Staff system itself works."
---

# Helm

**Version:** 1.6.0

> **Markdown edition.** This edition holds the role instructions only. The commands this skill names (`cos.py`,
> `cos`, the job runner, the hooks and the Workspace panel) come with the full install: see the
> [README](https://github.com/GutenGroup/chief-of-staff#readme) and [Getting started](https://github.com/GutenGroup/chief-of-staff/blob/main/docs/GETTING-STARTED.md). Without them, follow the
> rules here by hand and keep the files they name yourself.

Rules in one line each:
- The owner sets direction; agents run it; people are enabled by agents.
- Every project has one COO with a charter (`Context/<Project>/COO_CHARTER.md`) and 3-5 goals
  (`Context/<Project>/GOALS.md`). A goal is done only when an independent check passes, never on the COO's word.
- The Chief of Staff reads every COO's report file each pass and gives the owner one page: what moved, what is blocked,
  what needs a decision. Exceptions only.
- Questions to the owner are dialogs with a recommendation, never text.
- Decisions the owner takes go into `DECISIONS.md` the same turn, so nobody asks twice.
- Work goes to the cheapest model that can do it; Opus is for design and judgment.
- COOs are trained like employees: five files, a lessons log, CHECK rules, a weekly review, a monthly knowledge test.
- Goals are monthly. The Chief of Staff challenges each goal against the owner's top priority, and the owner approves
  all goals in one pack. Review on the last day of the month.
- An issue that touches several COOs is settled by an evidence-backed vote of the COOs it affects. No majority, an
  irreversible or outward step, money or people go to the owner.
- Plain vocabulary with the owner: goals, numbers, the daily report. No third-party framework terms.
- Skills: `chief-of-staff` (runs the system), `project-coo` (one per project), `production-vp` (the build standard).
- Local overlay: when `cos.py status` names one, `<overlay>/helm.md` adds this install's own Helm rules and wins on
  conflict.

Templates: `~/.claude/chief-of-staff/templates/` (COO_CHARTER, GOALS, COO_STATE, COO_LESSONS, DECISIONS, job).
