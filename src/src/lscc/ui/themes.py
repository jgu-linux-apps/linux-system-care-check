"""Themes, each with a light and a dark variant following the system: System (Adwaita), Aurora (the series
theme), Studio (graphite + amber), Aubergine (aubergine + Ubuntu orange), Solid, Terminal and Hologram
(cyan neon HUD with smoked glass). Colours are set through
libadwaita's CSS variables in a separate provider, so switching is live."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

THEMES = ("system", "aurora", "studio", "aubergine", "solid", "terminal", "hologram")

_HG = ("repeating-linear-gradient(0deg, alpha({c},{a}) 0px, alpha({c},{a}) 1px, transparent 1px, transparent 28px), "
       "repeating-linear-gradient(90deg, alpha({c},{a}) 0px, alpha({c},{a}) 1px, transparent 1px, transparent 28px)")

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
    # Hologram: a cyberpunk HUD — cyan neon on smoked glass, a faint grid behind; no warm colours
    ("hologram", True): dict(bg="#04121a", fg="#d6fbff", view="#061a24", head="#031018", side="#03121b", card="#082430",
                             pop="#0a2a38", acc="#22e6ff", acc2="#3b82f6", accfg="#021018", warn="#a78bfa",
                             grad="linear-gradient(90deg, alpha(#22e6ff,0.95), alpha(#0ea5e9,0.85))",
                             win=_HG.format(c="#22e6ff", a=0.04) + ", radial-gradient(ellipse at 70% 0%, alpha(#22e6ff,0.16), "
                                 "transparent 55%), radial-gradient(ellipse at 0% 100%, alpha(#0ea5e9,0.14), transparent 55%)"),
    ("hologram", False): dict(bg="#e6f6fb", fg="#04293a", view="#f2fbfe", head="#05202e", side="#062635", card="#ffffff",
                              pop="#ffffff", acc="#0aa5c7", acc2="#2563eb", accfg="#ffffff", warn="#7c3aed",
                              grad="linear-gradient(90deg, #22d3ee, #0284c7)",
                              win=_HG.format(c="#0891b2", a=0.06) + ", radial-gradient(ellipse at 80% 0%, alpha(#22d3ee,0.28), "
                                  "transparent 50%), radial-gradient(ellipse at 20% 110%, alpha(#3b82f6,0.14), transparent 50%)"),
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
/* window controls and header-bar icon buttons stay like the system draws them: no frame */
windowcontrols button, headerbar button.image-button, headerbar menubutton > button, button.flat,
.lscc-stat-card { box-shadow: none; }
windowcontrols button { border-radius: 999px; }
""",
    "solid": """
.card, .lscc-card { box-shadow: 0 0 0 1px alpha(@window_fg_color, 0.08); }
.navigation-sidebar > row { border-radius: 6px; }
button.pill { border-radius: 8px; }
""",
}

# Hologram: smoked-glass panels. GTK has no backdrop blur, so the "smoke" is a tinted, translucent fill with a
# soft sheen gradient over the grid. Both header bars share one rule, so the top bars stay equal.
_HOLO = """
.card, .lscc-card, .boxed-list, list.boxed-list > row, button, entry, .lscc-chip, .lscc-bar, popover > contents,
.navigation-sidebar > row, progressbar > trough, progressbar > trough > progress, levelbar > trough, levelbar block,
scale trough, scale highlight { border-radius: 6px; }
.lscc-kicker { letter-spacing: 3px; opacity: 0.95; }
.lscc-title, .lscc-brand { letter-spacing: 1px; }
.navigation-sidebar { background: transparent; }
button.flat, windowcontrols button, headerbar button.image-button, button.lscc-stat-card { border: none; background: none; box-shadow: none; }
/* header-bar buttons stay frameless, so both top bars keep the same height */
headerbar button, headerbar menubutton > button, menubutton.flat > button { border: none; background: none; box-shadow: none; }
headerbar button:hover, headerbar menubutton > button:hover { background: alpha(currentColor, 0.12); }
.navigation-sidebar > row:selected { font-weight: 700; }
"""
EXTRA_MODE = {
    ("hologram", True): _HOLO + """
.card, .lscc-card, .boxed-list {
  background-color: alpha(#0b2a38, 0.42);
  background-image: linear-gradient(160deg, alpha(#ffffff, 0.07), alpha(#ffffff, 0.0) 45%, alpha(#22e6ff, 0.04));
  border: 1px solid alpha(#22e6ff, 0.5);
  box-shadow: 0 0 18px alpha(#22e6ff, 0.20), inset 0 1px alpha(#bff9ff, 0.25), inset 0 0 28px alpha(#22e6ff, 0.06); }
.lscc-kicker { color: #22e6ff; }
.lscc-title { color: #e6fdff; }
.lscc-stat, .lscc-big { color: #7df3ff; }
headerbar, headerbar:backdrop, .sidebar-pane headerbar, .sidebar-pane headerbar:backdrop {
  background-color: #031620; background-image: linear-gradient(180deg, alpha(#22e6ff, 0.10), alpha(#22e6ff, 0.02)); color: #9ff6ff; box-shadow: none; }
toolbarview > .top-bar, .top-bar { background-color: #031620; background-image: linear-gradient(180deg, alpha(#22e6ff, 0.10), alpha(#22e6ff, 0.02)); box-shadow: inset 0 -1px alpha(#22e6ff, 0.6); }
.sidebar-pane headerbar, .sidebar-pane headerbar:backdrop { box-shadow: inset 0 -1px alpha(#22e6ff, 0.6); }
headerbar .title { color: #9ff6ff; }
.sidebar-pane { background-color: alpha(#02101a, 0.62);
  background-image: linear-gradient(180deg, alpha(#22e6ff, 0.06), alpha(#22e6ff, 0.0) 40%);
  box-shadow: inset -1px 0 alpha(#22e6ff, 0.4); }
.navigation-sidebar > row:selected { box-shadow: 0 0 18px alpha(#22e6ff, 0.55); }
.navigation-sidebar image { color: #22e6ff; }
.navigation-sidebar > row:selected image { color: #021018; }
button { background-color: alpha(#22e6ff, 0.08); border: 1px solid alpha(#22e6ff, 0.55); color: #c9fbff; }
button:hover { background-color: alpha(#22e6ff, 0.18); box-shadow: 0 0 14px alpha(#22e6ff, 0.45); }
button.suggested-action { border: none; box-shadow: 0 0 16px alpha(#22e6ff, 0.55); font-weight: 800; }
.lscc-chip { background: alpha(#22e6ff, 0.12); color: #7df3ff; border: 1px solid alpha(#22e6ff, 0.5); }
switch:checked { background: #22e6ff; }
popover > contents, dialog { background-color: alpha(#05202c, 0.94); }
""",
    ("hologram", False): _HOLO + """
.card, .lscc-card, .boxed-list {
  background-color: alpha(#ffffff, 0.55);
  background-image: linear-gradient(160deg, alpha(#ffffff, 0.85), alpha(#d6f3fa, 0.45) 60%, alpha(#bdeaf5, 0.35));
  border: 1px solid alpha(#0aa5c7, 0.65);
  box-shadow: 0 0 22px alpha(#22d3ee, 0.26), inset 0 2px alpha(#22d3ee, 0.85), 0 10px 24px alpha(#05202e, 0.08); }
.lscc-kicker { color: #0891b2; font-weight: 800; }
.lscc-title { color: #04293a; }
.lscc-stat, .lscc-big { color: #0369a1; }
headerbar, headerbar:backdrop, .sidebar-pane headerbar, .sidebar-pane headerbar:backdrop {
  background-color: #06283a; background-image: linear-gradient(180deg, alpha(#7df3ff, 0.14), alpha(#22d3ee, 0.03)); color: #bff6ff; box-shadow: none; }
toolbarview > .top-bar, .top-bar { background-color: #06283a; background-image: linear-gradient(180deg, alpha(#7df3ff, 0.14), alpha(#22d3ee, 0.03)); box-shadow: inset 0 -1px alpha(#22d3ee, 0.85); }
.sidebar-pane headerbar, .sidebar-pane headerbar:backdrop { box-shadow: inset 0 -1px alpha(#22d3ee, 0.85); }
headerbar .title, headerbar label, headerbar image { color: #9ff3ff; }
.sidebar-pane { background-color: alpha(#05202e, 0.86);
  background-image: linear-gradient(180deg, alpha(#22d3ee, 0.10), alpha(#22d3ee, 0.0) 35%, alpha(#0284c7, 0.08));
  box-shadow: inset -2px 0 alpha(#22d3ee, 0.6); }
.sidebar-pane, .sidebar-pane label, .sidebar-pane image { color: #d6fbff; }
/* menus opened from the dark sidebar are light popovers: give them dark text again */
.sidebar-pane popover label, .sidebar-pane popover image { color: #04293a; }
.sidebar-pane popover .accelerator, .sidebar-pane popover .dim-label { color: alpha(#04293a, 0.55); }
.sidebar-pane .dim-label, .sidebar-pane .lscc-kicker { color: #22d3ee; }
.lscc-foot { border-top: 1px solid alpha(#22d3ee, 0.35); }
.navigation-sidebar > row:selected { box-shadow: 0 0 18px alpha(#22d3ee, 0.6); }
.navigation-sidebar image { color: #22d3ee; }
.navigation-sidebar > row:selected image, .navigation-sidebar > row:selected label { color: #ffffff; }
button { background-color: alpha(#ffffff, 0.75); border: 1px solid alpha(#0aa5c7, 0.8); color: #04506a; box-shadow: 0 0 10px alpha(#22d3ee, 0.25); }
button:hover { background-color: alpha(#22d3ee, 0.12); box-shadow: 0 0 16px alpha(#22d3ee, 0.5); }
button.suggested-action { border: none; color: #ffffff; box-shadow: 0 0 16px alpha(#22d3ee, 0.6); }
.lscc-chip { background: alpha(#22d3ee, 0.16); color: #0369a1; border: 1px solid alpha(#0aa5c7, 0.6); }
switch:checked { background: #0aa5c7; }
""",
}

# The htop view has its own stylesheet above the theme's; these replace its terminal colours with smoked glass.
HTOP = {
    "hologram": """
.lscc-htop, .lscc-htop.light { background-color: alpha(#021018, 0.78); color: #d6fbff;
  box-shadow: inset 0 0 0 1px alpha(#22e6ff, 0.45), 0 0 18px alpha(#22e6ff, 0.18); }
.lscc-htop label, .lscc-htop list > row, .lscc-htop list, .lscc-htop.light label, .lscc-htop.light list > row,
.lscc-htop.light list, .lscc-htop button, .lscc-htop.light button { color: #d6fbff; }
.lscc-htop .hdr, .lscc-htop.light .hdr { background: alpha(#22e6ff, 0.85); color: #021018; }
.lscc-htop list > row:selected, .lscc-htop.light list > row:selected,
.lscc-htop button:checked, .lscc-htop .fkey, .lscc-htop.light button:checked, .lscc-htop.light .fkey { background: #22e6ff; color: #021018; }
.lscc-htop list > row:selected label, .lscc-htop.light list > row:selected label, .lscc-htop button:checked label,
.lscc-htop .fkey label, .lscc-htop.light button:checked label, .lscc-htop.light .fkey label, .lscc-htop.light .fkey image { color: #021018; }
.lscc-htop entry, .lscc-htop.light entry { background: alpha(#22e6ff, 0.10); color: #d6fbff; }
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
button.lscc-stat-card { padding: 0; background: none; font-weight: normal; }
button.lscc-stat-card > box { margin: 0; }
button.lscc-stat-card:hover > box { background-color: alpha(@accent_bg_color, 0.10); }
button.lscc-stat-card:hover .lscc-kicker { color: @accent_color; opacity: 1; }
.lscc-brand { font-size: 13px; font-weight: 800; line-height: 1.05; }
.lscc-foot { border-top: 1px solid alpha(currentColor, 0.10); padding-top: 4px; }
.lscc-foot .lscc-brand { line-height: 1.15; }
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
    if "warn" in c:
        root += f"@define-color lscc_warn {c['warn']};\n"
    win = f"window.background {{ background-image: {c['win']}; }}\n" if c["win"] != "none" else ""
    return root + win + f"""
headerbar {{ background: {c['head']}; box-shadow: inset 0 -1px alpha({c['fg']}, 0.08); }}
.navigation-sidebar > row:selected {{ background-image: {c['grad']}; color: {c['accfg']}; }}
.navigation-sidebar > row:selected image {{ color: {c['accfg']}; }}
button.suggested-action {{ background-image: {c['grad']}; color: {c['accfg']}; }}
progressbar > trough > progress {{ background-image: {c['grad']}; }}
""" + EXTRA.get(name, "") + EXTRA_MODE.get((name, dark), "")


DARK_CHIPS = """
.lscc-chip.sec { background: alpha(#f87171, 0.18); color: #fca5a5; }
.lscc-chip.warn { background: alpha(#fbbf24, 0.18); color: #fcd34d; }
.lscc-chip.ok { background: alpha(#4ade80, 0.16); color: #86efac; }
"""


class Themes:
    def __init__(self):
        self.name = "system"
        self.provider = None
        self.htop = None
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
        if self.htop is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self.htop)
            self.htop = None
        if self.name in HTOP:
            self.htop = Gtk.CssProvider()
            self.htop.load_from_string(HTOP[self.name])
            # above the htop view's own stylesheet (APPLICATION + 3)
            Gtk.StyleContext.add_provider_for_display(display, self.htop, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 4)
        dark = Adw.StyleManager.get_default().get_dark()
        css = ("" if self.name == "system" else _css(self.name, dark)) + (DARK_CHIPS if dark else "")
        if not css:
            return
        self.provider = Gtk.CssProvider()
        self.provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
