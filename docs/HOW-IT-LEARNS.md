# How it learns

The Chief of Staff, the Production VP and every COO are trained like employees. A correction you give once becomes a
written lesson, the lesson becomes a check that runs on every pass, and a weekly score shows whether the same mistake
comes back. Nothing here depends on the model remembering a conversation: it is all in files you can read and edit.

## The loop

| Step | What happens | Where it lands |
|---|---|---|
| 1. Correction | You correct a role ("don't ask me which COO, route it"). It stops, re-reads the source it got wrong, and records the lesson the same turn: `cos lesson <Role> "<lesson>"` | `Context/<Role>/COO_LESSONS.md`, plus one line in the fleet lessons log every role reads at start |
| 2. Check | When the mistake shows up as text, the lesson gets a CHECK line: `cos lesson <Role> "<lesson>" --check <id> "<regex>"` | `Context/<Role>/coo/LESSONS.md` |
| 3. Every pass | `coo_lesson_check.py` scans the role's reports written since the check was added. A hit becomes a coaching note the same pass | the role's `coo/SCORECARD.md` |
| 4. Weekly score | `cos learn-due` runs the weekly review (Sunday, or the first pass after it): one row per role with repeated corrections, asks it should have decided itself, stale knowledge and goal status | `coo/SCORECARD.md` and `_coo-training-<week>.md` |
| 5. Coaching | On Monday the Chief of Staff reads the training file and acts on every note, its own included; the VP's row coaches the product COOs | the role's PLAYBOOK or LESSONS |
| 6. Knowledge test | Monthly (and after a restart), one model answers five questions from the role's own files only, another grades the answers against the cited source. A wrong answer is fixed at the source | `coo/KNOWLEDGE.md` |

A lesson recorded a second time is promoted to a rule in the role's `coo/PERSONA.md`.

## What "getting better" means

Three numbers, all in the scorecards:

- **Repeated corrections per role per week go down.** The same mistake twice is the signal that a lesson is missing
  or not being read.
- **Knowledge-test scores go up.** A role that knows its own goals, owners and recent decisions answers from its files
  without guessing.
- **Fewer asks that a recorded decision already answered.** Every question to you is checked against the decision
  log; a question it already answers counts against the role.

## Who learns

| Role | Its training files | Seeded at install |
|---|---|---|
| Chief of Staff | `Context/Chief_of_Staff/coo/` | one CHECK (no "should I…" questions in text) |
| Production VP | `Context/Production_VP/coo/` | two CHECKs (no text questions, no hand-typed timestamps) |
| Each COO | `Context/<Project>/coo/` | one CHECK, plus whatever the setup interview records |

## The schedule

- **Each pass** (every 30 min for the Chief of Staff, every 3 h for the VP and COOs): lesson checks, and `cos
  learn-due`, which does nothing unless a weekly review or monthly test is due.
- **Daily at 18:05** a small background job (`launchd` on macOS, `cron` on Linux) runs `cos learn-due` too, so the
  weekly review happens even when no session is open. `uninstall.sh` removes it; set `COS_NO_LAUNCHD=1` before
  installing to skip it.
- **Monthly** the knowledge test runs in the background (it calls `claude`, so it costs a little).

## The fleet lessons log

`cos lesson` also appends one dated line to `<fleet>/lessons.log`. Every role reads the newest lines at start
(`cos lessons 20`), so a lesson one COO learned reaches the others the next pass.

## The cost review

Advice about saving money ("use Haiku for triage", "clear earlier") is a prediction, so it gets measured:

```bash
cos savings add triage-on-haiku 40 31 "per week, tokens in thousands"
cos savings review
```

The review shows measured ÷ predicted per category. Two or more measurements below 0.25 mark the advice
**disproved**: delete the lesson behind it. At 0.75 or more it **holds**.

## See it yourself

```bash
cos lessons 20                      # what every role has learned lately
cos learn-due --now                 # run this week's review now
cat ~/ChiefOfStaff/Context/Chief_of_Staff/coo/SCORECARD.md
```
