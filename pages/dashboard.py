"""
pages/dashboard.py - Dashboard: status do serviço e controles.
Todas as strings via i18n._().
"""

import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from service_manager import ServiceManager, ServiceStatus
import i18n


class DashboardPage(Gtk.Box):

    def __init__(self, service_manager: ServiceManager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.service_manager = service_manager
        self._busy    = False
        self._loading = False
        self._build_ui()
        self.connect("realize", lambda _: self.refresh_status())

    def _build_ui(self):
        _ = i18n._

        clamp = Adw.Clamp(maximum_size=700, tightening_threshold=500)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        self.append(clamp)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        clamp.set_child(outer)

        # ── Status ──────────────────────────────────────────────────
        status_group = Adw.PreferencesGroup(title=_("Service Status"))
        outer.append(status_group)

        status_row = Adw.ActionRow(title="lnxlink.service")
        status_group.add(status_row)

        self.status_label = Gtk.Label(label=_("● Checking…"))
        self.status_label.set_halign(Gtk.Align.END)
        self.status_label.set_valign(Gtk.Align.CENTER)
        status_row.add_suffix(self.status_label)

        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.END)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)
        status_row.add_suffix(self.spinner)

        # ── Controles ───────────────────────────────────────────────
        controls_group = Adw.PreferencesGroup(title=_("Controls"))
        outer.append(controls_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(8)

        self.btn_start   = self._make_btn(_("Start"),   "media-playback-start-symbolic", "suggested-action")
        self.btn_stop    = self._make_btn(_("Stop"),    "media-playback-stop-symbolic",  "destructive-action")
        self.btn_restart = self._make_btn(_("Restart"), "view-refresh-symbolic",          "")

        self.btn_start.connect("clicked",   self._on_start)
        self.btn_stop.connect("clicked",    self._on_stop)
        self.btn_restart.connect("clicked", self._on_restart)

        btn_box.append(self.btn_start)
        btn_box.append(self.btn_stop)
        btn_box.append(self.btn_restart)

        btn_row = Adw.ActionRow()
        btn_row.set_child(btn_box)
        controls_group.add(btn_row)

        self.autostart_row = Adw.SwitchRow(
            title=_("Start on Login"),
            subtitle=_("Enable lnxlink.service as a systemd user unit"),
        )
        self.autostart_row.connect("notify::active", self._on_autostart_toggled)
        controls_group.add(self.autostart_row)

        refresh_row = Adw.ActionRow(title=_("Refresh Status"), activatable=True)
        refresh_row.set_icon_name("view-refresh-symbolic")
        refresh_row.connect("activated", lambda _: self.refresh_status())
        controls_group.add(refresh_row)

        # ── Log ─────────────────────────────────────────────────────
        log_group = Adw.PreferencesGroup(title=_("Service Detail"))
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

    def refresh_status(self):
        if self._busy:
            return
        self._set_busy(True)
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        status  = self.service_manager.get_status()
        detail  = self.service_manager.get_status_text()
        enabled = self.service_manager.is_enabled()
        GLib.idle_add(self._update_ui, status, detail, enabled)

    def _update_ui(self, status, detail, enabled):
        _ = i18n._
        labels = {
            ServiceStatus.RUNNING: (_("● Running"), "service-status-running"),
            ServiceStatus.STOPPED: (_("● Stopped"), "service-status-stopped"),
            ServiceStatus.FAILED:  (_("● Failed"),  "service-status-failed"),
            ServiceStatus.UNKNOWN: (_("● Unknown"), "service-status-unknown"),
        }
        text, css = labels[status]
        for cls in ("service-status-running", "service-status-stopped",
                    "service-status-failed", "service-status-unknown"):
            self.status_label.remove_css_class(cls)
        self.status_label.set_label(text)
        self.status_label.add_css_class(css)
        self.log_view.get_buffer().set_text(detail)

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

    def _on_start(self, _):   self._dispatch(self.service_manager.start,   "Start")
    def _on_stop(self, _):    self._dispatch(self.service_manager.stop,    "Stop")
    def _on_restart(self, _): self._dispatch(self.service_manager.restart, "Restart")

    def _dispatch(self, fn, name):
        if self._busy: return
        self._set_busy(True)
        threading.Thread(target=lambda: GLib.idle_add(
            self._on_done, *fn(), name), daemon=True).start()

    def _on_done(self, success, msg, name):
        self._set_busy(False)
        GLib.timeout_add(800, lambda: (self.refresh_status(), GLib.SOURCE_REMOVE)[1])
        return GLib.SOURCE_REMOVE

    def _on_autostart_toggled(self, row, _):
        if self._loading or self._busy: return
        fn = self.service_manager.enable if row.get_active() else self.service_manager.disable
        self._dispatch(fn, "autostart")
