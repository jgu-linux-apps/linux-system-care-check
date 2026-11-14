"""Notifications with action buttons through org.freedesktop.Notifications (the same as linux-iphone-call-app).

Gio.Notification did not let the app close a notification on GNOME 51 / GLib 2.90: after a click the chat
opened, but the notification stayed in the list. Here every notification has a number from GNOME Shell,
so the app can close it itself (CloseNotification): after a click, when Chat closes it in the page
(message read) and when nothing is unread any more."""
from gi.repository import Gio, GLib

NAME = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


class Notifier:
    def __init__(self, app_name, desktop_id, icon, on_click):
        self.app_name, self.desktop_id, self.icon = app_name, desktop_id, icon
        self.on_click = on_click        # on_click(tag, action_key, activation_token or None)
        self.ids = {}                   # tag -> notification number from GNOME Shell
        self._tokens = {}               # notification number -> XDG activation token (focus on Wayland)
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            print("notifications unavailable:", e.message)
            self.bus = None
            return
        for sig, cb in (("ActionInvoked", self._on_action), ("NotificationClosed", self._on_closed),
                        ("ActivationToken", self._on_token)):
            self.bus.signal_subscribe(NAME, NAME, sig, PATH, None, Gio.DBusSignalFlags.NONE, cb)

    def show(self, tag, summary, body, actions=(), urgency=1):
        """actions: [(key, label)]; a click on the notification body sends the key "default"."""
        if self.bus is None:
            return
        hints = {"desktop-entry": GLib.Variant("s", self.desktop_id),
                 "urgency": GLib.Variant("y", urgency)}
        acts = ["default", ""]
        for key, label in actions:
            acts += [key, label]
        try:
            res = self.bus.call_sync(
                NAME, PATH, NAME, "Notify",
                GLib.Variant("(susssasa{sv}i)", (self.app_name, self.ids.get(tag, 0), self.icon, summary, body,
                                                 acts, hints, -1)),
                None, Gio.DBusCallFlags.NONE, 3000, None)
            self.ids[tag] = res.unpack()[0]
        except GLib.Error as e:
            print("notify failed:", e.message)

    def close(self, tag):
        nid = self.ids.pop(tag, None)
        if nid and self.bus is not None:
            self.bus.call(NAME, PATH, NAME, "CloseNotification", GLib.Variant("(u)", (nid,)), None,
                          Gio.DBusCallFlags.NONE, 2000, None, None, None)

    def close_all(self):
        for tag in list(self.ids):
            self.close(tag)

    def tags(self):
        return list(self.ids)

    def _tag_for(self, nid):
        return next((t for t, i in self.ids.items() if i == nid), None)

    def _on_token(self, _c, _s, _p, _i, _sig, params):
        nid, token = params.unpack()
        if self._tag_for(nid):
            self._tokens[nid] = token

    def _on_action(self, _c, _s, _p, _i, _sig, params):
        nid, key = params.unpack()
        tag = self._tag_for(nid)
        if tag:
            self.on_click(tag, key, self._tokens.pop(nid, None))
            self.close(tag)             # GNOME may keep it in the list after the click – close it ourselves

    def _on_closed(self, _c, _s, _p, _i, _sig, params):
        nid = params.unpack()[0]
        self._tokens.pop(nid, None)
        tag = self._tag_for(nid)
        if tag:
            self.ids.pop(tag, None)
