"""Tests for the Communication VP trust ramp in bin/comms.py (scratch HOME and data root, nothing real is touched).
Run: python3 -m unittest tests.test_comms_ramp   (or discover -s tests)"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMS = os.path.join(HERE, "bin", "comms.py")


class RampTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "cos-config.yaml"), "w") as f:
            f.write('owner_name: "Alex"\ndata_root: %s/data\nfleet_mode: single\nmachine_id: box1\n' % self.home)
        self.run_comms("init")
        d = os.path.join(self.home, "data", "Context", "Communication_VP", "comms")
        with open(os.path.join(d, "CONTACTS.md"), "a") as f:
            f.write("- Sam | team-chat | release notes\n")
        with open(os.path.join(d, "CHANNELS.md"), "a") as f:
            f.write("- team-chat | google_chat | spaces/AAAA | updates\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_comms(self, *args):
        env = dict(os.environ, HOME=self.home, COS_CONFIG=os.path.join(self.home, ".claude", "cos-config.yaml"),
                   COS_DATA_ROOT=os.path.join(self.home, "data"))
        r = subprocess.run([sys.executable, COMMS, *args], capture_output=True, text=True, env=env)
        return r.returncode, r.stdout.strip()

    def can(self, target, kind=None):
        args = ["can-send", target] + (["--kind", kind] if kind else [])
        code, out = self.run_comms(*args)
        self.assertEqual(code, 0, out)
        return out

    def test_relay_and_reply_send_always(self):
        self.assertEqual(self.can("Stranger", "relay"), "SEND")
        self.assertEqual(self.can("Stranger", "reply"), "SEND")

    def test_status_scheduling_answer_need_a_known_target(self):
        for k in ("status", "scheduling", "answer"):
            self.assertEqual(self.can("Sam", k), "SEND")
            self.assertEqual(self.can("team-chat", k), "SEND")
            self.assertTrue(self.can("Stranger", k).startswith("COS"))

    def test_money_and_legal_go_to_the_owner_with_a_tag(self):
        m = self.can("Sam", "money")
        self.assertTrue(m.startswith("OWNER [money]"))
        self.assertIn("one click", m)
        self.assertTrue(self.can("Sam", "legal").startswith("OWNER [legal]"))

    def test_access_is_held_for_the_verbatim_order(self):
        out = self.can("Sam", "access")
        self.assertTrue(out.startswith("COS"))
        self.assertIn("verbatim order", out)

    def test_other_and_unknown_kinds_go_to_the_chief_of_staff(self):
        self.assertTrue(self.can("Sam", "other").startswith("COS"))
        self.assertTrue(self.can("Sam", "gossip").startswith("COS"))
        self.assertTrue(self.can("Sam").startswith("COS"))

    def test_allow_overrides_the_ramp(self):
        self.assertTrue(self.can("Stranger", "status").startswith("COS"))
        self.assertEqual(self.run_comms("allow", "Stranger", "--kind", "status", "owner said so")[0], 0)
        self.assertEqual(self.can("Stranger", "status"), "SEND")
        self.assertEqual(self.run_comms("allow", "Sam", "--kind", "access", "ok")[0], 0)
        self.assertEqual(self.can("Sam", "access"), "SEND")

    def test_verify_overrides_the_ramp(self):
        self.assertEqual(self.can("Sam", "relay"), "SEND")
        self.run_comms("verify", "Sam", "--kind", "relay", "always ask")
        self.assertEqual(self.can("Sam", "relay"), "ASK")

    def test_allow_for_money_and_legal_is_refused_and_never_promotes(self):
        for k in ("money", "legal"):
            code, out = self.run_comms("allow", "Sam", "--kind", k, "pretty please")
            self.assertEqual(code, 2)
            self.assertIn("refused", out)
            self.assertTrue(self.can("Sam", k).startswith("OWNER"))
        # a hand-written line or a wildcard allow cannot promote either
        p = os.path.join(self.home, "data", "Context", "Communication_VP", "comms", "PERMISSIONS.md")
        with open(p, "a") as f:
            f.write("- send | Sam | money | since 2026-01-01 | hand edit\n- send | * | * | since 2026-01-01 | all\n")
        self.assertTrue(self.can("Sam", "money").startswith("OWNER [money]"))
        self.assertTrue(self.can("Sam", "legal").startswith("OWNER [legal]"))

    def test_help_and_permissions_text_drop_the_old_default(self):
        _, doc = self.run_comms("help")
        self.assertIn("Trust ramp", doc)
        p = os.path.join(self.home, "data", "Context", "Communication_VP", "comms", "PERMISSIONS.md")
        self.assertNotIn("the answer is ASK", open(p).read())


if __name__ == "__main__":
    unittest.main()
