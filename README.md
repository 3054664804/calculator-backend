# calculator-backend · 前后端分离计算器（后端）

> 软件工程课程作业 —— 前后端分离计算器系统的**后端仓库**。
> 所有表达式计算、历史记录持久化都在这里完成；前端仓库见
> [calculator-frontend](https://github.com/3054664804/calculator-frontend)。

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-68%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## 一、这个后端做了什么

| 作业硬性规则 | 本仓库的实现 |
| --- | --- |
| 前后端完全分离，计算逻辑全在后端 | 只有本仓库有计算能力：`evaluator.py` 是唯一的求值入口；前端只发字符串、只显示字符串 |
| 严禁 `eval`/`exec` 执行用户输入 | 使用安全解析库 **asteval**，并叠加字符白名单、符号表清空、复杂度限制三层加固；`tests/test_evaluator.py::test_no_eval_or_exec_in_source` 会扫描源码自证没有 `eval(`/`exec(` |
| 数据库持久化计算历史 | SQLite（标准库 `sqlite3`），表 `calculation_history` 含 `id / expression / result / created_at` |
| 3 个必需 API | `POST /api/calculate`、`GET /api/history`、`DELETE /api/history/{id}`，另有 2 个扩展接口 |
| 基础四则 / 复合 / 优先级 / 括号 / 小数 / 一元正负 | 全部支持并有单元测试覆盖（如 `3*(2+5)-4/2=19`、`3*-2=-6`、`- 5=-5`） |
| 异常处理：除零、非法表达式 | 统一错误码 + 中文提示，失败的计算**不会**写入历史表 |

## 二、技术栈

| 层次 | 选型 | 说明 |
| --- | --- | --- |
| Web 框架 | **FastAPI 0.115** | 自带 OpenAPI，`/docs` 可直接给助教演示接口 |
| ASGI 服务器 | **Uvicorn** | 支持 `--host 0.0.0.0 --port $PORT`，云平台通用 |
| 表达式求值 | **asteval 1.0** | 纯 Python 的 AST 安全求值库，不使用 `eval`/`exec` |
| 数据校验 | **Pydantic v2** | 请求/响应模型即接口文档 |
| 数据库 | **SQLite 3（标准库 sqlite3）** | 零配置、单文件；开启 WAL 提升并发读写 |
| 测试 | **pytest + httpx（TestClient）** | 单元测试 + 接口集成测试，共 38 条用例 |

## 三、目录结构

```
calculator-backend/
├── main.py                 # FastAPI 入口：路由、CORS、统一异常处理
├── evaluator.py            # ★ 安全表达式求值引擎（本项目核心）
├── db.py                   # SQLite 持久化层（仓储模式）
├── schemas.py              # Pydantic 请求/响应模型
├── errors.py               # 业务异常体系（错误码 + HTTP 状态码）
├── config.py               # 环境变量配置 + 日志
├── tests/
│   ├── conftest.py         # 夹具：每个用例一个独立的临时数据库文件
│   ├── test_evaluator.py   # 求值引擎单元测试（51 条）
│   └── test_api.py         # 接口集成测试 + 持久化验证（17 条）
├── requirements.txt        # 运行时依赖
├── requirements-dev.txt    # 开发/测试依赖
├── pyproject.toml          # ruff / black 规则（对应 codestyle.md）
├── pytest.ini              # 测试配置
├── render.yaml             # Render 一键部署蓝图
├── Dockerfile              # 容器化部署
├── docker-compose.yml      # 本地一键起服务
├── .env.example            # 环境变量样例
├── README.md               # 本文档
└── codestyle.md            # 代码规范文档（作业要求）
```

## 四、快速开始

### 4.1 环境要求

* Python **3.11+**（开发环境为 3.12.5）
* 无需安装数据库，SQLite 由 Python 标准库自带

### 4.2 启动服务

```bash
# 1) 进入后端目录
cd calculator-backend

# 2) 创建并激活虚拟环境（Windows / macOS 二选一）
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3) 安装依赖
pip install -r requirements.txt

# 4) 启动（开发热重载）
uvicorn main:app --reload --port 8000
#   等价写法：python main.py
```

启动成功后：

* 服务地址：<http://127.0.0.1:8000>
* 交互式接口文档（Swagger）：<http://127.0.0.1:8000/docs>
* 健康检查：<http://127.0.0.1:8000/api/health>

### 4.3 30 秒自测

```bash
# 计算 3*(2+5)-4/2
curl -X POST http://127.0.0.1:8000/api/calculate \
     -H "Content-Type: application/json" \
     -d "{\"expression\":\"3*(2+5)-4/2\"}"
# => {"success":true,"data":{"id":1,"expression":"3*(2+5)-4/2","result":"19",
#     "created_at":"2026-01-01T12:00:00+00:00","elapsed_ms":0.42}}

# 查询历史
curl http://127.0.0.1:8000/api/history

# 删除 id=1
curl -X DELETE http://127.0.0.1:8000/api/history/1
```

### 4.4 跑测试

```bash
pip install -r requirements-dev.txt
pytest -v
```

预期结果：**68 passed**（51 条求值引擎测试 + 17 条接口测试），耗时约 1.5 秒。

> 小提示：测试夹具刻意不使用 `tmp_path`（它用 `mode=0o700` 建目录，
> 在部分 Windows 受限安全环境下连创建者都无法读取，会直接抛 `WinError 5`），
> 而是用 uuid 在 `tests/` 下命名临时数据库文件，跑完自动删除。详见 `tests/conftest.py` 注释。

## 五、环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CALC_DB_PATH` | `./data/calculator.db` | SQLite 文件路径，目录不存在会自动创建 |
| `CALC_CORS_ORIGINS` | `*` | 允许的前端来源，多个用英文逗号分隔；**生产环境建议写死前端域名** |
| `CALC_APP_NAME` | `计算器后端 API` | Swagger 标题 |
| `CALC_LOG_LEVEL` | `INFO` | 日志级别 |
| `CALC_RELOAD` | `0` | 用 `python main.py` 启动时是否热重载 |
| `PORT` | `8000` | 云平台注入的端口，`python main.py` 会读取它 |

## 六、API 设计

统一响应结构（前端只认这一套）：

```jsonc
// 成功
{ "success": true, "total": 12, "data": { /* ... */ } }
// 失败
{ "success": false, "error": { "code": "DIVISION_BY_ZERO", "message": "除数不能为 0" } }
```

### 6.1 `POST /api/calculate` —— 计算并写库

请求体：

```json
{ "expression": "3*(2+5)-4/2" }
```

成功响应 `200`：

```json
{
  "success": true,
  "data": {
    "id": 7,
    "expression": "3*(2+5)-4/2",
    "result": "19",
    "created_at": "2026-01-01T12:00:00+00:00",
    "elapsed_ms": 0.418
  }
}
```

失败响应 `400`：

```json
{ "success": false, "error": { "code": "DIVISION_BY_ZERO", "message": "除数不能为 0" } }
```

### 6.2 `GET /api/history` —— 查询历史

查询参数（全部可选）：`keyword`（按表达式/结果模糊搜索）、`limit`、`offset`。

```json
{
  "success": true,
  "total": 2,
  "data": [
    { "id": 2, "expression": "2*3", "result": "6", "created_at": "2026-01-01T12:01:00+00:00" },
    { "id": 1, "expression": "1+1", "result": "2", "created_at": "2026-01-01T12:00:00+00:00" }
  ]
}
```

> 按 `id` 倒序返回，最新记录在最前面。

### 6.3 `DELETE /api/history/{id}` —— 删除单条

成功 `200`：

```json
{ "success": true, "data": { "deleted_id": 2, "deleted": true, "expression": "2*3", "result": "6" } }
```

记录不存在时返回 `404`（而不是静默成功的 `200`，方便前端给出准确提示）：

```json
{ "success": false, "error": { "code": "RECORD_NOT_FOUND", "message": "历史记录 2 不存在或已被删除" } }
```

### 6.4 扩展接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `DELETE` | `/api/history` | 清空全部历史（返回 `deleted_count`） |
| `GET` | `/api/health` | 健康检查，前端用它显示"后端在线/离线" |
| `GET` | `/docs` `GET /redoc` | 自动生成的接口文档 |
| `GET` | `/` | 服务自描述信息 |

### 6.5 错误码总表

| HTTP | code | 触发场景 | 用户看到的提示 |
| --- | --- | --- | --- |
| 400 | `EMPTY_EXPRESSION` | 表达式为空或全是空格 | 表达式不能为空 |
| 400 | `EXPRESSION_TOO_LONG` | 超过 200 个字符 | 表达式过长，请缩短后再试 |
| 400 | `ILLEGAL_CHARACTER` | 含字母、引号、下划线等 | 表达式包含非法字符：… |
| 400 | `UNBALANCED_PARENTHESES` | 左右括号数量不等 | 括号不匹配：左括号 1 个，右括号 0 个 |
| 400 | `SYNTAX_ERROR` | `3+`、`1+*2`、`*5`、`3..5` | 表达式语法错误，请检查运算符是否连续… |
| 400 | `DIVISION_BY_ZERO` | `1/0`、`5%0` | 除数不能为 0 |
| 400 | `EXPRESSION_TOO_COMPLEX` | `9**9**9`、`2**100000` | 为保证服务稳定，一个表达式最多支持一次幂运算 |
| 400 | `RESULT_OVERFLOW` | 结果超出可表示范围（inf） | 计算结果超出可表示范围 |
| 400 | `UNSUPPORTED_OPERATION` | 结果是复数/元组等非实数 | 暂不支持复数运算 |
| 404 | `RECORD_NOT_FOUND` | 删除不存在的 id | 历史记录 N 不存在或已被删除 |
| 422 | `VALIDATION_ERROR` | 请求体字段类型不对 | 请求参数不合法：字段 expression … |
| 500 | `DATABASE_ERROR` / `INTERNAL_ERROR` | 数据库/服务端异常 | 服务器内部错误，请稍后重试 |

## 七、数据库设计

```sql
CREATE TABLE IF NOT EXISTS calculation_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    expression TEXT    NOT NULL,   -- 用户输入的**原始**表达式（含 × ÷ 等符号）
    result     TEXT    NOT NULL,   -- 后端计算出的结果（字符串保存）
    created_at TEXT    NOT NULL    -- ISO 8601（UTC），如 2026-01-01T12:00:00+00:00
);

CREATE INDEX IF NOT EXISTS idx_history_created_at ON calculation_history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_expression ON calculation_history (expression);
```

三个设计决策：

1. **`result` 用 TEXT 而不是 REAL**：`10/3` 用浮点存会再次引入精度问题；大整数（如 `2**100`）超出 JS `Number.MAX_SAFE_INTEGER` 会失真，字符串可以原样展示。
2. **`created_at` 用 ISO 8601 带时区**：前端 `new Date(created_at)` 直接解析成本地时间，不需要任何时区换算逻辑。
3. **每次操作新建连接、用完即关**：FastAPI 同步路由跑在线程池里，`sqlite3` 连接不能跨线程复用；SQLite 建连接开销极小，配 WAL 模式足以支撑课程演示量级。

## 八、安全设计：为什么不用 eval，以及怎么加固

```
用户输入 ──▶ ①字符白名单 ──▶ ②长度/复杂度限制 ──▶ ③asteval(空符号表) ──▶ ④异常翻译 ──▶ 结果
                 │                   │                    │                  │
            非法字符直接拒绝     9**9**9 直接拒绝    没有任何可调用名字    统一错误码给前端
```

① `re.fullmatch(r"[0-9+\-*/().\s%^]+", expr)` —— 只允许数字、小数点、四则运算符、括号、`%`、`^` 和空格。`__import__('os')`、`1+2; rm -rf /` 在这一步就被拒绝。
② 长度 ≤ 200；幂运算最多一次且指数 ≤ 1000，杜绝 `9**9**9` 这类"几个字符打满 CPU"的表达式。
③ `Interpreter(minimal=True)` 之后把 `symtable` 清空（`len(symtable) == 0`），即使白名单被绕过，表达式里也没有任何可调用的名字。
④ 把 `ZeroDivisionError / SyntaxError / NotImplementedError / OverflowError` 等翻译成有错误码的业务异常，绝不把堆栈暴露给前端。

另外两个细节：

* **`^` 会被归一化成 `**`**：Python 的 `^` 是按位异或，`2^10` 会得到 `8`；计算器用户习惯用 `^` 表示乘方，所以在归一化阶段替换，避免"结果对不上但不报错"的诡异 bug（这是开发中真实踩到的坑）。
* **前端送来的 `×` `÷` 全角符号先翻译再校验**：数据库里保存的仍是用户原文，展示时更亲切。

## 九、部署

### 9.1 Render（推荐，本作业采用）

1. 把本仓库推到 GitHub（`main` 分支）。
2. 登录 [Render](https://render.com) → **New → Blueprint** → 选择本仓库 → **Apply**
   （仓库内的 `render.yaml` 已写好 build/start 命令、健康检查路径和 Python 版本）。
3. 部署完成后得到形如 `https://calculator-backend-xxxx.onrender.com` 的地址。
4. 验证：浏览器打开 `https://<你的域名>/docs`，能看到 Swagger 即成功。

> ⚠️ **免费实例的两个注意事项**
> 1. 15 分钟无请求会休眠，下次访问需要约 30–60 秒冷启动（助教测试时请先打开一次唤醒）。
> 2. 免费实例没有持久磁盘，**重新部署**后 SQLite 文件会重置。作业验收期间不要重新部署即可；
>    如需长期保留，升级付费实例并启用 `render.yaml` 里注释的 `disk` 配置，把 `CALC_DB_PATH` 指向挂载目录。

部署后把前端域名写进 CORS 白名单（更安全）：

```
CALC_CORS_ORIGINS = https://calculator-frontend-xxxx.vercel.app
```

### 9.2 Docker（本地一键演示）

```bash
docker compose up --build      # 启动后访问 http://127.0.0.1:8000/docs
docker compose down -v         # 停止并清除数据卷
```

### 9.3 其他平台

| 平台 | build | start |
| --- | --- | --- |
| Railway / Fly.io | `pip install -r requirements.txt` | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| 自建服务器（systemd） | `pip install -r requirements.txt` | 同上，配合 Nginx 反向代理与 `CALC_DB_PATH=/var/lib/calculator/calculator.db` |

## 十、常见问题

**Q1：前端报"无法连接后端服务"？**
A：① 后端是否启动（访问 `/api/health`）；② Render 免费实例是否在冷启动，等 30 秒；③ 前端 `VITE_API_BASE_URL` 是否填了后端公网地址；④ 后端 `CALC_CORS_ORIGINS` 是否包含前端域名。

**Q2：历史记录刷新后就没了？**
A：不会。历史保存在后端 SQLite 文件里。若你在 Render 上重建了服务，免费实例的数据会随容器重置（见 9.1 的说明）。

**Q3：能不能算 `sin(30)`？**
A：不能，本项目按作业要求只支持实数四则运算（含括号、小数、一元正负），并额外支持 `%` 与幂运算。函数名会被字符白名单拦截。

**Q4：为什么 `2**3**2` 被拒绝？**
A：为保证服务稳定，一个表达式最多允许一次幂运算。这是刻意的安全限制，见第八节。

## 十一、许可

MIT License，仅供课程学习使用。
