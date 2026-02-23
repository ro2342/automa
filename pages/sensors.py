"""
pages/sensors.py - Sensores. Todas as strings via i18n._().
Auto-restart ao toggle com debounce de 1.5s.
"""

import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager
import i18n

# Módulos: chave → (nome_i18n_key, desc_i18n_key, categoria)
# Usamos keys fixas e traduzimos na hora para suportar troca de idioma
MODULES = {
    "bash":          ("Bash Commands",   "Run custom bash scripts from HA",                          "supported"),
    "bluetooth":     ("Bluetooth",       "Connected bluetooth devices",                               "supported"),
    "camera_used":   ("Camera In Use",   "Detects if any camera is being used — no OpenCV needed",   "supported"),
    "clipboard":     ("Clipboard",       "Read/write system clipboard",                               "supported"),
    "cpu":           ("CPU Usage",       "Usage % per core",                                          "supported"),
    "disk":          ("Disk Usage",      "Usage % per mount point",                                   "supported"),
    "fan":           ("Fan Speed",       "RPM from hardware sensors",                                 "supported"),
    "memory":        ("Memory Usage",    "RAM and swap usage %",                                      "supported"),
    "microphone":    ("Microphone",      "Detects if mic is in use",                                  "supported"),
    "monitor":       ("Monitor",         "Connected displays info",                                   "supported"),
    "network":       ("Network Stats",   "Bytes sent/received per interface",                         "supported"),
    "power_profile": ("Power Profile",   "Active power profile (balanced / performance)",             "supported"),
    "screenshot":    ("Screenshot",      "Take screenshots triggered from HA",                        "supported"),
    "speakers":      ("Speaker Volume",  "Current volume level and mute state",                       "supported"),
    "battery":       ("Battery",         "Charge level — laptops only",                              "optional"),
    "gpu":           ("GPU Usage",       "Requires compatible GPU drivers",                           "optional"),
    "idle":          ("Idle Status",     "Detects if session is idle",                               "optional"),
    "media":         ("Media Player",    "Current track via MPRIS",                                   "optional"),
    "notify":        ("Notifications",   "Send desktop notifications from HA",                        "optional"),
    "webcam":        ("Webcam Capture",  "May fail with multiple /dev/video* — use Camera In Use instead", "advanced"),
    "wifi":          ("Wi-Fi Info",      "Requires passwordless sudo ethtool",                        "advanced"),
    "wol":           ("Wake-on-LAN",     "Requires passwordless sudo ethtool",                        "advanced"),
    "docker":        ("Docker",          "Requires Docker installed and running",                     "advanced"),
    "steam":         ("Steam",           "Requires Steam installed and running",                      "advanced"),
}

DEFAULT_EXCLUDED = {"webcam", "wifi", "wol", "docker", "steam"}

GROUPS = {
    "System":       ["cpu", "memory", "disk", "fan", "gpu", "battery", "power_profile"],
    "Desktop":      ["idle", "media", "speakers", "microphone", "monitor", "clipboard", "notify", "screenshot"],
    "Connectivity": ["network", "bluetooth"],
    "Automation":   ["bash", "camera_used"],
}
ADVANCED_KEYS = ["webcam", "wifi", "wol", "docker", "steam"]


class SensorsPage(Gtk.Box):

    def __init__(self, config_manager: ConfigManager, service_manager=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager  = config_manager
        self.service_manager = service_manager
        self._rows: dict[str, Adw.SwitchRow] = {}
        self._loading       = False
        self._restart_timer = None
        self._build_ui()
        self.connect("realize", lambda _: self._load_values())

    def _build_ui(self):
        _ = i18n._
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        clamp = Adw.Clamp(maximum_size=700, tightening_threshold=500)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scroll.set_child(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(outer)

        hint = Gtk.Label(label=_("Changes are saved and applied automatically."))
        hint.set_halign(Gtk.Align.START)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        outer.append(hint)

        # Status spinner discreto
        self._status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._status_box.set_halign(Gtk.Align.END)
        self._status_box.set_visible(False)
        self._status_spinner = Gtk.Spinner()
        self._status_spinner.set_spinning(True)
        self._status_box.append(self._status_spinner)
        self._status_label = Gtk.Label()
        self._status_label.add_css_class("dim-label")
        self._status_label.add_css_class("caption")
        self._status_box.append(self._status_label)
        outer.append(self._status_box)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_all  = Gtk.Button(label=_("Enable All"))
        btn_none = Gtk.Button(label=_("Disable All"))
        btn_all.add_css_class("flat")
        btn_none.add_css_class("flat")
        btn_all.connect("clicked",  lambda _: self._set_all(True))
        btn_none.connect("clicked", lambda _: self._set_all(False))
        btn_box.append(btn_all)
        btn_box.append(btn_none)
        outer.append(btn_box)

        placed: set[str] = set()
        for group_name, keys in GROUPS.items():
            group = Adw.PreferencesGroup(title=_(group_name))
            outer.append(group)
            for key in keys:
                if key in MODULES:
                    self._add_row(group, key)
                    placed.add(key)

        adv_group = Adw.PreferencesGroup()
        outer.append(adv_group)
        self._expander = Adw.ExpanderRow(
            title=_("Advanced"),
            subtitle=_("Modules that may require extra configuration — disabled by default"),
        )
        self._expander.set_expanded(False)
        adv_group.add(self._expander)
        for key in ADVANCED_KEYS:
            if key in MODULES:
                row = self._make_row(key)
                self._expander.add_row(row)
                self._rows[key] = row
                placed.add(key)

        remaining = [k for k in MODULES if k not in placed]
        if remaining:
            other = Adw.PreferencesGroup(title=_("Other"))
            outer.append(other)
            for key in remaining:
                self._add_row(other, key)

    def _make_row(self, key: str) -> Adw.SwitchRow:
        _ = i18n._
        name, desc, _cat = MODULES[key]
        row = Adw.SwitchRow(title=_(name), subtitle=_(desc))
        row.set_active(key not in DEFAULT_EXCLUDED)
        row.connect("notify::active", self._on_toggle)
        return row

    def _add_row(self, group, key):
        row = self._make_row(key)
        group.add(row)
        self._rows[key] = row

    def _load_values(self):
        self._loading = True
        excluded = self.config_manager.get_excluded_modules()
        for key, row in self._rows.items():
            row.set_active(key not in excluded)
        self._loading = False

    def _set_all(self, enabled: bool):
        self._loading = True
        for row in self._rows.values():
            row.set_active(enabled)
        self._loading = False
        self._schedule_restart()

    def _on_toggle(self, *_):
        if self._loading:
            return
        self._schedule_restart()

    def _schedule_restart(self):
        _ = i18n._
        if self._restart_timer is not None:
            GLib.source_remove(self._restart_timer)
        self._show_status(_("Saving…"))
        self._restart_timer = GLib.timeout_add(1500, self._apply)

    def _apply(self):
        _ = i18n._
        self._restart_timer = None
        self._show_status(_("Applying…"))
        self.apply_to_config()
        self.config_manager.save()
        if self.service_manager:
            threading.Thread(target=self._restart_thread, daemon=True).start()
        else:
            self._show_status(_("Saved ✓"), done=True)
        return GLib.SOURCE_REMOVE

    def _restart_thread(self):
        _ = i18n._
        self.service_manager.restart()
        GLib.idle_add(self._show_status, _("Applied ✓"), True)

    def _show_status(self, msg, done=False):
        self._status_box.set_visible(True)
        self._status_label.set_label(msg)
        self._status_spinner.set_visible(not done)
        self._status_spinner.set_spinning(not done)
        if done:
            GLib.timeout_add(2000, lambda: (self._status_box.set_visible(False), GLib.SOURCE_REMOVE)[1])
        return GLib.SOURCE_REMOVE

    def apply_to_config(self):
        excluded = [k for k, row in self._rows.items() if not row.get_active()]
        self.config_manager.set_excluded_modules(excluded)
