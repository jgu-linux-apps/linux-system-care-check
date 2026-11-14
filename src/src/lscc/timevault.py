"""Integration with Linux Backup TimeVault (the same author, JGu Linux Apps series).

Reads its state without root from /var/lib/timevault/status.json (TimeVault writes it for its own window,
without secrets), starts a backup with the same systemd unit as TimeVault's "Back up now" button, and —
when TimeVault is not installed — downloads the newest .deb from GitHub Releases and checks it before the
root helper installs it. A full system restore is always done by TimeVault itself (its Recovery system)."""
import json
import os
import shutil
import subprocess
import time
import urllib.request

from .sysrun import run

STATUS = "/var/lib/timevault/status.json"
REPO_API = "https://api.github.com/repos/jgu-linux-apps/linux-backup-timevault/releases/latest"
PAGE = "https://github.com/jgu-linux-apps/linux-backup-timevault"
DOWNLOAD_HOSTS = ("https://github.com/jgu-linux-apps/linux-backup-timevault/releases/download/",)
CACHE = os.path.join(os.path.expanduser("~/.cache"), "linux-system-care-check")


def installed():
    return shutil.which("timevault") is not None or os.path.isdir("/usr/share/timevault")


def version():
    rc, out, _err = run(["dpkg-query", "-W", "-f=${Version}", "timevault"], timeout=10)
    return out.strip() if rc == 0 else ""


def status():
    """TimeVault state for the UI; {} when unknown."""
    try:
        with open(STATUS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


TV_PARTLABELS = ("TM-EFI", "TM-RECOVERY-A", "TM-RECOVERY-B", "TM-DATA")
TV_FSLABELS = ("TM-EFI", "TM-RECOVA", "TM-RECOVB", "TM-DATA")


def disk_connected(st=None):
    """Is the TimeVault disk plugged in right now? Checked live, the same way TimeVault's own window does
    (udev links of its partition labels). status.json is updated only when a backup runs, so its
    disk_connected field can be hours old — it is not used for this."""
    for base, names in (("/dev/disk/by-partlabel", TV_PARTLABELS), ("/dev/disk/by-label", TV_FSLABELS)):
        for n in names:
            if os.path.exists(os.path.join(base, n)):
                return True
    return False


def last_backup_age_days(st=None):
    st = st if st is not None else status()
    ts = st.get("last_success")
    if not ts:
        return None
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 86400
    except ValueError:
        return None


def start_backup():
    """The same unit as TimeVault's own "Back up now" button (its polkit rule allows the active user)."""
    p = subprocess.run(["systemctl", "start", "--no-block", "timevault-backup-now.service"],
                       capture_output=True, text=True, timeout=30)
    return p.returncode == 0, p.stderr.strip()


def wait_backup(timeout=3 * 3600, poll=5, on_progress=None):
    """Wait until TimeVault reports the backup finished; returns (ok, message)."""
    start = time.time()
    seen_running = False
    while time.time() - start < timeout:
        st = status()
        state = st.get("state", "")
        if on_progress:
            on_progress(st)
        if state == "running":
            seen_running = True
        elif seen_running and state in ("idle", "disk-absent"):
            return True, st.get("last_success", "")
        elif seen_running and state == "error":
            return False, st.get("error", "")
        elif not seen_running and time.time() - start > 120:
            return False, "TimeVault did not start the backup"
        time.sleep(poll)
    return False, "timeout"


def open_app():
    subprocess.Popen(["timevault-gui"] if shutil.which("timevault-gui") else ["gtk-launch", "timevault"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


# ------------------------------------------------------------------ install the newest TimeVault
def latest_release():
    """(tag, asset name, download url, size) of the newest TimeVault release."""
    req = urllib.request.Request(REPO_API, headers={"Accept": "application/vnd.github+json",
                                                    "User-Agent": "linux-system-care-check"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    tag = data.get("tag_name", "")
    for a in data.get("assets", []):
        name = a.get("name", "")
        if name.startswith("timevault_") and name.endswith("_all.deb"):
            return tag, name, a.get("browser_download_url", ""), int(a.get("size") or 0)
    raise RuntimeError("no .deb in the latest TimeVault release")


def download(url, name, on_progress=None):
    if not url.startswith(DOWNLOAD_HOSTS) or "/" in name or not name.endswith(".deb"):
        raise ValueError("unexpected download address")
    os.makedirs(CACHE, exist_ok=True)
    dest = os.path.join(CACHE, name)
    req = urllib.request.Request(url, headers={"User-Agent": "linux-system-care-check"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if on_progress and total:
                on_progress(got / total)
    os.replace(dest + ".part", dest)
    return dest


def verify_deb(path, tag):
    """The package must be TimeVault, in the version of the release tag. Returns (ok, reason)."""
    rc, out, _err = run(["dpkg-deb", "-f", path, "Package", "Version", "Maintainer"], timeout=20)
    if rc != 0:
        return False, "not a valid .deb package"
    f = {}
    for line in out.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            f[k] = v.strip()
    if f.get("Package") != "timevault":
        return False, f"package name is {f.get('Package')!r}, expected 'timevault'"
    if "v" + f.get("Version", "") != tag:
        return False, f"version {f.get('Version')} does not match the release {tag}"
    if not any(n in f.get("Maintainer", "") for n in ("JGu", "Jaro")):
        return False, "unexpected maintainer"
    return True, ""
