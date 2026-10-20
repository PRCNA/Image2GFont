from pathlib import Path
import hashlib,json,zipfile
out=Path(r'D:\Software\写字机\Image2GFont_Portable_Build');app=out/'Image2GFont'
archive=out/'Image2GFont_Portable_2026-10-13.zip'
files=sorted(p for p in app.rglob('*') if p.is_file() and 'artifacts' not in p.relative_to(app).parts and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='PACKAGE_MANIFEST.json')
manifest={}
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
 for i,p in enumerate(files):
  rel=p.relative_to(app).as_posix();h=hashlib.sha256()
  with p.open('rb') as f,z.open('Image2GFont/'+rel,'w',force_zip64=True) as target:
   while block:=f.read(4*1024*1024):h.update(block);target.write(block)
  manifest[rel]={'size':p.stat().st_size,'sha256':h.hexdigest()}
  if i%3000==0:print('Packed',i,'/',len(files),flush=True)
 text=json.dumps(manifest,ensure_ascii=False,indent=2)
 (app/'PACKAGE_MANIFEST.json').write_text(text,encoding='utf-8');z.writestr('Image2GFont/PACKAGE_MANIFEST.json',text)
print('Checking ZIP CRC',flush=True)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
h=hashlib.sha256()
with archive.open('rb') as f:
 while block:=f.read(8*1024*1024):h.update(block)
archive.with_suffix('.zip.sha256').write_text(h.hexdigest()+'  '+archive.name+'\n')
print('VERIFIED',archive,archive.stat().st_size,flush=True)
