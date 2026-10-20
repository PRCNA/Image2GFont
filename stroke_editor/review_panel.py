import tkinter as tk
from tkinter import ttk
import numpy as np
from .junction_review import JunctionReview
from image_pipeline.ink_support import local_widths


class ReviewPanel:
    def __init__(self,editor):
        self.editor=editor;self.preview_paths=None;self.active=None;self.width_point=None
        self.window=tk.Toplevel(editor.root);self.window.title('\u4ea4\u53c9\u4e0e\u7b14\u5bbd\u68c0\u67e5');self.window.geometry('560x520')
        self.message=tk.StringVar()
        ttk.Label(self.window,textvariable=self.message,wraplength=530,padding=8).pack(fill='x')
        ttk.Button(self.window,text='\u91cd\u65b0\u5206\u6790\u5f53\u524d\u5b57',command=lambda:editor.safe(self.analyze)).pack()
        self.nodes=tk.Listbox(self.window,exportselection=False,height=8);self.nodes.pack(fill='both',expand=True)
        self.nodes.bind('<<ListboxSelect>>',lambda e:editor.safe(self.choose_node))
        self.options=tk.Listbox(self.window,exportselection=False,height=7);self.options.pack(fill='both',expand=True)
        self.options.bind('<<ListboxSelect>>',lambda e:editor.safe(self.preview))
        row=ttk.Frame(self.window);row.pack()
        for text,fn in [('\u63a5\u53d7\u9884\u89c8',self.accept),('\u53d6\u6d88\u9884\u89c8',self.cancel),('\u64a4\u9500',editor.undo)]:
            ttk.Button(row,text=text,command=lambda f=fn:editor.safe(f)).pack(side='left')
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.analyze()

    def invalidate(self):
        self.preview_paths=None;self.active=None;self.review=None;self.width_point=None
        self.nodes.delete(0,'end');self.options.delete(0,'end')
        self.message.set('\u5b57\u5f62\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u5206\u6790\u3002')

    def analyze(self):
        e=self.editor;e.require();e.no_pending();self.cancel()
        self.review=JunctionReview(e.session,e.cp);self.nodes.delete(0,'end');self.options.delete(0,'end')
        text='\u4ec5\u68c0\u67e5\u5df2\u5171\u4eab\u5750\u6807\u7684\u4ea4\u70b9\uff1b\u9884\u89c8\u4e0d\u4f1a\u81ea\u52a8\u4fdd\u5b58\u3002'
        if e.reference:
            rows=local_widths(np.asarray(e.reference[0].convert('L')),self.review.width_graph(e.reference))
            valid=[r['width'] for r in rows if r['width'] is not None]
            text+=f' \u539f\u56fe\u7b14\u5bbd\uff1a{np.median(valid):.1f}px\uff08\u4e2d\u4f4d\u6570\uff09' if valid else ' \u6682\u65e0\u53ef\u9760\u7b14\u5bbd\u3002'
            text+=f' \u53ef\u6d4b {len(valid)} / {len(rows)}\u3002\u7b14\u5bbd\u4e0d\u5199\u5165\u5b57\u4f53\u3002'
            self.width_rows=rows
        else:text+=' \u539f\u56fe\u672a\u914d\u51c6\uff0c\u4e0d\u4f30\u8ba1\u7b14\u5bbd\u3002';self.width_rows=[]
        self.message.set(text)
        for r in self.review.reports:self.nodes.insert('end',f"\u4ea4\u70b9 {r['node']} | \u5019\u9009 {len(r['candidates'])} | "+('\u5f85\u786e\u8ba4' if r['status']=='review' else '\u51e0\u4f55\u5efa\u8bae'))
        if not self.review.reports:self.message.set(text+' \u672a\u627e\u5230\u5171\u4eab\u4ea4\u70b9\u3002')
        # Bounded evenly spaced display; all measurements remain available in memory.
        self.shown_widths=self.width_rows[::max(1,(len(self.width_rows)+99)//100)]
        for row in self.shown_widths:
            value=f"{row['width']:.1f}px" if row['width'] is not None else '\u4e0d\u53ef\u9760'
            self.nodes.insert('end',f"\u5c40\u90e8\u7b14\u5bbd {value} | {row['point'][0]:.1f}, {row['point'][1]:.1f}")

    def choose_node(self):
        if self.review is None or not self.nodes.curselection():return
        self.width_point=None
        selected=self.nodes.curselection()[0]
        if selected>=len(self.review.reports):
            row=self.shown_widths[selected-len(self.review.reports)]
            _,sx,sy,ox,oy=self.editor.reference
            self.width_point=(row['point'][0]*sx+ox,row['point'][1]*sy+oy)
            self.active=None;self.preview_paths=None;self.options.delete(0,'end')
            self.editor.center=self.width_point;self.editor.draw();return
        self.preview_paths=None;self.active=self.nodes.curselection()[0];self.options.delete(0,'end')
        r=self.review.reports[self.active]
        for c in r['candidates']:self.options.insert('end',f"\u8f6c\u5411\u4ee3\u4ef7 {c['score']:.1f} | \u8fde\u63a5 {len(c['pairs'])} | \u65ad\u5f00 {len(c['unpaired'])}")
        self.editor.center=tuple(self.review.graph['nodes'][r['node']]['point']);self.editor.draw()

    def preview(self):
        if self.review is None or self.active is None or not self.options.curselection():return
        self.editor.no_pending();self.preview_paths=self.review.preview(self.active,self.options.curselection()[0]);self.editor.draw()

    def accept(self):
        if self.preview_paths is None:return
        self.editor.no_pending();self.review.accept(self.active,self.options.curselection()[0]);self.editor.selected=[];self.editor.node=None;self.editor.refresh()

    def cancel(self):
        self.preview_paths=None;self.active=None;self.width_point=None;self.editor.draw()

    def draw(self):
        e=self.editor
        if self.width_point:
            x,y=e.screen(*self.width_point)
            e.canvas.create_oval(x-7,y-7,x+7,y+7,outline='#007caa',width=3,tags='junction_preview')
        if self.preview_paths:
            for i,s in enumerate(self.preview_paths):
                xy=[v for p in s for v in e.screen(p.x,p.y)]
                if len(s)>1:e.canvas.create_line(*xy,fill=('#e47700','#007caa','#903db0')[i%3],width=3,dash=(5,2),tags='junction_preview')
        if self.active is not None and self.review:
            r=self.review.reports[self.active];p=self.review.graph['nodes'][r['node']]['point'];x,y=e.screen(*p)
            e.canvas.create_oval(x-9,y-9,x+9,y+9,outline='#d33',width=3,tags='junction_preview')

    def close(self):
        self.window.destroy();self.editor.review_panel=None;self.editor.draw()
