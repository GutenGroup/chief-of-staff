# The Communication VP

Every install has a Communication VP next to the Production VP. It handles all of your communication: what goes out,
to whom, on which channel, and what comes in and where it goes. Your COOs never message people themselves; they hand
the Communication VP what should be said, and it drafts, routes, sends or asks you, and logs.

```
you
 └─ Chief of Staff
     ├─ Production VP        build quality across the product COOs
     ├─ Communication VP     every message in and out, for every role
     └─ COOs ── workers
```

Session title: `CoS · Communication VP` (Opus, medium). It reports to the Chief of Staff.

## You decide who gets what

Its configuration is three plain files in `<data>/Context/Communication_VP/comms/`:

| File | What you write | Example line |
|---|---|---|
| `CHANNELS.md` | the channels it may use, and what goes in each | `- dev | google_chat | spaces/AAAA1234 | updates for the dev team` |
| `CONTACTS.md` | the people, their channel, and what they get | `- Sam | dev | release notes and anything that needs a developer` |
| `PERMISSIONS.md` | what may go out without asking (it writes this as you tell it) | `- send | dev | * | since 2026-11-24 | send freely` |

The Chief of Staff fills the first two with you in one dialog when it starts the Communication VP. Change them any time,
by editing the files or by telling the Communication VP.

## Channels

At launch: **Google Chat** spaces, **botreeve** groups and a **shared folder**, all behind one connector interface: each
channel type can list, read and post (botreeve can also create a group). The MCP tool names for each type are lines in
`CHANNELS.md`, so another connector is a config change.

**botreeve is the bridge.** You name the botreeve groups it reads and writes and what goes in each, and it can set up a
new group when you ask for one. Because everyone's Chief of Staff can join the same groups, botreeve is how people and
teams connect: each person keeps their own Chief of Staff and their own rules, and their Communication VPs talk to each
other in shared groups.

## Send authority is learned, not fixed

Out of the box it asks you before sending (a dialog with the draft: Send / Edit / Hold). Then it learns:

- You say **"send without approval"** for a person, a group or a kind of message: from then on it sends those.
- You say **"always verify"**: from then on it always asks.

Each instruction is one line in `PERMISSIONS.md`, so you can read and change what it may do. The most specific line
wins, and a newer line beats an older one. Money, legal commitments, credentials and anything irreversible for people
outside your team always come to you, whatever the permissions say.

Every message ends with a signature line, by default "Written and drafted by <your name>'s Communication VP.", so
readers know a system wrote it. Change it with `comms_signature` in `~/.claude/cos-config.yaml`.

## Drafting is pluggable

By default the Communication VP drafts with its own model and learns your register from what you edit. If you have your
own drafting tool, plug it in: set `comms_drafter` in `~/.claude/cos-config.yaml` to a command that reads the brief on
stdin and prints the draft (it also gets `COMMS_TO`, `COMMS_KIND` and `COMMS_SIGNATURE` in its environment). Describe how
to use it in your overlay (`communication-vp.md`, see [Add your own rules](OVERLAY.md)).

## How the other roles use it

```bash
python3 ~/.claude/chief-of-staff/bin/comms.py queue --from Acme --to Sam --kind update "Release 2 is live; the import bug is fixed"
```

(Every COO's skill already says to do this.) Inbound messages on your
channels are read each pass and routed to the COO that owns the topic.

## Commands

```bash
python3 ~/.claude/chief-of-staff/bin/comms.py outbox        # what is waiting to go out
python3 ~/.claude/chief-of-staff/bin/comms.py permissions   # what it may send without asking
python3 ~/.claude/chief-of-staff/bin/comms.py allow Sam "send freely"
python3 ~/.claude/chief-of-staff/bin/comms.py verify Board "always check with me"
python3 ~/.claude/chief-of-staff/bin/comms.py channels
```

The log of everything sent, held and received is `<data>/fleet/comms/LOG.md`.
