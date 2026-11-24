# The Production VP

Every install comes with a Production VP. It sits between the Chief of Staff and your product COOs and holds one
standard for how everything gets built and shipped.

```
you -> Chief of Staff -> Production VP -> product COOs -> workers
```

## What it does

| | |
|---|---|
| **Holds the quality bar** | "Done" means verified live on production, pinned to the commit that shipped, with a check you can open without logging in. Work claimed done without that goes back to the COO with the check to run. |
| **Keeps work moving** | Reads every product COO's report and state file every 3 hours. A COO with open work and no report for 6 hours gets one nudge naming the next step. |
| **Ships on green** | Finished work with green checks goes to production by the repo's own deploy path and is verified there. Production lagging the main branch while CI is green is a problem it chases. |
| **Runs cross-product work** | Balances jobs across build machines by live load, removes duplicate jobs, and sends you one review pack of every changed screen instead of one click request per item. |
| **Keeps QA accounts** | One permanent test account per product, in a marked test tenant, credentials only in your secrets store. Every "verified live" runs on it, never on your own login. |
| **Coaches the COOs** | Feedback in a fixed shape (what I saw, the evidence, the standard, the fix). A slip seen twice becomes a coaching note in that COO's scorecard and, when it shows up as text, a machine check. |

It runs on Opus at medium effort and is **delegate-only**: anything over two tool calls goes to a cheap worker. It never
writes code, never steers a COO's own workers, and never decides money or legal matters. Those come to you as a dialog
through the Chief of Staff.

## Why every install gets one

A COO is good at its own product. It is not well placed to notice that it calls things "done" a little early, or that
another product solved the same problem last week. Left alone, each COO drifts toward its own definition of done. The
VP is one role whose whole job is the standard, so quality does not depend on each COO remembering it. It also keeps
build and release noise off the Chief of Staff, which then has more room for what needs you.

## What reports where

- **Build and release status:** product COO -> VP.
- **Anything that needs you, and incidents:** product COO -> Chief of Staff, directly. It never waits at the VP.
- **VP's own decisions for you:** VP -> Chief of Staff -> a dialog for you. The VP never asks you in text.
- **Non-product COOs** (IT, admin, growth, personal) report straight to the Chief of Staff.

## A typical day

- **Morning pass:** a worker checks production against main for each product. One product's deploy did not run after
  last night's merge; the VP has that COO fix it and confirms the live version next pass.
- **Midday pass:** a COO reports a feature "done" with a link that needs a login. It goes back: verify it on the QA
  account and send a check path that opens without one.
- **Afternoon pass:** two COOs queued the same test run on different machines. The VP cancels one. Three screens
  changed across two products; you get one review pack with all three.
- **Evening pass:** nothing changed. No report line, no message.

You see none of this unless something needs you. The Chief of Staff's brief has a line when the VP did something worth
knowing.

## Training

The VP gets the same five files as every COO (persona, playbook, knowledge, lessons, scorecard) in
`Context/Production_VP/coo/`, made by `cos init`. Its lessons file starts with two machine checks: no questions to you
in text, and no hand-typed timestamps. It must pass the knowledge test before it starts, and the Chief of Staff grades
it in the weekly review like any COO.

## When it stays quiet

- **No product COOs yet:** there is nothing to supervise, so the Chief of Staff does not start it. Its files wait.
- **A pass with no change** writes nothing and sends nothing.
- **No progress updates to you.** It reports to the Chief of Staff in `coo-reports/Production_VP.md`.

## Tuning it

- Clear limit: `clear_at_vp` in `~/.claude/cos-config.yaml` (default 200,000 tokens). See [Operating](OPERATING.md).
- Charter: edit `Context/Production_VP/COO_CHARTER.md`; the VP reads it at every start.
- With a Jev key it asks `route`, `effort`, `safe` and `retry` before it acts. See [With and without Jev](JEV.md).
