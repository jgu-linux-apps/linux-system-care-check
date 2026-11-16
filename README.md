# Linux System Care Check

A system care center for Ubuntu with GNOME. One window shows updates, cleanup, installed programs (web apps
included), autostart, disk health, battery and temperatures, plus backups with **Linux Backup TimeVault**.
Background checks show notifications with buttons.

Part of the **JGu Linux Apps** series. Created by: JGu · Supported by Claude.

> **Safe by design.** Preview mode is on by default, so the app shows what it would do and changes nothing.
> Every change is listed in full and confirmed first. It only uses the system's own tools (apt, snap, flatpak,
> fwupd, journalctl) and never `purge`. Nothing runs on its own unless you switch it on in Settings.

## Features

| Page | What it does |
|---|---|
| **Overview** | Health score, what is worth doing now, disk / battery / temperature at a glance, recent actions |
| **Updates** | apt, snap, flatpak and firmware (fwupd) in one list; security updates marked; one-click update after confirmation |
| **Cleanup** | Only an allowlist of things the system re-creates: apt cache, journal logs (archive older than N days, or keep the last N weeks), disabled snap revisions, old kernels (the running kernel and one fallback are always kept), unused flatpak runtimes, thumbnails, Trash |
| **Programs** | Every installed program: apt, snap, flatpak, AppImage, Steam and **web apps** (Chrome, Chromium, Edge, Brave, Vivaldi, Opera, GNOME Web). Tick several and uninstall them together. System packages are protected, and apt removals are simulated first |
| **Autostart** | Turn session autostart entries on or off. Only your own copy in `~/.config/autostart` is written, never system files |
| **Disk** | Space per partition, drive health from SMART through UDisks2 (wear, hours, temperature), and the largest folders in your home |
| **Battery** | Health and cycles, plus a charge limit: the kernel `charge_control_end_threshold`, `charge_types` (Long_Life) or Lenovo conservation mode. The limit is re-applied at boot. Also the power profile |
| **Monitor** | Charts view or htop view (per-core meters, process table with F3/F6/F9). Live CPU and RAM charts, plus every hwmon sensor (CPU, NVMe, GPU, board) and fan with a sparkline, refreshed every 2 s |
| **Linux Backup TimeVault** | Backup state, "Back up now" and restore guidance. If TimeVault is missing, the app downloads the newest release from GitHub, checks it and installs it |
| **History and restore** | A log of every action, with undo for autostart and battery changes, the commands to reinstall removed programs, and the TimeVault backup taken before each change |

### Background checks and notifications

- `linux-system-care-check --background` starts with the session. It checks every 3, 6, 12 or 24 hours and has an optional tray icon.
- Notifications have buttons such as **Show** / **Later**. **Later** snoozes a notice for 24 h, or until something new appears. A button only opens the right page, where you confirm the change. **Back up now** starts a TimeVault backup.
- **Automatic actions only with your consent** (all off by default):
  - remove the thumbnail cache when it grows over 1 GB;
  - start a TimeVault backup when the last one is older than 7 days.
- Ubuntu and GNOME automatic features can be switched directly in Settings:
  - Ubuntu's own security updates (`unattended-upgrades`);
  - GNOME's removal of old Trash and temporary files.

### Look

The themes are System, Aurora, Studio (graphite + amber), Aubergine (aubergine + orange), Solid (flat, calm), Terminal (monospace, Ubuntu terminal aubergine) and Hologram (cyan neon HUD on smoked glass). Each has a light and a dark variant that follows the system. The app icon switches between light and dark with the system theme, even while the app is closed. Polish and English (follows the system language; `LSCC_LANG=en|pl` forces one).

## How changes are made

The window runs as your user. Changes that need root go through one small helper,
`/usr/lib/linux-system-care-check/care-helper`, started with `pkexec` under the polkit action
`io.github.jgu.LinuxSystemCareCheck.helper`. The helper accepts named operations only, never commands. It
validates every argument again, refuses protected packages and kernels, and simulates apt removals before
running them.

## Install

```bash
sudo apt install ./linux-system-care-check_0.4.9_all.deb
```

Recommended: `udisks2` (drive health), `power-profiles-daemon`, `gnome-shell-extension-appindicator` (tray
icon), `fwupd` (firmware updates) and Linux Backup TimeVault.

## Build

```bash
cd src && bash packaging/build-deb.sh
python3 -m unittest discover -s tests -v
```

## Version history

- **0.4.9** (2026-11-16): the tray icon no longer disappears after changing the language (the background
  process restarts in place); it also re-registers by itself if the tray host loses it.
- **0.4.8** (2026-11-16): normal-height title bars with a glass sheen; the app's name and menu sit fixed in
  the sidebar's bottom-left corner; more space between sidebar items and sections.
- **0.4.7** (2026-11-16): the app's logo and name sit in the sidebar's title bar, larger; both title bars
  are taller and level.
- **0.4.6** (2026-11-16): history entries (Overview "Recently" and History) follow the chosen language,
  also for entries saved earlier in the other language.
- **0.4.5** (2026-11-16): new Hologram theme (light and dark): cyan neon HUD, smoked-glass panels, a faint grid,
  equal top bars; charts and the htop view follow it.
- **0.4.4** (2026-11-15):
  - Overview: a "Top processes · htop" card above "Recent" shows the three processes using the most CPU, live. "Open htop" jumps to Monitor's htop view.
  - The htop view and the card follow light and dark mode: a light terminal palette in light mode, the aubergine terminal in dark mode.
  - Settings → Language · Język: Automatic, Polski or English. The app offers a restart; the tray icon switches language on its own.
- **0.4.3** (2026-11-15):
  - Overview: the Updates, Disk, Battery and Temperatures cards are clickable. They open Updates, Disk, Battery and Monitor.
  - Monitor's htop view shows a temperature line: CPU, NVMe, board and fans, coloured by how close each one is to its limit.
  - Terminal theme: the window buttons (minimize, maximize, close) and header-bar icon buttons have no frame.
- **0.4.2** (2026-11-14): full English user interface. It follows the system language; `LSCC_LANG=en` or `LSCC_LANG=pl` forces one. The sidebar shows the full name "Linux System Care Check" with a bigger icon. Tests check that every text has an English version.
- **0.4.1** (2026-11-14): the live icon (off / CPU / RAM / temperature / network, and graph or number) can be chosen straight from the tray menu. The F3/F6/F9 keys and the active sort in the htop view are readable (dark text on cyan).
- **0.4.0** (2026-11-14):
  - **htop view** on the Monitor page (Charts | htop):
    - per-core meters `[|||||   23%]`, Mem/Swap bars, tasks, load average, uptime and network speed;
    - a process table sortable by CPU%, MEM%, PID or TIME+, with search (F3), sort (F6) and end process (F9, SIGTERM). F9 works only on your own processes, after confirmation, and respects preview mode;
    - always drawn in Ubuntu terminal colours.
  - **Live tray icon**: CPU, RAM, CPU temperature or network ↓/↑, as a bar graph or a number, updated every 2 s. Details are in the tooltip.
  - **Terminal theme** now uses the Ubuntu terminal colours: aubergine `#300A24`, white text and inverse bars. The light variant is aubergine on white.
- **0.3.0** (2026-11-14):
  - Two new themes, each light and dark:
    - **Solid**: calm, flat, opaque, a single blue accent.
    - **Terminal**: monospace font everywhere, square corners, phosphor green on black or ink on paper, and page titles like `$ monitor`.
  - Charts:
    - the new **Monitor** page (replaces Temperatures) shows live CPU and RAM charts (last 5 minutes, load average, swap) and a sparkline for every temperature sensor and fan;
    - the Overview has a **Last 30 days** card with health score, disk use and pending updates. Points are recorded at most once an hour, both from the background checks and from the app.
  - The Linux Backup TimeVault page no longer shows the TimeVault version.
  - Disabled buttons are dimmed in every theme. Pages are rebuilt after a theme change.
- **0.2.5** (2026-11-14):
  - The dark app icon now switches like in the other apps of the series: the icon is overridden by name in `~/.local/share/icons` (the `.desktop` override is no longer used).
  - Log archives always stay on disk.
  - New option: move archives older than N days (30–365) to the Trash, by button or automatically with consent.
- **0.2.4** (2026-11-14): fixes the single-instance check of the icon-sync and background helpers (two copies could run at once because the D-Bus name was released too early).
- **0.2.3** (2026-11-14): fixed uneven text across the whole app (some letters at 65 % opacity, without antialiasing). The cause was the progress ring drawing its numbers with the widgets' shared Pango layout through PangoCairo. The numbers are now ordinary labels on top of the ring. The Renderer setting stays for troubleshooting: Automatic keeps the GTK default, and GL, Vulkan or Cairo can be forced.
- **0.2.2** (2026-11-14):
  - Update a single item: each update row has its own Update button. apt upgrades only that package, after a simulation that guarantees nothing is removed.
  - Cleanup → System logs:
    - archive the logs older than N days (1–90) to `Documents/System logs archive/*.txt.xz` and remove them;
    - or remove logs and keep only the last 1–8 weeks (sliders).
  - Linux Backup TimeVault: the disk is detected live from its partition labels (the status file can be hours old). "Back up now" is disabled while the disk is unplugged.
  - Battery health above 100 % is shown as 100 % with a note that the battery is new.
  - Tray menu: Close.
  - Renderer setting; the forced font rendering from 0.2.1 is removed.
- **0.2.1** (2026-11-14): preview mode switch in the window header bar (the banner button turns preview off directly, after one confirmation); opaque theme cards.
- **0.2.0** (2026-11-14):
  - New pages: Disk (partitions, SMART health, largest folders), Battery (health, charge limit kept across reboots, power profile), Temperatures and Autostart.
  - Background checks with notifications that carry action buttons, and a tray icon.
  - Automatic actions only with consent.
  - Switches for Ubuntu automatic security updates and GNOME old-file cleanup.
  - Undo in History for autostart and battery changes.
  - Grouped sidebar; brighter status chips in dark mode.
  - SHA256SUMS in releases.
- **0.1.0** (2026-11-14, not released on its own): first version.
  - Overview, Updates, Cleanup, Programs with web apps and multi-select uninstall, Linux Backup TimeVault integration (including download and install), and History.
  - Root helper behind polkit, and preview mode on by default.
  - Four themes, each light and dark.

## License

Freeware License (No Modifications) — see [LICENSE](LICENSE).
