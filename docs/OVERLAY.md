# Add your own rules

The plugin gives every install the same Chief of Staff, Production VP, Communication VP, COOs and Helm. Your setup is not the same as
anyone else's: your names, your tools, your folders, how you want to be asked. Those rules go in an **overlay**, a
private folder of your own that the Chief of Staff plugin reads on top of its own rules. By default it is yours alone, on your computer.

## Start one

```bash
cos overlay init
```

This creates your private overlay, `~/.claude/cos-overlay/`, with five starter files, one per skill:

| File | Read by |
|---|---|
| `chief-of-staff.md` | the Chief of Staff |
| `project-coo.md` | every COO |
| `production-vp.md` | the Production VP |
| `communication-vp.md` | the Communication VP (your drafter, channels, register) |
| `helm.md` | Helm (goals, charters, how the system runs) |

Each starts as a short comment that explains what to write and adds no rules. `cos overlay init` never overwrites a
file that exists, and it sets `overlay_dir` in `~/.claude/cos-config.yaml` when that is not set yet. Run it again any
time to put back a file you deleted. Check it with `cos status`: the `overlay:` line names the folder and its files.

## How it works

- `overlay_dir` in `~/.claude/cos-config.yaml` points at the folder. Default: `~/.claude/cos-overlay/`, private to you.
- Each skill reads its own file right after its own instructions.
- **The overlay wins** where the two disagree.
- **Plugin updates never touch it.** The overlay lives outside the plugin, so updating to a new release keeps every rule.
- Never put a password, key or token in it. Point at where a secret lives, never the secret.

Write plain rules, one per line:

```markdown
# Your rules for every COO
- Route anything about billing to the Finance COO.
- Our reports go to ~/Team/reports.
- Ask me before anything that emails a customer.
```

## Overlay or pull request?

| Goes in your overlay | Goes upstream as a pull request |
|---|---|
| names of people, products, machines | a rule that would help every user |
| your folders, tools, accounts and servers | a bug fix or a missing check |
| your policies and how you like to be asked | a clearer explanation in a skill or the docs |

If you are not sure: would a stranger installing the plugin want this rule? Yes means a pull request
([CONTRIBUTING](https://github.com/GutenGroup/chief-of-staff/blob/main/CONTRIBUTING.md)). No means your overlay.
Keeping your own rules out of the plugin files is what lets you take every new release without merging anything.

## People and teams connect through the Communication VP

Each person personalizes their own Chief of Staff with their own overlay; overlays are not shared. People and teams
connect through the [Communication VP](COMMUNICATION-VP.md): it sends each person and group what they should get, on
the channels you choose, and botreeve groups let several people's Chief of Staff installs talk to each other.
