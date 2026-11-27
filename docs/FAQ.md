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

### What is the Communication VP?
A standard role next to the Production VP that handles all your communication. COOs hand it what should be said; it
drafts (its own model, or your own drafter), sends to the right people on Google Chat, botreeve groups or a shared folder,
asks you first unless you have said "send without approval" for that person or group, and routes inbound messages to
the right COO. Every message is signed as written by your Communication VP. More: [The Communication VP](COMMUNICATION-VP.md).

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
It never moves money or signs or accepts anything legal without you. Those are the two hard stops, `[legal]` and
`[money]`, and each reaches you as a ready-to-act packet. Everything else it decides and does, then reports with an
undo line. COOs merge and deploy finished work on green checks. The Communication VP sends the messages the trust ramp
allows (your own words relayed, status, scheduling and answers to known contacts, replies in threads you already
engaged in) and sends money or legal messages to you first. Workers have a restricted tool list: they may commit, push
a non-default branch and open a PR, never merge or deploy.

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

### How do I add my own rules?
Run `cos overlay init`. It creates your private overlay, `~/.claude/cos-overlay/`, with one file per skill (`chief-of-staff.md`,
`project-coo.md`, `production-vp.md`, `communication-vp.md`, `helm.md`). Write your rules there in plain language: each skill reads its file
after its own text, the overlay wins on conflict, and plugin updates never touch it. Rules that would help everyone go
upstream as a pull request instead. The overlay is personal; people and teams connect through the Communication VP. More: [Add your own rules](OVERLAY.md).

### How do I teach a COO something?
Tell it, or tell the Chief of Staff about it. Corrections become lessons in that COO's `coo/LESSONS.md` the same day, and
repeated ones become rules and machine checks.

### Why is my Chief of Staff pinned with stars, and what is the "⭐ Chief of Staff" group?
That is the standard sidebar layout since 1.5.0: the Chief of Staff, every VP and every COO are pinned and grouped
together; workers stay unpinned in their project groups. Role titles have no "CoS · " prefix. After an update the Chief
of Staff fixes old titles, pins and groups once on its next pass. `cos layout` prints what it expects.

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
