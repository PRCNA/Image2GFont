import traceback
from pathlib import Path
import os
import tkinter as tk
from tkinter import messagebox

os.chdir(Path(__file__).resolve().parent)
try:
    from coordinate_editor.app import main
    main()
except Exception:
    root=tk.Tk();root.withdraw()
    messagebox.showerror('坐标纠正器启动失败',traceback.format_exc())
