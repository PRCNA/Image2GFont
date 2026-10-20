"""Explicit human review of OCR boxes before creating page/font projects."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageOps
from page_import import PageProject
from font_project import FontProject


class OCRReview:
    def __init__(self, results):
        self.path=Path(results);self.root=self.path.parent
        raw=self.path.read_bytes();self.results_sha256=hashlib.sha256(raw).hexdigest()
        self.data=json.loads(raw.decode('utf-8'))
        self.accepted={};self.vision_mode=None;self.annotations={};self.crop_edits={};self.suggestions={};self.review_flags={};self.deleted=[]

    def delete_candidate(self,page,index):
        if type(page) is not int or not 0<=page<len(self.data['images']):raise ValueError('Invalid page')
        if type(index) is not int or not 0<=index<len(self.data['images'][page]['characters']):raise ValueError('Invalid candidate')
        key=f'{page}:{index}'
        if key not in self.deleted:self.deleted.append(key)
        self.accepted.pop(key,None)

    def undo_delete(self):
        if not self.deleted:raise ValueError('No deleted candidates')
        return self.deleted.pop()

    def flag_review(self,page,index,reason='manual'):
        if reason not in ('manual','disagreement','uncertain'):raise ValueError('Invalid review reason')
        if type(page) is not int or not 0<=page<len(self.data['images']):raise ValueError('Invalid page')
        if type(index) is not int or not 0<=index<len(self.data['images'][page]['characters']):raise ValueError('Invalid candidate')
        key=f'{page}:{index}';self.review_flags[key]=reason;self.accepted.pop(key,None)

    def record_suggestion(self,page,index,text,box):
        from crop_editor import validate_box
        if type(page) is not int or not 0<=page<len(self.data['images']):raise ValueError('Invalid page')
        if type(index) is not int or not 0<=index<len(self.data['images'][page]['characters']):raise ValueError('Invalid candidate')
        if not isinstance(text,str) or len(text)>1:raise ValueError('Invalid suggestion')
        checked=validate_box(box,self.image(page).size);key=f'{page}:{index}'
        baseline=self.accepted.get(key,{}).get('character',self.data['images'][page]['characters'][index]['text'])
        self.suggestions[key]=dict(text=text,box=checked)
        if not text or text=='?':self.flag_review(page,index,'uncertain')
        elif text!=baseline:self.flag_review(page,index,'disagreement')

    def edit_crop(self,page,index,box):
        from crop_editor import validate_box
        if type(page) is not int or not 0<=page<len(self.data['images']):raise ValueError('Invalid page')
        if type(index) is not int or not 0<=index<len(self.data['images'][page]['characters']):raise ValueError('Invalid candidate')
        checked=validate_box(box,self.image(page).size)
        key=f'{page}:{index}'
        self.crop_edits[key]=checked
        self.accepted.pop(key,None)
        self.suggestions.pop(key,None)

    def annotate(self,page,index,note):
        if type(page) is not int or not 0<=page<len(self.data['images']):raise ValueError('Invalid page')
        if type(index) is not int or not 0<=index<len(self.data['images'][page]['characters']):raise ValueError('Invalid candidate')
        if not isinstance(note,str):raise ValueError('Invalid note')
        self.annotations[f'{page}:{index}']=note

    def image(self,index):
        row=self.data['images'][index]
        source=(self.root/row['file']).resolve()
        if self.root.resolve() not in source.parents:raise ValueError('Source outside results directory')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Source hash mismatch')
        with Image.open(source) as im:return ImageOps.exif_transpose(im).convert('RGB')

    def accept(self,page,index,character,box):
        if type(page) is not int or not 0 <= page < len(self.data['images']):raise ValueError('Invalid page index')
        row=self.data['images'][page]
        if type(index) is not int or not 0 <= index < len(row['characters']):raise ValueError('Invalid candidate index')
        if f'{page}:{index}' in self.deleted:raise ValueError('Candidate deleted; restore it first')
        candidate=row['characters'][index]
        w,h=self.image(page).size
        if len(character)!=1 or character.isspace() or not 0<ord(character)<=65535 or 0xD800<=ord(character)<=0xDFFF:raise ValueError('One BMP character required')
        if len(box)!=4 or any(type(v) is not int for v in box):raise ValueError('Integer rectangle required')
        x0,y0,x1,y1=box
        if not 0<=x0<x1<=w or not 0<=y0<y1<=h:raise ValueError('Rectangle outside image')
        from vision_core.segmentation import MODES
        if self.vision_mode is not None and self.vision_mode not in MODES:raise ValueError('Unknown vision mode')
        key=f'{page}:{index}'
        if any(v['character']==character for k,v in self.accepted.items() if k!=key):raise ValueError('Character already confirmed; remove the earlier selection first')
        self.accepted[key]=dict(page=page,index=index,character=character,box=box,ocr_original=candidate['text'],ocr_box=candidate['box'],source_sha256=row['sha256'])
        if self.vision_mode is not None:self.accepted[key]['vision_mode']=self.vision_mode

    def save_session(self,path):
        payload=dict(format='Image2GFontOCRSession',schema_version=1,
                     results_sha256=self.results_sha256,
                     confirmed=list(self.accepted.values()),vision_mode=self.vision_mode,annotations=self.annotations,crop_edits=self.crop_edits,suggestions=self.suggestions,review_flags=self.review_flags,deleted=self.deleted)
        path=Path(path)
        temp=path.with_name(path.name+'.tmp')
        temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(path)

    def restore_session(self,path):
        doc=json.loads(Path(path).read_text(encoding='utf-8'))
        if doc.get('format')!='Image2GFontOCRSession' or doc.get('schema_version')!=1:
            raise ValueError('Unsupported review session')
        if doc.get('results_sha256')!=self.results_sha256 or hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.results_sha256:
            raise ValueError('Session belongs to different OCR results')
        if not isinstance(doc.get('confirmed'),list):raise ValueError('Invalid confirmed list')
        mode=doc.get('vision_mode')
        from vision_core.segmentation import MODES
        if mode is not None and mode not in MODES:raise ValueError('Unknown vision mode')
        checked=OCRReview(self.path)
        for key,box in doc.get('crop_edits',{}).items():
            p,i=map(int,key.split(':'));checked.edit_crop(p,i,box)
        for key,suggestion in doc.get('suggestions',{}).items():
            p,i=map(int,key.split(':'));checked.record_suggestion(p,i,suggestion['text'],suggestion['box'])
        for key,reason in doc.get('review_flags',{}).items():
            p,i=map(int,key.split(':'));checked.flag_review(p,i,reason)
        for v in doc['confirmed']:
            key=f"{v['page']}:{v['index']}"
            if key in checked.accepted:raise ValueError('Duplicate candidate in session')
            checked.vision_mode=v.get('vision_mode')
            checked.accept(v['page'],v['index'],v['character'],v['box'])
            if checked.accepted[key]!=v:raise ValueError('Candidate provenance mismatch')
        for key,note in doc.get('annotations',{}).items():
            p,i=map(int,key.split(':'));checked.annotate(p,i,note)
        deleted=doc.get('deleted',[])
        if not isinstance(deleted,list) or any(not isinstance(k,str) for k in deleted) or len(set(deleted))!=len(deleted):raise ValueError('Invalid deleted candidates')
        for key in deleted:
            p,i=map(int,key.split(':'))
            if key!=f'{p}:{i}' or key in checked.accepted:raise ValueError('Invalid deleted candidate')
            checked.delete_candidate(p,i)
        # Validate every entry before replacing current work.
        self.accepted=checked.accepted;self.vision_mode=mode;self.annotations=checked.annotations;self.crop_edits=checked.crop_edits
        self.suggestions=checked.suggestions;self.review_flags=checked.review_flags;self.deleted=checked.deleted

    def export(self,destination,name):
        if not self.accepted:raise ValueError('No confirmed characters')
        for v in self.accepted.values():self.image(v['page'])
        root=Path(destination)
        if root.exists():raise FileExistsError(root)
        font=FontProject.create(root,name)
        if self.vision_mode is not None:font.data['vision_mode']=self.vision_mode;font.save()
        for page in sorted({v['page'] for v in self.accepted.values()}):
            row=self.data['images'][page]
            p=PageProject.create(self.root/row['file'],root/('reviewed_%03d'%page))
            p.data['regions']=[dict(box=v['box'],character=v['character'],**({'vision_mode':v['vision_mode']} if 'vision_mode' in v else {})) for v in self.accepted.values() if v['page']==page]
            p.save();font.add_page(p.root/'page.json')
        (root/'ocr_review.json').write_text(json.dumps(dict(format='Image2GFontOCRReview',schema_version=1,confirmed=list(self.accepted.values()),annotations=self.annotations,suggestions=self.suggestions,review_flags=self.review_flags,deleted=self.deleted),ensure_ascii=False,indent=2),encoding='utf-8')
        return root/'font_project.json'


def main(results_path=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox,simpledialog
    from PIL import ImageTk
    from datetime import datetime
    root=tk.Tk();root.title('OCR 单字审核 → 字体工程');root.geometry('1200x850')
    path=results_path or filedialog.askopenfilename(title='选择 OCR results.json',filetypes=[('OCR results','results.json')],parent=root)
    if not path:root.destroy();return
    review=OCRReview(path);state=dict(page=0,index=0,scale=1,origin=(0,0),box=None,start=None,photo=None)
    bar=ttk.Frame(root);bar.pack(fill='x')
    pages=ttk.Combobox(bar,state='readonly',values=[r['id'] for r in review.data['images']]);pages.pack(side='left');pages.current(0)
    char=tk.StringVar();ttk.Label(bar,text='字符：').pack(side='left');ttk.Entry(bar,textvariable=char,width=8).pack(side='left')
    status=tk.StringVar(value='从左侧图片或右侧列表选字，点击修改裁切。核对字符与完整笔画后确认。')
    ttk.Label(root,textvariable=status).pack(fill='x')
    body=ttk.Frame(root);body.pack(fill='both',expand=True)
    sidebar=ttk.Frame(body);sidebar.pack(side='right',fill='y')
    listing=tk.Listbox(sidebar,width=24,exportselection=False);listing.pack(side='left',fill='y')
    scroll=ttk.Scrollbar(sidebar,command=listing.yview);scroll.pack(side='right',fill='y');listing.configure(yscrollcommand=scroll.set)
    canvas=tk.Canvas(body,bg='#ddd');canvas.pack(side='left',fill='both',expand=True)
    def safe(fn):
        try:fn()
        except Exception as exc:messagebox.showerror('操作未完成',str(exc),parent=root)
    def draw_box():
        canvas.delete('box');b=state['box']
        if b:
            ox,oy=state['origin'];s=state['scale'];canvas.create_rectangle((b[0]-ox)*s,(b[1]-oy)*s,(b[2]-ox)*s,(b[3]-oy)*s,outline='#e66b00',width=2,tags='box')
    def show():
        if not listing.curselection():return
        i=listing.curselection()[0];state['index']=i;p=state['page'];r=review.data['images'][p]['characters'][i]
        im=review.image(p);points=r['box'];box=[max(0,math.floor(min(v[0] for v in points))),max(0,math.floor(min(v[1] for v in points))),min(im.width,math.ceil(max(v[0] for v in points))),min(im.height,math.ceil(max(v[1] for v in points)))]
        accepted=review.accepted.get(f'{p}:{i}');box=accepted['box'] if accepted else review.crop_edits.get(f'{p}:{i}',box);char.set(accepted['character'] if accepted else r['text']);state['box']=box
        if accepted and 'vision_mode' in accepted:mode.set(accepted['vision_mode'])
        ox=oy=0;crop=im
        scale=min(max(300,canvas.winfo_width())/crop.width,max(300,canvas.winfo_height())/crop.height,4)
        state.update(origin=(ox,oy),scale=scale,photo=ImageTk.PhotoImage(crop.resize((max(1,round(crop.width*scale)),max(1,round(crop.height*scale))))))
        canvas.delete('all');canvas.create_image(0,0,image=state['photo'],anchor='nw')
        for j,candidate in enumerate(review.data['images'][p]['characters']):
            pts=candidate['box'];b=review.accepted.get(f'{p}:{j}',{}).get('box',review.crop_edits.get(f'{p}:{j}',[min(v[0] for v in pts),min(v[1] for v in pts),max(v[0] for v in pts),max(v[1] for v in pts)]))
            canvas.create_rectangle(*[v*scale for v in b],outline='#84939c',width=1)
        draw_box()
        score=f'{r["score"]:.3f}' if isinstance(r.get('score'),(int,float)) else '未提供（须人工核对）'
        status.set(f'候选 {i+1} / 分数 {score}；已确认 {len(review.accepted)} 字。请检查框内是否包含完整笔画。')
    def load():
        state['page']=pages.current();listing.delete(0,'end');canvas.delete('all');state['box']=None
        for i,r in enumerate(review.data['images'][state['page']]['characters']):listing.insert('end',f'{i+1}: {r["text"]}')
        if listing.size():listing.selection_set(0);show()
    def accept():
        if state['box'] is None:return
        review.vision_mode=mode.get()
        review.accept(state['page'],state['index'],char.get(),state['box']);status.set(f'已确认 {len(review.accepted)} 字；请导出保存工程。')
    def remove():
        review.accepted.pop(f'{state["page"]}:{state["index"]}',None);status.set(f'已确认 {len(review.accepted)} 字')
    def recognize_current():
        if state['box'] is None:return
        import subprocess,threading,queue,sys
        base=Path(__file__).resolve().parent
        python=base/'.venv-vision'/'Scripts'/'python.exe'
        model=base/'vision_models'/'Qwen3-VL-4B-Instruct-NF4'
        if not python.exists() or not (model/'model.safetensors').exists():
            raise ValueError('Local Qwen runtime/model is not installed')
        im=review.image(state['page']);box=list(state['box'])
        if not 0<=box[0]<box[2]<=im.width or not 0<=box[1]<box[3]<=im.height:raise ValueError('Rectangle outside image')
        key=(state['page'],state['index'],box)
        initial_text=review.data['images'][state['page']]['characters'][state['index']]['text']
        work=base/'artifacts'/('recognition_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));work.mkdir()
        source=work/'crop.png';im.crop(box).save(source)
        events=queue.Queue();recognize_button.configure(state='disabled');status.set('正在本地识字，首次加载模型需要一些时间…')
        def worker():
            try:
                with (work/'runtime.log').open('w',encoding='utf-8') as log:
                    done=subprocess.run([str(python),'-m','vision_core.recognition',str(source),'--backend','qwen-crop','--output',str(work/'output'),'--model',str(model)],cwd=base,stdout=log,stderr=subprocess.STDOUT,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if done.returncode:raise RuntimeError('Recognition failed; see '+str(work/'runtime.log'))
                rows=json.loads((work/'output/recognition.json').read_text(encoding='utf-8'));events.put((True,rows[0]['text']))
            except Exception as exc:events.put((False,str(exc)))
        def poll():
            try:
                ok,text=events.get_nowait();recognize_button.configure(state='normal')
                if ok:
                    suffix='（已切换候选，此建议属于之前的裁切）' if key!=(state['page'],state['index'],state['box']) else ''
                    agreement='与初步结果一致（仍需核对）' if text==initial_text else '与初步结果不一致，请重点核对'
                    status.set('初步结果：'+initial_text+'；千问建议：'+(text or '无法确定')+suffix+'；'+agreement+'；不会自动确认。')
                else:status.set(text)
            except queue.Empty:root.after(150,poll)
        threading.Thread(target=worker,daemon=True).start();root.after(150,poll)
    def preview():
        if state['box'] is None:return
        from vision_core.segmentation import segment,SegmentationConfig
        from PIL import ImageDraw
        im=review.image(state['page']);box=state['box']
        if not 0<=box[0]<box[2]<=im.width or not 0<=box[1]<box[3]<=im.height:raise ValueError('Rectangle outside image')
        working,mask,report=segment(im.crop(box),SegmentationConfig(mode=mode.get()))
        panel=Image.new('RGB',(working.width*2,working.height),'white');panel.paste(working,(0,0));panel.paste(Image.fromarray((mask*255).astype('uint8')).convert('RGB'),(working.width,0))
        win=tk.Toplevel(root);win.title('原图 / 笔迹掩膜（白色为保留区域）')
        photo=ImageTk.PhotoImage(panel);label=ttk.Label(win,image=photo);label.image=photo;label.pack()
        ttk.Label(win,text=report['resolved_mode']+' | '+', '.join(report['warnings']),wraplength=760).pack()
    def export(generate=False):
        review.vision_mode=mode.get()
        folder=filedialog.askdirectory(parent=root)
        if not folder:return
        name=simpledialog.askstring('字体名称','这一组字体的名称：',parent=root)
        if not name:return
        result=review.export(Path(folder)/('review_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')),name)
        if generate:
            font=FontProject.load(result).generate(result.parent/'generated')
            from stroke_editor.app import StrokeEditor
            win=tk.Toplevel(root);StrokeEditor(win,font)
            status.set('候选字体已生成：'+str(font))
        else:
            messagebox.showinfo('已保存','字体工程已保存：\n'+str(result),parent=root)
    def save_session():
        review.vision_mode=mode.get()
        path=filedialog.asksaveasfilename(title='保存审核进度',defaultextension='.json',initialfile='review_session.json',filetypes=[('Review session','*.json')],parent=root)
        if path:
            review.save_session(path);status.set('审核进度已保存：'+path)
    def restore_session():
        path=filedialog.askopenfilename(title='恢复审核进度',filetypes=[('Review session','*.json')],parent=root)
        if not path:return
        if review.accepted and not messagebox.askyesno('恢复审核进度','载入将替换当前确认列表，请先保存当前进度。继续载入？',parent=root):return
        review.restore_session(path);mode.set(review.vision_mode or 'auto');load();status.set(f'已恢复 {len(review.accepted)} 个确认字')

    for title,fn in [('确认当前字和框',accept),('撤销当前确认',remove),('保存字体工程',export),('生成并纠正字体',lambda:export(True))]:ttk.Button(bar,text=title,command=lambda f=fn:safe(f)).pack(side='left')
    progressbar=ttk.Frame(root);progressbar.pack(fill='x',before=body)
    mode=tk.StringVar(value='auto')
    ttk.Label(progressbar,text='提取模式（auto自动 / dark深字 / light亮字 / cyan青色 / dark_red_grid红格线）：').pack(side='left')
    ttk.Combobox(progressbar,textvariable=mode,state='readonly',values=['auto','dark','light','cyan','dark_red_grid'],width=14).pack(side='left')
    ttk.Button(progressbar,text='预览笔迹掩膜',command=lambda:safe(preview)).pack(side='left')
    for title,fn in [('保存审核进度',save_session),('恢复审核进度',restore_session)]:ttk.Button(progressbar,text=title,command=lambda f=fn:safe(f)).pack(side='left')
    recognize_button=ttk.Button(progressbar,text='千问识字纠错建议',command=lambda:safe(recognize_current));recognize_button.pack(side='left')
    def annotate():
        if state['box'] is None:return
        p,i=state['page'],state['index']
        note=simpledialog.askstring('歧义标注','记录候选字或疑问（不会确认该字）：',initialvalue=review.annotations.get(f'{p}:{i}',''),parent=root)
        if note is not None:
            review.annotate(p,i,note);status.set('标注已记录；请保存审核进度。')
    ttk.Button(progressbar,text='歧义标注',command=lambda:safe(annotate)).pack(side='left')
    pages.bind('<<ComboboxSelected>>',lambda e:safe(load));listing.bind('<<ListboxSelect>>',lambda e:safe(show))
    def select_image(e):
        x,y=e.x/state['scale'],e.y/state['scale'];p=state['page'];hits=[]
        for i,r in enumerate(review.data['images'][p]['characters']):
            pts=r['box'];b=review.accepted.get(f'{p}:{i}',{}).get('box',review.crop_edits.get(f'{p}:{i}',[min(v[0] for v in pts),min(v[1] for v in pts),max(v[0] for v in pts),max(v[1] for v in pts)]))
            if b[0]<=x<=b[2] and b[1]<=y<=b[3]:hits.append(((b[2]-b[0])*(b[3]-b[1]),i))
        if hits:
            i=min(hits)[1];listing.selection_clear(0,'end');listing.selection_set(i);listing.see(i);show()
    def edit_crop():
        if state['box'] is None:return
        from crop_editor import open_crop_editor
        p,i=state['page'],state['index'];draft_character=char.get()
        def saved(box):
            review.edit_crop(p,i,box);show();char.set(draft_character)
            status.set('裁切已修改，须重新确认该字；请保存审核进度。')
        open_crop_editor(root,review.image(p),state['box'],saved)
    ttk.Button(bar,text='修改裁切',width=8,command=lambda:safe(edit_crop)).pack(side='left')
    canvas.bind('<ButtonPress-1>',lambda e:safe(lambda:select_image(e)))
    canvas.bind('<Configure>',lambda e:safe(show))
    root.protocol('WM_DELETE_WINDOW',lambda:root.destroy() if not (review.accepted or review.annotations or review.crop_edits) or messagebox.askyesno('关闭审核','请确认已保存审核进度；关闭会丢失未保存的确认、裁切和歧义标注。',parent=root) else None)
    root.after(100,lambda:safe(load));root.mainloop()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--results');args=parser.parse_args();main(args.results)
