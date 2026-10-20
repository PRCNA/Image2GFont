import unittest
import numpy as np
from PIL import Image,ImageDraw,ImageOps
from vision_core.segmentation import segment,SegmentationConfig
from vision_core.trajectory import extract
from tests import test_font_project as helpers
from font_project import FontProject
from gfont_core import GFontV5Reader

class VisionTests(unittest.TestCase):
    def line(self):
        im=Image.new('RGB',(64,64),'white');ImageDraw.Draw(im).line((12,32,52,32),fill='black',width=4);return im
    def test_polarity(self):
        im=self.line();_,a,ra=segment(im);_,b,rb=segment(ImageOps.invert(im))
        self.assertEqual(ra['resolved_mode'],'dark');self.assertEqual(rb['resolved_mode'],'light')
        self.assertGreater(np.logical_and(a,b).sum()/np.logical_or(a,b).sum(),.9)
    def test_cyan_rejects_white_grid(self):
        im=Image.new('RGB',(128,128),(30,30,30));d=ImageDraw.Draw(im)
        d.line((64,0,64,127),fill='white',width=2);d.line((20,40,108,40),fill=(80,220,220),width=6)
        _,m,r=segment(im,SegmentationConfig(working_side=128))
        self.assertEqual(r['resolved_mode'],'cyan');self.assertTrue(m[40,30]);self.assertFalse(m[100,64])
    def test_red_grid_rejected(self):
        im=Image.new('RGB',(128,128),'white');d=ImageDraw.Draw(im)
        d.line((10,0,10,127),fill=(180,65,65),width=4);d.line((30,64,100,64),fill='black',width=5)
        _,m,r=segment(im,SegmentationConfig(working_side=128))
        self.assertEqual(r['resolved_mode'],'dark_red_grid');self.assertTrue(m[64,50]);self.assertFalse(m[30,10])
    def test_white_blank_has_no_trajectory(self):
        with self.assertRaises(ValueError):extract(Image.new('RGB',(64,64),'white'),65)
    def test_scale_and_geometry(self):
        g,im,m,r=extract(self.line(),65)
        self.assertEqual(im.size,(384,384));self.assertIn('low_source_resolution_no_detail_recovery',r['warnings'])
        self.assertTrue(all(-410<=p.x<=410 and -910<=p.y<=-90 for s in g.strokes for p in s))
    def test_invalid_config(self):
        with self.assertRaises(ValueError):segment(self.line(),SegmentationConfig(mode='unknown'))

class VisionExportTests(unittest.TestCase):
    setUp=helpers.FontCollectionTests.setUp
    tearDown=helpers.FontCollectionTests.tearDown
    page=helpers.FontCollectionTests.page
    def test_collection_mode_persistence_and_masks(self):
        p=self.page('one','A');self.font.add_page(p.root/'page.json');self.font.data['vision_mode']='auto';self.font.save()
        loaded=FontProject.load(self.font.root/'font_project.json');out=loaded.generate(self.root/'out')
        self.assertEqual(set(GFontV5Reader.read(out).glyphs),{65})
        self.assertTrue((self.root/'out/page_001/mask_1.png').exists())
        from coordinate_editor.reference import load_report_reference
        ref=load_report_reference(self.root/'out',65)
        self.assertEqual(ref[0].size,(384,384))
        self.assertAlmostEqual(ref[3],-400)
        self.assertAlmostEqual(ref[4],-900)

if __name__=='__main__':unittest.main()
