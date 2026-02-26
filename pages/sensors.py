"""
pages/sensors.py - Sensores. Nomes dos módulos baseados no LNXlink real.
Lê/escreve em "exclude:" na raiz do config.yaml — único lugar que o LNXlink lê.
"""

import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager
import i18n

# Módulos reais do LNXlink baseados no config.yaml gerado pelo LNXlink
# Chave = nome exato usado no exclude: do LNXlink
# (nome_exibição, descrição, grupo)
MODULES = {
    # ── System ──────────────────────────────────────────────────────
    "cpu":               ("CPU Usage",        "Usage % per core",                          "System"),
    "memory":            ("Memory Usage",      "RAM and swap usage %",                      "System"),
    "disk_usage":        ("Disk Usage",        "Usage % per mount point",                   "System"),
    "disk_io":           ("Disk I/O",          "Read/write bytes per disk",                 "System"),
    "fan":               ("Fan Speed",         "RPM from hardware sensors",                 "System"),
    "gpu":               ("GPU Usage",         "Requires compatible GPU drivers",           "System"),
    "battery":           ("Battery",           "Charge level — laptops only",              "System"),
    "power_profile":     ("Power Profile",     "Active power profile (balanced/perf)",      "System"),
    # ── Desktop ─────────────────────────────────────────────────────
    "media":             ("Media Player",      "Current track via MPRIS",                   "Desktop"),
    "speakers":          ("Speaker Volume",    "Current volume and mute state",             "Desktop"),
    "microphone":        ("Microphone",        "Detects if mic is in use",                  "Desktop"),
    "idle":              ("Idle Status",       "Detects if session is idle",                "Desktop"),
    "monitor":           ("Monitor",           "Connected displays info",                   "Desktop"),
    "clipboard":         ("Clipboard",         "Read/write system clipboard",               "Desktop"),
    "notify":            ("Notifications",     "Send desktop notifications from HA",        "Desktop"),
    "screenshot":        ("Screenshot",        "Take screenshots triggered from HA",        "Desktop"),
    "brightness":        ("Brightness",        "Screen brightness control",                 "Desktop"),
    "screen_onoff":      ("Screen On/Off",     "Turn monitor on or off from HA",           "Desktop"),
    "fullscreen":        ("Fullscreen",        "Detects if app is fullscreen",             "Desktop"),
    "mouse":             ("Mouse",             "Mouse position and control",                "Desktop"),
    "audio_select":      ("Audio Select",      "Switch audio input/output devices",        "Desktop"),
    # ── Connectivity ────────────────────────────────────────────────
    "network":           ("Network Stats",     "Bytes sent/received per interface",         "Connectivity"),
    "bluetooth":         ("Bluetooth",         "Connected bluetooth devices",               "Connectivity"),
    # ── Automation ──────────────────────────────────────────────────
    "bash":              ("Bash Commands",     "Run custom bash scripts from HA",           "Automation"),
    "camera_used":       ("Camera In Use",     "Detects if any camera is being used",      "Automation"),
    "send_keys":         ("Send Keys",         "Send keyboard shortcuts from HA",           "Automation"),
    "xdg_open":          ("Open URLs",         "Open URLs/files from HA",                  "Automation"),
    "mounts":            ("Mounts",            "Auto-mount directories",                    "Automation"),
    # ── Advanced ────────────────────────────────────────────────────
    "webcam":            ("Webcam Capture",    "May fail with multiple /dev/video*",        "Advanced"),
    "systemd":           ("Systemd Units",     "Control systemd services from HA",          "Advanced"),
    "keep_alive":        ("Keep Alive",        "Periodic MQTT ping",                       "Advanced"),
    "boot_select":       ("Boot Select",       "Switch boot target from HA",               "Advanced"),
    "restful":           ("RESTful API",       "Local HTTP API on port 8112",              "Advanced"),
}

# Lista de todos os módulos que este app gerencia
# Usada pelo config_manager para atualização cirúrgica do exclude:
OUR_MODULES = list(MODULES.keys())

# Módulos desabilitados por padrão pelo próprio LNXlink
# (aparecem no exclude: quando o LNXlink gera o config pela primeira vez)
DEFAULT_EXCLUDED = {
    "audio_select", "battery", "beacondb", "boot_select", "brightness",
    "fullscreen", "gpio", "gpu", "idle", "inference_time", "ir_remote",
    "keep_alive", "keyboard_hotkeys", "media", "mouse", "notify",
    "power_profile", "restful", "screen_onoff", "screenshot", "send_keys",
    "speech_recognition", "systemd", "webcam", "xdg_open",
}

GROUPS = ["System", "Desktop", "Connectivity", "Automation", "Advanced"]


class SensorsPage(Gtk.Box):

    def __init__(self, config_manager: ConfigManager, service_manager=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager  = config_manager
        self.service_manager = service_manager
        self._rows: dict[str, Adw.SwitchRow] = {}
        self._loading        = False
        self._restart_timer  = None
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

        hint = Gtk.Label(label=_(
            "Changes are saved automatically and the LNXlink service is restarted."
        ))
        hint.set_halign(Gtk.Align.START)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        outer.append(hint)

        # Status
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

        # Cria grupos
        placed: set[str] = set()
        for group_name in GROUPS:
            keys = [k for k, v in MODULES.items() if v[2] == group_name]
            if not keys:
                continue
            if group_name == "Advanced":
                adv_group = Adw.PreferencesGroup()
                outer.append(adv_group)
                expander = Adw.ExpanderRow(
                    title=_("Advanced"),
                    subtitle=_("Modules that may require extra configuration"),
                )
                expander.set_expanded(False)
                adv_group.add(expander)
                for key in keys:
                    row = self._make_row(key)
                    expander.add_row(row)
                    self._rows[key] = row
                    placed.add(key)
            else:
                group = Adw.PreferencesGroup(title=_(group_name))
                outer.append(group)
                for key in keys:
                    self._add_row(group, key)
                    placed.add(key)

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
        """Lê o exclude: atual do config e aplica nos toggles."""
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
        if self._restart_timer is not None:
            GLib.source_remove(self._restart_timer)
        self._show_status(i18n._("Saving…"))
        self._restart_timer = GLib.timeout_add(600, self._apply)

    def _apply(self):
        self._restart_timer = None
        self._show_status(i18n._("Applying…"))
        self.apply_to_config()
        self.config_manager.save()
        if self.service_manager:
            threading.Thread(target=self._restart_thread, daemon=True).start()
        else:
            self._show_status(_("Saved ✓"), done=True)
        return GLib.SOURCE_REMOVE

    def _restart_thread(self):
        ok, _err = self.service_manager.restart()
        if ok:
            GLib.idle_add(self._show_status, i18n._("Saved and restarted ✓"), True)
        else:
            GLib.idle_add(self._show_status, i18n._("Saved — restart failed, check service"), True)

    def _show_status(self, msg, done=False):
        self._status_box.set_visible(True)
        self._status_label.set_label(msg)
        self._status_spinner.set_visible(not done)
        self._status_spinner.set_spinning(not done)
        if done:
            GLib.timeout_add(3000, lambda: (
                self._status_box.set_visible(False), GLib.SOURCE_REMOVE)[1])
        return GLib.SOURCE_REMOVE

    def apply_to_config(self):
        """Salva lista de módulos desabilitados em exclude: na raiz."""
        excluded = [k for k, row in self._rows.items() if not row.get_active()]
        self.config_manager.set_excluded_modules(excluded)
