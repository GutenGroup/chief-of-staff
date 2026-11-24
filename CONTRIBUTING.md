# Contributing

1. Improvements are welcome: push to `main` or open a pull request against it.
2. Every push and pull request runs CI: a private-data check, `claude plugin validate --profile directory`, and the tests.
3. A green push to `main` tags the next patch version and publishes a GitHub Release; installs pick it up on their next update.
4. A red check blocks the release. Fix forward on `main`.
5. Update `HIGHLIGHTS.md` with what users can now do (3-6 plain bullets); it becomes the release's `## Highlights` section.
6. Keep it generic: no names, hostnames, paths, keys or company-specific rules. Those belong in your own config or overlay.
