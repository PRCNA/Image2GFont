import unittest
from vision_core.qwen_recognition import suggestion
from tests import test_ocr_review as helpers
from ocr_review import OCRReview

class CropSuggestionTests(unittest.TestCase):
    def test_single_character_remains_unconfirmed(self):
        result=suggestion(' 若\n')
        self.assertEqual(result['text'],'若')
        self.assertFalse(result['binding_confirmed'])
        self.assertTrue(result['needs_review'])

    def test_uncertain_and_invalid_outputs_are_not_bindings(self):
        for raw in ('?', '', '两个', 'I think 若', '😀'):
            result=suggestion(raw)
            self.assertEqual(result['text'],'')
            self.assertTrue(result['ambiguous'])

class AnnotationTests(unittest.TestCase):
    setUp=helpers.OCRReviewTests.setUp
    tearDown=helpers.OCRReviewTests.tearDown
    page=helpers.OCRReviewTests.page
    make_review=helpers.OCRReviewTests.make_review
    def test_crop_edit_invalidates_confirmation_and_survives_restore(self):
        review=self.make_review();review.accept(0,0,'一',[10,10,90,90])
        review.edit_crop(0,0,[12,13,80,81])
        self.assertEqual(review.accepted,{})
        path=self.root/'crop_session.json';review.save_session(path)
        restored=OCRReview(review.path);restored.restore_session(path)
        self.assertEqual(restored.crop_edits,{'0:0':[12,13,80,81]})
        with self.assertRaises(ValueError):restored.edit_crop(0,0,[-1,0,80,81])
        self.assertEqual(restored.crop_edits,review.crop_edits)

    def test_unconfirmed_annotation_persists(self):
        review=self.make_review()
        review.annotate(0,0,'若/苦：待人工确认')
        path=self.root/'annotated.json';review.save_session(path)
        restored=OCRReview(review.path);restored.restore_session(path)
        self.assertEqual(restored.annotations,review.annotations)
        self.assertEqual(restored.accepted,{})
