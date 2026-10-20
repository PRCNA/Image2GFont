"""Loopback-only frontend bridge. Existing OCRReview remains the source of truth."""
import argparse, base64, io, json, secrets, subprocess, threading, time, webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from ocr_review import OCRReview

ROOT=Path(__file__).absolute().parent
WEB=ROOT/'frontend'

def runtime_python(kind):
    portable=ROOT/'runtime'/kind/'python.exe'
    return portable if portable.exists() else ROOT/('.venv-'+kind)/'Scripts/python.exe'


class Workspace:
    def __init__(self, results=None):
        self.review=OCRReview(results) if results else None
        self.lock=threading.RLock();self.job=None;self.revision=0
        self.output=None;self.suggestions={};self.dirty=False
    def snapshot(self):
        r=self.review
        return dict(revision=self.revision,job=self.job,output=self.output,dirty=self.dirty,dataset='' if r is None else r.results_sha256,
                    pages=[] if r is None else [dict(id=p['id'],characters=p['characters']) for p in r.data['images']],
                    accepted={} if r is None else r.accepted, annotations={} if r is None else r.annotations,
                    crops={} if r is None else r.crop_edits,suggestions={} if r is None else r.suggestions,
                    review_flags={} if r is None else r.review_flags,deleted=[] if r is None else r.deleted)
    def start_job(self, fn):
        if self.job and self.job['status']=='running':raise ValueError('A task is already running')
        self.job={'status':'running'}
        def work():
            try:
                result=fn()
                with self.lock:self.job={'status':'done','result':str(result)};self.revision+=1
            except Exception as exc:
                with self.lock:self.job={'status':'error','error':str(exc)};self.revision+=1
        threading.Thread(target=work,daemon=True).start()
    def folder(self, prefix):
        p=ROOT/'artifacts'/(prefix+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));p.mkdir(parents=True)
        return p
    def action(self, d):
        op=d['op'];r=self.review
        if self.job and self.job['status']=='running':raise ValueError('Wait for the current task to finish')
        if op=='load':
            self.review=OCRReview(Path(d['path']));self.suggestions={};self.output=None
        elif op=='import':
            folder=self.folder('frontend_import');paths=[]
            for n,item in enumerate(d['files']):
                suffix=Path(item['name']).suffix.lower()
                if suffix not in ('.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'):raise ValueError('Unsupported image')
                p=folder/(str(n)+suffix);p.write_bytes(base64.b64decode(item['data'],validate=True));paths.append(str(p))
            if not paths:raise ValueError('No images')
            def analyze():
                out=folder/'ocr'
                with (folder/'run.log').open('w',encoding='utf-8') as log:
                    subprocess.run([str(runtime_python('ocr')),str(ROOT/'ocr_demo.py'),*paths,'--output',str(out)],cwd=ROOT,stdout=log,stderr=log,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                with self.lock:self.review=OCRReview(out/'results.json');self.suggestions={};self.output=None
                return out/'results.json'
            self.start_job(analyze)
        elif op=='settings':
            target=ROOT/'artifacts/frontend_settings.json';target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(d['settings'],ensure_ascii=False,indent=2),encoding='utf-8')
        else:
            if r is None:raise ValueError('Open images or OCR results first')
            if op=='delete':r.delete_candidate(d['page'],d['index'])
            elif op=='undo_delete':r.undo_delete()
            elif op=='crop':r.edit_crop(d['page'],d['index'],d['box']);self.suggestions.pop(f"{d['page']}:{d['index']}",None)
            elif op=='accept':
                if 'note' in d and not isinstance(d['note'],str):raise ValueError('Invalid note')
                r.vision_mode='auto';r.accept(d['page'],d['index'],d['text'],d['box'])
                if 'note' in d:r.annotate(d['page'],d['index'],d['note'])
            elif op=='flag':
                if not isinstance(d.get('note',''),str):raise ValueError('Invalid note')
                r.flag_review(d['page'],d['index']);r.annotate(d['page'],d['index'],d.get('note',''))
            elif op=='note':r.annotate(d['page'],d['index'],d['note'])
            elif op=='unaccept':r.accepted.pop(f"{d['page']}:{d['index']}",None)
            elif op=='save':
                path=r.root/'frontend_review_session.json';r.save_session(path);self.output=str(path)
            elif op=='restore':r.restore_session(Path(d['path']))
            elif op=='export':
                destination=self.folder('frontend_export')/'font'
                def export():
                    project=r.export(destination,d.get('name') or 'Image2GFont')
                    if d.get('generate'):
                        from font_project import FontProject
                        project=FontProject.load(project).generate(destination/'generated')
                    with self.lock:self.output=str(project)
                    return project
                self.start_job(export)
            elif op=='recognize':
                page,index=d['page'],d['index'];box=d['box']
                from crop_editor import validate_box
                im=r.image(page);validate_box(box,im.size)
                folder=self.folder('frontend_recognition');source=folder/'crop.png';im.crop(box).save(source)
                def recognize():
                    with (folder/'run.log').open('w',encoding='utf-8') as log:
                        subprocess.run([str(runtime_python('vision')),'-m','vision_core.recognition',str(source),'--backend','qwen-crop','--output',str(folder/'output')],cwd=ROOT,stdout=log,stderr=log,timeout=300,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    result=json.loads((folder/'output/recognition.json').read_text(encoding='utf-8'))[0]
                    with self.lock:r.record_suggestion(page,index,result['text'],box);self.dirty=True
                    return result['text'] or '?'
                self.start_job(recognize)
            else:raise ValueError('Unknown action')
        if op in ('crop','accept','note','unaccept','flag','delete','undo_delete'):self.dirty=True
        elif op in ('save','restore','load','import'):self.dirty=False
        if self.job and self.job['status']=='error':self.job=None
        self.revision+=1
        return self.snapshot()

def make_server(workspace, port=0):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,body,kind='application/json',status=200):
            if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
        def authorized(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.authorized():self.send({},status=403);return
            path=urlparse(self.path).path
            try:
                if path=='/api/state':
                    with workspace.lock:self.send(workspace.snapshot())
                elif path=='/api/settings':
                    p=ROOT/'artifacts/frontend_settings.json';self.send(json.loads(p.read_text(encoding='utf-8')) if p.exists() else {})
                elif path.startswith('/api/image/'):
                    with workspace.lock:
                        im=workspace.review.image(int(path.rsplit('/',1)[1]));buf=io.BytesIO();im.save(buf,format='PNG')
                    self.send(buf.getvalue(),'image/png')
                elif path=='/bootstrap.js':self.send(('window.API_TOKEN='+json.dumps(token)+';').encode(),'text/javascript')
                else:
                    name={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/logo.svg':'logo.svg','/i18n.js':'i18n.js'}.get(path)
                    if not name:self.send({},status=404);return
                    kind={'html':'text/html','js':'text/javascript','css':'text/css','svg':'image/svg+xml'}[name.rsplit('.',1)[1]]
                    self.send((WEB/name).read_bytes(),kind)
            except Exception as exc:self.send({'error':str(exc)},status=400)
        def do_POST(self):
            if not self.authorized() or self.headers.get('X-Workspace-Token')!=token:self.send({},status=403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=100*1024*1024:raise ValueError('Request too large')
                d=json.loads(self.rfile.read(size))
                with workspace.lock:self.send(workspace.action(d))
            except Exception as exc:self.send({'error':str(exc)},status=400)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--results');parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');a=parser.parse_args()
    server=make_server(Workspace(a.results),a.port);url=f'http://127.0.0.1:{server.server_port}'
    print(url,flush=True)
    if not a.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
