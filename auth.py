# -*- coding: utf-8 -*-
"""用户账户认证：注册、登录、会话校验、退出、管理员初始化。

- 用户账号与密码哈希存于 data/accounts.db（UTF-8 编码，支持中文用户名）
- 内置管理员：id=0，账密均为 admin
- 业务数据按用户 id 分库：data/{id}.db
密码使用 PBKDF2-HMAC-SHA256 加盐存储（标准库实现，无第三方依赖）。
登录成功签发随机 token，存入 sessions 表用于后续请求鉴权。
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from db import get_accounts_conn, init_user_db

SESSION_TTL_HOURS = 24 * 7  # token 有效期：7 天


def _hash_password(password, salt=None):
    """返回 (salt, hash)，均存为十六进制字符串。"""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return salt, digest.hex()


def _user_from_row(row):
    return {"id": row["id"], "username": row["username"], "is_admin": (row["id"] == 0)}


def ensure_admin():
    """确保内置管理员（id=0，账密 admin/admin）存在。"""
    conn = get_accounts_conn()
    if not conn.execute("SELECT 1 FROM accounts WHERE id=0").fetchone():
        salt, h = _hash_password("admin")
        conn.execute(
            "INSERT INTO accounts (id, username, password_hash, salt, created_at) "
            "VALUES (0,'admin',?,?,?)",
            (h, salt, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    conn.close()
    init_user_db(0)  # 管理员的业务库（当前为空）


def register(username, password, confirm_password):
    """注册新用户。自动分配 id（从 1 向上，0 为管理员）。

    成功创建该用户独立的业务库（data/{id}.db）。
    """
    username = str(username or "").strip()
    if not (3 <= len(username) <= 20):
        return None, "用户名长度需为 3-20 个字符"
    if not password:
        return None, "密码不能为空"
    if password != confirm_password:
        return None, "两次输入的密码不一致"
    if len(password) < 6:
        return None, "密码长度至少 6 位"
    conn = get_accounts_conn()
    if conn.execute("SELECT 1 FROM accounts WHERE username=?", (username,)).fetchone():
        conn.close()
        return None, "用户名已存在：{}".format(username)
    m = conn.execute("SELECT COALESCE(MAX(id),0) AS m FROM accounts").fetchone()["m"]
    uid = max(1, m + 1)  # 0 被管理员占用，普通用户从 1 开始
    salt, h = _hash_password(password)
    conn.execute(
        "INSERT INTO accounts (id, username, password_hash, salt, created_at) VALUES (?,?,?,?,?)",
        (uid, username, h, salt, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    init_user_db(uid)  # 创建该用户独立的业务库
    return {"id": uid, "username": username, "is_admin": False}, None


def login(username, password):
    """校验用户名密码，成功签发 token。"""
    username = str(username or "").strip()
    conn = get_accounts_conn()
    row = conn.execute(
        "SELECT id, username, password_hash, salt FROM accounts WHERE username=?",
        (username,)).fetchone()
    if not row:
        conn.close()
        return None, "用户名或密码错误"
    _, h = _hash_password(password, row["salt"])
    if not hmac.compare_digest(h, row["password_hash"]):
        conn.close()
        return None, "用户名或密码错误"
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=SESSION_TTL_HOURS)
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
        (token, row["id"], expires.isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"token": token, "user": _user_from_row(row)}, None


def logout(token):
    """使 token 失效。"""
    token = str(token or "").strip()
    if not token:
        return
    conn = get_accounts_conn()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()


def check_auth(token):
    """校验 token。有效返回用户信息 {id, username, is_admin}，否则返回 None。"""
    token = str(token or "").strip()
    if not token:
        return None
    conn = get_accounts_conn()
    row = conn.execute(
        "SELECT a.id, a.username FROM sessions s "
        "JOIN accounts a ON a.id = s.user_id "
        "WHERE s.token=? AND s.expires_at>?",
        (token, datetime.now().isoformat(timespec="seconds"))).fetchone()
    conn.close()
    return _user_from_row(row) if row else None