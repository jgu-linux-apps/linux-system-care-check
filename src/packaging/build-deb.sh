#!/bin/bash
# Builds the .deb: dist/linux-system-care-check_<version>_all.deb
set -euo pipefail
cd "$(dirname "$0")/.."
PKG=linux-system-care-check
APP_ID=io.github.jgu.LinuxSystemCareCheck
VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' src/lscc/__init__.py)
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT

install -d "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/$PKG" "$ROOT/usr/share/applications" \
  "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/etc/xdg/autostart" "$ROOT/usr/share/doc/$PKG" \
  "$ROOT/usr/lib/$PKG" "$ROOT/usr/share/polkit-1/actions" "$ROOT/usr/lib/systemd/system"

cp -r src data "$ROOT/usr/share/$PKG/"
find "$ROOT/usr/share/$PKG" -name __pycache__ -prune -exec rm -rf {} +
chmod -R u=rwX,go=rX "$ROOT/usr/share/$PKG"
rm -rf "$ROOT/usr/share/$PKG/data/applications" "$ROOT/usr/share/$PKG/data/autostart" \
  "$ROOT/usr/share/$PKG/data/icons/hicolor" "$ROOT/usr/share/$PKG/data/polkit" "$ROOT/usr/share/$PKG/data/systemd"
install -m 755 bin/$PKG "$ROOT/usr/bin/$PKG"
install -m 755 bin/care-helper "$ROOT/usr/lib/$PKG/care-helper"
install -m 644 data/polkit/$APP_ID.policy "$ROOT/usr/share/polkit-1/actions/"
install -m 644 data/systemd/$PKG-battery.service "$ROOT/usr/lib/systemd/system/"
install -m 644 data/applications/$APP_ID.desktop "$ROOT/usr/share/applications/"
install -m 644 data/autostart/$PKG-iconsync.desktop data/autostart/$PKG-background.desktop "$ROOT/etc/xdg/autostart/"
install -m 644 data/icons/hicolor/scalable/apps/$APP_ID.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/"
install -m 644 README.md "$ROOT/usr/share/doc/$PKG/"
install -m 644 LICENSE "$ROOT/usr/share/doc/$PKG/copyright"

SIZE=$(du -sk "$ROOT/usr" "$ROOT/etc" | awk '{s+=$1} END {print s}')
cat > "$ROOT/DEBIAN/control" <<CTL
Package: $PKG
Version: $VERSION
Section: admin
Priority: optional
Architecture: all
Installed-Size: $SIZE
Maintainer: JGu <jaroslawguza83@gmail.com>
Homepage: https://github.com/jgu-linux-apps/linux-system-care-check
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.5), pkexec | policykit-1, librsvg2-common
Recommends: udisks2, power-profiles-daemon, gnome-shell-extension-appindicator, fwupd
Suggests: timevault, baobab
Description: Linux System Care Check – system care center for Ubuntu
 Updates (apt, snap, flatpak, firmware), safe cleanup, installed programs
 including web apps (multi-select uninstall), autostart, disk health (SMART),
 battery health and charge limit, temperatures, history with undo hints and
 Linux Backup TimeVault integration (backup before big changes).
 Preview mode is on by default; nothing changes without your confirmation and
 automatic actions run only when you allow them. Background checks show
 notifications with buttons. Themes: System, Aurora, Studio, Aubergine.
CTL

cat > "$ROOT/DEBIAN/postinst" <<'SH'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
  command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
  command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
  if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
    systemctl enable linux-system-care-check-battery.service >/dev/null 2>&1 || true
  fi
fi
exit 0
SH
cat > "$ROOT/DEBIAN/prerm" <<'SH'
#!/bin/sh
set -e
if [ "$1" = "remove" ] && [ -d /run/systemd/system ]; then
  systemctl disable linux-system-care-check-battery.service >/dev/null 2>&1 || true
fi
exit 0
SH
cat > "$ROOT/DEBIAN/postrm" <<'SH'
#!/bin/sh
set -e
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
if [ "$1" = "purge" ]; then rm -rf /etc/linux-system-care-check; fi
[ -d /run/systemd/system ] && systemctl daemon-reload >/dev/null 2>&1 || true
exit 0
SH
chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/prerm" "$ROOT/DEBIAN/postrm"
printf '%s\n' "/etc/xdg/autostart/$PKG-iconsync.desktop" "/etc/xdg/autostart/$PKG-background.desktop" > "$ROOT/DEBIAN/conffiles"

mkdir -p dist
dpkg-deb --root-owner-group --build "$ROOT" "dist/${PKG}_${VERSION}_all.deb" >/dev/null
echo "dist/${PKG}_${VERSION}_all.deb"
