"""Themes, each with a light and a dark variant following the system: System (Adwaita), Aurora (the series
theme), Studio (graphite + amber) and Aubergine (aubergine + Ubuntu orange). Colours are set through
libadwaita's CSS variables in a separate provider, so switching is live."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

THEMES = ("system", "aurora", "studio", "aubergine", "solid", "terminal")

P = {
    ("aurora", False): dict(bg="#f6f3ff", fg="#1f1a3a", view="#fcfbff", head="#f1edff", side="#f9f8ff",
                            card="#fdfcff", pop="#fbfaff", acc="#7c5cff", acc2="#22b8e6", accfg="#ffffff",
                            grad="linear-gradient(90deg, #7c5cff, #22b8e6)",
                            win="linear-gradient(135deg, #f6f2ff 0%, #eef8ff 55%, #fff4f8 100%)"),
    ("aurora", True): dict(bg="#0c0e1a", fg="#ecebff", view="#13151f", head="#0e1020", side="#121420",
                           card="#181a25", pop="#161a2e", acc="#a855f7", acc2="#22d3ee", accfg="#ffffff",
                           grad="linear-gradient(90deg, #a855f7, #22d3ee)",
                           win="radial-gradient(ellipse at 12% -5%, alpha(#22d3ee,0.18), transparent 55%), radial-gradient(ellipse at 100% 105%, alpha(#a855f7,0.22), transparent 55%)"),
    ("studio", False): dict(bg="#f5f5f4", fg="#1c1917", view="#ffffff", head="#ececea", side="#ececea", card="#ffffff",
                            pop="#ffffff", acc="#d97706", acc2="#f59e0b", accfg="#ffffff",
                            grad="linear-gradient(90deg, #d97706, #f59e0b)", win="none"),
    ("studio", True): dict(bg="#1e1f22", fg="#e0e2e6", view="#1a1b1e", head="#1a1b1e", side="#25272c", card="#25272c",
                           pop="#2e3138", acc="#f5b041", acc2="#e8a33d", accfg="#1a1b1e",
                           grad="linear-gradient(90deg, #e8a33d, #f5b041)", win="none"),
    ("aubergine", False): dict(bg="#fbf7fa", fg="#2c0f22", view="#ffffff", head="#f4ebf1", side="#f4ebf1", card="#ffffff",
                               pop="#ffffff", acc="#e95420", acc2="#a83279", accfg="#ffffff",
                               grad="linear-gradient(90deg, #e95420, #a83279)",
                               win="linear-gradient(135deg, #fbf5f9 0%, #fff6ef 100%)"),
    ("aubergine", True): dict(bg="#2c0f22", fg="#f6e9f1", view="#321729", head="#26091d", side="#240c1c",
                              card="#361b2d", pop="#3a1430", acc="#ff7a45", acc2="#e95420", accfg="#2c0f22",
                              grad="linear-gradient(90deg, #e95420, #ff7a45)",
                              win="radial-gradient(ellipse at 10% -5%, alpha(#e95420,0.18), transparent 55%)"),
    # Solid: calm, flat, opaque — no gradients, one accent
    ("solid", False): dict(bg="#f2f3f5", fg="#1f2328", view="#ffffff", head="#e9ebee", side="#e9ebee", card="#ffffff",
                           pop="#ffffff", acc="#2f6fdd", acc2="#2f6fdd", accfg="#ffffff",
                           grad="linear-gradient(#2f6fdd, #2f6fdd)", win="none"),
    ("solid", True): dict(bg="#1c1e21", fg="#e4e6e9", view="#222428", head="#18191c", side="#18191c", card="#26292d",
                          pop="#2b2e33", acc="#5b9cf5", acc2="#5b9cf5", accfg="#0f1114",
                          grad="linear-gradient(#5b9cf5, #5b9cf5)", win="none"),
    # Terminal: the Ubuntu terminal — aubergine #300A24, white text, inverse white bars (like top's header)
    ("terminal", False): dict(bg="#ffffff", fg="#300a24", view="#ffffff", head="#f3eef2", side="#f3eef2", card="#ffffff",
                              pop="#ffffff", acc="#300a24", acc2="#4e9a06", accfg="#ffffff",
                              grad="linear-gradient(#300a24, #300a24)", win="none"),
    ("terminal", True): dict(bg="#300a24", fg="#ffffff", view="#300a24", head="#2b0820", side="#2b0820", card="#350c29",
                             pop="#3d0f2f", acc="#ffffff", acc2="#8ae234", accfg="#300a24",
                             grad="linear-gradient(#ffffff, #ffffff)", win="none"),
}

EXTRA = {
    "terminal": """
* { font-family: "Ubuntu Sans Mono", "DejaVu Sans Mono", monospace; }
.card, .lscc-card, button, entry, .boxed-list, list.boxed-list > row, .lscc-chip, .lscc-bar, popover > contents,
dialog, .navigation-sidebar > row, switch, switch > slider, progressbar > trough, progressbar > trough > progress,
levelbar > trough, levelbar block, scale trough, scale highlight, scale slider { border-radius: 0; }
.card, .lscc-card, .boxed-list { border: 1px solid alpha(@window_fg_color, 0.25); box-shadow: none; }
.lscc-title { font-weight: 700; }
.lscc-kicker { letter-spacing: 2px; }
.navigation-sidebar > row:selected { background-image: none; background: @accent_bg_color; }
button { box-shadow: inset 0 0 0 1px alpha(@window_fg_color, 0.35); }
""",
    "solid": """
.card, .lscc-card { box-shadow: 0 0 0 1px alpha(@window_fg_color, 0.08); }
.navigation-sidebar > row { border-radius: 6px; }
button.pill { border-radius: 8px; }
""",
}

COMMON = """
.navigation-sidebar > row { border-radius: 11px; margin: 1px 6px; }
.lscc-big { font-size: 26px; font-weight: 800; }
.lscc-title { font-size: 24px; font-weight: 700; }
.lscc-kicker { font-size: 11px; font-weight: 700; letter-spacing: 1px; opacity: 0.65; }
.lscc-stat { font-size: 28px; font-weight: 800; }
.lscc-chip { font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 99px; background: alpha(@accent_bg_color, 0.15); color: @accent_color; }
.lscc-chip.sec { background: alpha(#dc2626, 0.14); color: #dc2626; }
.lscc-chip.warn { background: alpha(#d97706, 0.16); color: #b45309; }
.lscc-chip.ok { background: alpha(#16a34a, 0.14); color: #15803d; }
.lscc-card { padding: 16px 18px; }
.lscc-bar { padding: 10px 16px; border-radius: 14px; }
.navigation-sidebar > row.lscc-sep, .navigation-sidebar > row.lscc-sep:hover { background: none; min-height: 0; }
.navigation-sidebar > row:selected .lscc-chip { background: alpha(white, 0.25); color: inherit; }
.lscc-ring-small { opacity: 0.7; }
button:disabled { opacity: 0.45; }
.lscc-log { font-family: monospace; font-size: 12px; }
"""


def _css(name, dark):
    c = P[(name, dark)]
    v = dict(window_bg=c["bg"], window_fg=c["fg"], view_bg=c["view"], view_fg=c["fg"], headerbar_bg=c["head"],
             headerbar_fg=c["fg"], sidebar_bg=c["side"], sidebar_fg=c["fg"], card_bg=c["card"], card_fg=c["fg"],
             popover_bg=c["pop"], popover_fg=c["fg"], dialog_bg=c["pop"], dialog_fg=c["fg"],
             accent_bg=c["acc"], accent_fg=c["accfg"], accent=c["acc"])
    root = ":root {\n" + "".join(f"  --{k.replace('_', '-')}-color: {val};\n" for k, val in v.items()) + "}\n"
    root += "".join(f"@define-color {k}_color {val};\n" for k, val in v.items())
    root += f"@define-color lscc_accent2 {c['acc2'] if c['acc2'] != c['acc'] else c['fg']};\n"
    win = f"window.background {{ background-image: {c['win']}; }}\n" if c["win"] != "none" else ""
    return root + win + f"""
headerbar {{ background: {c['head']}; box-shadow: inset 0 -1px alpha({c['fg']}, 0.08); }}
.navigation-sidebar > row:selected {{ background-image: {c['grad']}; color: {c['accfg']}; }}
.navigation-sidebar > row:selected image {{ color: {c['accfg']}; }}
button.suggested-action {{ background-image: {c['grad']}; color: {c['accfg']}; }}
progressbar > trough > progress {{ background-image: {c['grad']}; }}
""" + EXTRA.get(name, "")


DARK_CHIPS = """
.lscc-chip.sec { background: alpha(#f87171, 0.18); color: #fca5a5; }
.lscc-chip.warn { background: alpha(#fbbf24, 0.18); color: #fcd34d; }
.lscc-chip.ok { background: alpha(#4ade80, 0.16); color: #86efac; }
"""


class Themes:
    def __init__(self):
        self.name = "system"
        self.provider = None
        self.common = Gtk.CssProvider()
        self.common.load_from_string(COMMON)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.common,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self._reload())

    def apply(self, name):
        self.name = name if name in THEMES else "system"
        self._reload()

    def _reload(self):
        display = Gdk.Display.get_default()
        if self.provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self.provider)
            self.provider = None
        dark = Adw.StyleManager.get_default().get_dark()
        css = ("" if self.name == "system" else _css(self.name, dark)) + (DARK_CHIPS if dark else "")
        if not css:
            return
        self.provider = Gtk.CssProvider()
        self.provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
