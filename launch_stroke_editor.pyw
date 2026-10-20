import os
from pathlib import Path
import traceback
import tkinter as tk
from tkinter import messagebox
os.chdir(Path(__file__).resolve().parent)
try:
    from stroke_editor.app import main
    main()
except Exception:
    root=tk.Tk();root.withdraw();messagebox.showerror('笔画修正器启动失败',traceback.format_exc())
