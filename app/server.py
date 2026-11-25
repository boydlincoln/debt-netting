"""本地 Web 服务：标准库 HTTP + JSON API + 静态前端，仅监听 127.0.0.1。"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, quote, urlparse

from .config import WEB_DIR
from .extract import MaterialError
from .service import AppService, ServiceError

MAX_BODY = 25 * 1024 * 1024


class DebtHTTPServer(ThreadingHTTPServer):
    """避免与 8765 等常用端口上的其他本地服务共享监听。"""

    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "DebtNetting/1.0"
    protocol_version = "HTTP/1.1"

    service: AppService
    routes: list

    # ------------------------------------------------------------------ HTTP
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method: str):
        # 无论业务处理器是否使用请求体，都先完整读取，避免 keep-alive 连接被残留字节污染
        self._raw_body = b""
        try:
            self._raw_body = self._read_request_body()
        except ServiceError as exc:
            self.close_connection = True
            self._json({"error": str(exc)}, exc.status)
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            self._handle_api(method, path, parse_qs(parsed.query))
        elif method == "GET":
            self._serve_static(path)
        else:
            self._json({"error": "接口不存在"}, 404)

    def _read_request_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError as exc:
            raise ServiceError("Content-Length 无效") from exc
        if length <= 0:
            return b""
        if length > MAX_BODY:
            raise ServiceError("请求体过大（上限 25MB）", 413)
        return self.rfile.read(length)

    def _handle_api(self, method: str, path: str, query: dict):
        try:
            for route_method, pattern, handler in self.routes:
                match = pattern.match(path)
                if match and route_method == method:
                    return handler(self, match, query)
            self._json({"error": "接口不存在"}, 404)
        except ServiceError as exc:
            self._json({"error": str(exc)}, exc.status)
        except MaterialError as exc:
            self._json({"error": str(exc)}, 400)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json({"error": f"请求参数错误：{exc}"}, 400)
        except Exception as exc:  # pragma: no cover - 兜底
            traceback.print_exc()
            self._json({"error": f"服务器内部错误：{exc}"}, 500)

    # ------------------------------------------------------------------ 工具
    def _body(self) -> dict:
        raw = getattr(self, "_raw_body", b"")
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServiceError("请求体不是有效的 JSON") from exc
        if not isinstance(data, dict):
            raise ServiceError("请求体必须是 JSON 对象")
        return data

    def _json(self, payload, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _binary(self, filename: str, content: bytes, mime: str):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        suffix = Path(filename).suffix or ""
        fallback = f"download{suffix}"
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _serve_static(self, path: str):
        if path in ("/", ""):
            relative = "index.html"
        else:
            relative = path.lstrip("/")
        target = (WEB_DIR / relative).resolve()
        try:
            target.relative_to(WEB_DIR.resolve())
        except ValueError:
            self._json({"error": "非法路径"}, 403)
            return
        if not target.exists() or not target.is_file():
            if "." not in relative:
                target = WEB_DIR / "index.html"
            else:
                self._json({"error": "文件不存在"}, 404)
                return
        content = target.read_bytes()
        mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix in (".html", ".js", ".css", ".svg"):
            mime += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):  # 静默访问日志
        return


def _route(method: str, pattern: str):
    return method, re.compile(pattern)


class DebtServer:
    def __init__(self, service: AppService, host: str = "127.0.0.1", port: int = 8765):
        self.service = service
        self.host = host
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    # ------------------------------------------------------------------ 路由
    def _build_routes(self):
        service = self.service

        def route(method: str, pattern: str, handler: Callable):
            return method, re.compile(pattern), handler

        def export_handler(handler_kind: str):
            def handler(request, match, query):
                plan_id = (query.get("plan_id") or [None])[0]
                filename, content, mime = service.export(handler_kind, plan_id)
                request._binary(filename, content, mime)

            return handler

        routes = [
            route("GET", r"^/api/health$", lambda r, m, q: r._json({"ok": True, "app": "debt-netting", "version": "1.0"})),
            route("POST", r"^/api/shutdown$", self._shutdown_handler),
            route("GET", r"^/api/bootstrap$", lambda r, m, q: r._json(service.dashboard())),
            route("GET", r"^/api/cases$", lambda r, m, q: r._json({"items": service.list_cases()})),
            route("POST", r"^/api/cases$", self._create_case_handler),
            route("POST", r"^/api/cases/([\w\-]+)/activate$", self._activate_case_handler),
            route("PATCH", r"^/api/cases/([\w\-]+)$", self._rename_case_handler),
            route("GET", r"^/api/settings$", lambda r, m, q: r._json(service.settings.public())),
            route("PUT", r"^/api/settings$", lambda r, m, q: r._json(service.update_settings(r._body()))),
            route("POST", r"^/api/ontology/reload$", lambda r, m, q: r._json(service.reload_ontology())),

            route("GET", r"^/api/entities$", lambda r, m, q: r._json({"items": service.list_entities()})),
            route("POST", r"^/api/entities$", lambda r, m, q: r._json(service.create_entity(r._body()), 201)),
            route("PUT", r"^/api/entities/([\w\-]+)$", lambda r, m, q: r._json(service.update_entity(m.group(1), r._body()))),
            route("DELETE", r"^/api/entities/([\w\-]+)$", lambda r, m, q: r._json(
                service.delete_entity(m.group(1), (q.get("cascade") or ["0"])[0] in ("1", "true", "yes"))
            )),

            route("GET", r"^/api/debts$", lambda r, m, q: r._json({
                "items": service.list_debts(
                    status=(q.get("status") or [""])[0],
                    group=(q.get("group") or [""])[0],
                    keyword=(q.get("q") or [""])[0],
                )
            })),
            route("POST", r"^/api/debts$", lambda r, m, q: r._json(service.create_debt(r._body()), 201)),
            route("POST", r"^/api/debts/import$", self._import_debts_handler),
            route("GET", r"^/api/debts/([\w\-]+)$", lambda r, m, q: r._json(service.get_debt(m.group(1)))),
            route("PUT", r"^/api/debts/([\w\-]+)$", lambda r, m, q: r._json(service.update_debt(m.group(1), r._body()))),
            route("DELETE", r"^/api/debts/([\w\-]+)$", lambda r, m, q: r._json(service.delete_debt(m.group(1)))),
            route("POST", r"^/api/debts/([\w\-]+)/confirm$", lambda r, m, q: r._json(service.set_debt_status(m.group(1), "confirmed"))),
            route("POST", r"^/api/debts/([\w\-]+)/reject$", lambda r, m, q: r._json(service.set_debt_status(m.group(1), "rejected"))),
            route("POST", r"^/api/eligibility/recheck$", lambda r, m, q: r._json(service.recheck_eligibility())),

            route("POST", r"^/api/netting/run$", self._netting_run_handler),
            route("POST", r"^/api/netting/compare$", self._netting_compare_handler),
            route("GET", r"^/api/plans$", lambda r, m, q: r._json({"items": service.list_plans()})),
            route("GET", r"^/api/plans/latest$", lambda r, m, q: r._json(service.get_plan(None))),
            route("GET", r"^/api/plans/([\w\-]+)$", lambda r, m, q: r._json(service.get_plan(m.group(1)))),
            route("POST", r"^/api/plans/([\w\-]+)/narrative$", lambda r, m, q: r._json(service.generate_narrative(m.group(1)))),
            route("DELETE", r"^/api/plans/([\w\-]+)$", lambda r, m, q: r._json(service.delete_plan(m.group(1)))),

            route("GET", r"^/api/graph$", lambda r, m, q: r._json(service.graph(
                include_ineligible=(q.get("ineligible") or ["1"])[0] not in ("0", "false")
            ))),

            route("GET", r"^/api/materials$", lambda r, m, q: r._json({"items": service.list_materials()})),
            route("POST", r"^/api/materials/extract$", self._extract_handler),
            route("POST", r"^/api/materials/import$", self._import_handler),

            route("POST", r"^/api/llm/test$", lambda r, m, q: r._json(service.llm_test())),

            route("GET", r"^/api/audit$", lambda r, m, q: r._json({
                "items": service.audit_log(min(500, int((q.get("limit") or ["100"])[0] or 100)))
            })),

            route("GET", r"^/api/export/([\w\-]+)$", lambda r, m, q: r._binary(*service.export(m.group(1), (q.get("plan_id") or [None])[0]))),
            route("POST", r"^/api/seed$", lambda r, m, q: r._json(service.seed_demo(bool(r._body().get("force"))))),
            route("POST", r"^/api/reset$", lambda r, m, q: r._json(service.reset_all())),
        ]
        return routes

    def _create_case_handler(self, request: ApiHandler, match, query):
        body = request._body()
        name = str(body.get("name") or "").strip()
        with_demo = bool(body.get("with_demo"))
        request._json({"case": self.service.create_case(name, with_demo)}, 201)

    def _activate_case_handler(self, request: ApiHandler, match, query):
        request._body()
        request._json({"case": self.service.switch_case(match.group(1))})

    def _rename_case_handler(self, request: ApiHandler, match, query):
        body = request._body()
        request._json({"case": self.service.rename_case(match.group(1), str(body.get("name") or ""))})

    def _import_debts_handler(self, request: ApiHandler, match, query):
        body = request._body()
        rows = body.get("rows")
        if not isinstance(rows, list):
            raise ServiceError("rows 必须是数组")
        request._json(self.service.import_debts(rows), 201)

    def _netting_run_handler(self, request: ApiHandler, match, query):
        body = request._body()
        request._json(self.service.run_netting(str(body.get("mode") or "legal")))

    def _netting_compare_handler(self, request: ApiHandler, match, query):
        request._body()
        request._json(self.service.compare_netting())

    def _shutdown_handler(self, request: ApiHandler, match, query):
        if request.headers.get("X-Requested-With") != "debt-netting":
            raise ServiceError("未授权的操作", 403)
        request._json({"ok": True, "message": "本地服务正在停止"})
        threading.Thread(target=request.server.shutdown, daemon=True).start()

    def _extract_handler(self, request: ApiHandler, match, query):
        body = request._body()
        content = body.get("content_base64") or ""
        data = base64.b64decode(content, validate=False) if content else None
        if data is not None and len(data) > MAX_BODY:
            raise ServiceError("文件过大（上限 25MB）", 413)
        result = self.service.extract(
            text=str(body.get("text") or ""),
            filename=str(body.get("filename") or ""),
            data=data,
            use_llm=bool(body.get("use_llm", True)),
        )
        request._json(result)

    def _import_handler(self, request: ApiHandler, match, query):
        body = request._body()
        request._json(
            self.service.import_candidates(
                body.get("candidates") or [],
                material_id=body.get("material_id"),
            ),
            201,
        )

    # ------------------------------------------------------------------ 启动
    def start(self, background: bool = False):
        handler = type(
            "BoundApiHandler",
            (ApiHandler,),
            {"service": self.service, "routes": self._build_routes()},
        )
        self.httpd = DebtHTTPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True
        if background:
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
        else:
            self.httpd.serve_forever()
        return self

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)
