"""Independent, non-destructive rectangle editor in source-image coordinates."""
def validate_box(box, size):
    if len(box)!=4 or any(type(v) is not int for v in box):
        raise ValueError('裁切坐标须为四个整数')
    x0,y0,x1,y1=box;w,h=size
    if not 0<=x0<x1<=w or not 0<=y0<y1<=h:
        raise ValueError('裁切框须在图片内且有宽度和高度')
    return list(box)


def open_crop_editor(parent, image, box, on_save):
    import tkinter as tk
    from tkinter import ttk,messagebox
    from PIL import ImageTk
    original=validate_box(box,image.size)
    win=tk.Toplevel(parent);win.title('修改单字裁切');win.geometry('1000x780')
    win.transient(parent);win.grab_set()
    ttk.Label(win,text='拖动重画矩形，或修改坐标后预览。保存后须重新确认该字；取消不改变原裁切。').pack(fill='x')
    bar=ttk.Frame(win);bar.pack(fill='x')
    fields=[tk.StringVar(value=str(v)) for v in original]
    for label,var in zip(('左','上','右','下'),fields):
        ttk.Label(bar,text=label).pack(side='left');ttk.Entry(bar,textvariable=var,width=7).pack(side='left')
    canvas=tk.Canvas(win,bg='#ddd');canvas.pack(fill='both',expand=True)
    state=dict(box=original[:],scale=1,start=None,photo=None)
    # Show the selected character and adjacent strokes at a useful scale.
    margin=max(40,original[2]-original[0],original[3]-original[1])
    ox=max(0,original[0]-margin);oy=max(0,original[1]-margin)
    region=[ox,oy,min(image.width,original[2]+margin),min(image.height,original[3]+margin)]
    def draw(event=None):
        part=image.crop(region);s=min(max(canvas.winfo_width(),100)/part.width,max(canvas.winfo_height(),100)/part.height,5)
        state['scale']=s;state['photo']=ImageTk.PhotoImage(part.resize((max(1,round(part.width*s)),max(1,round(part.height*s)))))
        canvas.delete('all');canvas.create_image(0,0,image=state['photo'],anchor='nw')
        b=state['box'];canvas.create_rectangle((b[0]-region[0])*s,(b[1]-region[1])*s,(b[2]-region[0])*s,(b[3]-region[1])*s,outline='#ed6500',width=2)
    def apply(save=False):
        try:
            b=validate_box([int(v.get()) for v in fields],image.size)
            state['box']=b;draw()
            if save:on_save(b);win.destroy()
        except Exception as exc:messagebox.showerror('无法保存',str(exc),parent=win)
    def release(e):
        if state['start'] is None:return
        x,y=state['start'];state['start']=None;s=state['scale']
        b=[max(0,min(image.width,round(min(x,e.x)/s+region[0]))),max(0,min(image.height,round(min(y,e.y)/s+region[1]))),max(0,min(image.width,round(max(x,e.x)/s+region[0]))),max(0,min(image.height,round(max(y,e.y)/s+region[1])))]
        for v,n in zip(fields,b):v.set(str(n))
        apply()
    def reset():
        for v,n in zip(fields,original):v.set(str(n))
        apply()
    def full():
        region[:]=[0,0,image.width,image.height];draw()
    for label,fn in [('预览',apply),('查看整张图',full),('重置',reset),('保存裁切',lambda:apply(True)),('取消',win.destroy)]:
        ttk.Button(bar,text=label,command=fn).pack(side='left')
    canvas.bind('<Configure>',draw)
    canvas.bind('<ButtonPress-1>',lambda e:state.update(start=(e.x,e.y)))
    canvas.bind('<B1-Motion>',lambda e:(canvas.delete('draft'),canvas.create_rectangle(*state['start'],e.x,e.y,outline='blue',tags='draft')) if state['start'] else None)
    canvas.bind('<ButtonRelease-1>',release)
    return win
