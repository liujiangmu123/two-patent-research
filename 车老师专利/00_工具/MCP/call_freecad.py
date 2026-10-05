"""Invoke one tool through the installed local FreeCAD MCP server."""
import argparse
import asyncio
import base64
import json
import os
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tool")
    parser.add_argument("--args", default="{}")
    parser.add_argument("--args-file")
    parser.add_argument("--code-file")
    parser.add_argument("--result-file")
    parser.add_argument("--image-file")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    options = parser.parse_args()
    arguments = json.loads(options.args)
    if options.args_file:
        arguments = json.loads(Path(options.args_file).read_text(encoding="utf-8"))
    if options.code_file:
        arguments = {"code": Path(options.code_file).read_text(encoding="utf-8"),
                     "timeout_ms": options.timeout_ms}
    server = StdioServerParameters(
        command="C:/Users/Administrator/.local/bin/freecad-mcp.exe",
        args=["--mode", "xmlrpc", "--transport", "stdio"],
    )
    with open(os.devnull, "w") as errlog:
        async with stdio_client(server, errlog=errlog) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=options.timeout_ms / 1000 + 15)) as session:
                await session.initialize()
                response = await session.call_tool(options.tool, arguments)
                result = response.model_dump(mode="json", exclude_none=True)
    if options.image_file:
        def save_image(value):
            if isinstance(value, dict):
                if isinstance(value.get("data"), str) and (value.get("format") == "png" or value.get("mimeType") == "image/png"):
                    Path(options.image_file).write_bytes(base64.b64decode(value["data"]))
                    value["data"] = "saved:" + options.image_file
                for child in value.values():
                    save_image(child)
            elif isinstance(value, list):
                for child in value:
                    save_image(child)
            elif isinstance(value, str):
                try:
                    save_image(json.loads(value))
                except (ValueError, TypeError):
                    pass
        save_image(result)
        # Screenshots can also be nested in a JSON text content block.
        for item in result.get("content", []):
            if item.get("type") == "text":
                try:
                    payload = json.loads(item["text"])
                    save_image(payload)
                    item["text"] = json.dumps(payload, ensure_ascii=False)
                except ValueError:
                    pass
    if options.result_file:
        Path(options.result_file).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result.get('structuredContent', result), ensure_ascii=False))
    if result.get("isError"):
        raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(main())
