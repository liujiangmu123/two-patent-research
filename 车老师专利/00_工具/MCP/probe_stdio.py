"""Read-only MCP initialization, tool discovery, and optional status probe."""
import json
import queue
import subprocess
import sys
import threading

args = sys.argv[1:]
tool_name = None
if args and args[0].startswith("--tool="):
    tool_name = args.pop(0).split("=", 1)[1]
process = subprocess.Popen(
    args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
)
responses = queue.Queue()

def read_lines():
    for line in process.stdout:
        try:
            responses.put(json.loads(line))
        except json.JSONDecodeError:
            pass
    responses.put(None)

threading.Thread(target=read_lines, daemon=True).start()

def request(payload):
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    if "id" not in payload:
        return None
    while True:
        response = responses.get(timeout=20)
        if response is None:
            raise RuntimeError("MCP server exited before response")
        if response.get("id") == payload["id"]:
            if "error" in response:
                raise RuntimeError(json.dumps(response["error"]))
            return response["result"]

try:
    result = request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "patent-mcp-readonly-probe", "version": "1.0"}}})
    print(json.dumps({"serverInfo": result.get("serverInfo"),
                      "protocolVersion": result.get("protocolVersion")}, ensure_ascii=False))
    request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tool_result = request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = [tool["name"] for tool in tool_result.get("tools", [])]
    print(json.dumps({"tool_count": len(names), "status_tools": [
        name for name in names if any(part in name for part in ("status", "version", "scene_info"))]}, ensure_ascii=False))
    if tool_name:
        if tool_name not in names:
            raise RuntimeError(f"Tool unavailable: {tool_name}")
        status = request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": tool_name, "arguments": {}}})
        print(json.dumps({"status": status}, ensure_ascii=False))
finally:
    process.stdin.close()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=3)
