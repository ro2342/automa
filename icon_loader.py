"""
icon_loader.py — Carrega ícones simbólicos do diretório bundled data/icons/.
Garante compatibilidade com o sandbox Flatpak onde os ícones do sistema
podem não estar disponíveis.
"""

import os
from pathlib import Path
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio

# Caminho absoluto para data/icons/ relativo a este arquivo
_ICONS_DIR = Path(__file__).parent / "data" / "icons"


def make_icon(name: str, size: int = 16) -> Gtk.Image:
    """
    Retorna um Gtk.Image para o ícone simbólico dado.
    Tenta carregar do diretório bundled primeiro, depois fallback para o tema.
    O ícone herda a cor do texto automaticamente (currentColor no SVG).
    """
    icon_file = _ICONS_DIR / f"{name}.svg"
    if icon_file.exists():
        paintable = Gtk.IconPaintable.new_for_file(
            Gio.File.new_for_path(str(icon_file)), size, 1
        )
        img = Gtk.Image.new_from_paintable(paintable)
    else:
        img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    return img


def set_icon(image: Gtk.Image, name: str, size: int = 16):
    """Atualiza um Gtk.Image existente com o ícone dado."""
    icon_file = _ICONS_DIR / f"{name}.svg"
    if icon_file.exists():
        paintable = Gtk.IconPaintable.new_for_file(
            Gio.File.new_for_path(str(icon_file)), size, 1
        )
        image.set_from_paintable(paintable)
    else:
        image.set_from_icon_name(name)
    image.set_pixel_size(size)
