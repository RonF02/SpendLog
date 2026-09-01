# -*- coding: utf-8 -*-
"""分类字典相关：分类树、增删分类、按 code 查 id。"""
from db import get_user_conn


def build_category_tree(uid):
    conn = get_user_conn(uid)
    rows = conn.execute(
        "SELECT id, code, name, parent_id, type FROM categories").fetchall()
    used_ids = {r[0] for r in conn.execute("SELECT DISTINCT category_id FROM records")}
    mains = {}
    for r in rows:
        if r["type"] == "main":
            mains[r["id"]] = {
                "code": r["code"], "name": r["name"],
                "used": r["id"] in used_ids, "children": [],
            }
    for r in rows:
        if r["type"] == "sub" and r["parent_id"] in mains:
            mains[r["parent_id"]]["children"].append(
                {"code": r["code"], "name": r["name"], "used": r["id"] in used_ids})
    for m in mains.values():
        m["children"].sort(key=lambda c: c["name"])
        if any(c["used"] for c in m["children"]):  # 任一子被用则主类不可删
            m["used"] = True
    result = sorted(mains.values(), key=lambda c: c["code"])
    conn.close()
    return result


def find_category_id(conn, code):
    """返回分类 id，兼容二级与一级（记录可直接指向一级）。"""
    row = conn.execute(
        "SELECT id FROM categories WHERE code=?", (code,)).fetchone()
    return row["id"] if row else None


def add_category(uid, payload):
    name = str(payload.get("name", "")).strip()
    code = str(payload.get("code", "")).strip()
    parent_code = str(payload.get("parent_code") or "").strip() or None
    if not (name and code):
        return None, "名称与标识不能为空"
    conn = get_user_conn(uid)
    if conn.execute("SELECT 1 FROM categories WHERE code=?", (code,)).fetchone():
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


def delete_category(uid, code):
    code = str(code or "").strip()
    if not code:
        return None, "缺少分类标识"
    conn = get_user_conn(uid)
    row = conn.execute(
        "SELECT id, parent_id, type FROM categories WHERE code=?",
        (code,)).fetchone()
    if not row:
        conn.close()
        return None, "分类不存在：{}".format(code)
    cid = row["id"]
    # 自身或（主分类下）任一子分类被记账引用则不可删除
    if conn.execute("SELECT 1 FROM records WHERE category_id=?", (cid,)).fetchone():
        conn.close()
        return None, "该分类已被记账使用，不能删除"
    if row["type"] == "main":
        used = conn.execute(
            "SELECT 1 FROM categories s WHERE s.parent_id=? AND EXISTS "
            "(SELECT 1 FROM records r WHERE r.category_id=s.id)", (cid,)).fetchone()
        if used:
            conn.close()
            return None, "该主分类下仍有已使用的子分类，不能删除"
        conn.execute("DELETE FROM categories WHERE parent_id=?", (cid,))
    conn.execute("DELETE FROM categories WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return {"code": code}, None