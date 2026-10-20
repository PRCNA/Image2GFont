from pathlib import Path
import json,time
import numpy as np
from PIL import Image
from ocr_demo import engine
import argparse
p=argparse.ArgumentParser();p.add_argument('--recognition-only',action='store_true');args=p.parse_args()
root=Path('artifacts/vision_recognition_inputs');rows=json.loads((root/'manifest.json').read_text(encoding='utf-8'));backend=engine();out=[]
for row in rows:
 start=time.perf_counter()
 with Image.open(root/row['file']) as im:result=backend(np.asarray(im.convert('RGB'))[:,:,::-1].copy(),use_det=not args.recognition_only,use_cls=not args.recognition_only)
 text=''.join(result.txts or [])
 out.append(dict(**row,text=text,correct=text==row['truth'],seconds=time.perf_counter()-start))
 print(row['file'],ascii(text),out[-1]['correct'],flush=True)
(Path('artifacts/vision_recognition_validation')/('rapidocr_recognition_only.json' if args.recognition_only else 'rapidocr_same_crops.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
