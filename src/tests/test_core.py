"""Unit tests for the parts that decide what may be changed (safety, parsers, classification)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lscc import autostart, background, cleanup, hw, logarchive, metrics, procs, programs, safety, updates  # noqa: E402


class Safety(unittest.TestCase):
    def test_protected(self):
        for p in ("ubuntu-desktop", "gnome-shell", "sudo", "linux-generic", "grub-efi-amd64", "systemd-resolved",
                  "python3.13", "timevault", "linux-system-care-check"):
            self.assertTrue(safety.is_protected_pkg(p), p)
        for p in ("gimp", "vlc", "audacity"):
            self.assertFalse(safety.is_protected_pkg(p), p)

    def test_kernels_keep_running_and_newest_other(self):
        inst = ["7.3.0-8-generic", "7.3.0-9-generic", "7.3.0-10-generic", "7.2.0-5-generic"]
        self.assertEqual(safety.removable_kernels(inst, "7.3.0-10-generic"), ["7.2.0-5-generic", "7.3.0-8-generic"])
        # running an older kernel: the newest (10) is kept as the "other", 9 goes
        self.assertEqual(safety.removable_kernels(inst, "7.3.0-8-generic"), ["7.2.0-5-generic", "7.3.0-9-generic"])
        self.assertEqual(safety.removable_kernels(inst, "9.9.9-1-generic"), [])
        self.assertEqual(safety.removable_kernels(["7.3.0-10-generic", "7.3.0-9-generic"], "7.3.0-10-generic"), [])

    def test_apt_simulation(self):
        sim = safety.parse_apt_sim_removed("Remv gimp [3.0]\nRemv gimp-data [3.0]\nInst x\n")
        self.assertEqual(sim, ["gimp", "gimp-data"])
        self.assertEqual(safety.check_apt_simulation(["gimp"], sim), (True, "", ["gimp-data"]))
        ok, reason, bad = safety.check_apt_simulation(["foo"], ["foo", "ubuntu-desktop"])
        self.assertFalse(ok)
        self.assertEqual(bad, ["ubuntu-desktop"])

    def test_validators(self):
        self.assertTrue(safety.valid_pkg("libreoffice-calc"))
        self.assertFalse(safety.valid_pkg("rm -rf /"))
        self.assertFalse(safety.valid_pkg("--purge"))
        self.assertTrue(safety.valid_flatpak("org.gimp.GIMP"))
        self.assertFalse(safety.valid_flatpak("../../etc"))


class Parsers(unittest.TestCase):
    def test_apt(self):
        u = updates.parse_apt("Listing...\nfirefox/questing-security 140.1 amd64 [upgradable from: 140.0]\n"
                              "gimp/questing-updates 3.0.4 amd64 [upgradable from: 3.0.2]")
        self.assertEqual([(x.name, x.security) for x in u], [("firefox", True), ("gimp", False)])

    def test_snap_disabled(self):
        t = "Name Version Rev Tracking Publisher Notes\ncore22 2024 1908 latest/stable canonical✓ base,disabled\n" \
            "core22 2024 2045 latest/stable canonical✓ base\n"
        self.assertEqual(cleanup.parse_snap_disabled(t), [("core22", "1908")])

    def test_kernels(self):
        t = "linux-image-7.3.0-9-generic install ok installed 15000\nlinux-image-generic install ok installed 10\n"
        self.assertEqual(cleanup.parse_kernels(t), {"7.3.0-9-generic": 15000 * 1024})

    def test_mounts_and_du(self):
        m = hw.parse_mounts("/dev/nvme0n1p5 / ext4 rw 0 0\n/dev/loop1 /snap/core22/1 squashfs ro 0 0\n"
                            "tmpfs /run tmpfs rw 0 0\n/dev/sda1 /media/x\\040y exfat rw 0 0\n")
        self.assertEqual(m, [("/dev/nvme0n1p5", "/", "ext4"), ("/dev/sda1", "/media/x y", "exfat")])
        self.assertEqual(hw.parse_du("10\t/h/a\n30\t/h/b\n40\t/h\n", "/h"), [("/h/b", 30), ("/h/a", 10)])

    def test_charge_types(self):
        self.assertEqual(hw.parse_charge_types("[Fast] Standard Long_Life"), ("Fast", ["Fast", "Standard", "Long_Life"]))
        self.assertEqual(hw.parse_charge_types(None), (None, []))


class Programs(unittest.TestCase):
    def test_webapp(self):
        self.assertEqual(programs.classify_webapp("chrome-abc-Default.desktop",
                                                  {"Exec": "/opt/google/chrome/google-chrome --app-id=abc"}),
                         (True, "Chrome"))
        self.assertEqual(programs.classify_webapp("org.gnome.Epiphany.WebApp_x.desktop", {}), (True, "GNOME Web"))
        self.assertEqual(programs.classify_webapp("gimp.desktop", {"Exec": "gimp %U"}), (False, ""))

    def test_remove_webapp_refuses_outside_user_dir(self):
        with self.assertRaises(ValueError):
            programs.remove_webapp("/usr/share/applications/firefox.desktop")


class Autostart(unittest.TestCase):
    def test_toggle_writes_user_copy_only(self):
        with tempfile.TemporaryDirectory() as d:
            sysd, usr = os.path.join(d, "sys"), os.path.join(d, "usr")
            os.makedirs(sysd)
            with open(os.path.join(sysd, "a.desktop"), "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=A\nExec=a\n")
            e = autostart.entries("en", [sysd], usr)[0]
            self.assertTrue(e["enabled"])
            autostart.set_enabled(e, False, usr)
            e = autostart.entries("en", [sysd], usr)[0]
            self.assertFalse(e["enabled"])
            with open(os.path.join(sysd, "a.desktop")) as f:
                self.assertNotIn("enabled", f.read())          # system file untouched
            autostart.set_enabled(e, True, usr)                  # back on: our override is removed
            self.assertFalse(os.path.exists(os.path.join(usr, "a.desktop")))
            self.assertTrue(autostart.entries("en", [sysd], usr)[0]["enabled"])

    def test_rejects_paths(self):
        with self.assertRaises(ValueError):
            autostart.set_enabled({"file": "../x.desktop"}, False, "/tmp/nowhere")


class LogArchive(unittest.TestCase):
    def test_older_than(self):
        with tempfile.TemporaryDirectory() as d:
            for name, age in (("journal-until-2026-01-01.txt.xz", 40), ("journal-until-2026-10-01.txt.xz", 5),
                              ("other.txt", 400)):
                p = os.path.join(d, name)
                open(p, "w").close()
                t = 1_800_000_000 - age * 86400
                os.utime(p, (t, t))
            old = logarchive.older_than(30, d, now=1_800_000_000)
            self.assertEqual([os.path.basename(p) for p, _m, _s in old], ["journal-until-2026-01-01.txt.xz"])


class Metrics(unittest.TestCase):
    def test_hourly_and_daily(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.jsonl")
            t = 1_800_000_000
            self.assertTrue(metrics.record(90, 25, 3, 0, path=p, now=t))
            self.assertFalse(metrics.record(80, 25, 3, 0, path=p, now=t + 600))       # < 1 h: skipped
            self.assertTrue(metrics.record(80, 26, 4, 0, path=p, now=t + 4000))
            self.assertTrue(metrics.record(70, 27, 5, 0, path=p, now=t + 2 * 86400))
            pts = metrics.load(30, path=p, now=t + 2 * 86400)
            self.assertEqual(len(pts), 3)
            self.assertEqual([x["score"] for x in metrics.daily(pts)], [80, 70])

    def test_cpu_percent(self):
        self.assertEqual(hw.cpu_percent((50, 100), (100, 200)), 50.0)
        self.assertIsNone(hw.cpu_percent(None, (1, 2)))


class Procs(unittest.TestCase):
    def test_parsers(self):
        net = "Inter-|\n face |\n    lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0\n wlp2s0: 5000 9 0 0 0 0 0 0 700 3 0 0 0 0 0 0\n" \
              " docker0: 10 1 0 0 0 0 0 0 10 1 0 0 0 0 0 0\n"
        self.assertEqual(procs.parse_net(net), (5000, 700))
        st = "1234 (Web Content (x)) S 1 2 3 4 5 6 7 8 9 10 150 50 0 0 20 0 1 0 9999 0 0"
        self.assertEqual(procs.parse_proc_stat(st), ("S", 200, 9999))
        cpus = procs.read_cpus("cpu  10 0 10 80 0 0 0 0 0 0\ncpu0 5 0 5 40 0 0 0 0 0 0\nintr 1\n")
        self.assertEqual(cpus["cpu"], (20, 100))
        self.assertEqual(procs.human_rate(1500), "1.5 KB/s")


class I18n(unittest.TestCase):
    def test_no_module_shadows_translate(self):
        """A local variable named _ (e.g. `rc, out, _ = run(...)`) hides the _() translation function and
        breaks the texts of that function (0.4.2 regression in Cleanup)."""
        import ast
        import glob
        root = os.path.join(os.path.dirname(__file__), "..", "src", "lscc")
        bad = []
        for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
            for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
                if isinstance(n, ast.Name) and n.id == "_" and isinstance(n.ctx, ast.Store):
                    bad.append(f"{os.path.basename(f)}:{n.lineno}")
        self.assertEqual(bad, [])

    def test_every_text_has_english(self):
        import ast
        import glob
        from lscc.i18n_en import EN
        root = os.path.join(os.path.dirname(__file__), "..", "src", "lscc")
        missing = set()
        for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
            for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
                if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_" and n.args
                        and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                    if n.args[0].value not in EN:
                        missing.add(n.args[0].value)
        self.assertEqual(sorted(missing), [])


class Background(unittest.TestCase):
    def test_findings_and_snooze(self):
        u = updates.Update("openssl", "1", "2", "apt", security=True)
        fs = background.findings([u], [], (90, 100), True, 10, True, [], None)
        tags = [f[0] for f in fs]
        self.assertEqual(tags, ["security", "backup"])
        self.assertEqual(fs[0][3][0][0], "open:updates")
        st = {"security": {"key": "openssl", "until": 100}}
        self.assertFalse(background.should_notify(st, "security", "openssl", 50))
        self.assertTrue(background.should_notify(st, "security", "openssl", 150))
        self.assertTrue(background.should_notify(st, "security", "openssl,curl", 50))   # something new
        self.assertEqual(background.findings([], [], (10, 100), False, None, False, [], None), [])


    def test_stored_texts_follow_language(self):
        from lscc import i18n
        old = i18n.LANG
        try:
            i18n.LANG = "en"
            self.assertEqual(i18n.stored("Aktualizacje: 2"), "Updates: 2")
            self.assertEqual(i18n.stored("Sprzątanie · 6.4 GB"), "Cleanup · 6.4 GB")
            self.assertEqual(i18n.stored("Odinstalowano: A, B"), "Uninstalled: A, B")
            self.assertEqual(i18n.stored("something else: x"), "something else: x")
            i18n.LANG = "pl"
            self.assertEqual(i18n.stored("Updates: 2"), "Aktualizacje: 2")
        finally:
            i18n.LANG = old

if __name__ == "__main__":
    unittest.main()
