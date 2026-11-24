#!/usr/bin/env python3
"""coo_onboard.py: build the five training files of a COO from what the project already wrote down.

  coo_onboard.py <Project> [--growth] [--dry-run]

Creates Context/<Project>/coo/{PERSONA,PLAYBOOK,KNOWLEDGE,LESSONS,SCORECARD}.md (growth COO: *_Growth.md)
in the format of the existing COOs (see skill project-coo). Idempotent: a file that exists is never touched,
so it is safe to run before every COO start. Seeded only from real sources: the project's COO_CHARTER.md,
GOALS.md, COO_LESSONS.md, _COO_STATE.md, <fleet>/coo-reports/<Project>.md and the optional Knowledge/<Project>/ folder.
Where a source is missing the file says so and names the first task that fixes it; nothing generic is invented.

Exit 0 = all five files exist afterwards, 2 = bad input.
"""
import datetime
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from coo_lesson_check import ROOT, FLEET, FOLDER_KEY, FIVE, OWNER_RX  # noqa: E402

BULLET = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*\S)\s*$")
DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def sections(text):
    """{heading: [lines]} for '#'-style headings, in order (a pre-heading block is stored under '')."""
    out, cur = {"": []}, ""
    for line in text.splitlines():
        m = re.match(r"^#{1,4}\s+(.*\S)\s*$", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
        else:
            out[cur].append(line)
    return out


def bullets(lines, limit=20, width=260):
    res = []
    for line in lines:
        m = BULLET.match(line)
        if m:
            t = re.sub(r"\s+", " ", m.group(1)).strip()
            res.append(t if len(t) <= width else t[: width - 1].rstrip() + "…")
        elif line.strip() and not res and not line.startswith(("|", "---", "```")):
            t = re.sub(r"\s+", " ", line).strip()
            res.append(t if len(t) <= width else t[: width - 1].rstrip() + "…")
        if len(res) >= limit:
            break
    return res


def pick(secs, rx, limit=14):
    out = []
    for h, lines in secs.items():
        if re.search(rx, h, re.I):
            out += bullets(lines, limit)
    return out[:limit]


def resolve(arg):
    base = os.path.join(ROOT, "Context")
    if os.path.isdir(os.path.join(base, arg)):
        folder = arg
    else:
        inv = {v: k for k, v in FOLDER_KEY.items()}
        folder = inv.get(arg)
        if not folder or not os.path.isdir(os.path.join(base, folder)):
            return None
    return folder, FOLDER_KEY.get(folder, os.path.basename(folder))


def knowledge_pointer(project):
    """Optional knowledge corpus per project: <data_root>/Knowledge/<project>/ (with an optional _SUMMARY.md)."""
    low = project.lower().replace("-", "").replace("_", "")
    corp = os.path.join(ROOT, "Knowledge")
    for d in sorted(glob.glob(os.path.join(corp, "*"))):
        if low in os.path.basename(d).lower().replace("-", "").replace("_", ""):
            rel = os.path.relpath(d, ROOT)
            has = os.path.isfile(os.path.join(d, "_SUMMARY.md"))
            return rel, has
    return None, False


def gather(folder, key, growth):
    base = os.path.join(ROOT, "Context", folder)
    sub = os.path.join(base, "growth") if growth and os.path.isdir(os.path.join(base, "growth")) else base
    name = key + ("_Growth" if growth else "")

    def src(fn):
        for d in (sub, base):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                return p
        return None

    d = {"folder": folder, "key": key, "name": name, "growth": growth, "base": base}
    for fn in ("COO_CHARTER.md", "GOALS.md", "COO_LESSONS.md", "_COO_STATE.md"):
        p = src(fn)
        d[fn] = (os.path.relpath(p, ROOT), read(p)) if p else (None, "")
    rp = os.path.join(FLEET, "coo-reports", name + ".md")
    d["report"] = (os.path.relpath(rp, ROOT), read(rp)) if os.path.isfile(rp) else (None, "")
    d["kdir"] = knowledge_pointer(key)
    return d


def lessons_list(d):
    """Dated lessons of COO_LESSONS.md as (date, text); reads bullet, table-row and heading layouts (the projects differ)."""
    out = []
    lines = d["COO_LESSONS.md"][1].splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*[-*]\s+\**(20\d\d-\d\d-\d\d)\b[^:]{0,40}?:?\s*(.*\S)", line)
        if not m:
            m = re.match(r"^\|\s*(20\d\d-\d\d-\d\d)\s*\|\s*([^|]*\S)\s*\|", line)
        if not m:
            h = re.match(r"^#{2,4}\s+(20\d\d-\d\d-\d\d)\s*(.*\S)?", line)
            if h:
                body = (h.group(2) or "").strip()
                if not body:
                    body = next((x.strip() for x in lines[i + 1:i + 4] if x.strip()), "")
                m = (h.group(1), body)
        if m:
            dt, tx = (m.group(1), m.group(2)) if hasattr(m, "group") else m
            tx = re.sub(r"\s+", " ", tx).strip(" *")
            if tx:
                out.append((dt, tx[:230]))
    return out


def fm(typ, d, ver=1):
    return f"---\ntype: {typ}\nentity: {d['key']}\ntimestamp: {now().strftime('%Y-%m-%dT%H:%M:%SZ')}\nversion: {ver}\n---\n"


def role(d):
    """Display name: 'Production VP' for the VP folder, '<Project> COO' for everything else."""
    n = d['name'].replace('_', ' ')
    return n if n.endswith(" VP") else n + " COO"


def todo(path, what):
    return f"- NOT YET ESTABLISHED: {what}. First task for this COO: create `{path}` (skill helm), then update this file."


# ------------------------------------------------------------------ PERSONA
def persona(d):
    ch_path, ch = d["COO_CHARTER.md"]
    secs = sections(ch)
    L = [fm("coo_persona", d), f"# {role(d)} persona v1\n"]
    owns = pick(secs, r"mission|owns|owned|scope|winning|people and systems|what winning", 12)
    L.append("## 1. Owns")
    if owns:
        L += [f"- {x}" for x in owns]
        L.append(f"- Report file: `coo-reports/{d['name']}.md`; state: `Context/{d['folder']}/_COO_STATE.md`; source: {ch_path}")
    else:
        L.append(todo(f"Context/{d['folder']}/COO_CHARTER.md", "no charter text to quote about what this COO owns"))
    L.append("\n## 2. How I decide")
    dec = pick(secs, r"decision|hard stop|escalat|authority|rights", 14)
    L += [f"- {x}" for x in dec] if dec else [todo(f"Context/{d['folder']}/COO_CHARTER.md", "no decision rights or hard stops written down")]
    L.append("- Asks go only as `needs-owner:` lines in my report file: recommendation first, data, alternatives, after a search of this folder, `DECISIONS.md`, coo-reports and the Knowledge folder (skill project-coo).")
    L.append("\n## 3. What the owner already told me (closed, never re-ask)")
    closed = []
    for x in pick(secs, r"closed|decided|decisions", 16):
        dm = DATE.search(x)
        closed.append(f"- {dm.group(1) if dm else 'date not recorded'} — {x} — source: {ch_path}")
    for dt, tx in lessons_list(d):
        if re.search(OWNER_RX, tx, re.I) and len(closed) < 18:
            closed.append(f"- {dt} — {tx} — source: {d['COO_LESSONS.md'][0]}")
    L += closed if closed else [todo(f"Context/{d['folder']}/COO_LESSONS.md", "no recorded owner decision found in the charter or the lessons log")]
    L.append("\n## 4. Corrections I must not repeat")
    les = lessons_list(d)
    if les:
        for i, (dt, tx) in enumerate(les[:15], 1):
            L.append(f"- R{i} ({dt}, seen 1x): {tx}")
    else:
        L.append("- None logged yet. The first correction goes into `../COO_LESSONS.md` the same turn, and a lesson seen twice is promoted here as R1 (skill project-coo).")
    L.append("\n## 5. Checks (machine-read by coo_lesson_check.py)\n(CHECK lines live in LESSONS.md, machine-read by coo_lesson_check.py)")
    L.append("\n## 6. My skills\n| Skill | Use here |\n|---|---|")
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "skills")
    base_skills = {"project-coo": "COO loop, report format, persona/playbook loop", "helm": "charter and goals format"}
    for s, use in base_skills.items():
        L.append(f"| {s} | {use} |")
    seen = set(base_skills)
    for p in sorted(glob.glob(os.path.join(skills_dir, "*", "SKILL.md"))):
        s = os.path.basename(os.path.dirname(p))
        if s not in seen and re.search(r"\b" + re.escape(s) + r"\b", ch + d["_COO_STATE.md"][1]):
            L.append(f"| {s} | named in this project's charter or state |")
            seen.add(s)
    L.append("- Gaps: none recorded yet; a skill the COO hunts for twice is listed here.")
    L.append("\n## 7. Where my knowledge lives")
    kdir, has = d["kdir"]
    L.append(f"- Knowledge folder: {kdir + (' (has _SUMMARY.md)' if has else ' (no _SUMMARY.md yet)') if kdir else 'none yet (optional: Knowledge/<Project>/ under the data root)'}")
    L.append(f"- Files: `Context/{d['folder']}/` (see KNOWLEDGE.md section 1).")
    L.append(f"- Searches: `grep -rn \"needs-owner\" coo-reports/{d['name']}.md`; `ls Context/{d['folder']}`; `grep -n -i \"{d['key'].split('_')[0].lower()}\" DECISIONS.md`")
    used = [p for p, t in (d["COO_CHARTER.md"], d["GOALS.md"], d["COO_LESSONS.md"], d["_COO_STATE.md"], d["report"]) if p]
    L.append("\n## 8. Promotion log")
    L.append(f"- {now().strftime('%Y-%m-%d')}: persona v1 seeded by coo_onboard.py from {', '.join(used) or 'no source files yet'} ({len(les)} lessons)")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ PLAYBOOK
def playbook(d):
    ch = sections(d["COO_CHARTER.md"][1])
    st = d["_COO_STATE.md"][1]
    L = [fm("coo_playbook", d), f"# {role(d)} playbook v1",
         "This is my own way of working. I edit it myself whenever a pass or a correction teaches me something, and log the edit in section 6. The shared `project-coo` skill holds how every COO works; this file holds only what is specific to this project.\n",
         "## 1. Cadence and per-pass checklist"]
    cad = pick(ch, r"cadence|scorecard|weekly|daily|pass|numbers", 10)
    if cad:
        L += [f"- {x}" for x in cad] + [f"- source: {d['COO_CHARTER.md'][0]}"]
    else:
        L.append(todo(f"Context/{d['folder']}/COO_CHARTER.md", "no cadence or scorecard section in the charter"))
    stl = [x for x in bullets(st.splitlines(), 40) if re.search(r"check|pass|every|daily|weekly|open", x, re.I)][:6]
    if stl:
        L.append(f"- From `_COO_STATE.md`: " + " | ".join(stl[:3]))
    L.append("\n## 2. Standard moves")
    mv = [f"- {tx} (lesson {dt})" for dt, tx in lessons_list(d) if re.search(r"always|never|before|first|must|rule", tx, re.I)][:6]
    L += mv if mv else ["- None recorded yet; moves are added here the first time a correction shows a better way (Edit log, section 6)."]
    L.append("\n## 3. Standing queries")
    L += [f"- `python3 ~/.claude/chief-of-staff/bin/coo_lesson_check.py {d['name']}`",
          f"- `python3 ~/.claude/chief-of-staff/bin/coo_knowledge_test.py {d['name']} --real`",
          f"- `grep -rn \"needs-owner\" coo-reports/{d['name']}.md`", f"- `ls Context/{d['folder']}`"]
    L.append(f"\n## 4. Report format (`coo-reports/{d['name']}.md`, newest on top)")
    L += ["- Header: `## <UTC timestamp from date -u> -- RESULT|CORRECTION|needs-owner: <one-line outcome>`.",
          "- Body: 2-5 bullets: what was read, the fix with commit sha or path, the live verification, what is still open.",
          "- A needs-owner line carries recommendation first, data, alternatives, and says what I searched.",
          "- No pass entry when nothing changed."]
    L.append("\n## 5. Open improvements")
    op = [f"- {x}" for x in pick(sections(st), r"open|next|todo|blocked", 6)]
    L += op if op else ["- None recorded."]
    L.append("\n## 6. Edit log")
    L.append(f"- {now().strftime('%Y-%m-%d')}: playbook v1 seeded by coo_onboard.py")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ KNOWLEDGE
def facts(d):
    """[(text, source_path)] taken verbatim from real files so the knowledge test can verify them."""
    out = []
    ch_path, ch = d["COO_CHARTER.md"]
    secs = sections(ch)
    for x in pick(secs, r"mission|winning|owns|owned", 8):
        out.append((x, ch_path))
    for x in pick(secs, r"closed|decided|decisions|hard stop", 8):
        out.append((x, ch_path))
    gp, gt = d["GOALS.md"]
    for h in re.findall(r"^##\s+(Goal\s*\d+[^\n]*)$", gt, re.M)[:6]:
        out.append((h.strip(), gp))
    for dt, tx in lessons_list(d)[:4]:
        out.append((tx[:200], d["COO_LESSONS.md"][0]))
    seen, res = set(), []
    for t, s in out:
        k = t.lower()
        if k not in seen and s and len(t) > 25:
            seen.add(k)
            res.append((t, s))
    return res[:20]


def verbatim(text, path):
    return re.sub(r"\s+", " ", text).strip().lower() in re.sub(r"\s+", " ", read(os.path.join(ROOT, path))).lower()


def knowledge(d):
    L = [fm("coo_knowledge", d), f"# {role(d)} knowledge index",
         "An index, not a copy. G = the data root.\n", "## 1. Sources", "| Path | Holds | Read when |", "|---|---|---|"]
    for p in sorted(glob.glob(os.path.join(d["base"], "*.md")))[:40]:
        txt = read(p)
        h = re.search(r"^#\s+(.*\S)", txt, re.M)
        L.append(f"| {os.path.relpath(p, ROOT)} | {(h.group(1) if h else os.path.basename(p))[:90]} | {'every session start' if os.path.basename(p) == '_COO_STATE.md' else 'before a decision or ask on this topic'} |")
    rp = d["report"][0] or f"coo-reports/{d['name']}.md"
    L.append(f"| {rp} | my dated results | before reporting |")
    kdir, has = d["kdir"]
    L.append(f"| {kdir or 'Knowledge/'} | {'knowledge folder' + (' with _SUMMARY.md' if has else ', no _SUMMARY.md yet') if kdir else 'no knowledge folder for this project yet (optional)'} | company knowledge questions |")
    L.append("\n## 2. Facts to know cold")
    fl = facts(d)
    L += [f"- {t} [source: {s}]" for t, s in fl] if fl else [todo(f"Context/{d['folder']}/COO_CHARTER.md", "no quotable facts yet (charter, goals and lessons are empty or absent)")]
    L.append("\n## 3. Known stale or missing knowledge")
    gaps = []
    for fn in ("COO_CHARTER.md", "GOALS.md", "COO_LESSONS.md", "_COO_STATE.md"):
        if not d[fn][0]:
            gaps.append(f"- `Context/{d['folder']}/{fn}` does not exist. Fix owed: create it from the project's own history (skill helm).")
    if not d["report"][0]:
        gaps.append(f"- No `coo-reports/{d['name']}.md` yet. Fix owed: the first pass creates it.")
    if not d["kdir"][0]:
        gaps.append("- No Knowledge/<Project>/ folder yet (optional). Create one when the project has reference material worth indexing.")
    L += gaps if gaps else ["- None found at onboarding; updated on the first pass that hunts twice."]
    L.append("\n## 4. Knowledge test")
    L.append("(structural pre-check lines; the real test is `coo_knowledge_test.py <Project> --real`, one model answers from these five files, another grades against the cited source)")
    n = 0
    for t, s in fl:
        if n >= 5:
            break
        if verbatim(t, s):
            n += 1
            lead = " ".join(t.split()[:7])
            L.append(f'- Q{n}: What does {os.path.basename(s)} record as: "{lead}…"? || A: {t[:200]} || SRC: {s} || QUOTE: "{t}"')
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ LESSONS / SCORECARD
def lessons(d):
    return (fm("coo_lessons", d) + f"# {d['name']} COO lessons and checks\n"
            f"Raw dated correction log: ../COO_LESSONS.md. Promoted rules: PERSONA section 4. Below: the machine-checked rules.\n\n"
            "## CHECK lines (format: - CHECK <id> | since <date> | forbid /<regex>/ | <why>)\n"
            f"- CHECK text-question | since {now().strftime('%Y-%m-%d')} | forbid /(?i)\\b(want me to|shall I|should I|let me know if)\\b/ | questions to the owner go up as needs-owner lines with options, never as text\n"
            + (f"- CHECK no-handtyped-timestamp | since {now().strftime('%Y-%m-%d')} | forbid /(?<!\\d)\\d{{2}}:[xX?]{{2}}(?!\\w)/ | timestamps come from `date -u`; a placeholder time like 14:xx was typed by hand\n"
               if d["name"] == "Production_VP" else "")
            + "(the standard starting check; add a line each time a correction is visible as text in a report entry, never invent one for a rule you were not corrected on)\n")


def scorecard(d):
    gp, gt = d["GOALS.md"]
    goals = re.findall(r"^##\s+(Goal\s*\d+[^\n]*)$", gt, re.M)
    L = [fm("coo_scorecard", d), f"# {d['name'].replace('_', ' ')} COO scorecard (graded by the Chief of Staff)\n",
         "## 1. Measures", "| Measure | How measured | Target | Baseline (source) |", "|---|---|---|---|",
         f"| Repeated logged corrections | `python3 ~/.claude/chief-of-staff/bin/coo_lesson_check.py {d['name']}` | 0 | not run yet |",
         f"| Asks to the owner already answered by a recorded decision | needs-owner lines in `coo-reports/{d['name']}.md` against PERSONA section 3 | 0 | not counted yet |",
         f"| Knowledge test | `python3 ~/.claude/chief-of-staff/bin/coo_knowledge_test.py {d['name']} --real` | PASS (every question correct) | not run yet |",
         "| Stale needs-owner items older than 24 h | open lines in the report file with a timestamp older than 24 h | 0 | not counted yet |",
         f"| Goal status per GOALS.md | `{gp or 'Context/<Project>/GOALS.md'}` Status lines | all on track | {len(goals)} goals listed ({gp}); statuses read by the weekly review" if gp else "| Goal status per GOALS.md | GOALS.md Status lines | all on track | GOALS.md does not exist yet |",
         "", "## 2. Weekly review log", "| date | repeated corrections | self-decidable asks | stale knowledge found | goals | coaching note written |", "|---|---|---|---|---|---|", "",
         "## 3. Coaching notes", "", "## 4. Knowledge test log", "| date | engine | score | gaps |", "|---|---|---|---|", ""]
    return "\n".join(L).replace("| Goal status per GOALS.md | `None`", "| Goal status per GOALS.md | `GOALS.md`") + "\n"


BUILD = {"PERSONA": persona, "PLAYBOOK": playbook, "KNOWLEDGE": knowledge, "LESSONS": lessons, "SCORECARD": scorecard}


def onboard(arg, growth=False, dry=False, quiet=False):
    r = resolve(arg)
    if not r:
        print(f"unknown project folder '{arg}' under {ROOT}/Context", file=sys.stderr)
        return 2
    folder, key = r
    d = gather(folder, key, growth)
    cdir = os.path.join(ROOT, "Context", folder, "coo")
    made, kept = [], []
    for n in FIVE:
        fn = f"{n}{'_Growth' if growth else ''}.md"
        path = os.path.join(cdir, fn)
        if os.path.exists(path):
            kept.append(fn)
            continue
        made.append(fn)
        if not dry:
            os.makedirs(cdir, exist_ok=True)
            with open(path, "x", encoding="utf-8") as f:     # 'x': never overwrite, even in a race
                f.write(BUILD[n](d))
    if not quiet:
        print(f"{d['name']}: created {made or 'nothing'}; kept {kept or 'nothing'}{' (dry run)' if dry else ''}")
    return 0


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 1:
        print(__doc__)
        sys.exit(2)
    sys.exit(onboard(a[0], "--growth" in sys.argv, "--dry-run" in sys.argv))
