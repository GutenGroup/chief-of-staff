# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/chief-of-staff` is not found | plugin not installed or app not restarted | `claude plugin list`; restart the app |
| Nothing under `~/ChiefOfStaff` after install | the setup hook runs on the next session start | start a new session; check `ls ~/.claude/cos-config.yaml` |
| `~/.claude/chief-of-staff exists and is not a link` | an older script install left a folder there | move it away, start a new session |
| Workspace panel missing | panel plugin not installed, or app not restarted | `claude plugin install workspace-sidebar@chief-of-staff`, restart the app |
| Panel shows "Chief of Staff not started yet" | no session titled `⭐ 𝐂𝐇𝐈𝐄𝐅 𝐎𝐅 𝐒𝐓𝐀𝐅𝐅 ⭐` (or the older plain `Chief of Staff`) has run a pass | title it that way, send `/chief-of-staff` |
| The brief is stale | the Chief of Staff loop expired (7 days) or the session stopped | send `/chief-of-staff` in that session; it re-arms its loop |
| A COO stopped reporting | its loop expired or the session ended | the Chief of Staff resumes it after 4 h; or open it and send `/project-coo` |
| Two COOs for one area | started twice by hand | stop one; the Chief of Staff flags duplicates hourly |
| A "needs input" flag that is not real | the session finished without a question | the Chief of Staff clears false flags every pass |
| The same question asked twice | the answer was not recorded | answer once more and say "record this"; it goes to `DECISIONS.md` |
| Usage higher than expected | many COOs or an over-sized model | see [Models and costs](MODELS-AND-COSTS.md) |
| `cos: command not found` | `~/.local/bin` is not on your PATH, or another `cos` exists | add `~/.local/bin` to PATH, or run `python3 ~/.claude/chief-of-staff/bin/cos.py <command>` |
| A message from another session was blocked | it held only a bare slash command | send a sentence instead; to turn the check off: `touch ~/.claude/peer-bare-command-drop-off` |

Check the install:

```bash
python3 ~/.claude/chief-of-staff/bin/cos.py status
python3 ~/.claude/chief-of-staff/bin/cos.py list-coos
```

Still stuck? Open an issue: https://github.com/GutenGroup/chief-of-staff/issues
