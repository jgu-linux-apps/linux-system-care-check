"""Settings dialog: appearance (theme) and safety (preview mode, TimeVault backup before changes)."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from .. import settings  # noqa: E402
from ..i18n import _  # noqa: E402
from .themes import THEMES  # noqa: E402

THEME_NAMES = {"system": "System", "aurora": "Aurora", "studio": "Studio", "aubergine": "Aubergine", "solid": "Solid",
               "terminal": "Terminal"}


class Prefs(Adw.PreferencesDialog):
    def __init__(self, win, themes):
        super().__init__(title=_("Ustawienia"))
        self.win, self.themes = win, themes
        s = settings.load()
        page = Adw.PreferencesPage(title=_("Ogólne"), icon_name="preferences-system-symbolic")

        look = Adw.PreferencesGroup(title=_("Wygląd"),
                                    description=_("Każdy motyw ma wersję jasną i ciemną — według ustawień systemu."))
        model = Gtk.StringList.new([_(THEME_NAMES[t]) for t in THEMES])
        row = Adw.ComboRow(title=_("Motyw"), model=model, selected=THEMES.index(s["theme"]) if s["theme"] in THEMES else 0)
        row.connect("notify::selected", self._theme)
        look.add(row)
        langs = ["auto", "pl", "en"]
        cur = s.get("language", "auto")
        lr = Adw.ComboRow(title=_("Język") + (" · Language" if _("Język") == "Język" else " · Język"),
                          subtitle=_("Automatyczny = język systemu. Zmiana po ponownym uruchomieniu."),
                          model=Gtk.StringList.new([_("Automatyczny"), "Polski", "English"]),
                          selected=langs.index(cur) if cur in langs else 0)
        lr.connect("notify::selected", lambda r, _p: self._language(langs[r.get_selected()]))
        look.add(lr)
        rend = ["auto", "gl", "vulkan", "cairo"]
        rr = Adw.ComboRow(title=_("Renderer"), subtitle=_("Do rozwiązywania problemów z wyświetlaniem. "
                                                          "Zmiana po ponownym uruchomieniu aplikacji."),
                          model=Gtk.StringList.new([_("Automatyczny"), "GL", "Vulkan", _("Cairo (programowy)")]),
                          selected=rend.index(s.get("renderer", "auto")) if s.get("renderer", "auto") in rend else 0)
        rr.connect("notify::selected", lambda r, _p: settings.save(renderer=rend[r.get_selected()]))
        look.add(rr)
        page.add(look)

        safe = Adw.PreferencesGroup(title=_("Bezpieczeństwo"))
        pv = Adw.SwitchRow(title=_("Tryb podglądu"),
                           subtitle=_("Aplikacja pokazuje polecenia, ale niczego nie zmienia. Wyłącz, by wprowadzać zmiany."),
                           active=bool(s["preview"]))
        pv.connect("notify::active", self._preview)
        safe.add(pv)
        for key, title in (("backup_before_uninstall", _("Kopia TimeVault przed odinstalowaniem programów")),
                           ("backup_before_kernels", _("Kopia TimeVault przed usunięciem starych jąder")),
                           ("backup_before_update", _("Kopia TimeVault przed aktualizacją systemu")),
                           ("backup_before_firmware", _("Kopia TimeVault przed aktualizacją firmware"))):
            sw = Adw.SwitchRow(title=title, active=bool(s.get(key)))
            sw.connect("notify::active", lambda r, _p, k=key: settings.save(**{k: r.get_active()}))
            safe.add(sw)
        page.add(safe)

        page.add(self._background(s))
        page.add(self._auto(s))
        page.add(self._system())
        self.add(page)

    def _language(self, value):
        settings.save(language=value)
        d = Adw.AlertDialog(heading=_("Uruchomić ponownie?"),
                            body=_("Nowy język pojawi się po ponownym uruchomieniu aplikacji. Ikona w trayu przełączy się sama."))
        d.add_response("later", _("Później"))
        d.add_response("restart", _("Uruchom ponownie"))
        d.set_response_appearance("restart", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("restart")
        d.connect("response", lambda _d, r: r == "restart" and self._restart())
        d.present(self)

    @staticmethod
    def _restart():
        import os
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _switch(self, title, subtitle, key, s):
        sw = Adw.SwitchRow(title=title, subtitle=subtitle, active=bool(s.get(key)))
        sw.connect("notify::active", lambda r, _p: self._saved(key, r.get_active()))
        return sw

    def _saved(self, key, value):
        settings.save(**{key: value})
        if key in ("background_checks", "tray") and value:
            from .. import background
            background.ensure_running()

    def _background(self, s):
        g = Adw.PreferencesGroup(title=_("Sprawdzanie w tle"),
                                 description=_("Sprawdzanie i powiadomienia niczego nie zmieniają. Przycisk w powiadomieniu "
                                               "otwiera odpowiedni ekran — tam każdą zmianę potwierdzasz."))
        g.add(self._switch(_("Sprawdzaj system w tle"), _("aktualizacje, miejsce, kopia TimeVault, kondycja dysków"),
                           "background_checks", s))
        g.add(self._switch(_("Powiadomienia z przyciskami"), _("np. „Pokaż” / „Później”; „Później” wycisza na 24 h"),
                           "notifications", s))
        hours = [3, 6, 12, 24]
        cr = Adw.ComboRow(title=_("Jak często"), model=Gtk.StringList.new([_("co %d h") % h for h in hours]),
                          selected=hours.index(s["check_hours"]) if s["check_hours"] in hours else 1)
        cr.connect("notify::selected", lambda r, _p: settings.save(check_hours=hours[r.get_selected()]))
        g.add(cr)
        g.add(self._switch(_("Ikona w trayu"), _("stan systemu i szybkie sprawdzenie"), "tray", s))
        live = ["off", "cpu", "ram", "temp", "net"]
        lr = Adw.ComboRow(title=_("Ikona w trayu na żywo"), subtitle=_("odświeżana co 2 s; szczegóły w podpowiedzi po najechaniu"),
                          model=Gtk.StringList.new([_("Wyłączona (stan systemu)"), "CPU", "RAM", _("Temperatura CPU"),
                                                    _("Sieć ↓ pobieranie / ↑ wysyłanie")]),
                          selected=live.index(s["tray_live"]) if s["tray_live"] in live else 0)
        lr.connect("notify::selected", lambda r, _p: self._saved("tray_live", live[r.get_selected()]))
        g.add(lr)
        styles = ["graph", "number"]
        st = Adw.ComboRow(title=_("Styl ikony na żywo"), model=Gtk.StringList.new([_("Wykres słupkowy"), _("Liczba")]),
                          selected=styles.index(s["tray_live_style"]) if s["tray_live_style"] in styles else 0)
        st.connect("notify::selected", lambda r, _p: settings.save(tray_live_style=styles[r.get_selected()]))
        g.add(st)
        return g

    def _auto(self, s):
        g = Adw.PreferencesGroup(title=_("Działania automatyczne (za Twoją zgodą)"),
                                 description=_("Domyślnie wyłączone. Włączając, zgadzasz się, by aplikacja robiła to sama, "
                                               "bez pytania. Każde działanie trafia do Historii."))
        g.add(self._switch(_("Czyść miniatury zdjęć, gdy zajmują ponad 1 GB"), _("GNOME odtworzy je sam"),
                           "auto_thumbnails", s))
        g.add(self._switch(_("Rób kopię w Linux Backup TimeVault, gdy ostatnia ma ponad 7 dni"),
                           _("tylko gdy dysk TimeVault jest podłączony"), "auto_backup", s))
        g.add(self._switch(_("Przenoś do Kosza archiwa logów starsze niż %d dni") % s["archive_keep_days"],
                           _("liczbę dni ustawisz w Sprzątanie → Logi systemowe"), "auto_prune_archives", s))
        return g

    def _system(self):
        from gi.repository import Gio
        from .. import updates
        g = Adw.PreferencesGroup(title=_("Automatyczne funkcje Ubuntu i GNOME"),
                                 description=_("Ustawienia samego systemu — te same co w „Oprogramowanie i aktualizacje” "
                                               "oraz „Prywatność” w Ustawieniach GNOME."))
        inst, enabled = updates.unattended_status()
        self.ua = Adw.SwitchRow(title=_("Ubuntu instaluje aktualizacje bezpieczeństwa samo"),
                                subtitle=_("unattended-upgrades · zmiana wymaga hasła administratora"), active=bool(enabled))
        self.ua_guard = False
        self.ua.connect("notify::active", self._unattended)
        g.add(self.ua)
        try:
            priv = Gio.Settings.new("org.gnome.desktop.privacy")
            for key, title in (("remove-old-trash-files", _("Usuwaj z Kosza pliki starsze niż 30 dni")),
                               ("remove-old-temp-files", _("Usuwaj stare pliki tymczasowe"))):
                sw = Adw.SwitchRow(title=title, subtitle=_("funkcja GNOME"), active=priv.get_boolean(key))
                sw.connect("notify::active", lambda r, _p, k=key: priv.set_boolean(k, r.get_active()))
                g.add(sw)
        except Exception:  # noqa: BLE001  (schema missing outside GNOME)
            pass
        return g

    def _unattended(self, row, _p):
        if self.ua_guard:
            return
        from .. import helperclient, history
        from .common import in_background
        on = row.get_active()
        prev = settings.load()["preview"]

        def done(res, err):
            ok, out = res if res else (False, str(err))
            history.add("settings", _("Automatyczne aktualizacje bezpieczeństwa") + ": " + (_("włączone") if on else _("wyłączone")),
                        ok=ok, preview=prev)
            if not ok or prev:
                self.ua_guard = True
                row.set_active(not on)
                self.ua_guard = False
                self.add_toast(Adw.Toast(title=(_("Tryb podglądu: ") + out) if prev else _("Nie zmieniono")))
        in_background(lambda: helperclient.run("unattended", "on" if on else "off", preview=prev), done)

    def _theme(self, row, _p):
        name = THEMES[row.get_selected()]
        settings.save(theme=name)
        self.themes.apply(name)
        self.win.reload_pages()

    def _preview(self, row, _p):
        settings.save(preview=row.get_active())
        self.win.update_banner()
