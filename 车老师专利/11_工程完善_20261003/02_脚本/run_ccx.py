import os
import sys
import json
import subprocess
from pathlib import Path
root=Path('车老师专利/11_工程完善_20261003/06_仿真/FEM').resolve()
case=sys.argv[1]
exe=Path('C:/Users/Administrator/AppData/Local/Programs/FreeCAD 1.1/bin/ccx.exe')
env=os.environ.copy();env['OMP_NUM_THREADS']='4';env['CCX_NPROC_RESULTS']='4'
with (root/(case+'_solver.log')).open('w',encoding='utf-8') as log:
    p=subprocess.run([str(exe),'-i',case],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
print(json.dumps({'case':case,'exit':p.returncode,'frd_exists':(root/(case+'.frd')).exists()}))
raise SystemExit(p.returncode)
