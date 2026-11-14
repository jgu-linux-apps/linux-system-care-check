"""Programs that start with the session (XDG autostart). Read without root; switching an entry on or off
writes only the user's own copy in ~/.config/autostart (the standard GNOME way, the same as GNOME Tweaks),
so it is always reversible and never touches system files."""
import configparser
import os

from gi.repository import GLib

SYSTEM_DIRS = ["/etc/xdg/autostart"]
USER_DIR = os.path.join(GLib.get_user_config_dir(), "autostart")
MARK = "X-LSCC-Override"


def _read(path):
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError, OSError):
        return None
    return dict(cp["Desktop Entry"]) if cp.has_section("Desktop Entry") else None


def _shown_in_gnome(d):
    only = [x for x in d.get("OnlyShowIn", "").split(";") if x]
    notin = [x for x in d.get("NotShowIn", "").split(";") if x]
    if only and not any(x in ("GNOME", "Unity", "ubuntu") for x in only):
        return False
    return "GNOME" not in notin


def enabled(d):
    return (d.get("Hidden", "").lower() != "true" and d.get("X-GNOME-Autostart-enabled", "true").lower() != "false")


def entries(lang="pl", system_dirs=None, user_dir=None):
    """[{file, name, comment, exec, icon, enabled, system, hidden_entry, user_path, system_path}]."""
    system_dirs = system_dirs or SYSTEM_DIRS
    user_dir = user_dir or USER_DIR
    files = {}
    for d in system_dirs:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".desktop"):
                    files.setdefault(f, {})["system"] = os.path.join(d, f)
    if os.path.isdir(user_dir):
        for f in sorted(os.listdir(user_dir)):
            if f.endswith(".desktop"):
                files.setdefault(f, {})["user"] = os.path.join(user_dir, f)
    out = []
    for f, where in files.items():
        sysd = _read(where["system"]) if "system" in where else None
        usrd = _read(where["user"]) if "user" in where else None
        eff = dict(sysd or {})
        if usrd:
            eff.update(usrd)
        if not eff or eff.get("Type", "Application") != "Application":
            continue
        if not _shown_in_gnome(eff):
            continue
        out.append(dict(file=f, name=eff.get(f"Name[{lang}]") or eff.get("Name") or f[:-8],
                        comment=eff.get(f"Comment[{lang}]") or eff.get("Comment", ""), exec=eff.get("Exec", ""),
                        icon=eff.get("Icon", ""), enabled=enabled(eff), system=sysd is not None,
                        internal=(sysd or eff).get("NoDisplay", "").lower() == "true",
                        user_path=where.get("user"), system_path=where.get("system")))
    return sorted(out, key=lambda e: (e["internal"], e["name"].lower()))


def set_enabled(entry, on, user_dir=None):
    """Switch an entry on/off by writing the user's copy only. Returns the path written."""
    user_dir = user_dir or USER_DIR
    fname = entry["file"]
    if "/" in fname or not fname.endswith(".desktop"):
        raise ValueError("bad autostart entry")
    os.makedirs(user_dir, exist_ok=True)
    dest = os.path.join(user_dir, fname)
    src = entry.get("user_path") or entry.get("system_path")
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(src, encoding="utf-8")
    if not cp.has_section("Desktop Entry"):
        raise ValueError("bad autostart entry")
    sec = cp["Desktop Entry"]
    sec["X-GNOME-Autostart-enabled"] = "true" if on else "false"
    if "Hidden" in sec:
        sec["Hidden"] = "false" if on else sec["Hidden"]
    if entry.get("system_path") and not entry.get("user_path"):
        sec[MARK] = "true"
    with open(dest + ".tmp", "w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
    os.replace(dest + ".tmp", dest)
    # our own override of a system entry switched back on = same as no override: remove it
    if on and entry.get("system_path") and sec.get(MARK) == "true":
        sysd = _read(entry["system_path"]) or {}
        if enabled(sysd):
            os.remove(dest)
            return None
    return dest
