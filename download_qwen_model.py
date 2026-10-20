"""Download pinned data-only NF4 checkpoint; verify published LFS hashes."""
import hashlib,json,shutil,urllib.request,time
from pathlib import Path

REPO='unsloth/Qwen3-VL-4B-Instruct-bnb-4bit'
REV='79cd853d0bc98bb0d67f865123eb49ef8985c2ec'
ROOT=Path(__file__).resolve().parent/'vision_models'/'Qwen3-VL-4B-Instruct-NF4'

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    meta=json.load(urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true',timeout=60))
    files=[f for f in meta['siblings'] if '/' not in f['rfilename'] and f['rfilename'].endswith(('.json','.safetensors','.txt','.jinja','.md'))]
    need=sum(f['size'] for f in files if not (ROOT/f['rfilename']).exists())
    if shutil.disk_usage(ROOT).free<need+2*1024**3:raise RuntimeError('Insufficient disk space with 2 GiB reserve')
    hashes={}
    for entry in files:
        name=entry['rfilename'];dest=ROOT/name
        if not dest.exists():
            print('Downloading '+name,flush=True)
            temp=dest.with_suffix(dest.suffix+'.part')
            with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REV}/{name}',timeout=120) as response,temp.open('wb') as out:
                count=0;last=time.monotonic()
                while True:
                    block=response.read(8*1024**2)
                    if not block:break
                    out.write(block);count+=len(block)
                    if time.monotonic()-last>20:print(f'{name}: {count/1024**2:.0f} MiB',flush=True);last=time.monotonic()
            if temp.stat().st_size!=entry['size']:raise ValueError('Size mismatch: '+name)
            expected=entry.get('lfs',{}).get('sha256')
            if expected and digest(temp)!=expected:raise ValueError('Hash mismatch: '+name)
            temp.replace(dest)
        hashes[name]=digest(dest)
        if entry.get('lfs',{}).get('sha256') not in (None,hashes[name]):raise ValueError('Existing hash mismatch: '+name)
    (ROOT/'provenance.json').write_text(json.dumps(dict(repository=REPO,revision=REV,sha256=hashes),indent=2),encoding='utf-8')
    print('Download verified',flush=True)

if __name__=='__main__':main()
