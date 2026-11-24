#!/bin/bash
# UserPromptSubmit: drop a peer (cross-session) message whose body is empty or only a
# bare slash command, e.g. "/loop". A peer cannot run our slash commands, and the desktop
# app can re-deliver such a message on a timer under changing sender names. Blocking stops
# the wasted turn and the reply loop. "/chief-of-staff" alone is let through: the Workspace
# panel uses it to wake the Chief of Staff session.
# Kill switch: touch ~/.claude/peer-bare-command-drop-off
[ -f "$HOME/.claude/peer-bare-command-drop-off" ] && exit 0
python3 -c '
import json, re, sys
try:
    p = json.load(sys.stdin).get("prompt", "")
except Exception:
    sys.exit(0)
m = re.search(r"<cross-session-message[^>]*>(.*?)</cross-session-message>", p, re.S)
if not m:
    sys.exit(0)
body = m.group(1).strip()
if body == "/chief-of-staff":
    sys.exit(0)  # Workspace panel wake-up for the Chief of Staff
if body == "" or re.fullmatch(r"/[\w:.-]+", body):
    print(json.dumps({"decision": "block",
        "reason": "Dropped a peer message that was empty or a bare slash command (%r). Peers cannot run slash commands here." % body[:60]}))
'
exit 0
