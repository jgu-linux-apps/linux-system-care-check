"""Live tray icon: draws CPU / RAM / temperature / network as a tiny graph or a number into ARGB pixels
for the StatusNotifierItem IconPixmap (no GTK in here — plain pycairo on an image surface)."""
import cairo

from . import health, hw
from .procs import Sampler

SIZE = 32
HIST = 12
WHITE = (1, 1, 1)
GREEN = (0.54, 0.89, 0.20)      # Tango green, like the htop view
ORANGE = (1.0, 0.55, 0.24)
RED = (0.94, 0.16, 0.16)


def to_argb(surface):
    """cairo ARGB32 (native little-endian BGRA, premultiplied) -> SNI ARGB bytes (big-endian, straight)."""
    surface.flush()
    src = bytes(surface.get_data())
    out = bytearray(len(src))
    for i in range(0, len(src), 4):
        b, g, r, a = src[i], src[i + 1], src[i + 2], src[i + 3]
        if a and a < 255:
            r, g, b = min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a)
        out[i:i + 4] = bytes((a, r, g, b))
    return bytes(out)


def level_color(frac):
    return RED if frac >= 0.9 else ORANGE if frac >= 0.7 else WHITE


def draw_graph(series, colors, lo=0.0, hi=100.0, mirror=False):
    """Bar history like the classic system-monitor applets. mirror: two series, up (first) and down (second)."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    cr = cairo.Context(surf)
    cr.set_source_rgba(1, 1, 1, 0.22)
    cr.rectangle(0.5, 0.5, SIZE - 1, SIZE - 1)
    cr.set_line_width(1)
    cr.stroke()
    w = (SIZE - 4) / HIST
    for si, ser in enumerate(series):
        vals = ser[-HIST:]
        for i, v in enumerate(vals):
            if v is None:
                continue
            f = max(0.0, min(1.0, (v - lo) / (hi - lo))) if hi > lo else 0
            x = 2 + (HIST - len(vals) + i) * w
            col = colors[si] if colors[si] else level_color(f)
            cr.set_source_rgb(*col)
            if mirror:
                hh = f * (SIZE / 2 - 3)
                if si == 0:
                    cr.rectangle(x, SIZE / 2 - hh, max(1, w - 0.6), hh)
                else:
                    cr.rectangle(x, SIZE / 2, max(1, w - 0.6), hh)
            else:
                hh = max(1, f * (SIZE - 4))
                cr.rectangle(x, SIZE - 2 - hh, max(1, w - 0.6), hh)
            cr.fill()
    return to_argb(surf)


def draw_number(text, frac, sub=None):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    cr = cairo.Context(surf)
    cr.select_font_face("Ubuntu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    size = 19 if len(text) <= 2 else 14 if len(text) <= 3 else 11
    cr.set_font_size(size)
    ext = cr.text_extents(text)
    cr.set_source_rgb(*level_color(frac))
    cr.move_to((SIZE - ext.x_advance) / 2, 21 if sub is None else 17)
    cr.show_text(text)
    # bar at the bottom
    cr.set_source_rgba(1, 1, 1, 0.25)
    cr.rectangle(3, SIZE - 6, SIZE - 6, 3)
    cr.fill()
    cr.set_source_rgb(*level_color(frac))
    cr.rectangle(3, SIZE - 6, (SIZE - 6) * max(0.0, min(1.0, frac)), 3)
    cr.fill()
    return to_argb(surf)


def short_rate(bps):
    if bps is None:
        return "0"
    for unit in ("", "K", "M", "G"):
        if bps < 1000:
            return f"{bps:.0f}{unit}"
        bps /= 1000
    return f"{bps:.0f}T"


class LiveIcon:
    """Keeps the history and returns (argb_bytes, tooltip) for the chosen metric."""

    def __init__(self):
        self.sampler = Sampler()
        self.hist = {"cpu": [], "ram": [], "temp": [], "rx": [], "tx": []}

    def _push(self, key, v):
        h = self.hist[key]
        h.append(v)
        del h[:-HIST]

    def update(self, metric, style):
        d = self.sampler.sample(with_procs=False)
        cpu = d["cpu"]
        ram = 100 * d["mem_used"] / d["mem_total"] if d["mem_total"] else 0
        temp = health.cpu_temp()
        self._push("cpu", cpu)
        self._push("ram", ram)
        self._push("temp", temp)
        self._push("rx", d["rx"])
        self._push("tx", d["tx"])
        if metric == "cpu":
            tip = f"CPU {cpu or 0:.0f}%"
            img = draw_number(f"{cpu or 0:.0f}", (cpu or 0) / 100) if style == "number" else draw_graph([self.hist["cpu"]], [None])
        elif metric == "ram":
            tip = f"RAM {ram:.0f}% ({d['mem_used'] / 1e9:.1f} / {d['mem_total'] / 1e9:.1f} GB)"
            img = draw_number(f"{ram:.0f}", ram / 100) if style == "number" else draw_graph([self.hist["ram"]], [None])
        elif metric == "temp":
            t = temp or 0
            tip = f"CPU {t:.0f}°C"
            img = draw_number(f"{t:.0f}°", (t - 30) / 70) if style == "number" else draw_graph([self.hist["temp"]], [None], 30, 100)
        else:
            rx, tx = d["rx"] or 0, d["tx"] or 0
            tip = f"↓ {short_rate(rx)}B/s  ↑ {short_rate(tx)}B/s"
            if style == "number":
                img = draw_number(short_rate(max(rx, tx)), 0)
            else:
                top = max([v or 0 for v in self.hist["rx"] + self.hist["tx"]] + [50_000])
                img = draw_graph([self.hist["rx"], self.hist["tx"]], [GREEN, ORANGE], 0, top, mirror=True)
        return img, tip
