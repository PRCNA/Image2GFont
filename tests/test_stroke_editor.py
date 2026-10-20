from pathlib import Path
import tempfile
import unittest
from gfont_core import GFont, GFontMetadata, Glyph, Point, GFontV5Reader, GFontV5Writer
from stroke_editor.model import StrokeSession


class StrokeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'source.gfont'
        font=GFont(GFontMetadata(glyph_count=2),{
            65:Glyph(65,[[Point(0,0),Point(10,0),Point(20,0)],[Point(30,0),Point(40,0)]]),
            66:Glyph(66,[[Point(1,1)]])},[65])
        GFontV5Writer.write(font,self.source);self.original=self.source.read_bytes();self.s=StrokeSession(self.source)
    def tearDown(self):self.temp.cleanup()

    def test_split_join_preserve_exact_path(self):
        original=self.s.paths[65][0]
        self.s.split(65,0,1)
        self.assertEqual(self.s.paths[65][0][-1],self.s.paths[65][1][0])
        self.s.join(65,0,1)
        self.assertEqual(self.s.paths[65][0],original)
        self.assertEqual(len(self.s.paths[65]),2)
        with self.assertRaises(ValueError):self.s.split(65,0,0)

    def test_join_gap_and_explicit_directions(self):
        self.s.join(65,0,1,True,False)
        self.assertEqual(self.s.paths[65][0],(Point(20,0),Point(10,0),Point(0,0),Point(30,0),Point(40,0)))
        self.assertEqual(self.s.font.glyphs[65].strokes[0][0],Point(0,0))

    def test_confirmation_edit_undo_redo(self):
        self.s.set_confirmed(65,True);self.s.reverse(65,0)
        self.assertFalse(self.s.confirmed[65]);self.s.undo();self.assertTrue(self.s.confirmed[65])
        self.s.redo();self.assertFalse(self.s.confirmed[65])
        self.s.undo();self.s.delete(65,[1]);self.assertIsNone(self.s.redo())
        self.assertEqual(len(self.s.paths[65]),1)

    def test_move_and_other_glyph_preserved(self):
        original=self.s.paths[65][0];other=self.s.paths[66]
        self.s.move(65,0,1);self.assertEqual(self.s.paths[65][1],original)
        self.assertEqual(self.s.paths[66],other)
        self.s.reset_glyph(65);self.assertEqual(self.s.paths[65][0],original)

    def test_record_roundtrip_and_source_guard(self):
        self.s.delete(65,[1]);self.s.set_confirmed(65,True);self.assertTrue(self.s.dirty)
        record=self.root/'record.json';self.s.save_project(record);self.assertFalse(self.s.dirty)
        self.s.reverse(65,0);self.assertTrue(self.s.dirty)
        self.s.load_project(record);self.assertTrue(self.s.confirmed[65]);self.assertFalse(self.s.dirty)
        result=self.root/'edited.gfont';self.s.export(result,'Edited')
        font=GFontV5Reader.read(result);self.assertEqual(font.glyphs[65],self.s.glyph(65))
        self.assertEqual(self.source.read_bytes(),self.original)
        with self.assertRaises(FileExistsError):self.s.export(self.source,'DoNotOverwrite')
        self.assertEqual(len(self.s.font.glyphs[65].strokes),2)

    def test_wrong_source_record_rejected(self):
        import json
        p=self.root/'bad.json';self.s.save_project(p)
        data=json.loads(p.read_text());data['source_sha256']='wrong';p.write_text(json.dumps(data))
        before=self.s.payload()
        with self.assertRaises(ValueError):self.s.load_project(p)
        self.assertEqual(self.s.payload(),before)

    def test_delete_all_can_be_undone(self):
        self.s.delete(65,[0,1]);self.assertEqual(self.s.paths[65],())
        self.s.undo();self.assertEqual(len(self.s.paths[65]),2)

    def test_node_move_insert_delete_and_undo(self):
        original=self.s.paths[65]
        self.s.move_point(65,0,1,Point(11,4))
        self.assertEqual(self.s.paths[65][0][1],Point(11,4))
        j=self.s.insert_point(65,0,0,Point(5,2));self.assertEqual(j,1)
        self.s.delete_point(65,0,j);self.assertEqual(len(self.s.paths[65][0]),3)
        self.s.undo();self.s.undo();self.s.undo();self.assertEqual(self.s.paths[65],original)

    def test_closed_path_endpoint_edit_keeps_closure(self):
        self.s.change(65,[[Point(0,0),Point(10,0),Point(10,10),Point(0,10),Point(0,0)]])
        self.s.move_point(65,0,0,Point(-2,-3))
        self.assertEqual(self.s.paths[65][0][0],self.s.paths[65][0][-1])
        self.s.delete_point(65,0,4)
        self.assertEqual(self.s.paths[65][0][0],self.s.paths[65][0][-1])
        self.assertEqual(len(self.s.paths[65][0]),4)
        with self.assertRaises(ValueError):self.s.delete_point(65,0,0)

    def test_invalid_node_does_not_mutate(self):
        original=self.s.paths[65]
        with self.assertRaises(ValueError):self.s.move_point(65,0,1,Point(float('nan'),0))
        self.assertEqual(self.s.paths[65],original)
        with self.assertRaises(ValueError):self.s.delete_point(65,1,0)

    def test_manual_path_commit_confirmation_and_record(self):
        self.s.set_confirmed(65,True)
        index=self.s.add_path(65,[Point(1,2),Point(1,2),Point(9,7)])
        self.assertEqual(self.s.paths[65][index],(Point(1,2),Point(9,7)))
        self.assertFalse(self.s.confirmed[65]);self.s.undo();self.assertTrue(self.s.confirmed[65])
        with self.assertRaises(ValueError):self.s.add_path(65,[Point(0,0),Point(0,0)])
        self.s.redo();p=self.root/'nodes.json';self.s.save_project(p);self.s.reset_glyph(65);self.s.load_project(p)
        self.assertEqual(self.s.paths[65][index],(Point(1,2),Point(9,7)))


if __name__=='__main__':unittest.main()
