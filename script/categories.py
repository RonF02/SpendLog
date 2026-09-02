# -*- coding: utf-8 -*-
"""分类字典相关：分类树、增删分类、按 code 查 id。"""
import hashlib
import re

from db import get_user_conn


def make_code(name, taken):
    """由名称生成稳定且唯一的分类 code（同名称恒同 code）。

    优先保留 ASCII 字母/数字并小写化；若为空（如纯中文名），
    退化为固定前缀 + 名称哈希，保证稳定且几乎唯一。
    """
    base = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if not base:
        base = "cat_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    base = base[:32]
    code = base
    i = 1
    while code in taken:
        i += 1
        code = "{}_{}".format(base, i)
    return code


def build_category_tree(uid):
    conn = get_user_conn(uid)
    rows = conn.execute(
        "SELECT id, code, name, parent_id, type, sort_order FROM categories").fetchall()
    used_ids = {r[0] for r in conn.execute("SELECT DISTINCT category_id FROM records")}
    mains = {}
    for r in rows:
        if r["type"] == "main":
            mains[r["id"]] = {
                "code": r["code"], "name": r["name"],
                "used": r["id"] in used_ids, "children": [],
                "sort": r["sort_order"] if r["sort_order"] is not None else r["id"],
            }
    for r in rows:
        if r["type"] == "sub" and r["parent_id"] in mains:
            mains[r["parent_id"]]["children"].append(
                {"code": r["code"], "name": r["name"], "used": r["id"] in used_ids,
                 "sort": r["sort_order"] if r["sort_order"] is not None else r["id"]})
    for m in mains.values():
        m["children"].sort(key=lambda c: c["sort"])
        if any(c["used"] for c in m["children"]):  # 任一子被用则主类不可删
            m["used"] = True
    result = sorted(mains.values(), key=lambda c: c["sort"])
    conn.close()
    # 仅暴露业务字段，排序用的内部 sort 不返回前端
    for m in result:
        m.pop("sort", None)
        for c in m["children"]:
            c.pop("sort", None)
    return result


def find_category_id(conn, code):
    """返回分类 id，兼容二级与一级（记录可直接指向一级）。"""
    row = conn.execute(
        "SELECT id FROM categories WHERE code=?", (code,)).fetchone()
    return row["id"] if row else None


def add_category(uid, payload):
    name = str(payload.get("name", "")).strip()
    parent_code = str(payload.get("parent_code") or "").strip() or None
    if not name:
        return None, "名称不能为空"
    conn = get_user_conn(uid)
    # 标识未提供时自动哈希生成；提供则沿用（供导入等内部使用）
    code = str(payload.get("code", "")).strip()
    if not code:
        taken = {r[0] for r in conn.execute("SELECT code FROM categories")}
        code = make_code(name, taken)
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


def reorder_categories(uid, payload):
    """按传入的 codes 顺序更新 sort_order。

    一级分类：payload={codes:[...]}；二级分类：payload={codes:[...], parent_code:主类code}。
    """
    codes = payload.get("codes")
    if not isinstance(codes, list) or not codes:
        return None, "缺少分类顺序列表"
    parent_code = str(payload.get("parent_code") or "").strip() or None
    conn = get_user_conn(uid)
    try:
        params = []
        for i, code in enumerate(codes):
            code = str(code or "").strip()
            if parent_code:
                r = conn.execute(
                    "SELECT id FROM categories WHERE code=? AND parent_id=("
                    "SELECT id FROM categories WHERE code=? AND type='main')",
                    (code, parent_code)).fetchone()
            else:
                r = conn.execute(
                    "SELECT id FROM categories WHERE code=? AND type='main'",
                    (code,)).fetchone()
            if not r:
                return None, "分级错误：分类不存在于该分组：{}".format(code)
            params.append((i, r["id"]))
        conn.executemany("UPDATE categories SET sort_order=? WHERE id=?", params)
        conn.commit()
    finally:
        conn.close()
    return {"count": len(codes)}, None