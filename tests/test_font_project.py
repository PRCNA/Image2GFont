import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from page_import import PageProject
from font_project import FontProject
from gfont_core import GFontV5Reader

class FontCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.font = FontProject.create(self.root/'font', 'TwoPages')
    def tearDown(self):
        import os
        for p in self.root.rglob('*'):
            if p.is_file(): os.chmod(p, 0o666)
        self.temp.cleanup()
    def page(self, name, char, vertical=False):
        im=Image.new('RGB',(100,100),'white');d=ImageDraw.Draw(im)
        d.line((20,50,80,50),fill='black',width=8)
        if vertical:d.line((50,20,50,80),fill='black',width=8)
        source=self.root/(name+'.png');im.save(source)
        p=PageProject.create(source,self.root/name)
        p.data['regions']=[dict(box=[10,10,90,90],character=char)];p.save()
        return p
    def test_two_pages_export_one_font_and_reload(self):
        a=self.page('a','\u4e00');b=self.page('b','\u5341',True)
        self.font.add_page(a.root/'page.json');self.font.add_page(b.root/'page.json')
        loaded=FontProject.load(self.font.root/'font_project.json')
        font=GFontV5Reader.read(loaded.generate(self.root/'export'))
        self.assertEqual(set(font.glyphs),{0x4e00,0x5341})
        self.assertTrue(all(g.strokes for g in font.glyphs.values()))
        self.assertEqual(font.metadata.name,'TwoPages')
        report=json.loads((self.root/'export/report.json').read_text(encoding='utf-8'))
        self.assertEqual(len(report['pages']),2)
    def test_duplicate_is_rejected_without_changing_manifest(self):
        a=self.page('a','\u4e00');b=self.page('b','\u4e00',True)
        self.font.add_page(a.root/'page.json')
        before=(self.font.root/'font_project.json').read_bytes()
        with self.assertRaises(ValueError):self.font.add_page(b.root/'page.json')
        self.assertEqual(before,(self.font.root/'font_project.json').read_bytes())
    def test_tampered_source_is_rejected(self):
        a=self.page('a','\u4e00');self.font.add_page(a.root/'page.json')
        p=self.font.pages()[0];source=p.root/p.data['source'];source.chmod(0o666);source.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.font.generate(self.root/'export')
        self.assertFalse((self.root/'export').exists())
    def test_path_escape_is_rejected(self):
        self.font.data['pages']=['../outside/page.json']
        with self.assertRaises(ValueError):self.font.pages()
    def test_empty_font_is_rejected(self):
        with self.assertRaises(ValueError):self.font.generate(self.root/'export')

if __name__=='__main__':unittest.main()
