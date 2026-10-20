"""Run pip in bundled Python; workspace temp dirs use inherited workspace ACLs."""
import os,runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path('.venv-ocr/Lib/site-packages').resolve()))
import pip
sys.path.pop(0)
original=os.mkdir
def mkdir(path,mode=0o777,*,dir_fd=None):
    return original(path,0o777 if mode==0o700 else mode,dir_fd=dir_fd)
os.mkdir=mkdir
runpy.run_module('pip',run_name='__main__')
