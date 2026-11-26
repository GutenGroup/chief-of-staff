# Chief of Staff

An operating layer for Claude Code. One **Chief of Staff** session watches all your other sessions. A **Production VP**
and a **Communication VP** (all your messages in and out) come standard. You choose your own **COOs**, one per product or area of your work, and the Chief of Staff guides you
through that. The COOs hand the real work to cheap **worker** sessions.
You only see a short brief and the decisions that need you, each one a click-through dialog with a recommendation.

Built and tuned for a product studio running several products (a COO per product, a Production VP across them), and it works for anyone: one business, a solo founder, side projects or personal areas. The COO setup interview adapts to you.

```
you
 └─ Chief of Staff          (Opus, medium)   one session titled "⭐ 𝐂𝐇𝐈𝐄𝐅 𝐎𝐅 𝐒𝐓𝐀𝐅𝐅 ⭐", loops every 30 min
     ├─ Production VP       (Opus, medium)   standard: supervises the product COOs
     │   └─ product COOs    (Sonnet, low)    one per product or business line YOU choose, "<Name> COO"
     │       └─ workers     (Haiku/Sonnet)   do the actual work, report to their COO
     ├─ Communication VP    (Opus, medium)   standard: every message in and out, for every role
     └─ other COOs          (Sonnet, low)    optional: IT, admin, growth, personal; report to the Chief of Staff
```

## What it does

- **Brief, not noise.** Every 30 minutes the Chief of Staff reads every session and every COO report. It clears false
  "needs input" flags and writes a one-page brief: what moved, what is blocked, what needs you.
- **Dialogs only.** Any question for you shows up as a multiple-choice dialog with the recommended answer first, both in
  the session and in the Workspace panel. You never get an open-ended question in text.
- **Delegate first.** When you ask for something, the Chief of Staff routes it to the right COO or worker. It does no
  work itself.
- **Cheap workers.** Each job goes to the cheapest model that can do it: Haiku for search, Sonnet for code, Opus only
  for design and judgment. The Chief of Staff audits this and corrects drift.
- **Auto-clear.** A COO with a full context window writes its state file and gets cleared in place. It keeps the same
  session, title and workers, so its context never runs out.
- **Training loop.** Each COO has five files: persona, playbook, knowledge, lessons and scorecard. Corrections become
  lessons, a lesson seen twice becomes a rule, and rules that show up as text become machine checks. On top of that
  there is a weekly review and a monthly knowledge test.

## Install

In Claude Code:

```
/plugin marketplace add GutenGroup/chief-of-staff
/plugin install chief-of-staff@chief-of-staff
```

The Workspace panel comes standard in the desktop app: the Chief of Staff installs it on its first run, or run
`claude plugin install workspace-sidebar@chief-of-staff`.
Then start a session titled **⭐ 𝐂𝐇𝐈𝐄𝐅 𝐎𝐅 𝐒𝐓𝐀𝐅𝐅 ⭐** (Opus, medium) and send `/chief-of-staff`. It sets up your COOs with you.

## Documentation

- **Docs site:** https://guten.group/ai/chief-of-staff/
- **In the repo:** [Getting started](docs/GETTING-STARTED.md) · [Setting up COOs](docs/SETTING-UP-COOS.md) ·
  [How it works](docs/HOW-IT-WORKS.md) · [Operating](docs/OPERATING.md) · [Production VP](docs/PRODUCTION-VP.md) · [Communication VP](docs/COMMUNICATION-VP.md) · [How it learns](docs/HOW-IT-LEARNS.md) · [Add your own rules](docs/OVERLAY.md) ·
  [Models and costs](docs/MODELS-AND-COSTS.md) · [With and without Jev](docs/JEV.md) · [FAQ](docs/FAQ.md) ·
  [Troubleshooting](docs/TROUBLESHOOTING.md) · [Reference](docs/REFERENCE.md)
- **Inside Claude Code:** `/cos-help <your question>`

## Contributing

Anyone can propose a change by pull request. Guten Group reviews it and decides what merges; releases ship only from
what we merge. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
