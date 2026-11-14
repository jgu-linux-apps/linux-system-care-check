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

from .i18n_en import EN  # noqa: E402


def _(s):
    return EN.get(s, s) if LANG == "en" else s
