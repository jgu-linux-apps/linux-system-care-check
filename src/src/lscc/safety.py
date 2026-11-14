"""Safety rules shared by the UI and the root helper (pure functions, unit-tested).

The helper never trusts its arguments: every name it gets is checked here against what the system
itself reports. Cleanup only works from an allowlist of re-creatable items, packages are removed with
`remove` (never `purge`), and a list of packages the desktop needs can never be removed."""
import re

# Packages without which Ubuntu with GNOME would not boot, log in or update. Never removable.
PROTECTED_EXACT = {
    "ubuntu-desktop", "ubuntu-desktop-minimal", "ubuntu-minimal", "ubuntu-standard", "ubuntu-session",
    "gnome-shell", "gnome-session", "gdm3", "mutter", "gnome-control-center", "gnome-settings-daemon",
    "nautilus", "gnome-terminal", "ptyxis", "xdg-desktop-portal", "xdg-desktop-portal-gnome",
    "apt", "dpkg", "sudo", "polkitd", "pkexec", "policykit-1", "systemd", "systemd-sysv", "udev",
    "init", "login", "passwd", "bash", "dash", "coreutils", "util-linux", "base-files", "libc6",
    "network-manager", "netplan.io", "wpasupplicant", "grub-efi-amd64-signed", "shim-signed", "grub-common",
    "linux-generic", "linux-generic-hwe-24.04", "linux-image-generic", "linux-firmware",
    "snapd", "flatpak", "pipewire", "wireplumber", "python3", "dbus", "openssh-client",
    "linux-system-care-check", "timevault",
}
PROTECTED_PREFIX = ("linux-image-generic", "linux-generic", "linux-headers-generic", "grub-", "shim-",
                    "systemd", "libsystemd", "python3.")
# Snaps the desktop depends on (bases, platform snaps, the snap store itself).
PROTECTED_SNAPS = {"snapd", "core", "core18", "core20", "core22", "core24", "core26", "bare",
                   "gnome-42-2204", "gnome-46-2404", "gtk-common-themes", "snapd-desktop-integration",
                   "firmware-updater", "desktop-security-center", "prompting-client"}

PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-]{0,100}$")
SNAP_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,40}$")
REV_RE = re.compile(r"^x?[0-9]{1,8}$")
FLATPAK_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*(\.[A-Za-z0-9_\-]+){2,}$")
KVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-[0-9]+(-[a-z0-9]+)?$")


def is_protected_pkg(name):
    return name in PROTECTED_EXACT or name.startswith(PROTECTED_PREFIX)


def valid_pkg(name):
    return bool(PKG_RE.match(name or ""))


def valid_snap(name):
    return bool(SNAP_RE.match(name or ""))


def valid_rev(rev):
    return bool(REV_RE.match(str(rev or "")))


def valid_flatpak(app_id):
    return bool(FLATPAK_RE.match(app_id or ""))


def _kver_key(v):
    """Sort key for kernel versions like 7.3.0-10-generic (numeric parts compared as numbers)."""
    return [int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v)]


def removable_kernels(installed, running):
    """Kernels that may go: every installed one except the running kernel and the newest other one.

    installed: versions like "7.3.0-9-generic" (from installed linux-image-* packages)
    running: `uname -r`. If the running kernel is not in the list (unusual), nothing is removable."""
    vers = sorted(set(installed), key=_kver_key)
    if running not in vers:
        return []
    others = [v for v in vers if v != running]
    keep = {running}
    if others:
        keep.add(others[-1])          # the newest other kernel stays as a fallback
    return [v for v in vers if v not in keep]


def check_apt_simulation(selected, sim_removed):
    """Decide whether an apt removal is safe, from `apt-get -s remove` output.

    selected: packages the user ticked. sim_removed: packages apt says it would remove.
    Returns (ok, reason, extra): extra = packages beyond the selection that would also go."""
    selected, removed = set(selected), set(sim_removed)
    bad = sorted(p for p in removed if is_protected_pkg(p))
    if bad:
        return False, "protected", bad
    extra = sorted(removed - selected)
    return True, "", extra


def parse_apt_sim_removed(text):
    """Package names from `LC_ALL=C apt-get -s remove …` lines "Remv name [version]"."""
    out = []
    for line in text.splitlines():
        if line.startswith("Remv "):
            parts = line.split()
            if len(parts) >= 2:
                out.append(parts[1].split(":")[0])
    return out


# The cleanup allowlist: id → what it is. Anything not here cannot be cleaned.
CLEAN_SYSTEM = ("apt-cache", "journal", "snap-disabled", "old-kernels", "flatpak-unused")
CLEAN_USER = ("thumbnails", "trash")
