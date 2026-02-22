"""
pages/mqtt_config.py - MQTT broker configuration page.

Reads from and writes to the 'mqtt' section of config.yaml via ConfigManager.
The user edits the fields and clicks "Save Config" in the main toolbar.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from config_manager import ConfigManager


class MqttConfigPage(Gtk.Box):
    """Form for editing MQTT broker connection parameters."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager = config_manager
        self._build_ui()
        self.connect("realize", lambda _: self._load_values())

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        clamp = Adw.Clamp(maximum_size=640, tightening_threshold=480)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        self.append(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(box)

        # ---- Broker connection ----
        broker_group = Adw.PreferencesGroup(
            title="Broker Connection",
            description="Connect to your MQTT broker (e.g., Mosquitto on Home Assistant OS).",
        )
        box.append(broker_group)

        self.host_row = self._entry_row("Broker Host / IP", "e.g. 192.168.1.10 or homeassistant.local")
        self.port_row = self._entry_row("Port", "Default: 1883")
        broker_group.add(self.host_row)
        broker_group.add(self.port_row)

        # ---- Authentication ----
        auth_group = Adw.PreferencesGroup(
            title="Authentication",
            description="Leave blank if your broker does not require credentials.",
        )
        box.append(auth_group)

        self.user_row = self._entry_row("Username", "MQTT username")
        self.pass_row = self._entry_row("Password", "MQTT password", is_password=True)
        auth_group.add(self.user_row)
        auth_group.add(self.pass_row)

        # ---- Discovery ----
        disc_group = Adw.PreferencesGroup(
            title="Home Assistant Discovery",
            description="MQTT discovery settings — must match your HA configuration.",
        )
        box.append(disc_group)

        self.disc_prefix_row = self._entry_row("Discovery Prefix", "Default: homeassistant")
        self.prefix_row = self._entry_row("LNXlink Prefix", "Default: lnxlink")
        disc_group.add(self.disc_prefix_row)
        disc_group.add(self.prefix_row)

        # ---- Info banner ----
        banner = Adw.Banner(
            title="Changes take effect after restarting the LNXlink service.",
            revealed=True,
        )
        box.append(banner)

    def _entry_row(self, title: str, placeholder: str, is_password: bool = False) -> Adw.EntryRow:
        row = Adw.EntryRow(title=title)
        row.set_show_apply_button(False)
        entry = row.get_child()  # Not reliable; use PasswordEntryRow for passwords
        return row

    def _entry_row(self, title: str, placeholder: str, is_password: bool = False):
        if is_password:
            row = Adw.PasswordEntryRow(title=title)
        else:
            row = Adw.EntryRow(title=title)
        return row

    # ------------------------------------------------------------------ #
    #  Data binding                                                        #
    # ------------------------------------------------------------------ #

    def _load_values(self):
        """Populate form fields from the loaded config."""
        mqtt = self.config_manager.get_mqtt()
        self.host_row.set_text(str(mqtt["host"]))
        self.port_row.set_text(str(mqtt["port"]))
        self.user_row.set_text(str(mqtt["user"]))
        self.pass_row.set_text(str(mqtt["password"]))
        self.disc_prefix_row.set_text(str(mqtt["discovery_prefix"]))
        self.prefix_row.set_text(str(mqtt["prefix"]))

    def apply_to_config(self):
        """Write current field values back to ConfigManager (does not save to disk)."""
        try:
            port = int(self.port_row.get_text().strip() or "1883")
        except ValueError:
            port = 1883

        self.config_manager.set_mqtt(
            host=self.host_row.get_text().strip(),
            port=port,
            user=self.user_row.get_text().strip(),
            password=self.pass_row.get_text().strip(),
            discovery_prefix=self.disc_prefix_row.get_text().strip() or "homeassistant",
            prefix=self.prefix_row.get_text().strip() or "lnxlink",
        )
