import copy
import unittest
from gfont_core import Glyph, Point
from image_pipeline.quality import inspect_glyph


def glyph(*paths):
    return Glyph(0x548c, [[Point(*p) for p in path] for path in paths])


class QualityTests(unittest.TestCase):
    def test_gap_and_no_mutation(self):
        g = glyph([(0, 0), (100, 0)], [(120, 0), (220, 0)])
        before = copy.deepcopy(g)
        r = inspect_glyph(g, 1000)
        self.assertEqual(r['aligned_gap_count'], 1)
        self.assertEqual(g, before)

    def test_touching_is_not_gap(self):
        g = glyph([(0, 0), (100, 0)], [(100, 0), (200, 0)])
        self.assertEqual(inspect_glyph(g, 1000)['nearby_endpoints'], [])

    def test_closed_and_dot(self):
        g = glyph([(0, 0), (100, 0), (100, 100), (0, 0)], [(10, 0)])
        r = inspect_glyph(g, 1000)
        self.assertEqual(r['short_count'], 1)
        self.assertEqual(r['nearby_endpoints'], [])

    def test_scale_translate(self):
        g = glyph([(0, 0), (100, 0)], [(120, 0), (220, 0)])
        h = Glyph(g.codepoint, [[Point(p.x*2-400, p.y*2+200) for p in s] for s in g.strokes])
        a, b = inspect_glyph(g, 1000), inspect_glyph(h, 2000)
        self.assertEqual(a['aligned_gap_count'], b['aligned_gap_count'])
        self.assertEqual(a['short_count'], b['short_count'])
        self.assertAlmostEqual(a['nearby_endpoints'][0]['distance']*2,
                               b['nearby_endpoints'][0]['distance'])

    def test_duplicate_and_invalid_threshold(self):
        g = glyph([(0, 0), (0, 0), (100, 0)])
        self.assertEqual(inspect_glyph(g, 1000)['paths'][0]['duplicate_segments'], 1)
        for size in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                inspect_glyph(g, size)
