"""The pages: Overview, Updates, Cleanup, Programs, Linux Backup TimeVault, History."""
import os
import platform
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import cleanup, health, helperclient, history, programs, safety, settings, timevault, updates  # noqa: E402
from ..i18n import _  # noqa: E402
from ..sysrun import human, run  # noqa: E402
from .common import Ring, card, chip, clear, confirm, in_background, label, page_box, scrolled, ProgressDialog  # noqa: E402

SRC_LABEL = {"apt": "apt", "snap": "snap", "flatpak": "flatpak", "firmware": "firmware", "appimage": "AppImage",
             "steam": "Steam", "webapp": "webapp", "other": _("inne")}


def header(title, subtitle="", *buttons):
    row = Gtk.Box(spacing=10)
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    term = settings.load()["theme"] == "terminal"
    col.append(label(("$ " + title.lower().replace(" ", "-")) if term else title, "lscc-title"))
    sub = label(subtitle, "dim-label")
    col.append(sub)
    row.append(col)
    for b in buttons:
        b.set_valign(Gtk.Align.CENTER)
        row.append(b)
    row.sub = sub
    return row


def button(text, cb, primary=False, icon=None):
    b = Gtk.Button()
    if icon:
        b.set_child(Adw.ButtonContent(icon_name=icon, label=text))
    else:
        b.set_label(text)
    if primary:
        b.add_css_class("suggested-action")
    b.add_css_class("pill")
    b.connect("clicked", lambda *_: cb())
    return b


# ====================================================================== running changes
class Operator:
    """Runs a list of steps with an optional TimeVault backup first; in preview mode only describes them."""

    def __init__(self, win):
        self.win = win

    def run(self, title, steps, kind, summary, undo=None, backup=False, after=None):
        """steps: [(description, fn)] where fn(preview) -> (ok, output)."""
        prev = settings.load()["preview"]
        dlg = ProgressDialog(self.win, title)

        def work():
            backup_id = None
            if backup and not prev:
                dlg.set_status(_("Kopia systemu w Linux Backup TimeVault…"))
                ok, err = timevault.start_backup()
                if not ok:
                    return False, "TimeVault: " + err, None
                ok, msg = timevault.wait_backup(on_progress=lambda st: dlg.set_status(
                    _("Kopia systemu w Linux Backup TimeVault…") + f" ({st.get('state', '')})"))
                if not ok:
                    return False, "TimeVault: " + msg, None
                backup_id = timevault.status().get("last_snapshot")
                dlg.log(f"TimeVault: kopia {backup_id} gotowa")
            elif backup and prev:
                dlg.log("PREVIEW: najpierw kopia systemu w Linux Backup TimeVault (timevault-backup-now.service)")
            all_ok = True
            for desc, fn in steps:
                dlg.set_status(desc)
                dlg.log("→ " + desc)
                ok, out = fn(prev)
                for line in (out or "").splitlines()[-40:]:
                    dlg.log("   " + line)
                if not ok:
                    all_ok = False
                    dlg.log("   ✗ " + _("Błąd"))
                    break
            return all_ok, "", backup_id

        def done(res, err):
            ok, msg, backup_id = res if res else (False, str(err), None)
            text = (_("Tryb podglądu — nic nie zostało zmienione") if prev else _("Gotowe")) if ok else (msg or _("Błąd"))
            dlg.finish(ok, text)
            history.add(kind, summary, undo=undo, backup=backup_id, ok=ok, preview=prev)
            if after:
                after()
        in_background(work, done)


def helper_step(desc, op, *args):
    return (desc, lambda prev: helperclient.run(op, *args, preview=prev))


def backup_offer(key):
    s = settings.load()
    if not timevault.installed():
        return None
    connected = timevault.disk_connected()
    note = "" if connected else _("Dysk TimeVault nie jest podłączony — kopia nie jest teraz możliwa.")
    return (connected, note, s.get(key, True))


def preview_note():
    return _("Tryb podglądu: aplikacja pokaże polecenia, ale niczego nie zmieni.") if settings.load()["preview"] else ""


# ====================================================================== Overview
class OverviewPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        hdr = header(_("Sprawdzam system…"), f"{self._os()} · GNOME",
                     button(_("Sprawdź ponownie"), self.refresh, icon="view-refresh-symbolic"))
        self.box.append(hdr)
        sp = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER, height_request=48)
        self.box.append(sp)

        def work():
            ups, _err = updates.check_all()
            items = cleanup.scan()
            return ups, items
        in_background(work, lambda res, err: self._show(hdr, sp, res, err))

    @staticmethod
    def _os():
        try:
            with open("/etc/os-release") as f:
                d = dict(line.rstrip().split("=", 1) for line in f if "=" in line)
            return d.get("PRETTY_NAME", "Linux").strip('"')
        except OSError:
            return "Linux"

    def _show(self, hdr, sp, res, err):
        self.box.remove(sp)
        ups, items = res if res else ([], [])
        self.win.updates_cache = ups
        self.win.set_badge("updates", len(ups))
        sec = [u for u in ups if u.security]
        cleanable = sum(i.size for i in items if i.default_on)
        used, total = health.disk_root()
        tv_ok = timevault.installed()
        age = timevault.last_backup_age_days() if tv_ok else None
        sc = health.score(len(sec), len(ups), used / total, cleanable, age, tv_ok)
        from .. import metrics
        try:
            metrics.record(sc, 100 * used / total, len(ups), cleanable)
        except OSError:
            pass
        hdr.get_first_child().get_first_child().set_text(
            _("Twój system jest w dobrej formie") if sc >= 80 else _("Twój system potrzebuje uwagi"))
        hdr.sub.set_text(f"{self._os()} · {_('sprawdzono')} {time.strftime('%H:%M')}")

        top = card(spacing=0)
        row = Gtk.Box(spacing=26)
        row.append(Ring(sc / 100, f"{sc}%", _("forma systemu"), 132))
        todo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, valign=Gtk.Align.CENTER)
        todo.append(label(_("CO WARTO ZROBIĆ"), "lscc-kicker"))
        n = 0
        if sec:
            n += 1
            todo.append(self._todo(chip(_("Bezpieczeństwo"), "sec"),
                                   f"<b>{len(sec)} {_('aktualizacje bezpieczeństwa')}</b> ({', '.join(u.name for u in sec[:3])})",
                                   _("Pokaż"), lambda: self.win.show_page("updates")))
        if len(ups) > len(sec):
            n += 1
            todo.append(self._todo(chip("apt · snap · flatpak"), f"<b>{len(ups) - len(sec)} {_('zwykłych aktualizacji')}</b>",
                                   _("Pokaż"), lambda: self.win.show_page("updates")))
        if cleanable > 300e6:
            n += 1
            todo.append(self._todo(chip(_("Miejsce"), "warn"), f"<b>{human(cleanable)} {_('do odzyskania')}</b>",
                                   _("Podgląd"), lambda: self.win.show_page("cleanup")))
        if tv_ok and (age is None or age > 7):
            n += 1
            todo.append(self._todo(chip("TimeVault", "warn"), "<b>" + _("Brak świeżej kopii systemu") + "</b>",
                                   _("Pokaż"), lambda: self.win.show_page("timevault")))
        elif not tv_ok:
            n += 1
            todo.append(self._todo(chip("TimeVault"), _("Kopie zapasowe systemu: zainstaluj Linux Backup TimeVault"),
                                   _("Pokaż"), lambda: self.win.show_page("timevault")))
        if updates.reboot_required():
            todo.append(self._todo(chip(_("Restart"), "warn"), _("System wymaga ponownego uruchomienia"), None, None))
        if n == 0:
            todo.append(label("✓ " + _("Wszystko w porządku"), "title-4"))
        row.append(todo)
        top.append(row)
        self.box.append(top)

        grid = Gtk.Grid(column_spacing=14, row_spacing=14, column_homogeneous=True)
        bat = health.battery()
        temp = health.cpu_temp()
        stats = [(_("Aktualizacje"), str(len(ups)), f"{len(ups) - len(sec)} {_('zwykłych')} · {len(sec)} {_('bezp.')}"),
                 (_("Dysk"), f"{round(100 * used / total)}%", f"{human(used)} / {human(total)}"),
                 (_("Bateria"), f"{min(100, bat[0])}%" if bat else "—",
                  (_("pojemności fabrycznej") + (f" · {bat[1]} {_('cykli')}" if bat and bat[1] else "")) if bat else _("brak baterii")),
                 (_("Temperatury"), f"{temp:.0f}°" if temp else "—", _("procesor"))]
        for i, (t, big, small) in enumerate(stats):
            c = card(spacing=2)
            c.append(label(t.upper(), "lscc-kicker"))
            c.append(label(big, "lscc-stat"))
            c.append(label(small, "dim-label caption"))
            grid.attach(c, i, 0, 1, 1)
        self.box.append(grid)

        self.box.append(self._trend())

        recent = history.entries(4)
        if recent:
            c = card(spacing=6)
            c.append(label(_("OSTATNIO"), "lscc-kicker"))
            for e in recent:
                r = Gtk.Box(spacing=8)
                r.append(label(("✓ " if e.get("ok") else "✗ ") + e.get("title", "") +
                               (" (" + _("podgląd") + ")" if e.get("preview") else "")))
                r.append(Gtk.Box(hexpand=True))
                r.append(label(time.strftime("%d.%m %H:%M", time.localtime(e.get("ts", 0))), "dim-label caption"))
                c.append(r)
            self.box.append(c)

    @staticmethod
    def _trend():
        from .. import metrics
        from .common import Chart
        pts = metrics.daily(metrics.load(30))
        c = card(spacing=6)
        top = Gtk.Box(spacing=8)
        top.append(label(_("OSTATNIE 30 DNI"), "lscc-kicker", wrap=False))
        top.append(Gtk.Box(hexpand=True))
        c.append(top)
        if len(pts) < 2:
            c.append(label(_("Wykresy pojawią się po kilku dniach — aplikacja zapisuje stan systemu raz na godzinę "
                             "(przy sprawdzaniu w tle lub w Przeglądzie)."), "dim-label caption"))
            return c
        grid = Gtk.Grid(column_spacing=18, row_spacing=4, column_homogeneous=True)
        for i, (key, title, kind, lo, hi, fmt) in enumerate((
                ("score", _("Forma systemu"), "accent", 0, 100, lambda v: f"{v}%"),
                ("disk", _("Zajęty dysk"), "accent2", None, None, lambda v: f"{v:.0f}%"),
                ("updates", _("Aktualizacje czekające"), "warn", 0, None, lambda v: str(v)))):
            vals = [p.get(key) for p in pts]
            hdr = Gtk.Box(spacing=6)
            hdr.append(label(title, "caption"))
            hdr.append(Gtk.Box(hexpand=True))
            hdr.append(label(fmt(vals[-1]), "heading", wrap=False))
            grid.attach(hdr, i, 0, 1, 1)
            ch = Chart(height=70, lo=lo, hi=hi)
            ch.set_series([(vals, kind)])
            grid.attach(ch, i, 1, 1, 1)
        c.append(grid)
        first = time.strftime("%d.%m", time.localtime(pts[0]["ts"]))
        c.append(label(f"{first} → {_('dziś')} · {len(pts)} {_('dni')}", "dim-label caption"))
        return c

    @staticmethod
    def _todo(ch, markup, btn_text, cb):
        r = Gtk.Box(spacing=10)
        r.append(ch)
        r.append(label(markup, markup=True, wrap=True))
        r.append(Gtk.Box(hexpand=True))
        if btn_text:
            b = Gtk.Button(label=btn_text, valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda *_: cb())
            r.append(b)
        return r


# ====================================================================== Updates
class UpdatesPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.ups = []
        self.refresh()

    def refresh(self):
        clear(self.box)
        self.hdr = header(_("Aktualizacje"), _("Sprawdzam apt, snap, flatpak i firmware…"),
                          button(_("Sprawdź"), self.refresh, icon="view-refresh-symbolic"),
                          button(_("Aktualizuj wszystko"), self.update_all, primary=True))
        self.box.append(self.hdr)
        inst, enabled = updates.unattended_status()
        info = card(spacing=4)
        info.append(label("<b>" + _("Automatyczne aktualizacje bezpieczeństwa Ubuntu") + ":</b> " +
                          (_("włączone") if enabled else _("wyłączone")) + " · " +
                          _("Ubuntu instaluje je samo (unattended-upgrades); ta aplikacja niczego nie instaluje bez Twojej zgody."),
                          markup=True))
        self.box.append(info)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.box.append(self.list)
        in_background(updates.check_all, self._show)

    def _show(self, res, err):
        ups, errors = res if res else ([], {"?": str(err)})
        self.ups = ups
        self.win.set_badge("updates", len(ups))
        by = {}
        for u in ups:
            by[u.source] = by.get(u.source, 0) + 1
        self.hdr.sub.set_text(f"{len(ups)} " + _("aktualizacji") + (": " + ", ".join(f"{k} {v}" for k, v in by.items()) if by else ""))
        if not ups:
            self.list.append(Adw.ActionRow(title="✓ " + _("System jest aktualny")))
        for u in sorted(ups, key=lambda u: (not u.security, u.source, u.name)):
            r = Adw.ActionRow(title=GLib.markup_escape_text(u.name),
                              subtitle=GLib.markup_escape_text(f"{u.old} → {u.new}" if u.old else u.new) +
                              (" · " + GLib.markup_escape_text(u.note) if u.note and u.source == "firmware" else ""))
            r.add_suffix(chip(SRC_LABEL[u.source]))
            if u.security:
                r.add_prefix(chip(_("bezp."), "sec"))
            b = Gtk.Button(label=_("Aktualizuj"), valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda *_a, uu=u: self.update_one(uu))
            r.add_suffix(b)
            self.list.append(r)
        for src, e in errors.items():
            if e:
                self.list.append(Adw.ActionRow(title=f"{src}: " + _("błąd odczytu"), subtitle=GLib.markup_escape_text(e[:200])))

    def update_one(self, u):
        if u.source == "apt":
            step = helper_step(f"apt: {u.name}", "apt-upgrade", u.name)
        elif u.source == "snap":
            step = helper_step(f"snap: {u.name}", "snap-refresh", u.name)
        elif u.source == "flatpak":
            step = helper_step(f"flatpak: {u.name}", "flatpak-update", u.name)
        else:
            dev = (u.extra or {}).get("device_id", "")
            step = helper_step(f"firmware: {u.name}", "fwupd-update", *([dev] if dev else []))
        lines = [f"{u.name}: {u.old} → {u.new}" if u.old else f"{u.name} → {u.new}",
                 _("Tylko ta pozycja; apt nie usunie żadnego pakietu (sprawdzane symulacją).") if u.source == "apt" else ""]
        lines = [ln for ln in lines if ln]
        note = preview_note()
        if note:
            lines.append(note)
        key = "backup_before_firmware" if u.source == "firmware" else "backup_before_update"
        confirm(self.win, _("Zaktualizować?") + f" {u.name}", lines, _("Aktualizuj"),
                lambda b: Operator(self.win).run(_("Aktualizacja"), [step], "update", f"{_('Aktualizacja')}: {u.name}",
                                                 backup=b, after=self.refresh),
                backup_offer=(lambda o: (o[0], o[1], False) if o else None)(backup_offer(key)))

    def update_all(self):
        if not self.ups:
            return
        srcs = sorted({u.source for u in self.ups})
        steps, lines = [], []
        if "apt" in srcs:
            steps += [helper_step(_("Odświeżanie list pakietów apt"), "apt-refresh"),
                      helper_step(_("Aktualizacja pakietów apt (bez usuwania)"), "apt-upgrade")]
            lines.append(f"apt: {sum(u.source == 'apt' for u in self.ups)} " + _("pakietów"))
        if "snap" in srcs:
            steps.append(helper_step(_("Aktualizacja snapów"), "snap-refresh"))
            lines.append(f"snap: {sum(u.source == 'snap' for u in self.ups)}")
        if "flatpak" in srcs:
            steps.append(helper_step(_("Aktualizacja flatpaków"), "flatpak-update"))
            lines.append(f"flatpak: {sum(u.source == 'flatpak' for u in self.ups)}")
        if "firmware" in srcs:
            steps.append(helper_step(_("Aktualizacja firmware"), "fwupd-update"))
            lines.append(_("firmware: ") + ", ".join(u.name for u in self.ups if u.source == "firmware"))
        note = preview_note()
        if note:
            lines.append(note)
        confirm(self.win, _("Zainstalować aktualizacje?"), lines, _("Aktualizuj"),
                lambda b: Operator(self.win).run(_("Aktualizacje"), steps, "update",
                                                 f"{_('Aktualizacje')}: {len(self.ups)}", backup=b, after=self.refresh),
                backup_offer=backup_offer("backup_before_update"))


# ====================================================================== Cleanup
class CleanupPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        self.hdr = header(_("Sprzątanie"), _("Podgląd — nic nie zostanie usunięte bez Twojego potwierdzenia"),
                          button(_("Sprawdź"), self.refresh, icon="view-refresh-symbolic"),
                          button(_("Wyczyść zaznaczone"), self.clean, primary=True))
        self.box.append(self.hdr)
        self.sum = label("", "title-3")
        self.box.append(self.sum)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.box.append(self.list)
        self.box.append(label(_("Bieżące jądro i jedno zapasowe są zawsze zachowane. Sprzątane są tylko rzeczy, "
                                "które system sam odtworzy; Twoje pliki i ustawienia nie są ruszane."), "dim-label caption"))
        self.checks = {}
        in_background(cleanup.scan, self._show)

    def _show(self, items, err):
        self.items = items or []
        journal = next((i for i in self.items if i.id == "journal"), None)
        for it in self.items:
            if it.id == "journal":
                continue
            r = Adw.ActionRow(title=GLib.markup_escape_text(_(it.title)), subtitle=GLib.markup_escape_text(it.detail))
            cb = Gtk.CheckButton(active=it.default_on, valign=Gtk.Align.CENTER)
            cb.set_sensitive(it.size > 0 or bool(it.args) or it.id == "journal")
            cb.connect("toggled", lambda *_: self._sum())
            r.add_prefix(cb)
            r.set_activatable_widget(cb)
            r.add_suffix(label(("ok. " if it.id in ("old-kernels",) else "") + human(it.size), "heading", wrap=False))
            self.checks[it.id] = (cb, it)
            self.list.append(r)
        self._sum()
        self._logs_card(journal)

    def _slider(self, lo, hi, val, marks, fmt):
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        sc.set_value(val)
        sc.set_round_digits(0)
        sc.set_hexpand(True)
        sc.set_draw_value(True)
        sc.set_value_pos(Gtk.PositionType.RIGHT)
        sc.set_format_value_func(lambda _s, v: fmt(int(v)))
        for m in marks:
            sc.add_mark(m, Gtk.PositionType.BOTTOM, None)
        return sc

    def _logs_card(self, journal):
        g = card(spacing=10)
        g.append(label(_("LOGI SYSTEMOWE") + (f" · {human(journal.size)}" if journal else ""), "lscc-kicker"))
        # 1) archive and remove
        g.append(label("<b>" + _("Zarchiwizuj i usuń starsze logi") + "</b>", markup=True))
        g.append(label(_("Logi starsze niż wybrana liczba dni zostaną zapisane do archiwum (skompresowany plik tekstowy w "
                         "Dokumentach, folder „System logs archive”). Archiwum zostaje na dysku — z dziennika systemu "
                         "usuwane są tylko oryginały, które są już w archiwum."), "dim-label caption"))
        row = Gtk.Box(spacing=12)
        self.arch = self._slider(1, 90, 30, (7, 14, 30, 60, 90), lambda v: _("starsze niż %d dni") % v)
        row.append(self.arch)
        b = Gtk.Button(label=_("Zarchiwizuj i usuń"), valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda *_a: self._logs("archive", int(self.arch.get_value())))
        row.append(b)
        g.append(row)
        g.append(Gtk.Separator())
        # 2) remove, keep N weeks
        g.append(label("<b>" + _("Usuń logi, zostaw ostatnie") + "</b>", markup=True))
        g.append(label(_("Bez archiwum: zostają tylko logi z wybranej liczby tygodni."), "dim-label caption"))
        row = Gtk.Box(spacing=12)
        self.keep = self._slider(1, 8, 2, range(1, 9), lambda v: (_("%d tydzień") if v == 1 else _("%d tygodnie") if v < 5 else _("%d tygodni")) % v)
        row.append(self.keep)
        b = Gtk.Button(label=_("Usuń starsze"), valign=Gtk.Align.CENTER)
        b.add_css_class("destructive-action")
        b.connect("clicked", lambda *_a: self._logs("vacuum", int(self.keep.get_value())))
        row.append(b)
        g.append(row)
        g.append(Gtk.Separator())
        # 3) the archives themselves
        from .. import logarchive
        arch = logarchive.archives()
        g.append(label("<b>" + _("Archiwa logów") + "</b> · " + (f"{len(arch)} " + _("plików") + f", {human(sum(a[2] for a in arch))}"
                                                                if arch else _("brak")), markup=True))
        s = settings.load()
        row = Gtk.Box(spacing=12)
        self.prune = self._slider(30, 365, s["archive_keep_days"], (30, 90, 180, 365), lambda v: _("starsze niż %d dni") % v)
        self.prune.connect("value-changed", lambda sc: settings.save(archive_keep_days=int(sc.get_value())))
        row.append(self.prune)
        b = Gtk.Button(label=_("Przenieś do Kosza"), valign=Gtk.Align.CENTER, sensitive=bool(arch))
        b.connect("clicked", lambda *_a: self._prune(int(self.prune.get_value())))
        row.append(b)
        if arch:
            ob = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text=_("Otwórz folder archiwów"))
            ob.connect("clicked", lambda *_a: Gtk.FileLauncher.new(Gio.File.new_for_path(logarchive.archive_dir())).launch(self.win, None, None, None))
            row.append(ob)
        g.append(row)
        sw = Gtk.CheckButton(label=_("Rób to automatycznie (za Twoją zgodą; sprawdzane w tle)"), active=bool(s["auto_prune_archives"]))
        sw.connect("toggled", lambda c: settings.save(auto_prune_archives=c.get_active()))
        g.append(sw)
        self.box.insert_child_after(g, self.list)

    def _prune(self, days):
        from .. import logarchive
        old = logarchive.older_than(days)
        if not old:
            self.win.toast(Adw.Toast(title=_("Brak archiwów starszych niż %d dni") % days))
            return
        lines = [os.path.basename(p) for p, _m, _s in old] + [_("Pliki trafią do Kosza — można je jeszcze przywrócić.")]
        prev = settings.load()["preview"]
        if prev:
            lines.append(preview_note())

        def go(_b):
            moved = [] if prev else logarchive.prune(days)
            history.add("cleanup", _("Archiwa logów do Kosza") + f": {len(old)}", ok=True, preview=prev)
            self.win.toast(Adw.Toast(title=(_("Tryb podglądu — nic nie przeniesiono") if prev else
                                            _("Przeniesiono do Kosza: %d") % len(moved))))
            self.refresh()
        confirm(self.win, _("Przenieść stare archiwa logów do Kosza?"), lines, _("Przenieś"), go)

    def _logs(self, mode, n):
        if mode == "archive":
            lines = [_("Logi starsze niż %d dni → archiwum: Dokumenty/System logs archive/*.txt.xz") % n,
                     _("Archiwum zostaje na dysku; z dziennika systemu znikają tylko zarchiwizowane oryginały.")]
            step = helper_step(_("Archiwizacja logów"), "archive-journal", str(n))
            title = _("Logi: archiwum i usunięcie starszych niż %d dni") % n
        else:
            lines = [_("Zostaną logi z ostatnich %d tyg.; starsze zostaną usunięte bez archiwum.") % n]
            step = helper_step(_("Usuwanie starszych logów"), "vacuum-journal", str(n))
            title = _("Logi: zostawiono %d tyg.") % n
        note = preview_note()
        if note:
            lines.append(note)
        confirm(self.win, _("Logi systemowe"), lines, _("Wykonaj"),
                lambda _b: Operator(self.win).run(_("Logi systemowe"), [step], "cleanup", title, after=self.refresh),
                destructive=mode == "vacuum")

    def _sum(self):
        sel = [it for cb, it in self.checks.values() if cb.get_active()]
        self.sum.set_text(f"{_('Zaznaczone')}: {human(sum(i.size for i in sel))} ({len(sel)})")

    def clean(self):
        sel = [it for cb, it in self.checks.values() if cb.get_active()]
        if not sel:
            return
        steps, lines = [], []
        for it in sel:
            lines.append(f"{_(it.title)} — {human(it.size)}" + (f" ({', '.join(it.args)})" if it.args and it.id == "old-kernels" else ""))
            if it.id == "apt-cache":
                steps.append(helper_step(_(it.title), "clean-apt-cache"))
            elif it.id == "journal":
                steps.append(helper_step(_(it.title), "vacuum-journal"))
            elif it.id == "snap-disabled" and it.args:
                steps.append(helper_step(_(it.title), "remove-snap-revisions", *it.args))
            elif it.id == "old-kernels" and it.args:
                steps.append(helper_step(_(it.title), "remove-kernels", *it.args))
            elif it.id == "flatpak-unused":
                steps.append(helper_step(_(it.title), "flatpak-unused"))
            elif it.id in safety.CLEAN_USER:
                steps.append((_(it.title), lambda prev, i=it.id: (True, f"PREVIEW: {i}") if prev else
                              (cleanup.clean_user(i), "")))
        note = preview_note()
        if note:
            lines.append(note)
        kernels = any(it.id == "old-kernels" and it.args for it in sel)
        confirm(self.win, _("Wyczyścić zaznaczone?"), lines, _("Wyczyść"),
                lambda b: Operator(self.win).run(_("Sprzątanie"), steps, "cleanup",
                                                 f"{_('Sprzątanie')} · {human(sum(i.size for i in sel))}",
                                                 backup=b, after=self.refresh),
                backup_offer=backup_offer("backup_before_kernels") if kernels else None, destructive=True)


# ====================================================================== Programs
class ProgramsPage(Gtk.Box):
    FILTERS = [("all", "Wszystkie"), ("apt", "apt"), ("snap", "snap"), ("flatpak", "flatpak"),
               ("webapp", "Webappy"), ("appimage", "AppImage"), ("steam", "Steam"), ("other", "inne")]

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.progs, self.selected, self.filter = [], {}, "all"
        self.box = page_box()
        self.append(scrolled(self.box))
        self.bar = Gtk.Box(spacing=10, margin_start=24, margin_end=24, margin_bottom=14)
        self.bar.add_css_class("card")
        self.bar.add_css_class("lscc-bar")
        self.bar_label = label("")
        self.bar.append(self.bar_label)
        self.bar.append(Gtk.Box(hexpand=True))
        self.bar.append(button(_("Odznacz"), self._clear_sel))
        ub = button(_("Odinstaluj zaznaczone"), self.uninstall, icon="user-trash-symbolic")
        ub.add_css_class("destructive-action")
        self.bar.append(ub)
        self.bar.set_visible(False)
        self.append(self.bar)
        self.refresh()

    def refresh(self):
        clear(self.box)
        self.selected = {}
        self.search = Gtk.SearchEntry(placeholder_text=_("Szukaj programu…"), width_request=220)
        self.search.connect("search-changed", lambda *_: self._fill())
        self.hdr = header(_("Programy"), _("Wczytywanie…"), self.search)
        self.box.append(self.hdr)
        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6,
                                 max_children_per_line=10, homogeneous=False)
        self.box.append(self.chips)
        self.webinfo = card(spacing=4)
        self.webinfo.append(label("<b>" + _("Webappy") + "</b> — " +
                                  _("strony zainstalowane jako aplikacje (Chrome, Chromium, Edge, Brave, GNOME Web). "
                                    "Usunięcie zabiera skrót z menu i ikonę; dane strony zostają w przeglądarce."), markup=True))
        self.webinfo.set_visible(False)
        self.box.append(self.webinfo)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.box.append(self.list)
        self.bar.set_visible(False)
        in_background(programs.list_programs, self._loaded)

    def _loaded(self, progs, err):
        self.progs = progs or []
        counts = {}
        for p in self.progs:
            counts[p.source] = counts.get(p.source, 0) + 1
        self.hdr.sub.set_text(f"{len(self.progs)} " + _("programów") + f" · {counts.get('webapp', 0)} " + _("webappów"))
        self.chips.remove_all()
        group = None
        for key, name in self.FILTERS:
            n = len(self.progs) if key == "all" else counts.get(key, 0)
            if key != "all" and n == 0:
                continue
            tb = Gtk.ToggleButton(label=f"{_(name)} · {n}", active=key == self.filter)
            tb.add_css_class("pill")
            if group is None:
                group = tb
            else:
                tb.set_group(group)
            tb.connect("toggled", lambda b, k=key: b.get_active() and self._set_filter(k))
            self.chips.append(tb)
        self._fill()

    def _set_filter(self, k):
        self.filter = k
        self._fill()

    def _fill(self):
        clear(self.list)
        q = self.search.get_text().strip().lower()
        self.webinfo.set_visible(self.filter == "webapp")
        shown = 0
        for p in self.progs:
            if self.filter != "all" and p.source != self.filter:
                continue
            if q and q not in p.name.lower() and q not in p.ident.lower():
                continue
            shown += 1
            r = Adw.ActionRow(title=GLib.markup_escape_text(p.name),
                              subtitle=GLib.markup_escape_text(
                                  (p.ident if p.source in ("apt", "snap", "flatpak") else os.path.basename(p.ident))
                                  + (f" · {p.note}" if p.note else "")),
                              title_lines=1, subtitle_lines=1)
            cb = Gtk.CheckButton(valign=Gtk.Align.CENTER, active=id(p) in self.selected)
            removable = p.source in ("apt", "snap", "flatpak", "webapp") and not p.protected
            cb.set_sensitive(removable)
            if p.protected:
                cb.set_tooltip_text(_("Chroniony — potrzebny do działania systemu"))
            elif not removable:
                cb.set_tooltip_text(_("Odinstalowanie z tego źródła będzie dostępne w kolejnej wersji"))
            cb.connect("toggled", lambda b, pp=p: self._toggle(pp, b.get_active()))
            r.add_prefix(cb)
            if removable:
                r.set_activatable_widget(cb)
            img = Gtk.Image(icon_name=p.icon if p.icon and "/" not in p.icon else "application-x-executable", pixel_size=32)
            if p.icon and "/" in p.icon and os.path.exists(p.icon):
                img = Gtk.Image.new_from_file(p.icon)
                img.set_pixel_size(32)
            r.add_prefix(img)
            r.add_suffix(chip(SRC_LABEL.get(p.source, p.source) + (" · " + p.origin if p.source == "webapp" else ""),
                              "ok" if p.source == "webapp" else ""))
            r.add_suffix(label(human(p.size) if p.size else "—", "dim-label", wrap=False))
            if p.protected:
                r.add_suffix(Gtk.Image(icon_name="changes-prevent-symbolic", tooltip_text=_("Chroniony")))
            self.list.append(r)
            if shown >= 400:
                break

    def _toggle(self, p, on):
        if on:
            self.selected[id(p)] = p
        else:
            self.selected.pop(id(p), None)
        n = len(self.selected)
        size = sum(p.size for p in self.selected.values())
        self.bar_label.set_markup(f"<b>{_('Zaznaczone')}: {n}</b> · " + GLib.markup_escape_text(
            ", ".join(p.name for p in list(self.selected.values())[:4])) + (f" · {_('zwolni ok.')} {human(size)}" if size else ""))
        self.bar.set_visible(n > 0)

    def _clear_sel(self):
        self.selected = {}
        self.bar.set_visible(False)
        self._fill()

    def uninstall(self):
        sel = list(self.selected.values())
        apt = sorted({p.ident for p in sel if p.source == "apt"})
        snaps = sorted({p.ident for p in sel if p.source == "snap"})
        flats = [p for p in sel if p.source == "flatpak"]
        webs = [p for p in sel if p.source == "webapp"]
        lines = [f"{p.name} ({SRC_LABEL[p.source]}{' · ' + p.origin if p.source == 'webapp' else ''})" for p in sel]
        confirm_list = None
        if apt:
            rc, out, err = run(["apt-get", "-s", "remove", *apt], timeout=60)
            sim = safety.parse_apt_sim_removed(out)
            ok, reason, extra = safety.check_apt_simulation(apt, sim)
            if not ok:
                Adw.AlertDialog(heading=_("Nie można odinstalować"),
                                body=_("Usunięcie pociągnęłoby chronione pakiety: ") + ", ".join(extra)).present(self.win)
                return
            if extra:
                lines.append(_("apt usunie też zależne pakiety: ") + ", ".join(extra))
                confirm_list = ",".join(sorted(set(sim)))
            else:
                lines.append(_("Symulacja apt: żaden inny pakiet nie zostanie usunięty."))
        if webs:
            lines.append(_("Webappy: znika skrót z menu i ikona; dane strony zostają w przeglądarce."))
        lines.append(_("Twoje pliki i ustawienia w katalogu domowym zostają."))
        note = preview_note()
        if note:
            lines.append(note)
        steps = []
        if apt:
            args = list(apt) + ([f"--confirm={confirm_list}"] if confirm_list else [])
            steps.append(helper_step("apt: " + ", ".join(apt), "apt-remove", *args))
        if snaps:
            steps.append(helper_step("snap: " + ", ".join(snaps), "snap-remove", *snaps))
        sys_flat = [p.ident for p in flats if "user" not in p.origin]
        usr_flat = [p.ident for p in flats if "user" in p.origin]
        if sys_flat:
            steps.append(helper_step("flatpak: " + ", ".join(sys_flat), "flatpak-remove", *sys_flat))
        if usr_flat:
            steps.append(("flatpak (user): " + ", ".join(usr_flat), lambda prev, ids=usr_flat:
                          (True, "PREVIEW: flatpak uninstall --user " + " ".join(ids)) if prev else
                          (run(["flatpak", "uninstall", "-y", "--noninteractive", "--user", *ids], timeout=600)[0] == 0, "")))
        for w in webs:
            steps.append((f"webapp: {w.name}", lambda prev, path=w.ident:
                          (True, "PREVIEW: " + ", ".join([path] + programs.webapp_icon_files(path))) if prev else
                          (True, "\n".join(programs.remove_webapp(path)))))
        undo = {"type": "reinstall", "apt": apt, "snap": snaps, "flatpak": [p.ident for p in flats],
                "webapp": [w.name for w in webs]}
        confirm(self.win, _("Odinstalować zaznaczone programy?") + f" ({len(sel)})", lines, _("Odinstaluj"),
                lambda b: Operator(self.win).run(_("Odinstalowanie"), steps, "uninstall",
                                                 _("Odinstalowano") + ": " + ", ".join(p.name for p in sel[:6]),
                                                 undo=undo, backup=b, after=self.refresh),
                backup_offer=backup_offer("backup_before_uninstall") if (apt or snaps or flats) else None,
                destructive=True)


# ====================================================================== Linux Backup TimeVault
class TimeVaultPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        same = chip(_("ten sam autor · JGu · seria JGu Linux Apps"))
        same.set_halign(Gtk.Align.START)
        if timevault.installed():
            st = timevault.status()
            hdr = header("Linux Backup TimeVault", _("Kopie zapasowe całego systemu"),
                         button(_("Otwórz TimeVault"), timevault.open_app, icon="external-link-symbolic"))
            self.box.append(hdr)
            self.box.append(same)
            age = timevault.last_backup_age_days(st)
            c = card()
            row = Gtk.Box(spacing=24)
            ok = age is not None and age <= 7
            row.append(Ring(1.0 if ok else 0.3, "✓" if ok else "!", (f"{age:.0f} {_('dni temu')}" if age is not None and age >= 1 else _("dziś") if ok else _("brak")), 120))
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER, hexpand=True)
            col.append(label(_("System jest zabezpieczony") if ok else _("Brak świeżej kopii systemu"), "title-3"))
            last = st.get("last_success", "")
            col.append(label(_("Ostatnia kopia: ") + (last.replace("T", " ")[:16] if last else "—") +
                             f" · {len(st.get('snapshots', []))} {_('kopii')} · " +
                             (_("dysk TimeVault podłączony") if timevault.disk_connected(st) else _("dysk TimeVault odłączony")),
                             "dim-label"))
            btns = Gtk.Box(spacing=10)
            bk = button(_("Utwórz kopię teraz"), self.backup_now, primary=True)
            if not timevault.disk_connected():
                bk.set_sensitive(False)
                bk.set_tooltip_text(_("Podłącz dysk TimeVault"))
            btns.append(bk)
            btns.append(button(_("Przywróć system…"), self.restore_info))
            col.append(btns)
            row.append(col)
            c.append(row)
            self.box.append(c)
            prefs = Adw.PreferencesGroup(title=_("Kopia przed zmianami w tej aplikacji"))
            s = settings.load()
            for key, title in (("backup_before_uninstall", _("Kopia przed odinstalowaniem programów")),
                               ("backup_before_kernels", _("Kopia przed usunięciem starych jąder")),
                               ("backup_before_update", _("Kopia przed aktualizacją systemu")),
                               ("backup_before_firmware", _("Kopia przed aktualizacją firmware"))):
                sw = Adw.SwitchRow(title=title, active=bool(s.get(key)))
                sw.connect("notify::active", lambda r, _p, k=key: settings.save(**{k: r.get_active()}))
                prefs.add(sw)
            self.box.append(prefs)
        else:
            self.box.append(header("Linux Backup TimeVault", _("Nie jest jeszcze zainstalowany")))
            self.box.append(same)
            c = card()
            c.append(label("<b>Linux Backup TimeVault — " + _("zabezpiecz system przed zmianami") + "</b>", markup=True))
            c.append(label(_("Darmowa aplikacja tego samego autora (Created by: JGu · Supported by Claude), z tej samej serii "
                             "co System Care Check. Robi kopie całego systemu na dysk zewnętrzny, jak Time Machine na Macu; "
                             "z nim ta aplikacja zrobi kopię przed każdą większą zmianą."), "dim-label"))
            btns = Gtk.Box(spacing=10)
            btns.append(button(_("Pobierz i zainstaluj TimeVault"), self.install, primary=True, icon="folder-download-symbolic"))
            btns.append(button(_("Strona projektu"), lambda: Gtk.UriLauncher.new(timevault.PAGE).launch(self.win, None, None, None)))
            c.append(btns)
            self.box.append(c)
            steps = card(spacing=4)
            steps.append(label(_("CO SIĘ STANIE PO KLIKNIĘCIU"), "lscc-kicker"))
            for t in (_("1. Pobranie najnowszej wersji z GitHub Releases (github.com/jgu-linux-apps)"),
                      _("2. Sprawdzenie paczki: nazwa, wersja i autor muszą się zgadzać"),
                      _("3. Instalacja przez apt (hasło administratora); apt doinstaluje zależności"),
                      _("4. Gotowe: TimeVault pojawi się w menu aplikacji")):
                steps.append(label(t))
            self.box.append(steps)

    def backup_now(self):
        ok, err = timevault.start_backup()
        if ok:
            history.add("timevault", _("Uruchomiono kopię w Linux Backup TimeVault"))
            toast = Adw.Toast(title=_("TimeVault robi kopię systemu w tle"))
        else:
            toast = Adw.Toast(title="TimeVault: " + err)
        self.win.toast(toast)

    def restore_info(self):
        d = Adw.AlertDialog(heading=_("Przywracanie systemu"),
                            body=_("Cały system przywraca Linux Backup TimeVault z systemu Recovery na swoim dysku: "
                                   "uruchom komputer z dysku TimeVault i wybierz kopię. Pojedyncze pliki odzyskasz "
                                   "w TimeVault przyciskiem „Przeglądaj kopie”."))
        d.add_response("close", _("Zamknij"))
        d.add_response("open", _("Otwórz TimeVault"))
        d.connect("response", lambda _d, r: r == "open" and timevault.open_app())
        d.present(self.win)

    def install(self):
        prev = settings.load()["preview"]

        def steps_work(dlg):
            dlg.set_status(_("Szukam najnowszej wersji…"))
            tag, name, url, size = timevault.latest_release()
            dlg.log(f"{tag}: {name} ({human(size)})\n{url}")
            dlg.set_status(_("Pobieranie…"))
            path = timevault.download(url, name)
            ok, reason = timevault.verify_deb(path, tag)
            dlg.log(("✓ " if ok else "✗ ") + _("Sprawdzenie paczki") + (": " + reason if reason else ""))
            if not ok:
                return False, reason
            ok, out = helperclient.run("install-timevault", path, preview=prev)
            dlg.log(out)
            return ok, ""
        dlg = ProgressDialog(self.win, "Linux Backup TimeVault")

        def done(res, err):
            ok, msg = res if res else (False, str(err))
            dlg.finish(ok, (_("Tryb podglądu — pobrano i sprawdzono, bez instalacji") if prev else _("Zainstalowano"))
                       if ok else msg)
            history.add("timevault", _("Instalacja Linux Backup TimeVault"), ok=ok, preview=prev)
            self.refresh()
        in_background(lambda: steps_work(dlg), done)


# ====================================================================== History
class HistoryPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        self.box.append(header(_("Historia i przywracanie"), _("Każda zmiana jest zapisana · dziennik: ") + history.LOG.replace(os.path.expanduser("~"), "~")))
        if timevault.installed():
            st = timevault.status()
            c = card(spacing=4)
            c.append(label("<b>Linux Backup TimeVault · " + (_("połączono") if timevault.disk_connected(st) else _("dysk odłączony")) +
                           "</b>", markup=True))
            c.append(label(_("Pełne przywrócenie systemu: system Recovery na dysku TimeVault."), "dim-label"))
            b = button(_("Otwórz TimeVault"), lambda: self.win.show_page("timevault"))
            b.set_halign(Gtk.Align.START)
            c.append(b)
            self.box.append(c)
        lst = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        lst.add_css_class("boxed-list")
        ents = history.entries()
        if not ents:
            lst.append(Adw.ActionRow(title=_("Brak zapisanych zmian")))
        for e in ents:
            sub = time.strftime("%d.%m.%Y %H:%M", time.localtime(e.get("ts", 0)))
            if e.get("backup"):
                sub += f" · {_('przed zmianą: kopia TimeVault')} {e['backup']}"
            if e.get("preview"):
                sub += " · " + _("tryb podglądu (bez zmian)")
            r = Adw.ActionRow(title=("✓ " if e.get("ok") else "✗ ") + GLib.markup_escape_text(e.get("title", "")),
                              subtitle=GLib.markup_escape_text(sub))
            u = e.get("undo") or {}
            if u.get("type") == "reinstall" and not e.get("preview") and (u.get("apt") or u.get("snap") or u.get("flatpak")):
                cmd = []
                if u.get("apt"):
                    cmd.append("sudo apt install " + " ".join(u["apt"]))
                if u.get("snap"):
                    cmd.append("sudo snap install " + " ".join(u["snap"]))
                if u.get("flatpak"):
                    cmd.append("flatpak install " + " ".join(u["flatpak"]))
                b = Gtk.Button(label=_("Jak cofnąć"), valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda *_a, c="\n".join(cmd): self._undo_info(c))
                r.add_suffix(b)
            elif u.get("type") == "autostart" and not e.get("preview"):
                b = Gtk.Button(label=_("Cofnij"), valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda *_a, uu=u: self._undo_autostart(uu))
                r.add_suffix(b)
            elif u.get("type") == "battery-reset" and not e.get("preview") and e.get("ok"):
                b = Gtk.Button(label=_("Cofnij"), valign=Gtk.Align.CENTER, tooltip_text=_("Przywróć pełne ładowanie"))
                b.connect("clicked", lambda *_a: Operator(self.win).run(
                    _("Bateria"), [helper_step(_("Pełne ładowanie (bez limitu)"), "battery-reset")], "battery",
                    _("Bateria: pełne ładowanie"), after=self.refresh))
                r.add_suffix(b)
            if e.get("detail") == "auto":
                r.add_suffix(chip(_("auto")))
            lst.append(r)
        self.box.append(lst)

    def _undo_autostart(self, u):
        from .. import autostart
        from ..i18n import LANG
        ent = next((x for x in autostart.entries(LANG) if x["file"] == u.get("file")), None)
        if ent is None:
            self.win.toast(Adw.Toast(title=_("Tego wpisu już nie ma")))
            return
        autostart.set_enabled(ent, bool(u.get("enabled")))
        history.add("autostart", _("Cofnięto zmianę autostartu") + f": {ent['name']}")
        self.win.refresh_page("autostart")
        self.refresh()

    def _undo_info(self, cmd):
        d = Adw.AlertDialog(heading=_("Jak cofnąć"), body=_("Zainstaluj ponownie poleceniem:") + "\n\n" + cmd)
        d.add_response("close", _("Zamknij"))
        d.present(self.win)
