#!/usr/bin/env python3
"""cos.py - the small command-line helper behind the Chief of Staff skills.

Setup and housekeeping
  cos.py init                       create the data folders and per-project files (never overwrites)
  cos.py add-project <Name> [--reports-to vp|cos]
                                    add a COO: product COOs report to the Production VP (default), IT, admin,
                                    growth and personal COOs to the Chief of Staff (--reports-to cos)
  cos.py list-coos                  the Production VP, the Communication VP and every COO with its report line and onboarding state
  cos.py layout                     print the expected sidebar layout: the Chief of Staff title, the group, every role title
  cos.py sidebar                    write ~/.claude/needs-input/sidebar.json for the Workspace panel
  cos.py precheck "<topic>" [--session ID] [--days 14]
                                    look before any ask, send or access change: no model call; searches DECISIONS.md,
                                    charters, lessons, the overlay, knowledge_sources, recent reports and the comms
                                    log; prints dated hits (newest first) and writes needs-input/precheck/<session>.json
  cos.py autonomy-drill [--model M] [--votes N] [--dry-run]
                                    score the 25 scenarios in tests/autonomy_cases.yaml on a cheap model; writes
                                    needs-input/autonomy-drill.json (--dry-run only validates the case file)
  cos.py decided "<line>" [--session ID]
                                    log one decided item (what, source, undo) to the ask ledger for the weekly review
  cos.py status                     print permission mode, autonomy state, mode, machine, folders, projects and queue counts
  cos.py overlay init               create your private rules overlay in ~/.claude/cos-overlay: one starter file per
                                    skill (never overwrites); sets overlay_dir when it is not set yet (docs/OVERLAY.md)

Learning (every role: the Chief of Staff, the Production VP, each COO)
  cos.py lesson <Role> "<text>" [--check <id> "<regex>"]
                                    record a correction the same turn: a dated lesson in Context/<Role>/COO_LESSONS.md,
                                    a line in <fleet>/lessons.log, and (with --check) a machine-checked CHECK line
  cos.py lessons [N]                the last N lines (default 20) of the fleet lessons log; every role reads it at start
  cos.py learn-due [--now]          run what the training schedule says is due: the weekly review (Sunday, or a missed
                                    week; --now: this week's review today) and the monthly real knowledge test; idempotent, safe every pass
  cos.py savings add <category> <predicted> <measured> [note]
  cos.py savings review             the self-learning cost review: predicted vs measured savings per category

Chief of Staff tick guard (keeps the 30-minute loop and the sidebar ticker from doing double work)
  cos.py tick-check                 SKIP: a full pass finished < 5 min ago and nothing changed; RUN: otherwise
  cos.py tick-peek                  same answer, records nothing (used by the Workspace sidebar)
  cos.py tick-complete              record a finished full pass (call only after a complete pass)

Fleet mode (opt-in; fleet_mode: lead | member in the config, fleet_dir = a folder every machine shares)
  cos.py submit <job.md> [--to M]   validate a job file and queue it in <fleet>/inbox/<M>/ (default: this machine)
  cos.py run-jobs [--all]           run the next queued job (--all: every one) with `claude -p`, cheapest model that fits
  cos.py merge-briefs               front desk: merge every machine's brief into <fleet>/status/fleet-brief.json

Kill switch for run-jobs: touch ~/.claude/cos-jobs-off
"""
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import cosconfig as C  # noqa: E402

HOME = os.path.expanduser("~")
FLAGS = os.path.join(HOME, ".claude", "needs-input")
WINDOW_S = 300
LIFECYCLE = frozenset(("running", "done", "failed", "rejected"))

# Runner classes: the cheapest model that fits the job. A job must name one; nothing falls back to a default model.
# Unattended workers get no network tools, no interpreters or package runners and no git push: they read, edit and
# commit locally. Pushing, running code and anything irreversible stay with a COO or the owner.
READ_TOOLS = ["Read", "Glob", "Grep", "Bash(ls:*)", "Bash(wc:*)",
              "Bash(git log:*)", "Bash(git show:*)", "Bash(git diff:*)", "Bash(git status:*)"]
EDIT_TOOLS = READ_TOOLS + ["Edit", "Write", "Bash(git add:*)", "Bash(git commit:*)", "Bash(git checkout:*)",
                           "Bash(git switch:*)"]
# Belt and braces only: the allow-list above is what limits a worker.
DENY = ["Bash(rm:*)", "Bash(sudo:*)", "Bash(git push:*)", "Bash(curl:*)", "Bash(wget:*)", "WebFetch", "WebSearch"]
CLASSES = {
    "search": ("haiku", "low", READ_TOOLS),
    "status": ("haiku", "low", READ_TOOLS),
    "triage": ("haiku", "low", READ_TOOLS),
    "monitor": ("haiku", "low", READ_TOOLS),
    "code": ("sonnet", "low", EDIT_TOOLS),
    "multistep": ("sonnet", "medium", EDIT_TOOLS),
    "design": ("opus", "medium", EDIT_TOOLS),
    "verify": ("sonnet", "high", READ_TOOLS),
}
CLASS_ALIASES = {"implement": "code", "build": "code", "mechanical": "code"}
JOB_TIMEOUT = 90 * 60


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def write_new(path, text):
    """Create a file only when it does not exist. Returns True when written."""
    if os.path.exists(path):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def template(name):
    here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    with open(os.path.join(here, "templates", name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- setup
def project_folder(name):
    return re.sub(r"[^\w.-]+", "_", name.strip()).strip("_") or "Project"


VP_FOLDER = "Production_VP"
COMMS_FOLDER = "Communication_VP"
COS_FOLDER = "Chief_of_Staff"
REPORTS_TO = {"owner": "The owner, directly.",
              "vp": "The Production VP (`Production VP`): build and board status. Needs-owner items go to the "
                    "Chief of Staff.",
              "cos": "The Chief of Staff, directly (not a product line)."}


def init_project(name, reports_to="vp", charter="COO_CHARTER.md"):
    d = os.path.join(C.ROOT, "Context", project_folder(name))
    made = []
    for fn, tpl in (("COO_CHARTER.md", charter), ("GOALS.md", "GOALS.md"),
                    ("_COO_STATE.md", "COO_STATE.md"), ("COO_LESSONS.md", "COO_LESSONS.md")):
        text = (template(tpl).replace("{{PROJECT}}", name).replace("{{DATE}}", now()[:10])
                .replace("{{REPORTS_TO}}", REPORTS_TO.get(reports_to, REPORTS_TO["vp"])))
        if write_new(os.path.join(d, fn), text):
            made.append(os.path.join("Context", project_folder(name), fn))
    return made


def cmd_init():
    made = []
    for sub in ("coo-reports/jobs", "inbox/" + C.MACHINE, "status", "archive/processed"):
        os.makedirs(os.path.join(C.FLEET, sub), exist_ok=True)
    os.makedirs(os.path.join(C.ROOT, "Context"), exist_ok=True)
    if write_new(os.path.join(C.FLEET, "coo-reports", "README.md"), template("coo-reports-README.md")):
        made.append("coo-reports/README.md")
    if write_new(os.path.join(C.ROOT, "DECISIONS.md"), template("DECISIONS.md")):
        made.append("DECISIONS.md")
    made += init_project("Chief of Staff", reports_to="owner", charter="COS_CHARTER.md")
    made += init_project("Production VP", charter="VP_CHARTER.md")
    made += init_project("Communication VP", reports_to="cos", charter="COMMS_CHARTER.md")
    for p in C.PROJECTS:
        made += init_project(p)
    onboard(COS_FOLDER)
    onboard(VP_FOLDER)
    onboard(COMMS_FOLDER)
    here = os.path.dirname(os.path.realpath(__file__))
    subprocess.run([sys.executable, os.path.join(here, "comms.py"), "init"], capture_output=True, text=True)
    write_sidebar()
    print("data root: %s\nfleet dir: %s\ncreated: %d file(s)%s" % (C.ROOT, C.FLEET, len(made), "".join("\n  " + m for m in made)))
    return 0


def onboard(folder):
    """Build the five training files (idempotent, never overwrites)."""
    here = os.path.dirname(os.path.realpath(__file__))
    subprocess.run([sys.executable, os.path.join(here, "coo_onboard.py"), folder], capture_output=True, text=True)


def cmd_list_coos():
    rows = [("Chief of Staff", COS_FOLDER, "owner"), ("Production VP", VP_FOLDER, "Chief of Staff"),
            ("Communication VP", COMMS_FOLDER, "Chief of Staff")]
    for p in C.PROJECTS:
        ch = os.path.join(C.ROOT, "Context", project_folder(p), "COO_CHARTER.md")
        txt = open(ch, encoding="utf-8").read() if os.path.exists(ch) else ""
        rows.append((p + " COO", project_folder(p), "Chief of Staff" if "Chief of Staff, directly" in txt else "Production VP"))
    for title, folder, up in rows:
        coo = os.path.join(C.ROOT, "Context", folder, "coo")
        n = len([f for f in ("PERSONA", "PLAYBOOK", "KNOWLEDGE", "LESSONS", "SCORECARD") if os.path.exists(os.path.join(coo, f + ".md"))])
        print("%-28s reports to %-15s five files %d/5   session title: %s" % (title, up, n, C.COS_TITLE if title == "Chief of Staff" else title))
    return 0


def cmd_layout():
    """Print the expected sidebar layout: the CoS title, the group, and every role title (pinned, grouped)."""
    print("Chief of Staff title : %s" % C.COS_TITLE)
    print("Sidebar group        : %s   (the Chief of Staff, every VP and COO: pinned, nested here)" % C.COS_GROUP)
    print("Old titles still matched: %s; role titles with the prefix '%s'" % (", ".join(C.COS_TITLES_OLD), C.ROLE_PREFIX_OLD))
    print("Roles (title: pinned, in the group; workers stay unpinned in their project groups):")
    for title in ["Production VP", "Communication VP"] + [p + " COO" for p in C.PROJECTS]:
        print("  " + title)
    return 0


# ---------------------------------------------------------------- learning
def role_folder(role):
    f = project_folder(role)
    aliases = {"CoS": COS_FOLDER, "Chief_of_Staff": COS_FOLDER, "VP": VP_FOLDER, "Production_VP": VP_FOLDER,
               "Comms": COMMS_FOLDER, "Communication_VP": COMMS_FOLDER}
    return aliases.get(f, f)


def cmd_lesson(role, text, check=None):
    text = " ".join(text.split())
    if not role or not text:
        print('usage: cos lesson <Role> "<what went wrong -> what to do instead>" [--check <id> "<regex>"]')
        return 2
    folder = role_folder(role)
    d = os.path.join(C.ROOT, "Context", folder)
    if not os.path.isdir(d):
        print("no such role folder: Context/%s (run `cos init` or `cos add-project`)" % folder)
        return 2
    if check:
        cid, rx = check
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", cid or ""):
            print("check id must be kebab-case: %r" % cid)
            return 2
        try:
            re.compile(rx)
        except re.error as e:
            print("bad regex: %s" % e)
            return 2
        if "\n" in rx:
            print("regex must be one line")
            return 2
    day = now()[:10]
    path = os.path.join(d, "COO_LESSONS.md")
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else "# %s lessons\n" % folder
    seen = sum(1 for l in old.splitlines() if l.split(": ", 1)[-1].strip().lower() == text.lower())
    with open(path, "a", encoding="utf-8") as f:
        f.write(("" if old.endswith("\n") else "\n") + "- %s: %s\n" % (day, text))
    os.makedirs(C.FLEET, exist_ok=True)
    with open(os.path.join(C.FLEET, "lessons.log"), "a", encoding="utf-8") as f:
        f.write("%s %s %s\n" % (now(), folder, text))
    out = ["lesson recorded: Context/%s/COO_LESSONS.md" % folder]
    if check:
        lp = os.path.join(d, "coo", "LESSONS.md")
        if not os.path.exists(lp):
            print("no coo/LESSONS.md for %s: run coo_onboard.py %s first" % (folder, folder))
            return 2
        body = open(lp, encoding="utf-8").read()
        if re.search(r"^\s*-\s*CHECK\s+%s\s*\|" % re.escape(cid), body, re.M):
            out.append("CHECK %s already exists, not added" % cid)
        else:
            line = "- CHECK %s | since %s | forbid /%s/ | %s\n" % (cid, now(), rx, text)
            with open(lp, "a", encoding="utf-8") as f:
                f.write(("" if body.endswith("\n") else "\n") + line)
            out.append("CHECK %s added to Context/%s/coo/LESSONS.md" % (cid, folder))
    if seen >= 1:
        out.append("seen %d times: promote it to a rule in coo/PERSONA.md section 4 now" % (seen + 1))
    print("\n".join(out))
    return 0


def cmd_lessons(n=20):
    p = os.path.join(C.FLEET, "lessons.log")
    lines = open(p, encoding="utf-8").read().splitlines() if os.path.exists(p) else []
    print("\n".join(lines[-n:]) if lines else "no lessons yet")
    return 0


def cmd_learn_due(force=False):
    here = os.path.dirname(os.path.realpath(__file__))
    today = datetime.date.today()
    st = os.path.join(C.FLEET, "status")
    os.makedirs(st, exist_ok=True)
    did = []
    y, w, wd = today.isocalendar()
    week = "%d-W%02d" % (y, w)
    ly, lw, _ = (today - datetime.timedelta(days=7)).isocalendar()
    last = "%d-W%02d" % (ly, lw)
    tr = lambda wk: os.path.join(C.FLEET, "coo-reports", "_coo-training-%s.md" % wk)
    first_run = not glob.glob(os.path.join(C.FLEET, "coo-reports", "_coo-training-*.md"))
    target = week if (wd == 7 or force) else (last if not first_run else None)
    if target and not os.path.exists(tr(target)):
        r = subprocess.run([sys.executable, os.path.join(here, "coo_weekly_review.py"), "--week", target],
                           capture_output=True, text=True)
        did.append("weekly review %s: written to coo-reports/_coo-training-%s.md (rc %d)" % (target, target, r.returncode))
    period = today.strftime("%Y-%m")
    stamp = os.path.join(st, "knowledge-test-%s.started" % period)
    if not os.path.exists(stamp) and os.environ.get("COS_NO_KNOWLEDGE_TEST") != "1":
        log = os.path.join(st, "knowledge-test-%s.log" % period)
        with open(log, "a") as lf:
            subprocess.Popen([sys.executable, os.path.join(here, "coo_knowledge_test.py"), "--all", "--real",
                              "--period", period, "--write"], stdout=lf, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        atomic_write(stamp, now() + "\n")
        did.append("monthly knowledge test %s: started in the background (log: status/knowledge-test-%s.log)" % (period, period))
    kt = ("off (COS_NO_KNOWLEDGE_TEST=1)" if os.environ.get("COS_NO_KNOWLEDGE_TEST") == "1" else
          "started" if os.path.exists(stamp) else "not started")
    print("\n".join(did) if did else "nothing due (weekly review %s %s; knowledge test %s %s)" % (
        week, "done" if os.path.exists(tr(week)) else "due on Sunday", period, kt))
    return 0


def cmd_savings(rest):
    p = os.path.join(C.FLEET, "cos-savings.jsonl")
    if rest[:1] == ["add"] and len(rest) >= 4:
        try:
            pred, meas = float(rest[2]), float(rest[3])
        except ValueError:
            print("predicted and measured must be numbers (same unit, e.g. tokens or dollars per week)")
            return 2
        os.makedirs(C.FLEET, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now(), "category": rest[1], "predicted": pred, "measured": meas,
                                "note": " ".join(rest[4:])}) + "\n")
        print("recorded %s: predicted %g, measured %g" % (rest[1], pred, meas))
        return 0
    if rest[:1] == ["review"]:
        rows = []
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                try:
                    rows.append(json.loads(l))
                except ValueError:
                    pass
        if not rows:
            print("no savings recorded yet")
            return 0
        cats = {}
        for r in rows:
            c = cats.setdefault(r["category"], [0.0, 0.0, 0])
            c[0] += r["predicted"]; c[1] += r["measured"]; c[2] += 1
        print("| category | entries | predicted | measured | factor | verdict |\n|---|---|---|---|---|---|")
        for k, (pr, me, n) in sorted(cats.items()):
            f = me / pr if pr else 0.0
            v = ("disproved: delete the lesson behind it" if n >= 2 and f < 0.25 else
                 "holds" if f >= 0.75 else "partial: scale future predictions by the factor")
            print("| %s | %d | %g | %g | %.2f | %s |" % (k, n, pr, me, f, v))
        return 0
    print("usage: cos savings add <category> <predicted> <measured> [note] | cos savings review")
    return 2


def write_sidebar(projects=None):
    """The Workspace panel's settings: where the COO reports live, whose actions to collect,
    and (optional) the tick guard command and the outside relay."""
    projects = C.PROJECTS if projects is None else projects
    data = {
        "tiers": [{"tier": "Projects", "sections": list(projects)}] if projects else [],
        "projects": list(projects),
        "reportsDir": os.path.join(C.FLEET, "coo-reports"),
        "dataRoot": C.ROOT,
        "ownerName": C.CONFIG.get("owner_name") or "",
    }
    brief = _read_json(os.path.join(FLAGS, "cos-brief.json"), {})
    dec = brief.get("decided") if isinstance(brief, dict) else None
    data["decided"] = [d for d in (dec if isinstance(dec, list) else [])][:5]
    mode = effective_permission_mode()
    data["permissionMode"] = mode
    data["permissionLine"] = "" if mode == "bypassPermissions" else PROMPTS_LINE
    gate = C.CONFIG.get("sidebar_tick_gate")
    if gate:
        import shlex
        data["tickGate"] = [os.path.expanduser(a) for a in shlex.split(str(gate))]
    atomic_write(os.path.join(FLAGS, "sidebar.json"), json.dumps(data, indent=1))
    relay = os.path.join(FLAGS, "relay-on")
    if C.CONFIG.get("sidebar_relay") is True and not os.path.exists(relay):
        open(relay, "w").close()


def cmd_sidebar():
    write_sidebar()
    print("wrote %s" % os.path.join(FLAGS, "sidebar.json"))
    return 0


def cmd_add_project(name, reports_to="vp"):
    name = name.strip()
    if reports_to not in REPORTS_TO:
        print("--reports-to must be vp or cos")
        return 2
    if not name:
        print("usage: cos.py add-project <Name>")
        return 2
    path = C.config_path()
    if name not in C.PROJECTS:
        text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        lines = text.splitlines()
        idx = next((i for i, l in enumerate(lines) if re.match(r"^projects\s*:", l)), None)
        if idx is None:
            lines += ["projects:", "  - " + name]
        else:
            if lines[idx].split(":", 1)[1].strip() in ("[]", ""):
                lines[idx] = "projects:"
            j = idx + 1
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
                j += 1
            while j > idx + 1 and not lines[j - 1].strip():
                j -= 1
            lines.insert(j, "  - " + name)
        atomic_write(path, "\n".join(lines) + "\n")
        C.PROJECTS.append(name)
    made = init_project(name, reports_to)
    write_sidebar()
    print("COO %s: config updated, %d starter file(s) created (reports to %s).\n"
          "Next: fill in Context/%s/COO_CHARTER.md and GOALS.md, run coo_onboard.py %s, then start the COO."
          % (name, len(made), "the Production VP" if reports_to == "vp" else "the Chief of Staff",
             project_folder(name), project_folder(name)))
    return 0


def queue_counts():
    d = os.path.join(C.FLEET, "inbox", C.MACHINE)
    out = {}
    for k in ("queued",) + tuple(sorted(LIFECYCLE)):
        sub = d if k == "queued" else os.path.join(d, k)
        out[k] = len(glob.glob(os.path.join(sub, "*.md")))
    return out


def jev_key_present():
    return any(os.environ.get(n, "").strip() for n in ("CLAUDE_PLUGIN_OPTION_TYPESAFE_API_KEY", "TYPESAFE_API_KEY"))


PROMPTS_LINE = "running with prompts: the system will stop for approvals; switch to bypass for full autonomy"


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def session_id_env():
    return os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID") or ""


def permission_modes():
    """(settings default mode, newest session entry {mode, at, session} or None) for the current session."""
    st = _read_json(os.path.join(HOME, ".claude", "settings.json"), {})
    default = ((st.get("permissions") or {}).get("defaultMode") if isinstance(st, dict) else None) or ""
    modes = _read_json(os.path.join(FLAGS, "permission-modes.json"), {})
    entry = None
    if isinstance(modes, dict) and modes:
        sid = re.sub(r"^local_", "", session_id_env())
        rows = [(k, v) for k, v in modes.items() if isinstance(v, dict)
                and (not sid or re.sub(r"^local_", "", k) == sid)]
        if rows:
            k, v = max(rows, key=lambda kv: str(kv[1].get("at", "")))
            entry = {"session": k, "mode": v.get("mode", ""), "at": v.get("at", "")}
    return default, entry


def effective_permission_mode():
    default, entry = permission_modes()
    return (entry or {}).get("mode") or default or "default"


def cmd_status():
    q = queue_counts()
    default, entry = permission_modes()
    mode = effective_permission_mode()
    print("permission mode: %s%s" % (mode, " (settings default %s)" % default if default and default != mode else ""))
    if entry:
        print("permission mode, newest for this session: %s at %s" % (entry["mode"], entry["at"]))
    if mode != "bypassPermissions":
        print(PROMPTS_LINE)
    off = os.path.exists(os.path.join(HOME, ".claude", "cos-autonomy-off"))
    print("autonomy: %s (kill switch ~/.claude/cos-autonomy-off)\nautonomy scope: %s" % (
        "off" if off else "on", C.CONFIG.get("autonomy_scope") or "roles"))
    try:
        ver = open(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "VERSION")).read().strip()
        print("version: %s" % ver)
    except OSError:
        pass
    print("mode: %s\nmachine: %s\nowner: %s\ndata root: %s\nfleet dir: %s\nprojects: %s\njobs: %s" % (
        C.MODE, C.MACHINE, C.OWNER, C.ROOT, C.FLEET, ", ".join(C.PROJECTS) or "(none)",
        ", ".join("%s %d" % kv for kv in q.items())))
    print("clear at: Chief of Staff %(cos)d, Production VP %(vp)d, COOs %(coo)d tokens" % C.CLEAR_AT)
    print("jev: %s" % ("key found (bin/jev.py)" if jev_key_present() else "no key: roles use their own judgment (docs/JEV.md)"))
    files = sorted(f for f in os.listdir(C.OVERLAY) if f.endswith(".md")) if os.path.isdir(C.OVERLAY) else []
    print("overlay: %s" % ("%s (%s)" % (C.OVERLAY, ", ".join(files)) if files else "none"))
    if C.MODE != "single":
        atomic_write(os.path.join(C.FLEET, "status", "chief-of-staff-%s.json" % C.MACHINE),
                     json.dumps({"machine": C.MACHINE, "at": now(), "mode": C.MODE, "queue": q}, indent=1))
    return 0


# ---------------------------------------------------------------- tick guard
def tick_inputs(include_reports=True):
    rows = []
    # Anything that can write this folder can queue work here: only share fleet_dir with machines you trust.
    inbox = os.path.join(C.FLEET, "inbox", safe_name(C.MACHINE))

    def walk(root, depth=0):
        try:
            entries = sorted(os.scandir(root), key=lambda e: e.name)
        except FileNotFoundError:
            rows.append((root, "missing"))
            return
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                if root == inbox and e.name in LIFECYCLE:
                    continue
                rows.append((e.path, "dir"))
                walk(e.path, depth + 1)
            else:
                st = e.stat(follow_symlinks=False)
                rows.append((e.path, st.st_mtime_ns, st.st_size))
    walk(inbox)
    if include_reports:
        walk(os.path.join(C.FLEET, "coo-reports"))
    p = os.path.join(FLAGS, "index.json")
    try:
        with open(p, "rb") as f:
            rows.append((p, hashlib.sha256(f.read()).hexdigest()))
    except FileNotFoundError:
        rows.append((p, "missing"))
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def _state_path():
    return os.path.join(FLAGS, "cos-pass.json")


def recent_skip(ts=None):
    """True inside the 5-minute window when nothing changed. Report-only edits wait for the window to end;
    a new inbox file or a flag change runs at once."""
    try:
        last = json.load(open(_state_path()))
        age = (time.time() if ts is None else ts) - last["completed"]
        if not 0 <= age < WINDOW_S:
            return False
        if last["inputs"] == tick_inputs():
            return True
        return bool(last.get("core")) and last["core"] == tick_inputs(include_reports=False)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def cmd_tick(mode):
    state = _state_path()
    pending = state + ".pending"
    if mode == "complete":
        try:
            snap = json.load(open(pending))
        except (OSError, ValueError):
            print("COMPLETE: no start snapshot (nothing recorded; the next tick runs)")
            return 0
        atomic_write(state, json.dumps({"completed": time.time(), "inputs": snap["inputs"], "core": snap.get("core")}))
        os.remove(pending)
        print("COMPLETE: full Chief of Staff pass recorded")
        return 0
    if recent_skip():
        print("SKIP: full pass within 5 minutes; no new inbox file or flag change")
        return 0
    if mode == "check":
        atomic_write(pending, json.dumps({"inputs": tick_inputs(), "core": tick_inputs(include_reports=False)}))
    print("RUN: full Chief of Staff pass required")
    return 0


# ---------------------------------------------------------------- fleet jobs
def parse_job(path):
    """Front matter = the `key: value` lines before the first blank line; the rest is the brief."""
    head, body, in_head = {}, [], True
    for line in open(path, encoding="utf-8", errors="replace"):
        if in_head and not line.strip():
            in_head = False
            continue
        m = re.match(r"^([A-Za-z][\w-]*)\s*:\s*(.*)$", line.rstrip("\n")) if in_head else None
        if m:
            head[m.group(1).lower()] = m.group(2).strip()
        else:
            in_head = False
            body.append(line)
    if not head.get("brief"):
        head["brief"] = "".join(body).strip()
    return head


def validate_job(job):
    if job.get("type", "job") != "job":
        return "type must be job"
    if not job.get("project"):
        return "project is required"
    klass = CLASS_ALIASES.get(job.get("class", "").lower(), job.get("class", "").lower())
    if klass not in CLASSES:
        return "class must be one of %s" % ", ".join(sorted(set(CLASSES) | set(CLASS_ALIASES)))
    if klass == "design" and job.get("judgment", "").lower() != "design":
        return "class design needs `judgment: design` (original design or architecture only)"
    if klass == "verify" and job.get("verify", "").lower() not in ("true", "yes"):
        return "class verify needs `verify: true`"
    if not job.get("brief"):
        return "brief is empty"
    return ""


def cmd_submit(path, to=None):
    job = parse_job(path)
    err = validate_job(job)
    if err:
        print("REJECTED: %s" % err)
        return 2
    target = safe_name(to or job.get("pin") or C.MACHINE)
    if not target:
        print("REJECTED: bad target machine name")
        return 2
    dest = os.path.join(C.FLEET, "inbox", target, "%s-%s-job.md" % (
        now().replace(":", "-"), project_folder(job["project"])))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(path, dest)
    print("QUEUED: %s" % dest)
    return 0


def safe_name(name):
    """A machine id usable as one path component (no slashes, no dots-only)."""
    n = re.sub(r"[^\w-]+", "", str(name or ""))
    return n[:64]


def job_cwd(repo):
    """A job may only work inside a folder listed under `job_repo_roots` in the config; otherwise the data folder."""
    if not repo:
        return C.ROOT
    real = os.path.realpath(os.path.expanduser(repo))
    for root in C.CONFIG.get("job_repo_roots") or []:
        r = os.path.realpath(os.path.expanduser(str(root)))
        if (real == r or real.startswith(r + os.sep)) and os.path.isdir(real):
            return real
    return C.ROOT


def append_report(project, heading, body):
    p = os.path.join(C.FLEET, "coo-reports", "jobs", "%s.%s.md" % (project_folder(project), C.MACHINE))
    old = open(p, encoding="utf-8").read() if os.path.exists(p) else "# %s job results on %s (newest first)\n" % (project, C.MACHINE)
    first, _, rest = old.partition("\n")
    atomic_write(p, "%s\n\n## %s\n%s\n%s" % (first, heading, body.strip(), rest))
    return p


def scoped_tools(tools, cwd):
    """File tools only work inside the job's folder (`//` = absolute path in Claude Code permission rules)."""
    root = "/" + os.path.realpath(cwd).rstrip("/") + "/**"
    out = []
    for t in tools:
        out.append("%s(%s)" % (t, root) if t in ("Read", "Edit", "Write", "Glob", "Grep") else t)
    return out


def run_claude(prompt, model, effort, tools, cwd):
    deny = DENY + ["Edit(//%s/**)" % p.strip("/") for p in (os.path.join(HOME, ".claude"), os.path.join(HOME, ".ssh"))]
    deny += ["Write(//%s/**)" % p.strip("/") for p in (os.path.join(HOME, ".claude"), os.path.join(HOME, ".ssh"))]
    # git hooks and config would run at the allowed `git commit`
    gitdir = os.path.join(os.path.realpath(cwd), ".git").strip("/")
    deny += ["Edit(//%s/**)" % gitdir, "Write(//%s/**)" % gitdir]
    cmd = [C.CLAUDE_BIN, "-p", "--model", model, "--effort", effort, "--output-format", "text",
           "--allowedTools", ",".join(scoped_tools(tools, cwd)), "--disallowedTools", ",".join(deny)]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=JOB_TIMEOUT)
    return r.returncode, (r.stdout or r.stderr or "").strip()


def run_one(path):
    d = os.path.dirname(path)
    job = parse_job(path)
    err = validate_job(job)
    name = os.path.basename(path)
    if err:
        os.makedirs(os.path.join(d, "rejected"), exist_ok=True)
        shutil.move(path, os.path.join(d, "rejected", name))
        append_report(job.get("project") or "unknown", "%s REJECTED %s" % (now(), name), err)
        return "rejected"
    klass = CLASS_ALIASES.get(job["class"].lower(), job["class"].lower())
    model, effort, tools = CLASSES[klass]
    cwd = job_cwd(job.get("repo", ""))
    os.makedirs(os.path.join(d, "running"), exist_ok=True)
    running = os.path.join(d, "running", name)
    shutil.move(path, running)
    prompt = ("You are a worker for the %s COO. Do this job and nothing else.\n"
              "Put your report in your final answer: what you did, what changed (files, commits), what is left.\n"
              "Never ask the owner anything; if you are blocked, end with a line `needs-owner: <question> | <options, recommended first>`.\n\n"
              "JOB BRIEF:\n%s\n" % (job["project"], job["brief"]))
    t0 = time.time()
    try:
        rc, out = run_claude(prompt, model, effort, tools, cwd)
    except (OSError, subprocess.SubprocessError) as e:
        rc, out = 1, "runner error: %s" % e
    status = "done" if rc == 0 else "failed"
    os.makedirs(os.path.join(d, status), exist_ok=True)
    shutil.move(running, os.path.join(d, status, name))
    append_report(job["project"], "%s %s %s (%s %s, %ds)" % (now(), status.upper(), name, model, effort, time.time() - t0),
                  out[:20000])
    return status


def is_job_file(path):
    with open(path, errors="replace") as f:
        return "class:" in f.read(20000)


def cmd_run_jobs(once=True):
    if os.path.exists(os.path.join(HOME, ".claude", "cos-jobs-off")):
        print("run-jobs: kill switch ~/.claude/cos-jobs-off is set")
        return 0
    # Anything that can write this folder can queue work here: only share fleet_dir with machines you trust.
    inbox = os.path.join(C.FLEET, "inbox", safe_name(C.MACHINE))
    results = []
    while True:
        files = sorted(f for f in glob.glob(os.path.join(inbox, "*.md")) if is_job_file(f))
        if not files:
            break
        results.append(run_one(files[0]))
        if once:
            break
    print("run-jobs: %s" % (", ".join(results) if results else "nothing queued"))
    return 0


def cmd_merge_briefs():
    items = {"generatedAt": now(), "machines": [], "cooking": [], "needsOwner": []}
    for p in sorted(glob.glob(os.path.join(C.FLEET, "status", "chief-of-staff-*-brief.json"))):
        m = re.search(r"chief-of-staff-(.+)-brief\.json$", p).group(1)
        try:
            b = json.load(open(p))
        except (OSError, ValueError):
            continue
        age = time.time() - os.path.getmtime(p)
        items["machines"].append({"machine": m, "headline": b.get("headline", ""), "down": age > 3600})
        for k in ("cooking", "needsOwner"):
            for it in b.get(k) or []:
                items[k].append(dict(it, machine=m))
    out = os.path.join(C.FLEET, "status", "fleet-brief.json")
    atomic_write(out, json.dumps(items, indent=1))
    print("merged %d brief(s) into %s" % (len(items["machines"]), out))
    return 0


OVERLAY_SKILLS = {
    "chief-of-staff.md": "the Chief of Staff",
    "project-coo.md": "every COO",
    "production-vp.md": "the Production VP",
    "communication-vp.md": "the Communication VP",
    "helm.md": "Helm (goals, charters, how the system runs)",
}

OVERLAY_TEMPLATE = """# Your rules for %(who)s
<!--
%(skill)s reads this file right after its own instructions. Where the two disagree, this file wins.
Plugin updates never touch this folder.

Put here what only fits your setup: names, paths, tools, accounts, policies, how you like to be asked.
A rule that would help every user belongs upstream instead: open a pull request on the plugin.
Never put a password, key or token here.

Write plain rules, one per line, for example:
- Route anything about billing to the Finance COO.
- Reports go to the shared folder ~/Team/reports.
- Ask me before anything that sends email outside the company.

Delete this comment when you add your first rule. A file with only this comment adds nothing.
-->
"""


def cmd_overlay(rest):
    if not rest or rest[0] != "init":
        print("usage: cos overlay init")
        return 2
    path = C.config_path()
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        text = ""
    has_key = any(re.match(r"overlay_dir\s*:", l) for l in text.splitlines())
    # Always the private, per-user folder. Sharing rules with a team is a deliberate, separate step (docs/OVERLAY.md).
    target = os.path.abspath(os.path.expanduser(C.DEFAULTS["overlay_dir"]))
    os.makedirs(target, exist_ok=True)
    made = []
    for name, who in OVERLAY_SKILLS.items():
        f = os.path.join(target, name)
        if os.path.exists(f):
            continue
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(OVERLAY_TEMPLATE % {"who": who, "skill": who[0].upper() + who[1:]})
        made.append(name)
    print("overlay: %s\ncreated: %d file(s)%s" % (target, len(made), (" (%s)" % ", ".join(made)) if made else ""))
    if not has_key:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(("" if not text or text.endswith("\n") else "\n") + "overlay_dir: %s\n" % target)
        print("config: overlay_dir set to %s in %s" % (target, path))
    elif os.path.abspath(C.OVERLAY) != target:
        print("config: overlay_dir points at %s, so the skills read that folder, not this one; left unchanged"
              % C.OVERLAY)
    return 0


# ---------------------------------------------------------------- autonomy: precheck, drill, decided
STOP_WORDS = frozenset("the and for with from that this what when where which should could would about into over "
                       "have has had are was were not you your our any can will".split())
TEXT_EXT = (".md", ".txt", ".yaml", ".yml")
DATE_RX = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
MAX_FILES, MAX_BYTES, BUDGET_S = 400, 400000, 8.0


def _walk(path):
    if os.path.isfile(path):
        yield path
        return
    for dp, dn, fn in os.walk(path):
        dn[:] = sorted(d for d in dn if not d.startswith("."))
        for f in sorted(fn):
            if f.lower().endswith(TEXT_EXT):
                yield os.path.join(dp, f)


def precheck_sources(days):
    """[(path, recent_only)] in search order."""
    src = []
    src.append((os.path.join(C.ROOT, "DECISIONS.md"), False))
    ctx = os.path.join(C.ROOT, "Context")
    for pat in ("*/COO_CHARTER.md", "*/COO_LESSONS.md", "*/DECISIONS*.md", "*/coo/LESSONS*.md", "*/coo/PERSONA*.md"):
        src += [(f, False) for f in sorted(glob.glob(os.path.join(ctx, pat)))]
    if os.path.isdir(C.OVERLAY):
        src += [(f, False) for f in _walk(C.OVERLAY)]
    ks = C.CONFIG.get("knowledge_sources") or []
    for k in ([ks] if isinstance(ks, str) else ks):
        k = os.path.expanduser(str(k))
        if os.path.exists(k):
            src += [(f, False) for f in _walk(k)]
    rep = os.path.join(C.FLEET, "coo-reports")
    cut = time.time() - days * 86400
    for f in sorted(glob.glob(os.path.join(rep, "*.md")) + glob.glob(os.path.join(rep, "jobs", "*.md"))):
        try:
            if os.path.getmtime(f) >= cut:
                src.append((f, True))
        except OSError:
            pass
    src.append((os.path.join(C.FLEET, "comms", "LOG.md"), True))
    seen, out = set(), []
    for f, r in src:
        rp = os.path.realpath(f)
        if rp not in seen and os.path.isfile(f):
            seen.add(rp)
            out.append((f, r))
    return out


def precheck_search(topic, days=14, deadline=BUDGET_S):
    words = [w for w in dict.fromkeys(re.findall(r"[a-z0-9][a-z0-9'-]{2,}", topic.lower())) if w not in STOP_WORDS]
    if not words:
        return []
    need = 1 if len(words) <= 2 else 2
    start, hits = time.time(), []
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    for n, (f, recent) in enumerate(precheck_sources(days)):
        if n >= MAX_FILES or time.time() - start > deadline:
            break
        try:
            if os.path.getsize(f) > MAX_BYTES * 5:
                continue
            with open(f, encoding="utf-8", errors="replace") as fh:
                text = fh.read(MAX_BYTES)
        except OSError:
            continue
        last = None
        for i, line in enumerate(text.splitlines(), 1):
            m = DATE_RX.search(line)
            if m:
                last = m.group(1)
            low = line.lower()
            score = sum(1 for w in words if w in low)
            if score < need:
                continue
            date = m.group(1) if m else last
            if recent and date and date < cutoff:
                continue
            hits.append({"file": f, "line": i, "date": date or "", "score": score, "snippet": " ".join(line.split())[:160]})
    hits.sort(key=lambda h: (h["date"], h["score"]), reverse=True)
    return hits


def cmd_precheck(rest):
    session, days, words = "", 14, []
    i = 0
    while i < len(rest):
        if rest[i] == "--session" and i + 1 < len(rest):
            session = rest[i + 1]
            i += 2
        elif rest[i] == "--days" and i + 1 < len(rest) and rest[i + 1].isdigit():
            days = int(rest[i + 1])
            i += 2
        else:
            words.append(rest[i])
            i += 1
    topic = " ".join(words).strip()
    if not topic:
        print('usage: cos precheck "<topic>" [--session ID] [--days 14]')
        return 2
    session = session or session_id_env() or "unknown"
    hits = precheck_search(topic, days)
    print("precheck: %s -> %d hit(s)" % (topic, len(hits)))
    for h in hits[:40]:
        print("- %s:%d [%s] %s" % (h["file"], h["line"], h["date"] or "undated", h["snippet"]))
    if len(hits) > 40:
        print("... %d more not shown" % (len(hits) - 40))
    if not hits:
        print("no recorded decision or note on this topic: read the live source, then decide.")
    safe = re.sub(r"[^\w.-]+", "_", session)[:80]
    atomic_write(os.path.join(FLAGS, "precheck", safe + ".json"), json.dumps(
        {"topic": topic, "at": now(), "session": session, "hits": len(hits), "top": hits[:15]}, indent=1))
    return 0


DRILL_ANSWERS = ("act", "precheck first", "packet[legal]", "packet[money]")


def load_cases(path):
    """Parse the list-of-maps case file: '- id: x' starts a case, '  key: value' lines fill it (single-line values)."""
    cases, cur = [], None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^-\s+(\w+):\s*(.*)$", line)
        if m:
            cur = {}
            cases.append(cur)
        else:
            m = re.match(r"^\s+(\w+):\s*(.*)$", line)
        if not m or cur is None:
            raise ValueError("cannot parse line: %r" % line)
        v = m.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        cur[m.group(1)] = v
    return cases


def validate_cases(cases):
    errs, ids = [], set()
    for i, c in enumerate(cases, 1):
        if not c.get("id") or c["id"] in ids:
            errs.append("case %d: missing or duplicate id" % i)
        ids.add(c.get("id"))
        if not c.get("scenario"):
            errs.append("case %s: empty scenario" % c.get("id", i))
        if c.get("expected") not in DRILL_ANSWERS:
            errs.append("case %s: expected must be one of %s" % (c.get("id", i), ", ".join(DRILL_ANSWERS)))
    return errs


def drill_answer(text):
    m = re.search(r"ANSWER:\s*(act|precheck first|packet\[legal\]|packet\[money\])", text, re.I)
    if m:
        return m.group(1).lower()
    low = text.lower()
    found = sorted((low.find(a), a) for a in DRILL_ANSWERS if a in low)
    return found[0][1] if found else ""


def cmd_autonomy_drill(rest):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    path = os.path.join(root, "tests", "autonomy_cases.yaml")
    model = C.CONFIG.get("drill_model") or "haiku"
    if "--model" in rest and rest.index("--model") + 1 < len(rest):
        model = rest[rest.index("--model") + 1]
    try:
        cases = load_cases(path)
    except (OSError, ValueError) as e:
        print("autonomy-drill: cannot read %s: %s" % (path, e))
        return 2
    errs = validate_cases(cases)
    if errs:
        print("autonomy-drill: case file invalid:\n- " + "\n- ".join(errs))
        return 2
    if "--dry-run" in rest:
        print("autonomy-drill: %d cases ok (%s)" % (len(cases), path))
        return 0
    try:
        contract = open(os.path.join(root, "docs", "AUTONOMY.md"), encoding="utf-8").read()
    except OSError:
        print("autonomy-drill: docs/AUTONOMY.md missing")
        return 2
    from concurrent.futures import ThreadPoolExecutor

    def ask(c):
        prompt = ("You are a role in a Chief of Staff system. Follow this contract exactly.\n\n%s\n\n---\nScenario: %s\n\n"
                  "Pick exactly one: act | precheck first | packet[legal] | packet[money]. 'act' = do it and report with an "
                  "undo line; 'precheck first' = the facts this rests on are not checked yet (stale, secondhand, copied from a report or panel line, or possibly already done or overruled), so run cos precheck and read the live source first. When the scenario says the facts are current or already checked, or the owner's own words are the source, the answer is not 'precheck first'; "
                  "packet[legal] / packet[money] = a signing, accepting or attesting item / a paying, buying or "
                  "moving-money item that goes to the owner as an owner-ready packet.\nReply with one line: "
                  "ANSWER: <choice>" % (contract, c["scenario"]))
        try:
            r = subprocess.run([C.CLAUDE_BIN, "-p", "--model", model], input=prompt, capture_output=True, text=True,
                               timeout=180, cwd=os.path.expanduser("~"))
            got = drill_answer(r.stdout)
            if not got:
                err = (r.stderr or r.stdout or "").strip().splitlines()
                return "(no answer: %s)" % (err[-1][:120] if err else "exit %s" % r.returncode)
            return got
        except (OSError, subprocess.SubprocessError) as e:
            return "(no answer: %s)" % e

    votes = int(rest[rest.index("--votes") + 1]) if "--votes" in rest and rest.index("--votes") + 1 < len(rest) else 3
    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = list(ex.map(ask, [c for c in cases for _ in range(votes)]))
    got = []
    for i in range(len(cases)):
        answers = raw[i * votes:(i + 1) * votes]
        got.append(max(answers, key=answers.count))  # the majority answer per case (cheap models vary run to run)
    misses = [{"id": c["id"], "expected": c["expected"], "got": g or "(no answer)"}
              for c, g in zip(cases, got) if g != c["expected"]]
    score = len(cases) - len(misses)
    print("autonomy-drill: %d/%d on model %s (majority of %d per case)" % (score, len(cases), model, votes))
    for m in misses:
        print("- MISS %(id)s: expected %(expected)s, got %(got)s" % m)
    atomic_write(os.path.join(FLAGS, "autonomy-drill.json"), json.dumps(
        {"at": now(), "model": model, "score": score, "total": len(cases), "misses": misses}, indent=1))
    return 0 if not misses else 1


def cmd_decided(rest):
    session = ""
    if "--session" in rest and rest.index("--session") + 1 < len(rest):
        i = rest.index("--session")
        session = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    text = " ".join(rest).strip()
    if not text:
        print('usage: cos decided "<what was decided and done | source | undo>" [--session ID]')
        return 2
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "session": session or session_id_env(), "hook": "cos", "type": "decided", "decision": "decided",
           "summary": " ".join(text.split())[:160]}
    os.makedirs(FLAGS, exist_ok=True)
    with open(os.path.join(FLAGS, "ask-ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print("logged")
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        return cmd_init()
    if cmd == "add-project":
        rt = "vp"
        if "--reports-to" in rest:
            i = rest.index("--reports-to")
            rt = rest[i + 1] if i + 1 < len(rest) else ""
            rest = rest[:i] + rest[i + 2:]
        return cmd_add_project(" ".join(rest), rt)
    if cmd == "lesson":
        check = None
        if "--check" in rest:
            i = rest.index("--check")
            check = tuple(rest[i + 1:i + 3]) if len(rest) >= i + 3 else ("", "")
            rest = rest[:i] + rest[i + 3:]
        return cmd_lesson(rest[0] if rest else "", " ".join(rest[1:]), check)
    if cmd == "lessons":
        return cmd_lessons(int(rest[0]) if rest and rest[0].isdigit() else 20)
    if cmd == "learn-due":
        return cmd_learn_due(force="--now" in rest)
    if cmd == "savings":
        return cmd_savings(rest)
    if cmd == "list-coos":
        return cmd_list_coos()
    if cmd == "layout":
        return cmd_layout()
    if cmd == "sidebar":
        return cmd_sidebar()
    if cmd == "status":
        return cmd_status()
    if cmd == "precheck":
        return cmd_precheck(rest)
    if cmd == "autonomy-drill":
        return cmd_autonomy_drill(rest)
    if cmd == "decided":
        return cmd_decided(rest)
    if cmd == "overlay":
        return cmd_overlay(rest)
    if cmd in ("tick-check", "tick-peek", "tick-complete"):
        return cmd_tick(cmd.split("-", 1)[1])
    if cmd == "submit" and rest:
        to = None
        if "--to" in rest:
            i = rest.index("--to")
            if i + 1 >= len(rest):
                print("usage: cos submit <job.md> [--to <machine>]")
                return 2
            to = rest[i + 1]
            rest = rest[:i] + rest[i + 2:]
        if not rest or not os.path.isfile(rest[0]):
            print("usage: cos submit <job.md> [--to <machine>]")
            return 2
        return cmd_submit(rest[0], to)
    if cmd == "run-jobs":
        return cmd_run_jobs(once="--all" not in rest)
    if cmd == "merge-briefs":
        return cmd_merge_briefs()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
