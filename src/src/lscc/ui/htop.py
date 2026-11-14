"""htop-style console view for the Monitor page: per-core meters, memory/swap bars, tasks/load/uptime/network
and a sortable process table (F3 search, F6 sort, F9 end process). Always drawn in the Ubuntu terminal colours
(aubergine #300A24) with a monospace font, whatever the app theme. All text is Gtk.Label markup."""
import os
import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import history, settings  # noqa: E402
from ..i18n import _  # noqa: E402
from ..procs import Sampler, fmt_time, human_rate  # noqa: E402
from ..sysrun import human  # noqa: E402

GREEN, BLUE, YELLOW, RED, CYAN, GREY = "#8ae234", "#729fcf", "#fce94f", "#ef2929", "#34e2e2", "#a89ba5"
BAR = 18
ROWS = 60
SORTS = [("cpu", "CPU%"), ("mem", "MEM%"), ("pid", "PID"), ("time", "TIME+")]

CSS = """
.lscc-htop { background: #300a24; color: #ffffff; padding: 12px 14px; border-radius: 0; }
.lscc-htop label, .lscc-htop entry, .lscc-htop button { font-family: "Ubuntu Sans Mono", "DejaVu Sans Mono", monospace; font-size: 13px; }
.lscc-htop .hdr { background: #ffffff; color: #300a24; font-weight: bold; padding: 1px 4px; }
.lscc-htop label, .lscc-htop list > row { color: #ffffff; }
.lscc-htop list { background: transparent; color: #ffffff; }
.lscc-htop list > row { padding: 0 4px; min-height: 0; border-radius: 0; }
.lscc-htop list > row:selected { background: #34e2e2; color: #300a24; }
.lscc-htop list > row:selected label { color: #300a24; }
.lscc-htop button { background: transparent; color: #ffffff; box-shadow: none; border-radius: 0; padding: 0 6px; min-height: 22px; }
.lscc-htop button:checked, .lscc-htop .fkey { background: #34e2e2; color: #300a24; }
.lscc-htop button:checked label, .lscc-htop .fkey label { color: #300a24; }
.lscc-htop entry { background: #4a1a3d; color: #ffffff; border-radius: 0; min-height: 24px; }
"""
_css_done = False


def _install_css():
    global _css_done
    if not _css_done:
        p = Gtk.CssProvider()
        p.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 3)
        _css_done = True


def esc(s):
    return GLib.markup_escape_text(str(s))


def meter(name, parts, text):
    """htop meter: name[|||||     text]; parts = [(fraction, colour)]."""
    cells = []
    used = 0
    for frac, col in parts:
        n = max(0, min(BAR - used, round(frac * BAR)))
        if n:
            cells.append(f"<span foreground='{col}'>{'|' * n}</span>")
        used += n
    pad = BAR - used - len(text)
    bar = "".join(cells) + " " * max(0, pad) + f"<span foreground='{GREY}'>{esc(text)}</span>"
    return f"<span foreground='{CYAN}'>{esc(name.rjust(4))}</span><b>[</b>{bar}<b>]</b>"


def uptime_str(s):
    d, s = divmod(int(s), 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return (f"{d} {'dzień' if d == 1 else 'dni'}, " if d else "") + f"{h:02d}:{m:02d}:{s:02d}"


class HtopView(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        _install_css()
        self.add_css_class("lscc-htop")
        self.win = win
        self.sampler = Sampler()
        self.sort = "cpu"
        self.mine_only = False
        self.selected_pid = None
        self.data = None

        top = Gtk.Box(spacing=18)
        self.cores_l = Gtk.Label(xalign=0, valign=Gtk.Align.START)
        self.cores_r = Gtk.Label(xalign=0, valign=Gtk.Align.START)
        self.info = Gtk.Label(xalign=0, valign=Gtk.Align.START, ellipsize=3, hexpand=True, width_chars=10)
        top.append(self.cores_l)
        top.append(self.cores_r)
        top.append(self.info)
        self.append(top)

        tools = Gtk.Box(spacing=4)
        self.search = Gtk.SearchEntry(placeholder_text=_("F3 szukaj…"), width_request=150)
        self.search.connect("search-changed", lambda *_: self._render())
        tools.append(self.search)
        tools.append(Gtk.Label(label="  " + _("sortuj:")))
        group = None
        for key, name in SORTS:
            b = Gtk.ToggleButton(label=name, active=key == self.sort)
            if group:
                b.set_group(group)
            else:
                group = b
            b.connect("toggled", lambda bt, k=key: bt.get_active() and self._set_sort(k))
            tools.append(b)
        self.sort_buttons = group
        mine = Gtk.ToggleButton(label=_("tylko moje"))
        mine.connect("toggled", lambda b: (setattr(self, "mine_only", b.get_active()), self._render()))
        tools.append(mine)
        self.append(tools)

        self.head = Gtk.Label(xalign=0, ellipsize=3, width_chars=10)
        self.head.add_css_class("hdr")
        self.append(self.head)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.connect("row-selected", self._row_selected)
        self.append(self.list)

        keys = Gtk.Box(spacing=0)
        for k, text, cb in (("F3", _("Szukaj"), lambda: self.search.grab_focus()),
                            ("F6", _("Sortuj"), self._next_sort),
                            ("F9", _("Zakończ"), self._kill)):
            b = Gtk.Button()
            b.set_child(Gtk.Label(use_markup=True, label=f"<b>{k}</b>"))
            b.add_css_class("fkey")
            b.connect("clicked", lambda *_a, c=cb: c())
            keys.append(b)
            lb = Gtk.Button(label=text + " ")
            lb.connect("clicked", lambda *_a, c=cb: c())
            keys.append(lb)
        self.append(keys)

        ctl = Gtk.EventControllerKey()
        ctl.connect("key-pressed", self._key)
        self.add_controller(ctl)

    # ------------------------------------------------------------------ data
    def tick(self):
        try:
            self.data = self.sampler.sample()
        except OSError:
            return
        self._meters()
        self._render()

    def _meters(self):
        d = self.data
        cores = d["cores"]
        lines = []
        for i, c in enumerate(cores):
            v = c or 0.0
            lines.append(meter(str(i), [(v / 100, GREEN)], f"{v:.1f}%"))
        half = (len(lines) + 1) // 2
        mt, mu, mc = d["mem_total"], d["mem_used"], d["mem_cache"]
        mem = meter("Mem", [(mu / mt, GREEN), (min(mc, mt - mu) / mt, YELLOW)], f"{human(mu)}/{human(mt)}")
        swp = meter("Swp", [(d["swap_used"] / d["swap_total"] if d["swap_total"] else 0, RED)],
                    f"{human(d['swap_used'])}/{human(d['swap_total'])}")
        self.cores_l.set_markup("\n".join(lines[:half] + [mem]))
        self.cores_r.set_markup("\n".join(lines[half:] + [swp]))
        n_threads = d["tasks"]
        la = d["load"]
        self.info.set_markup(
            f"<span foreground='{CYAN}'>Tasks:</span> <b>{len(d['procs'])}</b>, {esc(n_threads)} thr; <b>{d['running']}</b> running\n"
            f"<span foreground='{CYAN}'>Load average:</span> <b>{la[0]:.2f}</b> {la[1]:.2f} {la[2]:.2f}\n"
            f"<span foreground='{CYAN}'>Uptime:</span> <b>{esc(uptime_str(d['uptime']))}</b>\n"
            f"<span foreground='{CYAN}'>Net:</span> <span foreground='{GREEN}'>↓ {esc(human_rate(d['rx']))}</span>"
            f"  <span foreground='{RED}'>↑ {esc(human_rate(d['tx']))}</span>\n"
            f"<span foreground='{CYAN}'>CPU:</span> <b>{(d['cpu'] or 0):.1f}%</b> · {len(cores)} " + _("wątków"))

    def _set_sort(self, key):
        self.sort = key
        self._render()

    def _next_sort(self):
        keys = [k for k, _n in SORTS]
        nxt = keys[(keys.index(self.sort) + 1) % len(keys)]
        b = self.sort_buttons
        i = 0
        # activate the matching toggle (they are siblings in the tools box)
        w = b
        while w is not None and i < len(keys):
            if isinstance(w, Gtk.ToggleButton) and w.get_label() == dict(SORTS)[nxt]:
                w.set_active(True)
                break
            w = w.get_next_sibling()
            i += 1

    def _render(self):
        if not self.data:
            return
        procs = self.data["procs"]
        q = self.search.get_text().strip().lower()
        if q:
            procs = [p for p in procs if q in p["cmd"].lower() or q in p["user"].lower() or q == str(p["pid"])]
        if self.mine_only:
            procs = [p for p in procs if p["uid"] == os.getuid()]
        key = {"cpu": lambda p: (-p["cpu"], -p["mem"]), "mem": lambda p: (-p["mem"], -p["cpu"]),
               "pid": lambda p: p["pid"], "time": lambda p: -p["time"]}[self.sort]
        procs = sorted(procs, key=key)[:ROWS]
        cols = {"cpu": "CPU%", "mem": "MEM%", "pid": "PID", "time": "TIME+"}
        hdr = (f"{'PID':>7} {'USER':<9} S {'CPU%':>5} {'MEM%':>5} {'RES':>8} {'TIME+':>10}  COMMAND")
        sel = cols[self.sort]
        self.head.set_markup(esc(hdr).replace(sel, f"<u>{sel}</u>", 1))
        keep = self.selected_pid
        while (r := self.list.get_first_child()) is not None:
            self.list.remove(r)
        for p in procs:
            mine = p["uid"] == os.getuid()
            cpu_col = RED if p["cpu"] >= 50 else YELLOW if p["cpu"] >= 10 else "#ffffff"
            cmd = p["cmd"]
            line = (f"{p['pid']:>7} <span foreground='{GREY if not mine else '#ffffff'}'>{esc(p['user'][:9]):<9}</span> "
                    f"{esc(p['state'])} <span foreground='{cpu_col}'>{p['cpu']:>5.1f}</span> {p['mem']:>5.1f} "
                    f"{esc(human(p['rss'])):>8} {esc(fmt_time(p['time'])):>10}  "
                    f"<span foreground='{GREEN if p['comm'] and cmd.split(' ')[0].endswith(p['comm']) else '#ffffff'}'>"
                    f"{esc(cmd)}</span>")
            lb = Gtk.Label(xalign=0, ellipsize=3, use_markup=True, label=line, width_chars=10)
            row = Gtk.ListBoxRow(child=lb)
            row.proc = p
            self.list.append(row)
            if p["pid"] == keep:
                self.list.select_row(row)

    def _row_selected(self, _lb, row):
        if row is not None:
            self.selected_pid = row.proc["pid"]

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_F3:
            self.search.grab_focus()
        elif keyval == Gdk.KEY_F6:
            self._next_sort()
        elif keyval == Gdk.KEY_F9:
            self._kill()
        else:
            return False
        return True

    # ------------------------------------------------------------------ F9
    def _kill(self):
        row = self.list.get_selected_row()
        if row is None:
            self.win.toast(Adw.Toast(title=_("Zaznacz proces na liście")))
            return
        p = row.proc
        if p["uid"] != os.getuid():
            self.win.toast(Adw.Toast(title=_("To proces innego użytkownika lub systemu — aplikacja go nie zamyka")))
            return
        if p["pid"] == os.getpid():
            return
        from .common import confirm
        prev = settings.load()["preview"]
        lines = [f"PID {p['pid']} · {p['cmd'][:120]}", _("Wysyłany jest sygnał SIGTERM — program może się normalnie zamknąć "
                                                         "i zapisać dane.")]
        if prev:
            lines.append(_("Tryb podglądu: aplikacja pokaże polecenie, ale niczego nie zmieni."))

        def go(_b):
            if prev:
                self.win.toast(Adw.Toast(title=f"PREVIEW: kill -TERM {p['pid']}"))
                return
            try:
                os.kill(p["pid"], signal.SIGTERM)
                ok = True
            except OSError as e:
                ok = False
                self.win.toast(Adw.Toast(title=str(e)))
            history.add("process", _("Zakończono proces") + f": {p['comm']} ({p['pid']})", ok=ok)
        confirm(self.win, _("Zakończyć proces?") + f" {p['comm']}", lines, _("Zakończ"), go, destructive=True)
