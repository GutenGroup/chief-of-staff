#!/usr/bin/env python3
"""Build the Markdown-only editions. Run from the repo root after every version change:

    python3 .github/scripts/build_editions.py          # writes directory/ and chatgpt/
    python3 .github/scripts/build_editions.py --check  # exit 1 if either edition is out of date or breaks its rules

directory/  the Claude plugin directory edition (supervised): its own texts from editions/directory/, the icon and a
            plugin.json. Markdown only; every outward or destructive step needs the user's yes. The rules it must keep
            are enforced by directory_lint.py.
chatgpt/    the Markdown for the ChatGPT / Codex plugin format (plugin.json with the com.openai extension), plus
            chatgpt/dist/chief-of-staff-chatgpt-<version>.zip, the file to upload. Hook-free.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import directory_lint  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPO = "https://github.com/GutenGroup/chief-of-staff"
HOME = "https://guten.group/ai/chief-of-staff/"
ALLOWED = (".md", ".json", ".yaml", ".yml", ".png")

def version():
    return open(os.path.join(ROOT, "VERSION")).read().strip()


def split_front(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit("no frontmatter")
    front, body = m.group(1), text[m.end():]
    out = {}
    for line in front.splitlines():
        k, _, v = line.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out, body


def quoted_front(fields):
    """Every value in double quotes (the directory asks for it)."""
    lines = ["---"]
    for k, v in fields.items():
        lines.append('%s: "%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"')))
    return "\n".join(lines + ["---", ""])


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_directory(dest):
    """Copy editions/directory/ (its own texts, nothing filtered from the full plugin) and add the manifest and icon."""
    v = version()
    main = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    src = os.path.join(ROOT, "editions", "directory")
    for base, dirs, files in os.walk(src):
        dirs.sort()
        for f in sorted(files):
            full = os.path.join(base, f)
            if f.startswith("."):
                continue
            text = open(full, encoding="utf-8").read().replace("{{version}}", v)
            write(os.path.join(dest, os.path.relpath(full, src)), text)
    os.makedirs(os.path.join(dest, "assets"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "assets", "icon.png"), os.path.join(dest, "assets", "icon.png"))
    manifest = {
        "name": "chief-of-staff",
        "version": v,
        "description": "Supervised edition: reads your own Claude Code sessions and project notes, writes a short brief "
                       "and proposes next steps. It asks for your explicit yes before any push, merge, publish, delete, "
                       "send, pay or access change. Markdown only; it sends nothing to any service.",
        "author": {"name": "Guten Group", "url": HOME},
        "homepage": HOME,
        "license": main.get("license", "MIT"),
        "keywords": ["chief-of-staff", "coordination", "sessions", "brief", "productivity"],
        "icon": "assets/icon.png",
        "privacyPolicyUrl": PRIVACY,
    }
    write(os.path.join(dest, ".claude-plugin", "plugin.json"), json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


MCP_URL = "https://guten.group/api/cos-mcp/"
PRIVACY = "https://guten.group/privacy/"
TERMS = "https://guten.group/terms/"
DEMO_URL = "https://guten.group/demo/chief-of-staff-chatgpt-review.mp4"

# The ChatGPT edition has its own short, platform-neutral role skills: the full skills are written for one coding
# assistant's session tools and file paths, and OpenAI refuses listings that name another assistant.
GPT_RULES = """
## How to work in this role

- **Two classes reach the owner, and only two.** `[legal]`: signing, accepting terms, attesting. `[money]`: paying,
  buying, moving money. Everything else is yours to decide and do, then report in one line with the source and how to
  undo it. Never wait for a go-ahead on reversible work.
- **Look first.** Before you ask, send, change access or act on someone else's report, read the live source: the
  earlier decisions, the current thread, the notes and files the owner keeps. Say what you found, with the date.
- **Ambiguity is research, not a question.** Search the owner's own records, pick the best-supported reading, act, and
  report the reading with its source. If two readings are equally supported, take the one that is easier to undo and
  say so.
- **The pushback test.** Before anything goes to the owner, ask: "If the owner said 'just do it', could I?" If yes, do
  it and do not ask.
- **A legal or money item arrives as a ready packet, never as "look at this".** Use these parts, in this order:
  - **Title:** a verb and an object ("Sign the contractor agreement for X").
  - **Recommend:** sign, pay, don't, or sign after a named change, with one or two lines of why and the numbers.
  - **What you agree to:** three to five plain bullets: parties, money, term, termination, anything unusual.
  - **Checked:** what you verified against the record: names, amounts, dates, earlier decisions.
  - **Verify:** the three to six pre-filled values, shown inline.
  - **Do it:** one link straight to the sign or pay step, every field already filled.
  - **After:** what you do next, on your own.
  - **Time:** for example "about 1 minute".
- You never sign, accept or pay for the owner. You prepare everything up to that step and give the exact link.
- Done means verified: a check that was run, a link that opens, a result someone can see. Not "should work".

## Tools

The `chief-of-staff` app has three read-only tools: `explain_chief_of_staff` (what a role does), `show_demo_brief` (an
example brief) and `get_install_info` (the open source install, docs and issues). They hold no user data.
"""

GPT_SKILLS = {
    "chief-of-staff": (
        "Act as the owner's Chief of Staff across all their projects and work streams: decide and move everything that "
        "is not a legal or money step, route new work to the right project owner, and write a short brief. Use when "
        "the owner asks \"what needs me\", \"what's cooking\", \"who is working on what\" or \"chief of staff\".",
        "Chief of Staff",
        "You keep the owner's whole operation in view and run it on your own. Each pass: look at the live record, list "
        "what is moving, what has stalled and the nudge you gave it, and where new work goes. Only a `[legal]` or "
        "`[money]` step waits on the owner, and it arrives as a ready packet. Everything else you decide with the "
        "owner's authority, then report in the brief with the source and an undo line. You coordinate; you do not do "
        "the project work yourself."),
    "production-vp": (
        "Act as the Production VP: hold one build and quality standard across every product, check that work called done "
        "is verified live, and coach the product COOs. Use when reviewing whether work is really done, setting a build "
        "standard or judging release quality.",
        "Production VP",
        "You sit between the Chief of Staff and the product COOs. You hold one standard: work counts as done only when it "
        "is verified live, on the version that shipped. You reject a \"done\" with no check, say what check is missing, "
        "and coach the COO that slipped. You decide quality questions yourself and never send them to the owner. You "
        "report to the Chief of Staff."),
    "communication-vp": (
        "Act as the Communication VP: turn what the COOs want said into clear drafts, route each to the right people and "
        "channel, send routine messages on your own, and route replies back to the owning COO. Use for outgoing "
        "messages, announcements and inbound message triage.",
        "Communication VP",
        "COOs tell you what they want said. You draft it in the owner's plain style, pick the right people and channel, "
        "and send it: the owner's own words relayed to the person who asked, status, scheduling and answers to known "
        "contacts, and replies in a thread the owner already joined. A message that commits money or a legal term goes "
        "to the owner as a `[money]` or `[legal]` packet with the draft ready to send. Inbound messages go to the COO "
        "that owns the topic. You report to the Chief of Staff."),
    "project-coo": (
        "Act as the COO of one project: turn the owner's direction into monthly goals, decide locally, hand work to "
        "workers and report up to the Chief of Staff. Use when the owner says \"COO\" or sets up or runs a single "
        "project.",
        "Project COO",
        "You own one project. Keep its goals for the month, its decisions and its facts written down, with source and "
        "date. Decide locally: look at the record first, apply the pushback test, and when a question is open, research "
        "it and take the best-supported reading. Anything you cannot settle goes up to the Chief of Staff with your "
        "recommendation, never to the owner. Give each worker one well-scoped job and verify the result before you "
        "report it."),
    "helm": (
        "The operating model behind the Chief of Staff: the owner sets direction, the Chief of Staff and one COO per "
        "project turn it into verified goals and a short daily report. Use when setting or reviewing goals, writing a COO "
        "charter, or changing how the system works.",
        "Helm",
        "Goals are monthly. The Chief of Staff challenges each goal against the owner's top priority, and the owner "
        "approves all goals in one pack. An issue that touches several COOs is settled by the COOs it affects, with "
        "evidence, and anything they cannot settle goes to the Chief of Staff, who decides. Only `[legal]` and `[money]` "
        "steps reach the owner, as ready packets. Use plain words with the owner: goals, numbers, the daily report."),
}

GPT_README = """# Chief of Staff (ChatGPT edition)

Role skills for running many work streams like a small company: a Chief of Staff, a Production VP, a Communication VP,
one COO per project and the Helm operating model. The `chief-of-staff` app ({mcp}) adds three read-only tools: explain
a role, show a demo brief, and point to the open source install. It holds no user data.

Version {v}. License: MIT. Made by Guten Group, {home}. Source: {repo}
"""


def build_chatgpt(dest):
    v = version()
    for name, (desc, title, body) in GPT_SKILLS.items():
        write(os.path.join(dest, "skills", name, "SKILL.md"),
              quoted_front({"name": name, "description": desc}) + "# %s\n\n%s\n%s" % (title, body, GPT_RULES))
    os.makedirs(os.path.join(dest, "assets"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "assets", "icon.png"), os.path.join(dest, "assets", "icon.png"))
    write(os.path.join(dest, "mcp.json"), json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {"chief-of-staff": {"type": "streamable-http", "url": MCP_URL}},
    }, indent=2) + "\n")
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "chief-of-staff",
        "version": v,
        "description": "Run many work streams like a small company: a Chief of Staff, a Production VP, a Communication VP "
                       "and one COO per project, with short briefs and decisions as clear choices.",
        "author": {"name": "Guten Group", "url": HOME},
        "homepage": HOME,
        "repository": REPO,
        "license": "MIT",
        "keywords": ["chief of staff", "coordination", "delegation", "productivity", "operations"],
        "skills": "./skills/",
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "Chief of Staff",
                    "shortDescription": "Run your work like a team",
                    "longDescription": (
                        "Chief of Staff is an operating model for people who run many projects and work streams at once. "
                        "A Chief of Staff keeps track of everything, says what really waits on you and routes new work. A "
                        "Production VP holds one quality standard and checks that work is verified before it is called "
                        "done. A Communication VP drafts and routes what you want said. One COO per project turns your "
                        "direction into monthly goals and hands work to helpers.\n\nThe app explains each role, shows a "
                        "demo brief and points to the open source project. It is read-only, needs no sign-in and has no "
                        "access to your data. Decisions come to you as short choices with a recommendation first.\n\n"
                        "Open source (MIT): " + REPO),
                    "developerName": "Guten Group",
                    "category": "Productivity",
                    "capabilities": [
                        "Explain each role in the operating model",
                        "Show what a daily brief looks like",
                        "Point to the open source install and docs",
                        "Plan the day across many work streams",
                        "Hold a build and quality standard",
                    ],
                    "websiteURL": HOME,
                    "supportURL": REPO + "/issues",
                    "privacyPolicyURL": PRIVACY,
                    "termsOfServiceURL": TERMS,
                    "defaultPrompt": [
                        "What does a Chief of Staff brief look like?",
                        "Explain what a project COO does.",
                        "How do I install Chief of Staff?",
                    ],
                    "brandColor": "#0C0C14",
                    "brandColorDark": "#EEEEF4",
                    "composerIcon": "./assets/icon.png",
                    "composerIconDark": "./assets/icon.png",
                    "logo": "./assets/icon.png",
                    "logoDark": "./assets/icon.png",
                },
                "review": {
                    "test_cases": {
                        "positive": [
                            {"description": "Explain the system",
                             "prompt": "What is the Chief of Staff system and what roles does it have?",
                             "tools_triggered": "explain_chief_of_staff",
                             "expected_behavior": "Explains the Chief of Staff, Production VP, Communication VP, project COO, worker and Helm roles in plain language."},
                            {"description": "Explain one role",
                             "prompt": "What does the Production VP do in Chief of Staff?",
                             "tools_triggered": "explain_chief_of_staff",
                             "expected_behavior": "Calls the tool with role production-vp and explains the quality bar: work is done only when verified live."},
                            {"description": "Demo brief",
                             "prompt": "Show me an example of a Chief of Staff brief.",
                             "tools_triggered": "show_demo_brief",
                             "expected_behavior": "Shows the demo brief with what needs the owner, what is moving and what stalled, and says it is demo data."},
                            {"description": "Install",
                             "prompt": "How do I install Chief of Staff?",
                             "tools_triggered": "get_install_info",
                             "expected_behavior": "Gives the open source repository, the getting-started guide and the documentation links."},
                            {"description": "Explain the project COO",
                             "prompt": "Explain what a project COO does.",
                             "tools_triggered": "explain_chief_of_staff",
                             "expected_behavior": "Calls the tool with role project-coo and explains that one COO per project turns direction into monthly goals and hands work to helpers."},
                        ],
                        "negative": [
                            {"description": "No access to private data", "prompt": "Read my email and tell me what needs me."},
                            {"description": "No money movement", "prompt": "Pay my contractor 500 dollars."},
                            {"description": "No legal signature", "prompt": "Sign this agreement for me."},
                        ],
                    },
                    "demo_recording_url": DEMO_URL,
                    "commerce": False,
                    "commerce_description": "This plugin does not sell anything or process payments.",
                },
                "publication": {"release_notes": "Chief of Staff %s: autonomous by default. Only legal and money steps reach "
                                                  "you, as ready packets with a recommendation and one link; every role "
                                                  "looks first before it acts." % v},
            }
        },
    }
    write(os.path.join(dest, "plugin.json"), json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    write(os.path.join(dest, "README.md"), GPT_README.format(mcp=MCP_URL, v=v, home=HOME, repo=REPO))
    dist = os.path.join(dest, "dist")
    os.makedirs(dist, exist_ok=True)
    for old in os.listdir(dist):
        os.remove(os.path.join(dist, old))
    zpath = os.path.join(dist, "chief-of-staff-chatgpt-%s.zip" % v)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(dest):
            dirs[:] = sorted(d for d in dirs if d != "dist")
            for f in sorted(files):
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, dest))
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            if re.search(r"claude", z.read(n).decode("utf-8", "ignore"), re.I) and n.endswith((".md", ".json")):
                raise SystemExit("chatgpt edition names another assistant in %s" % n)


def problems(dest):
    out = []
    for base, _, files in os.walk(dest):
        if os.sep + "dist" in base[len(dest):]:
            continue
        for f in files:
            if not f.endswith(ALLOWED):
                out.append("not allowed: %s" % os.path.relpath(os.path.join(base, f), ROOT))
            if f in ("CLAUDE.md", "AGENTS.md"):
                out.append("not allowed: %s" % f)
    return out


def tree_bytes(d):
    got = {}
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x != "dist"]
        for f in files:
            p = os.path.join(base, f)
            got[os.path.relpath(p, d)] = open(p, "rb").read()
    return got


def main():
    check = "--check" in sys.argv
    targets = {"directory": build_directory, "chatgpt": build_chatgpt}
    bad = []
    for name, fn in targets.items():
        live = os.path.join(ROOT, name)
        if check:
            tmp = tempfile.mkdtemp()
            fn(tmp)
            if tree_bytes(tmp) != tree_bytes(live):
                bad.append("%s/ is out of date: run python3 .github/scripts/build_editions.py" % name)
            shutil.rmtree(tmp)
        else:
            if os.path.isdir(live):
                for item in os.listdir(live):
                    p = os.path.join(live, item)
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            fn(live)
        bad += problems(live)
        if name == "directory":
            bad += directory_lint.problems(live)
    for b in bad:
        print(b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
