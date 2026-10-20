from pathlib import Path
import shutil,subprocess,json,hashlib,zipfile,time
root=Path(__file__).resolve().parent
out=Path(r'D:\Software\写字机\Image2GFont_Portable_Build')
app=out/'Image2GFont';app.mkdir(parents=True,exist_ok=True)
def ignore(folder,names):return [n for n in names if n in ('__pycache__','.cache','.git') or n.endswith(('.pyc','.pyo'))]
for p in root.iterdir():
 if p.is_file() and p.suffix in ('.py','.pyw','.md','.toml','.txt','.cs','.html'):shutil.copy2(p,app/p.name)
for name in ('frontend','gfont_core','image_pipeline','coordinate_editor','stroke_editor','vision_core'):
 shutil.copytree(root/name,app/name,dirs_exist_ok=True,ignore=ignore)
for kind,base in [('vision',Path(r'C:\Users\YOUR_USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\python')),('ocr',Path(r'C:\Users\YOUR_USER\AppData\Local\Programs\Python\Python39'))]:
 target=app/'runtime'/kind;target.mkdir(parents=True,exist_ok=True)
 print('Copy runtime '+kind,flush=True)
 for p in base.iterdir():
  if p.is_file() and p.suffix in ('.exe','.dll','.txt'):shutil.copy2(p,target/p.name)
 for name in ('DLLs','tcl'):
  if (base/name).exists():shutil.copytree(base/name,target/name,dirs_exist_ok=True,ignore=ignore)
 shutil.copytree(base/'Lib',target/'Lib',dirs_exist_ok=True,ignore=lambda d,ns:ignore(d,ns)+(['site-packages'] if Path(d)==base/'Lib' else []))
 shutil.copytree(root/('.venv-'+kind)/'Lib/site-packages',target/'Lib/site-packages',dirs_exist_ok=True,ignore=ignore)
print('Copy OCR and Qwen models',flush=True)
shutil.copytree(root/'ocr_models',app/'ocr_models',dirs_exist_ok=True,ignore=ignore)
shutil.copytree(root/'vision_models/Qwen3-VL-4B-Instruct-NF4',app/'vision_models/Qwen3-VL-4B-Instruct-NF4',dirs_exist_ok=True,ignore=ignore)
subprocess.run([r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe','/nologo','/target:winexe','/platform:x64','/reference:System.Windows.Forms.dll','/win32icon:'+str(app/'frontend/logo.ico'),'/out:'+str(app/'Image2GFont.exe'),str(root/'portable_launcher.cs')],check=True)
(app/'artifacts').mkdir(exist_ok=True)
(app/'打开说明.txt').write_text('双击 Image2GFont.exe。请完整解压后使用，不要单独移动 EXE。\n已包含 Python、OCR、千问 NF4 模型，无需安装 Python。Windows 10/11 x64 需要 WebView2 运行时。千问需要兼容的 NVIDIA 驱动与足够显存；之前显存错误仍需在目标机器验证。\n未包含原始用户图片、字体样本或审核进度。PaddleOCR-VL 辅助实验模型不包含在此主流程包中。\n',encoding='utf-8')
print('BUILD_READY '+str(app),flush=True)
