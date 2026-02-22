"""
pages/sensors.py - Habilita/desabilita módulos do LNXlink via toggles.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager


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
        self._dirty = False
        self._build_ui()
        self.connect("realize", lambda _: self._load_values())

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        clamp = Adw.Clamp(maximum_size=700, tightening_threshold=500)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scroll.set_child(clamp)

        self._outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(self._outer)

        # Descrição discreta (sem banner azul)
        hint = Gtk.Label(
            label="Toggle sensors to enable or disable them. Changes require saving and restarting the service."
        )
        hint.set_halign(Gtk.Align.START)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        self._outer.append(hint)

        # Botões rápidos + Restart (aparece só quando há mudanças)
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_bar.set_halign(Gtk.Align.END)

        btn_all  = Gtk.Button(label="Enable All")
        btn_none = Gtk.Button(label="Disable All")
        btn_all.connect("clicked",  lambda _: self._set_all(True))
        btn_none.connect("clicked", lambda _: self._set_all(False))
        btn_all.add_css_class("flat")
        btn_none.add_css_class("flat")
        action_bar.append(btn_all)
        action_bar.append(btn_none)

        # Separador visual
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(4)
        sep.set_margin_end(4)
        action_bar.append(sep)

        self.restart_btn = Gtk.Button(label="Save & Restart")
        self.restart_btn.add_css_class("suggested-action")
        self.restart_btn.set_icon_name("view-refresh-symbolic")
        self.restart_btn.set_visible(False)
        self.restart_btn.connect("clicked", self._on_save_restart)
        action_bar.append(self.restart_btn)

        self._outer.append(action_bar)

        # Grupos normais
        placed: set[str] = set()
        for group_name, keys in GROUPS.items():
            group = Adw.PreferencesGroup(title=group_name)
            self._outer.append(group)
            for key in keys:
                if key in MODULES:
                    self._add_row(group, key)
                    placed.add(key)

        # Grupo Advanced como ExpanderRow dentro de um PreferencesGroup
        advanced_group = Adw.PreferencesGroup()
        self._outer.append(advanced_group)

        self._expander = Adw.ExpanderRow(
            title="Advanced",
            subtitle="Modules that may require extra configuration",
        )
        self._expander.set_expanded(False)
        advanced_group.add(self._expander)

        for key in ADVANCED_KEYS:
            if key in MODULES:
                row = self._make_switch_row(key)
                self._expander.add_row(row)
                self._rows[key] = row
                placed.add(key)

        # Restantes não categorizados
        remaining = [k for k in MODULES if k not in placed]
        if remaining:
            other = Adw.PreferencesGroup(title="Other")
            self._outer.append(other)
            for key in remaining:
                self._add_row(other, key)

    def _make_switch_row(self, key: str) -> Adw.SwitchRow:
        name, desc, category = MODULES[key]
        row = Adw.SwitchRow(title=name, subtitle=desc)
        row.set_active(key not in DEFAULT_EXCLUDED)
        row.connect("notify::active", self._on_toggle_changed)
        return row

    def _add_row(self, group: Adw.PreferencesGroup, key: str):
        row = self._make_switch_row(key)
        group.add(row)
        self._rows[key] = row

    # ------------------------------------------------------------------ #
    #  Data binding                                                        #
    # ------------------------------------------------------------------ #

    def _load_values(self):
        excluded = self.config_manager.get_excluded_modules()
        for key, row in self._rows.items():
            # Bloqueia o signal durante o load para não marcar como dirty
            row.handler_block_by_func(self._on_toggle_changed)
            if key in excluded:
                row.set_active(False)
            elif key in DEFAULT_EXCLUDED:
                row.set_active(False)
            else:
                row.set_active(True)
            row.handler_unblock_by_func(self._on_toggle_changed)
        self._set_dirty(False)

    def _on_toggle_changed(self, *_):
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool):
        self._dirty = dirty
        self.restart_btn.set_visible(dirty)

    def _set_all(self, enabled: bool):
        for row in self._rows.values():
            row.set_active(enabled)

    # ------------------------------------------------------------------ #
    #  Save & Restart                                                      #
    # ------------------------------------------------------------------ #

    def _on_save_restart(self, _btn):
        self.apply_to_config()
        self.config_manager.save()
        if self.service_manager:
            self.service_manager.restart()
        self._set_dirty(False)
        # Feedback visual
        self.restart_btn.set_label("Restarting…")
        self.restart_btn.set_sensitive(False)
        GLib.timeout_add(2500, self._on_restart_done)

    def _on_restart_done(self):
        self.restart_btn.set_label("Save & Restart")
        self.restart_btn.set_sensitive(True)
        self.restart_btn.set_visible(False)
        return GLib.SOURCE_REMOVE

    def apply_to_config(self):
        excluded = [key for key, row in self._rows.items() if not row.get_active()]
        self.config_manager.set_excluded_modules(excluded)
