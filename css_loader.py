"""
css_loader.py - Carrega o style.css customizado do app.

Deve ser chamado UMA VEZ após o Adw.Application iniciar,
antes de criar qualquer widget.

O libadwaita já fornece suporte automático a:
  - Dark/Light mode via Adw.StyleManager
  - Accent colors do GNOME via variáveis CSS (@accent_color etc)

Nosso CSS apenas complementa com classes específicas do app,
usando essas mesmas variáveis para integração perfeita.
"""

import logging
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

log = logging.getLogger(__name__)

_CSS_PATH = Path(__file__).parent / "style.css"


def load_css():
    """
    Carrega o style.css e registra como provider de alta prioridade.
    Seguro chamar múltiplas vezes (idempotente).
    """
    if not _CSS_PATH.exists():
        log.warning("style.css não encontrado em %s", _CSS_PATH)
        return

    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(str(_CSS_PATH))
    except Exception as exc:
        log.error("Erro ao carregar CSS: %s", exc)
        return

    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        log.info("CSS carregado de %s", _CSS_PATH)
