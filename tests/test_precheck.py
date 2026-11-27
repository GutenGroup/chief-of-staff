"""Tests for `cos precheck`, `cos autonomy-drill --dry-run`, `cos status` and `cos decided` (scratch HOME).
Run: python3 -m unittest discover -s tests"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COS = os.path.join(HERE, "bin", "cos.py")


class PrecheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.ni = os.path.join(self.home, ".claude", "needs-input")
        os.makedirs(self.ni)
        self.notes = os.path.join(self.home, "notes")
        os.makedirs(self.notes)
        with open(os.path.join(self.home, ".claude", "cos-config.yaml"), "w") as f:
            f.write("data_root: %s/data\nprojects:\n  - Acme\nmachine_id: box1\nknowledge_sources:\n  - %s\n" % (self.home, self.notes))
        self.data = os.path.join(self.home, "data")
        os.makedirs(os.path.join(self.data, "Context", "Acme", "coo"))
        os.makedirs(os.path.join(self.data, "fleet", "coo-reports"))
        os.makedirs(os.path.join(self.data, "fleet", "comms"))
        self.today = datetime.date.today().isoformat()

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(text)

    def cos(self, *args, env=None, ok=True):
        e = dict(os.environ, HOME=self.home)
        for k in ("COS_CONFIG", "COS_DATA_ROOT", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
            e.pop(k, None)
        e.update(env or {})
        r = subprocess.run([sys.executable, COS] + list(args), capture_output=True, text=True, env=e, timeout=60)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_finds_hits_newest_first_and_writes_file(self):
        self.put(os.path.join(self.data, "DECISIONS.md"), "# Decisions\n- 2026-03-01 Refund policy: refunds over 100 need a check.\n- 2026-05-02 Refund policy: always refund duplicates.\n")
        self.put(os.path.join(self.notes, "policy.md"), "Vendor refund terms live here.\n")
        self.put(os.path.join(self.data, "fleet", "coo-reports", "Acme.md"), "## %s\nrefund policy handled for Acme\n" % self.today)
        r = self.cos("precheck", "refund policy", "--session", "local_abc")
        self.assertIn("hit(s)", r.stdout)
        lines = [l for l in r.stdout.splitlines() if l.startswith("- ")]
        self.assertGreaterEqual(len(lines), 3)
        self.assertIn(self.today, lines[0])
        self.assertIn("2026-05-02", lines[1])
        out = json.load(open(os.path.join(self.ni, "precheck", "local_abc.json")))
        self.assertEqual(out["topic"], "refund policy")
        self.assertEqual(out["hits"], len(lines))
        self.assertIn("at", out)
        self.assertTrue(out["top"])

    def test_no_hits_still_writes_file(self):
        r = self.cos("precheck", "zebra migration", env={"CLAUDE_SESSION_ID": "sess9"})
        self.assertIn("0 hit(s)", r.stdout)
        self.assertEqual(json.load(open(os.path.join(self.ni, "precheck", "sess9.json")))["hits"], 0)

    def test_default_session_unknown_and_old_reports_skipped(self):
        old = os.path.join(self.data, "fleet", "coo-reports", "Old.md")
        self.put(old, "## 2020-01-01\nrefund policy old entry\n")
        os.utime(old, (1, 1))
        r = self.cos("precheck", "refund policy")
        self.assertIn("0 hit(s)", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.ni, "precheck", "unknown.json")))

    def test_lessons_and_charter_searched(self):
        self.put(os.path.join(self.data, "Context", "Acme", "COO_LESSONS.md"), "- 2026-04-01 over-ask: deploys on green are ours\n")
        self.put(os.path.join(self.data, "Context", "Acme", "COO_CHARTER.md"), "Closed: deploys on green need no ask\n")
        r = self.cos("precheck", "deploys green")
        self.assertIn("COO_LESSONS.md", r.stdout)
        self.assertIn("COO_CHARTER.md", r.stdout)

    def test_usage(self):
        self.assertEqual(self.cos("precheck", ok=False).returncode, 2)

    def test_drill_dry_run_validates_case_file(self):
        r = self.cos("autonomy-drill", "--dry-run")
        self.assertIn("25 cases ok", r.stdout)

    def test_case_file_shape(self):
        sys.path.insert(0, os.path.join(HERE, "bin"))
        env = dict(os.environ)
        os.environ["HOME"] = self.home
        try:
            import cos
            cases = cos.load_cases(os.path.join(HERE, "tests", "autonomy_cases.yaml"))
        finally:
            os.environ.clear()
            os.environ.update(env)
        self.assertEqual(len(cases), 25)
        self.assertEqual(sum(c["expected"] == "precheck first" for c in cases), 5)
        self.assertEqual(sum(c["expected"] == "packet[legal]" for c in cases), 2)
        self.assertEqual(sum(c["expected"] == "packet[money]" for c in cases), 2)
        self.assertEqual(cos.validate_cases(cases), [])
        self.assertEqual(cos.drill_answer("thinking... ANSWER: Precheck first"), "precheck first")
        self.assertEqual(cos.drill_answer("I would act."), "act")

    def test_status_prompts_line_and_bypass(self):
        r = self.cos("status")
        self.assertIn("running with prompts: the system will stop for approvals; switch to bypass for full autonomy", r.stdout)
        self.assertIn("autonomy: on", r.stdout)
        self.assertIn("autonomy scope: roles", r.stdout)
        self.put(os.path.join(self.home, ".claude", "settings.json"), json.dumps({"permissions": {"defaultMode": "bypassPermissions"}}))
        r = self.cos("status")
        self.assertIn("permission mode: bypassPermissions", r.stdout)
        self.assertNotIn("running with prompts", r.stdout)
        self.put(os.path.join(self.ni, "permission-modes.json"), json.dumps({"s1": {"mode": "default", "at": "2026-11-01T00:00:00Z"}}))
        r = self.cos("status", env={"CLAUDE_SESSION_ID": "local_s1"})
        self.assertIn("permission mode: default", r.stdout)
        self.assertIn("running with prompts", r.stdout)
        open(os.path.join(self.home, ".claude", "cos-autonomy-off"), "w").close()
        self.assertIn("autonomy: off", self.cos("status").stdout)

    def test_sidebar_carries_decided_and_permission_mode(self):
        self.put(os.path.join(self.ni, "cos-brief.json"), json.dumps({"decided": [{"title": "n%d" % i} for i in range(8)]}))
        self.cos("sidebar")
        sb = json.load(open(os.path.join(self.ni, "sidebar.json")))
        self.assertEqual(len(sb["decided"]), 5)
        self.assertEqual(sb["permissionMode"], "default")
        self.assertIn("running with prompts", sb["permissionLine"])

    def test_decided_logs_to_ledger_and_review_counts_it(self):
        self.cos("decided", "merged the fix | PR 12 | revert abc", "--session", "s1")
        rows = [json.loads(l) for l in open(os.path.join(self.ni, "ask-ledger.jsonl"))]
        self.assertEqual(rows[-1]["type"], "decided")
        sys.path.insert(0, os.path.join(HERE, "bin"))
        env = dict(os.environ)
        os.environ["HOME"] = self.home
        try:
            import coo_weekly_review as W
            lines = W.ledger_metrics(path=os.path.join(self.ni, "ask-ledger.jsonl"))
        finally:
            os.environ.clear()
            os.environ.update(env)
        self.assertIn("decided items logged: 1", "\n".join(lines))

    def test_single_mode_job_runner_works(self):
        job = os.path.join(self.home, "job.md")
        self.put(job, "---\nclass: read\nproject: Acme\n---\nsay hi\n")
        r = self.cos("submit", job, ok=False)
        self.assertIn(r.returncode, (0, 2), r.stdout)
        self.assertNotIn("single", r.stdout.lower())


if __name__ == "__main__":
    unittest.main()
