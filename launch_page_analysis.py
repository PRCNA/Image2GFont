"""Select a page backend, then open the existing explicit review workflow."""
import os,queue,subprocess,threading,sys,json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

ROOT=Path(__file__).resolve().parent

def main():
    root=tk.Tk();root.title('Image2GFont - 页面分析');root.geometry('680x240')
    status=tk.StringVar(value='RapidOCR 生成文字框；千问仅对裁切后的单字提供纠错建议，歧义由人工修改标注。')
    ttk.Label(root,text='页面分析方式',padding=10).pack(anchor='w')
    ttk.Label(root,text='RapidOCR 切割 → 千问单字建议 → 人工确认').pack(anchor='w',padx=10)
    ttk.Label(root,textvariable=status,wraplength=650,padding=10).pack(fill='x')
    events=queue.Queue();state={'running':False}
    def start():
        paths=filedialog.askopenfilenames(filetypes=[('图片','*.png *.jpg *.jpeg *.bmp *.tif *.webp')])
        if not paths:return
        runtime=ROOT/'.venv-ocr'/'Scripts/python.exe'
        if not runtime.exists():messagebox.showerror('缺少环境',str(runtime));return
        out=ROOT/'artifacts'/('page_analysis_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        command=[str(runtime),str(ROOT/'ocr_demo.py'),*paths,'--output',str(out)]
        state['running']=True;button.config(state='disabled');status.set('正在本地分析。密集页面可能需要数分钟；不会自动确认字符或生成字体。')
        log=out.with_suffix('.log')
        def work():
            try:
                env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
                with log.open('w',encoding='utf-8') as f:result=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode:raise RuntimeError('分析失败，请查看日志：'+str(log))
                data=json.loads((out/'results.json').read_text(encoding='utf-8'))
                if not any(r.get('characters') for r in data['images']):raise RuntimeError('没有可审核候选。请查看结果与日志：'+str(out))
                events.put(('ok',out/'results.json'))
            except Exception as exc:events.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def poll():
        try:
            kind,value=events.get_nowait();state['running']=False;button.config(state='normal')
            if kind=='error':status.set(value);messagebox.showerror('分析失败',value)
            else:
                data=json.loads(value.read_text(encoding='utf-8'));failed=sum(r.get('status')=='failed' for r in data['images'])
                status.set(f'候选已生成，失败页面 {failed} 张。请在复核界面调用千问识字建议、标注歧义并确认字符。')
                # Analyzer has exited, releasing Qwen GPU memory before Paddle use.
                subprocess.Popen([sys.executable,str(ROOT/'ocr_review.py'),'--results',str(value)],cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except queue.Empty:pass
        root.after(200,poll)
    def close():
        if state['running']:messagebox.showinfo('仍在分析','请等待分析结束后关闭。');return
        root.destroy()
    button=ttk.Button(root,text='选择图片并分析',command=start);button.pack(anchor='w',padx=10)
    root.protocol('WM_DELETE_WINDOW',close);root.after(200,poll);root.mainloop()

if __name__=='__main__':main()
