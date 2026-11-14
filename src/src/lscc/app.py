"""Application: themes, actions, main window."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, VERSION, WEBSITE, desktop, settings  # noqa: E402
from .i18n import _  # noqa: E402


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("page", 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             "Open a page (overview, updates, cleanup, programs, autostart, disk, battery, temps, "
                             "timevault, history)", "PAGE")
        GLib.set_application_name(APP_NAME)
        self.win = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        from .ui.themes import Themes
        self.themes = Themes()
        self.themes.apply(settings.load()["theme"])
        for name, cb, accel in (("quit", lambda *_: self.quit(), "<Control>q"),
                                ("preferences", self._prefs, "<Control>comma"),
                                ("about", self._about, None)):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            self.add_action(a)
            if accel:
                self.set_accels_for_action("app." + name, [accel])
        Gtk.Window.set_default_icon_name(APP_ID)
        import os
        from gi.repository import Gdk
        icons = os.path.dirname(desktop.icon_file(False) or "")
        if icons:
            Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(icons)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self._icon())
        self._icon()
        self._start_icon_watch()

    def _icon(self):
        try:
            desktop.apply_icon()
        except Exception as e:  # noqa: BLE001
            print("icon:", e)

    @staticmethod
    def _start_icon_watch():
        """The autostart helper runs from the next login; start it now too (it keeps one instance itself)."""
        import shutil
        import subprocess
        exe = shutil.which("linux-system-care-check")
        if exe:
            subprocess.Popen([exe, "--icon-sync-watch"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)

    def do_command_line(self, cmd):
        opts = cmd.get_options_dict().end().unpack()
        self.activate()
        page = opts.get("page")
        if page and self.win is not None and page in self.win.rows:
            self.win.show_page(page)
        return 0

    def do_activate(self):
        if self.win is None:
            from .ui.window import Window
            self.win = Window(self)
            if settings.load()["background_checks"] or settings.load()["tray"]:
                from . import background
                background.ensure_running()
        self.win.present()

    def _prefs(self, *_a):
        from .ui.prefs import Prefs
        Prefs(self.win, self.themes).present(self.win)

    def _about(self, *_a):
        d = Adw.AboutDialog(application_name=APP_NAME, application_icon=APP_ID, version=VERSION,
                            developer_name="JGu", website=WEBSITE, issue_url=WEBSITE + "/issues",
                            comments=_("Centrum opieki nad systemem Ubuntu: aktualizacje, sprzątanie, programy i "
                                       "kopie zapasowe z Linux Backup TimeVault — bez niespodzianek.") +
                            "\n\nCreated by: JGu · Supported by Claude",
                            license_type=Gtk.License.CUSTOM,
                            license="Freeware License (No Modifications). See /usr/share/doc/linux-system-care-check/copyright.")
        d.present(self.win)


def main():
    return App().run(sys.argv)
