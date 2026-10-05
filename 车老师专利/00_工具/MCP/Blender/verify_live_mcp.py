import asyncio, json, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    params=StdioServerParameters(command=sys.executable,args=['-m','blender_mcp.server','--host','127.0.0.1','--port','9877'],env={'BLENDER_HOST':'127.0.0.1','BLENDER_PORT':'9877','BLENDER_MCP_DISABLE_TELEMETRY':'1','DISABLE_TELEMETRY':'1'})
    out={}
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as s:
            await s.initialize()
            for name,args in [('get_addon_status',{}),('get_scene_info',{'user_prompt':'E:\\migrate\\01所有项目\\blender-5.1.1-windows-x64\\blender-5.1.1-windows-x64，放屁，这个下面就有blener，你仔细查看，'})]:
                result=await s.call_tool(name,args)
                out[name]=result.model_dump(mode='json')
    Path(__file__).with_name('live_connection_verified.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False))
asyncio.run(main())

