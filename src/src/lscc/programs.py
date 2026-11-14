"""Installed programs from every source, read from the app launchers (.desktop files). Read only (no root).

Sources: apt (.deb), snap, flatpak, AppImage, Steam games and web apps. Web apps are launchers made by a
browser for a site: Chrome/Chromium/Edge/Brave put `--app-id=<id>` in Exec (or `crx_` in StartupWMClass),
GNOME Web uses `org.gnome.Epiphany.WebApp_*`. Removing a web app removes its launcher and icon only —
the site data stays in the browser."""
import configparser
import glob
import os
import re
from dataclasses import dataclass, field

from . import safety
from .i18n import _
from .sysrun import have, parse_size, run

HOME = os.path.expanduser("~")
USER_APPS = os.path.join(HOME, ".local/share/applications")
DIRS = [
    ("/usr/share/applications", "system"),
    ("/usr/local/share/applications", "local"),
    ("/var/lib/snapd/desktop/applications", "snap"),
    ("/var/lib/flatpak/exports/share/applications", "flatpak"),
    (os.path.join(HOME, ".local/share/flatpak/exports/share/applications"), "flatpak-user"),
    (USER_APPS, "user"),
]


@dataclass
class Program:
    name: str
    source: str              # apt | snap | flatpak | appimage | steam | webapp | other
    ident: str               # package / snap / flatpak id / desktop path / steam id
    desktop: str
    icon: str = ""
    size: int = 0
    origin: str = ""         # e.g. "Chrome", "Flathub", "Snap Store", ".deb"
    protected: bool = False
    note: str = ""
    extra: dict = field(default_factory=dict)


def read_desktop(path):
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
        return dict(cp["Desktop Entry"]) if cp.has_section("Desktop Entry") else None
    except (configparser.Error, UnicodeDecodeError, OSError):
        return None


def localized_name(d, lang):
    return d.get(f"Name[{lang}]") or d.get("Name") or ""


WEB_BROWSERS = (("google-chrome", "Chrome"), ("chromium", "Chromium"), ("microsoft-edge", "Edge"),
                ("brave", "Brave"), ("vivaldi", "Vivaldi"), ("opera", "Opera"))


def classify_webapp(fname, d):
    """(is_webapp, browser) for a launcher."""
    exe = d.get("Exec", "")
    if fname.startswith("org.gnome.Epiphany.WebApp_"):
        return True, "GNOME Web"
    if "--app-id=" in exe or d.get("StartupWMClass", "").startswith("crx_"):
        for key, label in WEB_BROWSERS:
            if key in exe:
                return True, label
        return True, "Chromium"
    return False, ""


def classify(path, kind, d):
    """Source of a launcher: (source, ident, origin)."""
    fname = os.path.basename(path)
    web, browser = classify_webapp(fname, d)
    if web:
        return "webapp", path, browser
    exe = d.get("Exec", "")
    if kind == "snap":
        return "snap", fname.split("_")[0], "Snap Store"
    if kind.startswith("flatpak"):
        return "flatpak", fname[:-len(".desktop")], "Flathub" if kind == "flatpak" else "Flathub (user)"
    if ".AppImage" in exe or ".appimage" in exe:
        return "appimage", path, "AppImage"
    m = re.search(r"steam://rungameid/(\d+)", exe)
    if m:
        return "steam", m.group(1), "Steam"
    if kind in ("system", "local"):
        return "apt", path, ".deb"
    return "other", path, "local launcher"


def dpkg_owners(paths):
    """{desktop path: package} for launchers owned by a .deb (one dpkg -S call)."""
    if not paths:
        return {}
    owners = {}
    for chunk in range(0, len(paths), 200):
        rc, out, _err = run(["dpkg", "-S", *paths[chunk:chunk + 200]], timeout=60)
        for line in out.splitlines():
            if ": " in line:
                pkgs, path = line.split(": ", 1)
                owners[path.strip()] = pkgs.split(",")[0].split(":")[0].strip()
    return owners


def apt_sizes(pkgs):
    if not pkgs:
        return {}
    rc, out, _err = run(["dpkg-query", "-W", "-f=${Package} ${Installed-Size}\n", *sorted(set(pkgs))], timeout=60)
    sizes = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 2 and p[1].isdigit():
            sizes[p[0]] = int(p[1]) * 1024
    return sizes


def flatpak_sizes():
    if not have("flatpak"):
        return {}
    rc, out, _err = run(["flatpak", "list", "--app", "--columns=application,size"], timeout=30)
    return {p[0]: parse_size(p[1]) for p in (line.split("\t") for line in out.splitlines()) if len(p) >= 2}


def snap_sizes():
    sizes = {}
    for f in glob.glob("/var/lib/snapd/snaps/*.snap"):
        name = os.path.basename(f).rsplit("_", 1)[0]
        try:
            sizes[name] = sizes.get(name, 0) + os.path.getsize(f)
        except OSError:
            pass
    return sizes


def list_programs(lang="pl"):
    seen, progs, apt_paths = {}, [], []
    for d, kind in DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            de = read_desktop(path)
            if not de or de.get("Type") != "Application" or de.get("NoDisplay", "").lower() == "true":
                continue
            if de.get("Hidden", "").lower() == "true":
                continue
            src, ident, origin = classify(path, kind, de)
            p = Program(localized_name(de, lang), src, ident, path, de.get("Icon", ""), origin=origin)
            key = (src, ident)
            if key in seen:
                continue
            seen[key] = True
            if src == "apt":
                apt_paths.append(path)
            progs.append(p)
    owners = dpkg_owners(apt_paths)
    for p in progs:
        if p.source == "apt":
            pkg = owners.get(p.desktop)
            if pkg:
                p.ident = pkg
            else:
                p.source, p.origin = "other", "local launcher"
    sz_apt = apt_sizes([p.ident for p in progs if p.source == "apt"])
    sz_flat, sz_snap = flatpak_sizes(), snap_sizes()
    for p in progs:
        if p.source == "apt":
            p.size = sz_apt.get(p.ident, 0)
            p.protected = safety.is_protected_pkg(p.ident)
        elif p.source == "flatpak":
            p.size = sz_flat.get(p.ident, 0)
        elif p.source == "snap":
            p.size = sz_snap.get(p.ident, 0)
            p.protected = p.ident in safety.PROTECTED_SNAPS
        elif p.source == "webapp":
            p.note = _("skrót + ikona")
    # one entry per package: several launchers of one .deb (e.g. LibreOffice) are one program
    merged, by_pkg = [], {}
    for p in progs:
        if p.source in ("apt", "snap", "flatpak") and (p.source, p.ident) in by_pkg:
            first = by_pkg[(p.source, p.ident)]
            first.extra.setdefault("launchers", []).append(p.name)
            continue
        by_pkg[(p.source, p.ident)] = p
        merged.append(p)
    return sorted(merged, key=lambda p: p.name.lower())


def webapp_icon_files(desktop_path, d=None):
    """Icon files that belong to a web app (only inside ~/.local/share/icons, matched by the Icon name)."""
    d = d or read_desktop(desktop_path) or {}
    icon = d.get("Icon", "")
    if not icon or "/" in icon or not re.match(r"^[A-Za-z0-9_.\-]+$", icon):
        return []
    base = os.path.join(HOME, ".local/share/icons")
    return [f for f in glob.glob(os.path.join(base, "**", icon + ".*"), recursive=True) if os.path.isfile(f)]


def remove_webapp(desktop_path):
    """Remove a web app launcher and its icons — only files inside the user's own directories."""
    real = os.path.realpath(desktop_path)
    if not real.startswith(os.path.realpath(USER_APPS) + os.sep) or not real.endswith(".desktop"):
        raise ValueError("not a user web app launcher")
    d = read_desktop(real) or {}
    web, _browser = classify_webapp(os.path.basename(real), d)
    if not web:
        raise ValueError("not a web app")
    removed = []
    for f in webapp_icon_files(real, d):
        os.remove(f)
        removed.append(f)
    os.remove(real)
    removed.append(real)
    return removed
