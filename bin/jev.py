#!/usr/bin/env python3
"""Optional Jev (TypeSafe) decision helper for the Chief of Staff, the Production VP and COOs.

Jev is a small, fast model that answers typed questions with calibrated probabilities. The roles ask it four
questions before they act. Without a key every call prints {"skipped": "no key"} and exits 0, and the role uses its
own judgment, so the system works fully without Jev. See docs/JEV.md.

  jev.py route  --text "<task>" --options "Web COO,Mobile COO,Production VP"
  jev.py effort --text "<task>"
  jev.py safe   --text "<action and its context>" [--reversible]
  jev.py retry  --text "<what failed, how often, the error>"

Prints one JSON line. Key: TYPESAFE_API_KEY in the environment, else a TYPESAFE_API_KEY= line in
~/.claude/typesafe-api.env (mode 600). Never put the key in git or in a prompt.
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"  # pinned on purpose: a model change is a release, not a surprise
TIMEOUT = 8.0
SAFE_MIN = 0.8        # act alone only at P(safe) >= 0.8 AND reversible


def key():
    k = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if k:
        return k
    p = os.path.expanduser("~/.claude/typesafe-api.env")
    try:
        with open(p) as f:
            for line in f:
                if line.startswith("TYPESAFE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def ask(state, questions):
    """questions: {qid: instruction}. Returns ({qid: p}, None) or (None, reason)."""
    k = key()
    if not k:
        return None, "no key"
    body = json.dumps({"state": state, "model": MODEL,
                       "questions": {q: {"type": "noul", "instructions": t} for q, t in questions.items()}}).encode()
    req = urllib.request.Request(URL, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return None, "http %d" % e.code
    except Exception as e:  # network, timeout, bad JSON: fall back to judgment
        return None, type(e).__name__
    out = {}
    for q in questions:
        a = (resp.get("answers") or {}).get(q)
        v = a.get("noul") if isinstance(a, dict) else a
        try:
            out[q] = round(float(v), 3)
        except (TypeError, ValueError):
            pass
    return (out, None) if out else (None, "no answers")


def route(text, options):
    qs = {"o%d" % i: "The task is best handled by %s." % o for i, o in enumerate(options)}
    p, err = ask(text, qs)
    if err:
        return {"skipped": err}
    best = max(p, key=p.get)
    return {"route": options[int(best[1:])], "p": p[best],
            "all": {options[int(q[1:])]: v for q, v in p.items()}}


def effort(text):
    p, err = ask(text, {
        "spec": "The task is clearly specified: what done looks like is stated or obvious.",
        "judgment": "The task needs design, architecture or judgment, not just execution.",
        "mechanical": "The task is mechanical: search, status, a small edit or boilerplate.",
    })
    if err:
        return {"skipped": err}
    if p.get("spec", 1) < 0.3 and p.get("mechanical", 0) < 0.6:
        level, why = "ask", "underspecified: get the spec first, more effort would only add guesses"
    elif p.get("judgment", 0) >= 0.6:
        level, why = "medium", "judgment work"
    elif p.get("mechanical", 0) >= 0.6:
        level, why = "low", "mechanical work"
    else:
        level, why = "low", "default: spend effort on the spec and the verify, not the build"
    return {"effort": level, "why": why, "p": p}


def safe(text, reversible):
    p, err = ask(text, {"safe": "Taking this action now, without asking the owner, is safe and is what the owner wants."})
    if err:
        return {"skipped": err}
    ok = p["safe"] >= SAFE_MIN and reversible
    return {"act_alone": ok, "p_safe": p["safe"], "reversible": reversible,
            "why": "safe and reversible" if ok else ("irreversible: owner decides" if not reversible
                                                      else "P(safe) below %.1f: ask the owner" % SAFE_MIN)}


def retry(text):
    p, err = ask(text, {
        "again": "Retrying the same approach will succeed.",
        "human": "Only the owner can unblock this (a login, a decision, a payment, a physical step).",
    })
    if err:
        return {"skipped": err}
    return {"stop_retry": p.get("again", 1) < 0.3, "ask_human": p.get("human", 0) >= 0.6, "p": p}


def main(argv):
    if not argv or argv[0] not in ("route", "effort", "safe", "retry"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]

    def opt(name):
        return rest[rest.index(name) + 1] if name in rest and rest.index(name) + 1 < len(rest) else ""

    text = opt("--text")
    if not text:
        print('usage: jev.py %s --text "<state>"' % cmd)
        return 2
    if cmd == "route":
        options = [o.strip() for o in opt("--options").split(",") if o.strip()]
        if len(options) < 2:
            print("usage: jev.py route --text ... --options \"A,B[,C]\"")
            return 2
        out = route(text, options)
    elif cmd == "effort":
        out = effort(text)
    elif cmd == "safe":
        out = safe(text, "--reversible" in rest)
    else:
        out = retry(text)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
