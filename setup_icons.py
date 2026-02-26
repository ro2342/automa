#!/usr/bin/env python3
"""
setup_icons.py — Prepara os ícones bundled e limpa ~/Downloads.

Execute uma vez após clonar/atualizar o repositório:
  cd ~/lnxlink-gui
  python3 setup_icons.py

O que faz:
  1. Converte todos os SVGs em data/icons/ para usar currentColor
     (necessário para seguir o tema dark/light do GNOME automaticamente)
  2. Copia ícones que possam estar faltando do sistema Adwaita
  3. Limpa arquivos .py antigos de ~/Downloads
"""

import re
import sys
import shutil
from pathlib import Path

BASE      = Path(__file__).parent
ICONS_DIR = BASE / "data" / "icons"

FILL_RE   = re.compile(r'\bfill="(?!none)[^"]*"')
STROKE_RE = re.compile(r'\bstroke="(?!none)[^"]*"')

# ── 1. Copia ícones que podem estar faltando ────────────────────────

REQUIRED_ICONS = [
    "applications-system-symbolic",
    "computer-symbolic",
    "dialog-warning-symbolic",
    "document-edit-symbolic",
    "document-open-symbolic",
    "document-save-symbolic",
    "emblem-ok-symbolic",
    "folder-symbolic",
    "go-home-symbolic",
    "list-add-symbolic",
    "media-playback-start-symbolic",
    "media-playback-stop-symbolic",
    "network-wireless-symbolic",
    "open-menu-symbolic",
    "preferences-system-symbolic",
    "sidebar-show-symbolic",
    "user-trash-symbolic",
    "utilities-terminal-symbolic",
    "view-refresh-symbolic",
    # MQTT Config icons
    "network-server-symbolic",
    "avatar-default-symbolic",
    "dialog-password-symbolic",
    "text-x-generic-symbolic",
]

ADWAITA_DIRS = [
    Path("/usr/share/icons/Adwaita/symbolic"),
    Path("/usr/share/icons/hicolor/symbolic"),
]

ICONS_DIR.mkdir(parents=True, exist_ok=True)
copied_missing = []

for icon in REQUIRED_ICONS:
    dest = ICONS_DIR / f"{icon}.svg"
    if dest.exists():
        continue
    for base_dir in ADWAITA_DIRS:
        found = list(base_dir.rglob(f"{icon}.svg"))
        if found:
            shutil.copy2(found[0], dest)
            copied_missing.append(icon)
            break
    else:
        print(f"  ⚠ não encontrado no sistema: {icon}")

if copied_missing:
    print(f"✓ Copiados {len(copied_missing)} ícones faltando: {', '.join(copied_missing)}")

# ── 2. Converte todos os SVGs para currentColor ─────────────────────

converted = []
already   = []

for svg in sorted(ICONS_DIR.glob("*.svg")):
    text = svg.read_text(encoding="utf-8")
    original = text

    text = FILL_RE.sub('fill="currentColor"', text)
    text = STROKE_RE.sub('stroke="currentColor"', text)

    if 'style="color:inherit"' not in text and "<svg" in text:
        text = text.replace("<svg ", '<svg style="color:inherit" ', 1)

    if text != original:
        svg.write_text(text, encoding="utf-8")
        converted.append(svg.name)
    else:
        already.append(svg.name)

print(f"✓ {len(converted)} SVGs convertidos para currentColor")
if converted:
    for name in converted:
        print(f"    {name}")
print(f"  {len(already)} já estavam corretos")

# ── 3. Limpa ~/Downloads ────────────────────────────────────────────

downloads = Path.home() / "Downloads"
CLEANUP_FILES = [
    "main.py", "settings.py", "commands.py", "mqtt_config.py",
    "icon_loader.py", "installer.py", "service_manager.py",
    "welcome.py", "dashboard.py", "sensors.py", "setup_icons.py",
    "css_loader.py", "config_manager.py", "i18n.py",
]

removed = []
for fname in CLEANUP_FILES:
    f = downloads / fname
    if f.exists():
        f.unlink()
        removed.append(fname)

if removed:
    print(f"\n✓ Removidos {len(removed)} arquivo(s) antigos de ~/Downloads:")
    for name in removed:
        print(f"    {name}")
else:
    print(f"\n✓ ~/Downloads já estava limpo")

print("\n✅ Pronto!")
