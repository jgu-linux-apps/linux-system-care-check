"""System tray icon via StatusNotifierItem + DBusMenu (works with Ubuntu's AppIndicator
extension and KDE) implemented directly on GDBus - no GTK3 / libappindicator needed."""

import os
import time

from gi.repository import Gio, GLib

ICON_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "icons"))
if not os.path.isdir(ICON_DIR):
    ICON_DIR = "/usr/share/linux-system-care-check/data/icons"

SNI_XML = """
<node>
 <interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="WindowId" type="i" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="IconThemePath" type="s" access="read"/>
  <property name="OverlayIconName" type="s" access="read"/>
  <property name="AttentionIconName" type="s" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
  <signal name="NewTitle"/>
  <signal name="NewIcon"/>
  <signal name="NewAttentionIcon"/>
  <signal name="NewOverlayIcon"/>
  <signal name="NewToolTip"/>
  <signal name="NewStatus"><arg name="status" type="s"/></signal>
 </interface>
</node>"""

MENU_XML = """
<node>
 <interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout">
   <arg type="i" name="parentId" direction="in"/><arg type="i" name="recursionDepth" direction="in"/>
   <arg type="as" name="propertyNames" direction="in"/><arg type="u" name="revision" direction="out"/>
   <arg type="(ia{sv}av)" name="layout" direction="out"/>
  </method>
  <method name="GetGroupProperties">
   <arg type="ai" name="ids" direction="in"/><arg type="as" name="propertyNames" direction="in"/>
   <arg type="a(ia{sv})" name="properties" direction="out"/>
  </method>
  <method name="GetProperty">
   <arg type="i" name="id" direction="in"/><arg type="s" name="name" direction="in"/>
   <arg type="v" name="value" direction="out"/>
  </method>
  <method name="Event">
   <arg type="i" name="id" direction="in"/><arg type="s" name="eventId" direction="in"/>
   <arg type="v" name="data" direction="in"/><arg type="u" name="timestamp" direction="in"/>
  </method>
  <method name="EventGroup">
   <arg type="a(isvu)" name="events" direction="in"/><arg type="ai" name="idErrors" direction="out"/>
  </method>
  <method name="AboutToShow">
   <arg type="i" name="id" direction="in"/><arg type="b" name="needUpdate" direction="out"/>
  </method>
  <method name="AboutToShowGroup">
   <arg type="ai" name="ids" direction="in"/><arg type="ai" name="updatesNeeded" direction="out"/>
   <arg type="ai" name="idErrors" direction="out"/>
  </method>
  <signal name="ItemsPropertiesUpdated">
   <arg type="a(ia{sv})" name="updatedProps"/><arg type="a(ias)" name="removedProps"/>
  </signal>
  <signal name="LayoutUpdated"><arg type="u" name="revision"/><arg type="i" name="parent"/></signal>
 </interface>
</node>"""

ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"


class Tray:
    """items: list of (id, label, callback) or (id, None, None) for a separator."""

    @staticmethod
    def _check(items):
        """Bezpiecznik: id 0 to korzeń menu w DBusMenu – pozycja z id 0 tworzy pętlę, która potrafi zawiesić
        powłokę GNOME (AppIndicator). Identyfikatory muszą być dodatnie i unikalne."""
        ids = [it[0] for it in items]
        if any(i <= 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"tray: menu item ids must be unique and > 0, got {ids}")
        return items

    def __init__(self, app_id, title, icon_name, on_activate, items):
        self.app_id = app_id
        self.title = title
        self.icon_name = icon_name
        self.tooltip = title
        self.on_activate = on_activate
        self.items = self._check(items)
        self.revision = 1
        self.bus = None
        self.reg_ids = []
        # unique per start: a restart in place (os.execv, e.g. after a language change) keeps the PID, and the
        # host would drop the new icon together with the old one if both had the same name
        self.bus_name = "org.kde.StatusNotifierItem-%d-%d" % (os.getpid(), int(time.time() * 1000) % 1000000)
        self._sni_info = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        self._menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return
        self.reg_ids.append(self.bus.register_object(ITEM_PATH, self._sni_info, self._sni_call, self._sni_get, None))
        self.reg_ids.append(self.bus.register_object(MENU_PATH, self._menu_info, self._menu_call, self._menu_get, None))
        self.own_id = Gio.bus_own_name_on_connection(self.bus, self.bus_name, Gio.BusNameOwnerFlags.NONE, None, None)
        self.watch_id = Gio.bus_watch_name_on_connection(self.bus, "org.kde.StatusNotifierWatcher", Gio.BusNameWatcherFlags.NONE,
                                         self._watcher_appeared, None)
        self.check_id = GLib.timeout_add_seconds(5, self._ensure_registered)

    def close(self):
        """Remove the icon: drop the bus name and the exported objects."""
        if self.bus is None:
            return
        GLib.source_remove(self.check_id)
        Gio.bus_unwatch_name(self.watch_id)
        Gio.bus_unown_name(self.own_id)
        for rid in self.reg_ids:
            self.bus.unregister_object(rid)
        self.reg_ids = []
        self.bus = None

    # ------------------------------------------------ registration
    def _watcher_appeared(self, conn, name, owner):
        conn.call("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                  "RegisterStatusNotifierItem", GLib.Variant("(s)", (self.bus_name,)), None,
                  Gio.DBusCallFlags.NONE, -1, None, None, None)

    def _ensure_registered(self):
        """Re-register if the tray host lost the icon (shell restart, a race with an old instance)."""
        if self.bus is None:
            return False
        def done(conn, res):
            try:
                items = conn.call_finish(res).unpack()[0]
            except GLib.Error:
                return                                      # no tray host now; _watcher_appeared registers later
            mine = (self.bus_name, conn.get_unique_name())
            if not any(i.split("/")[0] in mine for i in items):
                self._watcher_appeared(conn, None, None)
        self.bus.call("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties", "Get",
                      GLib.Variant("(ss)", ("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")),
                      None, Gio.DBusCallFlags.NONE, -1, None, done)
        if self.check_id and getattr(self, "_slow", False) is False:
            self._slow = True
            self.check_id = GLib.timeout_add_seconds(60, self._ensure_registered)
            return False
        return True

    # ------------------------------------------------ public API
    def set_pixmap(self, width, height, argb):
        """Live icon: ARGB32 pixels in network byte order (None = back to the named icon)."""
        self.pixmap = (width, height, argb) if argb else None
        self._emit(ITEM_PATH, "org.kde.StatusNotifierItem", "NewIcon", None)

    def set_icon(self, name):
        if name != self.icon_name:
            self.icon_name = name
            self._emit(ITEM_PATH, "org.kde.StatusNotifierItem", "NewIcon", None)

    def set_tooltip(self, text):
        if text != self.tooltip:
            self.tooltip = text
            self._emit(ITEM_PATH, "org.kde.StatusNotifierItem", "NewToolTip", None)
            self._emit(ITEM_PATH, "org.kde.StatusNotifierItem", "NewTitle", None)

    def set_items(self, items):
        self.items = self._check(items)
        self.revision += 1
        self._emit(MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (self.revision, 0)))

    def _emit(self, path, iface, signal, params):
        if self.bus is None:
            return
        try:
            self.bus.emit_signal(None, path, iface, signal, params)
        except GLib.Error:
            pass

    # ------------------------------------------------ StatusNotifierItem
    def _sni_props(self):
        return {
            "Category": GLib.Variant("s", "SystemServices"),
            "Id": GLib.Variant("s", self.app_id),
            "Title": GLib.Variant("s", self.tooltip),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", "" if getattr(self, "pixmap", None) else self.icon_name),
            "IconPixmap": GLib.Variant("a(iiay)", [(self.pixmap[0], self.pixmap[1], self.pixmap[2])]
                                       if getattr(self, "pixmap", None) else []),
            "IconThemePath": GLib.Variant("s", ICON_DIR),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", (self.icon_name, [], self.title, self.tooltip)),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }

    def _sni_get(self, conn, sender, path, iface, prop):
        return self._sni_props().get(prop)

    def _sni_call(self, conn, sender, path, iface, method, params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(lambda: (self.on_activate(), False)[1])
        invocation.return_value(None)

    # ------------------------------------------------ DBusMenu
    def _item_props(self, item):
        """item: (id, label, callback) or (id, label, callback, radio_state) — radio_state True/False makes a radio
        item (shown with a dot); a separator has label None."""
        iid, label, cb = item[:3]
        if label is None:
            return {"type": GLib.Variant("s", "separator")}
        props = {"label": GLib.Variant("s", label), "enabled": GLib.Variant("b", cb is not None),
                 "visible": GLib.Variant("b", True)}
        if len(item) > 3 and item[3] is not None:
            props["toggle-type"] = GLib.Variant("s", "radio")
            props["toggle-state"] = GLib.Variant("i", 1 if item[3] else 0)
        return props

    def _layout(self):
        children = [GLib.Variant("(ia{sv}av)", (it[0], self._item_props(it), [])) for it in self.items]
        return (0, {"children-display": GLib.Variant("s", "submenu")}, children)

    def _menu_get(self, conn, sender, path, iface, prop):
        return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"),
                "IconThemePath": GLib.Variant("as", [ICON_DIR])}.get(prop)

    def _menu_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "GetLayout":
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self.revision, self._layout())))
        elif method == "GetGroupProperties":
            ids = params.unpack()[0]
            out = []
            for it in self.items:
                if not ids or it[0] in ids:
                    out.append((it[0], self._item_props(it)))
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (out,)))
        elif method == "GetProperty":
            iid, name = params.unpack()
            for it in self.items:
                if it[0] == iid:
                    v = self._item_props(it).get(name)
                    if v is not None:
                        invocation.return_value(GLib.Variant("(v)", (v,)))
                        return
            invocation.return_dbus_error("com.canonical.dbusmenu.Error", "no such property")
        elif method == "Event":
            iid, event_id, data, ts = params.unpack()
            if event_id == "clicked":
                self._fire(iid)
            invocation.return_value(None)
        elif method == "EventGroup":
            events = params.unpack()[0]
            for iid, event_id, data, ts in events:
                if event_id == "clicked":
                    self._fire(iid)
            invocation.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            invocation.return_value(None)

    def _fire(self, iid):
        for it in self.items:
            if it[0] == iid and it[2]:
                cb = it[2]
                GLib.idle_add(lambda: (cb(), False)[1])
