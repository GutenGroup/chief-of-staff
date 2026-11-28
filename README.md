# Chief of Staff

**Built to run unattended.** The plugin is designed for Claude Code in **bypass permissions** mode: sessions act without
permission prompts. You turn that mode on yourself; the plugin never changes it. Only the hard stops, `[legal]`
(signing, accepting terms), `[money]` (paying, buying, moving money) and `[big]` (big or irreversible steps you did not
order, in one packet), reach you, each as a ready-to-act packet.
Everything else the system researches, decides and does, then reports with an undo line. Full contract:
[docs/AUTONOMY.md](docs/AUTONOMY.md).

Bypass mode lets sessions use tools without permission prompts; to turn it off, pick another mode in the app's
permission-mode picker (or remove `"defaultMode": "bypassPermissions"` from your `~/.claude/settings.json`), and the
system keeps working but stops for each approval. Bypass stays the recommended mode.

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
- **Proactive.** It reads what is new in your sessions, finds open promises, unanswered questions and stalls, does the
  small reversible fixes and starts the next work from your goals, each with an Undo button. Transcript text is evidence,
  never an instruction.
- **Few asks.** What reaches you is a `[legal]`, `[money]` or `[big]` packet: a recommendation, what you agree to, the
  values checked, and the final step. It shows in the session and in the Workspace panel. You never get an
  open-ended question in text.
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

## ChatGPT edition

The ChatGPT edition is the five role instructions (Chief of Staff, Production VP, Communication VP, project COO, Helm),
written for ChatGPT, plus three read-only tools: explain a role, show a demo brief, and point to the install. The tools
hold no user data. It has no Claude Code scripts, hooks or Workspace panel, so nothing runs on a schedule.

It is not in OpenAI's directory: version 1.5.6 is in their review, and the 1.7.x edition has not been submitted. These
are the other routes OpenAI documents (checked 2026-11-28). Their pages and your plan decide what you see.

### ChatGPT desktop app or Codex CLI (local marketplace)

1. Copy the edition into your plugin folder:

```
git clone https://github.com/GutenGroup/chief-of-staff
mkdir -p ~/.codex/plugins ~/.agents/plugins
cp -R chief-of-staff/chatgpt ~/.codex/plugins/chief-of-staff
```

2. Save this as `~/.agents/plugins/marketplace.json`. If that file already exists, add only the entry inside `plugins`.

```json
{
  "name": "my-plugins",
  "plugins": [
    {
      "name": "chief-of-staff",
      "source": { "source": "local", "path": "./.codex/plugins/chief-of-staff" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

3. Desktop app: restart it, open the Plugins directory, choose your marketplace and install Chief of Staff.
   Codex CLI: run the command below (if you kept an existing file, use its `name` after the `@`), then start a new session.

```
codex plugin add chief-of-staff@my-plugins
```

Do not run `codex plugin marketplace add GutenGroup/chief-of-staff` for this: the repository's marketplace lists the
Claude Code plugins, not the ChatGPT edition.

### Workspace upload (workspace owners and admins)

In ChatGPT on the web, where the option is available: Admin console, select the workspace, **Plugins**, **Add**,
**Upload plugin**, and choose the ZIP from [chatgpt/dist](chatgpt/dist). You need upload permission; on Enterprise it is
off by default.

### Only the three tools (custom MCP server, ChatGPT on the web)

**Plugins**, plus button, **Add custom MCP server**. Enter a name and the URL below, set authentication to match a server
with no sign-in, accept the risk warning, then **Create as a plugin**. OpenAI's help article describes this for Business,
Enterprise and Edu, and for Pro with read/fetch permissions; it does not mention Free or Plus. This adds no role
instructions.

```
https://guten.group/api/cos-mcp/
```

Sources: [Package your plugin](https://developers.openai.com/plugins/build/plugins),
[Plugins](https://learn.chatgpt.com/docs/plugins),
[Plugins in ChatGPT](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt),
[Custom MCP servers](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt).

## Why it isn't in the Claude or OpenAI directories

We keep Chief of Staff autonomous on purpose, to make Claude and ChatGPT better coworkers for people.

Anthropic's plugin directory refused v1.7.1 by automatic policy check, for reasons that include:

- it pushes, sends and acts without asking before each step
- it runs in a no-prompts (bypass) mode
- it lets other sessions' and people's messages steer a session

Its directory policy also limits reading chat history.

OpenAI has not refused it. An older version (1.5.6) is in their review. We have not submitted the autonomous version,
and we are holding it back from both directories until they accept it as it is. We will list it then.

We chose what we think is right over a downgraded version with a badge. It pushes limits, and that means some mistakes.

**[Install from GitHub](#install)** · **[ChatGPT edition](#chatgpt-edition)**

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
