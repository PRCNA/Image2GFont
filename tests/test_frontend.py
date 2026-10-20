import unittest
from tests import test_ocr_review as helpers
from frontend_server import Workspace

class FrontendTests(unittest.TestCase):
    setUp=helpers.OCRReviewTests.setUp
    tearDown=helpers.OCRReviewTests.tearDown
    page=helpers.OCRReviewTests.page
    make_review=helpers.OCRReviewTests.make_review
    def test_disagreement_manual_resolution_persists(self):
        w=Workspace(self.make_review().path)
        w.review.record_suggestion(0,0,'二',[10,10,90,90])
        self.assertEqual(w.snapshot()['review_flags']['0:0'],'disagreement')
        self.assertEqual(w.snapshot()['accepted'],{})
        w.action(dict(op='accept',page=0,index=0,text='一',box=[10,10,90,90],note='原稿是一'))
        w.action(dict(op='save'))
        other=Workspace(w.review.path);other.action(dict(op='restore',path=w.output))
        self.assertEqual(other.snapshot()['accepted']['0:0']['character'],'一')
        self.assertEqual(other.snapshot()['suggestions']['0:0']['text'],'二')
        self.assertEqual(other.snapshot()['annotations']['0:0'],'原稿是一')
        other.action(dict(op='flag',page=0,index=0,note='再次核对'))
        self.assertEqual(other.snapshot()['accepted'],{})
        other.action(dict(op='save'))
        restored=Workspace(w.review.path);restored.action(dict(op='restore',path=other.output))
        self.assertEqual(restored.snapshot()['review_flags']['0:0'],'manual')
        self.assertEqual(restored.snapshot()['accepted'],{})

    def test_uncertain_suggestion_and_crop_invalidation(self):
        w=Workspace(self.make_review().path)
        w.review.record_suggestion(0,0,'',[10,10,90,90])
        self.assertEqual(w.snapshot()['review_flags']['0:0'],'uncertain')
        w.action(dict(op='crop',page=0,index=0,box=[12,12,80,80]))
        self.assertEqual(w.snapshot()['suggestions'],{})
        self.assertIn('0:0',w.snapshot()['review_flags'])
    def test_edit_confirm_save_restore(self):
        r=self.make_review();w=Workspace(r.path)
        w.action(dict(op='accept',page=0,index=0,text='一',box=[10,10,90,90]))
        self.assertTrue(w.snapshot()['dirty'])
        w.action(dict(op='crop',page=0,index=0,box=[12,12,80,80]))
        self.assertEqual(w.snapshot()['accepted'],{})
        w.action(dict(op='note',page=0,index=0,note='check crop'))
        w.action(dict(op='save'))
        self.assertFalse(w.snapshot()['dirty'])
        other=Workspace(r.path);other.action(dict(op='restore',path=w.output))
        self.assertEqual(other.snapshot()['crops'],{'0:0':[12,12,80,80]})
        self.assertEqual(other.snapshot()['annotations'],{'0:0':'check crop'})
    def test_invalid_crop_does_not_change_state(self):
        w=Workspace(self.make_review().path)
        with self.assertRaises(ValueError):w.action(dict(op='crop',page=0,index=0,box=[-1,0,80,80]))
        self.assertEqual(w.snapshot()['crops'],{})
        self.assertFalse(w.snapshot()['dirty'])
    def test_busy_state_rejects_mutation(self):
        w=Workspace(self.make_review().path);w.job={'status':'running'}
        with self.assertRaises(ValueError):w.action(dict(op='note',page=0,index=0,note='not allowed'))
        self.assertEqual(w.snapshot()['annotations'],{})
    def test_delete_persists_and_undo_requires_reconfirmation(self):
        w=Workspace(self.make_review().path)
        original=w.review.path.read_bytes()
        w.action(dict(op='accept',page=0,index=0,text='一',box=[10,10,90,90]))
        w.action(dict(op='delete',page=0,index=0))
        self.assertEqual(w.snapshot()['deleted'],['0:0'])
        self.assertEqual(w.snapshot()['accepted'],{})
        self.assertTrue(w.snapshot()['dirty'])
        with self.assertRaises(ValueError):w.review.export(self.root/'deleted_font','test')
        with self.assertRaises(ValueError):w.action(dict(op='accept',page=0,index=0,text='一',box=[10,10,90,90]))
        w.action(dict(op='save'))
        other=Workspace(w.review.path)
        other.action(dict(op='restore',path=w.output))
        self.assertEqual(other.snapshot()['deleted'],['0:0'])
        other.action(dict(op='undo_delete'))
        self.assertEqual(other.snapshot()['deleted'],[])
        self.assertEqual(other.snapshot()['accepted'],{})
        self.assertEqual(w.review.path.read_bytes(),original)
        other.action(dict(op='accept',page=0,index=0,text='一',box=[10,10,90,90]))

    def test_invalid_deletion_preserves_state(self):
        w=Workspace(self.make_review().path)
        with self.assertRaises(ValueError):w.action(dict(op='delete',page=0,index=-1))
        self.assertEqual(w.snapshot()['deleted'],[])
        self.assertFalse(w.snapshot()['dirty'])
