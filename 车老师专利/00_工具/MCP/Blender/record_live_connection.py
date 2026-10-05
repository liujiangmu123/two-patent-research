import json
from pathlib import Path
base=Path('车老师专利/00_工具/MCP/Blender')
p=base/'installation_manifest.json'
m=json.loads(p.read_text(encoding='utf-8-sig'))
m['blender_executable'].update(found=True,path=r'E:\migrate\01所有项目\blender-5.1.1-windows-x64\blender-5.1.1-windows-x64\blender.exe',signature='Valid — Blender Foundation',version='5.1.1')
m['bundled_addon'].update(installed_in_blender=True,enabled_in_blender=True)
m['checks'].update(addon_connection='verified_via_project_venv_stdio_mcp',addon_connection_result='Protocol 13, Blender 5.1.1, scene read successful, telemetry false')
m['launch']['env'].update(BLENDER_HOST='127.0.0.1',BLENDER_PORT='9877')
m['notes'].append('Correction: earlier outer-folder-only conclusion was incomplete. Nested executable exists. Both BLENDER_HOST and BLENDER_PORT env are required because package import creates a second server module; CLI flags alone do not propagate to all tool callbacks.')
m['not_executed']=['cloud generation/asset tools','Blender patent scene edits']
m['live_verification_file']='live_connection_verified.json'
p.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
p=base/'用户提供目录检查_20261003.json'
v=json.loads(p.read_text(encoding='utf-8-sig'))
v['correction']={'inner_folder':m['blender_executable']['path'],'executable_exists':True,'blender_version':'5.1.1','mcp_scene_read_verified':True,'earlier_conclusion_superseded':True}
p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
print('Blender installation and correction records updated.')
