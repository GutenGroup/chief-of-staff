# Contributing

Anyone can propose a change. Daniel Ekstrom and Tony Högqvist decide what merges, and a release ships only from what
they merge.

## Proposing a change

1. Fork the repository and open a pull request against `main`. Say what the change lets a user do.
2. Keep it generic: no names, hostnames, paths, keys or company-specific rules. Those belong in your own config or
   overlay (see [docs/OVERLAY.md](docs/OVERLAY.md)).
3. Update `HIGHLIGHTS.md` with what users can now do (3-6 plain bullets); it becomes the release's `## Highlights`
   section.
4. Daniel Ekstrom and Tony Högqvist are the code owners (`.github/CODEOWNERS`). A pull request needs an approving
   review from one of them before it can merge; nobody else can approve a merge or push to `main`.

## Checks

Every pull request runs the same checks as a release: a private-data check, `claude plugin validate --profile
directory`, and the tests. For a first-time contributor, the run starts only after it is approved, and pull requests
from forks never receive the repository's secrets.

## Releases

Only the two code owners and the release automation acting on their behalf push to `main`. A green change on `main` is
tagged and published as a GitHub Release; installs pick it up on their next update. A red check blocks the release.
