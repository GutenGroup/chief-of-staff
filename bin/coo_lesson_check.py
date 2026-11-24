#!/usr/bin/env python3
"""coo_lesson_check.py — prove a COO does not repeat a logged correction.

Reads the CHECK lines in Context/<Project>/coo/LESSONS*.md and scans the
COO's own report file (<fleet>/coo-reports/<Project>.md) entry by entry. An entry dated at or
after a check's `since` that matches the check's `forbid` regex is a violation.

CHECK line format (one per line, in the persona):
  - CHECK <kebab-id> | since <YYYY-MM-DD[THH:MMZ]> | forbid /<python regex>/ | <why>

Usage:
  coo_lesson_check.py <Project> [--as-of ISO] [--since-override ISO] [--entries N]
  coo_lesson_check.py --all
Exit 0 = clean, 1 = violations, 2 = bad input. `--as-of` ignores entries newer than that time
(replays history); `--since-override` replaces every check's `since` (shows what a check
would have caught before the correction existed).
"""
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from cosconfig import ROOT, FLEET, CONFIG  # noqa: E402

# Words that name the owner in a lesson or an ask: "owner", plus the configured first name.
_NAME = (CONFIG.get("owner_name") or "").strip()
OWNER_RX = r"\bowner\b" + (r"|\b" + re.escape(_NAME) + r"\b" if _NAME else "")
CHECK_RE = re.compile(
    r"^\s*-\s*CHECK\s+(?P<id>[\w.-]+)\s*\|\s*since\s+(?P<since>\S+)\s*\|\s*forbid\s+/(?P<rx>.+)/\s*\|\s*(?P<why>.*)$"
)
# Entries before this stamp predate the persona system: counted as history, never failed.
BASELINE = os.environ.get("COO_BASELINE", "")
HEAD_RE = re.compile(r"^(?:##\s+|[-*]\s+)(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):?(\d{2}))?")

# Discovery (replaces the hand-written PROJECTS dict): every Context/**/coo/PERSONA.md is one COO, every
# PERSONA_Growth.md the matching product-growth COO. key -> (folder under Context/, report basename).
# FOLDER_KEY maps a nested folder to a key when the folder name alone is not the key you want.
FOLDER_KEY = {}
FIVE = ("PERSONA", "PLAYBOOK", "KNOWLEDGE", "LESSONS", "SCORECARD")
PRIVATE_CFG = os.path.expanduser("~/.claude/coo-private.json")


def discover(root=None):
    base = os.path.join(root or ROOT, "Context")
    out = {}
    for suffix in ("", "_Growth"):
        for p in sorted(glob.glob(os.path.join(base, "**", "coo", f"PERSONA{suffix}.md"), recursive=True)):
            folder = os.path.relpath(os.path.dirname(os.path.dirname(p)), base)
            key = FOLDER_KEY.get(folder, os.path.basename(folder)) + suffix
            out[key] = (folder, key)
    return out


def private_coos():
    """Local-only COOs from ~/.claude/coo-private.json: {"coos": [{"key": "...", "root": "/abs/folder holding coo/", "report": "/abs/report.md"}]}.
    Their names and content never go into git, shared folders, reports or logs: callers print aggregates only."""
    try:
        import json
        cfg = json.load(open(PRIVATE_CFG))
    except (OSError, ValueError):
        return []
    return [c for c in cfg.get("coos", []) if c.get("key") and c.get("root")]


PROJECTS = discover()


def coo_dir(key):
    folder, _ = PROJECTS[key]
    return os.path.join(ROOT, "Context", folder, "coo")


def five_files(key):
    """The five files of one COO; product-growth COOs use *_Growth.md."""
    suf = "_Growth" if key.endswith("_Growth") else ""
    return {n: os.path.join(coo_dir(key), f"{n}{suf}.md") for n in FIVE}


def missing_files(key):
    return [os.path.relpath(p, ROOT) for n, p in five_files(key).items() if not os.path.isfile(p)]


def unonboarded():
    """COOs that exist (a COO_CHARTER.md) but have no coo/PERSONA.md: they must fail the check."""
    have = {v[0] for v in PROJECTS.values()}
    out = []
    for c in sorted(glob.glob(os.path.join(ROOT, "Context", "**", "COO_CHARTER.md"), recursive=True)):
        folder = os.path.relpath(os.path.dirname(c), os.path.join(ROOT, "Context"))
        covered = folder in have or any(folder.startswith(h + os.sep) for h in have)   # a growth charter sits under its parent's COO folder
        if not covered:
            out.append(folder)
    return out


def norm(ts):
    """'2026-11-21' / '2026-11-21T13:30Z' -> sortable 'YYYY-MM-DDTHH:MM'."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):?(\d{2}))?", ts)
    if not m:
        return None
    return f"{m.group(1)}T{m.group(2) or '00'}:{m.group(3) or '00'}"


def persona_files(folder, key):
    """CHECK lines live in Context/<folder>/coo/LESSONS*.md (and PERSONA*.md for old layouts)."""
    base = os.path.join(ROOT, "Context", folder, "coo")
    growth = key.endswith("_Growth")
    out = []
    for p in sorted(glob.glob(os.path.join(base, "*.md"))):
        name = os.path.basename(p)
        if not (name.startswith("LESSONS") or name.startswith("PERSONA")):
            continue
        if name.endswith("_Growth.md") == growth:
            out.append(p)
    return out


def load_checks(paths):
    checks = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if "CHECK " not in line:
                    continue
                m = CHECK_RE.match(line.rstrip("\n"))
                if not m:
                    if line.lstrip().startswith("- CHECK"):
                        print(f"BAD CHECK LINE {p}:{n}: {line.strip()}", file=sys.stderr)
                        sys.exit(2)
                    continue
                try:
                    rx = re.compile(m["rx"])
                except re.error as e:
                    print(f"BAD REGEX {p}:{n}: {e}", file=sys.stderr)
                    sys.exit(2)
                checks.append((m["id"], norm(m["since"]), rx, m["why"], p))
    return checks


def entries(report_path):
    """Yield (stamp, heading, body) for each dated entry: a `## <date>` heading or a `- <date> | ...` line."""
    cur = None
    with open(report_path, encoding="utf-8") as f:
        for line in f:
            h = HEAD_RE.match(line)
            if h:
                if cur:
                    yield cur
                stamp = norm(f"{h.group(1)}T{h.group(2) or '00'}:{h.group(3) or '00'}")
                cur = [stamp, line.strip(), []]
            elif cur is not None:
                cur[2].append(line)
    if cur:
        yield cur


def run(key, as_of=None, since_override=None, limit=0):
    folder, rname = PROJECTS[key]
    miss = missing_files(key)
    if miss:
        print(f"{key}: INCOMPLETE, missing {', '.join(miss)} (run: python3 ~/.claude/chief-of-staff/bin/coo_onboard.py {key.replace('_Growth','')}{' --growth' if key.endswith('_Growth') else ''})")
        return 1
    pf = persona_files(folder, key)
    if not pf:
        print(f"{key}: no persona file")
        return 2
    checks = load_checks(pf)
    if not checks:
        print(f"{key}: NO CHECK LINES (a COO role is not started until LESSONS has at least one CHECK line; add one for a correction that is visible as text)")
        return 1
    report = os.path.join(FLEET, "coo-reports", f"{rname}.md")
    if not os.path.exists(report):
        print(f"{key}: no report file")
        return 2
    viol = 0
    hist = 0
    scanned = 0
    for stamp, head, body in entries(report):
        if limit and scanned >= limit:
            break
        if as_of and stamp > as_of:
            continue
        scanned += 1
        text = head + "\n" + "".join(body)
        for cid, since, rx, why, src in checks:
            lo = norm(since_override) if since_override else since
            if stamp < lo:
                continue
            m = rx.search(text)
            if m:
                if stamp < BASELINE and not since_override:
                    hist += 1
                    continue
                viol += 1
                print(f"VIOLATION {key} [{cid}] entry {stamp}: ...{m.group(0)[:90]}... ({why})")
    print(f"{key}: {len(checks)} checks, {scanned} entries scanned, {viol} violations, {hist} historical hits before {BASELINE or 'the baseline'} (trend only)")
    return 1 if viol else 0


def run_private(c, as_of=None):
    """One local-only COO. Returns (checks, entries, violations). Nothing about it is printed except aggregates by the caller."""
    import glob as _g
    d = os.path.join(c["root"], "coo")
    need = [os.path.join(d, f"{n}.md") for n in FIVE]
    if any(not os.path.isfile(x) for x in need):
        return 0, 0, 1                         # incomplete files count as a failure
    checks = load_checks([x for x in _g.glob(os.path.join(d, "*.md")) if os.path.basename(x).startswith(("LESSONS", "PERSONA"))])
    viol = scanned = 0
    rep = c.get("report")
    if rep and os.path.isfile(rep):
        for stamp, head, body in entries(rep):
            if as_of and stamp > as_of:
                continue
            scanned += 1
            text = head + "\n" + "".join(body)
            for cid, since, rx, why, src in checks:
                if stamp >= since and stamp >= BASELINE and rx.search(text):
                    viol += 1
    return len(checks), scanned, viol


def main(argv):
    as_of = since = None
    limit = 0
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--as-of":
            as_of = norm(argv[i + 1]); i += 2
        elif a == "--since-override":
            since = argv[i + 1]; i += 2
        elif a == "--entries":
            limit = int(argv[i + 1]); i += 2
        else:
            args.append(a); i += 1
    if not args:
        print(__doc__)
        return 2
    allrun = args[0] == "--all"
    keys = list(PROJECTS) if allrun else args
    rc = 0
    print("[structural pre-check: CHECK lines vs report entries; the real knowledge test is coo_knowledge_test.py --real]" if allrun else "", end="" if not allrun else "\n")
    for k in keys:
        if k not in PROJECTS:
            print(f"unknown project {k}; known: {', '.join(PROJECTS)}")
            return 2
        rc = max(rc, run(k, as_of, since, limit))
    if allrun:
        for folder in unonboarded():
            print(f"{folder}: NOT ONBOARDED (COO_CHARTER.md but no coo/PERSONA.md) (run: python3 ~/.claude/chief-of-staff/bin/coo_onboard.py {os.path.basename(folder)})")
            rc = 1
        priv = private_coos()
        if priv:                                  # aggregate only: no names, no content
            tot = [run_private(c, as_of) for c in priv]
            v = sum(t[2] for t in tot)
            print(f"private COOs: {len(priv)} checked locally, {v} violations (aggregate only)")
            rc = max(rc, 1 if v else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
