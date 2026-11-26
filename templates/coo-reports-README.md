# coo-reports

One file per project, `<Project>.md`, newest line first. Every COO pass writes one line:

`- YYYY-MM-DDTHH:MMZ | status: green|amber|red | done: ... | next: ... | needs-owner: none|<question> (options, recommended first)`

Only `needs-owner[legal]:` (sign, accept terms) and `needs-owner[money]:` (pay, buy, move money) reach the owner's
Workspace panel. An untagged `needs-owner:` line is a question for the Chief of Staff.

The Chief of Staff reads these files on every pass. `jobs/` holds results from fleet job runners.
`coo_lesson_check.py` scans these lines for repeat mistakes listed as CHECK lines in each COO's `coo/LESSONS.md`.
