# -*- coding: utf-8 -*-
"""个人记账 PWA demo 后端
技术栈：Python 标准库（sqlite3 + http.server），无第三方依赖
部署：0.0.0.0:8080
存储：SQLite（data/accounting.db）

表结构：categories(分类字典)、records(记账记录)
API（均返回 JSON）：
  GET  /                    前端页面 index.html
  GET  /api/categories      分类字典（JSON 树）
  POST /api/records         新增记账
  GET  /api/statistics?month=YYYY-MM   月度统计（含恩格尔预留）
"""
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "accounting.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
HOST = "0.0.0.0"
PORT = 8080

# 分类内容完全由用户通过接口创建，后端不硬编码分类。
# init_db 仅规定数据库结构。


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            type TEXT CHECK(type IN ('main', 'sub')) NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category_id INTEGER NOT NULL,
            note TEXT,
            payment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE INDEX IF NOT EXISTS idx_records_date ON records(date);
        CREATE INDEX IF NOT EXISTS idx_records_category ON records(category_id);
    """)
    conn.commit()
    conn.close()


def build_category_tree():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, code, name, parent_id, type FROM categories").fetchall()
    # 被记账引用过的分类 id 集合
    used_ids = {r[0] for r in conn.execute("SELECT DISTINCT category_id FROM records")}
    mains = {}
    for r in rows:
        if r["type"] == "main":
            mains[r["id"]] = {
                "code": r["code"], "name": r["name"],
                "used": r["id"] in used_ids, "children": [],
            }
    for r in rows:
        if r["type"] == "sub":
            parent = mains.get(r["parent_id"])
            if parent:
                parent["children"].append(
                    {"code": r["code"], "name": r["name"], "used": r["id"] in used_ids})
    for m in mains.values():
        m["children"].sort(key=lambda c: c["name"])
        # 主分类只要有一个子被使用，或自身被使用，即视为不可删
        if any(c["used"] for c in m["children"]):
            m["used"] = True
    result = list(mains.values())
    result.sort(key=lambda c: c["code"])
    conn.close()
    return result


def find_category_id(conn, code):
    row = conn.execute(
        "SELECT id FROM categories WHERE code=? AND type='sub'", (code,)).fetchone()
    if not row:
        # 允许多级？只允许二级，但若传入主分类 code 则取其第一个子类兜底（实际应传二级）
        row = conn.execute(
            "SELECT id FROM categories WHERE code=? AND type='main'", (code,)).fetchone()
    return row["id"] if row else None


def add_record(payload):
    date = str(payload.get("date", "")).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return None, "日期格式应为 YYYY-MM-DD"
    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        return None, "金额格式错误"
    code = str(payload.get("category_code", "")).strip()
    note = str(payload.get("note", "")).strip()
    payment = str(payload.get("payment", "")).strip()

    conn = get_conn()
    cid = find_category_id(conn, code)
    if cid is None:
        conn.close()
        return None, "分类编码不存在：{}".format(code)
    rid = str(uuid.uuid4())
    created_at = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO records (id,date,amount,category_id,note,payment,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (rid, date, amount, cid, note, payment, created_at),
    )
    conn.commit()
    conn.close()
    return {"id": rid}, None


def add_category(payload):
    """新增分类。parent_code 为空则建一级(main)，否则建二级(sub)并挂到该一级下。
    返回 (data, err)；data 为新增后的分类。"""
    name = str(payload.get("name", "")).strip()
    code = str(payload.get("code", "")).strip()
    parent_code = str(payload.get("parent_code") or "").strip() or None
    if not name or not code:
        return None, "名称与标识不能为空"
    conn = get_conn()
    dup = conn.execute("SELECT 1 FROM categories WHERE code=?",
                       (code,)).fetchone()
    if dup:
        conn.close()
        return None, "该标识已存在：{}".format(code)
    if parent_code:
        parent = conn.execute(
            "SELECT id FROM categories WHERE code=? AND type='main'",
            (parent_code,)).fetchone()
        if not parent:
            conn.close()
            return None, "父一级分类不存在：{}".format(parent_code)
        conn.execute(
            "INSERT INTO categories (code,name,parent_id,type) VALUES (?,?,?,'sub')",
            (code, name, parent["id"]))
    else:
        conn.execute(
            "INSERT INTO categories (code,name,parent_id,type) VALUES (?,?,NULL,'main')",
            (code, name))
    conn.commit()
    conn.close()
    return {"code": code, "name": name, "parent_code": parent_code}, None


def delete_category(code):
    """删除分类（仅允许删除"空"分类：自身及其子均未被 records 引用）。
    删除一级会连同其所有（空）子分类一起删除。"""
    code = str(code or "").strip()
    if not code:
        return None, "缺少分类标识"
    conn = get_conn()
    row = conn.execute(
        "SELECT id, parent_id, type FROM categories WHERE code=?",
        (code,)).fetchone()
    if not row:
        conn.close()
        return None, "分类不存在：{}".format(code)
    cid = row["id"]
    if conn.execute("SELECT 1 FROM records WHERE category_id=? LIMIT 1",
                    (cid,)).fetchone():
        conn.close()
        return None, "该分类已被记账使用，不能删除"
    # 若是主分类，检查其子分类
    used_subs = []
    if row["type"] == "main":
        for s in conn.execute("SELECT id FROM categories WHERE parent_id=?",
                              (cid,)).fetchall():
            if conn.execute("SELECT 1 FROM records WHERE category_id=? LIMIT 1",
                            (s["id"],)).fetchone():
                used_subs.append(s["id"])
        if used_subs:
            conn.close()
            return None, "该主分类下仍有已使用的子分类，不能删除"
    if row["type"] == "main":
        conn.execute("DELETE FROM categories WHERE parent_id=?", (cid,))
    conn.execute("DELETE FROM categories WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return {"code": code}, None


def get_statistics(month):
    conn = get_conn()
    start = month + "-01"
    # 计算当月最后一天
    import calendar
    y, m = map(int, month.split("-"))
    end = "{}-{:02d}-{:02d}".format(y, m, calendar.monthrange(y, m)[1])

    income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS t FROM records "
        "WHERE date BETWEEN ? AND ? AND amount>0", (start, end)).fetchone()["t"]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS t FROM records "
        "WHERE date BETWEEN ? AND ? AND amount<0", (start, end)).fetchone()["t"]

    # 恩格尔系数预留：餐饮(food) 支出 + 总收入
    food = conn.execute(
        "SELECT COALESCE(SUM(r.amount),0) AS t FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "JOIN categories main ON s.parent_id=main.id "
        "WHERE r.date BETWEEN ? AND ? AND main.code='food' AND r.amount<0",
        (start, end)).fetchone()["t"]

    # 按主分类汇总支出
    # 兼容两种情况：记录指向二级分类（标准）或直接指向一级分类（如"学习"无二级时）
    by_main = conn.execute(
        "SELECT main.code AS code, main.name AS name, "
        "COALESCE(SUM(r.amount),0) AS total FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "JOIN categories main ON main.id = COALESCE(s.parent_id, s.id) "
        "   AND main.type='main' "
        "WHERE r.date BETWEEN ? AND ? AND r.amount<0 "
        "GROUP BY main.code, main.name ORDER BY total ASC",
        (start, end)).fetchall()

    by_main_list = []
    for m in by_main:
        by_main_list.append({
            "code": m["code"], "name": m["name"], "total": round(m["total"], 2),
            "percent": round(m["total"] / expense * 100, 1) if expense else 0,
        })

    # 按子分类汇总支出
    by_sub = conn.execute(
        "SELECT s.code AS code, s.name AS name, "
        "COALESCE(SUM(r.amount),0) AS total FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "WHERE r.date BETWEEN ? AND ? AND r.amount<0 "
        "GROUP BY s.code, s.name ORDER BY total ASC",
        (start, end)).fetchall()
    by_sub_list = [
        {"code": s["code"], "name": s["name"], "total": round(s["total"], 2)}
        for s in by_sub
    ]

    # 每日趋势
    daily = conn.execute(
        "SELECT date, "
        "COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) AS income, "
        "COALESCE(SUM(CASE WHEN amount<0 THEN amount ELSE 0 END),0) AS expense "
        "FROM records WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
        (start, end)).fetchall()
    daily_list = [
        {"date": d["date"], "income": round(d["income"], 2),
         "expense": round(d["expense"], 2)} for d in daily
    ]

    conn.close()
    # 恩格尔系数（预留）：餐饮支出 / 总收入 * 100（无收入则返回 None）
    engel = round(abs(food) / income * 100, 2) if income else None
    return {
        "month": month,
        "incomeTotal": round(income, 2),
        "expenseTotal": round(expense, 2),
        "balance": round(income + expense, 2),
        "foodExpenseTotal": round(food, 2),
        "engelCoefficient": engel,   # 恩格尔系数预留
        "byMainCategory": by_main_list,
        "bySubCategory": by_sub_list,
        "daily": daily_list,
    }


def get_report(month):
    """完整报表：当月每一笔明细，含备注、支付方式、一级/二级分类。"""
    conn = get_conn()
    start = month + "-01"
    import calendar
    y, m = map(int, month.split("-"))
    end = "{}-{:02d}-{:02d}".format(y, m, calendar.monthrange(y, m)[1])
    rows = conn.execute(
        "SELECT r.date, r.amount, r.note, r.payment, "
        "s.type AS s_type, "
        "main.name AS main_name, "
        "s.code AS sub_code, s.name AS sub_name "
        "FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "JOIN categories main ON main.id = COALESCE(s.parent_id, s.id) AND main.type='main' "
        "WHERE r.date BETWEEN ? AND ? "
        "ORDER BY r.date ASC, r.id ASC", (start, end)).fetchall()
    conn.close()
    result = []
    for x in rows:
        # 记录指向二级时 sub 用子类名，指向一级时可显式区分
        sub = x["sub_name"] if x["s_type"] == "sub" else ("（" + x["sub_name"] + "）")
        result.append({
            "date": x["date"],
            "amount": round(x["amount"], 2),
            "main": x["main_name"],
            "sub": sub,
            "note": x["note"],
            "payment": x["payment"],
        })
    return result


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
        # 精简日志，复用端口的自动选择日志在 __main__ 打印
        pass

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path in ("/manifest.webmanifest"):
            self._serve_file(os.path.join(STATIC_DIR, "manifest.webmanifest"),
                             "application/manifest+json; charset=utf-8")
        elif path == "/api/categories":
            json_response(self, {"categories": build_category_tree()})
        elif path == "/api/statistics":
            month = self._query_param("month")
            if not month:
                month = datetime.now().strftime("%Y-%m")
            json_response(self, get_statistics(month))
        elif path == "/api/report":
            month = self._query_param("month")
            if not month:
                month = datetime.now().strftime("%Y-%m")
            json_response(self, {"report": get_report(month)})
        else:
            self._serve_file(os.path.join(STATIC_DIR, path.lstrip("/")),
                             self._guess_type(path))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path in ("/api/records", "/api/categories"):
            try:
                payload = self._read_json()
            except Exception:
                json_response(self, {"code": 1, "message": "JSON 解析失败"}, 400)
                return
            if path == "/api/records":
                rid, err = add_record(payload)
            else:
                rid, err = add_category(payload)
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": rid}, 201)
        else:
            json_response(self, {"code": 1, "message": "Not Found"}, 404)

    def do_DELETE(self):
        path = self.path.split("?")[0]
        if path == "/api/categories":
            code = self._query_param("code")
            rid, err = delete_category(code)
            if err:
                json_response(self, {"code": 1, "message": err}, 400)
            else:
                json_response(self, {"code": 0, "message": "ok", "data": rid})
        else:
            json_response(self, {"code": 1, "message": "Not Found"}, 404)

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

    def _guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".json": "application/json; charset=utf-8",
            ".ico": "image/x-icon",
        }
        return mime.get(ext, "application/octet-stream")

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