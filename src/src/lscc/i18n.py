"""Polish / English. Strings in the code are Polish; English comes from this table.
Order: LSCC_LANG=en|pl, then Settings → Language (auto/pl/en), then the system language."""
import json
import locale
import os


def chosen():
    """The "language" setting: auto | pl | en (read directly: settings imports GLib)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    try:
        with open(os.path.join(base, "linux-system-care-check", "settings.json"), encoding="utf-8") as f:
            v = json.load(f).get("language", "auto")
    except (OSError, ValueError, AttributeError):
        v = "auto"
    return v if v in ("pl", "en") else "auto"


def _lang():
    forced = os.environ.get("LSCC_LANG")
    if forced in ("pl", "en"):
        return forced
    if chosen() != "auto":
        return chosen()
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            return "pl" if v.startswith("pl") else "en"
    try:
        return "pl" if (locale.getlocale()[0] or "").startswith("pl") else "en"
    except ValueError:
        return "en"


LANG = _lang()

from .i18n_en import EN  # noqa: E402


def _(s):
    return EN.get(s, s) if LANG == "en" else s
