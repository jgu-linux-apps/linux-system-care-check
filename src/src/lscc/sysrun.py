"""Running system tools for reading (no root): always with LC_ALL=C so the output can be parsed."""
import os
import shutil
import subprocess

ENV = dict(os.environ, LC_ALL="C", LANG="C", LANGUAGE="C")


def have(cmd):
    return shutil.which(cmd) is not None


def run(args, timeout=60):
    """(returncode, stdout, stderr); a missing tool or a timeout gives returncode 127 / 124."""
    if not have(args[0]):
        return 127, "", f"{args[0]}: not installed"
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=ENV)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as e:
        return 126, "", str(e)


def dir_size(path):
    """Bytes used by a directory tree (files only, symlinks not followed); 0 if missing."""
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                st = os.lstat(os.path.join(root, f))
                if not os.path.islink(os.path.join(root, f)):
                    total += st.st_blocks * 512 if hasattr(st, "st_blocks") else st.st_size
            except OSError:
                pass
    return total


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            if unit in ("B", "KB"):
                return f"{n:.0f} {unit}"
            return f"{n:.1f} {unit}".replace(".0 ", " ")
        n /= 1000.0
    return f"{n:.1f} TB"


def parse_size(text):
    """'58.2MB' / '1.2 GB' / '361,0 MB' → bytes (decimal units, as snap and flatpak print them)."""
    t = (text or "").strip().replace(",", ".").replace(" ", "")
    mult = {"B": 1, "kB": 1e3, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}
    for suf in ("TB", "GB", "MB", "kB", "KB", "B"):
        if t.endswith(suf):
            try:
                return int(float(t[:-len(suf)]) * mult[suf])
            except ValueError:
                return 0
    try:
        return int(float(t))
    except ValueError:
        return 0
