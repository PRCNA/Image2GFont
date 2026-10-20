"""Collect manually bound page projects into one candidate font."""
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from font_project import FontProject


def main():
    root=tk.Tk();root.withdraw()
    try:
        paths=filedialog.askopenfilenames(title='选择已完成裁切和字符绑定的 page.json（可多选）',filetypes=[('Page projects','*.json')],parent=root)
        if not paths:return
        name=simpledialog.askstring('字体名称','请输入这一组字体的名称：',parent=root)
        if not name:return
        destination=filedialog.askdirectory(title='选择字体工程存放目录',parent=root)
        if not destination:return
        project=FontProject.create(Path(destination)/('font_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')),name)
        for path in paths:project.add_page(path)
        output=project.generate(project.root/'generated')
        messagebox.showinfo('候选字体已生成','请继续检查轨迹；尚未经过驱动验证。\n'+str(output),parent=root)
        from stroke_editor.app import StrokeEditor
        root.deiconify();StrokeEditor(root,output);root.mainloop()
    except Exception as exc:
        messagebox.showerror('未完成',str(exc),parent=root)
    finally:
        try:root.destroy()
        except tk.TclError:pass

if __name__=='__main__':main()
