# Contributing

Anyone can propose a change. Guten Group reviews every proposal and decides what merges, and a release ships only from
what we merge.

## Proposing a change

1. Fork the repository and open a pull request against `next`. Say what the change lets a user do.
2. Keep it generic: no names, hostnames, paths, keys or company-specific rules. Those belong in your own config or
   overlay (see [docs/OVERLAY.md](docs/OVERLAY.md)).
3. Update `HIGHLIGHTS.md` with what users can now do (3-6 plain bullets); it becomes the release's `## Highlights`
   section.
4. A Guten Group member reviews it. A pull request from outside the organization needs an approving review from a
   member before it can merge; nobody outside the organization can push to `main`.

## The directory edition

`editions/directory/` holds the texts of the supervised edition published in the Claude plugin directory; `directory/` is
built from it. It is written on its own, not filtered from the full skills, and `.github/scripts/directory_lint.py`
fails the build on anything the directory policy refuses. Change both editions when a role's behavior changes.

## Checks

Every pull request runs the same checks as a release: a private-data check, `claude plugin validate --profile
directory`, and the tests. For a first-time contributor, a member approves the run before it starts, and pull requests
from forks never receive the repository's secrets.

## Releases

Changes collect on the `next` branch: open pull requests against `next`, not `main`. Every pull request and push to
`next` runs the full checks, and nothing on `next` is published.

A release ships every 7 to 10 days: a Guten Group member merges `next` into `main` in one pull request, with `VERSION`
bumped once and `HIGHLIGHTS.md` listing everything the release adds. A green change on `main` is tagged and published as
a GitHub Release; installs pick it up on their next update. A red check blocks the release. Only an urgent fix for a
broken install goes to `main` between releases, and it is merged back into `next` the same day.
