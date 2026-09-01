# -*- coding: utf-8 -*-
"""统计与完整报表。"""
import calendar

from db import get_user_conn


def _month_range(month):
    start = month + "-01"
    y, m = map(int, month.split("-"))
    end = "{}-{:02d}-{:02d}".format(y, m, calendar.monthrange(y, m)[1])
    return start, end


def get_statistics(uid, month):
    conn = get_user_conn(uid)
    start, end = _month_range(month)

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
        "JOIN categories main ON main.id = COALESCE(s.parent_id, s.id) AND main.type='main' "
        "WHERE r.date BETWEEN ? AND ? AND main.code='food' AND r.amount<0",
        (start, end)).fetchone()["t"]

    # 按主分类汇总支出（记录可直接指向一级或二级）
    by_main = conn.execute(
        "SELECT main.code AS code, main.name AS name, "
        "COALESCE(SUM(r.amount),0) AS total FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "JOIN categories main ON main.id = COALESCE(s.parent_id, s.id) AND main.type='main' "
        "WHERE r.date BETWEEN ? AND ? AND r.amount<0 "
        "GROUP BY main.code, main.name ORDER BY total ASC", (start, end)).fetchall()
    by_main_list = [{
        "code": m["code"], "name": m["name"], "total": round(m["total"], 2),
        "percent": round(m["total"] / expense * 100, 1) if expense else 0,
    } for m in by_main]

    # 按子分类汇总支出
    by_sub = conn.execute(
        "SELECT s.code AS code, s.name AS name, "
        "COALESCE(SUM(r.amount),0) AS total FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "WHERE r.date BETWEEN ? AND ? AND r.amount<0 "
        "GROUP BY s.code, s.name ORDER BY total ASC", (start, end)).fetchall()
    by_sub_list = [{
        "code": s["code"], "name": s["name"], "total": round(s["total"], 2),
    } for s in by_sub]

    daily = conn.execute(
        "SELECT date, "
        "COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) AS income, "
        "COALESCE(SUM(CASE WHEN amount<0 THEN amount ELSE 0 END),0) AS expense "
        "FROM records WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
        (start, end)).fetchall()
    daily_list = [{
        "date": d["date"], "income": round(d["income"], 2),
        "expense": round(d["expense"], 2),
    } for d in daily]

    conn.close()
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


def get_report(uid, month):
    """完整报表：当月每笔明细（含备注与支付方式）。"""
    conn = get_user_conn(uid)
    start, end = _month_range(month)
    rows = conn.execute(
        "SELECT r.date, r.amount, r.note, r.payment, "
        "s.type AS s_type, main.name AS main_name, s.name AS sub_name "
        "FROM records r "
        "JOIN categories s ON r.category_id=s.id "
        "JOIN categories main ON main.id = COALESCE(s.parent_id, s.id) AND main.type='main' "
        "WHERE r.date BETWEEN ? AND ? "
        "ORDER BY r.date ASC, r.id ASC", (start, end)).fetchall()
    conn.close()
    return [{
        "date": x["date"],
        "amount": round(x["amount"], 2),
        "main": x["main_name"],
        # 记录指向二级用子类名，指向一级则用一级名括起区分
        "sub": x["sub_name"] if x["s_type"] == "sub" else ("（" + x["sub_name"] + "）"),
        "note": x["note"],
        "payment": x["payment"],
    } for x in rows]