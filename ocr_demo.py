"""Local OCR demo. Recognition suggestions never modify font projects."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import time
import zipfile
import io
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parent


def engine():
    from rapidocr import RapidOCR,ModelType,OCRVersion,EngineType
    return RapidOCR(params={
        'Global.model_root_dir':str(ROOT/'ocr_models'),
        'Global.font_path':'C:/Windows/Fonts/msyh.ttc',
        'EngineConfig.onnxruntime.intra_op_num_threads':4,
        'EngineConfig.onnxruntime.inter_op_num_threads':1,
        'Global.text_score':0.0,
        'Det.limit_side_len':1280,
        'Det.limit_type':'min',
        'Det.engine_type':EngineType.ONNXRUNTIME,'Rec.engine_type':EngineType.ONNXRUNTIME,
        'Det.ocr_version':OCRVersion.PPOCRV5,'Rec.ocr_version':OCRVersion.PPOCRV5,
        'Det.model_type':ModelType.SERVER,'Rec.model_type':ModelType.SERVER})


def serial(value):
    if hasattr(value,'tolist'):return value.tolist()
    if isinstance(value,(tuple,list)):return [serial(v) for v in value]
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    return value


def run(paths,out):
    import numpy as np
    import importlib.metadata
    out=Path(out);out.mkdir(parents=True,exist_ok=False);(out/'originals').mkdir();(out/'images').mkdir()
    sources=[]
    for path in map(Path,paths):
        if path.suffix.lower()=='.zip':
            with zipfile.ZipFile(path) as z:
                selected=[e for e in z.infolist() if not e.is_dir() and Path(e.filename).suffix.lower() in ('.png','.jpg','.jpeg','.bmp','.tif','.webp')]
                if len(selected)>500 or sum(e.file_size for e in selected)>500*1024**2:raise ValueError('Archive exceeds demo image limits')
                sources.extend((path.name+'/'+e.filename,z.read(e)) for e in selected)
        else:sources.append((path.name,path.read_bytes()))
    if not sources:raise ValueError('No supported images')
    manifest=[]
    for i,(name,data) in enumerate(sources):
        key=f'image_{i+1:02d}';suffix=Path(name).suffix.lower();dest=out/'originals'/(key+suffix)
        dest.write_bytes(data);dest.chmod(0o444)
        manifest.append(dict(id=key,source=name,file=str(dest.relative_to(out)),sha256=hashlib.sha256(data).hexdigest()))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    config=dict(engine='RapidOCR',version=importlib.metadata.version('rapidocr'),onnxruntime=importlib.metadata.version('onnxruntime'),detector='PP-OCRv5_server',recognizer='PP-OCRv5_server',text_score=0,review_threshold=.8,ground_truth_available=False,det_limit_side_len=1280,det_limit_type='min',cpu_threads=4)
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    ocr=engine();results=[]
    from omegaconf import OmegaConf
    (out/'effective_config.yaml').write_text(OmegaConf.to_yaml(ocr.cfg),encoding='utf-8')
    (out/'model_hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ocr_models').glob('*.onnx')},indent=2),encoding='utf-8')
    for entry in manifest:
        start=time.perf_counter();row=dict(**entry,lines=[],characters=[],status='ok')
        try:
            data=(out/entry['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256']
            image=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB');image.save(out/'images'/(entry['id']+'.png'))
            row.update(image='images/'+entry['id']+'.png',size=list(image.size))
            result=ocr(np.asarray(image)[:,:,::-1].copy(),return_word_box=True,return_single_char_box=True)
            if result.txts:
                for box,text,score in zip(result.boxes,result.txts,result.scores):row['lines'].append(dict(box=serial(box),text=text,score=float(score)))
            if result.word_results:
                for line in result.word_results:
                    for text,score,box in line:
                        if box is not None:row['characters'].append(dict(text=text,score=float(score),box=serial(box)))
        except Exception as exc:row.update(status='failed',error=repr(exc))
        row['seconds']=round(time.perf_counter()-start,3);results.append(row)
        (out/'results.json').write_text(json.dumps(dict(config=config,images=results),ensure_ascii=False,indent=2),encoding='utf-8')
        print(entry['id'],row['status'],len(row['lines']),len(row['characters']),row['seconds'],flush=True)
    template=(ROOT/'ocr_demo.html').read_text(encoding='utf-8')
    payload=json.dumps(dict(config=config,images=results),ensure_ascii=False).replace('<','\\u003c')
    (out/'index.html').write_text(template.replace('__RESULT_DATA__',payload),encoding='utf-8')
    summary=dict(images=len(results),completed=sum(r['status']=='ok' for r in results),lines=sum(len(r['lines']) for r in results),characters=sum(len(r['characters']) for r in results),low_confidence_lines=sum(x['score']<.8 for r in results for x in r['lines']),seconds=sum(r['seconds'] for r in results))
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
    return out/'index.html'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('inputs',nargs='*');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.inputs:
        if not args.output:parser.error('--output is required for batch mode')
        run(args.inputs,args.output);return
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    import threading,queue,webbrowser
    from datetime import datetime
    root=tk.Tk();root.title('Image2GFont OCR Demo');root.geometry('650x180');events=queue.Queue()
    status=tk.StringVar(value='\u9009\u62e9\u56fe\u7247\u6216ZIP\uff1b\u5728\u672c\u5730\u8bc6\u522b\uff0c\u5b8c\u6210\u540e\u6253\u5f00\u5bf9\u7167\u9875\u3002')
    ttk.Label(root,textvariable=status,wraplength=620,padding=15).pack(fill='x')
    def start():
        files=filedialog.askopenfilenames(filetypes=[('Images / ZIP','*.png *.jpg *.jpeg *.bmp *.zip *.webp')])
        if not files:return
        button.configure(state='disabled');status.set('\u6b63\u5728\u8bc6\u522b\uff1b\u9996\u6b21\u8fd0\u884c\u53ef\u80fd\u9700\u8981\u4e0b\u8f7d\u6a21\u578b\u3002')
        out=ROOT/'artifacts'/('ocr_demo_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        def work():
            try:events.put(('ok',run(files,out)))
            except Exception as exc:events.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def poll():
        try:
            kind,value=events.get_nowait();button.configure(state='normal')
            if kind=='ok':status.set(str(value));webbrowser.open(value.resolve().as_uri())
            else:status.set('\u8bc6\u522b\u5931\u8d25');messagebox.showerror('OCR',value)
        except queue.Empty:pass
        root.after(200,poll)
    button=ttk.Button(root,text='\u9009\u62e9\u56fe\u7247 / ZIP \u5f00\u59cb\u8bc6\u522b',command=start);button.pack();poll();root.mainloop()


if __name__=='__main__':main()
