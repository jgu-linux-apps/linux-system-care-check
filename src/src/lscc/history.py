"""Log of every change the app made (JSON lines), with what is needed to undo it."""
import json
import os
import time

from gi.repository import GLib

LOG_DIR = os.path.join(GLib.get_user_state_dir(), "linux-system-care-check")
LOG = os.path.join(LOG_DIR, "history.jsonl")


def add(kind, title, detail="", undo=None, backup=None, ok=True, preview=False):
    """kind: update | cleanup | uninstall | timevault. undo: dict the History page can act on, e.g.
    {"type": "reinstall", "source": "apt", "items": [...]}. backup: TimeVault snapshot id taken before."""
    os.makedirs(LOG_DIR, exist_ok=True)
    rec = dict(ts=time.time(), kind=kind, title=title, detail=detail, undo=undo, backup=backup, ok=ok,
               preview=preview)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def entries(limit=200):
    try:
        with open(LOG, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out
