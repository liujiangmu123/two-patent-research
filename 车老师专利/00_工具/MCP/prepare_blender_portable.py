"""Download an official stable portable Blender into the authorised tool folder."""
import re
import urllib.request
import ssl
import hashlib
import json
import zipfile
from pathlib import Path
import certifi
root=Path('车老师专利/00_工具/MCP/Blender/portable').resolve();root.mkdir(exist_ok=True)
base='https://download.blender.org/release/Blender4.5/'
ctx=ssl.create_default_context(cafile=certifi.where())
listing=urllib.request.urlopen(base,context=ctx,timeout=40).read().decode()
names=set(re.findall(r'blender-4\.5\.(\d+)-windows-x64\.zip',listing))
if not names:raise RuntimeError('No official stable portable Windows build found')
patch=max(map(int,names));name=f'blender-4.5.{patch}-windows-x64.zip';url=base+name
archive=root/name
print('Downloading official '+name,flush=True)
with urllib.request.urlopen(url,context=ctx,timeout=60) as src,archive.open('wb') as dst:
    while True:
        block=src.read(1024*1024)
        if not block:break
        dst.write(block)
print('Validating and extracting official archive',flush=True)
with zipfile.ZipFile(archive) as z:
    for info in z.infolist():
        target=(root/info.filename).resolve()
        if not target.is_relative_to(root):raise RuntimeError('Unsafe archive path')
    z.extractall(root)
exe=root/f'blender-4.5.{patch}-windows-x64/blender.exe'
manifest={'source':url,'zip_bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'version':f'4.5.{patch}','executable':str(exe),'status':'portable extracted, addon connection pending'}
(root/'portable_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
