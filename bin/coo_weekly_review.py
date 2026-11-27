#!/usr/bin/env python3
"""coo_weekly_review.py: the Sunday COO training review (one row per COO in SCORECARD section 2).

  coo_weekly_review.py [--week YYYY-Www] [--dry-run] [--knowledge]

For every discovered COO it measures the four CoS review inputs:
  1 repeated corrections  = LESSONS CHECK violations in the report entries of the last 7 days
  2 self-decidable asks   = needs-owner lines in the last 7 days that restate a closed decision (PERSONA section 3)
  3 stale knowledge       = KNOWLEDGE section 3 stale/missing lines + facts whose source file is gone
  4 goals                 = GOALS.md done-checks ticked / total
and writes the row, plus a coaching note (SCORECARD section 3) when input 1 or 2 is non-zero. Idempotent per ISO week:
the date cell carries the week tag, a second run the same week writes nothing. Findings go to <fleet>/coo-reports/_coo-training-<week>.md
for the CoS. Nothing messages the owner. Private COOs (~/.claude/coo-private.json) are scanned for aggregates only, printed locally.
--knowledge also runs the real knowledge test for every COO (the monthly lane) and appends to SCORECARD section 4.
"""
import datetime
import io
import os
import re
import contextlib
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import coo_lesson_check as L  # noqa: E402

ROOT = L.ROOT
FLEET = L.FLEET
ASK = re.compile(r"needs[- ]owner|ask(ing)? (the )?(%s)|(%s) to decide|waiting on (the )?(%s)" % ((L.OWNER_RX,) * 3), re.I)
WORD = re.compile(r"[a-z0-9][a-z0-9'\-]{3,}")


def words(t):
    return set(WORD.findall(t.lower()))


def section(text, n):
    m = re.search(rf"^##\s*{n}\.[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def recent_entries(report, days=7, today=None):
    cut = (today or datetime.date.today()) - datetime.timedelta(days=days)
    out = []
    for stamp, head, body in L.entries(report):
        if stamp[:10] >= cut.isoformat():
            out.append((stamp, head + "\n" + "".join(body)))
    return out


def measure(paths, report, as_of=None):
    persona = open(paths["PERSONA"], encoding="utf-8").read()
    know = open(paths["KNOWLEDGE"], encoding="utf-8").read()
    ents = recent_entries(report) if os.path.isfile(report) else []
    # 1 repeated corrections
    checks = L.load_checks([paths["PERSONA"]] + ([paths["LESSONS"]] if os.path.isfile(paths["LESSONS"]) else []))
    viol = []
    for stamp, text in ents:
        for cid, since, rx, why, src in checks:
            if stamp >= since and stamp >= L.BASELINE and rx.search(text):
                viol.append(f"{cid}@{stamp[:10]}")
    # 2 self-decidable asks
    closed = [words(l) for l in section(persona, 3).splitlines() if l.strip().startswith("-") and "NOT YET ESTABLISHED" not in l]
    selfask = []
    for stamp, text in ents:
        for line in text.splitlines():
            if ASK.search(line):
                w = words(line)
                if any(len(w & c) >= 4 for c in closed):
                    selfask.append(stamp[:10])
    # 3 stale knowledge
    stale = [l for l in section(know, 3).splitlines() if l.strip().startswith("-") and "none" not in l.lower()[:12]]
    gone = 0
    for l in section(know, 2).splitlines():
        m = re.search(r"\[source:\s*([^\]]+?)\s*\]", l)
        if m and not os.path.isfile(os.path.join(ROOT, m.group(1))):
            gone += 1
    # 4 goals
    goals = "n/a"
    for g in (os.path.join(os.path.dirname(os.path.dirname(paths["PERSONA"])), "GOALS.md"),
              os.path.join(os.path.dirname(paths["PERSONA"]), "GOALS.md")):
        if os.path.isfile(g):
            t = open(g, encoding="utf-8").read()
            st = [x.strip().lower() for x in re.findall(r"^- Status:\s*(.+)$", t, re.M)]
            n = len(re.findall(r"^##\s*Goal", t, re.M))
            if n:
                cnt = {k: sum(1 for x in st if x.startswith(k)) for k in ("done", "on track", "at risk", "off track")}
                goals = f"{n} goals: " + ", ".join(f"{v} {k}" for k, v in cnt.items() if v)
            else:
                goals = "no goals listed"
            break
    return {"viol": viol, "selfask": selfask, "stale": len(stale) + gone, "goals": goals, "entries": len(ents)}


def ledger_metrics(days=7, path=None, today=None):
    """Autonomy metrics from the ask ledger (hooks/autonomy_common.py writes it): owner asks outside legal and money
    (ask-gate asks that were untagged, setup interview excluded, plus stop-guard blocks), pushbacks and their rate
    over owner prompts, decided items (cos decided)."""
    import json
    path = path or os.path.join(os.path.expanduser("~"), ".claude", "needs-input", "ask-ledger.jsonl")
    cut = ((today or datetime.date.today()) - datetime.timedelta(days=days)).isoformat()
    asks = push = prompts = decided = 0
    try:
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    except (OSError, ValueError):
        rows = []
    for r in rows:
        if not isinstance(r, dict) or str(r.get("ts", ""))[:10] < cut:
            continue
        t, d = r.get("type"), r.get("decision")
        if t == "ask" and r.get("tagged") is False and r.get("reason") not in ("setup", "interview", "no-questions"):
            asks += 1
        elif t == "stop" and d == "block":
            asks += 1
        elif t == "pushback":
            push += 1
            prompts += 1
        elif t == "prompt":
            prompts += 1
        elif t == "decided":
            decided += 1
    rate = f"{100 * push / prompts:.0f}%" if prompts else "n/a"
    return [f"- owner asks outside legal/money: {asks} in {days} days ({asks / days:.1f}/day)",
            f"- pushbacks: {push} of {prompts} owner prompts ({rate})",
            f"- decided items logged: {decided}"]


def insert_row(path, week, row, note):
    txt = open(path, encoding="utf-8").read()
    if f"({week})" in section(txt, 2):
        return False
    m = re.search(r"(^##\s*2\.[^\n]*\n(?:.*\n)*?)(^\|[- |]+\|\s*\n)", txt, re.M)
    if not m:
        return False
    # append row after the last table line of section 2
    sec = re.search(r"^##\s*2\.[^\n]*\n.*?(?=^##\s|\Z)", txt, re.M | re.S)
    body = sec.group(0).rstrip("\n") + "\n" + row + "\n\n"
    txt = txt[:sec.start()] + body + txt[sec.end():]
    if note:
        s3 = re.search(r"^##\s*3\.[^\n]*\n.*?(?=^##\s|\Z)", txt, re.M | re.S)
        if s3:
            b3 = s3.group(0).rstrip("\n") + "\n" + note + "\n\n"
            txt = txt[:s3.start()] + b3 + txt[s3.end():]
        else:
            txt = txt.rstrip("\n") + "\n\n## 3. Coaching notes\n" + note + "\n"
    open(path, "w", encoding="utf-8").write(txt)
    return True


def main(argv):
    dry = "--dry-run" in argv
    y, w, _ = datetime.date.today().isocalendar()
    week = argv[argv.index("--week") + 1] if "--week" in argv else f"{y}-W{w:02d}"
    today = datetime.date.today().isoformat()
    lines, rc = [], 0
    for key in L.PROJECTS:
        miss = L.missing_files(key)
        if miss:
            lines.append(f"- {key}: INCOMPLETE, missing {', '.join(miss)}")
            rc = 1
            continue
        paths = L.five_files(key)
        if not L.load_checks([paths["PERSONA"]] + ([paths["LESSONS"]] if os.path.isfile(paths["LESSONS"]) else [])):
            lines.append(f"- {key}: NO CHECK LINES (role not started until LESSONS has at least one)")
            rc = 1
        report = os.path.join(FLEET, "coo-reports", f"{L.PROJECTS[key][1]}.md")
        m = measure(paths, report)
        note = ""
        if m["viol"] or m["selfask"]:
            bits = []
            if m["viol"]:
                bits.append(f"repeated correction(s) {', '.join(m['viol'][:4])}: re-read PERSONA section 4 before the next report")
            if m["selfask"]:
                bits.append(f"{len(m['selfask'])} ask(s) a recorded decision already answered ({', '.join(sorted(set(m['selfask']))[:3])}): decide, do not ask")
            note = f"- {today} ({week}): " + "; ".join(bits)
        row = f"| {today} ({week}) | {len(m['viol'])} | {len(m['selfask'])} | {m['stale']} | {m['goals']} | {'yes' if note else 'no'} |"
        wrote = False if dry else insert_row(paths["SCORECARD"], week, row, note)
        lines.append(f"- {key}: {row.strip('| ')}" + ("" if (wrote or dry) else " (already reviewed this week)"))
        if m["viol"] or m["selfask"]:
            rc = max(rc, 0)
    if os.path.exists(L.PRIVATE_CFG):
        n = len(L.private_coos())
        print(f"private COOs configured: {n} (reviewed locally, aggregate only, nothing written to git or shared folders)")
    out = f"# COO training review {week}\n\nGenerated {today} by coo_weekly_review.py. One line per COO: date | repeated corrections | self-decidable asks | stale knowledge | goals | coaching note.\n\n" + "\n".join(lines) + "\n"
    out += "\n## Autonomy (ask ledger, last 7 days)\n" + "\n".join(ledger_metrics()) + "\n"
    if dry:
        print(out)
    else:
        p = os.path.join(FLEET, "coo-reports", f"_coo-training-{week}.md")
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").write(out)
        else:  # a COO added after the week's first run (new role) is appended, never duplicated
            have = open(p, encoding="utf-8").read()
            add = [l for l in lines if l.split(":")[0] not in have]
            if add:
                open(p, "a", encoding="utf-8").write("\n".join(add) + "\n")
        print(out)
    if "--knowledge" in argv:
        ks = os.path.join(HERE, "coo_knowledge_test.py")
        period = f"{y}-{datetime.date.today().month:02d}"
        a = [sys.executable, ks, "--all", "--real", "--period", period] + ([] if dry else ["--write"])
        subprocess.run(a)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
