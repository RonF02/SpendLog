# -*- coding: utf-8 -*-
"""数据库连接与初始化。"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "accounting.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """仅规定数据库结构；分类内容完全由用户创建。"""
    conn = get_conn()
    conn.executescript("""
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