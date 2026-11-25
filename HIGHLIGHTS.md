# Highlights

The "## Highlights" section of the next GitHub Release: 3-6 plain-language bullets of what users can now do.
Update it in the same change as the feature. CI fails when there are fewer than 3 or more than 6 bullets.

- A Markdown-only edition for the Claude plugin directory lives in `directory/`: the role skills, commands and the worker agent, no scripts or hooks.
- The same skills are packaged for ChatGPT in `chatgpt/` (upload `chatgpt/dist/chief-of-staff-chatgpt-<version>.zip`).
- The Jev (TypeSafe) key is now a sensitive plugin option; the plugin no longer reads a key file. `TYPESAFE_API_KEY` in your environment still works.
