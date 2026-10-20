import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
from stroke_editor.app import StrokeEditor,ROOT

root=tk.Tk();root.withdraw()
app=StrokeEditor(root,ROOT/'artifacts/photo_0923_hanzi/he_kou_cang_yi.gfont')
app.canvas.winfo_width=lambda:850;app.canvas.winfo_height=lambda:650
app.fit();app.draw()
assert app.cp==0x85cf and app.reference is not None
assert app.canvas.find_withtag('reference') and app.canvas.find_withtag('transformed')
before=len(app.session.paths[app.cp])
index=next(i for i,s in enumerate(app.session.paths[app.cp]) if len(s)>=3)
app.selected=[index];app.node=(index,1);app.split_selected()
assert len(app.session.paths[app.cp])==before+1
app.undo();assert len(app.session.paths[app.cp])==before
app.selected=[index];app.reverse_selected();app.confirm();assert app.session.confirmed[app.cp]
app.selected=[index];app.delete_selected();assert not app.session.confirmed[app.cp]
app.undo();assert app.session.confirmed[app.cp]
app.selected=[index];app.refresh();assert app.canvas.find_withtag('stroke_selection')
app.selected=[0,1];app.refresh();original_count=len(app.session.paths[app.cp])
app.join_dialog()
dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
assert app.canvas.find_withtag('join_preview')
next(w for w in dialog.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='取消').invoke()
assert len(app.session.paths[app.cp])==original_count
assert not app.canvas.find_withtag('join_preview')
app.join_dialog()
dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
next(w for w in dialog.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='确认连接').invoke()
assert len(app.session.paths[app.cp])==original_count-1
app.undo();assert len(app.session.paths[app.cp])==original_count
# Drag one node: preview is reversible without changing session until release.
app.selected=[0];p=app.session.paths[app.cp][0][0];x,y=app.screen(p.x,p.y)
position=app.session.position
app.start_drag(SimpleNamespace(x=x,y=y,state=0))
assert app.node_drag is not None
app.move_drag(SimpleNamespace(x=x+18,y=y+12))
assert app.session.position==position and app.session.paths[app.cp][0][0]==p
app.end_drag(SimpleNamespace(x=x+18,y=y+12))
assert app.session.position==position+1 and app.session.paths[app.cp][0][0]!=p
app.undo();assert app.session.paths[app.cp][0][0]==p
# Insert into a chosen segment using its exact midpoint, then delete it.
app.selected=[0];s=app.session.paths[app.cp][0]
j=next(j for j in range(len(s)-1) if s[j]!=s[j+1])
a,b=s[j:j+2];x,y=app.screen((a.x+b.x)/2,(a.y+b.y)/2)
old_nodes=len(s);app.insert_at(SimpleNamespace(x=x,y=y))
assert len(app.session.paths[app.cp][0])==old_nodes+1
app.delete_node();assert len(app.session.paths[app.cp][0])==old_nodes
before=app.session.paths[app.cp];app.begin_draft()
for x,y in [(220,220),(250,230),(280,250)]:app.start_drag(SimpleNamespace(x=x,y=y,state=0))
assert app.session.paths[app.cp]==before and app.canvas.find_withtag('draft')
app.cancel_pending();assert app.session.paths[app.cp]==before
app.begin_draft()
for x,y in [(220,220),(250,230),(280,250)]:app.start_drag(SimpleNamespace(x=x,y=y,state=0))
app.finish_draft();assert len(app.session.paths[app.cp])==len(before)+1
app.undo();assert app.session.paths[app.cp]==before
with tempfile.TemporaryDirectory() as temp:
    p=Path(temp);app.session.save_project(p/'edits.json');app.session.load_project(p/'edits.json')
    assert app.session.export(p/'stroke_edited.gfont','StrokeUISmoke')==4
root.destroy()
print('Stroke Tk smoke: image, path edits, join, atomic node drag, insertion/deletion, draft cancel/commit, undo, save/load and export PASS')
