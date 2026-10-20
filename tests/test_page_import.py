import tempfile
import unittest
from pathlib import Path
from PIL import Image,ImageDraw
from page_import import PageProject
from gfont_core import GFontV5Reader


class PageImportTests(unittest.TestCase):
    def test_crop_bind_generate_roundtrip_and_reference_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'paper.png'
            im=Image.new('RGB',(200,100),'white');d=ImageDraw.Draw(im)
            d.line((10,50,80,50),fill='black',width=5);d.line((150,10,150,90),fill='black',width=5);im.save(source)
            original=source.read_bytes();p=PageProject.create(source,root/'project')
            p.data['regions']=[dict(box=[0,0,100,100],character=chr(0x4e00)),dict(box=[100,0,200,100],character=chr(0x4e28))];p.save()
            loaded=PageProject.load(p.root/'page.json');fontpath=loaded.generate(p.root/'generation')
            font=GFontV5Reader.read(fontpath);self.assertEqual(set(font.glyphs),{0x4e00,0x4e28})
            self.assertTrue(all(g.strokes for g in font.glyphs.values()));self.assertEqual(source.read_bytes(),original)
            with self.assertRaises(FileExistsError):loaded.generate(p.root/'generation')
            p.data['regions'][1]['character']=chr(0x4e00)
            with self.assertRaises(ValueError):p.generate(p.root/'bad')
            self.assertFalse((p.root/'bad').exists())

    def test_unbound_and_out_of_bounds_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(20,20),'white').save(root/'blank.png')
            p=PageProject.create(root/'blank.png',root/'project');p.data['regions']=[dict(box=[0,0,20,20],character='')]
            p.save()
            with self.assertRaises(ValueError):p.generate(root/'bad')
            p.data['regions'][0]=dict(box=[-1,0,10,10],character='A')
            with self.assertRaises(ValueError):p.save()
