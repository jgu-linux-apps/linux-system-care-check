"""Quick health readings for the Overview (no root): disk, battery, temperature and the health score."""
import glob
import os
import shutil


def disk_root():
    u = shutil.disk_usage("/")
    return u.used, u.total


def battery():
    """(health % of the design capacity, cycles) of the first battery, or None (desktop)."""
    for b in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        def rd(name):
            try:
                with open(os.path.join(b, name)) as f:
                    return int(f.read().strip())
            except (OSError, ValueError):
                return None
        full = rd("energy_full") or rd("charge_full")
        design = rd("energy_full_design") or rd("charge_full_design")
        cycles = rd("cycle_count")
        if full and design:
            return round(100 * full / design), cycles
    return None


def cpu_temp():
    """Highest CPU package/core temperature in °C from /sys/class/hwmon (no lm-sensors needed)."""
    best = None
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            with open(os.path.join(hw, "name")) as f:
                name = f.read().strip()
        except OSError:
            continue
        if name not in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
            continue
        for t in glob.glob(os.path.join(hw, "temp*_input")):
            try:
                with open(t) as f:
                    v = int(f.read().strip()) / 1000
                if 0 < v < 130:
                    best = v if best is None else max(best, v)
            except (OSError, ValueError):
                pass
    return best


def score(n_security, n_updates, disk_frac, cleanable, backup_age_days, timevault_installed):
    """0–100. Starts at 100 and loses points for things worth doing (see the Overview list)."""
    s = 100
    s -= min(30, 10 * n_security)
    s -= min(15, (n_updates - n_security) // 2)
    if disk_frac > 0.95:
        s -= 30
    elif disk_frac > 0.85:
        s -= 15
    if cleanable > 5e9:
        s -= 5
    if timevault_installed and (backup_age_days is None or backup_age_days > 7):
        s -= 10
    return max(0, min(100, s))
