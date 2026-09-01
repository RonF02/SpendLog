# -*- coding: utf-8 -*-
"""数据库连接与初始化：账户库 + 按用户分库。

- data/accounts.db   用户账号与登录会话（UTF-8 编码）
- data/{id}.db       每个用户的业务数据（categories/records），按用户 id 命名
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录（本文件位于 script/）
DATA_DIR = os.path.join(BASE_DIR, "data")
ACCOUNTS_DB = os.path.join(DATA_DIR, "accounts.db")


def get_conn(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.text_factory = str  # 统一按 UTF-8 处理文本，支持中文用户名
    conn.execute("PRAGMA encoding='UTF-8';")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_accounts_conn():
    """账户库连接（users + sessions）。"""
    return get_conn(ACCOUNTS_DB)


def user_db_path(uid):
    """指定用户的业务库文件路径：data/{id}.db"""
    return os.path.join(DATA_DIR, "{}.db".format(uid))


def delete_user_db(uid):
    """删除指定用户业务库文件（不存在则忽略）。"""
    path = user_db_path(uid)
    if os.path.exists(path):
        os.remove(path)


def get_user_conn(uid):
    """指定用户业务库连接。"""
    return get_conn(user_db_path(uid))


def _init_accounts():
    conn = get_accounts_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0,
            last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES accounts(id)
        );
    """)
    _migrate_accounts(conn)
    conn.commit()
    conn.close()


def _migrate_accounts(conn):
    """老库补列：disabled（禁用）、last_login（最近登录）。幂等，可重复执行。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)")}
    if "disabled" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
    if "last_login" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN last_login TEXT")
    # sessions 老库补列：created_at（签发时间）、user_agent（设备标识）
    scols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "created_at" not in scols:
        conn.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")
    if "user_agent" not in scols:
        conn.execute("ALTER TABLE sessions ADD COLUMN user_agent TEXT")


def init_user_db(uid):
    """初始化指定用户的业务库格式（分类 + 记录）。"""
    conn = get_conn(user_db_path(uid))
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


def init_db():
    """初始化账户库结构。"""
    _init_accounts()