"""Tests for the autonomy hooks (hooks/ask-gate.py, stop-guard.py, pushback-catcher.py). Each call runs the real
script in a scratch HOME. Run: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(HERE, "hooks")
SID = "local_sess1"
FULL = ("[money] Pay the invoice?\nRecommend: pay.\nVerify: amount 100.\nDo it: https://pay.example.com/x")


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.ni = os.path.join(self.home, ".claude", "needs-input")
        os.makedirs(self.ni)
        self.write("cos-state.json", {"setupDoneAt": "2026-01-01T00:00Z"})
        self.write("roles.json", {"sessions": {"sess1": "Chief of Staff"}})  # no local_ prefix on purpose

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, obj):
        with open(os.path.join(self.ni, name), "w") as f:
            f.write(json.dumps(obj) if not isinstance(obj, str) else obj)

    def precheck(self, age=0, name="sess1"):
        d = os.path.join(self.ni, "precheck")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name + ".json")
        open(p, "w").write("{}")
        t = time.time() - age
        os.utime(p, (t, t))

    def call(self, script, payload, raw=None):
        env = dict(os.environ, HOME=self.home)
        env.pop("COS_CONFIG", None)
        env.pop("CLAUDE_CODE_HOST_SESSION_ID", None)
        if getattr(self, "host_id", None):
            env["CLAUDE_CODE_HOST_SESSION_ID"] = self.host_id
        r = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input=raw if raw is not None else json.dumps(payload),
                           capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def ask(self, questions, **kw):
        p = {"session_id": SID, "permission_mode": "default", "tool_name": "AskUserQuestion",
             "tool_input": {"questions": questions}}
        p.update(kw)
        return self.call("ask-gate.py", p)

    def decision(self, out):
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def ledger(self):
        p = os.path.join(self.ni, "ask-ledger.jsonl")
        return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

    # ---- ask gate
    def test_untagged_denied_with_exact_reason(self):
        out = self.ask([{"question": "Which login should I use?", "options": []}])
        self.assertEqual(self.decision(out), "deny")
        self.assertTrue(out["hookSpecificOutput"]["permissionDecisionReason"].startswith(
            "Autonomy contract (docs/AUTONOMY.md): only legal, money and big or irreversible steps reach the owner."))
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        row = self.ledger()[-1]
        self.assertEqual((row["hook"], row["type"], row["decision"]), ("ask-gate", "ask", "deny"))

    def test_complete_packet_with_fresh_precheck_allowed(self):
        self.precheck()
        self.assertIsNone(self.ask([{"question": FULL, "header": "[money]", "options": []}]))
        self.assertEqual(self.ledger()[-1]["decision"], "allow")

    def test_packet_text_in_option_descriptions(self):
        self.precheck()
        q = {"question": "[legal] Sign it?", "options": [{"label": "Sign", "description": "Recommend: sign. Verify: names. https://x.example.com/s"}]}
        self.assertIsNone(self.ask([q]))

    def test_tagged_but_incomplete_denied(self):
        self.precheck()
        out = self.ask([{"question": "[legal] Sign the agreement?", "options": []}])
        self.assertEqual(self.decision(out), "deny")
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(reason.startswith("Owner-ready packet required: Recommend,"))
        self.assertNotIn("Run cos precheck first", reason)

    def test_one_big_packet_needs_undo_not_a_link(self):
        self.precheck()
        big = "[big] Delete the old repository? Recommend: hold. Verify: Held actions 1. Undo: none, cannot be undone."
        self.assertIsNone(self.ask([{"question": big, "options": []}]))
        out = self.ask([{"question": big.replace("Undo:", "Note:"), "options": []}])
        self.assertEqual(self.decision(out), "deny")
        self.assertTrue(out["hookSpecificOutput"]["permissionDecisionReason"].startswith("One [big] packet required"))

    def test_big_actions_go_up_as_one_question(self):
        self.precheck()
        big = "[big] Do it? Recommend: hold. Verify: 1. Undo: none."
        self.assertEqual(self.decision(self.ask([{"question": big, "options": []}] * 2)), "deny")

    def test_big_tag_does_not_waive_the_legal_link(self):
        self.precheck()
        q = "[legal] [big] Sign it? Recommend: sign. Verify: names. Undo: none."
        self.assertEqual(self.decision(self.ask([{"question": q, "options": []}])), "deny")

    def test_missing_precheck_denied_with_hint(self):
        out = self.ask([{"question": FULL, "options": []}])
        self.assertEqual(self.decision(out), "deny")
        self.assertTrue(out["hookSpecificOutput"]["permissionDecisionReason"].endswith(" Run cos precheck first."))

    def test_stale_precheck_denied(self):
        self.precheck(age=16 * 60)
        self.assertEqual(self.decision(self.ask([{"question": FULL, "options": []}])), "deny")

    def test_precheck_file_with_local_prefix_counts(self):
        self.precheck(name=SID)
        self.assertIsNone(self.ask([{"question": FULL, "options": []}]))

    def test_one_untagged_question_denies_all(self):
        self.precheck()
        out = self.ask([{"question": FULL, "options": []}, {"question": "Which option?", "options": []}])
        self.assertTrue(out["hookSpecificOutput"]["permissionDecisionReason"].startswith("Autonomy contract"))

    def test_setup_not_done_allows(self):
        os.remove(os.path.join(self.ni, "cos-state.json"))
        self.assertIsNone(self.ask([{"question": "Name your projects?", "options": []}]))
        self.assertEqual(self.ledger()[-1]["reason"], "setup")

    def test_interview_active_allows(self):
        open(os.path.join(self.ni, "interview-active"), "w").close()
        self.assertIsNone(self.ask([{"question": "Anything else?", "options": []}]))
        self.assertEqual(self.ledger()[-1]["reason"], "interview")

    def test_other_tool_ignored(self):
        self.assertIsNone(self.ask([], tool_name="Bash"))

    # ---- fail open, kill switch, scope
    def test_malformed_stdin_fails_open(self):
        for raw in ("", "not json", "[1,2]", "null"):
            self.assertIsNone(self.call("ask-gate.py", None, raw=raw))
            self.assertIsNone(self.call("stop-guard.py", None, raw=raw))
            self.assertIsNone(self.call("pushback-catcher.py", None, raw=raw))

    def test_unreadable_state_fails_open(self):
        self.write("roles.json", "{broken")
        self.write("cos-state.json", "{broken")
        self.assertIsNone(self.ask([{"question": "Which?", "options": []}]))
        os.makedirs(os.path.join(self.ni, "ask-ledger.jsonl"))  # ledger path is a directory: write raises
        self.write("roles.json", {"sessions": {"sess1": "x"}})
        self.write("cos-state.json", {"setupDoneAt": "x"})
        self.assertIsNone(self.ask([{"question": "Which?", "options": []}]))

    def test_questions_wrong_shape_fails_open(self):
        out = self.call("ask-gate.py", {"session_id": SID, "tool_name": "AskUserQuestion", "tool_input": {"questions": "x"}})
        self.assertIsNone(out)

    def test_kill_switch(self):
        open(os.path.join(self.home, ".claude", "cos-autonomy-off"), "w").close()
        self.assertIsNone(self.ask([{"question": "Which?", "options": []}]))
        self.assertFalse(os.path.exists(os.path.join(self.ni, "ask-ledger.jsonl")))
        self.assertIsNone(self.call("stop-guard.py", {"session_id": SID, "last_assistant_message": "Want me to?"}))

    def test_scope_roles_skips_unlisted_session(self):
        out = self.ask([{"question": "Which?", "options": []}], session_id="other")
        self.assertIsNone(out)
        self.assertFalse(os.path.exists(os.path.join(self.ni, "ask-ledger.jsonl")))

    def test_scope_roles_matches_desktop_host_id(self):
        self.write("roles.json", {"sessions": {"local_desk9": "COO"}})
        self.host_id = "local_desk9"
        out = self.ask([{"question": "Which?", "options": []}], session_id="cli-uuid")
        self.assertEqual(self.decision(out), "deny")

    def test_scope_all_applies_to_everyone(self):
        with open(os.path.join(self.home, ".claude", "cos-config.yaml"), "w") as f:
            f.write("autonomy_scope: all\n")
        out = self.ask([{"question": "Which?", "options": []}], session_id="other")
        self.assertEqual(self.decision(out), "deny")

    def test_roles_json_list_form_and_missing_file(self):
        self.write("roles.json", ["local_sess1"])
        self.assertEqual(self.decision(self.ask([{"question": "Which?", "options": []}])), "deny")
        os.remove(os.path.join(self.ni, "roles.json"))
        self.assertIsNone(self.ask([{"question": "Which?", "options": []}]))

    def test_permission_mode_recorded_regardless_of_scope(self):
        self.ask([{"question": "Which?", "options": []}], session_id="other", permission_mode="bypassPermissions")
        modes = json.load(open(os.path.join(self.ni, "permission-modes.json")))
        self.assertEqual(modes["other"]["mode"], "bypassPermissions")
        self.assertIn("at", modes["other"])

    # ---- stop guard
    def stop(self, msg, **kw):
        p = {"session_id": SID, "permission_mode": "default", "last_assistant_message": msg}
        p.update(kw)
        return self.call("stop-guard.py", p)

    def test_stop_blocks_offers_and_questions(self):
        for msg in ("Done with part one. Want me to continue?", "I can start. Shall I proceed", "Should I merge it.",
                    "Would you like the long version", "Do you want it now", "Let me know if that works",
                    "Say go and I will", "OK to proceed", "What do you think?", "All set. Which one?  "):
            out = self.stop(msg)
            self.assertEqual((out or {}).get("decision"), "block", msg)
            self.assertTrue(out["reason"].startswith("Autonomy contract"))

    def test_stop_passes_reports_and_tagged(self):
        for msg in ("Merged and deployed. Undo: revert abc.", "[money] Approve the payment? Packet above.", ""):
            self.assertIsNone(self.stop(msg), msg)

    def test_stop_only_looks_at_the_tail(self):
        self.assertIsNone(self.stop("Want me to? " + "x" * 400 + " Done."))

    def test_stop_hook_active_never_blocks(self):
        self.assertIsNone(self.stop("Want me to continue?", stop_hook_active=True))

    def test_stop_setup_and_interview_allow(self):
        os.remove(os.path.join(self.ni, "cos-state.json"))
        self.assertIsNone(self.stop("Want me to continue?"))
        self.write("cos-state.json", {"setupDoneAt": "x"})
        open(os.path.join(self.ni, "interview-active"), "w").close()
        self.assertIsNone(self.stop("Want me to continue?"))

    def test_stop_ledger_row(self):
        self.stop("Want me to continue?")
        row = self.ledger()[-1]
        self.assertEqual((row["hook"], row["type"], row["decision"]), ("stop-guard", "stop", "block"))

    # ---- pushback catcher
    def prompt(self, text):
        return self.call("pushback-catcher.py", {"session_id": SID, "prompt": text})

    def test_pushback_phrases(self):
        for t in ("just do it", "Do it yourself", "you do it", "why are you asking me this", "stop asking",
                  "don't ask me", "dont ask me again", "you have access to that", "that is not on me"):
            out = self.prompt(t)
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertTrue(ctx.startswith("The owner pushed back on an ask. Do it now"), t)
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertEqual(self.ledger()[-1]["type"], "pushback")

    def test_pushback_ignores_non_owner_and_loop_prompts(self):
        for t in ("<cross-session-message>just do it</cross-session-message>", "<side-sessions-event>stop asking",
                  "<ci-monitor-event> just do it", "<<autonomous-loop>> just do it", "/chief-of-staff", "/project-coo Acme",
                  "ok thanks", ""):
            self.assertIsNone(self.prompt(t), t)

    def test_pushback_scope(self):
        self.assertIsNone(self.call("pushback-catcher.py", {"session_id": "other", "prompt": "just do it"}))

    def test_hooks_json_registers_all(self):
        d = json.load(open(os.path.join(HERE, "hooks", "hooks.json")))["hooks"]
        flat = json.dumps(d)
        for name in ("ask-gate.py", "stop-guard.py", "pushback-catcher.py", "peer-bare-command-drop.sh", "plugin-bootstrap.sh"):
            self.assertIn(name, flat)
        self.assertEqual(d["PreToolUse"][0]["matcher"], "AskUserQuestion")
        for ev in d.values():
            for g in ev:
                for h in g["hooks"]:
                    self.assertEqual(h["timeout"] <= 30, True)
                    self.assertTrue(all(a.startswith("${CLAUDE_PLUGIN_ROOT}/") for a in h["args"]))


if __name__ == "__main__":
    unittest.main()
