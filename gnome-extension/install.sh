#!/bin/bash
# Instala a extensão Automa localmente

EXT_ID="automa@automa.github.io"
DEST="$HOME/.local/share/gnome-shell/extensions/$EXT_ID"

echo "Instalando extensão Automa..."
mkdir -p "$DEST"
cp -r "$(dirname "$0")/$EXT_ID/"* "$DEST/"

echo "Habilitando extensão..."
gnome-extensions enable "$EXT_ID" 2>/dev/null || \
    gsettings set org.gnome.shell enabled-extensions \
        "$(gsettings get org.gnome.shell enabled-extensions | sed "s/]/, '$EXT_ID']/")"

echo ""
echo "✓ Extensão instalada em $DEST"
echo "  Reinicie o GNOME Shell para ativar:"
echo "  • Wayland: faça logout e login novamente"
echo "  • X11:     pressione Alt+F2, digite 'r', Enter"
