"""Read-only geometric review hints. These are not handwriting diagnoses."""
import math
from itertools import combinations


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def inspect_glyph(glyph, font_size, short_ratio=0.04, gap_ratio=0.035):
    """Indices are zero-based; all distances use font coordinates.

    Short real dots and nearby independent strokes can legitimately be flagged.
    Tangents use the first distinct segment; no repair or stroke-order inference.
    """
    glyph.validate()
    if any(not math.isfinite(v) or v <= 0 for v in
           (font_size, short_ratio, gap_ratio)):
        raise ValueError('Font size and thresholds must be finite and positive')
    epsilon = font_size * 1e-7
    paths, endpoints = [], []
    for index, points in enumerate(glyph.strokes):
        length = sum(distance(a, b) for a, b in zip(points, points[1:]))
        closed = len(points) > 2 and distance(points[0], points[-1]) <= epsilon
        paths.append(dict(stroke_index=index, length=length,
                          short=length <= font_size * short_ratio,
                          duplicate_segments=sum(distance(a, b) <= epsilon
                                                 for a, b in zip(points, points[1:])),
                          closed=closed))
        if closed or length <= epsilon:
            continue
        for end, ordered in [('start', points), ('end', points[::-1])]:
            p = ordered[0]
            q = next(q for q in ordered[1:] if distance(p, q) > epsilon)
            d = distance(p, q)
            endpoints.append((index, end, p, ((p.x-q.x)/d, (p.y-q.y)/d)))
    gaps = []
    for a, b in combinations(endpoints, 2):
        if a[0] == b[0]:
            continue
        d = distance(a[2], b[2])
        if not epsilon < d <= font_size * gap_ratio:
            continue
        ux, uy = (b[2].x-a[2].x)/d, (b[2].y-a[2].y)/d
        aligned = (a[3][0]*ux+a[3][1]*uy >= math.cos(math.pi/4)
                   and -b[3][0]*ux-b[3][1]*uy >= math.cos(math.pi/4))
        gaps.append(dict(a_stroke=a[0], a_end=a[1], b_stroke=b[0], b_end=b[1],
                         a=[a[2].x, a[2].y], b=[b[2].x, b[2].y],
                         distance=d, aligned=aligned))
    gaps.sort(key=lambda g: (not g['aligned'], g['distance'], g['a_stroke'], g['b_stroke']))
    return dict(codepoint=glyph.codepoint, character=chr(glyph.codepoint),
                stroke_count=len(paths), paths=paths, nearby_endpoints=gaps,
                short_count=sum(p['short'] for p in paths),
                aligned_gap_count=sum(g['aligned'] for g in gaps),
                thresholds=dict(short_length=font_size*short_ratio,
                                endpoint_gap=font_size*gap_ratio),
                status='review_hints_only')
