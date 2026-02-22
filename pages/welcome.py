"""
pages/welcome.py - Tela de boas-vindas / instalação do LNXlink.

Melhorias:
  - Fecha automaticamente ao terminar a instalação
  - Botão Cancelar funcional (para a thread de instalação)
  - Totalmente traduzida via i18n
"""

import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from installer import LNXlinkInstaller, detect_distro, is_lnxlink_installed


class WelcomePage(Gtk.Box):
    """
    Exibida quando o LNXlink não está instalado.
    on_installed_cb é chamado quando a instalação termina com sucesso,
    para que a janela pai possa fechar este diálogo e mostrar a UI normal.
    """

    def __init__(self, on_installed_cb, on_skip_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_installed_cb = on_installed_cb
        self.on_skip_cb = on_skip_cb or on_installed_cb
        self._installer: LNXlinkInstaller | None = None
        self._installing = False
        self._build_ui()

    def _build_ui(self):
        from i18n import _
        distro = detect_distro()

        self.set_vexpand(True)

        clamp = Adw.Clamp(maximum_size=560)
        clamp.set_valign(Gtk.Align.CENTER)
        clamp.set_vexpand(True)
        clamp.set_margin_top(32)
        clamp.set_margin_bottom(32)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        self.append(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_valign(Gtk.Align.CENTER)
        clamp.set_child(box)

        # Ícone
        icon = Gtk.Image.new_from_icon_name("computer-symbolic")
        icon.set_pixel_size(80)
        icon.add_css_class("dim-label")
        box.append(icon)

        # Título
        title = Gtk.Label(label=_("LNXlink not found"))
        title.add_css_class("title-1")
        title.set_justify(Gtk.Justification.CENTER)
        box.append(title)

        # Subtítulo
        subtitle = Gtk.Label()
        subtitle.set_markup(
            _("LNXlink is not installed on this system.\nDetected distro: {distro}").format(
                distro=f"<b>{distro.name}</b>"
            )
        )
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.set_wrap(True)
        box.append(subtitle)

        # O que será instalado
        steps_group = Adw.PreferencesGroup(title=_("What will be installed:"))
        box.append(steps_group)

        items = [
            ("package-x-generic-symbolic",
             _("System dependencies"),
             _("gcc, cmake and audio libs ({family})").format(family=distro.family)),
            ("application-x-executable-symbolic",
             _("pipx"),
             _("Isolated Python app manager")),
            ("go-home-symbolic",
             "LNXlink",
             "MQTT agent for Home Assistant"),
        ]
        for icon_name, row_title, row_sub in items:
            row = Adw.ActionRow(title=row_title, subtitle=row_sub)
            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(16)
            row.add_prefix(img)
            steps_group.add(row)

        # Aviso sudo
        Adw.Banner(
            title=_("⚠ Installation requires sudo privileges to install system packages."),
            revealed=True,
        )

        # --- Área de progresso (oculta inicialmente) ---
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.progress_box.set_visible(False)
        box.append(self.progress_box)

        self.progress_label = Gtk.Label(label=_("Preparing..."))
        self.progress_label.add_css_class("caption")
        self.progress_label.set_wrap(True)
        self.progress_box.append(self.progress_label)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(False)
        self.progress_box.append(self.progress_bar)

        # Mensagem de erro
        self.error_label = Gtk.Label()
        self.error_label.set_visible(False)
        self.error_label.add_css_class("error")
        self.error_label.set_wrap(True)
        self.error_label.set_justify(Gtk.Justification.CENTER)
        self.error_label.set_selectable(True)  # usuário pode copiar o erro
        box.append(self.error_label)

        # --- Botões ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        box.append(btn_box)

        self.skip_btn = Gtk.Button(label=_("Skip (LNXlink already installed)"))
        self.skip_btn.connect("clicked", self._on_skip)
        btn_box.append(self.skip_btn)

        self.cancel_btn = Gtk.Button(label=_("Cancel"))
        self.cancel_btn.set_visible(False)
        self.cancel_btn.connect("clicked", self._on_cancel)
        btn_box.append(self.cancel_btn)

        self.install_btn = Gtk.Button(label=_("Install Automatically"))
        self.install_btn.add_css_class("suggested-action")
        self.install_btn.add_css_class("pill")
        self.install_btn.connect("clicked", self._on_install)
        btn_box.append(self.install_btn)

        # Link manual
        manual_btn = Gtk.LinkButton(
            uri="https://github.com/bkbilly/lnxlink#installation",
            label=_("View manual installation on GitHub"),
        )
        manual_btn.set_halign(Gtk.Align.CENTER)
        box.append(manual_btn)

    # ------------------------------------------------------------------ #
    #  Ações                                                               #
    # ------------------------------------------------------------------ #

    def _on_skip(self, _btn):
        self.on_skip_cb()

    def _on_cancel(self, _btn):
        if self._installer:
            self._installer.cancel()
        self._set_installing(False)
        self.progress_box.set_visible(False)
        self.error_label.set_visible(False)

    def _on_install(self, _btn):
        if self._installing:
            return
        self._set_installing(True)
        self.error_label.set_visible(False)
        self.progress_box.set_visible(True)
        self.progress_bar.set_fraction(0)

        self._installer = LNXlinkInstaller(progress_cb=self._on_progress)
        threading.Thread(
            target=self._install_thread,
            args=(self._installer,),
            daemon=True,
        ).start()

    def _install_thread(self, installer: LNXlinkInstaller):
        success, message = installer.install()
        GLib.idle_add(self._on_install_done, success, message)

    # ------------------------------------------------------------------ #
    #  Callbacks de progresso (chamados via GLib.idle_add)                #
    # ------------------------------------------------------------------ #

    def _on_progress(self, msg: str, pct: int):
        GLib.idle_add(self._update_progress_ui, msg, pct / 100.0)

    def _update_progress_ui(self, msg: str, fraction: float):
        self.progress_label.set_label(msg)
        self.progress_bar.set_fraction(fraction)
        return GLib.SOURCE_REMOVE

    def _on_install_done(self, success: bool, message: str):
        self._set_installing(False)

        if success:
            # Atualiza barra pra 100% por um instante antes de fechar
            self.progress_bar.set_fraction(1.0)
            self.progress_label.set_label(message)
            # Fecha automaticamente após 1.5 segundos
            GLib.timeout_add(1500, self._auto_close)
        else:
            self.progress_box.set_visible(False)
            self.error_label.set_label(f"❌ {message}")
            self.error_label.set_visible(True)

        return GLib.SOURCE_REMOVE

    def _auto_close(self):
        """Chamado pelo timer após instalação bem-sucedida."""
        self.on_installed_cb()
        return GLib.SOURCE_REMOVE  # não repete o timer

    def _set_installing(self, installing: bool):
        self._installing = installing
        self.install_btn.set_visible(not installing)
        self.skip_btn.set_visible(not installing)
        self.cancel_btn.set_visible(installing)
