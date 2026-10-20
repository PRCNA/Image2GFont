import json
import math
from dataclasses import replace, asdict
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from gfont_core import Glyph, Point
from .model import EditorSession, Transform, bounds

ROOT=Path(__file__).resolve().parents[1]


class CoordinateEditor:
    def __init__(self,root,initial=None):
        self.root=root;self.session=None;self.cp=None;self.zoom=.5;self.center=(0,-300)
        self.drag=None;self.photo=None;self.reference=None;self.ref_cache={}
        root.title('Image2GFont · 坐标纠正器');root.geometry('1200x840');root.minsize(950,650)
        self.status=tk.StringVar(value='打开字体开始。坐标修正不改变断笔和笔顺。')
        bar=ttk.Frame(root,padding=8);bar.pack(fill='x')
        for title,fn in [('打开字体',self.open_dialog),('加载坐标配置',self.load_profile),('保存坐标配置',self.save_profile),('导出新字体',self.export)]:
            ttk.Button(bar,text=title,command=lambda f=fn:self.safe(f)).pack(side='left',padx=4)
        ttk.Label(bar,text='预览字形').pack(side='left',padx=(18,4))
        self.selector=ttk.Combobox(bar,state='readonly',width=24);self.selector.pack(side='left')
        self.selector.bind('<<ComboboxSelected>>',lambda e:self.select())
        body=ttk.Frame(root);body.pack(fill='both',expand=True)
        side=ttk.Frame(body,padding=12,width=245);side.pack(side='left',fill='y');side.pack_propagate(False)
        ttk.Label(side,text='整字变换 · 应用于整份字体',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=(0,10))
        self.fields={}
        for key,label,value in [('dx','横向平移 X',0),('dy','纵向平移 Y',0),('scale','等比缩放',1),('angle','旋转角度（°）',0),('pivot_x','变换中心 X',0),('pivot_y','变换中心 Y',0)]:
            row=ttk.Frame(side);row.pack(fill='x',pady=3)
            ttk.Label(row,text=label,width=17).pack(side='left')
            var=tk.StringVar(value=str(value));self.fields[key]=var
            entry=ttk.Entry(row,textvariable=var,width=10);entry.pack(side='right');entry.bind('<Return>',lambda e:self.safe(self.apply))
        self.flipx=tk.BooleanVar();self.flipy=tk.BooleanVar()
        ttk.Checkbutton(side,text='左右翻转',variable=self.flipx).pack(anchor='w')
        ttk.Checkbutton(side,text='上下翻转',variable=self.flipy).pack(anchor='w')
        ttk.Button(side,text='应用数值',command=lambda:self.safe(self.apply)).pack(fill='x',pady=6)
        ttk.Button(side,text='使用当前字形中心',command=lambda:self.safe(self.use_center)).pack(fill='x')
        row=ttk.Frame(side);row.pack(fill='x',pady=6)
        for title,fn in [('撤销',self.undo),('重做',self.redo),('重置',self.reset)]:
            ttk.Button(row,text=title,width=7,command=lambda f=fn:self.safe(f)).pack(side='left',padx=1)
        ttk.Separator(side).pack(fill='x',pady=12)
        self.show_original=tk.BooleanVar(value=True);self.show_ref=tk.BooleanVar(value=True)
        ttk.Checkbutton(side,text='原始路径（灰色）',variable=self.show_original,command=self.draw).pack(anchor='w')
        ttk.Checkbutton(side,text='原图参考（固定位置）',variable=self.show_ref,command=self.draw).pack(anchor='w')
        ttk.Label(side,text='蓝色：调整后路径\n绿色：边界框\n红色：原点坐标轴',justify='left').pack(anchor='w',pady=8)
        ttk.Button(side,text='适应视图',command=self.fit).pack(fill='x')
        ttk.Label(side,text='滚轮：缩放视图\n左键拖动：移动整份字体\nY 轴向下；正角度顺时针\n虚线框：1000 单位参考区域\n基线仅为参考，尚待驱动校准',wraplength=220,justify='left').pack(anchor='w',pady=10)
        ttk.Label(side,text='导出字体名称').pack(anchor='w')
        self.export_name=tk.StringVar();ttk.Entry(side,textvariable=self.export_name).pack(fill='x')
        self.canvas=tk.Canvas(body,bg='#fafbfe',highlightthickness=0);self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<ButtonPress-1>',self.start_drag)
        self.canvas.bind('<B1-Motion>',self.move_drag)
        self.canvas.bind('<ButtonRelease-1>',self.end_drag)
        self.canvas.bind('<Motion>',self.motion)
        root.bind('<Control-z>',lambda e:self.undo());root.bind('<Control-y>',lambda e:self.redo())
        ttk.Label(root,textvariable=self.status,padding=8,anchor='w').pack(fill='x')
        if initial:self.safe(lambda:self.open(initial))

    def safe(self,fn):
        try:fn()
        except Exception as e:messagebox.showerror('操作未完成',str(e),parent=self.root)

    def require(self):
        if not self.session:raise ValueError('请先打开字体')

    def open_dialog(self):
        p=filedialog.askopenfilename(filetypes=[('GFont 字体','*.gfont')])
        if p:self.open(p)

    def open(self,path):
        session=EditorSession(path)
        self.session=session;self.cps=sorted(session.font.glyphs);self.ref_cache={};self.drag=None
        self.selector['values']=[f'U+{cp:04X}  {chr(cp) if cp>=32 and not 0xD800<=cp<=0xDFFF else ""}' for cp in self.cps]
        self.export_name.set(session.font.metadata.name+'_Adjusted')
        self.sync()
        if self.cps:self.selector.current(self.cps.index(65) if 65 in self.cps else 0);self.select()
        else:self.cp=None;self.draw()
        self.status.set(f'已打开：{session.font.metadata.name} · {len(self.cps)} 字形。所有调整作用于整份字体。')

    def select(self):
        self.cp=self.cps[self.selector.current()];self.reference=self.get_reference();self.fit()

    def get_reference(self):
        if self.cp in self.ref_cache:return self.ref_cache[self.cp]
        result=None;folder=self.session.source.parent
        try:
            from .reference import load_report_reference
            result=load_report_reference(folder,self.cp)
            project=folder/'project.json'
            if result is None and project.exists():
                data=json.loads(project.read_text(encoding='utf-8'))
                if data.get('binding',{}).get('codepoint')==self.cp:
                    image=Image.open(folder/data['source']['preserved']).convert('RGB').resize(tuple(data['recipe']['working_size']))
                    s=data['export']['coordinate_scale'];ox,oy=data['export']['coordinate_offset'];pad=data['recipe']['padding']
                    result=(image,s,s,ox+pad*s,oy+pad*s)
        except (OSError,KeyError,ValueError):result=None
        self.ref_cache[self.cp]=result
        return result

    def current_transform(self):return self.drag['preview'] if self.drag else self.session.transform
    def current_glyph(self):
        if self.cp is None:return None
        t=self.current_transform();g=self.session.font.glyphs[self.cp]
        return Glyph(g.codepoint,[[t.apply(p) for p in s] for s in g.strokes])

    def sync(self):
        if not self.session:return
        t=self.session.transform
        for k,v in self.fields.items():v.set(f'{getattr(t,k):.6g}')
        self.flipx.set(t.flip_x);self.flipy.set(t.flip_y)

    def apply(self):
        self.require();t=Transform(**{k:float(v.get()) for k,v in self.fields.items()},flip_x=self.flipx.get(),flip_y=self.flipy.get())
        self.session.commit(t);self.sync();self.draw()

    def use_center(self):
        self.require();b=bounds(self.session.font.glyphs[self.cp]) if self.cp is not None else None
        if b:self.fields['pivot_x'].set(str((b[0]+b[2])/2));self.fields['pivot_y'].set(str((b[1]+b[3])/2));self.apply()

    def undo(self):
        if self.session:self.drag=None;self.session.undo();self.sync();self.draw()
    def redo(self):
        if self.session:self.drag=None;self.session.redo();self.sync();self.draw()
    def reset(self):
        self.require();self.session.commit(Transform());self.sync();self.fit()

    def save_profile(self):
        self.apply()
        p=filedialog.asksaveasfilename(defaultextension='.json',initialfile='coordinate_profile.json',filetypes=[('坐标配置','*.json')])
        if p:self.session.save_profile(p);self.status.set('坐标配置已保存；原始字体未修改。')

    def load_profile(self):
        self.require();p=filedialog.askopenfilename(filetypes=[('坐标配置','*.json')])
        if p:self.session.load_profile(p);self.sync();self.fit()

    def export(self):
        self.apply()
        p=filedialog.asksaveasfilename(defaultextension='.gfont',initialfile='adjusted.gfont',filetypes=[('GFont 字体','*.gfont')])
        if p:
            count=self.session.export(p,self.export_name.get())
            self.status.set(f'已导出并读回验证 {count} 个字形：{p}。仍需在驱动中预览。')
            messagebox.showinfo('导出完成',f'已验证 {count} 个字形的坐标和结构。\n原始字体未修改。\n请在驱动中选择新字体名称测试。')

    def screen(self,x,y):
        return ((x-self.center[0])*self.zoom+self.canvas.winfo_width()/2,(y-self.center[1])*self.zoom+self.canvas.winfo_height()/2)
    def world(self,x,y):
        return ((x-self.canvas.winfo_width()/2)/self.zoom+self.center[0],(y-self.canvas.winfo_height()/2)/self.zoom+self.center[1])

    def fit(self):
        if not self.session or self.cp is None:return
        b=bounds(self.current_glyph());a=bounds(self.session.font.glyphs[self.cp])
        if not b:return
        x0=min(a[0],b[0],0);y0=min(a[1],b[1],0);x1=max(a[2],b[2],0);y1=max(a[3],b[3],0)
        self.center=((x0+x1)/2,(y0+y1)/2)
        w=max(self.canvas.winfo_width(),650);h=max(self.canvas.winfo_height(),550)
        self.zoom=min((w-120)/max(x1-x0,300),(h-120)/max(y1-y0,300));self.draw()

    def draw(self):
        c=self.canvas;c.delete('all');self.photo=None
        if not self.session or self.cp is None:
            c.create_text(250,160,text='请打开一个 .gfont 字体',fill='#556677',font=('Microsoft YaHei UI',15));return
        w=c.winfo_width();h=c.winfo_height()
        if w<2 or h<2:return
        if self.reference and self.show_ref.get():
            im,sx,sy,ox,oy=self.reference
            left,top=self.world(0,0)
            coefficients=(1/(self.zoom*sx),0,(left-ox)/sx,0,1/(self.zoom*sy),(top-oy)/sy)
            ref=im.transform((w,h),Image.Transform.AFFINE,coefficients,Image.Resampling.BILINEAR,fillcolor='white')
            ref=Image.blend(Image.new('RGB',(w,h),'white'),ref,.32)
            self.photo=ImageTk.PhotoImage(ref);c.create_image(0,0,image=self.photo,anchor='nw',tags='reference')
        left,top=self.world(0,0);right,bottom=self.world(w,h)
        step=10**math.floor(math.log10(90/self.zoom))
        if step*self.zoom<45:step*=5
        for axis,lo,hi in [('x',left,right),('y',top,bottom)]:
            for i in range(math.floor(lo/step),math.ceil(hi/step)+1):
                v=i*step
                if axis=='x':
                    x,_=self.screen(v,0);c.create_line(x,0,x,h,fill='#dfe5ec');c.create_text(x+3,12,text=f'{v:g}',anchor='nw',fill='#667788')
                else:
                    _,y=self.screen(0,v);c.create_line(0,y,w,y,fill='#dfe5ec');c.create_text(5,y+2,text=f'{v:g}',anchor='nw',fill='#667788')
        x,y=self.screen(0,0);c.create_line(0,y,w,y,fill='#ba4a47',width=2,arrow='last');c.create_line(x,0,x,h,fill='#ba4a47',width=2,arrow='last')
        c.create_text(x+8,y+12,text='O (0,0)',anchor='nw',fill='#9e3430')
        c.create_rectangle(*self.screen(-500,-1000),*self.screen(500,0),outline='#8092a5',dash=(6,4),tags='frame')
        c.create_text(12,h-16,text='X →  Y ↓   灰色原路径 / 蓝色调整后 / 红色Y=0参考基线',anchor='w',fill='#516477')
        def path(g,color,width,tag):
            for stroke in g.strokes:
                coords=[n for p in stroke for n in self.screen(p.x,p.y)]
                if len(coords)>=4:c.create_line(*coords,fill=color,width=width,tags=tag)
                elif coords:c.create_oval(coords[0]-2,coords[1]-2,coords[0]+2,coords[1]+2,fill=color,outline='',tags=tag)
        if self.show_original.get():path(self.session.font.glyphs[self.cp],'#aab2bd',3,'original')
        g=self.current_glyph();path(g,'#136dc2',2,'transformed')
        b=bounds(g)
        if b:
            c.create_rectangle(*self.screen(b[0],b[1]),*self.screen(b[2],b[3]),outline='#25866d',dash=(4,3),tags='bounds')
            c.create_text(w-15,18,text=f'边界 X [{b[0]:.1f}, {b[2]:.1f}]\nY [{b[1]:.1f}, {b[3]:.1f}]\n{len(g.strokes)} 条路径 · 原图{"已配准" if self.reference else "不可用"}',anchor='ne',fill='#174b43')

    def wheel(self,event):
        before=self.world(event.x,event.y);self.zoom=max(.03,min(8,self.zoom*(1.15 if event.delta>0 else 1/1.15)))
        after=self.world(event.x,event.y);self.center=(self.center[0]+before[0]-after[0],self.center[1]+before[1]-after[1]);self.draw()
    def start_drag(self,event):
        if self.session and self.cp is not None:self.drag=dict(start=self.world(event.x,event.y),original=self.session.transform,preview=self.session.transform)
    def move_drag(self,event):
        if self.drag:
            x,y=self.world(event.x,event.y);a,b=self.drag['start'];t=self.drag['original']
            self.drag['preview']=replace(t,dx=t.dx+x-a,dy=t.dy+y-b);self.draw()
    def end_drag(self,event):
        if self.drag:
            self.session.commit(self.drag['preview']);self.drag=None;self.sync();self.draw()
    def motion(self,event):
        x,y=self.world(event.x,event.y);self.status.set(f'鼠标坐标 X={x:.2f}, Y={y:.2f}  ·  全字体变换；原始路径不会覆盖')


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('font',nargs='?',type=Path);args=parser.parse_args()
    default=ROOT/'artifacts/photo_0923_final/coordinate_test.gfont'
    root=tk.Tk();CoordinateEditor(root,args.font or (default if default.exists() else None));root.mainloop()


if __name__=='__main__':main()
