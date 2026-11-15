"""Background checks (session autostart: `linux-system-care-check --background`).

Every few hours it checks the system and shows GNOME notifications with buttons. A button only opens the
right page of the app (where every change is confirmed) or starts a TimeVault backup — the user's click is
the consent. Automatic actions run only when the user switched them on in Settings (all off by default):
  * auto_thumbnails  — remove the thumbnail cache when it grows over 1 GB (user files, re-created by GNOME)
  * auto_backup      — start a Linux Backup TimeVault backup when the last one is older than 7 days
Ubuntu's own automatic security updates and GNOME's old-Trash cleanup are system settings the Settings
dialog switches directly; they do not run here.
The tray icon (optional) shows the state and gives quick access. Only one instance runs (bus name)."""
import json
import os
import shutil
import subprocess
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import APP_ID, APP_NAME, PKG_NAME, cleanup, health, history, hw, settings, timevault, updates  # noqa: E402
from .i18n import _  # noqa: E402
from .sysrun import human  # noqa: E402

BUS_NAME = APP_ID + ".Background"
STATE = os.path.join(GLib.get_user_state_dir(), "linux-system-care-check", "background.json")
FIRST_DELAY = 120            # seconds after login
SNOOZE = 24 * 3600


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(STATE + ".tmp", STATE)


def findings(ups, items, disk, tv_installed, tv_age, tv_connected, drives, bat):
    """What is worth telling the user: [(tag, summary, body, [(action, label)], key)].
    key changes when the situation changes, so a snoozed notice comes back only when something new happens."""
    out = []
    sec = [u for u in ups if u.security]
    if sec:
        out.append(("security", _("Aktualizacje bezpieczeństwa"),
                    f"{len(sec)}: " + ", ".join(u.name for u in sec[:4]) + ("…" if len(sec) > 4 else ""),
                    [("open:updates", _("Pokaż")), ("snooze", _("Później"))], ",".join(sorted(u.name for u in sec))))
    elif len(ups) >= 15:
        out.append(("updates", _("Dostępne aktualizacje"), f"{len(ups)} " + _("aktualizacji czeka na instalację"),
                    [("open:updates", _("Pokaż")), ("snooze", _("Później"))], str(len(ups) // 10)))
    used, total = disk
    if total and used / total > 0.9:
        out.append(("disk", _("Mało miejsca na dysku"), f"{round(100 * used / total)}% " + _("zajęte") + " · " +
                    human(total - used) + " " + _("wolne"),
                    [("open:cleanup", _("Posprzątaj")), ("snooze", _("Później"))], str(round(100 * used / total))))
    clean = sum(i.size for i in items if i.default_on)
    if clean > 5e9:
        out.append(("cleanup", _("Można odzyskać miejsce"), f"{human(clean)} " + _("do odzyskania (pamięć apt, stare snapy, logi)"),
                    [("open:cleanup", _("Podgląd")), ("snooze", _("Później"))], str(int(clean // 1e9))))
    if tv_installed and tv_connected and (tv_age is None or tv_age > 7):
        out.append(("backup", _("Brak świeżej kopii systemu"),
                    _("Ostatnia kopia w Linux Backup TimeVault: ") + (f"{tv_age:.0f} " + _("dni temu") if tv_age else _("brak")),
                    [("backup", _("Utwórz kopię")), ("snooze", _("Później"))], str(int(tv_age or 0) // 7)))
    bad = [d for d in drives if d.get("smart") and not d["smart"]["ok"]]
    if bad:
        out.append(("smart", _("Dysk może się psuć"), ", ".join(d["model"] for d in bad) + " — " +
                    _("zrób kopię zapasową danych"),
                    [("open:disk", _("Pokaż")), ("snooze", _("Później"))], ",".join(d["model"] for d in bad)))
    if bat and bat.get("health") and bat["health"] < 60:
        out.append(("battery", _("Bateria jest mocno zużyta"), f"{bat['health']}% " + _("pojemności fabrycznej"),
                    [("open:battery", _("Pokaż")), ("snooze", _("Później"))], str(bat["health"] // 10)))
    return out


def should_notify(state, tag, key, now):
    rec = state.get(tag) or {}
    if rec.get("key") != key:
        return True
    return now >= rec.get("until", 0)


class Background:
    def __init__(self):
        from .notify import Notifier
        self.loop = GLib.MainLoop()
        self.tray = None
        self.summary = _("Sprawdzam…")
        self.alert = False
        self.timer = 0
        self.running = False
        self.notifier = Notifier(APP_NAME, APP_ID, APP_ID, self._on_action)
        self.keys = {}
        self.live = None
        self.live_timer = 0
        f = Gio.File.new_for_path(settings.PATH)
        self.mon = f.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.mon.connect("changed", lambda *_: GLib.timeout_add(300, self._settings_changed))
        self._settings_changed()
        GLib.timeout_add_seconds(FIRST_DELAY, self._first)

    # ------------------------------------------------ settings / tray
    def _settings_changed(self):
        s = settings.load()
        from . import i18n
        if i18n._lang() != i18n.LANG:                      # Settings → Language: restart in the new language
            if self.tray is not None:
                self.tray.close()
            self.notifier.close_all()
            import sys
            os.execv(sys.executable, [sys.executable] + sys.argv)
        if not s["background_checks"] and not s["tray"]:
            self.loop.quit()
            return False
        if s["tray"] and self.tray is None:
            self._make_tray()
        elif not s["tray"] and self.tray is not None:
            self.tray.close()
            self.tray = None
        self._schedule()
        self._live_setup(s)
        if self.tray:
            self.tray.set_items(self._tray_items())       # radio marks follow the settings
        return False

    # ------------------------------------------------ live icon (CPU / RAM / TEMP / NET)
    def _live_setup(self, s):
        want = s["tray"] and s["tray_live"] in ("cpu", "ram", "temp", "net")
        if want and not self.live_timer:
            from .liveicon import LiveIcon
            self.live = self.live or LiveIcon()
            self.live_timer = GLib.timeout_add_seconds(2, self._live_tick)
            self._live_tick()
        elif not want and self.live_timer:
            GLib.source_remove(self.live_timer)
            self.live_timer = 0
            if self.tray:
                self.tray.set_pixmap(0, 0, None)
                self.tray.set_tooltip(f"{APP_NAME} – {self.summary}")

    def _live_tick(self):
        s = settings.load()
        if not self.tray or s["tray_live"] not in ("cpu", "ram", "temp", "net"):
            self.live_timer = 0
            return False
        try:
            from .liveicon import SIZE
            img, tip = self.live.update(s["tray_live"], s["tray_live_style"])
            self.tray.set_pixmap(SIZE, SIZE, img)
            self.tray.set_tooltip(f"{tip} · {self.summary}")
        except (OSError, ValueError) as e:
            print("live icon:", e)
        return True

    def _make_tray(self):
        from .tray import Tray
        try:
            self.tray = Tray(APP_ID, APP_NAME, self._tray_icon(), lambda: self.open_app(), self._tray_items())
        except Exception as e:  # noqa: BLE001
            print("tray:", e)
            self.tray = None

    def _tray_icon(self):
        return "lscc-tray-alert" if self.alert else "lscc-tray"

    def _tray_items(self):
        st = settings.load()
        live = st["tray_live"]
        style = st["tray_live_style"]
        items = [(1, _("Otwórz System Care Check"), lambda: self.open_app()),
                 (2, None, None),
                 (3, self.summary, None),
                 (4, _("Sprawdź teraz"), lambda: self.check()),
                 (5, None, None),
                 (10, _("Ikona na żywo:"), None)]
        for i, (key, name) in enumerate((("off", _("Wyłączona (stan systemu)")), ("cpu", "CPU"), ("ram", "RAM"),
                                         ("temp", _("Temperatura CPU")), ("net", _("Sieć ↓ / ↑")))):
            items.append((11 + i, name, lambda k=key: settings.save(tray_live=k), live == key))
        if live != "off":
            items += [(20, None, None),
                      (21, _("Wykres słupkowy"), lambda: settings.save(tray_live_style="graph"), style == "graph"),
                      (22, _("Liczba"), lambda: settings.save(tray_live_style="number"), style == "number")]
        items += [(30, None, None),
                  (31, _("Ukryj ikonę w trayu"), lambda: settings.save(tray=False)),
                  (32, _("Zamknij"), self.quit)]
        return items

    def quit(self):
        """Tray "Close": stop the icon and the background checks until the next login or app start."""
        if self.tray is not None:
            self.tray.close()
            self.tray = None
        self.notifier.close_all()
        self.loop.quit()

    def _update_tray(self):
        if self.tray:
            self.tray.set_icon(self._tray_icon())
            self.tray.set_tooltip(f"{APP_NAME} – {self.summary}")
            self.tray.set_items(self._tray_items())

    # ------------------------------------------------ checks
    def _schedule(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        s = settings.load()
        if s["background_checks"]:
            self.timer = GLib.timeout_add_seconds(int(s["check_hours"]) * 3600, self._tick)

    def _first(self):
        self.check()
        return False

    def _tick(self):
        self.check()
        return True

    def check(self):
        if self.running:
            return
        self.running = True
        import threading

        def work():
            ups, _err = updates.check_all()
            items = cleanup.scan()
            disk = health.disk_root()
            tvi = timevault.installed()
            st = timevault.status() if tvi else {}
            return dict(ups=ups, items=items, disk=disk, tvi=tvi, tv_age=timevault.last_backup_age_days(st) if tvi else None,
                        tv_conn=timevault.disk_connected(st) if tvi else False, drives=hw.drives(), bat=hw.battery_info())

        def t():
            try:
                res = work()
            except Exception as e:  # noqa: BLE001
                print("check failed:", e)
                res = None
            GLib.idle_add(lambda: (self._checked(res), False)[1])
        threading.Thread(target=t, daemon=True).start()

    def _checked(self, r):
        self.running = False
        if r is None:
            return
        s = settings.load()
        fs = findings(r["ups"], r["items"], r["disk"], r["tvi"], r["tv_age"], r["tv_conn"], r["drives"], r["bat"])
        self.alert = any(f[0] in ("security", "disk", "smart") for f in fs)
        clean = sum(i.size for i in r["items"] if i.default_on)
        self.summary = f"{len(r['ups'])} " + _("aktualizacji") + f" · {human(clean)} " + _("do odzyskania")
        self._update_tray()
        try:
            from . import metrics
            used, total = r["disk"]
            sec = sum(1 for u in r["ups"] if u.security)
            metrics.record(health.score(sec, len(r["ups"]), used / total, clean, r["tv_age"], r["tvi"]),
                           100 * used / total, len(r["ups"]), clean)
        except (OSError, ZeroDivisionError):
            pass
        self._auto_actions(s, r)
        if not s["background_checks"] or not s["notifications"]:
            return
        state, now = load_state(), time.time()
        for tag, summary, body, actions, key in fs:
            self.keys[tag] = key
            if should_notify(state, tag, key, now):
                self.notifier.show(tag, summary, body, actions, urgency=2 if tag in ("smart",) else 1)
                state[tag] = dict(key=key, until=now + SNOOZE)
        save_state(state)

    def _auto_actions(self, s, r):
        if s["auto_prune_archives"]:
            from . import logarchive
            moved = logarchive.prune(int(s["archive_keep_days"]))
            if moved:
                history.add("cleanup", _("Automatycznie: archiwa logów do Kosza") + f": {len(moved)}", detail="auto")
        if s["auto_thumbnails"]:
            th = next((i for i in r["items"] if i.id == "thumbnails"), None)
            if th and th.size > 1e9:
                ok = cleanup.clean_user("thumbnails")
                history.add("cleanup", _("Automatycznie: miniatury") + f" · {human(th.size)}", ok=ok, detail="auto")
        if s["auto_backup"] and r["tvi"] and r["tv_conn"] and (r["tv_age"] is None or r["tv_age"] > 7):
            ok, err = timevault.start_backup()
            history.add("timevault", _("Automatycznie: kopia w Linux Backup TimeVault"), ok=ok, detail=err or "auto")
            if ok and s["notifications"]:
                self.notifier.show("auto-backup", _("Kopia systemu"),
                                   _("Linux Backup TimeVault robi kopię w tle (włączone w ustawieniach)."))

    # ------------------------------------------------ notification buttons
    def _on_action(self, tag, key, token):
        if key == "snooze":
            st = load_state()
            st[tag] = dict(key=self.keys.get(tag, ""), until=time.time() + SNOOZE)
            save_state(st)
        elif key == "backup":
            ok, err = timevault.start_backup()
            history.add("timevault", _("Uruchomiono kopię w Linux Backup TimeVault (z powiadomienia)"), ok=ok, detail=err)
        elif key.startswith("open:"):
            self.open_app(key[5:], token)
        else:                                   # click on the notification itself
            self.open_app({"security": "updates", "updates": "updates", "disk": "cleanup", "cleanup": "cleanup",
                           "backup": "timevault", "smart": "disk", "battery": "battery"}.get(tag, "overview"), token)

    @staticmethod
    def open_app(page="overview", token=None):
        env = dict(os.environ)
        if token:
            env["XDG_ACTIVATION_TOKEN"] = token
        exe = shutil.which(PKG_NAME) or PKG_NAME
        subprocess.Popen([exe, "--page", page], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run(self):
        self.loop.run()


_BUS = None          # see desktop._BUS: the connection must outlive main() locals


def main():
    global _BUS
    try:
        bus = _BUS = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                            GLib.Variant("(su)", (BUS_NAME, 4)), GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 3000, None)
        if res.unpack()[0] not in (1, 4):          # 1 = primary owner, 4 = already ours
            return 0
    except GLib.Error as e:
        print("no session bus:", e.message)
        return 1
    s = settings.load()
    if not s["background_checks"] and not s["tray"]:
        return 0
    Background().run()
    return 0


def ensure_running():
    """Start the background process from the app (the autostart entry does it at the next login)."""
    exe = shutil.which(PKG_NAME)
    if exe:
        subprocess.Popen([exe, "--background"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
