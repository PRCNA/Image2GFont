"""Small reproducible sanity check, not a general handwriting benchmark."""
import json,time
from pathlib import Path
from PIL import Image
from vision_core.recognition import PaddleVLRecognizer,LOCAL_MODEL

root=Path('artifacts/vision_recognition_inputs')
out=Path('artifacts/vision_recognition_validation');out.mkdir(exist_ok=False)
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
t0=time.perf_counter();engine=PaddleVLRecognizer(str(LOCAL_MODEL));init=time.perf_counter()-t0
rows=[]
for entry in manifest:
    t=time.perf_counter()
    with Image.open(root/entry['file']) as im:result=engine.recognize(im)
    rows.append(dict(**entry,**result,seconds=time.perf_counter()-t,correct=result['text']==entry['truth'],rapidocr_correct=entry['rapidocr']==entry['truth']))
    (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(entry['file'],ascii(result['text']),rows[-1]['correct'],flush=True)
summary=dict(samples=len(rows),paddle_vl_exact=sum(r['correct'] for r in rows),rapidocr_exact=sum(r['rapidocr_correct'] for r in rows),initialization_seconds=init,inference_seconds=sum(r['seconds'] for r in rows),gpu_peak_allocated_bytes=engine.torch.cuda.max_memory_allocated() if engine.device=='cuda' else None,model_parameters=sum(p.numel() for p in engine.model.parameters()),scope='11 selected crops only; 8 are earlier debugging examples; RapidOCR text was from full-page inference, not identical crop inference')
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print(summary,flush=True)
