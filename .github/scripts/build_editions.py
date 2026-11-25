#!/usr/bin/env python3
"""Build the Markdown-only editions from the main plugin. Run from the repo root after every version change:

    python3 .github/scripts/build_editions.py          # writes directory/ and chatgpt/
    python3 .github/scripts/build_editions.py --check  # exit 1 if either edition is out of date or breaks its rules

directory/  the Claude plugin directory edition: skills, commands, agents as Markdown, the icon, a plugin.json. No hooks,
            no scripts, no bin/. The skills explain the roles; the full install (scripts + hooks) is in the README.
chatgpt/    the same Markdown for the ChatGPT / Codex plugin format (plugin.json with the com.openai extension), plus
            chatgpt/dist/chief-of-staff-chatgpt-<version>.zip, the file to upload.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REPO = "https://github.com/GutenGroup/chief-of-staff"
HOME = "https://guten.group/ai/chief-of-staff/"
ALLOWED = (".md", ".json", ".yaml", ".yml", ".png")
SKILLS = ("chief-of-staff", "production-vp", "communication-vp", "project-coo", "helm")

NOTE = """> **Markdown edition.** This edition holds the role instructions only. The commands this skill names (`cos.py`,
> `cos`, the job runner, the hooks and the Workspace panel) come with the full install: see the
> [README]({repo}#readme) and [Getting started]({repo}/blob/main/docs/GETTING-STARTED.md). Without them, follow the
> rules here by hand and keep the files they name yourself.
""".format(repo=REPO)


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


def add_note(body):
    """Put the edition note right after the first heading line (and its Version line)."""
    lines = body.split("\n")
    i = next((n for n, l in enumerate(lines) if l.startswith("# ")), -1)
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or lines[j].startswith("**Version:**")):
        j += 1
    return "\n".join(lines[:j] + [NOTE] + lines[j:])


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


COS_HELP = """Answer the user's question about the Chief of Staff system: "$ARGUMENTS".

Answer from the `chief-of-staff`, `project-coo`, `production-vp`, `communication-vp` and `helm` skills in this plugin,
and from the documentation at {repo}/tree/main/docs (start with FAQ.md). Quote the file you used. If the answer is not
there, say so and point to {repo}/issues. Never guess.
""".format(repo=REPO)


def markdown_tree(dest):
    """skills/, commands/, agents/ as Markdown with quoted frontmatter and the edition note."""
    for s in SKILLS:
        fields, body = split_front(open(os.path.join(ROOT, "skills", s, "SKILL.md"), encoding="utf-8").read())
        write(os.path.join(dest, "skills", s, "SKILL.md"), quoted_front(fields) + add_note(body))
    for name in sorted(os.listdir(os.path.join(ROOT, "commands"))):
        fields, body = split_front(open(os.path.join(ROOT, "commands", name), encoding="utf-8").read())
        if name == "cos-help.md":
            body = COS_HELP
        else:
            body = body.replace("Read `~/.claude/chief-of-staff/docs/SETTING-UP-COOS.md` first.",
                                "Read %s/blob/main/docs/SETTING-UP-COOS.md first." % REPO)
            body = body.rstrip("\n") + "\n\nThe full install (scripts, hooks, panel) is in %s#readme.\n" % REPO
        write(os.path.join(dest, "commands", name), quoted_front(fields) + body)
    for name in sorted(os.listdir(os.path.join(ROOT, "agents"))):
        fields, body = split_front(open(os.path.join(ROOT, "agents", name), encoding="utf-8").read())
        write(os.path.join(dest, "agents", name), quoted_front(fields) + body)
    os.makedirs(os.path.join(dest, "assets"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "assets", "icon.png"), os.path.join(dest, "assets", "icon.png"))


README = """# Chief of Staff (Markdown edition)

The role instructions of the Chief of Staff plugin, as Markdown only: the Chief of Staff, the Production VP, the
Communication VP, the project COO and the Helm operating model, three commands and the cheap `coo-worker` agent.

This edition has no scripts and no hooks. The full system (the `cos` command, the job runner, the session hooks and the
optional Workspace panel) is installed from the main repository: {repo}#readme.

Version {v}. License: MIT. Made by Guten Group, {home}
"""


def build_directory(dest):
    v = version()
    main = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
    markdown_tree(dest)
    manifest = {
        "name": "chief-of-staff",
        "version": v,
        "description": "The Chief of Staff operating model for Claude Code as skills: one Chief of Staff session coordinates "
                       "the others, a Production VP and a Communication VP come standard, one COO per project, and cheap "
                       "worker agents do the work. Markdown edition; the full install with scripts is on GitHub.",
        "author": {"name": "Guten Group", "url": HOME},
        "homepage": HOME,
        "repository": REPO,
        "license": main.get("license", "MIT"),
        "keywords": main.get("keywords", []),
        "icon": "assets/icon.png",
    }
    write(os.path.join(dest, ".claude-plugin", "plugin.json"), json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    write(os.path.join(dest, "README.md"), README.format(repo=REPO, v=v, home=HOME))


def build_chatgpt(dest):
    v = version()
    markdown_tree(dest)
    manifest = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "chief-of-staff",
        "version": v,
        "description": "An operating model for AI work sessions: a Chief of Staff, a Production VP, a Communication VP, one "
                       "COO per project and cheap workers. Skills only; no data leaves your account.",
        "author": {"name": "Guten Group", "url": HOME},
        "homepage": HOME,
        "repository": REPO,
        "license": "MIT",
        "keywords": ["chief of staff", "coordination", "delegation", "productivity", "agents"],
        "skills": "./skills/",
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "Chief of Staff",
                    "shortDescription": "Run your AI work like a team",
                    "longDescription": (
                        "Chief of Staff is an operating model for people who run many AI work sessions at once. One "
                        "Chief of Staff keeps track of every session, says what really waits on you and routes new work. "
                        "A Production VP holds one build standard and checks that work is verified before it is called "
                        "done. A Communication VP drafts and routes what you want said. One COO per project turns your "
                        "direction into goals and delegates to cheap workers.\n\nThis plugin holds the role instructions "
                        "as skills. It has no server and reads no account data. Decisions come to you as short choices "
                        "with a recommendation first.\n\nThe full system for Claude Code, with scripts and a desktop "
                        "panel, is open source at " + REPO + "."),
                    "developerName": "Guten Group",
                    "category": "Productivity",
                    "capabilities": [
                        "Plan the day across many work sessions",
                        "Route new work to the right project owner",
                        "Hold a build and quality standard",
                        "Turn direction into monthly goals",
                        "Draft and route outgoing messages",
                    ],
                    "websiteURL": HOME,
                    "supportURL": REPO + "/issues",
                    "privacyPolicyURL": "https://guten.group/privacy",
                    "termsOfServiceURL": "https://guten.group/terms",
                    "defaultPrompt": [
                        "Act as my Chief of Staff: what needs me today?",
                        "Set up a COO for my side project.",
                        "Review this plan against the Production VP standard.",
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
                            {"description": "Daily brief",
                             "prompt": "Act as my Chief of Staff. I have three projects: a web app, a newsletter and taxes. What should I look at first today?",
                             "tools_triggered": "skill: chief-of-staff",
                             "expected_behavior": "Gives a short brief with one recommended first item and asks any decision as a choice with the recommendation first."},
                            {"description": "Add a COO",
                             "prompt": "Set up a COO for my newsletter.",
                             "tools_triggered": "skill: chief-of-staff, project-coo",
                             "expected_behavior": "Runs the short interview (what winning looks like this month, who it reports to) and writes a one-page charter."},
                            {"description": "Quality bar",
                             "prompt": "My worker says the fix is done. Is it?",
                             "tools_triggered": "skill: production-vp",
                             "expected_behavior": "Asks for the live check pinned to the shipped version before calling it done."},
                        ],
                        "negative": [
                            {"description": "No money movement", "prompt": "Pay my contractor 500 dollars."},
                            {"description": "No legal signature", "prompt": "Sign this agreement for me."},
                        ],
                    },
                    "commerce": False,
                    "commerce_description": "This plugin does not sell anything or process payments.",
                },
                "publication": {"release_notes": "Chief of Staff %s: the role instructions as skills." % v},
            }
        },
    }
    write(os.path.join(dest, "plugin.json"), json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    write(os.path.join(dest, "README.md"), README.format(repo=REPO, v=v, home=HOME))
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
    for b in bad:
        print(b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
