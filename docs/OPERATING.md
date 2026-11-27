# Operating the system

How the Chief of Staff, the Production VP and the COOs keep running for weeks: where their memory lives, when they
clear, which model and effort each job gets, and how the loops keep going. Every number here is a default you can
change.

## Bypass permissions mode

The system is built to run unattended in **bypass permissions** mode, where sessions act without tool permission
prompts. Turn it on yourself, either way:

- pick it in the app's permission-mode picker, or
- add `"permissions": {"defaultMode": "bypassPermissions"}` to your own `~/.claude/settings.json`.

The plugin never changes your permission mode. In any other mode it still works, but each approval the app asks for
stops that session. `cos status` and the Workspace panel show one line when a session is not in bypass mode. The
hard stops, `[legal]`, `[money]` and `[big]`, reach you in every mode. See the [autonomy contract](AUTONOMY.md).

## Memory and clearing

**No role keeps anything important in its conversation.** Its memory is in files, rewritten every pass:

| Role | Its memory | Its training files |
|---|---|---|
| Chief of Staff | `~/.claude/needs-input/cos-state.json` (last run, nudges, what it is watching, up to 10 standing notes, clear log, model audit) and `cos-brief.json` (the brief) | `DECISIONS.md` in the data folder |
| Production VP | `Context/Production_VP/_COO_STATE.md` | `Context/Production_VP/coo/` (persona, playbook, knowledge, lessons, scorecard) |
| Each COO | `Context/<Project>/_COO_STATE.md` (worker ids and status, open PRs, open loops with owners, due times, standing rules) | `Context/<Project>/coo/` (same five files) |

Because of that, any role can be cleared at any moment and pick up where it left off.

**When each role clears** (tokens in its context window):

| Role | Clears at | Config key |
|---|---|---|
| Chief of Staff | 150,000 | `clear_at_cos` |
| Production VP | 200,000 | `clear_at_vp` |
| Each COO | 150,000 | `clear_at_coo` |

Change them in `~/.claude/cos-config.yaml`; `cos status` shows the values in use (50,000 is the floor).

**The clear sequence for a COO or the VP** (the Chief of Staff runs it hourly):

1. It reads the session's usage. At or over its limit, it asks the session to write its state file, complete and
   dated, and reply `state written, ready to clear`.
2. It clears only when the session said ready (or its state file is newer than the request), is idle, is not open on
   your screen, has no queued message and has no live cron. A cron would block the clear, so the session deletes its
   own crons first.
3. A pinned session is unpinned, cleared and re-pinned.
4. Right after the clear it sends: "You were cleared. Re-read your skill and your state file, re-arm your loop, report
   one line." The session keeps its id, title, sidebar group and worker links.

**The Chief of Staff clears itself.** At its own limit it finishes the pass, writes `cos-state.json` with
`selfClearedAt`, and clears its own session. The Workspace panel wakes it about two minutes later, and it rebuilds
from its files. Without the panel, its next loop tick does the same.

**Why clearing beats compaction.** Compaction squeezes a long conversation into a summary the model wrote for itself:
details drop out without anyone deciding which, old mistakes can survive as "facts", and the summary still costs
tokens on every turn. A clear starts from files you can read, edit and correct. What survives a clear is exactly what
the role wrote down on purpose.

## Max context

Claude models come with a 200k or a 1M token window. A role could keep going until the window is full. It doesn't,
for two reasons:

- **Cost.** Every turn re-reads the whole context. A role at 600k tokens pays about four times as much per turn as the
  same role at 150k, for the same pass.
- **Quality.** Models attend less well to the middle of a very long context. A fresh role reading a 2-page state file
  makes better calls than one digging through 600k tokens of old turns.

So the limits sit far below the maximum, on either window size. The VP gets a little more (200k) because one of its
passes reads several product COOs' reports and diffs. Raise a limit only if a role clears more than about once a day
and you can see it losing the thread. Lower one if your usage is high.

## Models and effort

The Chief of Staff checks every session it reads (`model` and `effort`) and moves drifted ones back. COOs set the
same for every worker they start.

| Task | Model | Effort |
|---|---|---|
| Search, status, triage, monitors | Haiku | low |
| Mechanical code: edits, tests, migrations, boilerplate | Sonnet (or a cheaper coding agent you trust) | low |
| Multistep or unclear code | Sonnet | medium |
| Original design, architecture, judgment | Opus | medium |
| Verification, security review | the worker's model | high, for that step only, then back down |
| COO routine pass | Sonnet | low |
| COO planning or decision pass | Sonnet | medium |
| Production VP | Opus | medium, delegate-only |
| Chief of Staff | Opus | medium |

**Effort stays low by default.** Higher effort buys more checking of its own work and more decisions made on your
behalf; it does not make the model smarter. On a clearly specified task low and high land close together. On a vague
task high effort just fills the gaps with more guesses. So the rule is: **spend effort on the spec and the verify,
never the build.** Get the task clear first (the COO's brief says what done looks like and how to check it), build on
low, then raise effort only for the verification step.

**Never `max`, never fast mode by default.** A worker left on Opus `max` for a routine edit can burn many times the
credits of a Sonnet `low` worker for the same result. That is why the audit runs every pass: sessions the Chief of
Staff or a COO started are fixed and logged (`model_audit` in `cos-state.json`); sessions you started are never
changed, you get one line in the brief instead.

## Loops and cadence

| Who | Loop | Started by |
|---|---|---|
| Chief of Staff | every 30 min (`*/30 * * * *`, prompt `/chief-of-staff`) | itself, on its first run |
| Production VP | every 3 h (`/loop 3h /project-coo`) | the Chief of Staff, at setup |
| Each COO | every 3 h (`/loop 3h /project-coo`) | the Chief of Staff, at setup or `/add-coo` |

- **Duplicate-tick guard.** The loop and the Workspace panel can both wake the Chief of Staff. Each pass starts with
  `cos tick-check`: when nothing it reads has changed since the last complete pass, it prints `SKIP` and the pass ends
  at once. A pass that ran to the end records itself with `cos tick-complete`. A direct question from you always runs.
- **Loops expire after 7 days.** Claude Code ends `/loop` jobs after a week. The Chief of Staff checks `CronList` at
  the start of every run and re-arms its own loop when it is gone. A COO silent for more than 4 hours (one missed
  3-hour pass plus margin) gets resumed with a full brief, which includes re-arming its loop. You hear about it only if
  it stays down after one resume.
- **A pass with no change writes nothing and sends nothing.** Quiet weeks cost little.

## Decisions with Jev (optional)

With a Jev key the roles ask a small calibrated model four questions before they act: who should get this work, how
much effort it needs, whether an action is safe to take alone, and whether to retry after a failure. Without a key they
use their own judgment. See [With and without Jev](JEV.md).
