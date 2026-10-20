import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from coordinate_editor.app import CoordinateEditor,ROOT
from .model import StrokeSession
from gfont_core import Glyph, Point
from image_pipeline.quality import inspect_glyph


class StrokeEditor(CoordinateEditor):
    def __init__(self,root,initial=None):
        self.review_panel=None
        self.selected=[];self.node=None;self.listbox=None
        self.node_drag=None;self.draft=None;self.insert_mode=False
        self.quality_window=None;self.quality_items=[];self.quality_active=None
        super().__init__(root,None)
        root.title('Image2GFont · 笔画修正器')
        body=self.canvas.master
        sidebar=[w for w in body.winfo_children() if w!=self.canvas][0];sidebar.destroy()
        side=ttk.Frame(body,padding=10,width=275);side.pack(side='left',fill='y',before=self.canvas);side.pack_propagate(False)
        ttk.Label(side,text='只修改当前字形',font=('Microsoft YaHei UI',12,'bold')).pack(anchor='w')
        self.state_text=tk.StringVar();ttk.Label(side,textvariable=self.state_text).pack(anchor='w',pady=4)
        self.listbox=tk.Listbox(side,selectmode='extended',exportselection=False,height=13)
        self.listbox.pack(fill='both',expand=True);self.listbox.bind('<<ListboxSelect>>',self.list_select)
        for title,fn in [('连接所选两条…',self.join_dialog),('在选中节点断开',self.split_selected),('反转所选路径',self.reverse_selected),('删除所选路径',self.delete_selected)]:
            ttk.Button(side,text=title,command=lambda f=fn:self.safe(f)).pack(fill='x',pady=2)
        row=ttk.Frame(side);row.pack(fill='x',pady=3)
        for title,fn in [('上移',lambda:self.reorder(-1)),('下移',lambda:self.reorder(1)),('撤销',self.undo),('重做',self.redo)]:
            ttk.Button(row,text=title,width=6,command=lambda f=fn:self.safe(f)).pack(side='left')
        ttk.Button(side,text='恢复此字的原始候选',command=lambda:self.safe(self.reset)).pack(fill='x',pady=2)
        ttk.Button(side,text='将此字标为已人工确认',command=lambda:self.safe(self.confirm)).pack(fill='x',pady=3)
        ttk.Checkbutton(side,text='原图参考',variable=self.show_ref,command=self.draw).pack(anchor='w')
        ttk.Checkbutton(side,text='原始路径（灰色）',variable=self.show_original,command=self.draw).pack(anchor='w')
        ttk.Button(side,text='适应视图',command=self.fit).pack(fill='x')
        ttk.Label(side,text='点击路径选择；Ctrl可多选\n选中后点击蓝色节点，再断开\n橙色圆点=起点，箭头=方向\n滚轮缩放；笔画数不等于路径数',justify='left').pack(anchor='w',pady=6)
        ttk.Label(side,text='导出字体名称').pack(anchor='w');ttk.Entry(side,textvariable=self.export_name).pack(fill='x')
        bar=root.winfo_children()[0]
        ttk.Button(bar,text='\u4ea4\u53c9/\u7b14\u5bbd',command=lambda:self.safe(self.open_review)).pack(side='right',padx=4)
        ttk.Button(bar,text='检查疑点',command=lambda:self.safe(self.open_quality)).pack(side='left',padx=4)
        buttons=[w for w in bar.winfo_children() if isinstance(w,ttk.Button)]
        for b,text in zip(buttons,['打开原始字体','加载修正记录','保存修正记录','导出修正字体']):b.configure(text=text)
        nodebar=ttk.Frame(root,padding=(8,3));nodebar.pack(fill='x',before=body)
        for title,fn in [('插入节点',self.begin_insert),('删除节点',self.delete_node),('开始补画',self.begin_draft),('完成补画',self.finish_draft),('取消 / Esc',self.cancel_pending)]:
            ttk.Button(nodebar,text=title,command=lambda f=fn:self.safe(f)).pack(side='left',padx=2)
        self.node_x=tk.StringVar();self.node_y=tk.StringVar()
        for label,var in [('节点 X',self.node_x),('Y',self.node_y)]:
            ttk.Label(nodebar,text=label).pack(side='left',padx=3);ttk.Entry(nodebar,textvariable=var,width=9).pack(side='left')
        ttk.Button(nodebar,text='应用节点坐标',command=lambda:self.safe(self.apply_node)).pack(side='left',padx=4)
        self.canvas.bind('<ButtonPress-1>',lambda e:self.safe(lambda:self.start_drag(e)))
        self.canvas.bind('<ButtonRelease-1>',lambda e:self.safe(lambda:self.end_drag(e)))
        root.bind('<Escape>',lambda e:self.cancel_pending())
        root.protocol('WM_DELETE_WINDOW',self.close)
        if initial:self.safe(lambda:self.open(initial))

    def open_review(self):
        self.require();self.no_pending()
        if self.review_panel:self.review_panel.window.lift();return
        from .review_panel import ReviewPanel
        self.review_panel=ReviewPanel(self)

    def may_discard(self):
        return (not self.draft and (not self.session or not self.session.dirty)) or messagebox.askyesno('尚未保存修正记录','当前修改或补画尚未保存。继续会放弃这些修改，是否继续？',parent=self.root)

    def close(self):
        if self.may_discard():self.root.destroy()

    def open(self,path):
        if not self.may_discard():return
        session=StrokeSession(path);self.session=session;self.cps=sorted(session.font.glyphs);self.ref_cache={}
        self.draft=None;self.node_drag=None;self.insert_mode=False
        self.selector['values']=[f'U+{cp:04X}  {chr(cp) if cp>=32 and not 0xD800<=cp<=0xDFFF else ""}' for cp in self.cps]
        self.export_name.set(session.font.metadata.name+'_StrokeEdit');self.selected=[];self.node=None
        if self.cps:self.selector.current(self.cps.index(0x85cf) if 0x85cf in self.cps else 0);self.select()
        else:self.cp=None;self.refresh_quality();self.draw()

    def select(self):
        if self.draft is not None:
            if self.cp in self.cps:self.selector.current(self.cps.index(self.cp))
            self.status.set('请先完成或取消补画，再切换字形。');return
        self.node_drag=None;self.insert_mode=False
        self.selected=[];self.node=None;super().select();self.refresh()

    def current_glyph(self):
        if not self.session or self.cp is None:return None
        glyph=self.session.glyph(self.cp)
        if self.node_drag:
            i,j=self.node_drag['node'];s=glyph.strokes[i];closed=len(s)>2 and s[0]==s[-1]
            s[j]=self.node_drag['preview']
            if closed and j in (0,len(s)-1):s[0]=s[-1]=s[j]
        return glyph

    def refresh(self):
        if self.review_panel:self.review_panel.invalidate()
        if self.listbox is None or self.cp is None:return
        self.listbox.delete(0,'end')
        for i,s in enumerate(self.session.paths[self.cp]):
            length=sum(math.hypot(a.x-b.x,a.y-b.y) for a,b in zip(s,s[1:]))
            self.listbox.insert('end',f'{i+1:02d}  {len(s)} 点  长度 {length:.1f}')
        self.selected=[i for i in self.selected if i<len(self.session.paths[self.cp])]
        for i in self.selected:self.listbox.selection_set(i)
        self.state_text.set('已人工确认' if self.session.confirmed[self.cp] else '候选 / 尚未人工确认')
        self.refresh_quality()
        self.draw()

    def open_quality(self):
        self.require();self.no_pending()
        if self.quality_window is not None:
            self.quality_window.lift();return
        win=tk.Toplevel(self.root);self.quality_window=win
        win.title('字形疑点 · 仅供人工复核');win.geometry('540x440')
        self.quality_summary=tk.StringVar()
        ttk.Label(win,textvariable=self.quality_summary,padding=10,wraplength=510).pack(fill='x')
        frame=ttk.Frame(win);frame.pack(fill='both',expand=True,padx=10)
        self.quality_list=tk.Listbox(frame,exportselection=False)
        scroll=ttk.Scrollbar(frame,command=self.quality_list.yview)
        self.quality_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.quality_list.pack(side='left',fill='both',expand=True)
        self.quality_list.bind('<<ListboxSelect>>',lambda e:self.safe(self.select_quality))
        self.quality_reason=tk.StringVar(value='点击一条疑点，定位相关路径。')
        ttk.Label(win,textvariable=self.quality_reason,wraplength=510,padding=10).pack(fill='x')
        ttk.Label(win,text='提示不等于错误；不会自动连接、删除或确认笔画。',padding=10).pack(fill='x')
        win.protocol('WM_DELETE_WINDOW',self.close_quality)
        self.refresh_quality()

    def close_quality(self):
        if self.quality_window is not None:self.quality_window.destroy()
        self.quality_window=None;self.quality_items=[];self.quality_active=None;self.draw()

    def refresh_quality(self):
        self.quality_active=None
        if self.quality_window is None:return
        self.quality_items=[];self.quality_list.delete(0,'end')
        if self.cp is None:return
        result=inspect_glyph(self.session.glyph(self.cp),self.session.font.metadata.font_size)
        for p in result['paths']:
            if p['short']:
                self.quality_items.append(dict(indices=[p['stroke_index']],gap=None,
                    label=f"短路径 · {p['stroke_index']+1} · 长度 {p['length']:.1f}",
                    reason=f"长度不超过 {result['thresholds']['short_length']:.1f} 单位。可能是碎线，也可能是正常点画，请对照原图。"))
            if p['duplicate_segments']:
                self.quality_items.append(dict(indices=[p['stroke_index']],gap=None,
                    label=f"重复坐标 · {p['stroke_index']+1}",reason='存在连续重合节点。请检查后再决定是否删除节点。'))
        for q in result['nearby_endpoints']:
            self.quality_items.append(dict(indices=[q['a_stroke'],q['b_stroke']],gap=q,
                label=f"{'方向相对' if q['aligned'] else '端点邻近'} · {q['a_stroke']+1} / {q['b_stroke']+1} · 间距 {q['distance']:.1f}",
                reason='两条路径端点接近。'+('方向相对，优先检查是否断笔。' if q['aligned'] else '方向不满足断笔优先提示条件。')+'也可能是独立笔画，红虚线仅表示间隙。'))
        for item in self.quality_items:self.quality_list.insert('end',item['label'])
        self.quality_summary.set(f"{chr(self.cp)} · {len(self.quality_items)} 条提示（不是错误数）。修改、撤销和切字后自动重新检查。")
        self.quality_reason.set('点击一条疑点，定位相关路径。' if self.quality_items else '未命中当前规则，不表示字形或笔顺正确。')

    def select_quality(self):
        self.no_pending()
        selection=self.quality_list.curselection()
        if not selection:return
        item=self.quality_items[selection[0]]
        self.quality_active=item;self.selected=item['indices'][:];self.node=None
        self.listbox.selection_clear(0,'end')
        for i in self.selected:self.listbox.selection_set(i)
        self.listbox.see(self.selected[0])
        self.quality_reason.set(item['reason'])
        # Fit the whole glyph so the original image remains useful context.
        self.fit();self.draw()

    def list_select(self,event):
        if self.draft is not None:return
        self.quality_active=None
        self.selected=list(self.listbox.curselection());self.node=None;self.draw()

    def draw(self):
        super().draw()
        if self.review_panel:self.review_panel.draw()
        if not self.session or self.cp is None:return
        if self.quality_active is not None and not self.node_drag and self.draft is None:
            gap=self.quality_active['gap']
            if gap:
                self.canvas.create_line(*self.screen(*gap['a']),*self.screen(*gap['b']),
                    fill='#cc2646',width=3,dash=(4,4),tags='quality_hint')
                for p in (gap['a'],gap['b']):
                    x,y=self.screen(*p)
                    self.canvas.create_oval(x-7,y-7,x+7,y+7,outline='#cc2646',width=2,tags='quality_hint')
        self.canvas.delete('stroke_selection')
        for i in self.selected:
            if i>=len(self.session.paths[self.cp]):continue
            stroke=self.current_glyph().strokes[i];xy=[self.screen(p.x,p.y) for p in stroke]
            if len(xy)>1:self.canvas.create_line(*[v for p in xy for v in p],fill='#ef8a17',width=3,arrow='last',tags='stroke_selection')
            for j,(x,y) in enumerate(xy):
                color='#df3333' if self.node==(i,j) else '#136dc2'
                self.canvas.create_oval(x-3,y-3,x+3,y+3,fill=color,outline='white',tags='stroke_selection')
            x,y=xy[0];self.canvas.create_oval(x-5,y-5,x+5,y+5,outline='#ef8a17',width=2,tags='stroke_selection')
            self.canvas.create_text(x+10,y-10,text=str(i+1),fill='#a44f00',tags='stroke_selection')
        if self.draft is not None:
            xy=[self.screen(p.x,p.y) for p in self.draft]
            if len(xy)>1:self.canvas.create_line(*[v for p in xy for v in p],fill='#c52f82',width=3,dash=(5,3),tags='draft')
            for x,y in xy:self.canvas.create_oval(x-4,y-4,x+4,y+4,fill='#c52f82',outline='',tags='draft')
            self.canvas.create_text(15,40,text='补画中：逐点点击，完成后提交；Esc取消',anchor='nw',fill='#a51e6a',tags='draft')

    def start_drag(self,event):
        if not self.session or self.cp is None:return
        self.quality_active=None
        if self.draft is not None:
            self.draft.append(Point(*self.world(event.x,event.y)));self.draw();return
        if self.insert_mode or event.state&1:
            self.insert_at(event);return
        # Node picking precedes line picking for a single selected stroke.
        if len(self.selected)==1:
            i=self.selected[0]
            nearest=min(((math.hypot(event.x-self.screen(p.x,p.y)[0],event.y-self.screen(p.x,p.y)[1]),j)
                         for j,p in enumerate(self.session.paths[self.cp][i])),default=(999,None))
            if nearest[0]<=9:
                self.node=(i,nearest[1]);p=self.session.paths[self.cp][i][nearest[1]]
                self.node_drag=dict(node=self.node,start=self.world(event.x,event.y),original=p,preview=p)
                self.sync_node(p);self.draw();return
        best=(10,None)
        for i,s in enumerate(self.session.paths[self.cp]):
            xy=[self.screen(p.x,p.y) for p in s]
            segments=list(zip(xy,xy[1:])) or [(xy[0],xy[0])]
            for (ax,ay),(bx,by) in segments:
                dx,dy=bx-ax,by-ay;den=dx*dx+dy*dy
                t=max(0,min(1,((event.x-ax)*dx+(event.y-ay)*dy)/den)) if den else 0
                d=math.hypot(event.x-ax-t*dx,event.y-ay-t*dy)
                if d<best[0]:best=(d,i)
        if best[1] is not None:
            i=best[1]
            if event.state&4:
                self.selected=[x for x in self.selected if x!=i] if i in self.selected else self.selected+[i]
            else:self.selected=[i]
            self.node=None;self.refresh()
    def move_drag(self,event):
        if self.node_drag:
            x,y=self.world(event.x,event.y);a,b=self.node_drag['start'];p=self.node_drag['original']
            q=Point(p.x+x-a,p.y+y-b);self.node_drag['preview']=q;self.sync_node(q);self.draw()
    def end_drag(self,event):
        if self.node_drag:
            d=self.node_drag;self.node_drag=None
            if d['preview']!=d['original']:self.session.move_point(self.cp,*d['node'],d['preview'])
            self.refresh()

    def sync_node(self,p):
        self.node_x.set(f'{p.x:.6g}');self.node_y.set(f'{p.y:.6g}')

    def begin_insert(self):
        self.one();self.insert_mode=True;self.status.set('点击选中路径的一条线段插入节点；也可按住Shift点击。')

    def insert_at(self,event):
        i=self.one();s=self.session.paths[self.cp][i];best=(10,None,None)
        for j,(p,q) in enumerate(zip(s,s[1:])):
            ax,ay=self.screen(p.x,p.y);bx,by=self.screen(q.x,q.y);dx,dy=bx-ax,by-ay;den=dx*dx+dy*dy
            if not den:continue
            t=max(0,min(1,((event.x-ax)*dx+(event.y-ay)*dy)/den));d=math.hypot(event.x-ax-t*dx,event.y-ay-t*dy)
            if 0<t<1 and d<best[0]:best=(d,j,Point(p.x+t*(q.x-p.x),p.y+t*(q.y-p.y)))
        if best[1] is None:raise ValueError('请靠近所选路径的线段内部点击，而不是端点')
        j=self.session.insert_point(self.cp,i,best[1],best[2]);self.node=(i,j);self.insert_mode=False
        self.sync_node(best[2]);self.refresh()

    def delete_node(self):
        i=self.one()
        if self.node is None or self.node[0]!=i:raise ValueError('请先点击一个节点')
        self.session.delete_point(self.cp,i,self.node[1]);self.node=None;self.refresh()

    def apply_node(self):
        i=self.one()
        if self.node is None or self.node[0]!=i:raise ValueError('请先点击一个节点')
        self.session.move_point(self.cp,i,self.node[1],Point(float(self.node_x.get()),float(self.node_y.get())));self.refresh()

    def begin_draft(self):
        self.require()
        if self.draft is not None:raise ValueError('已有补画草稿，请完成或取消后再开始')
        self.node_drag=None;self.node=None;self.selected=[];self.insert_mode=False;self.draft=[];self.draw()

    def finish_draft(self):
        self.require()
        if self.draft is None:raise ValueError('请先开始补画')
        i=self.session.add_path(self.cp,self.draft);self.draft=None;self.selected=[i];self.refresh()

    def cancel_pending(self):
        self.draft=None;self.node_drag=None;self.insert_mode=False;self.draw()

    def motion(self,event):
        x,y=self.world(event.x,event.y);self.status.set(f'X={x:.1f}, Y={y:.1f} · 点击路径选择；当前字形修正，原始候选保持不变')

    def one(self):
        self.require()
        if self.draft is not None:raise ValueError('请先完成或取消补画')
        if len(self.selected)!=1:raise ValueError('请只选择一条路径')
        return self.selected[0]
    def reverse_selected(self):
        self.session.reverse(self.cp,self.one());self.node=None;self.refresh()
    def delete_selected(self):
        self.require()
        if not self.selected:raise ValueError('请先选中路径')
        self.session.delete(self.cp,self.selected);self.selected=[];self.node=None;self.refresh()
    def split_selected(self):
        i=self.one()
        if self.node is None or self.node[0]!=i:raise ValueError('请在画布中点击该路径的内部节点')
        self.session.split(self.cp,i,self.node[1]);self.node=None;self.selected=[i,i+1];self.refresh()
    def reorder(self,delta):
        i=self.one();self.selected=[self.session.move(self.cp,i,delta)];self.node=None;self.refresh()

    def join_dialog(self):
        self.require()
        if len(self.selected)!=2:raise ValueError('请在列表或画布中选择两条路径')
        a,b=sorted(self.selected);win=tk.Toplevel(self.root);win.title('连接两条路径');win.transient(self.root);win.grab_set()
        reverse_a=tk.BooleanVar();reverse_b=tk.BooleanVar();info=tk.StringVar()
        def ends():
            first=self.session.paths[self.cp][a][::-1] if reverse_a.get() else self.session.paths[self.cp][a]
            second=self.session.paths[self.cp][b][::-1] if reverse_b.get() else self.session.paths[self.cp][b]
            return first[-1],second[0]
        def preview():
            p,q=ends();distance=math.hypot(p.x-q.x,p.y-q.y)
            info.set(f'路径 {a+1} 的末端 → 路径 {b+1} 的起点\n连接距离：{distance:.2f} 字体单位\n若端点不同，将新增一段直线。')
            self.canvas.delete('join_preview');self.canvas.create_line(*self.screen(p.x,p.y),*self.screen(q.x,q.y),fill='#d92929',width=3,dash=(5,3),tags='join_preview')
        def close():self.canvas.delete('join_preview');win.destroy()
        def commit():
            self.selected=[self.session.join(self.cp,a,b,reverse_a.get(),reverse_b.get())]
            self.node=None;close();self.refresh()
        ttk.Label(win,textvariable=info,padding=14).pack()
        ttk.Checkbutton(win,text=f'反转路径 {a+1}',variable=reverse_a,command=preview).pack(anchor='w',padx=12)
        ttk.Checkbutton(win,text=f'反转路径 {b+1}',variable=reverse_b,command=preview).pack(anchor='w',padx=12)
        ttk.Button(win,text='确认连接',command=lambda:self.safe(commit)).pack(side='left',padx=12,pady=12)
        ttk.Button(win,text='取消',command=close).pack(side='right',padx=12,pady=12)
        win.protocol('WM_DELETE_WINDOW',close);preview()

    def undo(self):
        if self.draft is not None or self.node_drag:self.cancel_pending();return
        if self.session:
            cp=self.session.undo()
            if cp is not None:self.selector.current(self.cps.index(cp));self.select()
    def redo(self):
        if self.draft is not None or self.node_drag:self.cancel_pending();return
        if self.session:
            cp=self.session.redo()
            if cp is not None:self.selector.current(self.cps.index(cp));self.select()
    def reset(self):
        self.require();self.cancel_pending();self.session.reset_glyph(self.cp);self.selected=[];self.node=None;self.refresh()
    def confirm(self):
        self.require();self.no_pending();self.session.set_confirmed(self.cp,True);self.refresh()
    def no_pending(self):
        if self.draft is not None or self.node_drag:raise ValueError('请先完成或取消当前节点拖动/补画')
    def save_profile(self):
        self.require();self.no_pending();p=filedialog.asksaveasfilename(defaultextension='.json',initialfile='stroke_edits.json',filetypes=[('笔画修正记录','*.json')])
        if p:self.session.save_project(p);self.status.set('修正记录已保存；原始候选未修改。')
    def load_profile(self):
        self.require()
        if not self.may_discard():return
        p=filedialog.askopenfilename(filetypes=[('笔画修正记录','*.json')])
        if p:self.session.load_project(p);self.cancel_pending();self.selected=[];self.node=None;self.refresh()
    def export(self):
        self.require();self.no_pending();pending=sum(not v for v in self.session.confirmed.values())
        if pending and not messagebox.askyesno('仍有未确认笔画',f'{pending} 个字形尚未人工确认。是否导出供预览的候选字体？',parent=self.root):return
        p=filedialog.asksaveasfilename(defaultextension='.gfont',initialfile='stroke_corrected.gfont',filetypes=[('GFont 字体','*.gfont')])
        if p:
            count=self.session.export(p,self.export_name.get());self.status.set(f'已导出并验证 {count} 字形。请另存修正记录保留确认状态与可编辑数据。')


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('font',nargs='?',type=Path);args=parser.parse_args()
    default=ROOT/'artifacts/photo_0923_hanzi/he_kou_cang_yi.gfont'
    root=tk.Tk();StrokeEditor(root,args.font or (default if default.exists() else None));root.mainloop()


if __name__=='__main__':main()
