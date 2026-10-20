from dataclasses import dataclass, field
from typing import Dict, List
from .glyph import Glyph
from .metadata import GFontMetadata
from .errors import GFontError


@dataclass
class GFont:
    metadata: GFontMetadata
    glyphs: Dict[int, Glyph] = field(default_factory=dict)
    inline_codepoints: List[int] = field(default_factory=list)

    def validate(self):
        if not isinstance(self.metadata, GFontMetadata):
            raise GFontError("metadata must be GFontMetadata")
        if len(self.glyphs) > 65536:
            raise GFontError("Too many BMP glyphs")
        if len(set(self.inline_codepoints)) != len(self.inline_codepoints):
            raise GFontError("Duplicate inline codepoint")
        if any(cp not in self.glyphs for cp in self.inline_codepoints):
            raise GFontError("Inline codepoint missing from glyphs")
        for cp, glyph in self.glyphs.items():
            if type(cp) is not int or cp != glyph.codepoint:
                raise GFontError("Glyph dictionary key disagrees with codepoint")
            glyph.validate()
