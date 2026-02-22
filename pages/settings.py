"""
pages/settings.py - Configurações do app: tema, idioma, startup e backup.

Startup funciona via arquivos .desktop em ~/.config/autostart/
(padrão XDG — funciona em GNOME, KDE, XFCE etc sem depender de systemd).
"""

import shutil
import json
import os
import subprocess
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager
import i18n

PREFS_PATH = Path.home() / ".config" / "lnxlink-gui" / "prefs.json"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"

# Arquivo .desktop do nosso app para autostart
GUI_DESKTOP_AUTOSTART = AUTOSTART_DIR / "lnxlink-gui.desktop"
GUI_DESKTOP_CONTENT = """\
[Desktop Entry]
Name=LNXlink GUI
Comment=LNXlink MQTT Agent Control Panel
Exec=python3 {script_path}
Icon=io.github.lnxlink.gui
Terminal=false
Type=Application
Categories=Utility;System;
X-GNOME-Autostart-enabled=true
"""

# Arquivo .desktop do LNXlink para autostart (caso queira iniciar sem systemd)
LNXLINK_DESKTOP_AUTOSTART = AUTOSTART_DIR / "lnxlink.desktop"
LNXLINK_DESKTOP_CONTENT = """\
[Desktop Entry]
Name=LNXlink
Comment=LNXlink MQTT Agent
Exec={lnxlink_bin} -c {config_path}
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
"""


def load_prefs() -> dict:
    try:
        return json.loads(PREFS_PATH.read_text())
    except Exception:
        return {"theme": "system", "language": "system"}


def save_prefs(prefs: dict):
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2))


def apply_theme(theme: str):
    """Aplica tema via Adw.StyleManager — funciona na hora, sem reiniciar."""
    manager = Adw.StyleManager.get_default()
    mapping = {
        "system": Adw.ColorScheme.DEFAULT,
        "light":  Adw.ColorScheme.FORCE_LIGHT,
        "dark":   Adw.ColorScheme.FORCE_DARK,
    }
    manager.set_color_scheme(mapping.get(theme, Adw.ColorScheme.DEFAULT))


# ------------------------------------------------------------------ #
#  Helpers de startup                                                  #
# ------------------------------------------------------------------ #

def _get_gui_script_path() -> str:
    """Retorna o caminho absoluto do main.py desta aplicação."""
    return str(Path(__file__).parent.parent / "main.py")


def _get_lnxlink_bin() -> str:
    return shutil.which("lnxlink") or str(Path.home() / ".local/bin/lnxlink")


def is_gui_autostart_enabled() -> bool:
    """Verifica se o LNXlink GUI está configurado para iniciar com o sistema."""
    return GUI_DESKTOP_AUTOSTART.exists()


def set_gui_autostart(enabled: bool):
    """Habilita/desabilita o autostart do LNXlink GUI via ~/.config/autostart."""
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    if enabled:
        GUI_DESKTOP_AUTOSTART.write_text(
            GUI_DESKTOP_CONTENT.format(script_path=_get_gui_script_path())
        )
    else:
        GUI_DESKTOP_AUTOSTART.unlink(missing_ok=True)


def is_lnxlink_service_autostart_enabled() -> bool:
    """Verifica se lnxlink.service está habilitado no systemd --user."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", "lnxlink.service"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "enabled"
    except Exception:
        return False


def is_mqtt_broker_reachable() -> bool:
    """Testa conexão TCP com o broker MQTT configurado."""
    try:
        from config_manager import ConfigManager, DEFAULT_CONFIG_PATH
        import socket
        cm = ConfigManager()
        cm.load()
        mqtt = cm.get_mqtt()
        host = mqtt.get("host", "127.0.0.1")
        port = int(mqtt.get("port", 1883))
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        return True
    except Exception:
        return False


class SettingsPage(Gtk.Box):

    def __init__(self, config_manager: ConfigManager, show_toast_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager = config_manager
        self.show_toast_cb  = show_toast_cb or (lambda msg, **kw: None)
        self._prefs = load_prefs()
        self._build_ui()
        # Carrega status de startup ao exibir a página
        self.connect("realize", lambda _: self._refresh_startup_status())

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        _ = i18n._

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        clamp = Adw.Clamp(maximum_size=640, tightening_threshold=500)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(box)

        # ── Aparência ─────────────────────────────────────────────────
        appearance_group = Adw.PreferencesGroup(title=_("Appearance"))
        box.append(appearance_group)

        theme_row    = Adw.ActionRow(title=_("Color Scheme"))
        theme_keys   = ["system", "light", "dark"]
        theme_labels = [_("System Default"), _("Light"), _("Dark")]
        theme_combo  = Gtk.DropDown(model=Gtk.StringList.new(theme_labels))
        theme_combo.set_valign(Gtk.Align.CENTER)
        cur = self._prefs.get("theme", "system")
        theme_combo.set_selected(theme_keys.index(cur) if cur in theme_keys else 0)

        def on_theme(combo, _p):
            key = theme_keys[combo.get_selected()]
            self._prefs["theme"] = key
            save_prefs(self._prefs)
            apply_theme(key)

        theme_combo.connect("notify::selected", on_theme)
        theme_row.add_suffix(theme_combo)
        appearance_group.add(theme_row)

        # ── Idioma ────────────────────────────────────────────────────
        lang_group = Adw.PreferencesGroup(
            title=_("Language"),
            description=_("Restart the app to apply language changes."),
        )
        box.append(lang_group)

        lang_row    = Adw.ActionRow(title=_("App Language"))
        lang_keys   = list(i18n.AVAILABLE_LANGUAGES.keys())
        lang_labels = list(i18n.AVAILABLE_LANGUAGES.values())
        lang_combo  = Gtk.DropDown(model=Gtk.StringList.new(lang_labels))
        lang_combo.set_valign(Gtk.Align.CENTER)
        cur_lang = self._prefs.get("language", "system")
        lang_combo.set_selected(lang_keys.index(cur_lang) if cur_lang in lang_keys else 0)

        def on_lang(combo, _p):
            key = lang_keys[combo.get_selected()]
            self._prefs["language"] = key
            save_prefs(self._prefs)

        lang_combo.connect("notify::selected", on_lang)
        lang_row.add_suffix(lang_combo)
        lang_group.add(lang_row)

        # ── Startup ───────────────────────────────────────────────────
        startup_group = Adw.PreferencesGroup(
            title="Startup",
            description="Configure which components start automatically when you log in.",
        )
        box.append(startup_group)

        # LNXlink GUI autostart
        self.gui_startup_row = Adw.SwitchRow(
            title="LNXlink GUI",
            subtitle="Start this control panel on login (~/.config/autostart)",
        )
        self.gui_startup_row.connect("notify::active", self._on_gui_startup_toggled)
        startup_group.add(self.gui_startup_row)

        # LNXlink service via systemd
        self.service_startup_row = Adw.SwitchRow(
            title="LNXlink Service",
            subtitle="Start lnxlink.service on login (systemctl --user enable)",
        )
        self.service_startup_row.connect("notify::active", self._on_service_startup_toggled)
        startup_group.add(self.service_startup_row)

        # Status do broker MQTT (somente leitura — não dá pra controlar daqui)
        self.mqtt_status_row = Adw.ActionRow(
            title="MQTT Broker",
            subtitle="Checking connection…",
        )
        self.mqtt_status_icon = Gtk.Image()
        self.mqtt_status_icon.set_pixel_size(16)
        self.mqtt_status_row.add_suffix(self.mqtt_status_icon)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.set_tooltip_text("Re-check connection")
        refresh_btn.connect("clicked", lambda _: self._refresh_startup_status())
        self.mqtt_status_row.add_suffix(refresh_btn)
        startup_group.add(self.mqtt_status_row)

        # ── Backup & Restore ──────────────────────────────────────────
        backup_group = Adw.PreferencesGroup(title=_("Backup & Restore"))
        box.append(backup_group)

        export_row = Adw.ActionRow(
            title=_("Export Configuration"),
            subtitle=_("Save config.yaml to a custom location"),
            activatable=True,
        )
        export_row.set_icon_name("document-save-symbolic")
        export_row.connect("activated", self._on_export)
        backup_group.add(export_row)

        import_row = Adw.ActionRow(
            title=_("Import Configuration"),
            subtitle=_("Restore config.yaml from a backup"),
            activatable=True,
        )
        import_row.set_icon_name("document-open-symbolic")
        import_row.connect("activated", self._on_import)
        backup_group.add(import_row)

    # ------------------------------------------------------------------ #
    #  Startup status                                                      #
    # ------------------------------------------------------------------ #

    def _refresh_startup_status(self):
        """Verifica status de todos os itens de startup em background."""
        import threading
        threading.Thread(target=self._check_status_thread, daemon=True).start()

    def _check_status_thread(self):
        gui_enabled     = is_gui_autostart_enabled()
        service_enabled = is_lnxlink_service_autostart_enabled()
        mqtt_ok         = is_mqtt_broker_reachable()
        GLib.idle_add(self._update_status_ui, gui_enabled, service_enabled, mqtt_ok)

    def _update_status_ui(self, gui_enabled, service_enabled, mqtt_ok):
        # GUI toggle
        self.gui_startup_row.handler_block_by_func(self._on_gui_startup_toggled)
        self.gui_startup_row.set_active(gui_enabled)
        self.gui_startup_row.handler_unblock_by_func(self._on_gui_startup_toggled)

        # Service toggle
        self.service_startup_row.handler_block_by_func(self._on_service_startup_toggled)
        self.service_startup_row.set_active(service_enabled)
        self.service_startup_row.handler_unblock_by_func(self._on_service_startup_toggled)

        # MQTT status (só leitura)
        if mqtt_ok:
            self.mqtt_status_row.set_subtitle("Connected ✓")
            self.mqtt_status_icon.set_from_icon_name("emblem-ok-symbolic")
        else:
            self.mqtt_status_row.set_subtitle("Unreachable — check broker host and port")
            self.mqtt_status_icon.set_from_icon_name("dialog-warning-symbolic")

        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------ #
    #  Startup toggles                                                     #
    # ------------------------------------------------------------------ #

    def _on_gui_startup_toggled(self, row, _param):
        enabled = row.get_active()
        try:
            set_gui_autostart(enabled)
            msg = "LNXlink GUI will start on login." if enabled else "LNXlink GUI removed from startup."
            self.show_toast_cb(msg)
        except Exception as exc:
            self.show_toast_cb(f"Error: {exc}", is_error=True)

    def _on_service_startup_toggled(self, row, _param):
        enabled = row.get_active()
        try:
            action = "enable" if enabled else "disable"
            subprocess.run(
                ["systemctl", "--user", action, "lnxlink.service"],
                capture_output=True, timeout=5
            )
            msg = "LNXlink service enabled on startup." if enabled else "LNXlink service disabled from startup."
            self.show_toast_cb(msg)
        except Exception as exc:
            self.show_toast_cb(f"Error: {exc}", is_error=True)

    # ------------------------------------------------------------------ #
    #  Backup / Restore                                                    #
    # ------------------------------------------------------------------ #

    def _get_window(self):
        widget = self
        while widget:
            if isinstance(widget, Gtk.Window):
                return widget
            widget = widget.get_parent()
        return None

    def _on_export(self, _row):
        _ = i18n._
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Export Configuration"))
        dialog.set_initial_name("lnxlink-config-backup.yaml")

        def _done(dlg, result):
            try:
                dest = dlg.save_finish(result).get_path()
                shutil.copy2(self.config_manager.config_path, dest)
                self.show_toast_cb(_("Configuration exported to {path}").format(path=dest))
            except GLib.Error:
                pass
            except Exception as exc:
                self.show_toast_cb(_("Error exporting: {error}").format(error=exc), is_error=True)

        dialog.save(self._get_window(), None, _done)

    def _on_import(self, _row):
        _ = i18n._
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Import Configuration"))

        def _done(dlg, result):
            try:
                src = dlg.open_finish(result).get_path()
                dest = self.config_manager.config_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                self.config_manager.load()
                self.show_toast_cb(_("Configuration imported successfully!"))
            except GLib.Error:
                pass
            except Exception as exc:
                self.show_toast_cb(_("Error importing: {error}").format(error=exc), is_error=True)

        dialog.open(self._get_window(), None, _done)
