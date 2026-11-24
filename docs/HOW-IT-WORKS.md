# How it works

## The ladder

```
you
 └─ Chief of Staff          Opus, medium   session "Chief of Staff", loops every 30 min
     ├─ Production VP       Opus, medium   standard: supervises the product COOs
     │   └─ product COOs    Sonnet, low    one per product, "CoS · <Name> COO"
     │       └─ workers     Haiku/Sonnet   do the actual work
     └─ other COOs          Sonnet, low    IT, admin, growth, personal
```

Each level coordinates the one below and does not do its work. Workers do the work.

## The loops

| Who | How often | What it does |
|---|---|---|
| Chief of Staff | every 30 min | reads every session and COO report, clears false "needs input" flags, nudges stalled work, writes the brief, raises your decisions as dialogs |
| Production VP | every 3 h | reads each product COO's report, sends back "done" that was not verified, coaches |
| Each COO | every 3 h | checks its workers, starts the next job, writes one report line |
| Workers | per job | do one job, verify it, report |

Loops are `/loop` jobs inside each session. They expire after 7 days and the Chief of Staff re-arms its own.

## Memory lives in files

Every role can be cleared at any moment without losing anything, because its memory is in plain markdown:

| File | Holds |
|---|---|
| `~/.claude/needs-input/cos-state.json` | the Chief of Staff's notes, nudges and setup state |
| `~/.claude/needs-input/cos-brief.json` | the current brief and open decisions |
| `~/ChiefOfStaff/Context/<COO>/COO_CHARTER.md`, `GOALS.md` | what a COO owns and is aiming for |
| `~/ChiefOfStaff/Context/<COO>/_COO_STATE.md` | its working state |
| `~/ChiefOfStaff/fleet/coo-reports/<COO>.md` | its report lines, newest first |
| `~/ChiefOfStaff/DECISIONS.md` | your decisions, so nobody asks twice |

## Auto-clear

When a COO's context passes its limit (150k tokens, 200k for the VP) the Chief of Staff asks it to write its state file,
then clears it in place. The session keeps its id, title and workers, re-reads its files and carries on. The Chief of
Staff clears itself the same way at 150k.

## Dialogs, never questions in text

Anything that needs you becomes a multiple-choice dialog: 2-4 options, the recommended one first, each with what happens
and why. If you are away it waits in the panel. Before asking, the system checks your recorded decisions so you are not
asked twice. Reversible things on your own accounts that you already authorized are done, not asked.

## Training

Each COO and the VP have five files in `coo/`: PERSONA, PLAYBOOK, KNOWLEDGE, LESSONS, SCORECARD.
- A correction from you becomes a lesson the same day.
- A lesson seen twice becomes a rule in the playbook.
- A rule that shows up as text becomes a machine check (`CHECK` lines, run every pass).
- Weekly: a scorecard row per COO. Monthly: a knowledge test graded against sources.
