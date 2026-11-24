# FAQ

### What is this, in one line?
A management layer for Claude Code. One Chief of Staff session watches all your sessions, a Production VP and COOs you
choose coordinate the work, cheap worker sessions do it, and you get a short brief and click-through decisions.

### What does it cost?
Nothing beyond your Claude plan. It uses the same usage as any Claude Code session. The main drivers are the number of
COOs and the Chief of Staff's 30-minute loop. See [Models and costs](MODELS-AND-COSTS.md) for the levers.

### How many COOs should I have?
Start with 2-4: one per product or business line, plus at most one or two areas like IT or admin. Merge an area that has
less than a few hours of work a week. You can add more any time.

### What is the Production VP?
A standard role between the Chief of Staff and your product COOs. It reads every product COO's reports, sends back work
claimed "done" without a live check, and coaches a COO that slips. It ships with every install; with one product it has
little to do and costs almost nothing.

### Do I have to have a Production VP?
It is always set up, but it only runs once you have at least one product COO. If all your COOs are non-product areas,
it never starts. More: [The Production VP](PRODUCTION-VP.md).

### How do I add a COO?
Tell the Chief of Staff "add a COO", or run `/add-coo <name>`. It asks two or three dialog questions, writes the
charter and goals, and starts the COO. By hand: `cos add-project "<Name>"` (see [Setting up COOs](SETTING-UP-COOS.md)).

### How do I remove a COO?
Stop its session, then remove its name from `projects:` in `~/.claude/cos-config.yaml`. Its folder in
`~/ChiefOfStaff/Context/` stays as a record; delete it yourself if you want it gone.

### Can it run on one computer?
Yes. One computer is the default (`fleet_mode: single`). Several computers sharing a synced folder is optional
(see [Reference](REFERENCE.md#several-computers-optional)).

### Does it work without the desktop app?
The skills, commands and hooks work in Claude Code in a terminal. The Workspace panel and the session-management tools
the Chief of Staff uses to read and nudge other sessions are desktop-app features, so the full system needs the app.

### Why does it ask me in dialogs and never in text?
So every decision is one click, the recommended answer is always first, and nothing waits on you hidden in a long
message. If you are away the same dialog waits in the Workspace panel.

### Will it ask me the same thing twice?
It should not. Before asking it checks your recorded decisions (`~/ChiefOfStaff/DECISIONS.md`, each COO's charter and
lessons). If it does, tell it once; that becomes a lesson.

### What does it never do on its own?
It never moves money, signs or accepts anything legal, sends messages to other people, deletes data, or pushes to a
remote on your behalf without your answer. Those always come to you as a dialog. Workers run with a locked-down tool
list (no web, no interpreters, no push).

### What leaves my machine?
Nothing new. All state is plain markdown on your disk. The only network traffic is the Claude Code sessions themselves,
which talk to Claude exactly as they would without this plugin. There is no server, analytics or telemetry.

### Where is my data?
`~/ChiefOfStaff/` (change `data_root` in `~/.claude/cos-config.yaml`) and `~/.claude/needs-input/`. Put the data folder
in a synced folder if you want it on several machines.

### What happens when a session's context fills up?
The Chief of Staff has the COO write its state file, then clears it in place: same session, same title, same workers. It
re-reads its files and carries on. See [How it works](HOW-IT-WORKS.md).

### Does it actually learn?
Yes, in files, not in memory. Every correction becomes a dated lesson the same turn, a visible mistake becomes a check
that runs every pass, and a weekly scorecard counts repeated corrections per role (going down is the goal). A monthly
knowledge test grades each role on its own files. Works for the Chief of Staff, the Production VP and every COO. More:
[How it learns](HOW-IT-LEARNS.md).

### How do I teach a COO something?
Tell it, or tell the Chief of Staff about it. Corrections become lessons in that COO's `coo/LESSONS.md` the same day, and
repeated ones become rules and machine checks.

### Can I rename or restructure COOs later?
Yes. Merge two by moving one's goals into the other's `GOALS.md` and removing the first; split one with `/add-coo`. The
Chief of Staff keeps one active COO per area.

### How do I pause it?
Stop the Chief of Staff's loop (ask it, or `CronDelete` its `/chief-of-staff` job). COOs keep their files; restart any
time with `/chief-of-staff`.

### How do I uninstall?
`claude plugin uninstall chief-of-staff@chief-of-staff` (and `workspace-sidebar@chief-of-staff`). Your data folder and
config stay; delete `~/ChiefOfStaff`, `~/.claude/cos-config.yaml` and `~/.claude/needs-input` if you want them gone.

### What is Jev, and do I need it?
An optional decision model from TypeSafe. With a key, the roles ask it who should get a task, how much effort it needs,
whether an action is safe to take alone, and whether to retry after a failure. Without a key everything still works and
the roles use their own judgment. We recommend connecting one: see [With and without Jev](JEV.md).

### When do sessions clear, and can I change it?
The Chief of Staff and COOs clear at 150,000 tokens, the Production VP at 200,000, far below the model's maximum, to
keep cost and quality in check. Change `clear_at_cos`, `clear_at_vp` and `clear_at_coo` in `~/.claude/cos-config.yaml`.
See [Operating](OPERATING.md).

### Where do I get help or report a bug?
Ask inside Claude Code with `/cos-help <question>`, read [Troubleshooting](TROUBLESHOOTING.md), or open an issue on
[GitHub](https://github.com/GutenGroup/chief-of-staff/issues).
