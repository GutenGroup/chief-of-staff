#!/usr/bin/env python3
"""Stop: block a turn that ends on an untagged offer or question, once (docs/AUTONOMY.md section 7)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import autonomy_common as A
except Exception:
    sys.exit(0)

OFFER = re.compile(r"want me to|shall i\b|should i\b|would you like|do you want|let me know if|say go\b|ok to proceed",
                   re.I)


def handler(data, session):
    msg = str(data.get("last_assistant_message") or "")
    tail = msg[-300:]
    closing_q = re.sub(r"[\s\"'`*_)\]>]+$", "", tail).endswith("?")
    offer = bool(OFFER.search(tail)) or closing_q
    summary = tail[-120:]
    if data.get("stop_hook_active"):
        A.ledger(session, "stop-guard", "stop", "pass", summary, reason="stop-hook-active")
        return None
    for reason, hit in (("setup", not A.setup_done()), ("interview", A.interview_active())):
        if hit:
            A.ledger(session, "stop-guard", "stop", "pass", summary, reason=reason)
            return None
    if offer and not A.TAG_RX.search(tail):
        A.ledger(session, "stop-guard", "stop", "block", summary, tagged=False, reason="untagged-offer")
        return {"decision": "block", "reason": A.UNTAGGED}
    A.ledger(session, "stop-guard", "stop", "pass", summary, reason="no-offer" if not offer else "tagged")
    return None


if __name__ == "__main__":
    sys.exit(A.run("stop-guard", handler))
