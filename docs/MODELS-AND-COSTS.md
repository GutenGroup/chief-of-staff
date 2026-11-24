# Models and costs

Chief of Staff runs on your own Claude plan. It has no server, subscription or API key of its own. What it costs is the
Claude usage of the sessions it runs.

## Which model does what

| Role or task | Model | Effort |
|---|---|---|
| Chief of Staff | Opus | medium |
| Production VP | Opus | medium, delegate-only |
| COO routine pass | Sonnet | low |
| COO planning or decision pass | Sonnet | medium |
| Search, status, triage, monitors | Haiku | low |
| Code, edits, tests | Sonnet | low |
| Multistep or unclear code | Sonnet | medium |
| Original design, architecture, judgment | Opus | medium |
| Verification, security review | the worker's model | high, for that step only |

Never `max` by default. The Chief of Staff audits the sessions it or a COO started and moves drifted ones back down.
Sessions you started yourself are never changed; you get one line in the brief if one looks wasteful.

## What drives usage

- **How many COOs run.** Each COO pass is a short Sonnet turn every 3 hours. Start with 2-4.
- **The Chief of Staff's loop.** One Opus pass every 30 minutes. Each pass reads only what changed since the last one,
  and a duplicate-pass guard skips a tick when nothing moved.
- **Workers.** The real work. They go to the cheapest model that fits.

## Turning it down

| Lever | How |
|---|---|
| Slower Chief of Staff loop | ask it: "loop every 60 minutes" |
| Fewer COOs | merge thin ones ([Setting up COOs](SETTING-UP-COOS.md)) |
| Pause a COO | stop its session; nothing is lost, its files stay |
| Pause everything | stop the Chief of Staff session's loop (`CronList`, then `CronDelete`) |
