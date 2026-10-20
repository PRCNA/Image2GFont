import tempfile
import unittest
from pathlib import Path
from collections import Counter
from gfont_core import GFont,GFontMetadata,Glyph,Point,GFontV5Writer,GFontV5Reader
from stroke_editor.model import StrokeSession
from stroke_editor.junction_review import JunctionReview


def segments(paths):
    return Counter(tuple(sorted(((a.x,a.y),(b.x,b.y)))) for s in paths for a,b in zip(s,s[1:]))


class JunctionReviewTests(unittest.TestCase):
    def test_preview_accept_undo_save_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'input.gfont'
            paths=[[Point(-20,0),Point(0,0),Point(20,0)],[Point(0,-20),Point(0,0),Point(0,20)],[Point(50,50),Point(60,60)]]
            GFontV5Writer.write(GFont(GFontMetadata(glyph_count=1),{65:Glyph(65,paths)},[65]),source)
            raw=source.read_bytes();s=StrokeSession(source);review=JunctionReview(s,65)
            last=len(review.reports[0]['candidates'])-1
            preview=review.preview(0,last)
            self.assertFalse(s.dirty);self.assertEqual(segments(preview),segments(paths))
            review.accept(0,last);self.assertTrue(s.dirty);self.assertFalse(s.confirmed[65])
            changed=s.paths[65];s.undo();self.assertEqual(s.paths[65],review.snapshot)
            s.redo();self.assertEqual(s.paths[65],changed)
            with self.assertRaises(ValueError):review.preview(0,last)
            s.save_project(root/'edit.json');loaded=StrokeSession(source);loaded.load_project(root/'edit.json')
            self.assertEqual(loaded.paths,s.paths)
            loaded.export(root/'result.gfont','reviewed')
            self.assertEqual(segments(GFontV5Reader.read(root/'result.gfont').glyphs[65].strokes),segments(paths))
            self.assertEqual(source.read_bytes(),raw)

    def test_no_shared_point_does_not_invent_junction(self):
        class Session:
            paths={65:((Point(-10,0),Point(10,0)),(Point(0,-10),Point(0,10)))}
            font=GFont(GFontMetadata(),{},[])
        review=JunctionReview(Session(),65)
        self.assertEqual(review.reports,[])
