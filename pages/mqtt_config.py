"""
pages/mqtt_config.py - Configuração do broker MQTT.
Todas as strings usam i18n._() para suporte a tradução.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from config_manager import ConfigManager
import i18n


class MqttConfigPage(Gtk.Box):

    def __init__(self, config_manager: ConfigManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager = config_manager
        self._build_ui()
        self.connect("realize", lambda _: self._load_values())

    def _build_ui(self):
        _ = i18n._

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        clamp = Adw.Clamp(maximum_size=640, tightening_threshold=480)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(box)

        # ── Broker ────────────────────────────────────────────────────
        broker_group = Adw.PreferencesGroup(
            title=_("Broker Connection"),
            description=_("Connect to your MQTT broker (e.g., Mosquitto on Home Assistant OS)."),
        )
        box.append(broker_group)

        self.host_row = self._make_entry(_("Broker Host / IP"), _("e.g. 192.168.1.10 or homeassistant.local"))
        self.port_row = self._make_entry(_("Port"), _("Default: 1883"))
        broker_group.add(self.host_row)
        broker_group.add(self.port_row)

        # ── Autenticação ──────────────────────────────────────────────
        auth_group = Adw.PreferencesGroup(
            title=_("Authentication"),
            description=_("Leave blank if your broker does not require credentials."),
        )
        box.append(auth_group)

        self.user_row = self._make_entry(_("Username"), _("MQTT username"))
        self.pass_row = self._make_entry(_("Password"), _("MQTT password"), is_password=True)
        auth_group.add(self.user_row)
        auth_group.add(self.pass_row)

        # ── Discovery ─────────────────────────────────────────────────
        disc_group = Adw.PreferencesGroup(
            title=_("Home Assistant Discovery"),
            description=_("MQTT discovery settings — must match your HA configuration."),
        )
        box.append(disc_group)

        self.disc_prefix_row = self._make_entry(_("Discovery Prefix"), _("Default: homeassistant"))
        self.prefix_row      = self._make_entry(_("Automa Prefix"),     _("Default: lnxlink"))
        disc_group.add(self.disc_prefix_row)
        disc_group.add(self.prefix_row)

        note = Gtk.Label(label=_("Changes take effect after restarting the LNXlink service."))
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        note.set_halign(Gtk.Align.START)
        box.append(note)

    def _make_entry(self, title: str, placeholder: str, is_password: bool = False):
        if is_password:
            return Adw.PasswordEntryRow(title=title)
        return Adw.EntryRow(title=title)

    def _load_values(self):
        mqtt = self.config_manager.get_mqtt()
        self.host_row.set_text(str(mqtt["host"]))
        self.port_row.set_text(str(mqtt["port"]))
        self.user_row.set_text(str(mqtt["user"]))
        self.pass_row.set_text(str(mqtt["password"]))
        self.disc_prefix_row.set_text(str(mqtt["discovery_prefix"]))
        self.prefix_row.set_text(str(mqtt["prefix"]))

    def apply_to_config(self):
        try:
            port = int(self.port_row.get_text().strip() or "1883")
        except ValueError:
            port = 1883
        self.config_manager.set_mqtt(
            host             = self.host_row.get_text().strip(),
            port             = port,
            user             = self.user_row.get_text().strip(),
            password         = self.pass_row.get_text().strip(),
            discovery_prefix = self.disc_prefix_row.get_text().strip() or "homeassistant",
            prefix           = self.prefix_row.get_text().strip() or "lnxlink",
        )
