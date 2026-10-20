import hashlib,json,unittest
from tests import test_font_project as helpers
from ocr_review import OCRReview
from font_project import FontProject
from gfont_core import GFontV5Reader

class OCRReviewTests(unittest.TestCase):
    setUp = helpers.FontCollectionTests.setUp
    tearDown = helpers.FontCollectionTests.tearDown
    page = helpers.FontCollectionTests.page
    def make_review(self):
        pages=[self.page('a','\u4e00'),self.page('b','\u5341',True)]
        rows=[]
        for i,p in enumerate(pages):
            rows.append(dict(id=str(i),file=str((p.root/p.data['source']).relative_to(self.root)),sha256=p.data['source_sha256'],characters=[dict(text=p.data['regions'][0]['character'],score=.9,box=[[10,10],[90,10],[90,90],[10,90]])]))
        path=self.root/'results.json';path.write_text(json.dumps(dict(images=rows)),encoding='utf-8');return OCRReview(path)
    def test_confirmed_only_roundtrip(self):
        r=self.make_review()
        with self.assertRaises(ValueError):r.export(self.root/'empty','Test')
        r.accept(0,0,'\u4e00',[10,10,90,90]);r.accept(1,0,'\u5341',[10,10,90,90])
        project=FontProject.load(r.export(self.root/'review','Reviewed'))
        font=GFontV5Reader.read(project.generate(self.root/'generated'))
        self.assertEqual(set(font.glyphs),{0x4e00,0x5341})
    def test_invalid_confirmation_does_not_replace(self):
        r=self.make_review();r.accept(0,0,'\u4e00',[10,10,90,90])
        with self.assertRaises(ValueError):r.accept(1,0,'\u4e00',[10,10,90,90])
        with self.assertRaises(ValueError):r.accept(0,0,'AB',[10,10,90,90])
        with self.assertRaises(ValueError):r.accept(0,0,'\u4e00',[-1,10,90,90])
        self.assertEqual(len(r.accepted),1)

    def test_session_roundtrip_and_atomic_rejection(self):
        r=self.make_review();r.accept(0,0,'A',[10,10,90,90])
        path=self.root/'session.json';r.save_session(path)
        restored=OCRReview(r.path);restored.restore_session(path)
        self.assertEqual(restored.accepted,r.accepted)
        doc=json.loads(path.read_text(encoding='utf-8'))
        doc['confirmed'].append(dict(doc['confirmed'][0]))
        path.write_text(json.dumps(doc),encoding='utf-8')
        before=dict(restored.accepted)
        with self.assertRaises(ValueError):restored.restore_session(path)
        self.assertEqual(restored.accepted,before)
    def test_session_wrong_results_rejected(self):
        r=self.make_review();r.accept(0,0,'A',[10,10,90,90]);path=self.root/'session.json';r.save_session(path)
        r.path.write_text(r.path.read_text(encoding='utf-8')+' ',encoding='utf-8')
        other=OCRReview(r.path)
        with self.assertRaises(ValueError):other.restore_session(path)
        self.assertEqual(other.accepted,{})
    def test_session_forged_provenance_rejected(self):
        r=self.make_review();r.accept(0,0,'A',[10,10,90,90]);path=self.root/'session.json';r.save_session(path)
        doc=json.loads(path.read_text(encoding='utf-8'));doc['confirmed'][0]['source_sha256']='wrong'
        path.write_text(json.dumps(doc),encoding='utf-8')
        with self.assertRaises(ValueError):r.restore_session(path)
        self.assertEqual(len(r.accepted),1)
    def test_mode_restores_and_exports_per_character(self):
        r=self.make_review();r.vision_mode='dark';r.accept(0,0,'A',[10,10,90,90])
        r.vision_mode='auto';r.accept(1,0,'B',[10,10,90,90])
        session=self.root/'modes.json';r.save_session(session)
        other=OCRReview(r.path);other.restore_session(session)
        self.assertEqual(other.accepted,r.accepted)
        project=FontProject.load(other.export(self.root/'modes','Modes'))
        self.assertEqual([p.data['regions'][0]['vision_mode'] for p in project.pages()],['dark','auto'])

    def test_negative_index_rejected(self):
        r=self.make_review()
        with self.assertRaises(ValueError):r.accept(-1,0,'A',[10,10,90,90])
        with self.assertRaises(ValueError):r.accept(0,-1,'A',[10,10,90,90])

if __name__=='__main__':unittest.main()
