# Contributing

Anyone can propose a change. Guten Group reviews every proposal and decides what merges, and a release ships only from
what we merge.

## Proposing a change

1. Fork the repository and open a pull request against `main`. Say what the change lets a user do.
2. Keep it generic: no names, hostnames, paths, keys or company-specific rules. Those belong in your own config or
   overlay (see [docs/OVERLAY.md](docs/OVERLAY.md)).
3. Update `HIGHLIGHTS.md` with what users can now do (3-6 plain bullets); it becomes the release's `## Highlights`
   section.
4. A Guten Group member reviews it. A pull request from outside the organization needs an approving review from a
   member before it can merge; nobody outside the organization can push to `main`.

## Checks

Every pull request runs the same checks as a release: a private-data check, `claude plugin validate --profile
directory`, and the tests. For a first-time contributor, a member approves the run before it starts, and pull requests
from forks never receive the repository's secrets.

## Releases

Only Guten Group members and the organization's own release automation push to `main`. A green change on `main` is
tagged and published as a GitHub Release; installs pick it up on their next update. A red check blocks the release.
