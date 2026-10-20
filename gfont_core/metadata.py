from dataclasses import dataclass


@dataclass(frozen=True)
class GFontMetadata:
    creator: str = "kvenjoy"
    font_type_raw: int = 0
    name: str = "Image2GFont_Phase0"
    font_id: str = "Image2GFont_Phase0"
    description: str = "Phase 0 manual strokes"
    font_size: int = 1000
    glyph_count: int = 4
    extra_n: str = ""
    extra_o: str = ""
