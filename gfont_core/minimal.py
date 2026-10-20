from .font import GFont
from .glyph import Glyph, Point
from .metadata import GFontMetadata


def minimal_font(metadata=None):
    """Manual diagnostic geometry. Coordinate orientation is not yet verified."""
    strokes = {
        0x4E00: [[(100, 500), (900, 500)]],
        0x5341: [[(100, 500), (900, 500)], [(500, 100), (500, 900)]],
        0x4EBA: [[(500, 100), (400, 500), (100, 900)],
                 [(500, 100), (600, 500), (900, 900)]],
        0x53E3: [[(200, 200), (200, 800)],
                 [(200, 200), (800, 200), (800, 800)], [(200, 800), (800, 800)]],
    }
    glyphs = {cp: Glyph(cp, [[Point(x, y) for x, y in stroke] for stroke in lines])
              for cp, lines in strokes.items()}
    return GFont(metadata or GFontMetadata(), glyphs, list(strokes))
