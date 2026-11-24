"""cosconfig.py - one place that reads the Chief of Staff config.

Config file: $COS_CONFIG, else ~/.claude/cos-config.yaml (written by install.sh).
A small YAML subset is enough (flat `key: value` lines and one-level lists of
`- item`), so the scripts need nothing beyond the Python standard library.
PyYAML is used when it is installed.

Exported names:
  CONFIG   the parsed dict
  ROOT     data root: Context/<Project>/ lives here
  FLEET    folder for reports, inbox and status (fleet_dir, else ROOT/fleet)
  OWNER    the owner's first name ("you" in text when unset)
  PROJECTS list of project names
  MODE     single | lead | member
  MACHINE  this machine's id (machine_id, else the short hostname)
  OVERLAY  local overlay folder (overlay_dir): per-install rules the skills read after their own text
"""
import os
import re
import socket
import subprocess

DEFAULTS = {
    "owner_name": "",
    "data_root": "~/ChiefOfStaff",
    "fleet_mode": "single",
    "fleet_dir": "",
    "machine_id": "",
    "lead_machine": "",
    "projects": [],
    "claude_bin": "claude",
    "clear_at_cos": 150000,
    "clear_at_vp": 200000,
    "clear_at_coo": 150000,
    "overlay_dir": "~/.claude/cos-overlay",
}


def config_path():
    return os.path.expanduser(os.environ.get("COS_CONFIG", "~/.claude/cos-config.yaml"))


def _scalar(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    return v


def parse_yaml_subset(text):
    out, key = {}, None
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        s = line.strip()
        if s.startswith("- ") and key is not None:
            if not isinstance(out.get(key), list):
                out[key] = []
            out[key].append(_scalar(s[2:]))
            continue
        if ":" in s and not line.startswith((" ", "\t")):
            k, v = s.split(":", 1)
            key = k.strip()
            out[key] = _scalar(v) if v.strip() else []
    return out


def load(path=None):
    path = path or config_path()
    cfg = dict(DEFAULTS)
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return cfg
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
    except Exception:
        data = parse_yaml_subset(text)
    cfg.update({k: v for k, v in data.items() if v is not None})
    if not isinstance(cfg.get("projects"), list):
        cfg["projects"] = [cfg["projects"]] if cfg.get("projects") else []
    return cfg


def host_name():
    """Short machine name. macOS: LocalHostName (stable, ASCII); elsewhere the hostname."""
    name = ""
    if os.path.exists("/usr/sbin/scutil"):
        try:
            name = subprocess.run(["/usr/sbin/scutil", "--get", "LocalHostName"], capture_output=True,
                                  text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            name = ""
    name = name or socket.gethostname().split(".")[0]
    return re.sub(r"[^\w.-]+", "-", name, flags=re.ASCII).strip("-") or "this-machine"


def resolve(cfg):
    root = os.path.abspath(os.path.expanduser(os.environ.get("COS_DATA_ROOT") or cfg["data_root"]))
    fleet = os.path.expanduser(cfg.get("fleet_dir") or "") or os.path.join(root, "fleet")
    machine = cfg.get("machine_id") or host_name()
    return root, os.path.abspath(fleet), machine


CONFIG = load()
ROOT, FLEET, MACHINE = resolve(CONFIG)
MACHINE = re.sub(r"[^\w-]+", "", str(MACHINE))[:64] or "this-machine"  # one safe path component
OWNER = CONFIG.get("owner_name") or "you"
PROJECTS = [str(p) for p in CONFIG.get("projects") or []]
MODE = CONFIG.get("fleet_mode") or "single"
CLAUDE_BIN = CONFIG.get("claude_bin") or "claude"
OVERLAY = os.path.abspath(os.path.expanduser(os.environ.get("COS_OVERLAY") or CONFIG.get("overlay_dir")
                                             or DEFAULTS["overlay_dir"]))


def _int(name):
    try:
        return max(50000, int(CONFIG.get(name) or DEFAULTS[name]))
    except (TypeError, ValueError):
        return DEFAULTS[name]


CLEAR_AT = {"cos": _int("clear_at_cos"), "vp": _int("clear_at_vp"), "coo": _int("clear_at_coo")}
