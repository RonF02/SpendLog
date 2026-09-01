# -*- coding: utf-8 -*-
"""个人记账 PWA 后端 —— HTTP 服务与路由。

部署：0.0.0.0:8080
业务逻辑集中在独立模块（下方 import）：
  categories / records / statistics   —— 各 API 处理
  db                                  —— 数据库连接与初始化
"""
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from categories import build_category_tree, add_category, delete_category
from db import init_db
from records import add_record
from statistics import get_statistics, get_report

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HOST = "0.0.0.0"
PORT = 8080


def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "SpendLogDemo/0.1"

    def log_message(self, fmt, *args):
        pass

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _query_param(self, key):
        q = self.path.split("?", 1)
        if len(q) < 2:
            return None
        for part in q[1].split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k == key:
                    return v
        return None

    # ---- 路由 ----
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/api/categories":
            json_response(self, {"categories": build_category_tree()})
        elif path in ("/api/statistics", "/api/report"):
            month = self._query_param("month") or datetime.now().strftime("%Y-%m")
            data = get_statistics(month) if path == "/api/statistics" else {"report": get_report(month)}
            json_response(self, data)
        else:
            self._serve_file(os.path.join(STATIC_DIR, path.lstrip("/")), self._guess_type(path))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path not in ("/api/records", "/api/categories"):
            json_response(self, {"code": 1, "message": "Not Found"}, 404)
            return
        try:
            payload = self._read_json()
        except Exception:
            json_response(self, {"code": 1, "message": "JSON 解析失败"}, 400)
            return
        data, err = (add_record(payload) if path == "/api/records"
                     else add_category(payload))
        if err:
            json_response(self, {"code": 1, "message": err}, 400)
        else:
            json_response(self, {"code": 0, "message": "ok", "data": data}, 201)

    def do_DELETE(self):
        path = self.path.split("?")[0]
        if path != "/api/categories":
            json_response(self, {"code": 1, "message": "Not Found"}, 404)
            return
        data, err = delete_category(self._query_param("code"))
        if err:
            json_response(self, {"code": 1, "message": err}, 400)
        else:
            json_response(self, {"code": 0, "message": "ok", "data": data})

    # ---- 静态文件 ----
    def _serve_file(self, path, content_type):
        if not os.path.isfile(path):
            json_response(self, {"code": 404, "message": "Not Found"}, 404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _guess_type(self, path):
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".json": "application/json; charset=utf-8",
            ".ico": "image/x-icon",
            ".webmanifest": "application/manifest+json; charset=utf-8",
        }
        return mime.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("SpendLog demo running at http://{}:{}/  ".format(HOST, PORT))
    print("手机访问请使用电脑局域网 IP，例如 http://<局域网IP>:8080/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()