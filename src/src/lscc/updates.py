"""Available updates from apt, snap, flatpak and firmware (fwupd) — read only, no root.

apt shows what its package lists know; refreshing the lists (`apt update`) needs root and goes through the
helper. Snaps also refresh by themselves (snapd); Ubuntu installs apt security updates by itself through
unattended-upgrades — this module only reports, it never installs."""
import json
import re
from dataclasses import dataclass, field

from .sysrun import have, parse_size, run


@dataclass
class Update:
    name: str
    old: str
    new: str
    source: str            # apt | snap | flatpak | firmware
    security: bool = False
    note: str = ""
    size: int = 0
    extra: dict = field(default_factory=dict)


APT_RE = re.compile(r"^(?P<name>[^/\s]+)/(?P<suite>\S+)\s+(?P<new>\S+)\s+(?P<arch>\S+)\s+\[upgradable from: (?P<old>[^\]]+)\]")


def parse_apt(text):
    out = []
    for line in text.splitlines():
        m = APT_RE.match(line.strip())
        if m:
            suite = m["suite"]
            out.append(Update(m["name"], m["old"], m["new"], "apt", security="-security" in suite,
                              note=suite))
    return out


def parse_snap(text):
    """`snap refresh --list`: Name Version Rev Size Publisher Notes (old version from `snap list`)."""
    out = []
    lines = text.splitlines()
    for line in lines[1:] if lines and lines[0].startswith("Name") else []:
        parts = line.split()
        if len(parts) >= 4:
            out.append(Update(parts[0], "", parts[1], "snap", size=parse_size(parts[3]),
                              note=" ".join(parts[5:]) if len(parts) > 5 else ""))
    return out


def parse_flatpak(text):
    """`flatpak remote-ls --updates --columns=application,version,origin` (tab separated)."""
    out = []
    for line in text.splitlines():
        parts = line.split("\t")
        if parts and parts[0] and "." in parts[0]:
            out.append(Update(parts[0], "", parts[1] if len(parts) > 1 else "", "flatpak",
                              note=parts[2] if len(parts) > 2 else ""))
    return out


def parse_fwupd(text):
    """`fwupdmgr get-updates --json`: devices with releases newer than the installed firmware."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return []
    out = []
    for dev in data.get("Devices", []):
        rels = dev.get("Releases") or []
        if not rels:
            continue
        rel = rels[0]
        out.append(Update(dev.get("Name", "?"), dev.get("Version", ""), rel.get("Version", ""), "firmware",
                          security="security" in json.dumps(rel.get("Flags", [])).lower(),
                          note=(rel.get("Summary") or "").strip(), size=int(rel.get("Size") or 0),
                          extra={"device_id": dev.get("DeviceId", "")}))
    return out


def snap_installed_versions():
    rc, out, _ = run(["snap", "list"], timeout=30)
    vers = {}
    for line in out.splitlines()[1:]:
        p = line.split()
        if len(p) >= 2:
            vers[p[0]] = p[1]
    return vers


def check_all():
    """All updates; sources whose tool is missing are skipped. Returns (updates, errors)."""
    ups, errors = [], {}
    rc, out, err = run(["apt", "list", "--upgradable"], timeout=60)
    if rc == 0:
        ups += parse_apt(out)
    elif rc != 127:
        errors["apt"] = err.strip()
    if have("snap"):
        rc, out, err = run(["snap", "refresh", "--list"], timeout=60)
        if rc == 0:
            snaps = parse_snap(out)
            vers = snap_installed_versions()
            for u in snaps:
                u.old = vers.get(u.name, "")
            ups += snaps
        elif "All snaps up to date" not in (out + err):
            errors["snap"] = err.strip()
    if have("flatpak"):
        rc, out, err = run(["flatpak", "remote-ls", "--updates", "--columns=application,version,origin"], timeout=60)
        if rc == 0:
            ups += parse_flatpak(out)
        else:
            errors["flatpak"] = err.strip()
    if have("fwupdmgr"):
        rc, out, err = run(["fwupdmgr", "get-updates", "--json"], timeout=60)
        if out.strip().startswith("{"):
            ups += parse_fwupd(out)
    return ups, errors


def unattended_status():
    """Ubuntu's own automatic security updates (unattended-upgrades): (installed, enabled)."""
    import os
    installed = os.path.exists("/usr/bin/unattended-upgrade")
    enabled = False
    try:
        with open("/etc/apt/apt.conf.d/20auto-upgrades", encoding="utf-8") as f:
            enabled = bool(re.search(r'Unattended-Upgrade\s+"1"', f.read()))
    except OSError:
        pass
    return installed, enabled


def reboot_required():
    import os
    return os.path.exists("/var/run/reboot-required")
