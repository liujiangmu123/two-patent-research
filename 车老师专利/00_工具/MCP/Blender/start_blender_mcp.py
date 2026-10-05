import bpy, addon_utils, json, traceback
from pathlib import Path
import sys
root = Path(__file__).parent
try:
    addon_path = bpy.utils.user_resource('SCRIPTS', path='addons', create=True)
    if addon_path not in sys.path:
        sys.path.insert(0, addon_path)
    bpy.utils.refresh_script_paths()
    addon_utils.enable('blender_mcp', default_set=True, persistent=True)
    bpy.context.scene.blendermcp_port = 9877
    bpy.context.scene.blendermcp_auto_start_server = True
    if not getattr(bpy.types, 'blendermcp_server', None):
        bpy.ops.blendermcp.start_server()
    bpy.ops.wm.save_userpref()
    result = {'ok': True, 'blender_version': bpy.app.version_string, 'port': 9877, 'running': bpy.types.blendermcp_server.running, 'file': bpy.data.filepath}
except Exception:
    result = {'ok': False, 'error': traceback.format_exc()}
(root / 'bootstrap_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
