"""A small history of the system's state for the Overview charts (JSON lines, at most one point an hour,
kept for 90 days): health score, disk use, number of updates, space to free."""
import json
import os
import time

from gi.repository import GLib

FILE = os.path.join(GLib.get_user_state_dir(), "linux-system-care-check", "metrics.jsonl")
EVERY = 3600
KEEP = 90 * 86400


def load(days=30, path=None, now=None):
    path = path or FILE
    now = now or time.time()
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    p = json.loads(line)
                except ValueError:
                    continue
                if now - p.get("ts", 0) <= days * 86400:
                    out.append(p)
    except OSError:
        pass
    return sorted(out, key=lambda p: p["ts"])


def record(score, disk_pct, updates, cleanable, path=None, now=None):
    """Add a point unless the last one is less than an hour old. Returns True when written."""
    path = path or FILE
    now = now or time.time()
    pts = load(days=KEEP / 86400, path=path, now=now)
    if pts and now - pts[-1]["ts"] < EVERY:
        return False
    pts.append(dict(ts=now, score=int(score), disk=round(disk_pct, 1), updates=int(updates), clean=int(cleanable)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        for p in pts:
            f.write(json.dumps(p) + "\n")
    os.replace(path + ".tmp", path)
    return True


def daily(points):
    """One value per day (the last point of each day) — smoother charts for 30 days."""
    by = {}
    for p in points:
        by[time.strftime("%Y-%m-%d", time.localtime(p["ts"]))] = p
    return [by[k] for k in sorted(by)]
