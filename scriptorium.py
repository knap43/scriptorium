#!/usr/bin/env python3
"""Scriptorium: write the conlang syllabary with an on-screen keyboard."""

import json
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glyphs  # noqa: E402
from glyphs import Document, Glyph  # noqa: E402

APP_ID = "io.github.knap43.Scriptorium"

CSS = """
.glyph-key { min-width: 64px; min-height: 64px; padding: 4px; }
.glyph-key label { font-size: 0.8em; opacity: 0.6; }
.canvas-frame { border-radius: 12px; }
.roman { font-family: monospace; opacity: 0.75; }
"""


def widget_rgb(widget):
    c = widget.get_color()
    return (c.red, c.green, c.blue)


class GlyphKey(Gtk.Button):
    """A keyboard button that shows a glyph and its romanization."""

    def __init__(self, glyph: Glyph, label: str, dashed: bool = False):
        super().__init__(focus_on_click=False)
        self.add_css_class("glyph-key")
        self.glyph, self.dashed = glyph, dashed
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        area = Gtk.DrawingArea(content_width=44, content_height=34)
        area.set_draw_func(self._draw)
        box.append(area)
        box.append(Gtk.Label(label=label))
        self.set_child(box)

    def _draw(self, area, cr, width, height):
        scale = 0.6
        x = (width - 36 * scale) / 2
        y = (height - 36 * scale) / 2
        rgb = widget_rgb(area)
        if self.dashed:
            cr.set_source_rgba(*rgb, 0.35)
            cr.set_line_width(1)
            cr.set_dash([2, 2])
            cr.rectangle(x, y, 36 * scale, 36 * scale)
            cr.stroke()
            cr.set_dash([])
        glyphs.draw_glyph(cr, self.glyph, x, y, rgb, scale)


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Scriptorium")
        self.set_default_size(820, 860)
        self.doc = Document()
        self.path = None

        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        view.add_top_bar(self._header())
        view.set_content(self._body())
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        keys = Gtk.EventControllerKey()
        # Capture phase, so Space and Enter don't press a focused button.
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self._refresh()

    # Layout -----------------------------------------------------------------

    def _header(self):
        header = Adw.HeaderBar()

        new = Gtk.Button(icon_name="document-new-symbolic",
                         tooltip_text="New page")
        new.connect("clicked", lambda *_: self._edit(self.doc.clear))
        header.pack_start(new)

        menu = Gio.Menu()
        files = Gio.Menu()
        files.append("Open…", "win.open")
        files.append("Save…", "win.save")
        menu.append_section(None, files)
        export = Gio.Menu()
        export.append("Export as SVG…", "win.export-svg")
        export.append("Export as PNG…", "win.export-png")
        menu.append_section(None, export)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic",
                                       menu_model=menu))

        for name, cb in [("open", self._open), ("save", self._save),
                         ("export-svg", self._export_svg),
                         ("export-png", self._export_png)]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)
        app = self.get_application()
        app.set_accels_for_action("win.open", ["<Ctrl>o"])
        app.set_accels_for_action("win.save", ["<Ctrl>s"])
        app.set_accels_for_action("win.export-svg", ["<Ctrl>e"])
        return header

    def _body(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=12, margin_bottom=12,
                      margin_start=12, margin_end=12)

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self._draw_canvas)
        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_child(self.canvas)
        frame = Gtk.Frame(child=scroller)
        frame.add_css_class("canvas-frame")
        frame.add_css_class("view")
        box.append(frame)

        self.roman = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.roman.add_css_class("roman")
        box.append(self.roman)

        box.append(self._keyboard())
        return box

    def _keyboard(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6,
                        halign=Gtk.Align.CENTER)
        half = len(glyphs.CONSONANTS) // 2
        for i, c in enumerate(glyphs.CONSONANTS):
            key = GlyphKey(Glyph(consonant=c), c)
            key.set_tooltip_text(f"Consonant {c}  (key {c.upper()})")
            key.connect("clicked", lambda _b, c=c: self._edit(
                self.doc.add_consonant, c))
            grid.attach(key, i % half, i // half, 1, 1)

        for i, v in enumerate(glyphs.VOWEL_ORDER):
            key = GlyphKey(Glyph(vowel=v), v, dashed=True)
            key.set_tooltip_text(f"Vowel {v}  (key {v.upper()})")
            key.connect("clicked", lambda _b, v=v: self._edit(
                self.doc.add_vowel, v))
            grid.attach(key, i + 1, 2, 1, 1)

        actions = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, margin_top=6)
        for label, tip, cb in [
            ("Space", "Single stroke beneath  (Space)",
             lambda *_: self._edit(self.doc.set_mark, 1)),
            ("Full stop", "Double stroke beneath  (.)",
             lambda *_: self._edit(self.doc.set_mark, 2)),
            ("New column", "Start a new column  (Enter)",
             lambda *_: self._edit(self.doc.new_column)),
        ]:
            button = Gtk.Button(label=label, tooltip_text=tip)
            button.connect("clicked", cb)
            actions.append(button)
        back = Gtk.Button(icon_name="edit-clear-symbolic",
                          tooltip_text="Erase  (Backspace)")
        back.connect("clicked", lambda *_: self._edit(self.doc.backspace))
        actions.append(back)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(grid)
        outer.append(actions)
        return outer

    # Drawing ----------------------------------------------------------------

    def _draw_canvas(self, area, cr, width, height):
        rgb = widget_rgb(area)
        glyphs.draw_document(cr, self.doc, rgb)
        x, y = self.doc.cursor_position()
        try:
            a = Adw.StyleManager.get_default().get_accent_color_rgba()
            cr.set_source_rgba(a.red, a.green, a.blue, 0.8)
        except AttributeError:   # libadwaita older than 1.6
            cr.set_source_rgba(0.21, 0.52, 0.89, 0.8)
        cr.rectangle(x, y + 40, 36, 3)
        cr.fill()

    def _refresh(self):
        w, h = self.doc.size()
        self.canvas.set_content_width(w)
        self.canvas.set_content_height(h + glyphs.ROW)
        self.canvas.queue_draw()
        self.roman.set_label(self.doc.roman() or "Type or click a glyph to begin.")

    def _edit(self, fn, *args):
        fn(*args)
        self._refresh()

    # Physical keyboard ------------------------------------------------------

    def _on_key(self, _ctl, keyval, _code, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        name = Gdk.keyval_name(keyval) or ""
        ch = chr(Gdk.keyval_to_unicode(keyval) or 0).lower()
        if ch in glyphs.FRAMES:
            self._edit(self.doc.add_consonant, ch)
        elif ch in glyphs.VOWELS:
            self._edit(self.doc.add_vowel, ch)
        elif name == "space":
            self._edit(self.doc.set_mark, 1)
        elif name in ("period", "KP_Decimal"):
            self._edit(self.doc.set_mark, 2)
        elif name in ("Return", "KP_Enter"):
            self._edit(self.doc.new_column)
        elif name == "BackSpace":
            self._edit(self.doc.backspace)
        else:
            return False
        return True

    # Files ------------------------------------------------------------------

    def _dialog(self, title, name, pattern, mime):
        dialog = Gtk.FileDialog(title=title, initial_name=name)
        flt = Gtk.FileFilter(name=mime)
        flt.add_pattern(pattern)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(flt)
        dialog.set_filters(filters)
        return dialog

    def _ask_save(self, title, name, pattern, mime, writer):
        if self.doc.is_empty():
            self._toast("Nothing to save yet")
            return
        dialog = self._dialog(title, name, pattern, mime)

        def done(d, result):
            try:
                path = d.save_finish(result).get_path()
            except GLib.Error:
                return
            try:
                writer(path)
                self._toast(f"Saved {os.path.basename(path)}")
            except OSError as err:
                self._toast(f"Could not save: {err.strerror}")
        dialog.save(self, None, done)

    def _save(self, *_):
        def write(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "columns": self.doc.to_list()}, f,
                          indent=1)
        self._ask_save("Save page", "inscription.scr", "*.scr",
                       "Scriptorium page", write)

    def _open(self, *_):
        dialog = self._dialog("Open page", None, "*.scr", "Scriptorium page")

        def done(d, result):
            try:
                path = d.open_finish(result).get_path()
                with open(path, encoding="utf-8") as f:
                    self.doc = Document.from_list(json.load(f)["columns"])
            except GLib.Error:
                return
            except (OSError, ValueError, KeyError, TypeError):
                self._toast("That file could not be read")
                return
            self._refresh()
        dialog.open(self, None, done)

    def _export_svg(self, *_):
        def write(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(glyphs.to_svg(self.doc))
        self._ask_save("Export SVG", "inscription.svg", "*.svg",
                       "SVG image", write)

    def _export_png(self, *_):
        self._ask_save("Export PNG", "inscription.png", "*.png",
                       "PNG image", lambda p: glyphs.to_png(self.doc, p))

    def _toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=2))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.get_active_window() or Window(self)
        win.present()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
