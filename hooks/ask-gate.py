#!/usr/bin/env python3
"""PreToolUse on AskUserQuestion: only [legal], [money] and one [big] packet reach the owner (docs/AUTONOMY.md section 7)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import autonomy_common as A
except Exception:
    sys.exit(0)


def texts(q):
    parts = [str(q.get("question") or ""), str(q.get("header") or "")]
    for o in q.get("options") or []:
        if isinstance(o, dict):
            parts += [str(o.get("label") or ""), str(o.get("description") or "")]
    return "\n".join(parts)


def precheck_fresh(session):
    for v in A.id_variants(session):
        try:
            if time.time() - os.path.getmtime(A.ni("precheck", v + ".json")) <= A.PRECHECK_MAX_AGE:
                return True
        except OSError:
            continue
    return False


def deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def handler(data, session):
    if data.get("tool_name") != "AskUserQuestion":
        return None
    qs = [q for q in ((data.get("tool_input") or {}).get("questions") or []) if isinstance(q, dict)]
    summary = qs[0].get("question") if qs else ""
    if not qs:
        A.ledger(session, "ask-gate", "ask", "allow", "no questions", tagged=False, reason="no-questions")
        return None
    for reason, hit in (("setup", not A.setup_done()), ("interview", A.interview_active())):
        if hit:
            A.ledger(session, "ask-gate", "ask", "allow", summary, tagged=False, reason=reason)
            return None
    tagged = all(A.TAG_RX.search(str(q.get("question") or "") + " " + str(q.get("header") or "")) for q in qs)
    if not tagged:
        A.ledger(session, "ask-gate", "ask", "deny", summary, tagged=False, reason="untagged")
        return deny(A.UNTAGGED)
    complete, bigs = True, 0
    for q in qs:
        t = texts(q).lower()
        head = str(q.get("question") or "") + " " + str(q.get("header") or "")
        # [big] only: the dialog itself is the final step, so it carries Undo instead of a link.
        big = {m.lower() for m in A.TAG_RX.findall(head)} == {"big"}
        bigs += big
        if not ("recommend:" in t and "verify:" in t and ("undo:" if big else "https://") in t):
            complete = False
    if bigs > 1:
        complete = False
    fresh = precheck_fresh(session)
    if complete and fresh:
        A.ledger(session, "ask-gate", "ask", "allow", summary, tagged=True, reason="packet")
        return None
    reason = (A.BIG_PACKET if bigs else A.PACKET) + ("" if fresh else " Run cos precheck first.")
    A.ledger(session, "ask-gate", "ask", "deny", summary, tagged=True,
             reason="no-precheck" if complete else "incomplete-packet")
    return deny(reason)


if __name__ == "__main__":
    sys.exit(A.run("ask-gate", handler))
