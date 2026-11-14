"""Archives of system logs made by Cleanup (Documents/System logs archive/*.txt.xz).

Archives stay on disk; they are removed only when the user asks (button) or allowed it (setting
auto_prune_archives). Removal goes to the Trash, so it can still be undone."""
import glob
import os
import time

from gi.repository import Gio, GLib

DIR_NAME = "System logs archive"


def archive_dir():
    docs = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~/Documents")
    return os.path.join(docs, DIR_NAME)


def archives(base=None):
    """[(path, mtime, size)] newest first."""
    base = base or archive_dir()
    out = []
    for p in glob.glob(os.path.join(base, "journal-until-*.txt.xz")):
        try:
            st = os.stat(p)
            out.append((p, st.st_mtime, st.st_size))
        except OSError:
            pass
    return sorted(out, key=lambda x: -x[1])


def older_than(days, base=None, now=None):
    now = now or time.time()
    return [a for a in archives(base) if now - a[1] > days * 86400]


def prune(days, base=None):
    """Move archives older than `days` to the Trash. Returns the list of moved paths."""
    moved = []
    for path, _m, _s in older_than(days, base):
        try:
            Gio.File.new_for_path(path).trash(None)
            moved.append(path)
        except GLib.Error:
            pass
    return moved
