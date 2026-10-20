import urllib.request,json,hashlib,time
from pathlib import Path
meta=json.loads(Path('artifacts/paddle_vl_model_metadata.json').read_text(encoding='utf-8'));rev=meta['sha'];root=Path('vision_models/PaddleOCR-VL-1.6');root.mkdir(parents=True,exist_ok=True)
files=[x['rfilename'] for x in meta['siblings'] if '/' not in x['rfilename'] and not x['rfilename'].endswith('.py') and not x['rfilename'].startswith('.')]
for name in files:
 dest=root/name
 if dest.exists():continue
 url='https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/resolve/'+rev+'/'+name
 print('Downloading',name,flush=True)
 with urllib.request.urlopen(url,timeout=120) as response, dest.with_suffix(dest.suffix+'.part').open('wb') as f:
  while True:
   block=response.read(8*1024*1024)
   if not block:break
   f.write(block)
 dest.with_suffix(dest.suffix+'.part').replace(dest)
(root/'provenance.json').write_text(json.dumps(dict(repository=meta['id'],revision=rev,sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}),indent=2))
print('Model downloaded',flush=True)
