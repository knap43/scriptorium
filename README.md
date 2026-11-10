# Scriptorium

A small GTK 4 / libadwaita app for writing the conlang syllabary.

## Requirements (Arch)

```fish
sudo pacman -S --needed python-gobject gtk4 libadwaita python-cairo
```

## Run or install

```fish
python3 scriptorium.py      # run in place
bash install.sh             # install for your user, with an app-grid entry
```

## Writing

Glyphs are written in columns, top to bottom, and columns run left to right.

| Action | Click | Key |
|---|---|---|
| Consonant frame | consonant key | its letter |
| Vowel | vowel key | a e i o u |
| Single stroke beneath (space) | Space | Space |
| Double stroke beneath (full stop) | Full stop | . |
| New column | New column | Enter |
| Erase | ⌫ | Backspace |

A vowel fills the last consonant frame if it is still empty. Otherwise it
starts a vowel-only glyph. Pressing a stroke key again removes the stroke.
Backspace removes a stroke first, then a vowel, then the frame.

Ctrl+S saves the page as a `.scr` file you can reopen with Ctrl+O.
Ctrl+E exports SVG; PNG export is in the menu.

## Changing the script

All shapes live in `glyphs.py`: `FRAMES` for consonants, `VOWELS` for vowel
marks and `MARKS` for the strokes beneath, in a 36 × 36 grid.
