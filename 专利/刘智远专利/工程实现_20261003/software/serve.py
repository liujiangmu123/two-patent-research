"""Local-only engineering workbench. Run from the workspace root with its venv."""
from __future__ import annotations

import argparse
import copy
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import tempfile
import urllib.parse

from trusstwin.pipeline import demo_case, run_case

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
WEB = HERE / "web"
OUTPUT = PACKAGE / "deliverables" / "workbench"
MAX_BODY = 4 * 1024 * 1024


def clean_json(value):
    """Reject non-finite JSON; do not turn invalid engineering results into zeros."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


class Workbench:
    def __init__(self):
        self.lock = threading.RLock()
        self.case = demo_case()
        self.case["synthetic"] = True
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.result = run_case(self.case, OUTPUT)
        self.save_case()

    def save_case(self):
        (OUTPUT / "case.json").write_bytes(clean_json(self.case))

    def snapshot(self):
        return {"case": self.case, "result": self.result,
                "build": {"version": "0.1.0", "mode": "engineering_prototype",
                          "rendering": "parameter_bound_surface_gaussians",
                          "raw_photo_training": False}}

    def run(self, case):
        # Keep the last accepted project if validation/analysis fails.
        if not isinstance(case, dict):
            raise ValueError("项目 JSON 必须是对象")
        with tempfile.TemporaryDirectory(prefix="trusstwin-stage-", dir=OUTPUT.parent) as stage:
            staging = Path(stage)
            result = run_case(case, staging)
            clean_json(result)
            (staging / "case.json").write_bytes(clean_json(case))
            for name in ("surface_gaussians.ply", "gaussian_members.json", "result.json", "case.json"):
                (staging / name).replace(OUTPUT / name)
        self.case, self.result = copy.deepcopy(case), result
        return self.snapshot()


def handler_class(workbench):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(fmt % args, flush=True)

        def send(self, payload, status=200, content_type="application/json; charset=utf-8"):
            data = payload if isinstance(payload, bytes) else clean_json(payload)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                return self.send({"status": "ok", "version": "0.1.0"})
            if path == "/api/project":
                with workbench.lock:
                    return self.send(workbench.snapshot())
            is_export = path.startswith("/export/")
            if is_export:
                name = urllib.parse.unquote(path[8:])
                if name not in {"result.json", "case.json", "surface_gaussians.ply", "gaussian_members.json"}:
                    return self.send({"error": "未知导出文件"}, 404)
                source = OUTPUT / name
            else:
                requested = urllib.parse.unquote(path).lstrip("/") or "index.html"
                source = (WEB / requested).resolve()
                if not source.is_relative_to(WEB.resolve()):
                    return self.send({"error": "路径无效"}, 400)
            with workbench.lock:
                if not source.is_file():
                    return self.send({"error": "文件不存在"}, 404)
                mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
                return self.send(source.read_bytes(), content_type=mime)

        def do_POST(self):
            # No cross-origin writes and no commands supplied by a browser.
            origin = self.headers.get("Origin")
            if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
                return self.send({"error": "仅接受本地同源请求"}, 403)
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= MAX_BODY:
                    return self.send({"error": "JSON 输入为空或超过 4 MiB"}, 413)
                payload = json.loads(self.rfile.read(n), parse_constant=lambda x: (_ for _ in ()).throw(ValueError("非有限数值")))
                if not isinstance(payload, dict):
                    raise ValueError("JSON 请求必须是对象")
                with workbench.lock:
                    if self.path == "/api/run":
                        case = payload.get("case", payload)
                    elif self.path == "/api/demo":
                        case = demo_case(with_thickness=bool(payload.get("with_thickness", False)))
                        case["synthetic"] = True
                    elif self.path == "/api/measurement":
                        case = copy.deepcopy(workbench.case)
                        measurement = payload.get("measurement", payload)
                        if not isinstance(measurement, dict):
                            raise ValueError("测量记录必须是对象")
                        if measurement.get("kind") != "thickness":
                            raise ValueError("该入口接受 thickness 记录；其他观测通过项目 JSON 导入")
                        case.setdefault("measurements", []).append(measurement)
                    else:
                        return self.send({"error": "未知接口"}, 404)
                    return self.send(workbench.run(case))
            except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                return self.send({"error": str(exc)}, 422)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                return self.send({"error": f"计算未完成：{type(exc).__name__}: {exc}"}, 500)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    state = Workbench()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_class(state))
    print(f"TrussTwin 工程工作台 http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
