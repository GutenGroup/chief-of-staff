#!/usr/bin/env python3
"""coo_knowledge_test.py: does a COO actually know its project?

  coo_knowledge_test.py <Project>|--all                 STRUCTURAL pre-check (fast, free): the 5 Q/A lines in KNOWLEDGE.md
                                                        have an existing SRC and a verbatim QUOTE. It proves the index is
                                                        sound, not that the COO knows anything.
  coo_knowledge_test.py <Project>|--all --real [opts]   REAL test: one model answers questions using ONLY that COO's five
                                                        files; a DIFFERENT model grades each answer against the cited source.

Real-test options:
  --questions N    questions per COO (default 4); picked from KNOWLEDGE section 2 and PERSONA section 3, rotating by --period
  --period P       rotation seed, default the ISO week (YYYY-Www); the monthly run passes YYYY-MM
  --write          append one row to SCORECARD section 4 (public COOs only)
  --inject-wrong K replace the answer to question K with a deliberately false one (proves the grader marks it wrong; implies no --write)
  --answerer M / --grader M   claude models (default claude-haiku-5-5 answers, claude-sonnet-5-5 grades; never the same model)
Questions are written by the grader model from a fact line, so the answerer never sees the fact. The test uses the Claude CLI (`claude -p`).
A private COO (~/.claude/coo-private.json) prints
aggregates only and writes nothing to git, shared folders or logs.
Exit 0 = every COO passed, 1 = a FAIL or a gap, 2 = bad input, 3 = the test model could not be reached.
"""
import datetime
import json
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from coo_lesson_check import ROOT, PROJECTS, five_files, missing_files, private_coos, FIVE  # noqa: E402

LINE = re.compile(r'^\s*-\s*Q(\d+):\s*(?P<q>.+?)\s*\|\|\s*A:\s*(?P<a>.+?)\s*\|\|\s*SRC:\s*(?P<src>.+?)\s*\|\|\s*QUOTE:\s*"(?P<quote>.+)"\s*$')
FACT = re.compile(r"^-\s+(?P<t>.+?)\s*\[source:\s*(?P<s>[^\]]+?)\s*\]\s*$")
CLOSED = re.compile(r"^-\s+(?P<d>[^—]+?)\s+—\s+(?P<t>.+?)\s+—\s+source:\s+(?P<s>\S+)\s*$")
from cosconfig import CLAUDE_BIN  # noqa: E402
CLAUDE = os.environ.get("CLAUDE_BIN", CLAUDE_BIN)


def norm(t):
    return re.sub(r"\s+", " ", t).strip().lower()


# --------------------------------------------------------------- structural pre-check
def structural(key):
    p = five_files(key)["KNOWLEDGE"]
    if not os.path.exists(p):
        print(f"{key}: [structural] no {os.path.basename(p)}")
        return 1
    passed, seen, bad = 0, set(), []
    for line in open(p, encoding="utf-8"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        q = norm(m["q"])
        src = os.path.join(ROOT, m["src"])
        ok = q not in seen and os.path.isfile(src)
        seen.add(q)
        if ok:
            ok = norm(m["quote"]) in norm(open(src, encoding="utf-8", errors="replace").read())
        if ok:
            passed += 1
        else:
            bad.append(m["q"][:60])
    status = "PASS" if passed >= 5 else "FAIL"
    print(f"{key}: [structural pre-check] {status} {passed} verified answers" + (f"; failed: {bad}" if bad else ""))
    return 0 if passed >= 5 else 1


# --------------------------------------------------------------- real test
def llm(model, prompt, timeout=240):
    cmd = [CLAUDE, "-p", "--model", model, "--effort", "low", "--no-session-persistence", "--output-format", "text",
           "--disallowedTools", "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch"]
    # a minimal environment: the user's Claude Code login, no inherited overrides or keys
    home = os.path.expanduser("~")
    env = {"HOME": home, "LANG": "en_US.UTF-8",
           "PATH": home + "/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, env=env)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out or out.startswith("Failed to authenticate"):
        raise RuntimeError("claude CLI call failed: " + (out or r.stderr or "no output")[:120])
    return out


ENGINE = {"mode": "claude"}


def ask(model, prompt):
    return llm(model, prompt)


def load_facts(paths):
    """[(fact text, source path)] from KNOWLEDGE section 2 and PERSONA section 3."""
    out = []
    kt = open(paths["KNOWLEDGE"], encoding="utf-8").read()
    sec = re.search(r"^##\s*2\.[^\n]*\n(.*?)(?=^##\s)", kt, re.M | re.S)
    for line in (sec.group(1) if sec else "").splitlines():
        m = FACT.match(line.strip())
        if m:
            out.append((m["t"].strip(), m["s"].strip()))
    pt = open(paths["PERSONA"], encoding="utf-8").read()
    sec = re.search(r"^##\s*3\.[^\n]*\n(.*?)(?=^##\s)", pt, re.M | re.S)
    for line in (sec.group(1) if sec else "").splitlines():
        m = CLOSED.match(line.strip())
        if m and "NOT YET ESTABLISHED" not in line:
            out.append((f"{m['d'].strip()}: {m['t'].strip()}", m["s"].strip()))
    return [(t, s) for t, s in out if os.path.isfile(os.path.join(ROOT, s)) and len(t) > 25]


def real_test(paths, label, n, period, answerer, grader, inject=None):
    facts = load_facts(paths)
    if len(facts) < n:
        return {"label": label, "score": 0, "n": len(facts), "rows": [], "gaps": [f"only {len(facts)} testable facts, need {n}"], "error": True}
    rnd = random.Random(f"{label}|{period}")
    picks = rnd.sample(facts, n)
    corpus = "\n\n".join(f"=== {os.path.basename(paths[k])} ===\n{open(paths[k], encoding='utf-8').read()}" for k in FIVE)
    rows, gaps, score = [], [], 0
    for i, (fact, src) in enumerate(picks, 1):
        q = ask(grader, "Write ONE short question (max 25 words) whose correct answer is exactly the fact below. "
                        "Do not include the answer or its distinctive words in the question. Output only the question.\n\nFACT: " + fact)
        q = q.strip().strip('"')
        ans = ask(answerer, "You are a COO. Answer ONLY from the five files below, in at most 2 sentences, and name the file you used. "
                            "If the files do not say, answer exactly: NOT IN MY FILES.\n\n" + corpus + "\n\nQUESTION: " + q)
        if inject == i:
            ans = "The files say it is 42 and the owner is Mallory (file: PERSONA.md)."
        srctext = open(os.path.join(ROOT, src), encoding="utf-8", errors="replace").read()[:60000]
        g = ask(grader, "Grade an answer against the cited source. Reply with ONE JSON object only: "
                        '{"verdict":"correct"|"wrong"|"unsupported","gap":"<one line: what the COO did not know or got wrong, or empty>"}. '
                        "correct = the core fact the question asks about matches the source and nothing is contradicted (extra harmless detail is fine). wrong = the core fact is missing, contradicted or invented. "
                        "unsupported = says it does not know or the point is missing.\n\n"
                        f"SOURCE ({src}):\n{srctext}\n\nQUESTION: {q}\nANSWER: {ans}")
        m = re.search(r"\{.*\}", g, re.S)
        try:
            j = json.loads(m.group(0)) if m else {}
        except ValueError:
            j = {}
        v = j.get("verdict", "wrong")
        if v == "correct":
            score += 1
        else:
            gaps.append(f"{src}: {j.get('gap') or 'answer not supported'}")
        rows.append({"q": q, "a": ans, "src": src, "verdict": v, "gap": j.get("gap", "")})
    return {"label": label, "score": score, "n": n, "rows": rows, "gaps": gaps, "error": False}


def write_scorecard(key, res, engine):
    p = five_files(key)["SCORECARD"]
    txt = open(p, encoding="utf-8").read()
    if "## 4. Knowledge test log" not in txt:
        txt = txt.rstrip("\n") + "\n\n## 4. Knowledge test log\n| date | engine | score | gaps |\n|---|---|---|---|\n"
    gap = "; ".join(g[:120] for g in res["gaps"]) or "none"
    row = f"| {datetime.date.today().isoformat()} | {engine} | {res['score']}/{res['n']} {'PASS' if res['score'] == res['n'] else 'FAIL'} | {gap.replace('|', '/')} |"
    if not txt.endswith("\n"):
        txt += "\n"
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt + row + "\n")


def run_real(key, o):
    paths = five_files(key)
    miss = missing_files(key)
    if miss:
        print(f"{key}: [real] INCOMPLETE, missing {', '.join(miss)}")
        return 1
    try:
        res = real_test(paths, key, o["n"], o["period"], o["answerer"], o["grader"], o["inject"])
    except Exception as e:  # engine down is not a COO failure
        print(f"{key}: [real test] ENGINE UNAVAILABLE ({str(e)[:100]}); not scored, not written")
        return 3
    eng = "claude"
    for i, r in enumerate(res["rows"], 1):
        print(f"  Q{i} [{r['verdict']}] {r['q'][:100]}\n      A: {r['a'][:140]}\n      src: {r['src']}" + (f"\n      gap: {r['gap'][:140]}" if r["gap"] else ""))
    ok = (not res["error"]) and res["score"] == res["n"]
    print(f"{key}: [real test, engine={eng}, {o['answerer']} answers, {o['grader']} grades] {'PASS' if ok else 'FAIL'} {res['score']}/{res['n']}" + (f"; gaps: {res['gaps']}" if res["gaps"] else ""))
    if o["write"] and not o["inject"] and not res["error"]:
        write_scorecard(key, res, eng + ":" + f"{o['answerer'].split('-')[1]}/{o['grader'].split('-')[1]}")
    return 0 if ok else 1


def run_private_real(c, o):
    """Local-only COO: aggregate result only, never a name, never a file write outside the COO's own local folder."""
    d = os.path.join(c["root"], "coo")
    paths = {n: os.path.join(d, f"{n}.md") for n in FIVE}
    if any(not os.path.isfile(p) for p in paths.values()):
        return None
    base = os.path.dirname(os.path.abspath(c["root"]))
    save = ROOT
    res = real_test(paths, "private", o["n"], o["period"], o["answerer"], o["grader"])
    return res


def main(argv):
    o = {"engine": "claude", "n": 4, "period": None, "write": False, "inject": None, "answerer": "claude-haiku-5-5", "grader": "claude-sonnet-5-5"}
    real = False
    args, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--real":
            real = True; i += 1
        elif a == "--write":
            o["write"] = True; i += 1
        elif a in ("--questions", "--period", "--inject-wrong", "--answerer", "--grader", "--engine"):
            k = {"--engine": "engine", "--questions": "n", "--period": "period", "--inject-wrong": "inject", "--answerer": "answerer", "--grader": "grader"}[a]
            o[k] = int(argv[i + 1]) if k in ("n", "inject") else argv[i + 1]; i += 2
        else:
            args.append(a); i += 1
    if not args:
        print(__doc__)
        return 2
    if o["answerer"] == o["grader"]:
        print("answerer and grader must be different models")
        return 2
    if not o["period"]:
        y, w, _ = datetime.date.today().isocalendar()
        o["period"] = f"{y}-W{w:02d}"
    allrun = args[0] == "--all"
    keys = list(PROJECTS) if allrun else args
    rc = 0
    for k in keys:
        if k not in PROJECTS:
            print(f"unknown project {k}; known: {', '.join(PROJECTS)}")
            return 2
        rc = max(rc, run_real(k, o) if real else structural(k))
    if allrun and real:
        pv = private_coos()
        if pv:
            res = [run_private_real(c, o) for c in pv]
            done = [r for r in res if r]
            fails = sum(1 for r in done if r["score"] != r["n"])
            print(f"private COOs: {len(done)} tested locally, {fails} failed (aggregate only)")
            rc = max(rc, 1 if fails else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
