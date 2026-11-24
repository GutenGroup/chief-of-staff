#!/bin/bash
# Installs into a scratch HOME twice, runs the COO scripts on a sample project, then uninstalls.
# Run: bash tests/test_install.sh
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export HOME="$(mktemp -d)"
export COS_NO_LAUNCHD=1 COS_NO_KNOWLEDGE_TEST=1   # never load a real LaunchAgent or call claude from a test
FIRST_HOME="$HOME"
trap 'rm -rf "$FIRST_HOME" "$HOME"' EXIT
PASS=0; FAIL=0
check() { if eval "$2"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $1"; fi; }

"$REPO/install.sh" --yes --owner Alex --projects "Acme,Beta Labs" >/tmp/cos-install-1.log 2>&1
check "install exits 0" '[ $? -eq 0 ]'
check "release link" '[ "$(readlink "$HOME/.claude/chief-of-staff")" = "$REPO" ]'
for s in chief-of-staff project-coo helm; do
  check "skill $s linked" '[ "$(readlink "$HOME/.claude/skills/'$s'")" = "$REPO/skills/'$s'" ]'
done
check "config owner" 'grep -q "owner_name: \"Alex\"" "$HOME/.claude/cos-config.yaml"'
check "config projects" 'grep -q "  - Beta Labs" "$HOME/.claude/cos-config.yaml"'
check "charter Acme" '[ -f "$HOME/ChiefOfStaff/Context/Acme/COO_CHARTER.md" ]'
check "charter Beta" '[ -f "$HOME/ChiefOfStaff/Context/Beta_Labs/COO_CHARTER.md" ]'
check "panel files" '[ -f "$HOME/.claude/needs-input/index.json" ] && [ -f "$HOME/.claude/needs-input/cos-brief.json" ] && [ -f "$HOME/.claude/needs-input/sidebar.json" ]'
check "settings mod" 'python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d[\"enabledPlugins\"][\"workspace-sidebar@cos-mods\"] is True;assert d[\"extraKnownMarketplaces\"][\"cos-mods\"][\"source\"][\"path\"]==sys.argv[2]+\"/mods\"" "$HOME/.claude/settings.json" "$REPO"'
check "settings hook" 'grep -q peer-bare-command-drop.sh "$HOME/.claude/settings.json"'
check "VP charter standard" '[ -f "$HOME/ChiefOfStaff/Context/Production_VP/COO_CHARTER.md" ] && grep -q "Production VP charter" "$HOME/ChiefOfStaff/Context/Production_VP/COO_CHARTER.md"'
for f in PERSONA PLAYBOOK KNOWLEDGE LESSONS SCORECARD; do
  check "VP coo/$f.md" '[ -f "$HOME/ChiefOfStaff/Context/Production_VP/coo/'$f'.md" ]'
done
check "VP persona title" 'grep -q "^# Production VP persona" "$HOME/ChiefOfStaff/Context/Production_VP/coo/PERSONA.md"'
check "VP has a CHECK line" 'grep -q "^- CHECK text-question" "$HOME/ChiefOfStaff/Context/Production_VP/coo/LESSONS.md"'
check "product COO reports to VP" 'grep -q "Production VP (\`CoS" "$HOME/ChiefOfStaff/Context/Acme/COO_CHARTER.md"'
check "marketplace json valid" 'python3 -c "import json;d=json.load(open(\"$REPO/mods/.claude-plugin/marketplace.json\"));assert d[\"plugins\"][0][\"name\"]==\"workspace-sidebar\""'

cp "$HOME/.claude/settings.json" "$HOME/settings.first"
echo "Alex edit" >> "$HOME/ChiefOfStaff/Context/Acme/COO_CHARTER.md"
"$REPO/install.sh" --yes >/tmp/cos-install-2.log 2>&1
check "second install exits 0" '[ $? -eq 0 ]'
check "second install keeps settings" 'cmp -s "$HOME/.claude/settings.json" "$HOME/settings.first"'
check "second install keeps edits" 'grep -q "Alex edit" "$HOME/ChiefOfStaff/Context/Acme/COO_CHARTER.md"'
check "second install says already" 'grep -q "settings: already set" /tmp/cos-install-2.log'
check "hook registered once" '[ "$(grep -c peer-bare-command-drop.sh "$HOME/.claude/settings.json")" = 1 ]'

# A skill folder the user already has is never replaced.
rm "$HOME/.claude/skills/helm"; mkdir "$HOME/.claude/skills/helm"; echo mine > "$HOME/.claude/skills/helm/SKILL.md"
"$REPO/install.sh" --yes >/tmp/cos-install-3.log 2>&1
check "foreign skill kept" 'grep -q mine "$HOME/.claude/skills/helm/SKILL.md" && grep -q "skill helm: SKIPPED" /tmp/cos-install-3.log'

# A non-product COO reports to the Chief of Staff.
python3 "$REPO/bin/cos.py" add-project "IT" --reports-to cos >/tmp/cos-add.log 2>&1
check "add-project --reports-to cos" 'grep -q "Chief of Staff, directly" "$HOME/ChiefOfStaff/Context/IT/COO_CHARTER.md" && grep -q "  - IT" "$HOME/.claude/cos-config.yaml"'
python3 "$REPO/bin/cos.py" list-coos >/tmp/cos-list.log 2>&1
check "list-coos shows VP and lines" 'grep -q "^Production VP .*five files 5/5" /tmp/cos-list.log && grep -q "^IT COO .*reports to Chief of Staff" /tmp/cos-list.log && grep -q "^Acme COO .*reports to Production VP" /tmp/cos-list.log'
python3 "$REPO/bin/coo_lesson_check.py" Production_VP >/tmp/cos-vp.log 2>&1; rc=$?
check "VP lesson check runs clean (no report yet = 2 allowed)" '[ $rc -eq 0 ] || [ $rc -eq 2 ]'

# COO scripts on the sample project.
python3 "$REPO/bin/coo_onboard.py" Acme >/tmp/cos-onboard.log 2>&1
check "onboard exits 0" '[ $? -eq 0 ]'
for f in PERSONA PLAYBOOK KNOWLEDGE LESSONS SCORECARD; do
  check "coo/$f.md" '[ -f "$HOME/ChiefOfStaff/Context/Acme/coo/'$f'.md" ]'
done
printf -- '- CHECK no-tbd | since 2026-01-01 | forbid /\\bTBD\\b/ | write a real date\n' >> "$HOME/ChiefOfStaff/Context/Acme/coo/LESSONS.md"
printf -- '- 2026-06-01T10:00Z | status: green | done: shipped | next: TBD | needs-owner: none\n' >> "$HOME/ChiefOfStaff/fleet/coo-reports/Acme.md"
python3 "$REPO/bin/coo_lesson_check.py" Acme >/tmp/cos-lesson.log 2>&1
check "lesson check finds the violation" 'grep -qi "no-tbd" /tmp/cos-lesson.log'
python3 "$REPO/bin/coo_knowledge_test.py" Acme >/tmp/cos-knowledge.log 2>&1; rc=$?
check "knowledge pre-check runs (exit 0 or 1)" '[ $rc -le 1 ]'
python3 "$REPO/bin/coo_weekly_review.py" --dry-run >/tmp/cos-weekly.log 2>&1; rc=$?
check "weekly review dry run (exit 0 or 1)" '[ $rc -le 1 ]'

# Learning loop: a planted correction becomes a lesson and a CHECK line; the weekly review writes a scorecard row.
python3 "$REPO/bin/cos.py" lesson CoS "asked the owner which COO gets a task -> route it yourself" --check no-route-ask "(?i)which COO should" >/tmp/cos-learn.log 2>&1
check "CoS has five files" '[ -f "$HOME/ChiefOfStaff/Context/Chief_of_Staff/coo/PERSONA.md" ] && [ -f "$HOME/ChiefOfStaff/Context/Chief_of_Staff/coo/SCORECARD.md" ]'
check "correction became a dated lesson" 'grep -q "route it yourself" "$HOME/ChiefOfStaff/Context/Chief_of_Staff/COO_LESSONS.md"'
check "correction became a CHECK line" 'grep -q "CHECK no-route-ask" "$HOME/ChiefOfStaff/Context/Chief_of_Staff/coo/LESSONS.md"'
check "fleet lessons log" 'grep -q "Chief_of_Staff" "$HOME/ChiefOfStaff/fleet/lessons.log"'
TOMORROW=$(python3 -c 'import datetime;print((datetime.date.today()+datetime.timedelta(days=1)).isoformat())')
printf -- "- ${TOMORROW}T10:00Z | status: x | done: y | next: z | needs-owner: which COO should take it?\n" >> "$HOME/ChiefOfStaff/fleet/coo-reports/Chief_of_Staff.md"
python3 "$REPO/bin/coo_lesson_check.py" Chief_of_Staff >/tmp/cos-learn2.log 2>&1
check "the CHECK catches a repeat" 'grep -q "no-route-ask" /tmp/cos-learn2.log'
python3 "$REPO/bin/cos.py" learn-due --now >/tmp/cos-learn3.log 2>&1
check "weekly review ran" 'grep -q "weekly review" /tmp/cos-learn3.log'
check "CoS scorecard row written" 'grep -qE "^\| [0-9-]+ \([0-9]{4}-W[0-9]{2}\) \| 1 \|" "$HOME/ChiefOfStaff/Context/Chief_of_Staff/coo/SCORECARD.md"'
check "VP scorecard row written" 'grep -qE "\([0-9]{4}-W[0-9]{2}\)" "$HOME/ChiefOfStaff/Context/Production_VP/coo/SCORECARD.md"'
python3 "$REPO/bin/cos.py" learn-due --now >/tmp/cos-learn4.log 2>&1
check "learn-due idempotent" 'grep -q "nothing due" /tmp/cos-learn4.log'

"$REPO/uninstall.sh" >/tmp/cos-uninstall.log 2>&1
check "uninstall exits 0" '[ $? -eq 0 ]'
check "links gone" '[ ! -e "$HOME/.claude/chief-of-staff" ] && [ ! -e "$HOME/.claude/skills/chief-of-staff" ]'
check "settings cleaned" '! grep -q cos-mods "$HOME/.claude/settings.json" && ! grep -q peer-bare-command-drop "$HOME/.claude/settings.json"'
check "data kept" '[ -f "$HOME/ChiefOfStaff/Context/Acme/COO_CHARTER.md" ]'

# A default install ships no COOs: only the Production VP.
export HOME="$(mktemp -d)"
export COS_NO_LAUNCHD=1 COS_NO_KNOWLEDGE_TEST=1   # never load a real LaunchAgent or call claude from a test
"$REPO/install.sh" --yes --owner Sam >/tmp/cos-install-4.log 2>&1
check "default install exits 0" '[ $? -eq 0 ]'
check "default config has no COOs" 'grep -q "^projects: \[\]" "$HOME/.claude/cos-config.yaml"'
check "default Context holds the CoS and both VPs" '[ "$(ls "$HOME/ChiefOfStaff/Context" | tr "\n" " ")" = "Chief_of_Staff Communication_VP Production_VP " ]'
python3 "$REPO/bin/cos.py" add-project "First App" >/dev/null 2>&1
check "add-project into empty list" 'grep -q "^  - First App" "$HOME/.claude/cos-config.yaml" && ! grep -q "projects: \[\]" "$HOME/.claude/cos-config.yaml"'
rm -rf "$HOME"

echo "install test: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
