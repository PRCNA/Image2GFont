from dataclasses import dataclass
import math
from typing import List

from .errors import GFontError


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class Glyph:
    codepoint: int
    strokes: List[List[Point]]

    def validate(self):
        if type(self.codepoint) is not int or not 0 <= self.codepoint <= 0xFFFF:
            raise GFontError("V5 codepoint must be an integer in U+0000..U+FFFF")
        for stroke in self.strokes:
            if not stroke:
                raise GFontError("Empty stroke cannot be serialized")
            for point in stroke:
                if not isinstance(point, Point):
                    raise GFontError("Stroke entries must be Point instances")
                if any(not math.isfinite(v) or abs(v) > 3.4028234663852886e38
                       for v in (point.x, point.y)):
                    raise GFontError("Coordinates must be finite float32 values")
