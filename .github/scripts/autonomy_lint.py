#!/usr/bin/env python3
"""Fail the build when the old broad escalation phrases come back (docs/AUTONOMY.md: only legal, money and big steps reach the owner).

Scans tracked files under skills/, agents/, templates/, docs/, chatgpt/ and README.md. Prints file:line and
exits 1 on a hit. docs/AUTONOMY.md may quote the old phrases only if a line carries the marker `autonomy-lint: ignore`.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIRS = ("skills/", "agents/", "templates/", "docs/", "chatgpt/")
BANNED = [
    ("old escalation list", re.compile(r"approvals,\s*money,\s*outward sends,\s*people", re.I)),
    ("old verify rule", re.compile(r"always verify until", re.I)),
    ("old fallback", re.compile(r"with no rule,?\s*ask", re.I)),
]
HARD_STOP = re.compile(r"hard[- ]stop|never (decide|answer|do)|owner'?s? (call|only)", re.I)
CRED = re.compile(r"\bcredentials?\b", re.I)
WORKER_NEEDS_OWNER = re.compile(r"needs-owner\s*:")


def tracked():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.SubprocessError):
        out = [os.path.relpath(os.path.join(dp, f), ROOT) for dp, _, fs in os.walk(ROOT) for f in fs]
    return [f for f in out if f and (f.startswith(DIRS) or f == "README.md") and f.endswith((".md", ".txt", ".yaml", ".yml", ".json"))]


def main():
    bad = []
    for rel in tracked():
        try:
            lines = open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(lines, 1):
            if "autonomy-lint: ignore" in line:
                continue
            for name, rx in BANNED:
                if rx.search(line):
                    bad.append("%s:%d: %s: %s" % (rel, n, name, line.strip()[:100]))
            if HARD_STOP.search(line) and CRED.search(line):
                bad.append("%s:%d: credentials listed as a hard stop: %s" % (rel, n, line.strip()[:100]))
            if rel.startswith("agents/") and WORKER_NEEDS_OWNER.search(line):
                bad.append("%s:%d: a worker reports needs-owner (workers use needs-coo): %s" % (rel, n, line.strip()[:100]))
    for b in bad:
        print(b)
    if bad:
        print("autonomy_lint: %d problem(s)" % len(bad))
        return 1
    print("autonomy_lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
