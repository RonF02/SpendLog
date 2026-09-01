# 个人记账（局域网 PWA Demo）

一个部署在电脑上的个人记账软件。手机通过局域网访问页面即可录入消费、查看统计，数据统一保存在电脑的 SQLite 数据库中，实现手机录入、电脑存储与同步查看。

> 技术栈：Python 标准库（`http.server` + `sqlite3`，零第三方依赖）+ 原生 HTML/CSS/JS。

---

## 快速开始

```bash
# 启动服务（监听 0.0.0.0:8080）
python server.py
```

启动后：

- 电脑浏览器访问：`http://127.0.0.1:8080/`
- 手机浏览器访问（需与电脑同一局域网）：`http://<电脑局域网IP>:8080/`

> Windows 查看局域网 IP：`ipconfig`，找 IPv4 地址。

---

## 目录结构

```
SpendLog/
├── server.py            # 后端：HTTP 服务 + SQLite 存储 + API
├── import_xlsx.py       # （可选）工具：从 收支明晰.xlsx 批量导入历史数据
├── data/
│   ├── accounting.db    # SQLite 数据库（categories / records）
│   └── 收支明晰.xlsx     # 原始账本（导入来源）
└── static/
    ├── index.html       # 移动端单页（记一笔 / 统计）
    └── style.css        # 样式
```

---

## 功能特性

- **记一笔**：录入金额、选择一级/二级分类、填写备注与支付方式；负数为支出、正数为收入。
- **分类管理**：
  - 记一笔页内联"＋ 新增分类标签"即可新增一级/二级分类（二级需选择归属的一级）。
  - 右键（电脑）/ 长按（手机）分类标签弹出大叉：
    - 红色＝该分类为空、可删除；
    - 灰色＝已被记账使用、不可删除。
- **统计**：
  - 月收入 / 月支出 / 月结余；
  - 支出占比（按一级分类，带进度条）；
  - 支出明细（按二级分类）；
  - **完整报表（含备注）**：可展开查看当月每笔明细（日期、分类、备注、支付方式），支持切换月份。
- **恩格尔系数预留**：接口返回 `foodExpenseTotal` 与 `engelCoefficient`，按"餐饮支出 ÷ 总收入"预留计算能力。

---

## API 说明

所有接口返回 JSON，统一结构：`{ "code": 0, "message": "ok", "data": ... }`，出错时 `code=1`。

### 分类

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/categories` | 分类树，含一级/二级及 `used`（是否被记账使用） |
| POST | `/api/categories` | 新增分类。body：`{name, code, parent_code?}`，`parent_code` 为空建一级，否则建二级 |
| DELETE | `/api/categories?code=xxx` | 删除分类（仅允许删"空"分类，否则返回错误） |

### 记账

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/records` | 新增记账。body：`{date, amount, category_code, note?, payment?}` |

### 统计 / 报表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/statistics?month=2026-09` | 月度统计（收入/支出/结余/占比/明细/每日趋势/恩格尔） |
| GET | `/api/report?month=2026-09` | 完整报表（逐笔明细，含备注与支付方式） |

---

## 数据库结构

### `categories` 分类字典

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键自增 |
| code | TEXT | 稳定英文标识（唯一），新增分类时手动输入 |
| name | TEXT | 分类名称 |
| parent_id | INTEGER | 外键，指向父分类 id；一级为空 |
| type | TEXT | `'main'` 一级 / `'sub'` 二级 |

### `records` 记账记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT | UUID 主键 |
| date | TEXT | 日期 `YYYY-MM-DD` |
| amount | REAL | 金额，负数支出 / 正数收入 |
| category_id | INTEGER | 外键 → categories.id |
| note | TEXT | 备注 |
| payment | TEXT | 支付方式 |
| created_at | TEXT | 创建时间 |

> 记录只通过 `category_id` 关联分类，因此分类层级调整（如把子类升级为一级）不需要改动 `records` 数据。

> `init_db()` 仅负责建表，"分类字典"完全由用户通过接口自行创建，后端不硬编码任何分类。

---

## 历史数据导入（可选）

```bash
python import_xlsx.py
```

将 `data/收支明晰.xlsx` 中各月份 sheet 的数据按分类映射写入 `accounting.db`。脚本幂等，重复运行不会产生重复数据。

---

## 说明与后续方向

- 当前为单页应用，若需离线可用/一键加入手机主屏，可补充 PWA（`manifest` + `service worker`）。
- 部署在局域网内，适合个人家庭使用；如需公网访问需自行加固网络与鉴权。