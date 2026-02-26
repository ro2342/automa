"""
pages/mqtt_config.py - Configuração do broker MQTT.
Todas as strings usam i18n._() para suporte a tradução.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from config_manager import ConfigManager
from icon_loader import make_icon
import i18n


class MqttConfigPage(Gtk.Box):

    def __init__(self, config_manager: ConfigManager, save_cb=None, service_manager=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager  = config_manager
        self.save_cb         = save_cb          # chamado após salvar
        self.service_manager = service_manager
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

        self.host_row = self._make_entry(_("Broker Host / IP"), _("e.g. 192.168.1.10 or homeassistant.local"), icon="network-server-symbolic")
        self.port_row = self._make_entry(_("Port"), _("Default: 1883"), icon="network-wireless-symbolic")
        broker_group.add(self.host_row)
        broker_group.add(self.port_row)

        # ── Autenticação ──────────────────────────────────────────────
        auth_group = Adw.PreferencesGroup(
            title=_("Authentication"),
            description=_("Leave blank if your broker does not require credentials."),
        )
        box.append(auth_group)

        self.user_row = self._make_entry(_("Username"), _("MQTT username"), icon="avatar-default-symbolic")
        self.pass_row = self._make_entry(_("Password"), _("MQTT password"), is_password=True, icon="dialog-password-symbolic")
        auth_group.add(self.user_row)
        auth_group.add(self.pass_row)

        # ── Discovery ─────────────────────────────────────────────────
        disc_group = Adw.PreferencesGroup(
            title=_("Home Assistant Discovery"),
            description=_("MQTT discovery settings — must match your HA configuration."),
        )
        box.append(disc_group)

        self.disc_prefix_row = self._make_entry(_("Discovery Prefix"), _("Default: homeassistant"), icon="go-home-symbolic")
        self.prefix_row      = self._make_entry(_("Automa Prefix"),     _("Default: lnxlink"), icon="text-x-generic-symbolic")
        disc_group.add(self.disc_prefix_row)
        disc_group.add(self.prefix_row)

        # Botão Save
        save_btn = Gtk.Button(label=_("Save & Restart Service"))
        save_btn.add_css_class("suggested-action")
        save_btn.add_css_class("pill")
        save_btn.set_halign(Gtk.Align.END)
        save_btn.connect("clicked", self._on_save)
        box.append(save_btn)

        note = Gtk.Label(label=_("Save applies changes and restarts the LNXlink service."))
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        note.set_halign(Gtk.Align.START)
        box.append(note)

    def _make_entry(self, title: str, placeholder: str, is_password: bool = False, icon: str = ""):
        if is_password:
            row = Adw.PasswordEntryRow(title=title)
        else:
            row = Adw.EntryRow(title=title)
        if icon:
            row.add_prefix(make_icon(icon, 16))
        return row

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

    def _on_save(self, _btn):
        import threading
        _ = i18n._
        self.apply_to_config()
        self.config_manager.save()
        if self.save_cb:
            self.save_cb(_("MQTT settings saved!"))
        if self.service_manager:
            def _restart():
                ok, err = self.service_manager.restart()
                if self.save_cb:
                    from gi.repository import GLib
                    if ok:
                        GLib.idle_add(self.save_cb, _("MQTT saved and service restarted!"))
                    else:
                        GLib.idle_add(self.save_cb, _("MQTT saved — restart failed: {e}").format(e=err))
            threading.Thread(target=_restart, daemon=True).start()
