"""Tests for bin/cos.py. Each test runs cos.py in a scratch HOME, so nothing on the real machine is touched.
Run: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COS = os.path.join(HERE, "bin", "cos.py")


class CosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        os.makedirs(os.path.join(self.home, ".claude", "needs-input"))
        self.cfg = os.path.join(self.home, ".claude", "cos-config.yaml")
        fake = os.path.join(self.home, "fake-claude")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\ncat >/dev/null\necho \"fake run: $* pwd=$(pwd -P)\"\n")
        os.chmod(fake, 0o755)
        with open(self.cfg, "w") as f:
            f.write('owner_name: "Alex"\ndata_root: %s/data\nprojects:\n  - Acme\nfleet_mode: single\n'
                    'machine_id: box1\nclaude_bin: %s\n' % (self.home, fake))

    def tearDown(self):
        self.tmp.cleanup()

    def run_cos(self, *args, ok=True):
        env = dict(os.environ, HOME=self.home)
        env.pop("COS_CONFIG", None)
        env.pop("COS_DATA_ROOT", None)
        r = subprocess.run([sys.executable, COS] + list(args), capture_output=True, text=True, env=env)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def p(self, *parts):
        return os.path.join(self.home, *parts)

    def test_init_creates_files_and_is_idempotent(self):
        self.run_cos("init")
        charter = self.p("data", "Context", "Acme", "COO_CHARTER.md")
        self.assertTrue(os.path.exists(charter))
        self.assertIn("Acme COO charter", open(charter).read())
        self.assertTrue(os.path.exists(self.p("data", "fleet", "coo-reports", "README.md")))
        self.assertTrue(os.path.isdir(self.p("data", "fleet", "inbox", "box1")))
        side = json.load(open(self.p(".claude", "needs-input", "sidebar.json")))
        self.assertEqual(side["tiers"][0]["sections"], ["Acme"])
        with open(charter, "a") as f:
            f.write("owner edit\n")
        out = self.run_cos("init").stdout
        self.assertIn("created: 0 file(s)", out)
        self.assertIn("owner edit", open(charter).read())

    def test_add_project_updates_config_and_sidebar(self):
        self.run_cos("init")
        self.run_cos("add-project", "Side Project")
        self.assertIn("  - Side Project", open(self.cfg).read())
        self.assertIn("  - Acme", open(self.cfg).read())
        self.assertTrue(os.path.exists(self.p("data", "Context", "Side_Project", "GOALS.md")))
        side = json.load(open(self.p(".claude", "needs-input", "sidebar.json")))
        self.assertEqual(side["tiers"][0]["sections"], ["Acme", "Side Project"])
        self.run_cos("add-project", "Side Project")
        self.assertEqual(open(self.cfg).read().count("Side Project"), 1)

    def test_tick_guard(self):
        self.run_cos("init")
        self.assertTrue(self.run_cos("tick-check").stdout.startswith("RUN:"))
        self.assertTrue(self.run_cos("tick-complete").stdout.startswith("COMPLETE:"))
        self.assertTrue(self.run_cos("tick-check").stdout.startswith("SKIP:"))
        self.assertTrue(self.run_cos("tick-peek").stdout.startswith("SKIP:"))
        # a new inbox file runs at once
        with open(self.p("data", "fleet", "inbox", "box1", "note.md"), "w") as f:
            f.write("hello")
        self.assertTrue(self.run_cos("tick-peek").stdout.startswith("RUN:"))
        # peek records nothing
        self.assertFalse(os.path.exists(self.p(".claude", "needs-input", "cos-pass.json.pending")))

    def test_tick_complete_without_start_records_nothing(self):
        self.assertIn("nothing recorded", self.run_cos("tick-complete").stdout)
        self.assertTrue(self.run_cos("tick-peek").stdout.startswith("RUN:"))

    def test_tick_window_expires(self):
        self.run_cos("init")
        self.run_cos("tick-check")
        self.run_cos("tick-complete")
        st = self.p(".claude", "needs-input", "cos-pass.json")
        d = json.load(open(st))
        d["completed"] = time.time() - 400
        json.dump(d, open(st, "w"))
        self.assertTrue(self.run_cos("tick-peek").stdout.startswith("RUN:"))

    def write_job(self, body):
        path = self.p("job.md")
        with open(path, "w") as f:
            f.write(body)
        return path

    def test_submit_validates_class(self):
        self.run_cos("init")
        r = self.run_cos("submit", self.write_job("type: job\nproject: Acme\n\nBrief: do it\n"), ok=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("class must be", r.stdout)
        r = self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: design\n\nBrief: x\n"), ok=False)
        self.assertIn("judgment: design", r.stdout)
        r = self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: search\n\nFind the thing.\n"))
        self.assertIn("QUEUED:", r.stdout)

    def test_run_jobs_runs_and_reports(self):
        self.run_cos("init")
        self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: search\n\nFind the thing.\n"))
        out = self.run_cos("run-jobs").stdout
        self.assertIn("done", out)
        rep = open(self.p("data", "fleet", "coo-reports", "jobs", "Acme.box1.md")).read()
        self.assertIn("DONE", rep)
        self.assertIn("--model haiku", rep)
        self.assertEqual(len(os.listdir(self.p("data", "fleet", "inbox", "box1", "done"))), 1)

    def test_worker_tools_are_locked_down(self):
        self.run_cos("init")
        self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: code\nmodel: opus\n\nFix it.\n"))
        self.run_cos("run-jobs")
        rep = open(self.p("data", "fleet", "coo-reports", "jobs", "Acme.box1.md")).read()
        allowed = rep.split("--allowedTools ", 1)[1].split(" --disallowedTools", 1)[0]
        self.assertIn("Edit", allowed)
        for bad in ("git push", "python3", "npx", "npm", "make", "WebFetch", "WebSearch", "cat:", "curl"):
            self.assertNotIn(bad, allowed)
        self.assertIn("--model sonnet", rep)  # a job cannot raise its own model
        self.assertNotIn("Edit,", allowed)  # file tools are scoped to the job folder, never bare
        self.assertIn("Edit(//", allowed)
        self.assertIn("/.claude/**", rep.split("--disallowedTools ", 1)[1])

    def test_job_repo_must_be_under_allowed_roots(self):
        code = self.p("code", "repo1")
        os.makedirs(code)
        outside = self.p("elsewhere")
        os.makedirs(outside)
        with open(self.cfg, "a") as f:
            f.write("job_repo_roots:\n  - %s\n" % self.p("code"))
        self.run_cos("init")
        self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: search\nrepo: %s\n\nLook.\n" % outside))
        self.run_cos("run-jobs")
        self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: search\nrepo: %s\n\nLook.\n" % code))
        self.run_cos("run-jobs")
        rep = open(self.p("data", "fleet", "coo-reports", "jobs", "Acme.box1.md")).read()
        self.assertIn("pwd=%s" % os.path.realpath(code), rep)
        self.assertNotIn("pwd=%s" % os.path.realpath(outside), rep)
        self.assertIn("pwd=%s" % os.path.realpath(self.p("data")), rep)

    def test_submit_target_cannot_escape_inbox(self):
        self.run_cos("init")
        r = self.run_cos("submit", self.write_job("type: job\nproject: Acme\nclass: search\n\nx\n"), "--to", "../../evil")
        self.assertNotIn("..", r.stdout.split("QUEUED:")[-1])
        self.assertFalse(os.path.exists(self.p("data", "evil")))

    def test_submit_bad_args(self):
        self.run_cos("init")
        self.assertEqual(self.run_cos("submit", "--to", ok=False).returncode, 2)
        job = self.write_job("type: job\nproject: Acme\nclass: search\n\nx\n")
        r = self.run_cos("submit", "--to", "box2", job)
        self.assertIn("inbox/box2/", r.stdout)

    def test_run_jobs_kill_switch(self):
        self.run_cos("init")
        open(self.p(".claude", "cos-jobs-off"), "w").close()
        self.assertIn("kill switch", self.run_cos("run-jobs").stdout)

    def test_merge_briefs(self):
        self.run_cos("init")
        st = self.p("data", "fleet", "status")
        json.dump({"headline": "h1", "needsOwner": [{"id": "x", "ask": "q"}]},
                  open(os.path.join(st, "chief-of-staff-box1-brief.json"), "w"))
        self.run_cos("merge-briefs")
        fb = json.load(open(os.path.join(st, "fleet-brief.json")))
        self.assertEqual(fb["machines"][0]["machine"], "box1")
        self.assertEqual(fb["needsOwner"][0]["machine"], "box1")

    def run_jev(self, *args):
        env = dict(os.environ, HOME=self.home)
        env.pop("TYPESAFE_API_KEY", None)
        jev = os.path.join(os.path.dirname(COS), "jev.py")
        return subprocess.run([sys.executable, jev] + list(args), capture_output=True, text=True, env=env)

    def test_jev_without_key_is_skipped(self):
        for cmd in (["route", "--text", "t", "--options", "A,B"], ["effort", "--text", "t"],
                    ["safe", "--text", "t", "--reversible"], ["retry", "--text", "t"]):
            r = self.run_jev(*cmd)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {"skipped": "no key"})
        self.assertIn("no key", self.run_cos("status").stdout)

    def test_jev_usage_errors(self):
        self.assertEqual(self.run_jev().returncode, 2)
        self.assertEqual(self.run_jev("safe").returncode, 2)
        self.assertEqual(self.run_jev("route", "--text", "t", "--options", "A").returncode, 2)

    def test_clear_thresholds_from_config(self):
        with open(self.cfg, "a") as f:
            f.write("clear_at_vp: 300000\nclear_at_coo: 1000\n")
        out = self.run_cos("status").stdout
        self.assertIn("Production VP 300000", out)
        self.assertIn("COOs 50000", out)  # floor
        self.assertIn("Chief of Staff 150000", out)

    def test_overlay_none_by_default(self):
        self.assertIn("overlay: none", self.run_cos("status").stdout)

    def test_overlay_listed_from_config(self):
        ov = self.p("my-overlay")
        os.makedirs(ov)
        for name in ("project-coo.md", "chief-of-staff.md", "notes.txt"):
            open(os.path.join(ov, name), "w").close()
        with open(self.cfg, "a") as f:
            f.write("overlay_dir: %s\n" % ov)
        out = self.run_cos("status").stdout
        self.assertIn("overlay: %s (chief-of-staff.md, project-coo.md)" % os.path.abspath(ov), out)

    def test_overlay_init_creates_files_sets_config_never_overwrites(self):
        out = self.run_cos("overlay", "init").stdout
        ov = self.p(".claude", "cos-overlay")
        self.assertIn("created: 4 file(s)", out)
        for name in ("chief-of-staff.md", "project-coo.md", "production-vp.md", "helm.md"):
            self.assertIn("<!--", open(os.path.join(ov, name)).read())
        self.assertIn("overlay_dir: %s\n" % ov, open(self.cfg).read())
        with open(os.path.join(ov, "helm.md"), "w") as f:
            f.write("my rule\n")
        os.remove(os.path.join(ov, "project-coo.md"))
        out = self.run_cos("overlay", "init").stdout
        self.assertIn("created: 1 file(s) (project-coo.md)", out)
        self.assertEqual(open(os.path.join(ov, "helm.md")).read(), "my rule\n")
        self.assertEqual(open(self.cfg).read().count("overlay_dir:"), 1)
        self.assertIn("overlay: %s (chief-of-staff.md, helm.md, production-vp.md, project-coo.md)" % ov,
                      self.run_cos("status").stdout)

    def test_overlay_init_is_private_and_never_points_at_shared(self):
        shared = self.p("team-rules")
        with open(self.cfg, "a") as f:
            f.write("overlay_dir: %s\n" % shared)
        before = open(self.cfg).read()
        out = self.run_cos("overlay", "init").stdout
        self.assertTrue(os.path.exists(self.p(".claude", "cos-overlay", "chief-of-staff.md")))
        self.assertFalse(os.path.exists(shared))
        self.assertIn("left unchanged", out)
        self.assertEqual(open(self.cfg).read(), before)

    def test_overlay_bad_usage(self):
        self.assertEqual(self.run_cos("overlay", ok=False).returncode, 2)

    def test_plugin_version_matches_version_file(self):
        root = os.path.dirname(os.path.dirname(COS))
        v = open(os.path.join(root, "VERSION")).read().strip()
        pj = json.load(open(os.path.join(root, ".claude-plugin", "plugin.json")))
        self.assertEqual(pj["version"], v, "plugin.json version must equal VERSION (installs report plugin.json)")
        for skill in ("chief-of-staff", "project-coo", "production-vp", "helm"):
            text = open(os.path.join(root, "skills", skill, "SKILL.md")).read()
            self.assertIn("**Version:** %s" % v, text, skill)

    def test_vp_seeded_with_checks(self):
        self.run_cos("init")
        les = open(self.p("data", "Context", "Production_VP", "coo", "LESSONS.md")).read()
        self.assertIn("CHECK text-question", les)
        self.assertIn("CHECK no-handtyped-timestamp", les)


if __name__ == "__main__":
    unittest.main()
