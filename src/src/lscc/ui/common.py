"""Shared UI pieces: progress ring, cards, a background runner and the confirm / progress dialogs."""
import math
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ..i18n import _  # noqa: E402


def label(text, cls=None, wrap=True, xalign=0.0, markup=False):
    lb = Gtk.Label(xalign=xalign, wrap=wrap)
    if markup:
        lb.set_markup(text)
    else:
        lb.set_text(text)
    if cls:
        for c in cls.split():
            lb.add_css_class(c)
    return lb


def card(child=None, spacing=8):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    b.add_css_class("card")
    b.add_css_class("lscc-card")
    if child:
        b.append(child)
    return b


def chip(text, kind=""):
    lb = label(text, "lscc-chip " + kind, wrap=False)
    lb.set_valign(Gtk.Align.CENTER)
    return lb


def page_box():
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    for side in ("start", "end", "top", "bottom"):
        getattr(b, f"set_margin_{side}")(24)
    return b


def scrolled(child):
    sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
    sw.set_child(child)
    return sw


def clear(box):
    while (c := box.get_first_child()) is not None:
        box.remove(c)


class _RingArea(Gtk.DrawingArea):
    """Only the circle. Text is NOT drawn here: drawing a widget's shared Pango layout with PangoCairo (and a
    span alpha) corrupted the glyph cache of every other label on screen (letters at 65 % / without
    antialiasing on NVIDIA). The numbers are ordinary Gtk.Labels on top (see Ring)."""

    def __init__(self, frac, size):
        super().__init__()
        self.frac, self.size = frac, size
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self._draw)

    def _draw(self, area, cr, w, h):
        fg = self.get_color()
        ok, acc = self.get_style_context().lookup_color("accent_bg_color")
        lw = self.size * 0.08
        r = self.size / 2 - lw / 2 - 1
        cr.set_line_width(lw)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.12)
        cr.arc(w / 2, h / 2, r, 0, 2 * math.pi)
        cr.stroke()
        if self.frac > 0:
            if ok:
                cr.set_source_rgba(acc.red, acc.green, acc.blue, 1)
            cr.set_line_cap(1)
            cr.arc(w / 2, h / 2, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * self.frac)
            cr.stroke()


class Ring(Gtk.Overlay):
    def __init__(self, frac, big, small="", size=120):
        super().__init__(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.set_child(_RingArea(max(0.0, min(1.0, frac)), size))
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        b = Gtk.Label(label=str(big))
        b.add_css_class("lscc-ring-big")
        b.set_markup(f"<span size='{int(size * 0.19) * 1024}' weight='bold'>{GLib.markup_escape_text(str(big))}</span>")
        col.append(b)
        if small:
            sl = Gtk.Label(label=small, justify=Gtk.Justification.CENTER, max_width_chars=12, wrap=True)
            sl.add_css_class("lscc-ring-small")
            sl.set_markup(f"<span size='{max(7, int(size * 0.075)) * 1024}'>{GLib.markup_escape_text(small)}</span>")
            col.append(sl)
        self.add_overlay(col)


class Chart(Gtk.DrawingArea):
    """Line chart / sparkline. Draws only shapes — never text (labels go in Gtk.Labels around it).

    series: [(values, kind)] where kind is "accent", "accent2" (second colour) or "warn"; values may contain None.
    lo/hi: fixed range (e.g. 0..100 for %), None = from the data. grid: number of horizontal guide lines."""

    def __init__(self, height=90, lo=None, hi=None, grid=3, fill=True, width=-1):
        super().__init__(hexpand=width < 0)
        self.series, self.lo, self.hi, self.grid, self.fill = [], lo, hi, grid, fill
        self.set_content_height(height)
        if width > 0:
            self.set_content_width(width)
        self.set_draw_func(self._draw)

    def set_series(self, series):
        self.series = series
        self.queue_draw()

    def _color(self, kind):
        ctx = self.get_style_context()
        ok, acc = ctx.lookup_color("accent_bg_color")
        if kind == "warn":
            okw, wc = ctx.lookup_color("lscc_warn")
            return (wc.red, wc.green, wc.blue) if okw else (0.96, 0.62, 0.04)
        if kind == "accent2":
            ok2, a2 = ctx.lookup_color("lscc_accent2")
            if ok2:
                return (a2.red, a2.green, a2.blue)
            fg = self.get_color()
            return (fg.red, fg.green, fg.blue)
        return (acc.red, acc.green, acc.blue) if ok else (0.3, 0.5, 0.9)

    def _draw(self, area, cr, w, h):
        fg = self.get_color()
        pad = 3
        cr.set_line_width(1)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.08)
        for i in range(self.grid + 1):
            y = pad + (h - 2 * pad) * i / max(1, self.grid)
            cr.move_to(0, round(y) + 0.5)
            cr.line_to(w, round(y) + 0.5)
        cr.stroke()
        vals = [v for ser, _k in self.series for v in ser if v is not None]
        if not vals:
            return
        lo = self.lo if self.lo is not None else min(vals)
        hi = self.hi if self.hi is not None else max(vals)
        if hi - lo < 1e-9:
            hi, lo = hi + 1, lo - 1
        for ser, kind in self.series:
            n = len(ser)
            if n < 2:
                continue
            pts = [(w * i / (n - 1), pad + (h - 2 * pad) * (1 - (v - lo) / (hi - lo)))
                   for i, v in enumerate(ser) if v is not None]
            if len(pts) < 2:
                continue
            r, g, b = self._color(kind)
            if self.fill:
                cr.move_to(pts[0][0], h)
                for x, y in pts:
                    cr.line_to(x, y)
                cr.line_to(pts[-1][0], h)
                cr.close_path()
                cr.set_source_rgba(r, g, b, 0.14)
                cr.fill()
            cr.set_line_width(2)
            cr.set_line_join(1)
            cr.set_line_cap(1)
            cr.move_to(*pts[0])
            for x, y in pts[1:]:
                cr.line_to(x, y)
            cr.set_source_rgba(r, g, b, 1)
            cr.stroke()
            cr.arc(pts[-1][0] - 2, pts[-1][1], 3, 0, 2 * math.pi)
            cr.fill()


def in_background(work, done):
    """Run work() in a thread, then done(result, error) on the GTK main loop."""
    def t():
        try:
            res, err = work(), None
        except Exception as e:  # noqa: BLE001
            res, err = None, e
        GLib.idle_add(lambda: (done(res, err), False)[1])
    threading.Thread(target=t, daemon=True).start()


def confirm(parent, heading, lines, ok_label, on_ok, backup_offer=None, destructive=False):
    """Confirmation before any change: the full list of what will happen + optional TimeVault backup.
    backup_offer: None, or (available: bool, note: str, default_on: bool)."""
    d = Adw.AlertDialog(heading=heading)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    body = label("\n".join("•  " + ln for ln in lines[:30]) + (f"\n… (+{len(lines) - 30})" if len(lines) > 30 else ""))
    body.set_selectable(True)
    box.append(body)
    chk = None
    if backup_offer is not None:
        available, note, on = backup_offer
        chk = Gtk.CheckButton(label=_("Najpierw zrób kopię systemu w Linux Backup TimeVault"), active=available and on)
        chk.set_sensitive(available)
        box.append(chk)
        if note:
            box.append(label(note, "dim-label caption"))
    d.set_extra_child(box)
    d.add_response("cancel", _("Anuluj"))
    d.add_response("ok", ok_label)
    d.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED)
    d.set_default_response("cancel")
    d.connect("response", lambda _d, r: r == "ok" and on_ok(bool(chk and chk.get_active())))
    d.present(parent)


class ProgressDialog(Adw.Dialog):
    """Shows a running operation with its log; closes only when the work is finished."""

    def __init__(self, parent, title):
        super().__init__(title=title, content_width=640, content_height=420, can_close=False)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar(show_end_title_buttons=False))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16,
                      margin_bottom=16)
        self.status = label(_("Pracuję…"))
        self.bar = Gtk.ProgressBar()
        self.buf = Gtk.TextBuffer()
        view = Gtk.TextView(buffer=self.buf, editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.add_css_class("lscc-log")
        self.close_btn = Gtk.Button(label=_("Zamknij"), sensitive=False, halign=Gtk.Align.END)
        self.close_btn.add_css_class("suggested-action")
        self.close_btn.connect("clicked", lambda *_: self.force_close())
        box.append(self.status)
        box.append(self.bar)
        box.append(scrolled(view))
        box.append(self.close_btn)
        tv.set_content(box)
        self.set_child(tv)
        self._pulse = GLib.timeout_add(120, lambda: (self.bar.pulse(), True)[1])
        self.present(parent)

    def log(self, text):
        GLib.idle_add(lambda: (self.buf.insert(self.buf.get_end_iter(), text.rstrip() + "\n"), False)[1])

    def set_status(self, text):
        GLib.idle_add(lambda: (self.status.set_text(text), False)[1])

    def finish(self, ok, text):
        def f():
            if self._pulse:
                GLib.source_remove(self._pulse)
                self._pulse = 0
            self.bar.set_fraction(1.0)
            self.status.set_markup(("<b>✓ " if ok else "<b>✗ ") + GLib.markup_escape_text(text) + "</b>")
            self.close_btn.set_sensitive(True)
            self.set_can_close(True)
            return False
        GLib.idle_add(f)
