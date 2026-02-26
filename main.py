#!/usr/bin/env python3
"""
LNXlink GUI - Painel de controle GTK4/libadwaita para o LNXlink MQTT agent.
"""

import sys
import os
import signal
import logging
import time

# ── Logging com cores e timestamps ─────────────────────────────────────────
_START_TIME = time.monotonic()

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BLUE   = "\033[34m"

LEVEL_COLORS = {
    "DEBUG":    DIM + BLUE,
    "INFO":     GREEN,
    "WARNING":  YELLOW,
    "ERROR":    RED,
    "CRITICAL": BOLD + RED,
}


class _ColorFormatter(logging.Formatter):
    def format(self, record):
        elapsed = time.monotonic() - _START_TIME
        color   = LEVEL_COLORS.get(record.levelname, "")
        level   = f"{color}{record.levelname:<8}{RESET}"
        name    = f"{DIM}{record.name}{RESET}"
        t       = f"{DIM}+{elapsed:05.2f}s{RESET}"
        msg     = super().format(record)
        # Extrai só a mensagem formatada (sem level/name do formatter padrão)
        record.getMessage()
        plain_msg = record.getMessage()
        if record.exc_info:
            plain_msg += "\n" + self.formatException(record.exc_info)
        return f"{t} {level} {name}: {plain_msg}"


def _setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)

    # Usa cores só se o terminal suportar
    if sys.stderr.isatty():
        handler.setFormatter(_ColorFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root.addHandler(handler)

    # Silencia loggers muito verbosos de terceiros
    for noisy in ("gi.repository", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
log = logging.getLogger(__name__)

log.info("━━━ Automa starting ━━━")
log.debug("Python %s | pid %d", sys.version.split()[0], os.getpid())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

log.debug("Importing GTK/Adwaita…")
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
log.debug("GTK %d.%d | Adw %d.%d",
    Gtk.get_major_version(), Gtk.get_minor_version(),
    Adw.VERSION_S and 0 or Adw.get_major_version(),
    Adw.get_minor_version() if hasattr(Adw, "get_minor_version") else 0,
)

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

import i18n
from pages.settings import load_prefs, apply_theme

_prefs = load_prefs()
i18n.setup(_prefs.get("language", "system"))

from config_manager import ConfigManager
from service_manager import ServiceManager
from installer import is_lnxlink_installed
from pages.dashboard import DashboardPage
from pages.mqtt_config import MqttConfigPage
from pages.sensors import SensorsPage
from pages.commands import CommandsPage
from pages.settings import SettingsPage
from pages.welcome import WelcomePage
from css_loader import load_css
from icon_loader import make_icon, set_icon, register_icon_theme

APP_ID      = "io.github.ro2342.automa"
APP_NAME    = "Automa"
APP_VERSION = "1.0.20"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

# Nomes das páginas para o título contextual do header
PAGE_TITLES = {
    "dashboard": "Dashboard",
    "mqtt":      "MQTT Config",
    "sensors":   "Sensors",
    "commands":  "Commands",
    "settings":  "Settings",
}


class LNXlinkWindow(Adw.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(960, 680)
        self.set_size_request(640, 480)
        self.config_manager  = ConfigManager()
        self.service_manager = ServiceManager()
        self._toast_overlay  = None
        self._current_page   = "dashboard"
        self._build_ui()
        self._connect_signals()
        if not is_lnxlink_installed():
            self._show_welcome()
        else:
            self.config_manager.load()

    # ------------------------------------------------------------------ #
    #  UI — estrutura moderna GNOME (sem título no header, menu hamburguer)
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        _ = i18n._

        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # OverlaySplitView: sidebar sobreposta em mobile, fixa em desktop
        self.split_view = Adw.OverlaySplitView()
        self.split_view.set_min_sidebar_width(200)
        self.split_view.set_max_sidebar_width(260)
        self.split_view.set_sidebar_width_fraction(0.25)
        self._toast_overlay.set_child(self.split_view)

        # ── Sidebar ──────────────────────────────────────────────────
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_bar     = Adw.HeaderBar()
        sidebar_bar.set_show_end_title_buttons(False)
        # Nome do app na sidebar (padrão GNOME moderno)
        sidebar_bar.set_title_widget(Gtk.Label(label=APP_NAME))
        sidebar_toolbar.add_top_bar(sidebar_bar)

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
            img = make_icon(icon_name)
            img.add_css_class("dim-label")
            row.add_prefix(img)
            row.set_activatable(True)
            self.list_box.append(row)

        sidebar_scroll = Gtk.ScrolledWindow(vexpand=True)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_child(self.list_box)
        sidebar_toolbar.set_content(sidebar_scroll)
        self.split_view.set_sidebar(sidebar_toolbar)

        # ── Conteúdo ─────────────────────────────────────────────────
        content_toolbar = Adw.ToolbarView()

        # Header do conteúdo — título contextual + menu hamburguer
        content_bar = Adw.HeaderBar()
        content_bar.set_show_start_title_buttons(False)

        # Botão hamburguer (abre sidebar em modo mobile / tela pequena)
        toggle_btn = Gtk.ToggleButton()
        toggle_btn.set_child(make_icon("sidebar-show-symbolic"))
        toggle_btn.set_tooltip_text("Toggle Sidebar")
        toggle_btn.set_active(True)
        toggle_btn.connect("toggled", lambda btn: self.split_view.set_show_sidebar(btn.get_active()))
        content_bar.pack_start(toggle_btn)

        # Título contextual que muda conforme a página
        self._page_title = Adw.WindowTitle(title="Dashboard")
        content_bar.set_title_widget(self._page_title)

        # Menu ☰ (kebab/hamburger menu) no canto direito
        menu_btn = Gtk.MenuButton()
        menu_btn.set_child(make_icon("open-menu-symbolic"))
        menu_btn.set_tooltip_text("Menu")
        menu = Gio.Menu()
        menu.append(_("Save Config"),      "win.save_config")
        menu.append(_("Setup Assistant"),  "win.setup_assistant")
        menu.append(_("About"),            "win.about")
        menu.append(_("Quit"),             "app.quit")
        menu_btn.set_menu_model(menu)
        content_bar.pack_end(menu_btn)

        content_toolbar.add_top_bar(content_bar)

        # Stack de páginas
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        content_toolbar.set_content(self.stack)
        self.split_view.set_content(content_toolbar)

        # Instancia as páginas
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

        # Actions da janela para o menu
        self._setup_window_actions()

    def _setup_window_actions(self):
        _ = i18n._

        save_action = Gio.SimpleAction.new("save_config", None)
        save_action.connect("activate", lambda *_: self._on_save_config())
        self.add_action(save_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", lambda *_: self._on_about())
        self.add_action(about_action)

        setup_action = Gio.SimpleAction.new("setup_assistant", None)
        setup_action.connect("activate", lambda *_: self._show_welcome())
        self.add_action(setup_action)

    # ------------------------------------------------------------------ #
    #  Welcome dialog                                                      #
    # ------------------------------------------------------------------ #

    def _show_welcome(self):
        # Fecha o dialog anterior se ainda estiver aberto
        if hasattr(self, "_welcome_dialog") and self._welcome_dialog:
            try:
                self._welcome_dialog.close()
            except Exception:
                pass
        self._welcome_dialog = Adw.Dialog()
        self._welcome_dialog.set_title("Setup Assistant")
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
        self._current_page = name
        self.stack.set_visible_child_name(name)
        # Atualiza título contextual do header
        self._page_title.set_title(PAGE_TITLES.get(name, APP_NAME))
        if name == "dashboard":
            self.dashboard_page.refresh_status()

    def _on_save_config(self):
        _ = i18n._
        try:
            self.mqtt_page.apply_to_config()
            self.sensors_page.apply_to_config()
            self.commands_page.apply_to_config()
            self.config_manager.save()
            self.service_manager.restart()
            self._show_toast(_("Configuration saved and service restarted!"))
            GLib.timeout_add(2000, lambda: (self.dashboard_page.refresh_status(), GLib.SOURCE_REMOVE)[1])
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

    def _on_about(self):
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
        apply_theme(_prefs.get("theme", "system"))
        register_icon_theme()  # registra data/icons/ no IconTheme
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
