# 个人记账（局域网 PWA）

一个部署在电脑/服务器上的个人记账软件。手机通过局域网访问页面即可录入消费、查看统计，数据统一保存在服务器端 SQLite 数据库中，实现手机录入、服务器存储与同步查看。

> 技术栈：Python 标准库（`http.server` + `sqlite3`，**零第三方依赖**）+ 原生 HTML/CSS/JS。

---

## 功能特性

- **账户体系**：用户自助注册 / 登录；会话管理（查看已登录设备，可强制下线，如手机丢失时踢掉手机）；登录界面回车适配（电脑端回车=登录，手机端回车=收起键盘）。
- **记一笔**：录入金额、选择一级/二级分类、填写备注与支付方式；负数为支出、正数为收入。
- **分类管理**：
  - 记一笔页内联"＋ 新增分类标签"即可新增一级/二级分类（二级需选择归属的一级），标识自动哈希生成，无需手动填写。
  - 右键（电脑）/ 长按（手机）分类标签弹出大叉：红色＝可删除（未被使用）、灰色＝已被记账使用、不可删除。
- **统计**：月收入 / 月支出 / 月结余；支出占比（按一级分类，带进度条）；支出明细（按二级分类）；每日趋势；恩格尔系数预留（`foodExpenseTotal` / `engelCoefficient`）。
- **完整报表**：统计页可展开当月每笔明细（日期、分类、备注、支付方式），支持切换月份。
- **数据备份（用户自助）**：普通用户在汉堡菜单中可一键导出本人全部记账为 Excel（一条记录一行），或导入 Excel 合并（按记录 ID 去重，分类缺失自动创建）。
- **管理后台**：管理员可新增账户、重置密码、禁用/启用/删除用户、按用户查看全部登录会话并强制下线、查看各用户记录数与数据库占用。

---

## 环境要求

- Python 3.7+（仅使用标准库，无需 `pip install`）
- 一台可常开的电脑 / 服务器（部署后手机经局域网访问）

---

## 快速开始（本地运行）

```bash
# 启动服务（监听 0.0.0.0:8080）
python script/server.py
```

启动后：

- 电脑浏览器访问：`http://127.0.0.1:8080/`
- 手机浏览器访问（需与电脑同一局域网）：`http://<电脑局域网IP>:8080/`

首次登录使用内置管理员：**账号 `admin` / 密码 `admin`**，登录后请尽快在「修改密码」中改掉。

---

## 服务器部署教程

### 1. 准备

- 安装 Python 3.7+，并确认 `python` 可用（Windows 下可在 `cmd` 中运行 `python --version` 验证）。
- 将整个项目目录复制/克隆到服务器，例如 `C:\SpendLog`（Windows）或 `/opt/spendlog`（Linux）。
- 目录无需预建 `data/`，首次启动会自动创建。

### 2. 启动服务

```bash
python script/server.py
```

看到输出 `SpendLog demo running at http://0.0.0.0:8080/` 即启动成功。

### 3. 防火墙放行端口

**Windows：**

```powershell
# 以管理员身份运行 PowerShell，放行 8080 端口（按需选择网络类型）
netsh advfirewall firewall add rule name="SpendLog" dir=in action=allow protocol=TCP localport=8080
```

**Linux（使用 firewalld）：**

```bash
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

**Linux（使用 ufw）：**

```bash
sudo ufw allow 8080/tcp
```

### 4. 访问与验证

- 本机访问 `http://127.0.0.1:8080/` 确认页面可打开。
- 查看服务器局域网 IP：Windows `ipconfig` 中找 IPv4；Linux `ip addr` 或 `hostname -I`。
- 手机连同一局域网，访问 `http://<服务器IP>:8080/`。
- 用 `admin` / `admin` 登录，修改初始密码；也可自行注册普通账户。

### 5. 后台常驻运行（可选，推荐）

避免关掉终端服务就停止：

**Windows（使用任务计划程序实现开机自启）：**

1. 新建启动脚本 `start.bat`（放在项目目录）：

```bat
@echo off
cd /d %~dp0
python script/server.py
```

2. 打开「任务计划程序」→「创建任务」：
   - 常规：勾选「不管用户是否登录都要运行」。
   - 触发器：新建 → 开始任务「启动时」。
   - 操作：新建 → 程序填 `start.bat` 的完整路径，起始于项目目录。
   - 条件：取消「只有在计算机使用交流电源时才启动此任务」。

**Linux（使用 systemd）：**

新建服务文件 `/etc/systemd/system/spendlog.service`：

```ini
[Unit]
Description=SpendLog accounting server
After=network.target

[Service]
WorkingDirectory=/opt/spendlog
ExecStart=/usr/bin/python3 /opt/spendlog/script/server.py
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now spendlog
# 查看状态 / 日志
systemctl status spendlog
journalctl -u spendlog -f
```

> 按实际路径调整 `WorkingDirectory` 与 `ExecStart`，并将 `User` 改为运行该服务的系统用户。

### 6. 数据与备份

- 所有数据存放在项目根目录 `data/` 下：`accounts.db`（账户与会话）、`{用户ID}.db`（每个用户的分类与记账）。
- 整体备份只需复制整个 `data/` 目录；恢复时停止服务、替换 `data/`、再启动即可。
- 普通用户也可在页内自助导出/导入本人记账 Excel，无需管理员介入。

---

## 目录结构

```
SpendLog/
├── script/               # 后端 Python 代码
│   ├── server.py         # 入口：HTTP 服务 + 路由（python script/server.py 启动）
│   ├── db.py             # SQLite 连接与建表（账户库 + 按用户分库）
│   ├── auth.py           # 注册/登录/会话/管理员初始化
│   ├── admin.py          # 用户管理/改密/会话管理
│   ├── categories.py     # 分类树/新增/删除/标识自动哈希
│   ├── records.py        # 记账
│   ├── statistics.py     # 统计与完整报表
│   ├── backup.py         # 导出 Excel / 导入合并
│   └── excel.py          # 纯标准库读写 .xlsx
├── static/               # 前端
│   ├── index.html        # 单页应用（登录/记一笔/统计/管理）
│   └── style.css         # 样式
└── data/                 # 运行时自动创建（.gitignore 已忽略）
    ├── accounts.db       # 账户与会话
    ├── 0.db              # 管理员业务库（空）
    └── {用户ID}.db       # 每个用户的分类 + 记账
```

---

## API 说明

所有接口返回 JSON，统一结构：`{ "code": 0, "message": "ok", "data": ... }`，出错时 `code=1`（HTTP 401/403 对应未登录/无权限）。除登录/注册外均需请求头 `Authorization: Bearer <token>`。

### 认证与会话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册。body：`{username, password, confirm_password}` |
| POST | `/api/auth/login` | 登录，返回 `{token, user}` |
| POST | `/api/auth/logout` | 退出（使当前 token 失效） |
| GET | `/api/auth/me` | 当前登录用户信息 |
| GET | `/api/sessions` | 当前用户的有效会话（含设备/登录时间/是否当前） |
| POST | `/api/sessions/revoke` | 强制下线指定会话。body：`{token}`（不能下线当前会话） |
| POST | `/api/auth/password` | 修改密码。body：`{old_password, new_password}` |

### 分类 / 记账

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/categories` | 分类树，含一级/二级及 `used` |
| POST | `/api/categories` | 新增分类。body：`{name, parent_code?}`（`code` 可选，缺省自动哈希生成） |
| DELETE | `/api/categories?code=xxx` | 删除分类（仅允许删"空"分类） |
| POST | `/api/records` | 新增记账。body：`{date, amount, category_code, note?, payment?}` |

### 统计 / 报表 / 备份

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/statistics?month=2026-09` | 月度统计（收入/支出/结余/占比/明细/每日趋势/恩格尔） |
| GET | `/api/report?month=2026-09` | 完整报表（逐笔明细，含备注与支付方式） |
| GET | `/api/export` | 下载当前用户全部记录为 `.xlsx` |
| POST | `/api/import` | 上传 `.xlsx` 导入合并（multipart 文件字段），按记录 ID 去重 |
| GET | `/api/backup/info` | 当前用户记录数与导出体积预估 |

### 管理（需管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users` | 用户列表（含记录数、数据库占用、最近登录） |
| POST | `/api/admin/users/create` | 新增账户。body：`{username, password}` |
| POST | `/api/admin/users/reset_password` | 重置密码。body：`{user_id, new_password}` |
| POST | `/api/admin/users/disable` / `.../enable` | 禁用 / 启用用户 |
| DELETE | `/api/admin/users?user_id=x` | 删除用户（含其业务库） |
| GET | `/api/admin/sessions` | 全部有效会话，按用户分组 |
| POST | `/api/admin/sessions/revoke` | 强制下线任意会话。body：`{token}`（不能下线自己当前会话） |

---

## 数据库结构

数据按用户分库：账户与会话存 `data/accounts.db`，每个用户的业务数据存 `data/{用户ID}.db`。

### `accounts`（账户库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，0 为内置管理员，普通用户从 1 起 |
| username | TEXT | 用户名（唯一） |
| password_hash / salt | TEXT | PBKDF2-HMAC-SHA256 加盐哈希 |
| disabled | INTEGER | 0 正常 / 1 禁用 |
| created_at / last_login | TEXT | 注册时间 / 最近登录 |

### `sessions`（会话）

| 字段 | 类型 | 说明 |
|------|------|------|
| token | TEXT | 登录令牌（主键） |
| user_id | INTEGER | 外键 → accounts.id |
| expires_at / created_at | TEXT | 过期时间 / 签发时间 |
| user_agent | TEXT | 登录设备标识 |

### `categories`（分类字典，业务库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键自增 |
| code | TEXT | 稳定唯一标识（新增分类时自动哈希生成） |
| name | TEXT | 分类名称 |
| parent_id | INTEGER | 外键指向父分类；一级为空 |
| type | TEXT | `'main'` 一级 / `'sub'` 二级 |

### `records`（记账记录，业务库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT | UUID 主键 |
| date | TEXT | 日期 `YYYY-MM-DD` |
| amount | REAL | 金额，负数支出 / 正数收入 |
| category_id | INTEGER | 外键 → categories.id |
| note / payment | TEXT | 备注 / 支付方式 |
| created_at | TEXT | 创建时间 |

> 记录只通过 `category_id` 关联分类，分类层级调整（如子类升级为一级）不需改动 `records`。
> `init_db()` 仅负责建表，"分类字典"完全由用户创建，后端不硬编码。

---

## 说明与后续方向

- 单页应用；如需离线可用/一键加入手机主屏，可补充 PWA（`manifest` + `service worker`）。
- 面向局域网部署，适合个人家庭使用；如需公网访问需自行加固网络与鉴权（建议套用 HTTPS 反向代理）。
