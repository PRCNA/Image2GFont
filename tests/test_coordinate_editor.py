import json
from pathlib import Path
import tempfile
import unittest
from gfont_core import GFont, GFontMetadata, Glyph, Point, GFontV5Reader, GFontV5Writer
from coordinate_editor.model import Transform, EditorSession, transformed


class CoordinateTests(unittest.TestCase):
    def test_pivot_scale_flip_rotate_translate_order(self):
        t=Transform(dx=7,dy=9,scale=2,angle=90,pivot_x=10,pivot_y=20,flip_x=True)
        p=t.apply(Point(13,24))
        self.assertAlmostEqual(p.x,9)
        self.assertAlmostEqual(p.y,23)

    def test_invalid_transform(self):
        for t in [Transform(scale=0),Transform(dx=float('nan')),Transform(angle=float('inf')),Transform(flip_x=1)]:
            with self.assertRaises(ValueError):t.validate()

    def test_inverse_rotation(self):
        p=Point(-73.5,92.1)
        q=Transform(angle=-37).apply(Transform(angle=37).apply(p))
        self.assertAlmostEqual(q.x,p.x);self.assertAlmostEqual(q.y,p.y)

    def test_history_profile_and_verified_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'input.gfont'
            font=GFont(GFontMetadata(glyph_count=2),{65:Glyph(65,[[Point(10,20),Point(30,40)]]),66:Glyph(66,[[Point(-9,6)]])},[65])
            GFontV5Writer.write(font,src);original=src.read_bytes();session=EditorSession(src)
            session.commit(Transform(dx=100,dy=-200));session.commit(Transform(scale=2))
            session.undo();self.assertEqual(session.transform.dx,100)
            session.redo();self.assertEqual(session.transform.scale,2)
            session.undo();session.commit(Transform(dx=-500,dy=-800));session.redo()
            self.assertEqual(session.transform.dx,-500)
            profile=root/'profile.json';session.save_profile(profile)
            session.commit(Transform());session.load_profile(profile)
            self.assertEqual(session.transform.dy,-800)
            self.assertEqual(json.loads(profile.read_text())['driver_verified'],False)
            target=root/'out.gfont';self.assertEqual(session.export(target,'CoordinateTest'),2)
            result=GFontV5Reader.read(target)
            self.assertEqual(result.glyphs[65].strokes[0][0],Point(-490,-780))
            self.assertEqual(result.glyphs[66].strokes[0][0],Point(-509,-794))
            self.assertEqual(src.read_bytes(),original)
            self.assertEqual(session.font.glyphs[65].strokes[0][0],Point(10,20))
            with self.assertRaises(FileExistsError):session.export(src,'NoOverwrite')
            with self.assertRaises(FileExistsError):session.save_profile(profile)

    def test_source_change_prevents_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source.gfont';GFontV5Writer.write(GFont(GFontMetadata(glyph_count=0)),src)
            session=EditorSession(src);src.write_bytes(b'changed')
            with self.assertRaises(ValueError):session.export(Path(tmp)/'new.gfont','Test')


if __name__=='__main__':unittest.main()
