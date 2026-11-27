#!/usr/bin/env python3
"""UserPromptSubmit: when the owner pushes back on an ask, tell the session to do it now and record the lesson."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import autonomy_common as A
except Exception:
    sys.exit(0)

SKIP = ("<cross-session-message", "<side-sessions-event", "<ci-monitor-event", "<<autonomous-loop")
SLASH_ONLY = re.compile(r"^/[\w:.-]+(\s+[\w:./-]+){0,3}\s*$")
PUSHBACK = re.compile(r"just do it|do it yourself|you do it|why are you asking|stop asking|don['’]?t ask me|"
                      r"you have access|not on me", re.I)
CONTEXT = ("The owner pushed back on an ask. Do it now, then record cos lesson <Role> 'over-ask: <class> is the "
           "system's to do' (with --check when it is visible as text).")


def handler(data, session):
    prompt = str(data.get("prompt") or "")
    s = prompt.strip()
    if not s or any(m in s for m in SKIP) or s.startswith("<<autonomous-loop") or SLASH_ONLY.match(s):
        return None
    m = PUSHBACK.search(s)
    if not m:
        A.ledger(session, "pushback-catcher", "prompt", "pass", s[:80])
        return None
    A.ledger(session, "pushback-catcher", "pushback", "inform", s[:120], match=m.group(0).lower())
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": CONTEXT}}


if __name__ == "__main__":
    sys.exit(A.run("pushback-catcher", handler))
