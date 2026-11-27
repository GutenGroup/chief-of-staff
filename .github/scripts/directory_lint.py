#!/usr/bin/env python3
"""Fail the build when the plugin directory edition (directory/) breaks the directory policy: forbidden phrases, files
that are not Markdown / the manifest / the icon, a role that relays other people's messages, or a skill or agent without
the explicit-yes rule. Used by build_editions.py --check, the tests and CI. Run: python3 .github/scripts/directory_lint.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILES = re.compile(r"^(README\.md|\.claude-plugin/plugin\.json|assets/icon\.png|"
                   r"skills/(chief-of-staff|production-vp|project-coo|helm)/SKILL\.md|"
                   r"commands/[a-z-]+\.md|agents/[a-z-]+\.md)$")
FORBIDDEN = [
    ("permission bypass", r"bypass|yolo|full[- ]auto|no[- ]prompts|unattended|dangerously|defaultMode|permission[- ]mode"),
    ("approve everything", r"approve (everything|all)|allow (all|everything)|auto[- ]?approv|up front"),
    ("go ahead without asking", r"without (asking|confirm|a yes|your yes|permission)|(do not|don'?t) ask|just do it|"
                                r"pushback test|ship to prod|autonom|on (its|your) own authority"),
    ("acting as the user", r"owner'?s (word|authority|order)|user'?s authority|on (your|the user'?s|the owner'?s) behalf|"
                           r"your word is|per-send approval|answers? for (the )?(user|owner)"),
    ("message relays", r"communication[- ]vp|\brelay|inbound|webhook|chat (group|room|space)|comms\.py"),
    ("install or download code", r"\binstall|download|\bcurl\b|\bwget\b|git clone|plugin (update|marketplace)|"
                                 r"\bmarketplace\b|\b(npm|npx|pip|pipx|brew)\b|self-update|auto-?update|"
                                 r"github\.com|[\w-]+\.(py|sh|mjs|js|ts)\b"),
    ("access and sign-in", r"sign[- ]?in with|passkey|magic link|keychain|password manager|secret store|"
                           r"\b(add|remove)s? members|create (a )?(key|token|account)"),
    ("timers and self-run loops", r"CronCreate|/loop\b|clear_session|self-clear|\bjev\b|typesafe"),
]
RULE = "explicit yes"
VERBS = ("push", "merge", "publish", "delete", "send", "pay", "access change")


def problems(dest):
    out, seen = [], []
    for base, _, files in os.walk(dest):
        for f in sorted(files):
            full = os.path.join(base, f)
            rel = os.path.relpath(full, dest).replace(os.sep, "/")
            seen.append(rel)
            if not FILES.match(rel):
                out.append("directory/%s: file not allowed in the directory edition" % rel)
                continue
            if rel.endswith(".png"):
                continue
            text = open(full, encoding="utf-8").read()
            for n, line in enumerate(text.splitlines(), 1):
                for name, rx in FORBIDDEN:
                    m = re.search(rx, line, re.I)
                    if m:
                        out.append("directory/%s:%d: %s: '%s'" % (rel, n, name, m.group(0)))
            if rel.startswith(("skills/", "agents/")) or rel in ("README.md", ".claude-plugin/plugin.json"):
                flat = " ".join(text.split()).lower()
                missing = [w for w in (RULE,) + VERBS if w not in flat]
                if missing:
                    out.append("directory/%s: missing the confirm rule (%s)" % (rel, ", ".join(missing)))
    if "README.md" in seen:
        flat = " ".join(open(os.path.join(dest, "README.md"), encoding="utf-8").read().split())
        for need in ("## What it reads", "## What it sends Nothing."):
            if need not in flat:
                out.append("directory/README.md: missing '%s'" % need)
    else:
        out.append("directory/README.md: missing")
    return out


def main():
    bad = problems(os.path.join(ROOT, "directory"))
    for b in bad:
        print(b)
    print("directory_lint: %s" % ("%d problem(s)" % len(bad) if bad else "clean"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
