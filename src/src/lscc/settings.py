"""Settings (~/.config/linux-system-care-check/settings.json). Nothing automatic is ever on by default."""
import json
import os

from gi.repository import GLib

DIR = os.path.join(GLib.get_user_config_dir(), "linux-system-care-check")
FILE = os.path.join(DIR, "settings.json")
PATH = FILE
DEFAULTS = {
    "theme": "system",            # system | aurora | studio | aubergine
    "preview": True,              # preview mode: show what would happen, change nothing
    "backup_before_uninstall": True,
    "backup_before_kernels": True,
    "backup_before_update": True,
    "backup_before_firmware": False,
    # background (0.2): checking and notifying changes nothing, so it is on; actions need consent
    "background_checks": True,
    "notifications": True,
    "check_hours": 6,
    "tray": True,
    "auto_thumbnails": False,     # consent: remove the thumbnail cache when over 1 GB
    "auto_backup": False,
    "auto_prune_archives": False, # consent: move log archives older than archive_keep_days to the Trash
    "archive_keep_days": 30,
    "monitor_view": "charts",     # charts | htop
    "tray_live": "off",           # off | cpu | ram | temp | net — live tray icon
    "tray_live_style": "graph",   # graph | number
    "renderer": "auto",           # auto (GTK default) | gl | vulkan | cairo — read by the launcher         # consent: start a TimeVault backup when the last one is older than 7 days
}


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def save(**kw):
    s = load()
    s.update(kw)
    os.makedirs(DIR, exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, FILE)
    return s
