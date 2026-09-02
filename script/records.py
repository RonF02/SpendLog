# -*- coding: utf-8 -*-
"""记账记录：新增一笔。"""
import re
import uuid
from datetime import datetime

from db import get_user_conn
from categories import find_category_id


def add_record(uid, payload):
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

    conn = get_user_conn(uid)
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


def clear_user_data(uid):
    """清空指定用户的全部记账数据（记录 + 分类）。"""
    conn = get_user_conn(uid)
    conn.execute("DELETE FROM records")
    conn.execute("DELETE FROM categories")
    conn.commit()
    conn.close()
    return True, None