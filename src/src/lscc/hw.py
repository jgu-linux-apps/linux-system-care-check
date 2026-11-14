"""Hardware readings without root: mounted disks, drive health (UDisks2 SMART), battery details,
temperature/fan sensors (hwmon) and the power profile. Nothing here changes the system."""
import glob
import os

from gi.repository import Gio, GLib

from .i18n import _
from .sysrun import have, run

REAL_FS = {"ext4", "ext3", "ext2", "btrfs", "xfs", "f2fs", "vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "zfs"}


# ------------------------------------------------------------------ mounted file systems
def parse_mounts(text):
    """[(device, mountpoint, fstype)] of real file systems from /proc/mounts."""
    out, seen = [], set()
    for line in text.splitlines():
        p = line.split()
        if len(p) < 3 or p[2] not in REAL_FS:
            continue
        mnt = p[1].replace("\\040", " ")
        if mnt.startswith(("/snap/", "/var/snap/", "/var/lib/snapd/", "/run/snapd/")):
            continue
        if p[0] in seen and mnt != "/":
            continue
        seen.add(p[0])
        out.append((p[0], mnt, p[2]))
    return out


def mounts():
    """[{device, mount, fs, used, total, free}] — root first."""
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    res = []
    for dev, mnt, fs in parse_mounts(text):
        try:
            st = os.statvfs(mnt)
        except OSError:
            continue
        total = st.f_blocks * st.f_frsize
        if total < 50e6:
            continue
        free = st.f_bavail * st.f_frsize
        res.append(dict(device=dev, mount=mnt, fs=fs, total=total, free=free,
                        used=total - st.f_bfree * st.f_frsize))
    return sorted(res, key=lambda m: (m["mount"] != "/", m["mount"]))


def parse_du(text, home):
    """[(path, bytes)] from `du -x -b -d1`, largest first, without the total line for home itself."""
    out = []
    for line in text.splitlines():
        p = line.split("\t", 1)
        if len(p) == 2 and p[0].isdigit() and p[1] != home:
            out.append((p[1], int(p[0])))
    return sorted(out, key=lambda x: -x[1])


def biggest_folders(home=None, limit=10):
    home = home or os.path.expanduser("~")
    rc, out, _err = run(["du", "-x", "-b", "-d1", home], timeout=180)
    return parse_du(out, home)[:limit]


# ------------------------------------------------------------------ drive health (UDisks2)
def _variant(v):
    return v.unpack() if isinstance(v, GLib.Variant) else v


def drives():
    """[{model, size, kind, removable, smart: {...} | None}] from UDisks2 (no root)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        res = bus.call_sync("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2",
                            "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None, None,
                            Gio.DBusCallFlags.NONE, 5000, None)
    except GLib.Error:
        return []
    objs = res.unpack()[0]
    out = []
    for path, ifaces in objs.items():
        d = ifaces.get("org.freedesktop.UDisks2.Drive")
        if not d or not d.get("Size"):
            continue
        item = dict(path=path, model=(d.get("Vendor", "") + " " + d.get("Model", "")).strip() or "Disk",
                    size=int(d.get("Size", 0)), removable=bool(d.get("Removable")),
                    kind="ssd" if d.get("RotationRate", -1) == 0 else "hdd", smart=None)
        ata = ifaces.get("org.freedesktop.UDisks2.Drive.Ata")
        nvme = ifaces.get("org.freedesktop.UDisks2.NVMe.Controller")
        if nvme:
            item["kind"] = "nvme"
            warn = nvme.get("SmartCriticalWarning", [])
            sm = dict(ok=not warn, warnings=list(warn), hours=int(nvme.get("SmartPowerOnHours", 0)),
                      temp=_kelvin(nvme.get("SmartTemperature", 0)))
            try:
                attrs = bus.call_sync("org.freedesktop.UDisks2", path, "org.freedesktop.UDisks2.NVMe.Controller",
                                      "SmartGetAttributes", GLib.Variant("(a{sv})", ({},)), None,
                                      Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
                if "percent_used" in attrs:
                    sm["wear"] = int(attrs["percent_used"])
                if "avail_spare" in attrs:
                    sm["spare"] = int(attrs["avail_spare"])
            except GLib.Error:
                pass
            item["smart"] = sm
        elif ata and ata.get("SmartSupported"):
            sm = dict(ok=not ata.get("SmartFailing", False), warnings=[], hours=int(ata.get("SmartPowerOnSeconds", 0)) // 3600,
                      temp=_kelvin(ata.get("SmartTemperature", 0)), bad_sectors=int(ata.get("SmartNumBadSectors", 0)))
            if sm["bad_sectors"] > 0:
                sm["warnings"].append(f"{sm['bad_sectors']} bad sectors")
            item["smart"] = sm
        out.append(item)
    return sorted(out, key=lambda d: (d["removable"], d["model"]))


def _kelvin(k):
    try:
        k = float(k)
    except (TypeError, ValueError):
        return None
    return round(k - 273.15, 1) if k > 200 else None


# ------------------------------------------------------------------ battery
BAT_GLOB = "/sys/class/power_supply/BAT*"


def _rd(base, name, conv=str):
    try:
        with open(os.path.join(base, name), encoding="utf-8") as f:
            return conv(f.read().strip())
    except (OSError, ValueError):
        return None


def battery_path():
    paths = sorted(glob.glob(BAT_GLOB))
    return paths[0] if paths else None


def battery_info():
    """Details of the first battery, or None on a desktop."""
    b = battery_path()
    if not b:
        return None
    full = _rd(b, "energy_full", int) or _rd(b, "charge_full", int)
    design = _rd(b, "energy_full_design", int) or _rd(b, "charge_full_design", int)
    power = _rd(b, "power_now", int)
    if power is None:
        cur, volt = _rd(b, "current_now", int), _rd(b, "voltage_now", int)
        power = cur * volt // 1_000_000 if cur and volt else None
    return dict(name=os.path.basename(b), status=_rd(b, "status") or "", capacity=_rd(b, "capacity", int),
                health=round(100 * full / design) if full and design else None, cycles=_rd(b, "cycle_count", int),
                technology=_rd(b, "technology") or "", vendor=_rd(b, "manufacturer") or "",
                model=_rd(b, "model_name") or "", power_w=round(power / 1e6, 1) if power else None,
                full_wh=round(full / 1e6, 1) if full and _rd(b, "energy_full", int) else None,
                design_wh=round(design / 1e6, 1) if design and _rd(b, "energy_full_design", int) else None,
                limit=_rd(b, "charge_control_end_threshold", int),
                limit_supported=os.path.exists(os.path.join(b, "charge_control_end_threshold")),
                **charge_modes(b))


def parse_charge_types(text):
    """'[Fast] Standard Long_Life' -> ('Fast', ['Fast', 'Standard', 'Long_Life'])."""
    opts, cur = [], None
    for w in (text or "").split():
        if w.startswith("[") and w.endswith("]"):
            w = w[1:-1]
            cur = w
        opts.append(w)
    return cur, opts


def charge_modes(b):
    """Other charge-limit controls: the generic charge_types (kernel 6.x) and Lenovo IdeaPad/LOQ
    conservation mode (stops at about 80 %)."""
    cur, opts = parse_charge_types(_rd(b, "charge_types"))
    cons = sorted(glob.glob("/sys/bus/platform/drivers/ideapad_acpi/*/conservation_mode"))
    return dict(charge_type=cur, charge_types=[o for o in opts if o in ("Standard", "Long_Life", "Adaptive", "Fast")],
                conservation=_rd(os.path.dirname(cons[0]), "conservation_mode", int) if cons else None)


def power_profile():
    """(current, [available]) from power-profiles-daemon, or (None, [])."""
    if not have("powerprofilesctl"):
        return None, []
    rc, cur, _err = run(["powerprofilesctl", "get"], timeout=5)
    rc2, lst, _err = run(["powerprofilesctl", "list"], timeout=5)
    avail = [ln.strip().lstrip("* ").rstrip(":") for ln in lst.splitlines() if ln.strip().rstrip(":") and
             ln.rstrip().endswith(":")]
    return (cur.strip() or None), avail


def set_power_profile(name):
    """power-profiles-daemon lets the active user switch the profile without a password."""
    if name not in ("power-saver", "balanced", "performance"):
        return False
    return run(["powerprofilesctl", "set", name], timeout=10)[0] == 0


# ------------------------------------------------------------------ sensors
SENSOR_NAMES = {"acpi_fan": "Wentylator", "thinkpad_fan": "Wentylator", "coretemp": "Procesor (Intel)", "k10temp": "Procesor (AMD)", "zenpower": "Procesor (AMD)",
                "acpitz": "Płyta główna (ACPI)", "nvme": "Dysk NVMe", "amdgpu": "Karta graficzna (AMD)",
                "nouveau": "Karta graficzna (NVIDIA)", "i915": "Grafika Intel", "iwlwifi_1": "Wi-Fi",
                "thinkpad": "ThinkPad", "dell_smm": "Dell", "asus": "ASUS", "BAT0": "Bateria",
                "pch_cannonlake": "Chipset", "pch_cometlake": "Chipset", "pch_tigerlake": "Chipset",
                "spd5118": "Pamięć RAM", "jc42": "Pamięć RAM"}


def sensors(root="/sys/class/hwmon"):
    """[{chip, title, temps: [(label, °C, high, crit)], fans: [(label, rpm)]}]."""
    out = []
    for hw in sorted(glob.glob(os.path.join(root, "hwmon*"))):
        name = _rd(hw, "name") or os.path.basename(hw)
        temps, fans = [], []
        for t in sorted(glob.glob(os.path.join(hw, "temp*_input")), key=_natkey):
            base = t[:-len("_input")]
            v = _rd(hw, os.path.basename(t), int)
            if v is None or not (-40000 < v < 150000):
                continue
            lbl = _rd(hw, os.path.basename(base) + "_label") or os.path.basename(base).replace("temp", _("czujnik") + " ")
            hi = _rd(hw, os.path.basename(base) + "_max", int)
            cr = _rd(hw, os.path.basename(base) + "_crit", int)
            temps.append((lbl, v / 1000, hi / 1000 if hi and 0 < hi < 150000 else None,
                          cr / 1000 if cr and 0 < cr < 150000 else None))
        for fp in sorted(glob.glob(os.path.join(hw, "fan*_input")), key=_natkey):
            v = _rd(hw, os.path.basename(fp), int)
            if v is None:
                continue
            lbl = _rd(hw, os.path.basename(fp)[:-len("_input")] + "_label") or os.path.basename(fp)[:-len("_input")].replace("fan", _("wentylator") + " ")
            fans.append((lbl, v))
        if temps or fans:
            out.append(dict(chip=name, path=os.path.basename(hw), title=SENSOR_NAMES.get(name, name), temps=temps, fans=fans))
    return out


def _natkey(p):
    import re
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p)]


# ------------------------------------------------------------------ live load (for the Monitor charts)
def cpu_times():
    """(busy, total) jiffies from /proc/stat; the CPU % is the difference between two readings."""
    try:
        with open("/proc/stat", encoding="utf-8") as f:
            p = [int(x) for x in f.readline().split()[1:]]
    except (OSError, ValueError):
        return None
    idle = p[3] + (p[4] if len(p) > 4 else 0)
    total = sum(p[:8])
    return total - idle, total


def cpu_percent(prev, cur):
    if not prev or not cur or cur[1] <= prev[1]:
        return None
    return max(0.0, min(100.0, 100.0 * (cur[0] - prev[0]) / (cur[1] - prev[1])))


def memory():
    """(used_bytes, total_bytes, swap_used, swap_total) from /proc/meminfo."""
    info = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
    except (OSError, ValueError):
        return None
    total = info.get("MemTotal", 0)
    used = total - info.get("MemAvailable", 0)
    return used, total, info.get("SwapTotal", 0) - info.get("SwapFree", 0), info.get("SwapTotal", 0)


def loadavg():
    try:
        with open("/proc/loadavg", encoding="utf-8") as f:
            return tuple(float(x) for x in f.read().split()[:3])
    except (OSError, ValueError):
        return None
