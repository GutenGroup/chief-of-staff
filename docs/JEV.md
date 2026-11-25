# With and without Jev

Chief of Staff works fully without Jev. We still recommend connecting a Jev key, and this page explains why, honestly.

## What Jev is

[Jev](https://typesafe.ai) is a small, fast model from TypeSafe. It does not write text. You give it the situation and
a typed question, and it returns a calibrated probability, in well under a second. That makes it good at the kind of
yes/no and pick-one calls the Chief of Staff, the Production VP and the COOs make dozens of times a day.

## The four questions

When a key is present, every role asks Jev before these moves (`bin/jev.py`):

| Question | Asked | What the role does with the answer |
|---|---|---|
| `route` | before handing new work to a COO or worker | gives it to the most likely owner |
| `effort` | when a task is unclear | `ask` = get the spec first; `low` / `medium` = set the worker's effort |
| `safe` | before any action taken without you | acts alone only when P(safe) >= 0.8 **and** the action is reversible; otherwise it becomes a dialog for you |
| `retry` | after a failure | `stop_retry` = stop repeating the same thing; `ask_human` = raise it to you |

An irreversible action always comes to you, whatever Jev says.

## The tradeoff

| | Without Jev | With Jev |
|---|---|---|
| Who makes the call | the role's own model, in its own words | a model built for typed decisions, then the role acts on it |
| Cost | each call is reasoning tokens on Opus or Sonnet | a small API call; the big model reasons less |
| Consistency | the same situation can get a different call on a different day | the same input gives the same probability |
| Safety gate | "seems fine" | a number with a fixed bar (0.8), logged with the decision |
| Retry loops | a stuck worker can retry the same failing step several times | `stop_retry` ends the loop early |
| Setup | none | one key |

Without Jev nothing breaks. The roles are still told to raise anything risky or irreversible as a dialog. What you
lose is the calibrated gate and some token cost on routine calls. We've run both ways; the version with Jev asks you
fewer needless questions and wastes fewer retries.

## Connect a key

1. Get a key at [typesafe.ai](https://typesafe.ai).
2. Enter it in the plugin's **TypeSafe API key** option (Claude Code asks for it when you enable the plugin, and
   stores it as a sensitive value, not in a file the plugin reads). **Never put it in the config file or any
   repository.** Or export `TYPESAFE_API_KEY` in your shell profile.
3. Check: `cos status` prints `jev: key found`.

Try it by hand:

```bash
python3 ~/.claude/chief-of-staff/bin/jev.py safe --text "Re-run the failed unit tests on a feature branch" --reversible
```

## What gets sent

The `--text` you pass, which is the situation the role describes (a task, an action, an error), goes to TypeSafe's API
with the question. The roles are told never to put a password, key or token in it. Nothing else leaves your machine,
and without a key nothing is sent at all. If the API is slow or down, `jev.py` prints `skipped` and the role falls
back to its own judgment.
