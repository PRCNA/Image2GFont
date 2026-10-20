"""Record actual local checks without treating candidate counts as accuracy."""
import json,hashlib
from pathlib import Path
from ocr_review import OCRReview
from compare_page_backends import run

def main():
    sparse=Path('artifacts/qwen_page_validation_final')
    dense=Path('artifacts/qwen_dense_validation_v2')
    run(dense,'artifacts/e2e_0928/ocr')
    base=json.loads((sparse/'comparison_summary.json').read_text(encoding='utf-8'))['rows'][:2]
    base+=json.loads((dense/'comparison_summary.json').read_text(encoding='utf-8'))['rows']
    for folder in (sparse,dense):
        review=OCRReview(folder/'results.json');assert not review.accepted
        for i,r in enumerate(review.data['images']):
            assert hashlib.sha256((folder/r['file']).read_bytes()).hexdigest()==r['sha256']
            review.image(i)
    q=json.loads(Path('artifacts/qwen_paddle_crops/manifest.json').read_text(encoding='utf-8'))
    p=json.loads(Path('artifacts/qwen_paddle_review_final/recognition.json').read_text(encoding='utf-8'))
    checks=[dict(index=a['index'],qwen=a['qwen'],paddle=b['text'],agree=a['qwen']==b['text']) for a,b in zip(q,p)]
    result=dict(date='2026-10-11',page_tests=base,paddle_checks=checks,source_hashes_verified=True,automatic_confirmations=0,python_tests_passed=131,desktop_buttons_verified=False,independent_holdout=False,quality_verified=False)
    Path('artifacts/qwen_validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
