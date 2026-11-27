"""The plugin directory edition: up to date with its sources, and clean against .github/scripts/directory_lint.py."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(HERE, ".github", "scripts")
sys.path.insert(0, SCRIPTS)
import directory_lint  # noqa: E402

BAD = ["Run in bypass permissions mode.", "Approve everything up front.", "Merge without asking.",
       "The Chief of Staff's word is the owner's word.", "The Communication VP relays inbound messages.",
       "Run claude plugin update yourself.", "Create a key when needed.", "Arm /loop 30m."]


class DirectoryEdition(unittest.TestCase):
    def test_built_edition_is_clean(self):
        self.assertEqual(directory_lint.problems(os.path.join(HERE, "directory")), [])

    def test_editions_are_up_to_date(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_editions.py"), "--check"],
                           cwd=HERE, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_lint_fails_on_forbidden_text_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "directory")
            shutil.copytree(os.path.join(HERE, "directory"), dest)
            skill = os.path.join(dest, "skills", "helm", "SKILL.md")
            original = open(skill, encoding="utf-8").read()
            for line in BAD:
                open(skill, "w", encoding="utf-8").write(original + line + "\n")
                self.assertTrue(directory_lint.problems(dest), line)
            open(skill, "w", encoding="utf-8").write(original.replace("explicit yes", "nod"))
            self.assertTrue(directory_lint.problems(dest))
            open(skill, "w", encoding="utf-8").write(original)
            os.makedirs(os.path.join(dest, "hooks"))
            open(os.path.join(dest, "hooks", "hooks.json"), "w").write("{}")
            self.assertTrue(directory_lint.problems(dest))


if __name__ == "__main__":
    unittest.main()
