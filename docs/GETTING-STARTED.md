# Getting started

Ten minutes from install to a running Chief of Staff.

## 1. Install

You need the Claude desktop app with Claude Code (or Claude Code in a terminal) and `python3`.

In Claude Code:

```
/plugin marketplace add GutenGroup/chief-of-staff
/plugin install chief-of-staff@chief-of-staff
```

From a terminal instead:

```bash
claude plugin marketplace add GutenGroup/chief-of-staff
claude plugin install chief-of-staff@chief-of-staff
```

Standard in the desktop app: the Workspace panel (every action waiting on you, with Open, Done and Later buttons, and one line per COO with its latest outcome). The Chief of Staff installs it on its first run if it is missing; to install it yourself:

```bash
claude plugin install workspace-sidebar@chief-of-staff
```

Restart the app. On the next session start the plugin creates:

| Path | What |
|---|---|
| `~/.claude/cos-config.yaml` | your settings (only if it does not exist) |
| `~/.claude/needs-input/` | the brief and the decision queue the panel reads |
| `~/ChiefOfStaff/Context/Production_VP/` | the Production VP, which comes standard |

No COOs yet: you choose those next.

## 2. Start the Chief of Staff

1. Start a new Code session with **Opus, medium effort**.
2. Title it exactly **Chief of Staff** (the panel finds it by that title).
3. Send `/chief-of-staff`.

## 3. The COO setup interview

On its first run the Chief of Staff interviews you. Every question is a click-through dialog with the recommended answer
first, and you can always type your own answer.

1. Your first name.
2. What you build or sell: products, apps, client services, business lines. Each one is a candidate **product COO**.
3. Recurring areas: IT, admin and finance, growth and marketing, personal. Each pick is a candidate COO.
4. A recommended list (usually 2-4 COOs). Untick, rename or add.
5. For each COO you keep: what winning looks like this month. It then writes the charter and goals, builds the five
   training files and starts the COO session (`<Name> COO`).
6. It arms its own 30-minute loop.

From then on you talk to the Chief of Staff, or answer its dialogs in the panel. Run the interview again any time with
`/coo-setup`, or add a single COO with `/add-coo <name>`.

## 4. Add your own rules (optional)

Your names, tools, folders and policies go in an overlay that updates never touch:

```bash
cos overlay init
```

It creates your private overlay, `~/.claude/cos-overlay/`, with one starter file per skill. Edit them in plain language;
each skill reads its file after its own instructions and the overlay wins on conflict. More:
[Add your own rules](OVERLAY.md).

Next: [How it works](HOW-IT-WORKS.md) · [Setting up COOs](SETTING-UP-COOS.md) · [FAQ](FAQ.md)
