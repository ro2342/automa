"""
pages/dashboard.py - Dashboard: status do serviço e controles.

CORREÇÕES:
  - refresh_status() SÓ consulta — nunca chama start/stop/enable/disable
  - autostart toggle usa flag _loading para não disparar ações durante refresh
  - _on_action_done não chama refresh se foi cancelado
"""

import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from service_manager import ServiceManager, ServiceStatus


STATUS_STYLES = {
    ServiceStatus.RUNNING: ("●  Running", "service-status-running"),
    ServiceStatus.STOPPED: ("●  Stopped", "service-status-stopped"),
    ServiceStatus.FAILED:  ("●  Failed",  "service-status-failed"),
    ServiceStatus.UNKNOWN: ("●  Unknown", "service-status-unknown"),
}


class DashboardPage(Gtk.Box):

    def __init__(self, service_manager: ServiceManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.service_manager = service_manager
        self._busy    = False
        self._loading = False  # flag para bloquear handlers durante refresh

        self._build_ui()
        self.connect("realize", lambda _: self.refresh_status())

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        clamp = Adw.Clamp(maximum_size=700, tightening_threshold=500)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        self.append(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(outer)

        # ── Status ──────────────────────────────────────────────────
        status_group = Adw.PreferencesGroup(title="Service Status")
        outer.append(status_group)

        status_row = Adw.ActionRow(title="lnxlink.service")
        status_group.add(status_row)

        self.status_label = Gtk.Label(label="● Checking…")
        self.status_label.set_halign(Gtk.Align.END)
        self.status_label.set_valign(Gtk.Align.CENTER)
        status_row.add_suffix(self.status_label)

        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.END)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)
        status_row.add_suffix(self.spinner)

        # ── Controles ───────────────────────────────────────────────
        controls_group = Adw.PreferencesGroup(title="Controls")
        outer.append(controls_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(8)

        self.btn_start   = self._make_btn("Start",   "media-playback-start-symbolic", "suggested-action")
        self.btn_stop    = self._make_btn("Stop",    "media-playback-stop-symbolic",  "destructive-action")
        self.btn_restart = self._make_btn("Restart", "view-refresh-symbolic",          "")

        self.btn_start.connect("clicked",   self._on_start)
        self.btn_stop.connect("clicked",    self._on_stop)
        self.btn_restart.connect("clicked", self._on_restart)

        btn_box.append(self.btn_start)
        btn_box.append(self.btn_stop)
        btn_box.append(self.btn_restart)

        btn_row = Adw.ActionRow()
        btn_row.set_child(btn_box)
        controls_group.add(btn_row)

        # Autostart toggle — Start on Login
        self.autostart_row = Adw.SwitchRow(
            title="Start on Login",
            subtitle="Enable lnxlink.service as a systemd user unit",
        )
        self.autostart_row.connect("notify::active", self._on_autostart_toggled)
        controls_group.add(self.autostart_row)

        # Refresh manual
        refresh_row = Adw.ActionRow(title="Refresh Status", activatable=True)
        refresh_row.set_icon_name("view-refresh-symbolic")
        refresh_row.connect("activated", lambda _: self.refresh_status())
        controls_group.add(refresh_row)

        # ── Log de detalhes ─────────────────────────────────────────
        log_group = Adw.PreferencesGroup(title="Service Detail")
        outer.append(log_group)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(180)
        scroll.set_max_content_height(300)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.add_css_class("status-log")
        self.log_view.set_margin_start(8)
        self.log_view.set_margin_end(8)
        self.log_view.set_margin_top(4)
        self.log_view.set_margin_bottom(4)
        scroll.set_child(self.log_view)

        log_row = Adw.ActionRow()
        log_row.set_child(scroll)
        log_group.add(log_row)

    def _make_btn(self, label, icon, style):
        btn = Gtk.Button(label=label)
        btn.set_icon_name(icon)
        btn.add_css_class("control-btn")
        if style:
            btn.add_css_class(style)
        return btn

    # ------------------------------------------------------------------ #
    #  Status refresh (SOMENTE leitura — nunca chama start/stop)          #
    # ------------------------------------------------------------------ #

    def refresh_status(self):
        if self._busy:
            return
        self._set_busy(True)
        threading.Thread(target=self._fetch_status_thread, daemon=True).start()

    def _fetch_status_thread(self):
        status  = self.service_manager.get_status()
        detail  = self.service_manager.get_status_text()
        enabled = self.service_manager.is_enabled()
        GLib.idle_add(self._update_status_ui, status, detail, enabled)

    def _update_status_ui(self, status, detail, enabled):
        text, css = STATUS_STYLES[status]

        for cls in ("service-status-running", "service-status-stopped",
                    "service-status-failed", "service-status-unknown"):
            self.status_label.remove_css_class(cls)

        self.status_label.set_label(text)
        self.status_label.add_css_class(css)

        self.log_view.get_buffer().set_text(detail)

        # Atualiza o toggle de autostart SEM disparar _on_autostart_toggled
        self._loading = True
        self.autostart_row.set_active(enabled)
        self._loading = False

        self._set_busy(False)
        return GLib.SOURCE_REMOVE

    def _set_busy(self, busy):
        self._busy = busy
        GLib.idle_add(self.spinner.set_visible, busy)
        GLib.idle_add(self.spinner.start if busy else self.spinner.stop)
        for btn in (self.btn_start, self.btn_stop, self.btn_restart):
            GLib.idle_add(btn.set_sensitive, not busy)

    # ------------------------------------------------------------------ #
    #  Botões de controle                                                  #
    # ------------------------------------------------------------------ #

    def _on_start(self, _btn):
        self._dispatch(self.service_manager.start, "Start")

    def _on_stop(self, _btn):
        self._dispatch(self.service_manager.stop, "Stop")

    def _on_restart(self, _btn):
        self._dispatch(self.service_manager.restart, "Restart")

    def _dispatch(self, action_fn, name):
        if self._busy:
            return
        self._set_busy(True)

        def _thread():
            success, msg = action_fn()
            GLib.idle_add(self._on_action_done, success, msg, name)

        threading.Thread(target=_thread, daemon=True).start()

    def _on_action_done(self, success, msg, name):
        import logging
        logging.getLogger(__name__).info("%s %s: %s",
            name, "succeeded" if success else "failed", msg or "")
        self._set_busy(False)
        # Aguarda um pouco para o serviço estabilizar antes de verificar status
        GLib.timeout_add(800, self._delayed_refresh)
        return GLib.SOURCE_REMOVE

    def _delayed_refresh(self):
        self.refresh_status()
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------ #
    #  Autostart toggle                                                    #
    # ------------------------------------------------------------------ #

    def _on_autostart_toggled(self, row, _param):
        # Ignora durante refresh — evita loop de enable/disable
        if self._loading or self._busy:
            return
        enabled = row.get_active()
        action = self.service_manager.enable if enabled else self.service_manager.disable
        self._dispatch(action, "Enable" if enabled else "Disable")
