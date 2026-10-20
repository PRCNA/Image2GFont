import json,unittest,tempfile,hashlib
from pathlib import Path
from PIL import Image
from vision_core.qwen_page import parse_proposals
from ocr_review import OCRReview

class QwenProposalTests(unittest.TestCase):
    def test_structured_output_allows_more_than_twenty_candidates(self):
        from lmformatenforcer import JsonSchemaParser
        from vision_core.qwen_page import OUTPUT_SCHEMA
        text=json.dumps({'characters':[{'text':'A','bbox':[1,2,3,4]} for _ in range(25)]})
        parser=JsonSchemaParser(OUTPUT_SCHEMA)
        for character in text:
            self.assertIn(character,parser.get_allowed_characters())
            parser=parser.add_character(character)
        self.assertTrue(parser.can_end())
    def test_mapping_and_no_confidence_fabrication(self):
        rows,bad=parse_proposals('{"characters":[{"text":"A","bbox":[100,200,300,400]}]}',(200,100))
        self.assertEqual(rows[0]['box'],[[20,20],[60,20],[60,40],[20,40]])
        self.assertIsNone(rows[0]['score']);self.assertFalse(rows[0]['binding_confirmed']);self.assertEqual(bad,[])
    def test_reject_bad_boxes_and_multichar(self):
        candidates=[dict(text='AB',bbox=[0,0,10,10]),dict(text='A',bbox=[10,0,0,10]),dict(text='A',bbox=[0,0,1001,10]),dict(text='A',bbox=[True,0,10,10])]
        good,bad=parse_proposals(json.dumps(dict(characters=candidates)),(100,100));self.assertEqual(good,[]);self.assertEqual(len(bad),4)
    def test_truncated_output_fails(self):
        with self.assertRaises(ValueError):parse_proposals('{"characters":[',(100,100))
    def test_fenced_json(self):
        self.assertEqual(parse_proposals('```json\n{"characters":[]}\n```',(100,100)),([],[]))
    def test_review_remains_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'original.png';Image.new('RGB',(100,100),'white').save(image)
            chars,_=parse_proposals('{"characters":[{"text":"A","bbox":[100,100,900,900]}]}',(100,100))
            path=root/'results.json';path.write_text(json.dumps(dict(images=[dict(file='original.png',sha256=hashlib.sha256(image.read_bytes()).hexdigest(),characters=chars)])),encoding='utf-8')
            review=OCRReview(path);self.assertEqual(review.accepted,{})
            review.accept(0,0,'A',[10,10,90,90]);self.assertEqual(len(review.accepted),1)
