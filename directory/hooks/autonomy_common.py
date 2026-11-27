"""Shared helpers for the three autonomy hooks (docs/AUTONOMY.md section 7). Standard library only.

Every hook: reads the hook JSON on stdin, fails open (any exception: exit 0 with no output), stops when
~/.claude/cos-autonomy-off exists, applies only to the sessions in scope, and logs one line to
~/.claude/needs-input/ask-ledger.jsonl.

Scope: `autonomy_scope` in ~/.claude/cos-config.yaml (or $COS_CONFIG).
  roles (default)  only the sessions listed in ~/.claude/needs-input/roles.json
  all              every session
roles.json schema (written by the Chief of Staff; session ids may carry the "local_" prefix or not):
  {"sessions": {"<session id>": "<role>"}}      e.g. {"sessions": {"local_ab12": "Chief of Staff"}}
A plain list of ids is accepted too: ["local_ab12", "cd34"].
"""
import datetime
import json
import os
import re
import sys

UNTAGGED = ("Autonomy contract (docs/AUTONOMY.md): only legal and money reach the owner. Research it in the knowledge "
            "sources, decide, do it, and report it under decided with an undo line. Sign-ins go through an existing "
            "session, SSO or a magic link.")
PACKET = ("Owner-ready packet required: Recommend, What you agree to, Checked, Verify (pre-filled values), "
          "Do it (one link to the final step, all fields filled), After, Time.")
TAG_RX = re.compile(r"\[(legal|money)\]", re.I)
PRECHECK_MAX_AGE = 15 * 60


def home():
    return os.path.expanduser("~")


def ni(*parts):
    return os.path.join(home(), ".claude", "needs-input", *parts)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_id(s):
    return re.sub(r"^local_", "", str(s or ""))


def id_variants(s):
    b = strip_id(s)
    return [v for v in dict.fromkeys([str(s or ""), b, "local_" + b]) if v and v != "local_"]


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def kill_switch():
    return os.path.exists(os.path.join(home(), ".claude", "cos-autonomy-off"))


def config_scope():
    path = os.path.expanduser(os.environ.get("COS_CONFIG") or "~/.claude/cos-config.yaml")
    try:
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^autonomy_scope\s*:\s*[\"']?(\w+)", line)
            if m:
                return m.group(1).lower()
    except OSError:
        pass
    return "roles"


def in_scope(session):
    if config_scope() == "all":
        return True
    roles = read_json(ni("roles.json"), {})
    ids = roles.get("sessions", roles) if isinstance(roles, dict) else roles
    keys = list(ids.keys()) if isinstance(ids, dict) else list(ids or [])
    have = {strip_id(k) for k in keys}
    # The hook input carries the CLI session id; the Chief of Staff lists desktop app ids (local_...), which the
    # desktop app passes to every hook as CLAUDE_CODE_HOST_SESSION_ID. Either one in roles.json puts the session in scope.
    cands = [session, os.environ.get("CLAUDE_CODE_HOST_SESSION_ID", "")]
    return any(c and strip_id(c) in have for c in cands)


def setup_done():
    st = read_json(ni("cos-state.json"), {})
    return isinstance(st, dict) and bool(st.get("setupDoneAt"))


def interview_active():
    return os.path.exists(ni("interview-active"))


def _atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def record_mode(session, mode):
    if not session or not mode:
        return
    path = ni("permission-modes.json")
    cur = read_json(path, {})
    if not isinstance(cur, dict):
        cur = {}
    cur[str(session)] = {"mode": str(mode), "at": now_iso()}
    if len(cur) > 200:  # keep the newest 200
        keep = sorted(cur.items(), key=lambda kv: str((kv[1] or {}).get("at", "")), reverse=True)[:200]
        cur = dict(keep)
    _atomic(path, json.dumps(cur, indent=1))


def ledger(session, hook, typ, decision, summary, **extra):
    row = {"ts": now_iso(), "session": session, "hook": hook, "type": typ, "decision": decision,
           "summary": " ".join(str(summary or "").split())[:160]}
    row.update(extra)
    path = ni("ask-ledger.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def run(hook, handler):
    """Run handler(data, session) -> dict|None. Prints its dict as JSON. Never raises, always exits 0."""
    try:
        try:
            data = json.load(sys.stdin)
        except Exception:
            return 0
        if not isinstance(data, dict) or kill_switch():
            return 0
        session = str(data.get("session_id") or "")
        try:
            record_mode(session, data.get("permission_mode"))
        except Exception:
            pass
        if not in_scope(session):
            return 0
        out = handler(data, session)
        if out:
            sys.stdout.write(json.dumps(out))
    except Exception:
        return 0
    return 0
