#!/usr/bin/env python3
"""SessionStart (plugin install only). Points ~/.claude/chief-of-staff at this plugin version, so the skills' paths
work after every update, and on the first session (and once after each update) runs the idempotent init, which
creates the config, the panel files and the standard roles (Production VP, Communication VP).
Never overwrites a config, data or a ~/.claude/chief-of-staff folder that is not a link. Silent; never blocks."""
import os
import shutil
import subprocess
import sys


def main():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    home = os.path.expanduser("~")
    claude = os.path.join(home, ".claude")
    flags = os.path.join(claude, "needs-input")
    os.makedirs(flags, exist_ok=True)
    link = os.path.join(claude, "chief-of-staff")
    if os.path.islink(link) or not os.path.exists(link):
        if not (os.path.islink(link) and os.readlink(link) == root):
            tmp = link + ".tmp-cos"
            if os.path.lexists(tmp):
                os.remove(tmp)
            os.symlink(root, tmp)
            os.replace(tmp, link)
    defaults = {
        "index.json": "{}\n",
        "cos-state.json": "{}\n",
        "cos-brief.json": '{"generatedAt":"","headline":"Chief of Staff not started yet","cooking":[],"needsOwner":[]}\n',
    }
    for name, text in defaults.items():
        p = os.path.join(flags, name)
        if not os.path.exists(p):
            with open(p, "w") as f:
                f.write(text)
    cfg = os.path.join(claude, "cos-config.yaml")
    if not os.path.exists(cfg):
        shutil.copyfile(os.path.join(root, "config.example.yaml"), cfg)
    done = os.path.join(flags, ".cos-init-done")
    # init is idempotent: it runs once per plugin version, so roles added in an update appear without a reinstall;
    # a run cut off by the hook timeout is finished on the next session.
    try:
        version = open(os.path.join(root, "VERSION")).read().strip()
    except OSError:
        version = ""
    try:
        done_v = open(done).read().strip()
    except OSError:
        done_v = None
    if done_v != version:
        r = subprocess.run([sys.executable, os.path.join(root, "bin", "cos.py"), "init"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=home)
        if r.returncode == 0:
            with open(done, "w") as f:
                f.write(version + "\n")
    # The `cos` command, unless something else already owns that name.
    cosbin = os.path.join(home, ".local", "bin", "cos")
    if not os.path.lexists(cosbin):
        os.makedirs(os.path.dirname(cosbin), exist_ok=True)
        os.symlink(os.path.join(link, "bin", "cos.py"), cosbin)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
