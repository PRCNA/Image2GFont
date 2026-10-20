"""Manual multi-character crop/binding project, with immutable source copy."""
import hashlib
import json
import math
import stat
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
from gfont_core import GFont,GFontMetadata,Glyph,Point,GFontV5Writer,GFontV5Reader
from image_pipeline.core import preprocess,skeletonize,prune_spurs,graph_from_skeleton,candidate_strokes,simplify

RECIPE=dict(blur=.8,threshold=7,closing=2,min_area=12,background_sigma=18,silhouette_sigma=.4,max_hole_area=3)


class PageProject:
    @classmethod
    def create(cls,source,destination):
        data=Path(source).read_bytes()
        with Image.open(source) as im:ImageOps.exif_transpose(im).load()
        root=Path(destination);root.mkdir(parents=True,exist_ok=False)
        name='source_original'+Path(source).suffix.lower();(root/name).write_bytes(data);(root/name).chmod(stat.S_IREAD)
        obj=cls.__new__(cls);obj.root=root;obj.data=dict(format='Image2GFontPage',schema_version=1,source=name,source_sha256=hashlib.sha256(data).hexdigest(),regions=[])
        obj.save();return obj

    @classmethod
    def load(cls,path):
        obj=cls.__new__(cls);obj.root=Path(path).parent;obj.data=json.loads(Path(path).read_text(encoding='utf-8'))
        if obj.data.get('format')!='Image2GFontPage' or obj.data.get('schema_version')!=1:raise ValueError('Unsupported page project')
        obj.image();obj.validate(False);return obj

    def image(self):
        path=(self.root/self.data['source']).resolve()
        if path.parent!=self.root.resolve():raise ValueError('Source must be inside project')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=self.data['source_sha256']:raise ValueError('Source image changed')
        with Image.open(path) as im:return ImageOps.exif_transpose(im).convert('RGB')

    def validate(self,require_bindings=True):
        w,h=self.image().size;seen=set()
        if require_bindings and not self.data['regions']:raise ValueError('Add at least one region')
        for r in self.data['regions']:
            from vision_core.segmentation import MODES
            if r.get('vision_mode') is not None and r['vision_mode'] not in MODES:raise ValueError('Unknown vision mode')
            box=r['box']
            if len(box)!=4 or any(type(v)is not int for v in box):raise ValueError('Invalid crop coordinates')
            x0,y0,x1,y1=box
            if not 0<=x0<x1<=w or not 0<=y0<y1<=h:raise ValueError('Crop outside image')
            c=r['character']
            if not c and not require_bindings:continue
            if len(c)!=1 or c.isspace() or not 0<ord(c)<=65535 or 0xD800<=ord(c)<=0xDFFF:raise ValueError('Bind one BMP character per region')
            if c in seen:raise ValueError('Duplicate character binding')
            seen.add(c)

    def save(self):
        self.validate(False)
        temp=self.root/'page.json.tmp';temp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.root/'page.json')

    def generate(self,destination,vision_mode=None):
        self.validate();image=self.image();prepared=[]
        used_v2=False
        for i,r in enumerate(self.data['regions']):
            region_mode=r.get('vision_mode',vision_mode)
            crop=image.crop(r['box'])
            if region_mode is not None:
                used_v2=True
                from vision_core.segmentation import SegmentationConfig
                from vision_core.trajectory import extract
                glyph,working,mask,detail=extract(crop,ord(r['character']),SegmentationConfig(mode=region_mode))
                prepared.append((working,glyph,dict(slot=str(i+1),crop=r['box'],binding_confirmed=True,status='candidate',vision=detail,transforms=[dict(key=r['character'],scale_x=detail['transform']['scale'],scale_y=detail['transform']['scale'],offset=detail['transform']['offset'])])))
                continue
            crop.thumbnail((200,200),Image.Resampling.LANCZOS)
            gray=np.asarray(crop.convert('L'));pad=16
            mask=preprocess(np.pad(gray,pad,mode='edge'),**RECIPE)
            mask[:pad]=False;mask[-pad:]=False;mask[:,:pad]=False;mask[:,-pad:]=False
            thin,_=prune_spurs(skeletonize(mask),3);graph=graph_from_skeleton(thin)
            paths=[simplify(s['points'],.65) for s in candidate_strokes(graph)]
            if not paths:raise ValueError(f'Region {i+1}: no extracted paths')
            scale=800/max(crop.size);ox=-crop.width*scale/2;oy=-900
            strokes=[[Point((x-pad)*scale+ox,(y-pad)*scale+oy) for x,y in s] for s in paths]
            prepared.append((crop,Glyph(ord(r['character']),strokes),dict(slot=str(i+1),crop=r['box'],binding_confirmed=True,
                transforms=[dict(key=r['character'],scale_x=scale,scale_y=scale,offset=[ox-pad*scale,oy-pad*scale])],status='candidate')))
        font=GFont(GFontMetadata(name='Image2GFont_PageCandidate',glyph_count=len(prepared)),{g.codepoint:g for _,g,_ in prepared},[g.codepoint for _,g,_ in prepared])
        encoded=GFontV5Writer.dumps(font);decoded=GFontV5Reader.loads(encoded)
        assert set(decoded.glyphs)==set(font.glyphs)
        out=Path(destination);out.mkdir(parents=True,exist_ok=False)
        for crop,g,row in prepared:
            crop.save(out/f'crop_{row["slot"]}.png')
            if 'vision' in row:
                from vision_core.segmentation import segment,SegmentationConfig
                _,mask,_=segment(image.crop(row['crop']),SegmentationConfig(**row['vision']['config']))
                Image.fromarray((mask*255).astype('uint8')).save(out/f'mask_{row["slot"]}.png')
        (out/'report.json').write_text(json.dumps(dict(padding=None if used_v2 else pad,recipe={'vision_mode':vision_mode,'version':2,'per_region':True} if used_v2 else RECIPE,source_sha256=self.data['source_sha256'],rows=[r for _,_,r in prepared]),ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'candidate.gfont').write_bytes(encoded)
        return out/'candidate.gfont'


def main():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox,simpledialog
    from PIL import ImageTk
    from datetime import datetime
    root=tk.Tk();root.title('Image2GFont - \u591a\u5b57\u56fe\u7247\u5bfc\u5165');root.geometry('1050x760')
    state=dict(project=None,scale=1,photo=None,start=None)
    bar=ttk.Frame(root);bar.pack(fill='x');status=tk.StringVar(value='\u6253\u5f00\u56fe\u7247\uff0c\u62d6\u51fa\u5355\u5b57\u77e9\u5f62\uff0c\u8f93\u5165\u5bf9\u5e94\u5b57\u7b26\u3002')
    ttk.Label(root,textvariable=status).pack(fill='x');canvas=tk.Canvas(root,bg='#dddddd');canvas.pack(fill='both',expand=True)
    def safe(fn):
        try:fn()
        except Exception as exc:messagebox.showerror('\u64cd\u4f5c\u672a\u5b8c\u6210',str(exc),parent=root)
    def draw():
        project=state['project']
        if not project:return
        im=project.image();scale=min(max(canvas.winfo_width(),100)/im.width,max(canvas.winfo_height(),100)/im.height,1)
        state['scale']=scale;state['photo']=ImageTk.PhotoImage(im.resize((max(1,round(im.width*scale)),max(1,round(im.height*scale)))))
        canvas.delete('all');canvas.create_image(0,0,image=state['photo'],anchor='nw')
        for i,r in enumerate(project.data['regions']):
            box=[v*scale for v in r['box']];canvas.create_rectangle(*box,outline='#d34d00',width=2)
            canvas.create_text(box[0]+3,box[1]+3,text=f'{i+1}: {r["character"]}',anchor='nw',fill='#d34d00')
    def open_image():
        path=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.bmp *.tif')])
        if not path:return
        folder=filedialog.askdirectory(title='\u9009\u62e9\u5de5\u7a0b\u5b58\u653e\u76ee\u5f55')
        if not folder:return
        state['project']=PageProject.create(path,Path(folder)/('page_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')));draw()
    def load():
        path=filedialog.askopenfilename(filetypes=[('Page project','page.json')])
        if path:state['project']=PageProject.load(path);draw()
    def finish(event):
        if not state['project'] or state['start'] is None:return
        start=state['start'];state['start']=None;scale=state['scale'];w,h=state['project'].image().size
        x0,x1=sorted((round(start[0]/scale),round(event.x/scale)));y0,y1=sorted((round(start[1]/scale),round(event.y/scale)))
        box=[max(0,x0),max(0,y0),min(w,x1),min(h,y1)]
        if box[2]-box[0]<3 or box[3]-box[1]<3:return
        char=simpledialog.askstring('\u7ed1\u5b9a\u5b57\u7b26','\u8bf7\u8f93\u5165\u6846\u4e2d\u7684\u4e00\u4e2a\u5b57\uff1a',parent=root)
        if char is None:return
        p=state['project'];p.data['regions'].append(dict(box=box,character=char))
        try:p.validate();p.save()
        except Exception:p.data['regions'].pop();raise
        draw()
    def remove():
        p=state['project']
        if p and p.data['regions']:p.data['regions'].pop();p.save();draw()
    def generate():
        p=state['project']
        if not p:return
        font=p.generate(p.root/('generated_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')))
        from stroke_editor.app import StrokeEditor
        win=tk.Toplevel(root);StrokeEditor(win,font)
        status.set('\u5019\u9009\u5b57\u4f53\u5df2\u751f\u6210\uff0c\u8bf7\u5728\u7ea0\u6b63\u5668\u4e2d\u68c0\u67e5\uff1a'+str(font))
    for title,fn in [('\u6253\u5f00\u56fe\u7247',open_image),('\u6253\u5f00\u88c1\u5207\u5de5\u7a0b',load),('\u5220\u9664\u6700\u540e\u4e00\u4e2a\u6846',remove),('\u751f\u6210\u5e76\u8fdb\u5165\u7ea0\u6b63\u5668',generate)]:
        ttk.Button(bar,text=title,command=lambda f=fn:safe(f)).pack(side='left')
    canvas.bind('<ButtonPress-1>',lambda e:state.update(start=(e.x,e.y)))
    canvas.bind('<B1-Motion>',lambda e:(canvas.delete('draft'),canvas.create_rectangle(*state['start'],e.x,e.y,outline='blue',tags='draft')) if state['start'] else None)
    canvas.bind('<ButtonRelease-1>',lambda e:safe(lambda:finish(e)))
    canvas.bind('<Configure>',lambda e:draw());root.mainloop()


if __name__=='__main__':main()
