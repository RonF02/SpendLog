<div align="center">

# 📒 SpendLog · 个人记账

**Lightweight self-hosted personal expense tracker — 部署在电脑/服务器上，手机经局域网即记账。**

`Python 标准库` · `SQLite` · `原生 HTML/CSS/JS` · `PWA`（零第三方依赖）

</div>

<p align="center">
  <!-- 徽章区：此处为模板占位，按需替换为真实仓库/CI 链接 -->
  <img alt="Python" src="https://img.shields.io/badge/Python-3.7%2B-3f7cff?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-3da639">
  <img alt="Build" src="https://img.shields.io/badge/build-passing-brightgreen" title="本地验证通过">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey">
  <a href="https://github.com/RonF02/SpendLog"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-RonF02%2FSpendLog-181717?logo=github&logoColor=white"></a>
</p>

---

## 目录

- [项目背景](#项目背景)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [使用示例](#使用示例)
- [项目结构](#项目结构)
- [数据与备份](#数据与备份)
- [API 一览](#api-一览)
- [贡献指南](#贡献指南-)
- [许可证](#许可证-)
- [致谢与联系](#致谢与联系)

---

## 项目背景

日常记账通常依赖记账 App，数据存在云端、受制于厂商，难以按自己的思路分类统计和导出存档。
SpendLog 要解决的是**"数据自主可控"**：把记账软件装在自己的电脑/服务器上，手机连上同一个局域网即可随时录入与查看，所有数据统一保存在独立的 SQLite 数据库中，天然支持多设备同步记账与本地备份。

项目坚持"零第三方依赖、单文件可迁移"的理念：后端仅用 Python 标准库（HTTP + SQLite），前端为原生单页应用，拷贝即部署。

---

## 功能特性

- **账户与会话体系**
  用户自助注册/登录，多设备会话可视化管理，可一键强制下线任一设备（如手机丢失时）；登录界面适配回车交互（电脑端回车=登录、手机端回车=收起键盘）。

- **一目了然的记账**
  记一笔页录入金额（负数为支出、正数为收入）、日期、支付方式与备注，选择一级/二级分类即可保存，全程无需跳出页面。

- **灵活的二级分类管理**
  页面内联新增一级/二级分类，标识自动哈希生成；电脑右键 / 手机长按标签弹出删除大叉——**红色=可删（未被使用）**、**灰色=已被使用不可删**。

- **🧲 分类标签拖拽排序**
  一级、二级分类标签均可按住拖动调整顺序，松手即时保存，顺序随随机存取（主/二级分别保存）。

- **📊 月度统计与完整报表**
  月收入/支出/结余、按一级分类的支出占比（带进度条）、按二级分类的支出明细、每日趋势，恩格尔系数字段预留；完整报表逐笔列出日期、分类、备注与支付方式，并支持**按主分类筛选**与切换月份。

- **🗑️ 删除全部数据（二次确认）**
  普通用户在汉堡菜单数据管理区可一键清空本人全部记录与分类，需连续两次弹窗确认，避免误删；删除前建议先导出备份。

- **数据备份与导入**
  一键导出本人全部记账为 `.xlsx`，也可导入 Excel 合并（按记录 ID 去重，缺失分类自动创建）。

- **管理后台**
  管理员可新增账户、重置/修改密码、禁用/启用/删除用户、按用户查看全部会话并强制下线、查看各用户记录数与数据库占用。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.7+（标准库 `http.server` + `sqlite3`，**零第三方依赖**） |
| 数据库 | SQLite：`data/accounts.db`（账户/会话）+ `data/{用户ID}.db`（每个人的分类与记账） |
| 前端 | 原生 HTML / CSS / JavaScript 单页应用，PWA 友好，适配电脑与手机 |
| 安全 | PBKDF2-HMAC-SHA256 加盐哈希存储密码，token 会话鉴权 |

---

## 快速开始

> 无需 `pip install`，仅需安装 Python 3.7+；`data/` 目录首次启动会自动创建。

### ① 安装

```bash
# 克隆 / 复制项目目录后，确认 Python 可用
python --version     # 要求 3.7+
```

### ② 配置

无需额外配置。默认监听 `0.0.0.0:8080`；如需改端口，用 `--port` 参数，并按端口放行防火墙：

```powershell
# Windows（管理员 PowerShell），以 8080 为例
netsh advfirewall firewall add rule name="SpendLog" dir=in action=allow protocol=TCP localport=8080
```

```bash
# Linux（firewalld）
sudo firewall-cmd --permanent --add-port=8080/tcp && sudo firewall-cmd --reload
```

### ③ 运行

```bash
python script/server.py            # 默认 8080
python script/server.py --port 9000   # 自定义端口
```

启动后：

- 电脑访问 `http://127.0.0.1:<端口>/`
- 手机连同一局域网，访问 `http://<服务器局域网IP>:<端口>/`
- 首次登录内置管理员 **`admin` / `admin`**，登录后请尽快修改密码

> 局域网 IP 查看：Windows `ipconfig`（IPv4），Linux `ip addr` 或 `hostname -I`。

### ④ 测试

项目为自托管工具，未内置自动化测试套件。建议用下面[使用示例](#使用示例)中的 `curl` 做一次冒烟测试（登录 → 新增记录 → 查统计），确认接口 200/`code=0` 即可。

---

## 使用示例

> 所有接口均返回 JSON：`{ "code", "message", "data" }`，出错 `code=1`；除登录/注册外需带 `Authorization: Bearer <token>`。

**登录并获取 token：**

```bash
curl -s -X POST http://127.0.0.1:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

**新增一笔支出（分类 code 用自己创建的标识）：**

```bash
curl -s -X POST http://127.0.0.1:8080/api/records \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"date":"2026-09-02","amount":-45.5,"category_code":"food_dinner","note":"晚餐","payment":"微信"}'
```

**查询本月完整报表（仅支出占比主分类筛选依赖该接口返回的 `code`）：**

```bash
curl -s "http://127.0.0.1:8080/api/report?month=2026-09" -H "Authorization: Bearer <token>"
```

**调整一级分类顺序：**

```bash
curl -s -X POST http://127.0.0.1:8080/api/categories/reorder \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"codes":["food","transport","income","other"]}'
```

**清空本人全部数据（前端会二次确认，接口层面直接生效）：**

```bash
curl -s -X DELETE http://127.0.0.1:8080/api/data -H "Authorization: Bearer <token>"
```

---

## 项目结构

```
SpendLog/
├── script/                  # 后端 Python 代码
│   ├── server.py            # 入口：HTTP 服务与路由（python script/server.py 启动）
│   ├── db.py                # SQLite 连接、建表与老库迁移
│   ├── auth.py              # 注册/登录/会话/管理员初始化
│   ├── admin.py             # 用户管理/改密/管理员会话管理
│   ├── categories.py        # 分类树/增删/标识哈希/拖拽排序
│   ├── records.py           # 记账、清空全部数据
│   ├── statistics.py        # 月度统计与完整报表
│   ├── backup.py            # 导出/导入 Excel（含备份信息）
│   ├── import_xlsx.py       # Excel 解析与合并
│   └── excel.py             # 纯标准库读写 .xlsx
├── static/                  # 前端
│   ├── index.html           # 单页应用（登录/记一笔/统计/管理/抽屉）
│   └── style.css            # 样式
├── data/                    # 运行时自动创建（.gitignore 已忽略）
│   ├── accounts.db          # 账户与会话
│   ├── 0.db                 # 管理员业务库（空）
│   └── {用户ID}.db          # 每个用户的分类 + 记账
└── README.md
```

---

## 数据与备份

- 所有数据集中在根目录 `data/`：`accounts.db`（账户与会话）、`{用户ID}.db`（每人分类与记账）。
- 整体备份：直接复制 `data/` 目录；恢复时先停服务、替换 `data/`、再启动。
- 普通用户也可页内自助导入/导出本人 Excel，无需管理员。

**数据库要点：**

- `categories`：`id / code(稳定唯一) / name / parent_id / type('main'|'sub') / sort_order`。
- `records`：`id(UUID) / date / amount(负支出正收入) / category_id / note / payment / created_at`。
- 记录仅通过 `category_id` 关联分类，改分类层级无需改动 `records`；`init_db()` 只负责建表/迁移，分类字典完全由用户维护。

---

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` `/login` `/logout` | 注册 / 登录 / 退出 |
| GET | `/api/auth/me` | 当前用户信息 |
| GET / POST | `/api/sessions` `/api/sessions/revoke` | 会话列表 / 强制下线 |
| POST | `/api/auth/password` | 修改密码 |
| GET / POST / DELETE | `/api/categories` | 分类树 / 新增 / 删除 |
| POST | `/api/categories/reorder` | 分类拖拽排序 |
| POST | `/api/records` | 新增记账 |
| GET | `/api/statistics?month=…` | 月度统计 |
| GET | `/api/report?month=…` | 完整报表（含主分类 `code` 供筛选） |
| GET / POST / GET | `/api/export` `/api/import` `/api/backup/info` | 备份相关 |
| DELETE | `/api/data` | 清空本人全部数据 |
| `admin/*` 系列 | `/api/admin/users…` `/api/admin/sessions` | 用户与会话管理 |

---

## 贡献指南 🙏

欢迎提交改进与反馈：

- **提 Issue**：遇到 Bug 或想提新功能，请到 [Issues](https://github.com/RonF02/SpendLog/issues) 描述复现步骤 / 具体需求。
- **社区约定**：提交前请自查——后端改动可通过 `python script/server.py` 冒烟验证；前端改动在 `static/index.html` / `style.css`，注意页面同时服务电脑与手机（右键=删除、长按=删除）。提交信息建议遵循约定式提交（`feat:` / `fix:` / `style:` …）。
- **Pull Request**：Fork → 新建分支 → 提交改动 → 开 PR，描述改动目的与验证方式，维护者会及时 review 合并。

## 许可证 📄

本项目采用 **MIT License**，详见 [LICENSE](LICENSE)。

## 致谢与联系

- 感谢所有为本项目提供反馈与改进建议的用户。
- 项目面向局域网个人/家庭使用，如需公网访问请自行加固鉴权并建议搭配 HTTPS 反向代理。
- 更多讨论或功能建议，欢迎到 [Issues](https://github.com/RonF02/SpendLog/issues) 反馈，或访问仓库主页：[RonF02/SpendLog](https://github.com/RonF02/SpendLog)。