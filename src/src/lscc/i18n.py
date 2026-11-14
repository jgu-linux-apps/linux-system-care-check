"""Polish / English. Strings in the code are Polish; English comes from this table when the system
language is not Polish (LSCC_LANG=en|pl forces one)."""
import locale
import os


def _lang():
    forced = os.environ.get("LSCC_LANG")
    if forced in ("pl", "en"):
        return forced
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            return "pl" if v.startswith("pl") else "en"
    try:
        return "pl" if (locale.getlocale()[0] or "").startswith("pl") else "en"
    except ValueError:
        return "en"


LANG = _lang()

EN = {
    "Przegląd": "Overview", "Aktualizacje": "Updates", "Sprzątanie": "Cleanup", "Programy": "Programs",
    "Historia i przywracanie": "History and restore", "Ustawienia": "Settings", "O programie": "About",
    "Zakończ": "Quit", "Sprawdź ponownie": "Check again", "Sprawdź": "Check",
    "Twój system jest w dobrej formie": "Your system is in good shape",
    "Twój system potrzebuje uwagi": "Your system needs attention",
    "forma systemu": "system health", "Co warto zrobić": "What to do", "Wszystko w porządku": "All good",
    "Dysk": "Disk", "Bateria": "Battery", "Temperatury": "Temperatures", "Ostatnio": "Recently",
    "aktualizacje bezpieczeństwa": "security updates", "Zainstaluj": "Install", "Pokaż": "Show",
    "Podgląd": "Preview", "do odzyskania": "to free up", "Aktualizuj wszystko": "Update everything",
    "Wyczyść zaznaczone": "Clean selected", "Odinstaluj zaznaczone": "Uninstall selected",
    "Zaznaczone": "Selected", "Odznacz": "Deselect", "Anuluj": "Cancel", "Szukaj programu…": "Search for a program…",
    "Wszystkie": "All", "Webappy": "Web apps", "Tryb podglądu": "Preview mode",
    "Tryb podglądu: aplikacja pokazuje, co by zrobiła, ale niczego nie zmienia w systemie.":
        "Preview mode: the app shows what it would do, but changes nothing in the system.",
    "Wyłącz w Ustawieniach": "Turn off in Settings",
    "Najpierw zrób kopię systemu w Linux Backup TimeVault": "First back up the system with Linux Backup TimeVault",
    "Utwórz kopię teraz": "Back up now", "Otwórz TimeVault": "Open TimeVault", "Przywróć system…": "Restore system…",
    "Pobierz i zainstaluj TimeVault": "Download and install TimeVault", "Strona projektu": "Project page",
    "Motyw": "Theme", "Wygląd": "Appearance", "Bezpieczeństwo": "Safety", "Gotowe": "Done", "Błąd": "Error",
    "Zamknij": "Close", "Szczegóły": "Details", "Wykonano": "Done", "Brak zmian": "No changes",
    "System": "System", "Aurora": "Aurora", "Studio": "Studio", "Aubergine": "Aubergine",
}


def _(s):
    return EN.get(s, s) if LANG == "en" else s
