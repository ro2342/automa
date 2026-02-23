#!/usr/bin/env python3
"""
LNXlink GUI - Painel de controle GTK4/libadwaita para o LNXlink MQTT agent.
"""

import sys
import os
import signal
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    HAS_INDICATOR = True
except (ValueError, ImportError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3
        HAS_INDICATOR = True
    except (ValueError, ImportError):
        HAS_INDICATOR = False

# i18n: inicializa ANTES de qualquer widget, mas DEPOIS dos imports gi
import i18n
from pages.settings import load_prefs

_prefs = load_prefs()
i18n.setup(_prefs.get("language", "system"))
# NOTA: apply_theme() é chamado em do_startup(), após o Adw.Application existir

from config_manager import ConfigManager
from service_manager import ServiceManager
from installer import is_lnxlink_installed
from pages.dashboard import DashboardPage
from pages.mqtt_config import MqttConfigPage
from pages.sensors import SensorsPage
from pages.commands import CommandsPage
from pages.settings import SettingsPage, apply_theme
from pages.welcome import WelcomePage
from css_loader import load_css

APP_ID      = "io.github.lnxlink.automa"
APP_NAME    = "Automa"
APP_VERSION = "1.0.0"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)


class LNXlinkWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(960, 680)
        self.set_size_request(640, 480)
        self.config_manager  = ConfigManager()
        self.service_manager = ServiceManager()
        self._toast_overlay  = None
        self._build_ui()
        self._connect_signals()
        if not is_lnxlink_installed():
            self._show_welcome()
        else:
            self.config_manager.load()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        _ = i18n._

        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        toolbar_view = Adw.ToolbarView()
        self._toast_overlay.set_child(toolbar_view)

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(title=APP_NAME,
                            subtitle=_("MQTT Agent Control Panel"))
        )
        toolbar_view.add_top_bar(header)

        about_btn = Gtk.Button(icon_name="help-about-symbolic")
        about_btn.set_tooltip_text(_("About"))
        about_btn.connect("clicked", self._on_about)
        header.pack_end(about_btn)

        self.save_btn = Gtk.Button(label=_("Save Config"))
        self.save_btn.add_css_class("suggested-action")
        self.save_btn.connect("clicked", self._on_save_config)
        header.pack_end(self.save_btn)

        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(200)
        self.split_view.set_max_sidebar_width(260)
        toolbar_view.set_content(self.split_view)

        # Sidebar
        sidebar_nav      = Adw.NavigationPage(title="Navigation")
        sidebar_toolbar  = Adw.ToolbarView()
        sidebar_bar      = Adw.HeaderBar()
        sidebar_bar.set_show_end_title_buttons(False)
        sidebar_toolbar.add_top_bar(sidebar_bar)
        sidebar_nav.set_child(sidebar_toolbar)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("navigation-sidebar")

        nav_items = [
            ("go-home-symbolic",            _("Dashboard")),
            ("network-wireless-symbolic",   _("MQTT Config")),
            ("computer-symbolic",           _("Sensors")),
            ("utilities-terminal-symbolic", _("Commands")),
            ("preferences-system-symbolic", _("Settings")),
        ]
        for icon_name, label in nav_items:
            row = Adw.ActionRow()
            row.set_title(label)
            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(16)
            row.add_prefix(img)
            row.set_activatable(True)
            self.list_box.append(row)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.list_box)
        sidebar_toolbar.set_content(scroll)
        self.split_view.set_sidebar(sidebar_nav)

        # Stack de conteúdo
        content_nav = Adw.NavigationPage(title="Content")
        self.stack  = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        content_nav.set_child(self.stack)
        self.split_view.set_content(content_nav)

        self.dashboard_page = DashboardPage(self.service_manager)
        self.mqtt_page      = MqttConfigPage(self.config_manager)
        self.sensors_page   = SensorsPage(self.config_manager,
                                           service_manager=self.service_manager)
        self.commands_page  = CommandsPage(self.config_manager)
        self.settings_page  = SettingsPage(self.config_manager,
                                           show_toast_cb=self._show_toast)

        self.stack.add_named(self.dashboard_page, "dashboard")
        self.stack.add_named(self.mqtt_page,      "mqtt")
        self.stack.add_named(self.sensors_page,   "sensors")
        self.stack.add_named(self.commands_page,  "commands")
        self.stack.add_named(self.settings_page,  "settings")

        self.list_box.select_row(self.list_box.get_row_at_index(0))

    # ------------------------------------------------------------------ #
    #  Welcome dialog                                                      #
    # ------------------------------------------------------------------ #

    def _show_welcome(self):
        self._welcome_dialog = Adw.Dialog()
        self._welcome_dialog.set_title("Configuração Inicial")
        self._welcome_dialog.set_content_width(600)
        self._welcome_dialog.set_content_height(700)
        welcome = WelcomePage(
            on_installed_cb=self._on_lnxlink_installed,
            on_skip_cb=self._on_lnxlink_installed,
        )
        self._welcome_dialog.set_child(welcome)
        self._welcome_dialog.present(self)

    def _on_lnxlink_installed(self):
        self._welcome_dialog.close()
        self.config_manager.load()
        # Atualiza dashboard
        self.dashboard_page.refresh_status()

    # ------------------------------------------------------------------ #
    #  Signals                                                             #
    # ------------------------------------------------------------------ #

    def _connect_signals(self):
        self.list_box.connect("row-selected", self._on_nav_row_selected)
        self.connect("close-request", self._on_close_request)

    def _on_nav_row_selected(self, _lb, row):
        if row is None:
            return
        pages = ["dashboard", "mqtt", "sensors", "commands", "settings"]
        name  = pages[row.get_index()]
        self.stack.set_visible_child_name(name)
        if name == "dashboard":
            self.dashboard_page.refresh_status()

    def _on_save_config(self, _btn):
        _ = i18n._
        try:
            self.mqtt_page.apply_to_config()
            self.sensors_page.apply_to_config()
            self.commands_page.apply_to_config()
            self.config_manager.save()
            self._show_toast(_("Configuration saved successfully!"))
        except Exception as exc:
            self._show_toast(
                _("Error saving config: {error}").format(error=exc),
                is_error=True)

    def _on_close_request(self, _win):
        app = self.get_application()
        if HAS_INDICATOR and hasattr(app, "indicator"):
            self.set_visible(False)
            return True
        return False

    def _on_about(self, _btn):
        Adw.AboutWindow(
            transient_for=self,
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=APP_VERSION,
            developer_name="LNXlink GUI Contributors",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/bkbilly/lnxlink",
            comments="GNOME/GTK4 control panel for the LNXlink MQTT agent.",
        ).present()

    def _show_toast(self, message: str, is_error: bool = False):
        toast = Adw.Toast(title=message, timeout=4)
        self._toast_overlay.add_toast(toast)


class LNXlinkApp(Adw.Application):

    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None
        GLib.set_application_name(APP_NAME)

    def do_startup(self):
        Adw.Application.do_startup(self)
        # Tema aplicado AQUI — após Adw.Application existir, antes da janela
        apply_theme(_prefs.get("theme", "system"))
        # CSS customizado — accent colors + dark/light variants
        load_css()

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self):
        if not self.window:
            self.window = LNXlinkWindow(self)
            self._setup_tray()
        self.window.present()

    def _setup_tray(self):
        if not HAS_INDICATOR:
            return
        self.indicator = AppIndicator3.Indicator.new(
            APP_ID, "network-wireless",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title(APP_NAME)
        menu = Gtk.Menu()
        item = Gtk.MenuItem(label="Mostrar / Ocultar")
        item.connect("activate", lambda _: (
            self.window.set_visible(False) if self.window and self.window.get_visible()
            else self.window.present()))
        menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Sair")
        quit_item.connect("activate", lambda _: self.quit())
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return LNXlinkApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
