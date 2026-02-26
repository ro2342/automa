"""
pages/settings.py - Configurações: tema, idioma, device name, startup, backup.
Todas as strings via i18n._().
"""

import shutil
import json
import subprocess
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from config_manager import ConfigManager
from icon_loader import make_icon, set_icon
import i18n

PREFS_PATH    = Path.home() / ".config" / "automa-gui" / "prefs.json"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
GUI_AUTOSTART = AUTOSTART_DIR / "automa-gui.desktop"
GUI_DESKTOP   = """\
[Desktop Entry]
Name=Automa
Comment=LNXlink MQTT Agent Control Panel
Exec=python3 {script_path}
Icon=io.github.lnxlink.gui
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
    manager = Adw.StyleManager.get_default()
    mapping = {
        "system": Adw.ColorScheme.DEFAULT,
        "light":  Adw.ColorScheme.FORCE_LIGHT,
        "dark":   Adw.ColorScheme.FORCE_DARK,
    }
    manager.set_color_scheme(mapping.get(theme, Adw.ColorScheme.DEFAULT))


def is_gui_autostart_enabled() -> bool:
    return GUI_AUTOSTART.exists()


def set_gui_autostart(enabled: bool):
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    if enabled:
        script = str(Path(__file__).parent.parent / "main.py")
        GUI_AUTOSTART.write_text(GUI_DESKTOP.format(script_path=script))
    else:
        GUI_AUTOSTART.unlink(missing_ok=True)


def _sys_cmd(args: list) -> list:
    """Prefixa com flatpak-spawn --host se estiver dentro do Flatpak."""
    if os.environ.get("FLATPAK_ID"):
        return ["flatpak-spawn", "--host"] + args
    return args


def is_lnxlink_service_autostart_enabled() -> bool:
    try:
        r = subprocess.run(_sys_cmd(["systemctl", "--user", "is-enabled", "lnxlink.service"]),
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "enabled"
    except Exception:
        return False


def is_mqtt_broker_reachable(config_manager: ConfigManager) -> bool:
    try:
        import socket
        mqtt = config_manager.get_mqtt()
        s = socket.create_connection((mqtt["host"], int(mqtt["port"])), timeout=3)
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
        self.connect("realize", lambda _: self._refresh_startup())

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
        app_group = Adw.PreferencesGroup(title=_("Appearance"))
        box.append(app_group)

        theme_row  = Adw.ActionRow(title=_("Color Scheme"))
        theme_keys = ["system", "light", "dark"]
        theme_lbls = [_("System Default"), _("Light"), _("Dark")]
        theme_combo = Gtk.DropDown(model=Gtk.StringList.new(theme_lbls))
        theme_combo.set_valign(Gtk.Align.CENTER)
        cur = self._prefs.get("theme", "system")
        theme_combo.set_selected(theme_keys.index(cur) if cur in theme_keys else 0)

        def on_theme(c, _):
            k = theme_keys[c.get_selected()]
            self._prefs["theme"] = k
            save_prefs(self._prefs)
            apply_theme(k)

        theme_combo.connect("notify::selected", on_theme)
        theme_row.add_suffix(theme_combo)
        app_group.add(theme_row)

        # ── Idioma ────────────────────────────────────────────────────
        lang_group = Adw.PreferencesGroup(
            title=_("Language"),
            description=_("Restart the app to apply language changes."),
        )
        box.append(lang_group)

        lang_row  = Adw.ActionRow(title=_("App Language"))
        lang_keys = list(i18n.AVAILABLE_LANGUAGES.keys())
        lang_lbls = list(i18n.AVAILABLE_LANGUAGES.values())
        lang_combo = Gtk.DropDown(model=Gtk.StringList.new(lang_lbls))
        lang_combo.set_valign(Gtk.Align.CENTER)
        cur_lang = self._prefs.get("language", "system")
        lang_combo.set_selected(lang_keys.index(cur_lang) if cur_lang in lang_keys else 0)

        def on_lang(c, _):
            k = lang_keys[c.get_selected()]
            self._prefs["language"] = k
            save_prefs(self._prefs)

        lang_combo.connect("notify::selected", on_lang)
        lang_row.add_suffix(lang_combo)
        lang_group.add(lang_row)

        # ── Device Name ───────────────────────────────────────────────
        device_group = Adw.PreferencesGroup(
            title=_("Device"),
            description=_("Name shown in Home Assistant for this machine."),
        )
        box.append(device_group)

        self.device_name_row = Adw.EntryRow(title=_("Device Name"))
        # Carrega o clientId atual do config
        current_name = str(self.config_manager.get("mqtt", "clientId") or
                           self.config_manager.get("mqtt", "prefix") or "")
        if not current_name:
            import socket as _sock
            current_name = _sock.gethostname()
        self.device_name_row.set_text(current_name)

        save_name_btn = Gtk.Button(label=_("Save"))
        save_name_btn.set_valign(Gtk.Align.CENTER)
        save_name_btn.add_css_class("suggested-action")
        save_name_btn.connect("clicked", self._on_save_device_name)
        self.device_name_row.add_suffix(save_name_btn)
        device_group.add(self.device_name_row)

        hint = Gtk.Label(label=_("After changing, restart the LNXlink service for it to take effect."))
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        hint.set_halign(Gtk.Align.START)
        device_group.add(hint)

        # ── Startup ───────────────────────────────────────────────────
        startup_group = Adw.PreferencesGroup(
            title=_("Startup"),
            description=_("Configure which components start automatically when you log in."),
        )
        box.append(startup_group)

        self.gui_startup_row = Adw.SwitchRow(
            title=_("Automa"),
            subtitle=_("Start this control panel on login (~/.config/autostart)"),
        )
        self.gui_startup_row.connect("notify::active", self._on_gui_startup)
        startup_group.add(self.gui_startup_row)

        self.service_startup_row = Adw.SwitchRow(
            title=_("LNXlink Service"),
            subtitle=_("Start lnxlink.service on login (systemctl --user enable)"),
        )
        self.service_startup_row.connect("notify::active", self._on_service_startup)
        startup_group.add(self.service_startup_row)

        self.mqtt_status_row = Adw.ActionRow(
            title=_("MQTT Broker"),
            subtitle=_("Checking connection…"),
        )
        self.mqtt_icon = make_icon("dialog-warning-symbolic", 16)
        self.mqtt_status_row.add_suffix(self.mqtt_icon)
        refresh_btn = Gtk.Button()
        refresh_btn.set_child(make_icon("view-refresh-symbolic"))
        refresh_btn.add_css_class("flat")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.connect("clicked", lambda _: self._refresh_startup())
        self.mqtt_status_row.add_suffix(refresh_btn)
        startup_group.add(self.mqtt_status_row)

        # ── Backup ────────────────────────────────────────────────────
        backup_group = Adw.PreferencesGroup(title=_("Backup & Restore"))
        box.append(backup_group)

        export_row = Adw.ActionRow(
            title=_("Export Configuration"),
            subtitle=_("Save config.yaml to a custom location"),
            activatable=True,
        )
        export_row.add_prefix(make_icon("document-save-symbolic"))
        export_row.connect("activated", self._on_export)
        backup_group.add(export_row)

        import_row = Adw.ActionRow(
            title=_("Import Configuration"),
            subtitle=_("Restore config.yaml from a backup"),
            activatable=True,
        )
        import_row.add_prefix(make_icon("document-open-symbolic"))
        import_row.connect("activated", self._on_import)
        backup_group.add(import_row)

    # ── Device name ───────────────────────────────────────────────────

    def _on_save_device_name(self, _):
        _ = i18n._
        name = self.device_name_row.get_text().strip()
        if not name:
            return
        self.config_manager.set("mqtt", "clientId", name)
        self.config_manager.set("mqtt", "prefix",   name.lower().replace(" ", "_"))
        self.config_manager.save()
        self.show_toast_cb(_("Device name saved. Restart the service to apply."))

    # ── Startup ───────────────────────────────────────────────────────

    def _refresh_startup(self):
        import threading
        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        gui_ok     = is_gui_autostart_enabled()
        service_ok = is_lnxlink_service_autostart_enabled()
        mqtt_ok    = is_mqtt_broker_reachable(self.config_manager)
        GLib.idle_add(self._update_startup_ui, gui_ok, service_ok, mqtt_ok)

    def _update_startup_ui(self, gui_ok, service_ok, mqtt_ok):
        _ = i18n._
        self.gui_startup_row.handler_block_by_func(self._on_gui_startup)
        self.gui_startup_row.set_active(gui_ok)
        self.gui_startup_row.handler_unblock_by_func(self._on_gui_startup)

        self.service_startup_row.handler_block_by_func(self._on_service_startup)
        self.service_startup_row.set_active(service_ok)
        self.service_startup_row.handler_unblock_by_func(self._on_service_startup)

        if mqtt_ok:
            self.mqtt_status_row.set_subtitle(_("Connected ✓"))
            set_icon(self.mqtt_icon, "emblem-ok-symbolic")
        else:
            self.mqtt_status_row.set_subtitle(_("Unreachable — check broker host and port"))
            set_icon(self.mqtt_icon, "dialog-warning-symbolic")
        return GLib.SOURCE_REMOVE

    def _on_gui_startup(self, row, _):
        _ = i18n._
        try:
            set_gui_autostart(row.get_active())
            msg = (_("Automa will start on login.") if row.get_active()
                   else _("Automa removed from startup."))
            self.show_toast_cb(msg)
        except Exception as e:
            self.show_toast_cb(f"Error: {e}", is_error=True)

    def _on_service_startup(self, row, _):
        _ = i18n._
        try:
            action = "enable" if row.get_active() else "disable"
            subprocess.run(_sys_cmd(["systemctl", "--user", action, "lnxlink.service"]),
                           capture_output=True, timeout=5)
            msg = (_("LNXlink service enabled on startup.") if row.get_active()
                   else _("LNXlink service disabled from startup."))
            self.show_toast_cb(msg)
        except Exception as e:
            self.show_toast_cb(f"Error: {e}", is_error=True)

    # ── Backup ────────────────────────────────────────────────────────

    def _get_window(self):
        w = self
        while w:
            if isinstance(w, Gtk.Window): return w
            w = w.get_parent()
        return None

    def _on_export(self, _):
        _ = i18n._
        d = Gtk.FileDialog()
        d.set_title(_("Export Configuration"))
        d.set_initial_name("automa-config-backup.yaml")
        def done(dlg, res):
            try:
                dest = dlg.save_finish(res).get_path()
                shutil.copy2(self.config_manager.config_path, dest)
                self.show_toast_cb(_("Configuration exported to {path}").format(path=dest))
            except GLib.Error: pass
            except Exception as e:
                self.show_toast_cb(_("Error exporting: {error}").format(error=e), is_error=True)
        d.save(self._get_window(), None, done)

    def _on_import(self, _):
        _ = i18n._
        d = Gtk.FileDialog()
        d.set_title(_("Import Configuration"))
        def done(dlg, res):
            try:
                src = dlg.open_finish(res).get_path()
                dest = self.config_manager.config_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                self.config_manager.load()
                self.show_toast_cb(_("Configuration imported successfully!"))
            except GLib.Error: pass
            except Exception as e:
                self.show_toast_cb(_("Error importing: {error}").format(error=e), is_error=True)
        d.open(self._get_window(), None, done)
