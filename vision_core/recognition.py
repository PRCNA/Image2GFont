"""Local PaddleOCR-VL crop recognition; suggestions never mutate glyph geometry."""
from pathlib import Path
import argparse,json,time,hashlib
from PIL import Image,ImageOps

MODEL='PaddlePaddle/PaddleOCR-VL-1.6'
ROOT=Path(__file__).resolve().parents[1]
LOCAL_MODEL=ROOT/'vision_models'/'PaddleOCR-VL-1.6'

class PaddleVLRecognizer:
    def __init__(self,model=MODEL,cache_dir=None):
        import torch
        from transformers import AutoProcessor,AutoModelForImageTextToText
        self.torch=torch;self.model_id=model
        self.device='cuda' if torch.cuda.is_available() else 'cpu'
        dtype=torch.bfloat16 if self.device=='cuda' else torch.float32
        self.processor=AutoProcessor.from_pretrained(model,cache_dir=cache_dir)
        self.model=AutoModelForImageTextToText.from_pretrained(model,cache_dir=cache_dir,dtype=dtype).to(self.device).eval()
    def recognize(self,image):
        messages=[dict(role='user',content=[dict(type='image',image=image.convert('RGB')),dict(type='text',text='OCR:')])]
        inputs=self.processor.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            result=self.model.generate(**inputs,max_new_tokens=128,do_sample=False)
        text=self.processor.decode(result[0][inputs['input_ids'].shape[-1]:],skip_special_tokens=True).strip()
        return dict(text=text,confidence=None,backend=self.model_id,binding_confirmed=False,device=self.device,model_revision=getattr(self.model.config,'_commit_hash',None))


class RapidOCRRecognizer:
    """Recognition-only baseline for a crop; do not detect a page again."""
    def __init__(self):
        from ocr_demo import engine
        self.engine=engine()
    def recognize(self,image):
        import numpy as np
        result=self.engine(np.asarray(image.convert('RGB'))[:,:,::-1].copy(),use_det=False,use_cls=False)
        return dict(text=''.join(result.txts or []),confidence=None,backend='PP-OCRv5_server_rec_only',binding_confirmed=False,device='cpu')


def main():
    p=argparse.ArgumentParser();p.add_argument('images',nargs='+');p.add_argument('--output',required=True);p.add_argument('--backend',choices=['paddle-vl','ppocr','qwen-crop'],default='paddle-vl');p.add_argument('--model');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    if a.backend=='qwen-crop':
        from .qwen_recognition import QwenCropRecognizer, LOCAL_MODEL as QWEN_MODEL
        backend=QwenCropRecognizer(a.model or QWEN_MODEL)
    else:
        backend=PaddleVLRecognizer(a.model or (str(LOCAL_MODEL) if LOCAL_MODEL.exists() else MODEL),str(ROOT/'vision_models')) if a.backend=='paddle-vl' else RapidOCRRecognizer()
    rows=[]
    for path in map(Path,a.images):
        start=time.perf_counter()
        with Image.open(path) as im:result=backend.recognize(ImageOps.exif_transpose(im))
        rows.append(dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),seconds=time.perf_counter()-start,**result))
        (out/'recognition.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(path.name,ascii(result['text']),flush=True)
if __name__=='__main__':main()
