"""Desktop integration: the app icon follows the light/dark system theme, also while the app is closed
(a session autostart entry runs watch())."""
import os
import shutil

from gi.repository import Gio, GLib

from . import APP_ID

USER_ICON = os.path.join(GLib.get_user_data_dir(), "icons/hicolor/scalable/apps", APP_ID + ".svg")
USER_DESKTOP = os.path.join(GLib.get_user_data_dir(), "applications", APP_ID + ".desktop")
SYSTEM_DESKTOP = os.path.join("/usr/share/applications", APP_ID + ".desktop")
ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "icons")


def icon_file(dark):
    for base in (ICONS, "/usr/share/linux-system-care-check/data/icons"):
        p = os.path.realpath(os.path.join(base, "app-dark.svg" if dark else "app-light.svg"))
        if os.path.exists(p):
            return p
    return None


def system_dark():
    try:
        src = Gio.SettingsSchemaSource.get_default()
        if src and src.lookup("org.gnome.desktop.interface", True):
            s = Gio.Settings.new("org.gnome.desktop.interface")
            if s.get_string("color-scheme") == "prefer-dark":
                return True
            return "-dark" in s.get_string("gtk-theme").lower()
    except Exception:  # noqa: BLE001
        pass
    return False


def _write_if_changed(path, data):
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)
    return True


def apply_icon(dark=None):
    """The same proven way as the other apps of the series (e.g. Linux Español Learning): in dark mode the dark
    icon is copied under the app's icon name into ~/.local/share/icons/hicolor (it wins over /usr/share), in
    light mode the copy is removed, and the icon theme folders are touched so GNOME Shell re-reads them.
    No user copy of the .desktop file (GNOME Shell did not refresh an Icon= path change)."""
    if os.path.exists(USER_DESKTOP):                # left by 0.2.0–0.2.4: remove, the system file is used again
        try:
            with open(USER_DESKTOP, encoding="utf-8") as f:
                ours = "/linux-system-care-check/data/icons/" in f.read()
            if ours:
                os.remove(USER_DESKTOP)
                if shutil.which("update-desktop-database"):
                    os.system(f"update-desktop-database -q '{os.path.dirname(USER_DESKTOP)}' >/dev/null 2>&1")
        except OSError:
            pass
    if not os.path.exists(SYSTEM_DESKTOP):          # uninstalled: clean up
        if os.path.exists(USER_ICON):
            os.remove(USER_ICON)
        return None
    dark = system_dark() if dark is None else dark
    changed = False
    if dark:
        src = icon_file(True)
        if src:
            with open(src, "rb") as f:
                changed = _write_if_changed(USER_ICON, f.read())
    elif os.path.exists(USER_ICON):
        os.remove(USER_ICON)
        changed = True
    if changed:
        base = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor")
        for d in (base, os.path.dirname(base)):
            try:
                os.utime(d, None)                    # GNOME Shell watches the theme folders' mtime
            except OSError:
                pass
    return "dark" if dark else "light"


_BUS = None          # keep the connection: GIO holds the shared bus only weakly, and the owned name
                     # is released as soon as the connection is finalised


def _single_instance():
    global _BUS
    try:
        bus = _BUS = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                            GLib.Variant("(su)", (APP_ID + ".IconSync", 4)), GLib.VariantType("(u)"),
                            Gio.DBusCallFlags.NONE, 3000, None)
        return res.unpack()[0] in (1, 4)
    except GLib.Error:
        return True


def watch():
    if not _single_instance():
        return
    apply_icon()
    src = Gio.SettingsSchemaSource.get_default()
    if not (src and src.lookup("org.gnome.desktop.interface", True)):
        return
    s = Gio.Settings.new("org.gnome.desktop.interface")
    s.connect("changed::color-scheme", lambda *_: apply_icon())
    s.connect("changed::gtk-theme", lambda *_: apply_icon())
    GLib.MainLoop().run()
