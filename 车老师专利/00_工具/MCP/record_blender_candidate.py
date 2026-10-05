"""Record user-supplied addon folder and reserve a non-conflicting MCP port."""
import datetime
import hashlib
import json
from pathlib import Path

folder=Path('E:/migrate/01所有项目/blender-5.1.1-windows-x64')
root=Path('车老师专利/00_工具/MCP/Blender').resolve()
files=[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.iterdir() if p.is_file()]
record={'checked_at':datetime.datetime.now().astimezone().isoformat(),'folder':str(folder),'files':files,'blender_exe_in_folder':(folder/'blender.exe').is_file(),'addon_version_read_from_bl_info':'1.2','conclusion':'addon-only directory; no Blender executable or complete installation in supplied directory','migration_search':'bounded filename search interrupted after no matches; not proof that entire E drive has no executable','reserved_addon_port':9877,'reason':'FreeCAD Robust MCP socket listener already uses 9876','scene_access':'not connected; no Blender scene accessed or modified'}
(root/'用户提供目录检查_20261003.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
config=Path('C:/Users/Administrator/.codex/config.toml')
source=config.read_text(encoding='utf-8')
start=source.index('[mcp_servers.blender]')
end=source.index('[mcp_servers.blender.env]',start)
old=source[start:end]
new=old.replace("'--port', '9876'","'--port', '9877'")
if new!=old:
    backup=config.with_name('config.toml.before-blender-port9877-20261003.bak')
    if not backup.exists():backup.write_bytes(config.read_bytes())
    config.write_text(source[:start]+new+source[end:],encoding='utf-8')
manifest=root/'installation_manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8'))
m['launch']['args'][-1]='9877'
m['blender_executable']['checked_locations'].append(str(folder))
m['user_supplied_directory_check']=record
m['notes'].append('2026-10-03: Blender MCP port changed to9877 to avoid live FreeCAD9876 socket. Client restart/reload required for saved config to apply.')
manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
