"""Run directly from repository root: python -m tests.smoke_coordinate_ui is not required."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import tkinter as tk
from coordinate_editor.app import CoordinateEditor, ROOT

root=tk.Tk();root.withdraw()
app=CoordinateEditor(root,ROOT/'artifacts/photo_0923_final/coordinate_test.gfont')
root.update_idletasks()
# Hidden smoke test exercises real Tk Canvas widgets without opening a user window.
app.canvas.configure(width=850,height=650)
root.geometry('1200x840');root.update()
# A withdrawn window has no allocated viewport; supply explicit dimensions to
# exercise Canvas drawing and registered-image rasterization without showing it.
app.canvas.winfo_width=lambda:850
app.canvas.winfo_height=lambda:650
assert app.session and len(app.cps)==18
app.selector.current(app.cps.index(ord('A')));app.select()
assert app.reference is not None
app.fields['dx'].set('-500');app.fields['dy'].set('-800');app.apply()
assert app.session.transform.dx==-500
app.undo();assert app.session.transform.dx==0
app.redo();assert app.session.transform.dy==-800
for cp in [ord('A'),ord('I'),ord('M')]:
    app.selector.current(app.cps.index(cp));app.select()
    assert app.reference is not None
    app.draw()
    assert app.canvas.find_withtag('reference')
    assert app.canvas.find_withtag('transformed')
    assert app.canvas.find_withtag('bounds')
    x,y=app.screen(123,-456);a,b=app.world(x,y)
    assert abs(a-123)<1e-8 and abs(b+456)<1e-8
with tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'adjusted.gfont';assert app.session.export(p,'UI_Smoke')==18
root.destroy()
print('Tk UI smoke: selection, registered image, transforms, undo/redo, coordinate mapping and export PASS')
