"""What can be cleaned — only items from the allowlist in safety.py, all re-creatable. Read only (no root).

Each item knows its size, a short description and whether it is ticked by default. System items are
cleaned by the root helper with the tool's own command; user items (thumbnails, Trash) by the app itself."""
import glob
import os
import platform
import re
from dataclasses import dataclass, field

from . import safety
from .i18n import _
from .sysrun import dir_size, have, run


@dataclass
class Item:
    id: str
    title: str
    detail: str
    size: int
    default_on: bool = True
    system: bool = True
    args: list = field(default_factory=list)     # what exactly will be cleaned (passed to the helper)


def apt_cache():
    files = glob.glob("/var/cache/apt/archives/*.deb")
    size = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
    return Item("apt-cache", "Pamięć podręczna apt", _("%d pobranych paczek .deb po instalacji") % len(files), size)


JOURNAL_RE = re.compile(r"take up ([0-9.]+)([KMGT]?)B?")


def journal():
    rc, out, err = run(["journalctl", "--disk-usage"], timeout=20)
    m = JOURNAL_RE.search(out + err)
    size = 0
    if m:
        size = int(float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}[m.group(2)])
    # we keep the last 2 weeks; what goes depends on the age of the logs — shown as "up to"
    return Item("journal", "Logi systemowe (journal)", _("zostają logi z ostatnich 2 tygodni"), size)


def parse_snap_disabled(text):
    """[(name, rev)] of disabled snap revisions from `snap list --all`."""
    out = []
    for line in text.splitlines()[1:]:
        p = line.split()
        if len(p) >= 6 and "disabled" in p[-1]:
            out.append((p[0], p[2]))
    return out


def snap_disabled():
    if not have("snap"):
        return None
    rc, out, _err = run(["snap", "list", "--all"], timeout=30)
    revs = [(n, r) for n, r in parse_snap_disabled(out) if safety.valid_snap(n) and safety.valid_rev(r)]
    size = 0
    for n, r in revs:
        f = f"/var/lib/snapd/snaps/{n}_{r}.snap"
        if os.path.exists(f):
            size += os.path.getsize(f)
    names = {}
    for n, _r in revs:
        names[n] = names.get(n, 0) + 1
    detail = ", ".join(f"{n} ({c})" for n, c in sorted(names.items())) or _("brak")
    return Item("snap-disabled", "Wyłączone wersje snapów", detail, size, args=[f"{n}={r}" for n, r in revs])


def parse_kernels(text):
    """{version: size_bytes} of *installed* kernels from dpkg-query output 'pkg status size'."""
    out = {}
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 4 and p[1:4] == ["install", "ok", "installed"]:
            m = re.match(r"^linux-image-(?:unsigned-)?([0-9].*)$", p[0])
            if m:
                out[m.group(1)] = int(p[4]) * 1024 if len(p) > 4 and p[4].isdigit() else 0
    return out


def old_kernels():
    rc, out, _err = run(["dpkg-query", "-W", "-f=${Package} ${Status} ${Installed-Size}\n", "linux-image-[0-9]*"], timeout=20)
    inst = parse_kernels(out)
    running = platform.release()
    rem = safety.removable_kernels(list(inst), running)
    others = sorted((v for v in inst if v != running), key=safety._kver_key)
    keep = _("zostają: bieżące %s") % running + ((_(" i zapasowe %s") % others[-1]) if others else "")
    detail = (", ".join(rem) + " · " + keep) if rem else _("brak starych jąder") + " · " + keep
    # each kernel also has modules (~5x the image size); report image + modules estimate
    size = sum(inst[v] for v in rem) * 6
    return Item("old-kernels", "Stare jądra Linux", detail, size, args=rem)


def flatpak_unused():
    if not have("flatpak"):
        return None
    rc, out, _err = run(["flatpak", "uninstall", "--unused", "--assumeno"], timeout=60)
    refs = re.findall(r"^\s*\d+\.\s+(\S+)", out, re.M)
    sizes = {}
    rc2, out2, _err = run(["flatpak", "list", "--runtime", "--columns=application,size"], timeout=30)
    from .sysrun import parse_size
    for line in out2.splitlines():
        p = line.split("\t")
        if len(p) >= 2:
            sizes[p[0]] = parse_size(p[1])
    size = sum(sizes.get(r, 0) for r in refs)
    return Item("flatpak-unused", "Nieużywane środowiska flatpak", ", ".join(refs) or _("brak"), size)


def thumbnails():
    path = os.path.expanduser("~/.cache/thumbnails")
    return Item("thumbnails", "Miniatury zdjęć", _("~/.cache/thumbnails — odtworzą się same"), dir_size(path),
                default_on=False, system=False)


def trash():
    path = os.path.expanduser("~/.local/share/Trash/files")
    n = len(os.listdir(path)) if os.path.isdir(path) else 0
    return Item("trash", "Kosz", (_("%d plików") % n) if n else _("pusty"), dir_size(path), default_on=False, system=False)


def scan():
    items = []
    for fn in (old_kernels, snap_disabled, apt_cache, journal, flatpak_unused, thumbnails, trash):
        try:
            it = fn()
        except Exception as e:  # noqa: BLE001 — one failing source must not hide the others
            it = Item(fn.__name__, fn.__name__, _("błąd odczytu") + f": {e}", 0, default_on=False)
        if it is not None:
            if it.size == 0 and not it.args and it.id not in ("journal",):
                it.default_on = False
            items.append(it)
    return items


def clean_user(item_id):
    """Thumbnails / Trash: done by the app itself (user files), never anything else."""
    import shutil
    if item_id == "thumbnails":
        path = os.path.expanduser("~/.cache/thumbnails")
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        return True
    if item_id == "trash":
        from gi.repository import Gio
        trash = Gio.File.new_for_uri("trash:///")
        try:
            en = trash.enumerate_children("standard::name", Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None)
            for info in en:
                trash.get_child(info.get_name()).delete(None)
        except Exception:  # noqa: BLE001
            return False
        return True
    raise ValueError("not a user cleanup item: " + item_id)
