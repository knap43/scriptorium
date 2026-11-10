"""Glyph geometry, document model and SVG/PNG rendering for the script.

Pure Python plus cairo, with no GTK dependency, so it can be tested
on its own.
"""

from dataclasses import dataclass, field
from typing import Optional

# --- Geometry -------------------------------------------------------------

SIZE = 36          # side of a consonant frame
ROW = 70           # vertical distance between glyphs in a column
COLUMN = 100       # horizontal distance between columns
MARGIN = 40
STROKE = 2.5
DOT_RADIUS = 2.4

_RIGHT_BAR = [(45, 0), (45, 36)]
_LEFT_BAR = [(-9, 0), (-9, 36)]

# Each frame is a list of polylines in local coordinates (0..36).
FRAMES = {
    "p": [[(0, 0), (36, 0), (36, 36)]],
    "t": [[(36, 0), (0, 0), (0, 36)]],
    "k": [[(0, 0), (0, 36), (36, 36)]],
    "m": [[(36, 0), (36, 36), (0, 36)]],
    "h": [[(0, 0), (36, 0), (36, 36), (0, 36)]],
    "f": [[(36, 0), (0, 0), (0, 36), (36, 36)]],
    "s": [[(0, 36), (0, 0), (36, 0), (36, 36)]],
    "y": [[(0, 0), (0, 36), (36, 36), (36, 0)]],
}
FRAMES["b"] = FRAMES["p"] + [_RIGHT_BAR]
FRAMES["n"] = FRAMES["m"] + [_RIGHT_BAR]
FRAMES["r"] = FRAMES["h"] + [_RIGHT_BAR]
FRAMES["d"] = FRAMES["t"] + [_LEFT_BAR]
FRAMES["g"] = FRAMES["k"] + [_LEFT_BAR]
FRAMES["v"] = FRAMES["f"] + [_LEFT_BAR]

# Keyboard order: voiceless/plain form above its paired form.
CONSONANTS = ["p", "t", "k", "m", "h", "f", "s",
              "b", "d", "g", "n", "r", "v", "y"]

VOWELS = {
    "a": [[(18, 12), (18, 24)]],
    "e": [[(14, 12), (14, 24)], [(22, 12), (22, 24)]],
    "i": [[(12, 18), (24, 18)]],
    "u": [[(12, 14), (24, 14)], [(12, 22), (24, 22)]],
    "o": "dot",
}
VOWEL_ORDER = ["a", "e", "i", "o", "u"]

# Strokes beneath a glyph: 1 = space, 2 = full stop.
MARKS = {
    1: [[(6, 48), (30, 48)]],
    2: [[(6, 48), (30, 48)], [(6, 55), (30, 55)]],
}

# --- Document model -------------------------------------------------------


@dataclass
class Glyph:
    consonant: Optional[str] = None
    vowel: Optional[str] = None
    mark: int = 0

    def roman(self) -> str:
        text = (self.consonant or "") + (self.vowel or "")
        return text + {0: "", 1: " ", 2: ". "}[self.mark]

    def to_dict(self):
        return {"c": self.consonant, "v": self.vowel, "m": self.mark}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("c"), d.get("v"), d.get("m", 0))


@dataclass
class Document:
    columns: list = field(default_factory=lambda: [[]])

    # Editing --------------------------------------------------------------

    @property
    def current(self) -> list:
        return self.columns[-1]

    def last(self) -> Optional[Glyph]:
        return self.current[-1] if self.current else None

    def add_consonant(self, c: str):
        self.current.append(Glyph(consonant=c))

    def add_vowel(self, v: str):
        """Give the last glyph a vowel, or start a vowel-only glyph."""
        g = self.last()
        if g and g.consonant and not g.vowel and not g.mark:
            g.vowel = v
        else:
            self.current.append(Glyph(vowel=v))

    def set_mark(self, mark: int):
        g = self.last()
        if g:
            g.mark = 0 if g.mark == mark else mark

    def new_column(self):
        if self.current:
            self.columns.append([])

    def backspace(self):
        g = self.last()
        if g is None:
            if len(self.columns) > 1:
                self.columns.pop()
            return
        if g.mark:
            g.mark = 0
        elif g.consonant and g.vowel:
            g.vowel = None
        else:
            self.current.pop()

    def clear(self):
        self.columns = [[]]

    def is_empty(self) -> bool:
        return not any(self.columns)

    def roman(self) -> str:
        return "\n".join("".join(g.roman() for g in col).strip()
                         for col in self.columns if col)

    def to_list(self):
        return [[g.to_dict() for g in col] for col in self.columns]

    @classmethod
    def from_list(cls, data):
        cols = [[Glyph.from_dict(d) for d in col] for col in data]
        return cls(cols or [[]])

    # Layout ---------------------------------------------------------------

    def size(self):
        cols = max(1, len(self.columns))
        rows = max(1, max(len(c) for c in self.columns))
        width = 2 * MARGIN + (cols - 1) * COLUMN + 45
        height = 2 * MARGIN + (rows - 1) * ROW + 60
        return width, height

    def positions(self):
        """Yield (x, y, glyph) for every glyph."""
        for ci, col in enumerate(self.columns):
            for ri, g in enumerate(col):
                yield MARGIN + 9 + ci * COLUMN, MARGIN + ri * ROW, g

    def cursor_position(self):
        """Where the next glyph will go, for the caret."""
        ci = len(self.columns) - 1
        return MARGIN + 9 + ci * COLUMN, MARGIN + len(self.current) * ROW


# --- Drawing --------------------------------------------------------------


def glyph_parts(g: Glyph):
    """Return (polylines, dot) in local coordinates for one glyph."""
    lines, dot = [], False
    if g.consonant:
        lines += FRAMES[g.consonant]
    if g.vowel:
        if VOWELS[g.vowel] == "dot":
            dot = True
        else:
            lines += VOWELS[g.vowel]
    if g.mark:
        lines += MARKS[g.mark]
    return lines, dot


def draw_glyph(cr, g: Glyph, x: float, y: float, rgb=(0.04, 0.04, 0.04),
               scale: float = 1.0):
    """Draw one glyph with cairo at (x, y)."""
    cr.save()
    cr.translate(x, y)
    cr.scale(scale, scale)
    cr.set_source_rgb(*rgb)
    cr.set_line_width(STROKE)
    cr.set_line_cap(2)   # square caps, as in the SVG
    cr.set_line_join(0)
    lines, dot = glyph_parts(g)
    for line in lines:
        cr.move_to(*line[0])
        for pt in line[1:]:
            cr.line_to(*pt)
        cr.stroke()
    if dot:
        cr.arc(18, 18, DOT_RADIUS, 0, 6.2832)
        cr.fill()
    cr.restore()


def draw_document(cr, doc: Document, rgb=(0.04, 0.04, 0.04)):
    for x, y, g in doc.positions():
        draw_glyph(cr, g, x, y, rgb)


def _fmt(n):
    return f"{n:g}"


def to_svg(doc: Document, color: str = "#0b0b0b") -> str:
    width, height = doc.size()
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'  <g fill="none" stroke="{color}" stroke-width="{STROKE}" '
        'stroke-linecap="square">',
    ]
    for x, y, g in doc.positions():
        lines, dot = glyph_parts(g)
        if lines:
            d = " ".join(
                "M" + " L".join(f"{_fmt(x + px)} {_fmt(y + py)}"
                                for px, py in line)
                for line in lines)
            out.append(f'    <path d="{d}"/>')
        if dot:
            out.append(f'    <circle cx="{_fmt(x + 18)}" cy="{_fmt(y + 18)}" '
                       f'r="{DOT_RADIUS}" fill="{color}" stroke="none"/>')
    out += ["  </g>", "</svg>", ""]
    return "\n".join(out)


def to_png(doc: Document, path: str, scale: float = 3.0,
           transparent: bool = False):
    import cairo
    width, height = doc.size()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                 int(width * scale), int(height * scale))
    cr = cairo.Context(surface)
    if not transparent:
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
    cr.scale(scale, scale)
    draw_document(cr, doc)
    surface.write_to_png(path)
