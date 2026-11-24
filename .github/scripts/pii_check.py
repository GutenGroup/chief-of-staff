#!/usr/bin/env python3
"""Refuse a release that carries private data.

Patterns: the generic ones below, plus one regex per line from the DENY_PATTERNS environment variable (a repository
secret, so the private word list itself is never published). A line starting with "cs " is case-sensitive. Exact
strings in .github/pii-allow.txt are removed from a line before it is tested. Exit 1 on any hit.
"""
import os
import re
import sys

GENERIC = [
    r"[a-z0-9._%+-]+@[a-z0-9.-]+\.(com|group|tech|net|org|io)",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"cs \bAKIA[0-9A-Z]{16}\b",
    r"cs \b(sk|pk|rk)_(live|test)_[0-9a-zA-Z]{16,}",
    r"cs \bgh[pousr]_[A-Za-z0-9]{30,}",
    r"cs \bxox[abpr]-[A-Za-z0-9-]{10,}",
    r"local_[0-9a-f]{6,}",
    r"/Users/[a-z][a-z0-9._-]+/",
]
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
SKIP_FILES = {".github/pii-allow.txt", ".github/scripts/pii_check.py"}


def main(root):
    pats = GENERIC + [l.strip() for l in os.environ.get("DENY_PATTERNS", "").splitlines()
                      if l.strip() and not l.lstrip().startswith("#")]
    compiled = []
    for p in pats:
        cs = p.startswith("cs ")
        compiled.append((p, re.compile(p[3:] if cs else p, 0 if cs else re.I)))
    allow_file = os.path.join(root, ".github", "pii-allow.txt")
    allow = [l.rstrip("\n") for l in open(allow_file)] if os.path.exists(allow_file) else []
    allow = [a for a in allow if a.strip() and not a.startswith("#")]
    hits = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            path = os.path.join(d, f)
            rel = os.path.relpath(path, root)
            if rel in SKIP_FILES:
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                rest = line
                for a in allow:
                    rest = rest.replace(a, "")
                for i, (p, rx) in enumerate(compiled):
                    if rx.search(rest):
                        hits += 1
                        # never print the private pattern itself, only its number
                        print(f"PRIVATE DATA {rel}:{n} (pattern {i + 1})")
    print(f"pii check: {hits} hit(s), {len(pats)} patterns ({len(pats) - len(GENERIC)} from DENY_PATTERNS)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
