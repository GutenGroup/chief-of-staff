#!/usr/bin/env python3
"""comms.py - the Communication VP's helper: who gets what, on which channel, and what may go out without asking.

The Communication VP handles all of the owner's communication. COOs never message people directly: they queue a
request here and the VP drafts, routes, sends (or asks the owner) and logs it.

Files (all plain markdown the owner can edit):
  <data>/Context/Communication_VP/comms/CHANNELS.md     channels:    - <id> | <type> | <address> | <what goes here>
  <data>/Context/Communication_VP/comms/CONTACTS.md     contacts:    - <name> | <channel id> | <what they get>
  <data>/Context/Communication_VP/comms/PERMISSIONS.md  learned send authority, one line per owner instruction
  <fleet>/comms/outbox/  queued requests from COOs       <fleet>/comms/sent/  handled requests
  <fleet>/comms/LOG.md   one line per message sent, held or received

Trust ramp (can-send). Kinds: relay, status, scheduling, answer, reply, money, legal, access, other.
  relay                       SEND   the owner's own words, relayed to the person who asked
  reply                       SEND   a thread the owner already engaged in
  status, scheduling, answer  SEND   when the target is listed in CONTACTS.md or CHANNELS.md, else COS
  money                       OWNER  [money]: an owner-ready packet with the draft ready to send in one click
  legal                       OWNER  [legal]: the same packet
  access                      COS    held until the verbatim order is found in the record
  other / unknown             COS    the Chief of Staff researches and decides
An explicit `allow` line (SEND) or `verify` line (ASK) in PERMISSIONS.md wins over the ramp, except that money and
legal can never become SEND: they always go to the owner.

Channel types: google_chat, botreeve (both through MCP tools named in CHANNELS.md), folder (built in: a shared folder).

Commands
  comms.py init                                  create the three files (never overwrites) and the queue folders
  comms.py queue --from <Role> --to <target> [--kind K] [--channel C] "<what to say>"
                                                 a COO asks the VP to send something; prints the request file
  comms.py outbox                                pending requests, oldest first
  comms.py done <request> --sent|--held ["<note>"]
                                                 close a request: move it to sent/ and log it
  comms.py can-send <target> [--kind K]          SEND, OWNER or COS (the trust ramp below; an explicit line wins)
  comms.py allow <target> [--kind K] ["<why>"]   the owner said: send to this target without asking
                                                 (refused for kind money and legal: those always go to the owner)
  comms.py verify <target> [--kind K] ["<why>"]  the owner said: always ask first for this target (prints ASK)
  comms.py permissions                           the learned rules, newest last
  comms.py channels                              the configured channels
  comms.py signature                             the line every message ends with (comms_signature in the config)
  comms.py draft --to <target> [--kind K] < brief
                                                 run the owner's drafter (comms_drafter in the config) on the brief;
                                                 with no drafter it prints DRAFT-WITH-OWN-MODEL and exits 3
  comms.py folder-send <channel id> <file>       deliver a message file to a folder channel
  comms.py folder-read <channel id>              list messages in a folder channel not read yet (marks them read)
  comms.py log <sent|held|received> <channel> <target> "<summary>"
"""
import datetime
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import cosconfig as C  # noqa: E402

FOLDER = "Communication_VP"
CFG_DIR = os.path.join(C.ROOT, "Context", FOLDER, "comms")
Q = os.path.join(C.FLEET, "comms")
DEFAULT_SIGNATURE = "Written and drafted by {owner}'s Communication VP."

TEMPLATES = {
    "CHANNELS.md": """# Channels
<!--
One line per channel the Communication VP may use:
  - <id> | <type> | <address> | <what goes here>
Types: google_chat (a space), botreeve (a group), folder (a shared folder path).
Example:
  - team-chat | google_chat | spaces/AAAA1234 | updates for the dev team
  - family | botreeve | Family | personal plans and logistics
  - handoff | folder | ~/Shared/handoff | files and notes for the assistant

MCP tools for each type (the names your Claude Code shows; edit to match your connectors):
  - tools | google_chat | list=<tool> read=<tool> post=<tool>
  - tools | botreeve | list=<tool> create=<tool> read=<tool> post=<tool>
-->
""",
    "CONTACTS.md": """# Contacts
<!--
Who gets what, and where:
  - <name> | <channel id> | <what they get>
Example:
  - Sam | team-chat | release notes and anything that needs a developer
  - Board | handoff | the monthly numbers only
-->
""",
    "PERMISSIONS.md": """# Send permissions (learned)
<!--
Written by `comms.py allow` and `comms.py verify` when the owner says "send without approval" or "always verify".
  - send | <target> | <kind or *> | since <date> | <why>
  - verify | <target> | <kind or *> | since <date> | <why>
The most specific line wins (target and kind before target only before *), and the newest line wins a tie.
Explicit lines win over the trust ramp (see `comms.py` help). With no line the ramp decides: SEND, OWNER or COS.
money and legal are never SEND, whatever this file says.
-->
""",
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rows(name):
    try:
        text = open(os.path.join(CFG_DIR, name), encoding="utf-8").read()
    except OSError:
        return []
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return [[c.strip() for c in l[2:].split("|")] for l in text.splitlines() if l.startswith("- ")]


def norm(s):
    return " ".join(str(s).lower().split())


def cmd_init():
    os.makedirs(CFG_DIR, exist_ok=True)
    made = []
    for name, text in TEMPLATES.items():
        p = os.path.join(CFG_DIR, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            made.append(name)
    for sub in ("outbox", "sent"):
        os.makedirs(os.path.join(Q, sub), exist_ok=True)
    print("comms: %s\ncreated: %d file(s)%s" % (CFG_DIR, len(made), (" (%s)" % ", ".join(made)) if made else ""))
    return 0


KINDS = ("relay", "status", "scheduling", "answer", "reply", "money", "legal", "access", "other")
OWNER_KINDS = {"money": "[money]", "legal": "[legal]"}


def known_target(target):
    """True when the target is listed in CONTACTS.md (name) or CHANNELS.md (id)."""
    t = norm(target)
    return bool(t) and any(r and norm(r[0]) == t for n in ("CONTACTS.md", "CHANNELS.md") for r in rows(n))


def explicit(target, kind="*"):
    """SEND or ASK from a matching PERMISSIONS.md line, or None when no line matches."""
    best, best_rank = None, -1
    for i, r in enumerate(rows("PERMISSIONS.md")):
        if len(r) < 3 or r[0] not in ("send", "verify"):
            continue
        t, k = norm(r[1]), norm(r[2] or "*")
        if t not in (norm(target), "*") or k not in (norm(kind), "*"):
            continue
        rank = (2 if t != "*" else 0) + (1 if k != "*" else 0)
        if rank >= best_rank:
            best, best_rank = ("SEND" if r[0] == "send" else "ASK"), rank
    return best


def ramp(target, kind="*"):
    """(verdict, note): SEND, OWNER, COS, or ASK (an explicit verify line)."""
    k = norm(kind or "*")
    k = "other" if k in ("*", "") or k not in KINDS else k
    if k in OWNER_KINDS:
        return "OWNER", ("%s must be an owner-ready packet with the draft ready to send in one click; never auto-sent"
                         % OWNER_KINDS[k]), OWNER_KINDS[k]
    rule = explicit(target, kind or "*")
    if rule:
        return rule, "", ""
    if k in ("relay", "reply"):
        return "SEND", "", ""
    if k in ("status", "scheduling", "answer"):
        if known_target(target):
            return "SEND", "", ""
        return "COS", "target is not in CONTACTS.md or CHANNELS.md: the Chief of Staff decides", ""
    if k == "access":
        return "COS", "held until the verbatim order is found in the record", ""
    return "COS", "the Chief of Staff researches and decides", ""


def decide(target, kind="*"):
    return ramp(target, kind)[0]


def add_permission(verb, target, kind, why):
    if verb == "send" and norm(kind or "*") in OWNER_KINDS:
        print("refused: %s always goes to the owner as a packet and can never be auto-sent" % kind)
        return 2
    if not target:
        print("usage: comms.py %s <target> [--kind K] [\"<why>\"]" % ("allow" if verb == "send" else "verify"))
        return 2
    cmd_init_quiet()
    with open(os.path.join(CFG_DIR, "PERMISSIONS.md"), "a", encoding="utf-8") as f:
        f.write("- %s | %s | %s | since %s | %s\n" % (verb, target, kind or "*", now()[:10], why or "owner instruction"))
    print("%s: %s (%s) -> %s" % ("allow" if verb == "send" else "verify", target, kind or "*", ramp(target, kind or "*")[0]))
    return 0


def cmd_init_quiet():
    os.makedirs(CFG_DIR, exist_ok=True)
    for name, text in TEMPLATES.items():
        p = os.path.join(CFG_DIR, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
    for sub in ("outbox", "sent"):
        os.makedirs(os.path.join(Q, sub), exist_ok=True)


def signature():
    s = C.CONFIG.get("comms_signature")
    s = DEFAULT_SIGNATURE if s in (None, "", []) else str(s)
    return s.replace("{owner}", C.OWNER if C.OWNER != "you" else "the owner")


def log(status, channel, target, summary):
    os.makedirs(Q, exist_ok=True)
    with open(os.path.join(Q, "LOG.md"), "a", encoding="utf-8") as f:
        f.write("- %s | %s | %s | %s | %s\n" % (now(), status, channel or "-", target or "-", " ".join(summary.split())))


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        val = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
        return val
    return default


def cmd_queue(args):
    frm, to = opt(args, "--from"), opt(args, "--to")
    kind, channel = opt(args, "--kind", "*"), opt(args, "--channel", "")
    text = " ".join(args).strip()
    if not frm or not to or not text:
        print('usage: comms.py queue --from <Role> --to <target> [--kind K] [--channel C] "<what to say>"')
        return 2
    cmd_init_quiet()
    stamp = now().replace(":", "-")
    name = "%s-%s.md" % (stamp, re.sub(r"[^\w-]+", "_", frm)[:40])
    p = os.path.join(Q, "outbox", name)
    n = 1
    while os.path.exists(p):
        n += 1
        p = os.path.join(Q, "outbox", name[:-3] + "-%d.md" % n)
    with open(p, "w", encoding="utf-8") as f:
        f.write("from: %s\nto: %s\nkind: %s\nchannel: %s\nqueued: %s\n\n%s\n" % (frm, to, kind, channel, now(), text))
    print(p)
    return 0


def cmd_outbox():
    d = os.path.join(Q, "outbox")
    files = sorted(f for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []
    for f in files:
        head = dict(l.split(": ", 1) for l in open(os.path.join(d, f), encoding="utf-8").read().split("\n\n")[0].splitlines()
                    if ": " in l)
        print("%s  from %s to %s (%s) -> %s" % (f, head.get("from", "?"), head.get("to", "?"), head.get("kind", "*"),
                                                decide(head.get("to", ""), head.get("kind", "*"))))
    print("%d pending" % len(files))
    return 0


def cmd_done(args):
    status = "sent" if "--sent" in args else "held" if "--held" in args else ""
    args = [a for a in args if a not in ("--sent", "--held")]
    if not args or not status:
        print('usage: comms.py done <request> --sent|--held ["<note>"]')
        return 2
    src = args[0] if os.path.isabs(args[0]) else os.path.join(Q, "outbox", os.path.basename(args[0]))
    if not os.path.isfile(src):
        print("no such request: %s" % args[0])
        return 2
    text = open(src, encoding="utf-8").read()
    head = dict(l.split(": ", 1) for l in text.split("\n\n")[0].splitlines() if ": " in l)
    note = " ".join(args[1:])
    os.makedirs(os.path.join(Q, "sent"), exist_ok=True)
    with open(os.path.join(Q, "sent", os.path.basename(src)), "w", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n\n%s: %s %s\n" % (status, now(), note))
    os.remove(src)
    log(status, head.get("channel"), head.get("to"), note or "request from %s" % head.get("from", "?"))
    print("%s: %s" % (status, os.path.basename(src)))
    return 0


def channel(cid):
    for r in rows("CHANNELS.md"):
        if len(r) >= 3 and r[0] == cid and r[0] != "tools":
            return r
    return None


def cmd_folder_send(args):
    if len(args) < 2 or not os.path.isfile(args[1]):
        print("usage: comms.py folder-send <channel id> <file>")
        return 2
    ch = channel(args[0])
    if not ch or ch[1] != "folder":
        print("no folder channel named %s in CHANNELS.md" % args[0])
        return 2
    dest = os.path.expanduser(ch[2])
    os.makedirs(dest, exist_ok=True)
    out = os.path.join(dest, "%s-%s" % (now().replace(":", "-"), os.path.basename(args[1])))
    shutil.copyfile(args[1], out)
    log("sent", args[0], ch[2], os.path.basename(args[1]))
    print(out)
    return 0


def cmd_folder_read(args):
    ch = channel(args[0]) if args else None
    if not ch or ch[1] != "folder":
        print("usage: comms.py folder-read <folder channel id>")
        return 2
    src = os.path.expanduser(ch[2])
    seen_p = os.path.join(Q, ".read-%s" % re.sub(r"[^\w-]+", "_", args[0]))
    seen = set(open(seen_p, encoding="utf-8").read().split("\n")) if os.path.exists(seen_p) else set()
    new = sorted(f for f in os.listdir(src) if not f.startswith(".") and f not in seen) if os.path.isdir(src) else []
    for f in new:
        print(os.path.join(src, f))
        log("received", args[0], "-", f)
    os.makedirs(Q, exist_ok=True)
    with open(seen_p, "a", encoding="utf-8") as fh:
        fh.write("".join(f + "\n" for f in new))
    return 0


def cmd_draft(args):
    to, kind = opt(args, "--to", ""), opt(args, "--kind", "*")
    brief = sys.stdin.read()
    drafter = C.CONFIG.get("comms_drafter")
    if not drafter:
        print("DRAFT-WITH-OWN-MODEL")
        return 3
    env = dict(os.environ, COMMS_TO=to, COMMS_KIND=kind, COMMS_SIGNATURE=signature())
    r = subprocess.run(str(drafter), shell=True, input=brief, capture_output=True, text=True, env=env, timeout=900)
    if r.returncode != 0 or not r.stdout.strip():
        sys.stderr.write("drafter failed (exit %d): %s\n" % (r.returncode, r.stderr.strip()[:500]))
        return 1
    print(r.stdout.rstrip())
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], list(argv[1:])
    if cmd == "init":
        return cmd_init()
    if cmd == "queue":
        return cmd_queue(rest)
    if cmd == "outbox":
        return cmd_outbox()
    if cmd == "done":
        return cmd_done(rest)
    if cmd in ("allow", "verify"):
        kind = opt(rest, "--kind", "*")
        return add_permission("send" if cmd == "allow" else "verify", rest[0] if rest else "", kind, " ".join(rest[1:]))
    if cmd == "can-send":
        kind = opt(rest, "--kind", "*")
        if not rest:
            print("usage: comms.py can-send <target> [--kind K]")
            return 2
        verdict, note, tag = ramp(rest[0], kind)
        print(verdict + (" " + tag if tag else ""))
        if note:
            print(note)
        return 0
    if cmd == "permissions":
        for r in rows("PERMISSIONS.md"):
            print(" | ".join(r))
        return 0
    if cmd == "channels":
        for r in rows("CHANNELS.md"):
            print(" | ".join(r))
        return 0
    if cmd == "signature":
        print(signature())
        return 0
    if cmd == "draft":
        return cmd_draft(rest)
    if cmd == "folder-send":
        return cmd_folder_send(rest)
    if cmd == "folder-read":
        return cmd_folder_read(rest)
    if cmd == "log" and len(rest) >= 4:
        log(rest[0], rest[1], rest[2], " ".join(rest[3:]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
