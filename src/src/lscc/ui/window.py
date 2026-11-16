"""Main window: sidebar (overview, updates, cleanup, programs, TimeVault, history) + pages."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from .. import APP_NAME, settings  # noqa: E402
from ..i18n import _  # noqa: E402
from . import hwpages, pages  # noqa: E402

PAGES = [
    ("overview", "Przegląd", "lscc-pulse-symbolic", pages.OverviewPage),
    ("updates", "Aktualizacje", "software-update-available-symbolic", pages.UpdatesPage),
    ("cleanup", "Sprzątanie", "user-trash-symbolic", pages.CleanupPage),
    ("programs", "Programy", "view-app-grid-symbolic", pages.ProgramsPage),
    ("autostart", "Autostart", "system-run-symbolic", hwpages.AutostartPage),
    (None, "SPRZĘT", None, None),
    ("disk", "Dysk", "drive-harddisk-symbolic", hwpages.DiskPage),
    ("battery", "Bateria", "battery-good-symbolic", hwpages.BatteryPage),
    ("temps", "Monitor", "lscc-temp-symbolic", hwpages.TempsPage),
    (None, "KOPIE I HISTORIA", None, None),
    ("timevault", "Linux Backup TimeVault", "drive-multidisk-symbolic", pages.TimeVaultPage),
    ("history", "Historia i przywracanie", "document-open-recent-symbolic", pages.HistoryPage),
]


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME, default_width=1180, default_height=780)
        self.set_size_request(760, 520)
        self.updates_cache = []
        self.built = {}
        self.rows = {}
        self.badges = {}

        self.toasts = Adw.ToastOverlay()
        split = Adw.NavigationSplitView(sidebar_width_fraction=0.24, min_sidebar_width=230, max_sidebar_width=290)

        # sidebar
        sb = Adw.ToolbarView()
        sh = Adw.HeaderBar(show_title=False)
        sh.add_css_class("lscc-tall")
        menu = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=self._menu(), primary=True)
        sh.pack_end(menu)
        # brand lives in the sidebar's header bar, level with the content's title bar
        brand = Gtk.Box(spacing=12, margin_start=6)
        brand.append(Gtk.Image(icon_name="io.github.jgu.LinuxSystemCareCheck", pixel_size=52, valign=Gtk.Align.CENTER))
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, valign=Gtk.Align.CENTER)
        t = Gtk.Label(label="Linux System\nCare Check", xalign=0, justify=Gtk.Justification.LEFT)
        t.add_css_class("lscc-brand")
        col.append(t)
        s = Gtk.Label(label="JGu Linux Apps", xalign=0)
        s.add_css_class("dim-label")
        s.add_css_class("caption")
        col.append(s)
        brand.append(col)
        sh.pack_start(brand)
        sb.add_top_bar(sh)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=10)
        self.list = Gtk.ListBox()
        self.list.add_css_class("navigation-sidebar")
        for key, title, icon, _cls in PAGES:
            if key is None:
                sep = Gtk.ListBoxRow(selectable=False, activatable=False, can_focus=False)
                sep.add_css_class("lscc-sep")
                sep.set_child(Gtk.Label(label=_(title or ""), xalign=0, css_classes=["lscc-kicker"],
                                        margin_top=10, margin_start=10))
                self.list.append(sep)
                continue
            row = Gtk.ListBoxRow()
            rb = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=6, margin_end=6)
            rb.append(Gtk.Image(icon_name=icon))
            lb = Gtk.Label(label=_(title), xalign=0, hexpand=True, ellipsize=3)
            rb.append(lb)
            badge = Gtk.Label(visible=False)
            badge.add_css_class("lscc-chip")
            rb.append(badge)
            self.badges[key] = badge
            row.set_child(rb)
            row.key = key
            self.rows[key] = row
            self.list.append(row)
        self.list.connect("row-selected", self._selected)
        box.append(Gtk.ScrolledWindow(child=self.list, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        sb.set_content(box)
        split.set_sidebar(Adw.NavigationPage(title=APP_NAME, child=sb))

        # content
        self.content_tv = Adw.ToolbarView()
        self.content_hb = Adw.HeaderBar()
        self.content_hb.add_css_class("lscc-tall")
        self.content_tv.add_top_bar(self.content_hb)
        pv = Gtk.Box(spacing=8, tooltip_text=_("Tryb podglądu: aplikacja pokazuje polecenia, ale niczego nie zmienia"))
        pv.append(Gtk.Label(label=_("Podgląd")))
        self.preview_sw = Gtk.Switch(valign=Gtk.Align.CENTER, active=bool(settings.load()["preview"]))
        self._pv_guard = False
        self.preview_sw.connect("notify::active", self._preview_toggled)
        pv.append(self.preview_sw)
        self.content_hb.pack_end(pv)
        self.banner = Adw.Banner(title=_("Tryb podglądu: aplikacja pokazuje, co by zrobiła, ale niczego nie zmienia w systemie."),
                                 button_label=_("Wyłącz podgląd"))
        self.banner.connect("button-clicked", lambda *_: self.preview_sw.set_active(False))
        self.content_tv.add_top_bar(self.banner)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.content_tv.set_content(self.stack)
        self.content_page = Adw.NavigationPage(title=_("Przegląd"), child=self.content_tv)
        split.set_content(self.content_page)
        self.split = split

        self.toasts.set_child(split)
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 820sp"))
        bp.add_setter(split, "collapsed", True)
        self.add_breakpoint(bp)
        self.set_content(self.toasts)
        self.update_banner()
        self.list.select_row(self.rows["overview"])

    def _menu(self):
        from gi.repository import Gio
        m = Gio.Menu()
        m.append(_("Ustawienia"), "app.preferences")
        m.append(_("O programie"), "app.about")
        m.append(_("Zakończ"), "app.quit")
        return m

    def _selected(self, _lb, row):
        if row is None or not hasattr(row, "key"):
            return
        self.show_page(row.key, select=False)

    def show_page(self, key, select=True):
        if select:
            self.list.select_row(self.rows[key])
            return
        if key not in self.built:
            cls = next(c for k, _t, _i, c in PAGES if k == key)
            page = cls(self)
            self.built[key] = page
            self.stack.add_named(page, key)
        self.stack.set_visible_child_name(key)
        self.content_page.set_title(_(next(t for k, t, _i, _c in PAGES if k == key)))
        self.split.set_show_content(True)

    def reload_pages(self):
        """Rebuild every page that was opened (e.g. after a theme change)."""
        cur = self.stack.get_visible_child_name()
        for key, page in list(self.built.items()):
            self.stack.remove(page)
        self.built = {}
        if cur:
            self.show_page(cur, select=False)

    def refresh_page(self, key):
        p = self.built.get(key)
        if p is not None:
            p.refresh()

    def set_badge(self, key, n):
        b = self.badges.get(key)
        if b:
            b.set_text(str(n))
            b.set_visible(n > 0)

    def toast(self, t):
        self.toasts.add_toast(t)

    def update_banner(self):
        on = bool(settings.load()["preview"])
        self.banner.set_revealed(on)
        if self.preview_sw.get_active() != on:
            self._pv_guard = True
            self.preview_sw.set_active(on)
            self._pv_guard = False

    def _preview_toggled(self, sw, _p):
        if self._pv_guard:
            return
        if sw.get_active():
            settings.save(preview=True)
            self.update_banner()
            return
        d = Adw.AlertDialog(heading=_("Wyłączyć tryb podglądu?"),
                            body=_("Od teraz aplikacja będzie naprawdę wprowadzać zmiany. Każdą zmianę nadal zobaczysz "
                                   "w całości i potwierdzisz przed wykonaniem; zmiany systemowe wymagają hasła."))
        d.add_response("cancel", _("Anuluj"))
        d.add_response("off", _("Wyłącz podgląd"))
        d.set_response_appearance("off", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel")

        def resp(_d, r):
            if r == "off":
                settings.save(preview=False)
            self.update_banner()
        d.connect("response", resp)
        d.present(self)

    def app_prefs(self):
        self.get_application().activate_action("preferences", None)
