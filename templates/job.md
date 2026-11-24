type: job
project: MyProject
class: code
repo: ~/code/my-repo

<!-- repo must sit under a folder listed in job_repo_roots in ~/.claude/cos-config.yaml. Workers read,
     edit and commit locally; they cannot push, run code or use the web. Push and test from the COO. -->
Brief: one paragraph a worker can act on with no other context.
Say what done looks like and how to verify it.
