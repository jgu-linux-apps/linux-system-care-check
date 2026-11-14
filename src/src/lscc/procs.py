"""Live system sampling for the htop-style view and the live tray icon (read only, from /proc).

Sampler.sample() returns per-core CPU %, memory, swap, load, uptime, task counts, network speed and the
process list with CPU % (htop semantics: 100 % = one full core). Call it every ~2 s; the first call has no
CPU % yet (it needs two readings)."""
import os
import pwd
import time

CLK = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")
NCPU = os.cpu_count() or 1


def read_cpus(text=None):
    """{"cpu": (busy, total), "cpu0": (...), ...} from /proc/stat."""
    if text is None:
        with open("/proc/stat", encoding="utf-8") as f:
            text = f.read()
    out = {}
    for line in text.splitlines():
        if not line.startswith("cpu"):
            continue
        p = line.split()
        v = [int(x) for x in p[1:9]]
        idle = v[3] + v[4]
        out[p[0]] = (sum(v) - idle, sum(v))
    return out


def parse_net(text):
    """(rx_bytes, tx_bytes) summed over real interfaces (not lo, not virtual bridges/docker/veth)."""
    rx = tx = 0
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        name = name.strip()
        if name == "lo" or name.startswith(("veth", "docker", "br-", "virbr", "vnet")):
            continue
        f = data.split()
        if len(f) >= 9:
            rx += int(f[0])
            tx += int(f[8])
    return rx, tx


def parse_proc_stat(text):
    """(state, utime+stime, starttime) from /proc/<pid>/stat (the command may contain spaces and ')')."""
    r = text.rfind(")")
    f = text[r + 2:].split()
    return f[0], int(f[11]) + int(f[12]), int(f[19])


def fmt_time(jiffies):
    """htop TIME+ like 1:23.45 or 12h05:00."""
    s = jiffies / CLK
    if s >= 3600:
        return f"{int(s // 3600)}h{int(s % 3600 // 60):02d}:{int(s % 60):02d}"
    return f"{int(s // 60)}:{s % 60:05.2f}"


class Sampler:
    def __init__(self):
        self.prev_cpu = {}
        self.prev_proc = {}
        self.prev_net = None
        self.prev_t = None
        self.users = {}

    def _user(self, uid):
        if uid not in self.users:
            try:
                self.users[uid] = pwd.getpwuid(uid).pw_name
            except KeyError:
                self.users[uid] = str(uid)
        return self.users[uid]

    def sample(self, with_procs=True):
        now = time.monotonic()
        cpus = read_cpus()
        cores = {}
        for k, (busy, total) in cpus.items():
            pb, pt = self.prev_cpu.get(k, (None, None))
            cores[k] = (100.0 * (busy - pb) / (total - pt)) if pb is not None and total > pt else None
        d_total = (cpus["cpu"][1] - self.prev_cpu["cpu"][1]) / NCPU if "cpu" in self.prev_cpu else 0
        self.prev_cpu = cpus

        mem = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                mem[k] = int(v.split()[0]) * 1024
        with open("/proc/loadavg", encoding="utf-8") as f:
            la = f.read().split()
        with open("/proc/uptime", encoding="utf-8") as f:
            uptime = float(f.read().split()[0])
        with open("/proc/net/dev", encoding="utf-8") as f:
            net = parse_net(f.read())
        rx_s = tx_s = None
        if self.prev_net and self.prev_t and now > self.prev_t:
            dt = now - self.prev_t
            rx_s = max(0, net[0] - self.prev_net[0]) / dt
            tx_s = max(0, net[1] - self.prev_net[1]) / dt
        self.prev_net, self.prev_t = net, now

        procs, running = [], 0
        if with_procs:
            cur = {}
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as f:
                        state, cpu_j, start = parse_proc_stat(f.read())
                    with open(f"/proc/{pid}/statm", encoding="utf-8") as f:
                        rss = int(f.read().split()[1]) * PAGE
                    uid = os.stat(f"/proc/{pid}").st_uid
                    with open(f"/proc/{pid}/comm", encoding="utf-8", errors="replace") as f:
                        comm = f.read().strip()
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        cmd = f.read(400).replace(b"\0", b" ").decode("utf-8", "replace").strip()
                except (OSError, ValueError, IndexError):
                    continue
                if state == "R":
                    running += 1
                key = (int(pid), start)
                cur[key] = cpu_j
                prev = self.prev_proc.get(key)
                pct = (100.0 * (cpu_j - prev) / d_total) if prev is not None and d_total > 0 else 0.0
                procs.append(dict(pid=int(pid), user=self._user(uid), uid=uid, state=state, cpu=pct,
                                  mem=100.0 * rss / mem["MemTotal"], rss=rss, time=cpu_j,
                                  cmd=cmd or f"[{comm}]", comm=comm))
            self.prev_proc = cur
        return dict(cores=[cores[f"cpu{i}"] for i in range(NCPU) if f"cpu{i}" in cores], cpu=cores.get("cpu"),
                    mem_total=mem["MemTotal"], mem_used=mem["MemTotal"] - mem["MemAvailable"],
                    mem_cache=mem.get("Buffers", 0) + mem.get("Cached", 0),
                    swap_total=mem["SwapTotal"], swap_used=mem["SwapTotal"] - mem["SwapFree"],
                    load=tuple(float(x) for x in la[:3]), tasks=la[3].split("/")[1] if "/" in la[3] else "",
                    uptime=uptime, rx=rx_s, tx=tx_s, procs=procs, running=running)


def human_rate(bps):
    if bps is None:
        return "—"
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1000:
            return f"{bps:.0f} {unit}" if unit == "B/s" else f"{bps:.1f} {unit}"
        bps /= 1000
    return f"{bps:.1f} TB/s"
