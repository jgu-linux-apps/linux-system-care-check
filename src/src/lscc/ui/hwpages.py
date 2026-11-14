"""Hardware and session pages: Disk, Battery, Temperatures, Autostart."""
import os
import shutil
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import autostart, history, hw, settings  # noqa: E402
from ..i18n import LANG, _  # noqa: E402
from ..sysrun import human  # noqa: E402
from .common import Chart, Ring, card, chip, clear, in_background, label, page_box, scrolled  # noqa: E402
from .pages import Operator, button, header, helper_step, preview_note  # noqa: E402


def level(frac):
    lb = Gtk.LevelBar(min_value=0, max_value=1, value=max(0.0, min(1.0, frac)), valign=Gtk.Align.CENTER)
    lb.add_offset_value(Gtk.LEVEL_BAR_OFFSET_LOW, 0.85)
    lb.add_offset_value(Gtk.LEVEL_BAR_OFFSET_HIGH, 0.95)
    lb.add_offset_value(Gtk.LEVEL_BAR_OFFSET_FULL, 1.0)
    lb.set_size_request(-1, 10)
    return lb


def boxed():
    lst = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    lst.add_css_class("boxed-list")
    return lst


def open_folder(win, path):
    Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(win, None, None, None)


# ====================================================================== Disk
class DiskPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        btns = [button(_("Sprawdź"), self.refresh, icon="view-refresh-symbolic")]
        if shutil.which("baobab"):
            btns.append(button(_("Analizator dysku"), lambda: subprocess.Popen(["baobab"], start_new_session=True)))
        self.box.append(header(_("Dysk"), _("Miejsce na partycjach, kondycja dysków (SMART) i największe foldery"), *btns))

        lst = boxed()
        for m in hw.mounts():
            frac = m["used"] / m["total"] if m["total"] else 0
            r = Adw.ActionRow(title=GLib.markup_escape_text(m["mount"]),
                              subtitle=GLib.markup_escape_text(f"{m['device']} · {m['fs']} · {_('wolne')} {human(m['free'])}"))
            lv = level(frac)
            lv.set_size_request(180, 10)
            r.add_suffix(lv)
            r.add_suffix(label(f"{round(100 * frac)}% · {human(m['used'])} / {human(m['total'])}", "dim-label", wrap=False))
            lst.append(r)
        self.box.append(label(_("PARTYCJE"), "lscc-kicker"))
        self.box.append(lst)

        self.box.append(label(_("KONDYCJA DYSKÓW"), "lscc-kicker"))
        self.drives = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=14, row_spacing=14,
                                  max_children_per_line=3, homogeneous=True)
        self.box.append(self.drives)
        in_background(hw.drives, self._drives)

        row = Gtk.Box(spacing=10)
        row.append(label(_("NAJWIĘKSZE FOLDERY W KATALOGU DOMOWYM"), "lscc-kicker", wrap=False))
        row.append(Gtk.Box(hexpand=True))
        self.du_btn = Gtk.Button(label=_("Policz"))
        self.du_btn.connect("clicked", lambda *_: self._du())
        row.append(self.du_btn)
        self.box.append(row)
        self.du_list = boxed()
        self.du_list.append(Adw.ActionRow(title=_("Kliknij „Policz” — liczenie może potrwać do minuty")))
        self.box.append(self.du_list)

    def _drives(self, drives, err):
        if not drives:
            self.drives.append(label(_("Brak danych o dyskach (UDisks2 niedostępny)"), "dim-label"))
            return
        for d in drives:
            c = card(spacing=4)
            sm = d["smart"]
            top = Gtk.Box(spacing=8)
            top.append(Gtk.Image(icon_name="drive-harddisk-solidstate-symbolic" if d["kind"] != "hdd" else "drive-harddisk-symbolic"))
            top.append(label(f"<b>{GLib.markup_escape_text(d['model'])}</b>", markup=True, wrap=True))
            c.append(top)
            c.append(label(f"{human(d['size'])} · {d['kind'].upper()}" + (" · " + _("wymienny") if d["removable"] else ""), "dim-label caption"))
            if sm is None:
                c.append(chip(_("brak SMART")))
            else:
                ch = chip(_("Kondycja: dobra") if sm["ok"] else _("Kondycja: UWAGA"), "ok" if sm["ok"] else "sec")
                ch.set_halign(Gtk.Align.START)
                c.append(ch)
                bits = []
                if sm.get("wear") is not None:
                    bits.append(f"{_('zużycie')} {sm['wear']}%")
                if sm.get("hours"):
                    bits.append(f"{sm['hours']} h {_('pracy')}")
                if sm.get("temp"):
                    bits.append(f"{sm['temp']:.0f}°C")
                c.append(label(" · ".join(bits), "caption"))
                for w in sm.get("warnings", []):
                    c.append(label("⚠ " + str(w), "caption"))
            self.drives.append(c)

    def _du(self):
        self.du_btn.set_sensitive(False)
        clear(self.du_list)
        sp = Adw.ActionRow(title=_("Liczę…"))
        sp.add_prefix(Gtk.Spinner(spinning=True))
        self.du_list.append(sp)
        in_background(hw.biggest_folders, self._du_done)

    def _du_done(self, res, err):
        self.du_btn.set_sensitive(True)
        clear(self.du_list)
        res = res or []
        top = res[0][1] if res else 1
        home = os.path.expanduser("~")
        for path, size in res:
            r = Adw.ActionRow(title=GLib.markup_escape_text(path.replace(home, "~")))
            lv = level(size / top)
            lv.set_size_request(160, 8)
            r.add_suffix(lv)
            r.add_suffix(label(human(size), "heading", wrap=False))
            b = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text=_("Otwórz w Plikach"))
            b.add_css_class("flat")
            b.connect("clicked", lambda *_a, p=path: open_folder(self.win, p))
            r.add_suffix(b)
            self.du_list.append(r)
        self.du_list.append(Adw.ActionRow(subtitle=_("Aplikacja niczego tu nie usuwa — sprawdź foldery i zdecyduj sam.")))


# ====================================================================== Battery
TYPE_NAMES = {"Standard": "Standardowe (100%)", "Fast": "Szybkie (100%)",
              "Long_Life": "Ochrona baterii (~80%)", "Adaptive": "Adaptacyjne"}
PROFILE_NAMES = {"power-saver": "Oszczędzanie energii", "balanced": "Zrównoważony", "performance": "Wydajność"}


class BatteryPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        b = hw.battery_info()
        self.box.append(header(_("Bateria"), _("Kondycja, cykle i ochrona baterii przed zużyciem"),
                               button(_("Sprawdź"), self.refresh, icon="view-refresh-symbolic")))
        if not b:
            c = card()
            c.append(label(_("Ten komputer nie ma baterii."), "title-4"))
            self.box.append(c)
            self._profile()
            return
        c = card()
        row = Gtk.Box(spacing=26)
        row.append(Ring(min(100, b["health"] or 0) / 100, f"{min(100, b['health'])}%" if b["health"] else "—", _("kondycja"), 128))
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER, hexpand=True)
        h = b["health"] or 0
        col.append(label(_("Bateria w świetnej formie") if h >= 90 else _("Bateria w dobrej formie") if h >= 75
                         else _("Bateria jest zużyta"), "title-3"))
        st = {"Charging": _("ładowanie"), "Discharging": _("rozładowywanie"), "Full": _("naładowana"),
              "Not charging": _("nie ładuje (podłączona)")}.get(b["status"], b["status"])
        col.append(label(f"{_('Naładowanie')}: {b['capacity']}% · {st}" + (f" · {b['power_w']} W" if b["power_w"] else ""), "dim-label"))
        bits = []
        if b["full_wh"] and b["design_wh"]:
            bits.append(f"{_('pojemność')} {b['full_wh']} / {b['design_wh']} Wh {_('fabrycznie')}")
        if h > 100:
            bits.append(_("nowa bateria — trzyma nawet więcej niż fabrycznie"))
        if b["cycles"]:
            bits.append(f"{b['cycles']} {_('cykli')}")
        if b["vendor"] or b["model"]:
            bits.append(f"{b['vendor']} {b['model']}".strip())
        col.append(label(" · ".join(bits), "dim-label caption"))
        row.append(col)
        c.append(row)
        self.box.append(c)

        grp = Adw.PreferencesGroup(title=_("Ochrona baterii"),
                                   description=_("Ładowanie do ok. 80% wyraźnie wydłuża życie baterii, gdy laptop "
                                                 "pracuje głównie podłączony do prądu. Zmiana wymaga hasła administratora."))
        if b["charge_types"]:
            names = [_(TYPE_NAMES[t]) for t in b["charge_types"]]
            cr = Adw.ComboRow(title=_("Tryb ładowania"), model=Gtk.StringList.new(names),
                              selected=b["charge_types"].index(b["charge_type"]) if b["charge_type"] in b["charge_types"] else 0)
            apply = Gtk.Button(label=_("Zastosuj"), valign=Gtk.Align.CENTER)
            apply.connect("clicked", lambda *_a: self._set("types", b["charge_types"][cr.get_selected()],
                                                           _(TYPE_NAMES[b["charge_types"][cr.get_selected()]])))
            cr.add_suffix(apply)
            grp.add(cr)
        elif b["conservation"] is not None:
            sw = Adw.ActionRow(title=_("Tryb ochrony baterii (Lenovo, do ok. 80%)"),
                               subtitle=_("włączony") if b["conservation"] else _("wyłączony"))
            bt = Gtk.Button(label=_("Wyłącz") if b["conservation"] else _("Włącz"), valign=Gtk.Align.CENTER)
            bt.connect("clicked", lambda *_a: self._set("conservation", "0" if b["conservation"] else "1",
                                                        _("Tryb ochrony baterii") + ": " + (_("wyłączony") if b["conservation"] else _("włączony"))))
            sw.add_suffix(bt)
            grp.add(sw)
        elif b["limit_supported"]:
            sp = Adw.SpinRow.new_with_range(50, 100, 5)
            sp.set_title(_("Ładuj maksymalnie do (%)"))
            sp.set_value(b["limit"] or 100)
            apply = Gtk.Button(label=_("Zastosuj"), valign=Gtk.Align.CENTER)
            apply.connect("clicked", lambda *_a: self._set("threshold", str(int(sp.get_value())),
                                                           f"{_('Limit ładowania')}: {int(sp.get_value())}%"))
            sp.add_suffix(apply)
            grp.add(sp)
        else:
            grp.add(Adw.ActionRow(title=_("Ten laptop nie udostępnia limitu ładowania w Linuksie")))
        self.box.append(grp)
        self._profile()

    def _profile(self):
        cur, avail = hw.power_profile()
        if not avail:
            return
        grp = Adw.PreferencesGroup(title=_("Profil zasilania"),
                                   description=_("To samo co w szybkich ustawieniach GNOME; zmienia się od razu."))
        cr = Adw.ComboRow(title=_("Profil"), model=Gtk.StringList.new([_(PROFILE_NAMES.get(p, p)) for p in avail]),
                          selected=avail.index(cur) if cur in avail else 0)
        cr.connect("notify::selected", lambda r, _p: hw.set_power_profile(avail[r.get_selected()]))
        grp.add(cr)
        self.box.append(grp)

    def _set(self, kind, value, title):
        lines = [title]
        note = preview_note()
        if note:
            lines.append(note)
        from .common import confirm
        confirm(self.win, _("Zmienić ładowanie baterii?"), lines + [_("Ustawienie zostanie przywrócone po każdym uruchomieniu komputera.")],
                _("Zmień"), lambda _b: Operator(self.win).run(_("Bateria"), [helper_step(title, "battery-set", kind, value)],
                                                               "battery", title, undo={"type": "battery-reset"},
                                                               after=self.refresh))


# ====================================================================== Monitor (CPU, memory, temperatures)
HIST = 150          # samples kept per series (5 minutes at 2 s)


class TempsPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.timer = 0
        self.cpu_prev = hw.cpu_times()
        self.cpu_hist, self.mem_hist, self.temp_hist = [], [], {}
        self.sensor_rows = {}
        self.sensor_key = None
        self.box = page_box()
        self.append(scrolled(self.box))
        self.connect("map", lambda *_: self._start())
        self.connect("unmap", lambda *_: self._stop())
        self.refresh()

    def _start(self):
        if not self.timer:
            self.timer = GLib.timeout_add_seconds(2, self._tick)

    def _stop(self):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0

    @staticmethod
    def _push(hist, v):
        hist.append(v)
        del hist[:-HIST]

    def _stat_card(self, kicker):
        c = card(spacing=4)
        top = Gtk.Box(spacing=8)
        top.append(label(kicker, "lscc-kicker", wrap=False))
        top.append(Gtk.Box(hexpand=True))
        big = label("—", "lscc-stat", wrap=False)
        c.append(top)
        c.append(big)
        ch = Chart(height=96, lo=0, hi=100)
        c.append(ch)
        cap = label("", "dim-label caption")
        c.append(cap)
        return c, big, ch, cap

    def refresh(self):
        clear(self.box)
        view = settings.load().get("monitor_view", "charts")
        sw = Gtk.Box(spacing=0)
        sw.add_css_class("linked")
        b1 = Gtk.ToggleButton(label=_("Wykresy"), active=view == "charts")
        b2 = Gtk.ToggleButton(label="htop", active=view == "htop", group=b1)
        b1.connect("toggled", lambda b: b.get_active() and self._view("charts"))
        b2.connect("toggled", lambda b: b.get_active() and self._view("htop"))
        sw.append(b1)
        sw.append(b2)
        self.box.append(header(_("Monitor"), _("Procesor, pamięć, procesy i czujniki na żywo · odświeżane co 2 s"), sw))
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE, vhomogeneous=False)
        charts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        from .htop import HtopView
        self.htop = HtopView(self.win)
        self.stack.add_named(charts, "charts")
        self.stack.add_named(self.htop, "htop")
        self.box.append(self.stack)
        grid = Gtk.Grid(column_spacing=14, row_spacing=14, column_homogeneous=True)
        c1, self.cpu_big, self.cpu_chart, self.cpu_cap = self._stat_card(_("PROCESOR"))
        c2, self.mem_big, self.mem_chart, self.mem_cap = self._stat_card(_("PAMIĘĆ RAM"))
        grid.attach(c1, 0, 0, 1, 1)
        grid.attach(c2, 1, 0, 1, 1)
        charts.append(grid)
        charts.append(label(_("CZUJNIKI"), "lscc-kicker"))
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=14, row_spacing=14,
                                max_children_per_line=3, homogeneous=True)
        charts.append(self.flow)
        self.sensor_key = None
        self.stack.set_visible_child_name(view)
        self._tick()

    def _view(self, name):
        settings.save(monitor_view=name)
        self.stack.set_visible_child_name(name)
        self._tick()

    def _build_sensors(self, data):
        self.flow.remove_all()
        self.sensor_rows = {}
        if not data:
            self.flow.append(label(_("Brak czujników"), "dim-label"))
        for s in data:
            c = card(spacing=6)
            c.append(label(_(s["title"]).upper(), "lscc-kicker"))
            for lbl, *_rest in s["temps"]:
                key = (s["path"], lbl)
                r = Gtk.Box(spacing=8)
                r.append(label(lbl, wrap=False))
                r.append(Gtk.Box(hexpand=True))
                ch = chip("—")
                r.append(ch)
                c.append(r)
                spark = Chart(height=34, grid=1, lo=None, hi=None)
                c.append(spark)
                self.sensor_rows[key] = (ch, spark)
            for lbl, _rpm in s["fans"]:
                key = (s["path"], "fan:" + lbl)
                r = Gtk.Box(spacing=8)
                r.append(label(lbl, wrap=False))
                r.append(Gtk.Box(hexpand=True))
                ch = chip("—")
                r.append(ch)
                c.append(r)
                spark = Chart(height=34, grid=1)
                c.append(spark)
                self.sensor_rows[key] = (ch, spark)
            self.flow.append(c)

    def _tick(self):
        if self.stack.get_visible_child_name() == "htop":
            self.htop.tick()
            return True
        cur = hw.cpu_times()
        pct = hw.cpu_percent(self.cpu_prev, cur)
        self.cpu_prev = cur
        if pct is not None:
            self._push(self.cpu_hist, pct)
            self.cpu_big.set_text(f"{pct:.0f}%")
        la = hw.loadavg()
        self.cpu_cap.set_text(f"{_('obciążenie')}: {la[0]:.2f} · {la[1]:.2f} · {la[2]:.2f} · {os.cpu_count()} {_('wątków')}" if la else "")
        self.cpu_chart.set_series([(self.cpu_hist, "accent")])
        m = hw.memory()
        if m:
            used, total, su, st = m
            self._push(self.mem_hist, 100 * used / total)
            self.mem_big.set_text(f"{human(used)} / {human(total)}")
            self.mem_cap.set_text(f"{100 * used / total:.0f}% · swap {human(su)} / {human(st)}")
            self.mem_chart.set_series([(self.mem_hist, "accent2")])
        data = hw.sensors()
        key = tuple((s["path"], s["title"], tuple(t[0] for t in s["temps"]), tuple(f[0] for f in s["fans"])) for s in data)
        if key != self.sensor_key:
            self.sensor_key = key
            self._build_sensors(data)
        for s in data:
            for lbl, v, hi, cr in s["temps"]:
                k = (s["path"], lbl)
                h = self.temp_hist.setdefault(k, [])
                self._push(h, v)
                limit = cr or hi or 100
                kind = "sec" if v >= limit - 5 else "warn" if v >= limit - 20 else "ok"
                ch, spark = self.sensor_rows[k]
                ch.set_text(f"{v:.0f}°C")
                for cls in ("sec", "warn", "ok"):
                    ch.remove_css_class(cls)
                ch.add_css_class(kind)
                spark.set_series([(h, "warn" if kind != "ok" else "accent")])
            for lbl, rpm in s["fans"]:
                k = (s["path"], "fan:" + lbl)
                h = self.temp_hist.setdefault(k, [])
                self._push(h, rpm)
                ch, spark = self.sensor_rows[k]
                ch.set_text(f"{rpm} RPM")
                spark.set_series([(h, "accent2")])
        return True


# ====================================================================== Autostart
class AutostartPage(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.box = page_box()
        self.append(scrolled(self.box))
        self.refresh()

    def refresh(self):
        clear(self.box)
        ents = autostart.entries(LANG)
        apps = [e for e in ents if not e["internal"]]
        internal = [e for e in ents if e["internal"]]
        self.box.append(header(_("Autostart"), f"{sum(e['enabled'] for e in apps)} / {len(apps)} " +
                               _("programów uruchamia się po zalogowaniu"),
                               button(_("Sprawdź"), self.refresh, icon="view-refresh-symbolic")))
        self.box.append(label(_("Wyłączenie zapisuje tylko Twoją kopię w ~/.config/autostart — pliki systemowe "
                                "nie są zmieniane, a każdą zmianę cofniesz tym samym przełącznikiem."), "dim-label caption"))
        lst = boxed()
        for e in apps:
            lst.append(self._row(e))
        if not apps:
            lst.append(Adw.ActionRow(title=_("Brak programów w autostarcie")))
        self.box.append(lst)
        exp = Adw.ExpanderRow(title=_("Usługi systemowe i pomocnicze"),
                              subtitle=f"{len(internal)} · " + _("potrzebne do działania pulpitu — tylko podgląd"))
        for e in internal:
            r = Adw.ActionRow(title=GLib.markup_escape_text(e["name"]), subtitle=GLib.markup_escape_text(e["file"]),
                              subtitle_lines=1)
            r.add_suffix(chip(_("włączone") if e["enabled"] else _("wyłączone"), "ok" if e["enabled"] else ""))
            exp.add_row(r)
        g = boxed()
        g.append(exp)
        self.box.append(g)

    def _row(self, e):
        r = Adw.ActionRow(title=GLib.markup_escape_text(e["name"]),
                          subtitle=GLib.markup_escape_text(e["comment"] or e["exec"]), subtitle_lines=1)
        img = Gtk.Image(pixel_size=32)
        if e["icon"].startswith("/") and os.path.exists(e["icon"]):
            img.set_from_file(e["icon"])
        else:
            img.set_from_icon_name(e["icon"] or "application-x-executable")
        r.add_prefix(img)
        if e["system"]:
            r.add_suffix(chip(_("systemowy")))
        sw = Gtk.Switch(active=e["enabled"], valign=Gtk.Align.CENTER)
        sw.connect("state-set", lambda s, on, ent=e: self._toggle(s, on, ent))
        r.add_suffix(sw)
        r.set_activatable_widget(sw)
        return r

    def _toggle(self, sw, on, e):
        if settings.load()["preview"]:
            self.win.toast(Adw.Toast(title=_("Tryb podglądu: zapisałbym ~/.config/autostart/") + e["file"]))
            return True                         # keep the old state
        try:
            autostart.set_enabled(e, on)
            history.add("autostart", (_("Autostart włączony") if on else _("Autostart wyłączony")) + f": {e['name']}",
                        undo={"type": "autostart", "file": e["file"], "enabled": not on})
        except (OSError, ValueError) as ex:
            self.win.toast(Adw.Toast(title=str(ex)))
            return True
        GLib.idle_add(lambda: (self.refresh(), False)[1])
        return False
