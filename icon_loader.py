"""
icon_loader.py — Carrega ícones simbólicos do diretório bundled data/icons/.

Registra data/icons/ no Gtk.IconTheme padrão para que todos os ícones
sejam encontrados por nome e herdem cor automaticamente em qualquer
contexto GTK (prefix de EntryRow, botões, sidebar, etc.).
"""

from pathlib import Path
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

_ICONS_DIR = Path(__file__).parent / "data" / "icons"
_registered = False


def _ensure_registered():
    """Registra data/icons/ no IconTheme padrão (executa uma só vez)."""
    global _registered
    if _registered:
        return
    display = Gdk.Display.get_default()
    if display and _ICONS_DIR.is_dir():
        theme = Gtk.IconTheme.get_for_display(display)
        theme.add_search_path(str(_ICONS_DIR))
    _registered = True


def make_icon(name: str, size: int = 16) -> Gtk.Image:
    """
    Retorna um Gtk.Image para o ícone simbólico dado.
    O ícone herda a cor do tema automaticamente (currentColor no SVG).
    """
    _ensure_registered()
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    return img


def set_icon(image: Gtk.Image, name: str, size: int = 16):
    """Atualiza um Gtk.Image existente com o ícone dado."""
    _ensure_registered()
    image.set_from_icon_name(name)
    image.set_pixel_size(size)
