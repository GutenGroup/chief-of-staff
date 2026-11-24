# Reference

Commands, files, script install, several computers and tests.

## Adding a COO by hand

The guided way is "add a COO" to the Chief of Staff. By hand ([details](SETTING-UP-COOS.md#setting-one-up)):

```bash
cos add-project "New Thing"                  # product COO, reports to the Production VP
cos add-project "IT" --reports-to cos        # other COO, reports to the Chief of Staff
cos list-coos                                # the VP and every COO, whom each reports to, training files
```

Fill in the charter and goals, run `coo_onboard.py New_Thing`, then ask the Chief of Staff to start the COO.

## Where things live

| Path | What |
|---|---|
| `~/.claude/cos-config.yaml` | your name, projects, data folder, fleet mode |
| `~/.claude/needs-input/` | `index.json` (input flags), `cos-brief.json` (the brief), `cos-state.json` (Chief of Staff memory), `sidebar.json` (panel tiers) |
| `<data>/Context/<Project>/` | charter, goals, `_COO_STATE.md`, `COO_LESSONS.md`, `coo/` (the five training files) |
| `<data>/fleet/coo-reports/<Project>.md` | each COO's report, newest line first; the Chief of Staff reads these every pass |
| `<data>/DECISIONS.md` | your decisions, so nobody asks twice |

The data folder is plain markdown. Keep it in a synced folder if you want it on several machines.

## Commands

```
cos status                 mode, folders, projects, job queue
cos init                   create missing folders and starter files (never overwrites)
cos add-project <Name> [--reports-to cos]   add a COO (default: reports to the Production VP)
cos list-coos              the Production VP and every COO
cos tick-check / tick-complete   the Chief of Staff's duplicate-pass guard (used by the skill)
coo_onboard.py <Project>   build or refresh a COO's five files (never overwrites)
coo_lesson_check.py --all  check every COO's reports against its CHECK rules
coo_knowledge_test.py <Project> --real --write   monthly knowledge test (needs the claude CLI)
coo_weekly_review.py       weekly scorecard rows and coaching notes
```

## Several computers (optional)

`fleet_mode: single` is the default and needs nothing else. To spread work over more machines, give every machine the
same `fleet_dir`, any folder they all sync. Then set `fleet_mode: lead` on your main machine and `fleet_mode: member` on
the others, with a short `machine_id` each.

- On a member, install the background job runner with `./install.sh --runner`. It is a launchd job that runs every 5 minutes.
  On Linux, add the cron line the installer prints.
- COOs queue work for a machine with `cos submit job.md --to <machine>`. `templates/job.md` shows the format. Every job names a
  `class`: search, status, triage, monitor, code, multistep, `design` (needs `judgment: design`), or `verify` (needs
  `verify: true`). The runner picks the model from the class and writes the result to
  `<fleet>/coo-reports/jobs/<Project>.<machine>.md`.
- Workers are locked down: they read, edit and commit inside a folder listed under `job_repo_roots`. They cannot push,
  run interpreters or package scripts, or use the web. The COO pushes and runs the tests.
- Anything that can write a machine's inbox can queue work there, so share `fleet_dir` only between your own machines.
- Kill switch on any machine: `touch ~/.claude/cos-jobs-off`.

## External relay (optional, off by default)

The Workspace panel writes `~/.claude/needs-input/sessions.json` (open sessions and what waits on you) for outside tools
to read. It can also deliver messages into your sessions: when `~/.claude/needs-input/relay-on` exists, any
`~/.claude/needs-input/relay/<name>.json` holding `{"to": "<session id>", "text": "<message>"}` is sent to that session
within a minute, and the result is filed in `relay/sent/`. Anything that can write that folder can then talk to your
sessions, so turn it on only for a tool you trust:

```bash
touch ~/.claude/needs-input/relay-on     # on
rm ~/.claude/needs-input/relay-on        # off
```

## Uninstall

Plugin: `claude plugin uninstall chief-of-staff@chief-of-staff` (and `workspace-sidebar@chief-of-staff`). Script install:

```bash
~/chief-of-staff/uninstall.sh            # removes links, panel mod, hook and job runner; keeps config and data
~/chief-of-staff/uninstall.sh --purge    # also removes ~/.claude/cos-config.yaml and ~/.claude/needs-input
```

Your data folder is never deleted.

## Tests

```bash
python3 -m unittest discover -s tests     # cos.py: init, projects, tick guard, jobs
bash tests/test_install.sh                # full install into a scratch HOME, twice, then uninstall
```

## Script install

**Script install (no plugin system, or a fleet machine that runs the background job runner).** Requires `python3` and
`git`:

```bash
git clone https://github.com/GutenGroup/chief-of-staff ~/chief-of-staff
cd ~/chief-of-staff && ./install.sh            # add --runner on a fleet member
```

It links the release to `~/.claude/chief-of-staff` and the skills into `~/.claude/skills/` (a skill folder you already
have is left alone), writes the config only if missing, registers the Workspace panel and the hook in
`~/.claude/settings.json` after a backup, and puts a `cos` command in `~/.local/bin`. Non-interactive:
`./install.sh --yes --owner Alex`; skip the settings change with `--no-settings`. Running it again is safe. Use one of
the two install paths, not both.
