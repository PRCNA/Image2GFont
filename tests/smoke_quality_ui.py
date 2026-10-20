"""Hidden Tk integration checks; not a substitute for visible/driver testing."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from stroke_editor.app import StrokeEditor,ROOT

root=tk.Tk();root.withdraw()
try:
    app=StrokeEditor(root,ROOT/'artifacts/photo_0923_hanzi/he_kou_cang_yi.gfont')
    app.canvas.winfo_width=lambda:850;app.canvas.winfo_height=lambda:650
    original=app.session.payload();position=app.session.position
    app.open_quality();app.quality_window.withdraw()
    assert app.quality_items
    count=len(app.quality_items)
    index=next(i for i,q in enumerate(app.quality_items) if q['gap'] and q['gap']['aligned'])
    app.quality_list.selection_set(index);app.select_quality()
    assert len(app.selected)==2 and app.canvas.find_withtag('quality_hint')
    assert app.session.payload()==original and app.session.position==position
    # Editing rebuilds hints and removes stale path indices/markers.
    app.delete_selected()
    assert app.quality_active is None and not app.canvas.find_withtag('quality_hint')
    assert all(i<len(app.session.paths[app.cp]) for q in app.quality_items for i in q['indices'])
    app.undo();assert app.session.payload()==original and len(app.quality_items)==count
    app.selector.current(app.cps.index(0x6263));app.select()
    assert '扣' in app.quality_summary.get()
    assert all(i<len(app.session.paths[app.cp]) for q in app.quality_items for i in q['indices'])
    # A pending draft must not be discarded by selecting a hint.
    app.begin_draft();app.quality_list.selection_set(0)
    try:app.select_quality()
    except ValueError:pass
    else:raise AssertionError('Pending draft should block hint navigation')
    app.cancel_pending();app.close_quality()
    assert app.quality_window is None and not app.canvas.find_withtag('quality_hint')
    app.open_quality();app.quality_window.withdraw()
    assert app.quality_items
    print('PASS: hint navigation, read-only review, refresh, undo, glyph switch, draft guard, reopen')
finally:
    root.destroy()
