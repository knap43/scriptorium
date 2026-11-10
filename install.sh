#!/usr/bin/env bash
# Install Scriptorium for the current user (no root needed).
set -euo pipefail

src="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.local/share/scriptorium"
apps="$HOME/.local/share/applications"

mkdir -p "$dest" "$apps" "$HOME/.local/bin"
cp "$src/scriptorium.py" "$src/glyphs.py" "$dest/"
chmod +x "$dest/scriptorium.py"
ln -sf "$dest/scriptorium.py" "$HOME/.local/bin/scriptorium"

cat > "$apps/io.github.knap43.Scriptorium.desktop" <<EOF
[Desktop Entry]
Name=Scriptorium
Comment=Write the conlang syllabary
Exec=python3 $dest/scriptorium.py
Icon=accessories-text-editor-symbolic
Terminal=false
Type=Application
Categories=Utility;TextEditor;GTK;
StartupWMClass=io.github.knap43.Scriptorium
EOF

echo "Installed. Launch Scriptorium from the app grid, or run: scriptorium"
