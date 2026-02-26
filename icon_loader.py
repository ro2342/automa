"""
icon_loader.py — Carrega ícones simbólicos do diretório bundled data/icons/.

Registra data/icons/ no Gtk.IconTheme padrão para que todos os ícones
sejam encontrados por nome e herdem cor automaticamente em qualquer
contexto GTK (prefix de EntryRow, botões, sidebar, etc.).

Uso:
  - Chamar register_icon_theme() UMA VEZ em do_startup() do app (main.py)
  - Depois usar make_icon() e set_icon() normalmente em qualquer widget
"""

from pathlib import Path
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

_ICONS_DIR = Path(__file__).parent / "data" / "icons"
_registered = False


def register_icon_theme():
    """
    Registra data/icons/ no IconTheme padrão.
    DEVE ser chamado em do_startup() do Adw.Application, antes de
    qualquer widget ser criado. Executa uma só vez.
    """
    global _registered
    if _registered:
        return
    display = Gdk.Display.get_default()
    if display and _ICONS_DIR.is_dir():
        theme = Gtk.IconTheme.get_for_display(display)
        theme.add_search_path(str(_ICONS_DIR))
        _registered = True


def _ensure_registered():
    """Fallback: tenta registrar se ainda não foi feito."""
    if not _registered:
        register_icon_theme()


def make_icon(name: str, size: int = 16) -> Gtk.Image:
    """
    Retorna um Gtk.Image para o ícone simbólico dado.
    O ícone herda a cor do tema automaticamente (currentColor no SVG).
    valign=CENTER evita o warning de baseline do GTK4.
    """
    _ensure_registered()
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    img.set_valign(Gtk.Align.CENTER)
    return img


def set_icon(image: Gtk.Image, name: str, size: int = 16):
    """Atualiza um Gtk.Image existente com o ícone dado."""
    _ensure_registered()
    image.set_from_icon_name(name)
    image.set_pixel_size(size)
    image.set_valign(Gtk.Align.CENTER)
