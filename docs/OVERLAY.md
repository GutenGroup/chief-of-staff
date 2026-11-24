# Add your own rules

The plugin gives every install the same Chief of Staff, Production VP, COOs and Helm. Your setup is not the same as
anyone else's: your names, your tools, your folders, how you want to be asked. Those rules go in an **overlay**, a
private folder of your own that the skills read on top of the package. By default it is yours alone, on your computer.

## Start one

```bash
cos overlay init
```

This creates your private overlay, `~/.claude/cos-overlay/`, with four starter files, one per skill:

| File | Read by |
|---|---|
| `chief-of-staff.md` | the Chief of Staff |
| `project-coo.md` | every COO |
| `production-vp.md` | the Production VP |
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

## Optional: share rules with your team

You do not need this. The private overlay above is the default and covers one person. Read on only if several people
on a team want the same company-wide rules.

**What to share and what to keep private**

| Share with the team | Keep in your private overlay |
|---|---|
| company-wide rules: how work is routed, who owns what, review and release policy | your personal preferences: how you like to be asked, your working hours |
| the team's shared folders, tools and services | your own accounts, machines and paths |
| names of the company's products and areas | anything about one person only |

**How**

1. Put the shared rules in a folder everyone can read: a shared drive folder, or better a git repository, so changes
   are reviewed and everyone gets them on their next pull. Use the same four file names.
2. Each person who wants them points `overlay_dir` at that folder in their own `~/.claude/cos-config.yaml`:

   ```yaml
   overlay_dir: ~/repos/team-config/cos-overlay
   ```

3. `cos status` confirms it: the `overlay:` line names the shared folder.

The skills read one overlay folder. When you point `overlay_dir` at the shared one, put any personal rules you still
want there under your own heading, or keep them out. `cos overlay init` only ever creates the private folder; it never
points you at a shared one. Anyone who can write the shared folder changes how every Chief of Staff on the team behaves,
so give write access only to people you trust.
