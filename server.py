# -*- coding: utf-8 -*-
"""个人记账 PWA 后端 —— HTTP 服务与路由。

部署：0.0.0.0:8080
业务逻辑集中在独立模块（下方 import）：
  categories / records / statistics   —— 各 API 处理
  db                                  —— 数据库连接与初始化
"""
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from admin import (list_users, change_password, admin_reset_password,
                   set_user_disabled, delete_user)
from auth import ensure_admin, register, login, logout, check_auth
from backup import export_records, import_records, backup_info
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


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


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

    def _bearer_token(self):
        h = self.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            return h[7:].strip()
        return None

    def _read_multipart_file(self):
        """读取 multipart/form-data 中第一个带 filename 的文件，返回其字节。"""
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=(.+)$", ctype)
        if not m:
            return None
        boundary = m.group(1).strip().strip('"')
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length)
        sep = ("--" + boundary).encode()
        for part in raw.split(sep):
            part = part.lstrip(b"\r\n")
            if part.startswith(b"Content-Disposition") and b"filename=" in part:
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                body = part[header_end + 4:]
                if body.endswith(b"\r\n"):
                    body = body[:-2]
                return body
        return None

    def _send_bytes(self, body, content_type, filename):
        """发送二进制响应（用于文件下载）。"""
        base = os.path.basename(filename)
        # BaseHTTPRequestHandler 只会 latin-1 编码响应头，中文文件名需用 percent 编码的 RFC5987
        ascii_name = re.sub(r"[^\x00-\x7f]", "_", base)
        from urllib.parse import quote
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Disposition",
                         "attachment; filename=\"{}\"; filename*=UTF-8''{}".format(ascii_name, quote(base)))
        self.end_headers()
        self.wfile.write(body)

    def _require_admin(self):
        """管理员鉴权。通过返回用户信息，否则已发错误响应并返回 None。"""
        user = check_auth(self._bearer_token())
        if not user:
            json_response(self, {"code": 401, "message": "未登录或登录已过期"}, 401)
            return None
        if not user["is_admin"]:
            json_response(self, {"code": 403, "message": "无权限"}, 403)
            return None
        return user

    # ---- 路由 ----
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/auth/me":
            user = check_auth(self._bearer_token())
            if not user:
                json_response(self, {"code": 1, "message": "未登录或登录已过期"}, 401)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": user})
            return
        if path == "/api/admin/users":
            if not self._require_admin():
                return
            json_response(self, {"code": 0, "message": "ok", "data": list_users()})
            return
        if path in ("/", "/index.html"):
            self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path.startswith("/api/"):
            user = check_auth(self._bearer_token())
            if not user:
                json_response(self, {"code": 401, "message": "未登录或登录已过期"}, 401)
                return
            uid = user["id"]
            if path == "/api/categories":
                json_response(self, {"categories": build_category_tree(uid)})
            elif path == "/api/backup/info":
                json_response(self, {"code": 0, "message": "ok",
                                     "data": backup_info(uid)})
            elif path == "/api/export":
                data = export_records(uid)
                name = "记账备份_{}.xlsx".format(datetime.now().strftime("%Y%m%d"))
                self._send_bytes(data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", name)
            elif path in ("/api/statistics", "/api/report"):
                month = self._query_param("month") or datetime.now().strftime("%Y-%m")
                data = get_statistics(uid, month) if path == "/api/statistics" else {"report": get_report(uid, month)}
                json_response(self, data)
            else:
                json_response(self, {"code": 404, "message": "Not Found"}, 404)
        else:
            self._serve_file(os.path.join(STATIC_DIR, path.lstrip("/")), self._guess_type(path))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/import":
            user = check_auth(self._bearer_token())
            if not user:
                json_response(self, {"code": 1, "message": "未登录或登录已过期"}, 401)
                return
            body = self._read_multipart_file()
            if body is None:
                json_response(self, {"code": 1, "message": "未找到上传文件"}, 400)
                return
            try:
                result = import_records(user["id"], body)
            except Exception as e:
                json_response(self, {"code": 1, "message": "Excel 解析失败：{}".format(e)}, 400)
                return
            if "error" in result:
                json_response(self, {"code": 1, "message": result["error"]}, 400)
                return
            json_response(self, {"code": 0, "message": "ok", "data": result}, 201)
            return
        try:
            payload = self._read_json()
        except Exception:
            json_response(self, {"code": 1, "message": "JSON 解析失败"}, 400)
            return
        if path == "/api/auth/login":
            data, err = login(payload.get("username"), payload.get("password"))
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": data})
            return
        if path == "/api/auth/register":
            data, err = register(payload.get("username"), payload.get("password"),
                                 payload.get("confirm_password"))
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": data}, 201)
            return
        if path == "/api/auth/logout":
            logout(self._bearer_token())
            json_response(self, {"code": 0, "message": "ok"})
            return
        if path == "/api/auth/password":
            user = check_auth(self._bearer_token())
            if not user:
                json_response(self, {"code": 401, "message": "未登录或登录已过期"}, 401)
                return
            data, err = change_password(user["id"], payload.get("old_password"),
                                        payload.get("new_password"), self._bearer_token())
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": data})
            return
        if path.startswith("/api/admin/"):
            if not self._require_admin():
                return
            uid = _to_int(payload.get("user_id"))
            if uid is None:
                json_response(self, {"code": 1, "message": "缺少有效的 user_id"}, 400)
                return
            if path == "/api/admin/users/reset_password":
                data, err = admin_reset_password(uid, payload.get("new_password"))
            elif path == "/api/admin/users/disable":
                data, err = set_user_disabled(uid, True)
            elif path == "/api/admin/users/enable":
                data, err = set_user_disabled(uid, False)
            else:
                json_response(self, {"code": 1, "message": "Not Found"}, 404)
                return
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": data})
            return
        if path not in ("/api/records", "/api/categories"):
            json_response(self, {"code": 1, "message": "Not Found"}, 404)
            return
        user = check_auth(self._bearer_token())
        if not user:
            json_response(self, {"code": 401, "message": "未登录或登录已过期"}, 401)
            return
        uid = user["id"]
        data, err = (add_record(uid, payload) if path == "/api/records"
                     else add_category(uid, payload))
        if err:
            json_response(self, {"code": 1, "message": err}, 400)
        else:
            json_response(self, {"code": 0, "message": "ok", "data": data}, 201)

    def do_DELETE(self):
        path = self.path.split("?")[0]
        if path == "/api/admin/users":
            if not self._require_admin():
                return
            uid = _to_int(self._query_param("user_id"))
            if uid is None:
                json_response(self, {"code": 1, "message": "缺少有效的 user_id"}, 400)
                return
            data, err = delete_user(uid)
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": data})
            return
        if path != "/api/categories":
            json_response(self, {"code": 1, "message": "Not Found"}, 404)
            return
        user = check_auth(self._bearer_token())
        if not user:
            json_response(self, {"code": 401, "message": "未登录或登录已过期"}, 401)
            return
        data, err = delete_category(user["id"], self._query_param("code"))
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
        self.send_header("Cache-Control", "no-store")  # 开发期禁用缓存，改动即时生效
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
    ensure_admin()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("SpendLog demo running at http://{}:{}/  ".format(HOST, PORT))
    print("手机访问请使用电脑局域网 IP，例如 http://<局域网IP>:8080/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()