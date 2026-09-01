# -*- coding: utf-8 -*-
"""用户数据的备份（导出/导入）与备份概况。

- 导出：把某用户的全部记录写成一个 .xlsx，一条记录一行。
- 导入：读取用户上传的 .xlsx，按"记录ID"合并去重——已存在的跳过，缺失的插入；
  若记录指向的分类（按名称）尚未建立，则自动创建分类后再插入记录。
- 概况：返回该用户的记录数与导出文件的预估体积。

导出/导入格式列（表头不区分大小写/别名，顺序无关）：
  记录ID / 日期 / 金额 / 一级分类 / 二级分类 / 备注 / 支付方式
记录ID 列用于导入时去重，若手工新增的记录没有该列为空，则作为新记录插入。
"""
import uuid
from datetime import datetime

from categories import make_code
from db import get_user_conn
from excel import write_xlsx, read_xlsx

EXPORT_HEADERS = ["记录ID", "日期", "金额", "一级分类", "二级分类", "备注", "支付方式"]

# 表头别名 -> 规范键
_ALIASES = {
    "rid": ["记录ID", "记录id", "ID", "id", "Uuid", "uuid"],
    "date": ["日期", "date", "Date", "DATE"],
    "amount": ["金额", "amount", "Amount", "金额元", "数额", "money"],
    "main": ["一级分类", "一级", "主分类", "主类", "大类", "main", "Main"],
    "sub": ["二级分类", "二级", "子分类", "子类", "小类", "sub", "Sub"],
    "note": ["备注", "note", "Note", "说明", "desc"],
    "payment": ["支付方式", "支付", "支付渠道", "方式", "payment", "Payment"],
}


def _map_headers(headers):
    """把可选表头映射为规范键，返回 {规范键: 表头}。"""
    idx = {}
    for h in headers:
        hs = (h or "").strip()
        if not hs:
            continue
        for key, aliases in _ALIASES.items():
            if hs in aliases or hs.lower() == key.lower():
                idx[key] = hs
                break
    return idx


def _to_amount(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def export_records(uid):
    """导出某用户全部记录为 .xlsx 字节。"""
    conn = get_user_conn(uid)
    rows = conn.execute(
        "SELECT r.id, r.date, r.amount, r.note, r.payment, "
        "s.type AS s_type, main.name AS main_name, s.name AS sub_name "
        "FROM records r "
        "JOIN categories s ON r.category_id = s.id "
        "JOIN categories main ON main.id = COALESCE(s.parent_id, s.id) AND main.type='main' "
        "ORDER BY r.date, r.id").fetchall()
    conn.close()
    data = [(
        x["id"], x["date"], x["amount"],
        x["main_name"],
        x["sub_name"] if x["s_type"] == "sub" else "",
        x["note"] or "", x["payment"] or "",
    ) for x in rows]
    return write_xlsx(EXPORT_HEADERS, data)


def backup_info(uid):
    """返回记录数与导出文件的预估体积（字节）。"""
    conn = get_user_conn(uid)
    n = conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
    conn.close()
    size = len(export_records(uid))
    return {"record_count": n, "export_size": size}


def import_records(uid, data):
    """导入 .xlsx，按记录ID合并去重。返回统计摘要。"""
    headers, rows = read_xlsx(data)
    if not rows:
        return {"added": 0, "skipped_existing": 0, "skipped_no_category": 0,
                "skipped_invalid": 0, "missing_categories": [], "total_rows": 0}

    col = _map_headers(headers)
    for key in ("date", "amount", "main"):
        if key not in col:
            return {"error": "缺少必要列：日期 / 金额 / 一级分类"}

    conn = get_user_conn(uid)
    # 已有记录ID集合（用于合并去重）
    existing = {r[0] for r in conn.execute("SELECT id FROM records")}

    # 加载分类：一级按名称、二级按 (父一级名, 二级名)
    cats = conn.execute("SELECT id, code, name, parent_id, type FROM categories").fetchall()
    by_id = {r["id"]: r for r in cats}
    mains_by_name = {}
    subs_by_key = {}
    taken_codes = set()
    for r in cats:
        taken_codes.add(r["code"])
        if r["type"] == "main":
            mains_by_name.setdefault(r["name"], []).append(r["id"])
        else:
            parent = by_id.get(r["parent_id"])
            key = (parent["name"] if parent else "", r["name"])
            subs_by_key[key] = r["id"]

    created_categories = 0

    def ensure_main(conn, name):
        """返回一级分类 id；不存在则自动创建。"""
        ids = mains_by_name.get(name)
        if ids:
            return ids[0], False
        code = make_code(name, taken_codes)
        cur = conn.execute(
            "INSERT INTO categories (code, name, parent_id, type) VALUES (?,?,NULL,'main')",
            (code, name))
        cid = cur.lastrowid
        taken_codes.add(code)
        mains_by_name.setdefault(name, []).append(cid)
        return cid, True

    def ensure_sub(conn, main_id, main_name, name):
        """返回二级分类 id；不存在则挂到 main_id 下自动创建。"""
        cid = subs_by_key.get((main_name, name))
        if cid is not None:
            return cid, False
        code = make_code(name, taken_codes)
        cur = conn.execute(
            "INSERT INTO categories (code, name, parent_id, type) VALUES (?,?,?,'sub')",
            (code, name, main_id))
        cid = cur.lastrowid
        taken_codes.add(code)
        subs_by_key[(main_name, name)] = cid
        return cid, True

    added = skipped_existing = skipped_invalid = 0
    now = datetime.now().isoformat(timespec="seconds")

    for row in rows:
        date = (row.get(col.get("date", "")) or "").strip()
        amount = _to_amount(row.get(col.get("amount", "")))
        main_name = (row.get(col.get("main", "")) or "").strip()
        sub_name = (row.get(col.get("sub", "")) or "").strip()
        rid = (row.get(col.get("rid", "")) or "").strip()
        note = row.get(col.get("note", "")) or ""
        payment = row.get(col.get("payment", "")) or ""
        if not date or amount is None or not main_name:
            skipped_invalid += 1
            continue
        if rid and rid in existing:
            skipped_existing += 1
            continue
        main_id, created_main = ensure_main(conn, main_name)
        if created_main:
            created_categories += 1
        cid = None
        if sub_name:
            cid, created_sub = ensure_sub(conn, main_id, main_name, sub_name)
            if created_sub:
                created_categories += 1
        else:
            cid = main_id
        if not rid:
            rid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO records (id,date,amount,category_id,note,payment,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, date, amount, cid, note, payment, now))
        added += 1
        existing.add(rid)

    conn.commit()
    conn.close()
    return {
        "added": added,
        "created_categories": created_categories,
        "skipped_existing": skipped_existing,
        "skipped_invalid": skipped_invalid,
        "total_rows": len(rows),
    }