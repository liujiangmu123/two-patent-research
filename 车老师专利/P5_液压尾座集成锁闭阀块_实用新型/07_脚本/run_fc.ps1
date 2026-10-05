# Run a FreeCAD script headless with freecadcmd (no window). Output goes to $env:TEMP\p5_fc_run.log and is printed.
# Usage: powershell -NoProfile -File 07_脚本\run_fc.ps1 <script.py | absolute path> [ENV=VALUE ...]
# ASCII only (PowerShell 5.1 safe).
param([Parameter(Mandatory = $true)][string]$Script, [string[]]$Env = @())
$ErrorActionPreference = "Stop"
$fc = "C:\Users\Administrator\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([System.IO.Path]::IsPathRooted($Script)) { $target = $Script } else { $target = Join-Path $here $Script }
foreach ($kv in $Env) { $p = $kv.Split("=", 2); [Environment]::SetEnvironmentVariable($p[0], $p[1], "Process") }
$env:P5_SCRIPT = $target
$env:P5_SCRIPTS_DIR = $here
$log = Join-Path $env:TEMP "p5_fc_run.log"
$runner = Join-Path $env:TEMP ("p5_fc_runner_" + [guid]::NewGuid().ToString("N") + ".py")
@'
import os, sys, traceback
log = open(os.path.join(os.environ["TEMP"], "p5_fc_run.log"), "w", encoding="utf-8")
sys.stdout = sys.stderr = log
try:
    p = os.environ["P5_SCRIPT"]
    exec(compile(open(p, encoding="utf-8-sig").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
except BaseException:
    traceback.print_exc()
log.close()
'@ | Set-Content -Path $runner -Encoding UTF8
$code = "exec(open(r'" + $runner + "', encoding='utf-8-sig').read())"
& $fc -c $code *> $null
Remove-Item $runner -ErrorAction SilentlyContinue
Get-Content $log -Encoding UTF8
