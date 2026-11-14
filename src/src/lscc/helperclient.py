"""Calls the root helper through pkexec. In preview mode nothing is called: the command is only described."""
import subprocess

from . import HELPER


def run(op, *args, preview=True, timeout=3 * 3600):
    """(ok, output). preview=True → returns the command it would run, without running anything."""
    cmd = ["pkexec", HELPER, op, *args]
    if preview:
        return True, "PREVIEW: " + " ".join(cmd[1:])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if p.returncode in (126, 127) and not p.stdout:
        return False, "cancelled" if p.returncode == 126 else (p.stderr.strip() or "helper missing")
    return p.returncode == 0, (p.stdout + p.stderr).strip()
