#!/bin/sh
# 用法：sh run_fc.sh 脚本名.py   以 freecadcmd 无头运行，输出写入 $TEMP/run.log
B="/c/Users/Administrator/AppData/Local/Programs/FreeCAD 1.1/bin/freecadcmd.exe"
HERE=$(cd "$(dirname "$0")" && pwd)
export TC_SCRIPT=$(cygpath -w "$HERE/$1")
R=$(cygpath -w "$TEMP/_fc_run.py")
cat > "$TEMP/_fc_run.py" <<'PY'
import traceback,os,sys
log=open(os.path.join(os.environ["TEMP"],"run.log"),"w",encoding="utf-8")
sys.stdout=sys.stderr=log
try:
    p=os.environ["TC_SCRIPT"]
    exec(compile(open(p,encoding="utf-8").read(),p,"exec"),{"__file__":p,"__name__":"__main__"})
except BaseException:
    traceback.print_exc()
log.close()
PY
"$B" -c "exec(open(r'$R').read())" >/dev/null 2>&1
rm -f "$TEMP/_fc_run.py"
cat "$TEMP/run.log"
