# calculator-backend 代码规范

> 本文档描述**本仓库实际执行的**编码约定。所有示例均取自仓库现有代码（`main.py` / `evaluator.py` /
> `db.py` / `schemas.py` / `errors.py` / `config.py` / `tests/`），不是泛泛的通用建议。
> 规范的目标有三个：**统一的自动化格式**、**可讲清楚的架构边界**（答辩时能逐行解释）、
> **安全与异常处理零妥协**（计算逻辑全在后端，绝不执行用户输入的代码）。

---

## 一、适用范围与工具链

### 1.1 适用范围

适用于本仓库所有 Python 源码与测试：`main.py`、`evaluator.py`、`db.py`、`schemas.py`、`errors.py`、
`config.py`、`tests/**`。`data/`（运行时 SQLite 文件目录）不纳入检查。

### 1.2 工具链：ruff + black

格式与静态检查统一由 **ruff**（lint + format）与 **black**（兜底格式化）承担，规则集中配置在
`pyproject.toml`，不在代码里用注释零散地压制规则。

```toml
[tool.ruff]
# 与 codestyle.md 中约定的规则保持一致
line-length = 110
target-version = "py311"
exclude = [".venv", "venv", "__pycache__", "data"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle error
    "W",   # pycodestyle warning
    "F",   # pyflakes
    "I",   # isort（import 排序）
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
    "RET", # flake8-return
    "ARG", # 未使用的参数
    "PTH", # 用 pathlib 替代 os.path
    "RUF", # ruff 自带规则
]
ignore = [
    "B008", # FastAPI 的 Depends()/Query() 必须写在默认值位置，属框架约定
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ARG001", "ARG002"] # 测试夹具参数多为占位

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.black]
line-length = 110
target-version = ["py311"]
skip-string-normalization = false
```

| 配置项 | 取值 | 理由 |
| --- | --- | --- |
| `line-length` | `110` | 与 black 保持一致；110 列能容纳 `main.py` 里较长的路由装饰器与带中文描述的 `Field(...)`，不必为凑 88 列把签名拆得难读 |
| `target-version` | `py311` | README 声明 Python 3.11+；代码里用的是 `str \| None`、`list[dict[str, Any]]` 这类 3.10+ 语法 |
| 规则集 `E/W/F` | pycodestyle + pyflakes | 基础风格与未使用变量/导入 |
| `I` | isort | import 分组固定为「标准库 → 第三方 → 本项目」，`from __future__ import annotations` 永远在最前 |
| `N` | pep8-naming | 保证下文第二节的命名约定可自动校验 |
| `UP` | pyupgrade | 强制使用现代写法（本仓库已统一用 `X \| None` 而非 `Optional[X]`） |
| `B` | flake8-bugbear | 捕获可变默认参数、裸 `except` 等真实缺陷 |
| `C4` | flake8-comprehensions | 列表/字典推导式写法统一 |
| `SIM` | flake8-simplify | 去掉冗余分支与嵌套 |
| `RET` | flake8-return | 返回值写法一致（`evaluator.py` 里大量提前返回） |
| `ARG` | 未使用参数 | 只对 `tests/*` 放开 `ARG001/ARG002`，夹具签名里的占位参数可保留 |
| `PTH` | pathlib | 全部路径操作使用 `pathlib.Path`（如 `db.py` 的 `Path(__file__).resolve().parent`） |
| `RUF` | ruff 自带规则 | 额外的最佳实践检查 |
| `ignore B008` | **仅这一条** | FastAPI 的 `Query(...)` / `Path(...)` 按框架约定必须写在函数默认值位置，`B008` 会把它误判为“函数调用作为默认值”。这是框架要求而非代码异味，因此全局忽略；**不要**为了绕开它改用其他写法 |
| `per-file-ignores` | `tests/* = [ARG001, ARG002]` | 测试函数的夹具参数（如 `client`、`evaluator`）常不被直接引用，属正常现象 |

### 1.3 命令

```bash
# 静态检查（不修改文件）
ruff check .

# 自动修复可修复项（import 排序、简化写法等）
ruff check . --fix

# 格式化（等价的 black 用法见下）
ruff format .

# black 兜底格式化 + 检查
black .
black --check .
```

**提交前必须保证 `ruff check .` 与 `black --check .` 双双通过**，不允许把 lint 错误留到 CI 之外。
确需压制单行规则时，使用带原因的行内注释，例如 `evaluator.py` 中的：

```python
except Exception as exc:  # noqa: BLE001 - 统一翻译成业务异常
```

```python
if __name__ == "__main__":  # pragma: no cover - 本地调试入口
```

---

## 二、命名规范

| 对象 | 约定 | 仓库中的实际例子 |
| --- | --- | --- |
| 模块 / 文件 | 全小写 + 下划线，短而直白 | `main.py`、`evaluator.py`、`db.py`、`schemas.py`、`errors.py`、`config.py` |
| 类 | PascalCase | `SafeEvaluator`、`HistoryRepository`、`Settings`、`CalculateRequest`、`HistoryListResponse` |
| 函数 / 方法 | snake_case，动词开头 | `evaluate`、`normalize`、`validate`、`format_result`、`list_all`、`init_schema`、`configure_logging` |
| 变量 / 参数 | snake_case，名称即含义，不用缩写 | `raw_expression`、`elapsed_ms`、`normalized_keyword`、`db_path`、`record_id` |
| 常量 | UPPER_SNAKE_CASE，模块级 | `MAX_EXPRESSION_LENGTH`、`MAX_POWER_EXPONENT`、`ALLOWED_CHARACTERS`、`DEFAULT_DB_PATH`、`SCHEMA_STATEMENTS` |
| 私有成员 | 单下划线前缀 | 函数 `_now_iso`、`_row_to_dict`；方法 `_connect`、`_connection`、`_run`、`_translate_error`、`_format_float`、`_harden_symbol_table`；属性 `self._db_path`、`self._interpreter`；模块级 `_ALLOWED_PATTERN`、`_TRANSLATION_TABLE`、`_evaluator_lock`、`_evaluator_pool` |
| 异常类 | 以 `Error` 结尾，PascalCase | `CalculatorError`、`EmptyExpressionError`、`DivisionByZeroError`、`DatabaseError`、`RecordNotFoundError` |
| 内部常量字符串 | 私有前缀 + UPPER_SNAKE | `_SELECT_COLUMNS`、`_BOOT_DB`、`_SQLITE_SUFFIXES` |
| 日志器 | 点分层级名，模块内一个 | `logging.getLogger("calculator.api")`、`logging.getLogger("calculator.evaluator")` |
| 夹具 | 名词，与被测对象同名 | `db_file`、`client`、`evaluator` |

补充约定：

* **类名即职责**：类名里出现 `Repository` 就说明它是数据访问层（`HistoryRepository`），出现 `Evaluator`
  就是求值层（`SafeEvaluator`）；不要造 `Manager`、`Helper`、`Util` 这类没有信息量的名字。
* **表达“尚未处理”的变量加前缀**：路由层拿到用户输入先叫 `raw_expression`，归一化后才叫 `expression`；
  拿到查询参数先叫 `normalized_keyword`。名字要能反映它处在流水线的哪一步。
* 不为短生命周期变量起 1–2 个字母的名字；`for index in range(5)` 里的 `index` 是下限。

---

## 三、类型注解与文档字符串

### 3.1 类型注解

* 每个文件（含测试文件）第一段 import 之前必须是 `from __future__ import annotations`：

  ```python
  from __future__ import annotations

  import sqlite3
  from pathlib import Path
  ```

* **所有公开函数/方法必须有完整类型注解**（参数 + 返回值），包括路由函数：

  ```python
  def calculate(payload: CalculateRequest, request: Request) -> CalculateResponse:
  ```

  ```python
  def list_all(
      self,
      keyword: str | None = None,
      limit: int | None = None,
      offset: int = 0,
  ) -> list[dict[str, Any]]:
  ```

  ```python
  def evaluate(self, raw_expression: str) -> str:
  ```

  ```python
  def to_payload(self) -> dict:
  ```

* 现代写法优先：可空用 `X | None`（**不用** `Optional[X]`），容器用内建泛型 `list[...]` / `dict[...]` / `tuple[...]`。
* 私有辅助函数同样注解，返回类型模糊时用 `Any` 并配注释说明为什么模糊（如 `_run` 返回 `Any`：
  值来自 asteval，可能是 `int/float/complex`，由 `format_result` 负责甄别）。
* 常量显式标注容器类型：`SCHEMA_STATEMENTS: tuple[str, ...] = (...)`。
* 路由需要用具名响应模型：`@app.get("/api/health", response_model=HealthResponse)`，
  而不是返回裸 `dict`；唯一例外是 `/`（`include_in_schema=False` 的自描述信息）。
* 不写 `# type: ignore` 掩盖真实问题。

### 3.2 文档字符串

* **模块级 docstring 用中文写“为什么”**，不只写“是什么”。每个模块开头都要说明设计动机和边界：

  ```python
  """SQLite 持久化层（标准库 sqlite3，不引入 ORM）。

  为什么不用 ORM：
    * 单表 CRUD，SQL 直白可读，答辩时能逐行讲清楚；
    * 少一个依赖，Render 免费实例冷启动更快。

  线程安全说明：
    FastAPI 的同步路由跑在线程池里，sqlite3 连接不能跨线程复用，
    因此这里**每次操作新建连接、用完即关**（SQLite 连接开销极小），
    并开启 WAL 模式提升读写并发。
  """
  ```

* **函数 docstring 写“为什么这么设计”，以及别人接手时最容易踩的坑**：

  ```python
  @staticmethod
  def normalize(raw_expression: str) -> str:
      """去掉首尾空白、翻译全角符号、把 ^ 统一成 Python 的幂运算 **。

      为什么要替换 `^`：Python 里 `^` 是**按位异或**，`2^10` 会得到 8 而不是 1024。
      计算器用户习惯用 `^` 表示乘方，所以在归一化阶段统一成 `**`，
      避免出现"结果对不上但代码没报错"的诡异现象。
      """
  ```

* **复杂函数必须写清边界条件与规则列表**（阈值、上下界、哪些输入被拒绝）：
  `evaluator.py` 的模块 docstring 逐层列出四层加固与各自的阈值；`SafeEvaluator.format_result`
  用项目符号列出四条格式化规则；`db.py` 的模块 docstring 用表格化的字段说明表结构。
* 简单清晰的函数（`db.py::_row_to_dict`、`schemas.py` 各类的 `"""一行说明。"""`）保持一行即可，
  不要为了凑字数写废话。
* 数据模型字段用 Pydantic 的 `Field(description=...)` 承载给前端/文档看的说明，与 docstring 分工明确：

  ```python
  expression: str = Field(
      default="",
      description="待计算的表达式字符串，例如 3*(2+5)-4/2 或 3*-2",
      examples=["3*(2+5)-4/2"],
  )
  ```

* 章节分隔注释统一用 `# ---------------------------------------------------------------- 常量` 这类长横线注释，
  让 200+ 行的模块能被快速扫读（`main.py` 用 `# ===...=== 异常处理` 分隔大块）。

---

## 四、分层与依赖方向

### 4.1 分层结构

```
        ┌──────────────────────────────────────────┐
        │ main.py            路由层（FastAPI）      │  HTTP、CORS、统一异常处理、日志
        └───────────────┬──────────────────────────┘
                        │ 只调用下层公开接口
        ┌───────────────▼──────────────┐  ┌──────────────────────────┐
        │ evaluator.py   领域层（求值） │  │ db.py  领域层（持久化）   │
        └───────────────┬──────────────┘  └────────────┬─────────────┘
                        │                              │
                        └──────────┬───────────────────┘
                                   ▼
                      errors.py   异常体系（code / status_code / 中文 message）
                      schemas.py  数据模型（Pydantic v2 请求与响应）
```

| 模块 | 职责 | 允许依赖 |
| --- | --- | --- |
| `main.py` | 路由、参数声明、生命周期、CORS、异常处理器、启动入口 | `evaluator`、`db`、`errors`、`schemas`、`config`、FastAPI |
| `evaluator.py` | 唯一的表达式求值入口：归一化 → 校验 → asteval 求值 → 结果格式化 | `errors`、`asteval`、标准库 |
| `db.py` | SQLite 仓储：建表、增删查、连接管理 | `errors`、标准库 `sqlite3` |
| `schemas.py` | 请求/响应数据模型，统一 `{success, data}` / `{success, error}` 结构 | `pydantic` |
| `errors.py` | 业务异常基类与全部子类，自带 `code` / `status_code` / 中文 `message` | 标准库 `http.HTTPStatus` |
| `config.py` | 环境变量读取、`settings` 单例、日志初始化 | 标准库 |

### 4.2 依赖方向硬性规则

* **禁止路由层直接拼接 SQL**。`main.py` 中不出现任何 SQL 关键字（`SELECT` / `INSERT` / `DELETE`），
  一律通过仓储方法完成：`repo.create(...)`、`repo.list_all(...)`、`repo.count(...)`、`repo.get(...)`、
  `repo.delete(...)`、`repo.clear()`。SQL 只允许出现在 `db.py`。
* **禁止领域层依赖 FastAPI**。`evaluator.py` 与 `db.py` **不得** import `fastapi`、`starlette`、
  `Request`、`HTTPException`；它们抛出的只有 `errors.py` 里的业务异常。这样求值引擎与仓储都可以
  脱离 Web 框架被单测直接调用（`tests/test_evaluator.py` 只用 `SafeEvaluator`，
  `tests/test_api.py::test_history_survives_repository_restart` 只用 `HistoryRepository`）。
* **禁止跨层反向调用**：`errors.py`、`schemas.py` 是最底层，除标准库/`pydantic` 外不 import 任何本项目模块，
  也不 import 彼此。
* **业务异常只在领域层抛出，只在路由层渲染**。`evaluator.py` / `db.py` 抛异常；
  `main.py::handle_calculator_error` 把它转成 JSON。领域层不构造 HTTP 响应。
* **仓储实例不散落**：全局仓储在模块级创建（`repository = HistoryRepository(settings.db_path)`），
  在 `lifespan` 中 `init_schema()` 并挂到 `app.state.repository`；路由通过
  `repo: HistoryRepository = request.app.state.repository` 取用，不新建连接、不 import 全局变量之外的实例。
* **配置只从 `config.settings` 取**：代码里不写死路径、端口、CORS 域名与日志级别（见 `config.py` 的
  环境变量表）；只在 `main.py` 的 `__main__` 调试入口读取 `PORT` / `CALC_RELOAD`。

---

## 五、异常处理规范

### 5.1 业务异常必须继承 `CalculatorError`

所有**可预期**的错误都定义在 `errors.py`，继承 `CalculatorError`，并给出 `code` / `status_code` /
中文 `default_message` 三要素，由 `main.py` 的统一处理器渲染成同一套 JSON。

```python
class CalculatorError(Exception):
    """所有业务异常的基类。"""

    code: str = "CALCULATOR_ERROR"
    status_code: int = HTTPStatus.BAD_REQUEST
    default_message: str = "计算失败，请检查表达式"

    def __init__(self, message: str | None = None, *, expression: str | None = None) -> None:
        self.message = message or self.default_message
        self.expression = expression
        super().__init__(self.message)
```

```python
class DivisionByZeroError(CalculatorError):
    code = "DIVISION_BY_ZERO"
    default_message = "除数不能为 0"


class DatabaseError(CalculatorError):
    code = "DATABASE_ERROR"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message = "数据库操作失败，请稍后重试"
```

规则：

* `code` 是给程序看的**稳定**标识（前端可据此做特殊处理），全大写下划线，**不要随意改名**；
  `message` 是给用户看的中文提示，两者分离。
* HTTP 状态码用 `http.HTTPStatus` 常量而非魔法数字：输入问题 4xx（默认 `BAD_REQUEST`），
  服务端问题 5xx（`NOT_FOUND`、`INTERNAL_SERVER_ERROR`）。
* 需要定位问题时把原始表达式带上：`raise IllegalCharacterError("...", expression=expression)`；
  `to_payload()` 只在 `expression is not None` 时输出该字段。
* 新增异常类时按 `errors.py` 现有的分组注释归类（输入校验类 / 求值类 / 数据访问类）。

### 5.2 禁止裸 `except`

* **禁止 `except:` 与 `except Exception:` 后什么都不做**。捕获必须满足其一：翻译成业务异常、记录日志、
  或作有意的降级并写清理由。
* 允许的两处“宽捕获”都带 `noqa` 与理由注释，见 `evaluator.py::_run`：

  ```python
  try:
      value = interpreter.eval(expression, show_errors=False, raise_errors=True)
  except Exception as exc:  # noqa: BLE001 - 统一翻译成业务异常
      raise self._translate_error(exc, expression) from exc
  ```

* 必带 `raise ... from exc` 保留因果链；翻译后的异常必须是 `CalculatorError` 子类。
* 收窄捕获范围：数据层只捕获 `sqlite3.Error`（`db.py::_connect`、`_connection`），
  且 `_connection` 在异常时先 `rollback()` 再抛 `DatabaseError`，连接在 `finally` 中关闭。
* 权限/兼容性降级也要留日志，例如清空符号表失败时
  `logger.warning("无法清空 asteval 符号表，已退化为仅依赖字符白名单")`。

### 5.3 禁止把堆栈返回给前端

* 兜底处理器只返回固定文案，堆栈只进服务端日志：

  ```python
  @app.exception_handler(Exception)
  async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
      """兜底：任何未预料的异常都不能把堆栈暴露给前端。"""
      logger.exception("未捕获异常：%s", exc)
      return JSONResponse(
          status_code=500,
          content={
              "success": False,
              "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后重试"},
          },
      )
  ```

* Pydantic 校验失败（422）与框架级 404/405 也统一成
  `{"success": false, "error": {"code": ..., "message": ...}}`，前端只需处理一种错误结构
  （`VALIDATION_ERROR`、`HTTP_404` 等）。
* 错误响应里**绝不**包含 `traceback`、SQL 语句、文件路径、依赖版本。

### 5.4 失败的计算不得写库

* 顺序固定为**先算后写**：`main.py::calculate` 中 `get_evaluator().evaluate(...)` 抛异常时直接冒泡，
  根本走不到 `repo.create(...)`：

  ```python
  result_text = get_evaluator().evaluate(raw_expression)  # 失败会抛 CalculatorError
  elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)

  record = repo.create(expression=raw_expression, result=result_text)
  ```

* 必须有用例守住这条规则：`tests/test_api.py::test_calculate_division_by_zero_returns_400_and_writes_nothing`
  断言失败后 `client.get("/api/history").json()["total"] == 0`。
* 写库失败（`DatabaseError`）返回 500，不得返回“计算成功”的假响应。

---

## 六、安全规范

### 6.1 严禁 `eval` / `exec`

**绝对禁止**使用 `eval()`、`exec()`、`compile()`、`__import__()`、`pickle` 反序列化用户输入来执行表达式。
求值一律通过 **asteval**（纯 Python AST 安全解析库）完成，且三层加固叠加使用。

### 6.2 三层加固（外加归一化，共四步）

```
用户输入 ──▶ ①字符白名单 ──▶ ②长度/复杂度限制 ──▶ ③asteval(空符号表) ──▶ ④归一化/异常翻译 ──▶ 结果
```

| 层 | 实现 | 规则 |
| --- | --- | --- |
| ① 字符白名单 | `ALLOWED_CHARACTERS = r"0-9+\-*/().\s%^"` + `re.fullmatch` | 只允许数字、小数点、`+ - * / ( ) % ^` 与空白。字母、下划线、引号、方括号、分号一律在进入解析器前拒绝，从根上堵住 `__import__('os')`、`1+2; rm -rf /` |
| ② 复杂度限制 | `MAX_EXPRESSION_LENGTH = 200`、`MAX_POWER_OPERATORS = 1`、`MAX_POWER_EXPONENT = 1000` | 长度 ≤ 200；幂运算最多一次且指数 ≤ 1000，杜绝 `9**9**9` 这种“几个字符打满 CPU”的表达式 |
| ③ 空符号表 | `Interpreter(minimal=True)` 后 `self._interpreter.symtable.clear()` | 即使白名单被绕过，表达式里也没有任何可调用的名字/变量 |
| ④ 归一化 + 异常翻译 | `normalize()` → `_translate_error()` | 全角/数学符号先翻译（`×`→`*`、`÷`→`/`、`^`→`**`），失败一律翻译成带 `code` 的业务异常 |

校验顺序在 `SafeEvaluator.validate()` 中固定为：非空 → 长度 → 字符白名单 → 括号配对 → 幂运算次数/指数。
**新增任何校验都必须放在 asteval 调用之前**，因为这四层是纵深防御，任何一层被绕过都不能导致代码执行。

额外注意事项：

* 不允许为了“支持更多运算”而放宽白名单去兼容字母；函数名（`sin`、`print`）按设计被拒绝（见 README Q3）。
* asteval 实例**非线程安全**，必须通过 `get_evaluator()` 取线程局部的实例（内部用 `threading.Lock` +
  `dict[thread_id, SafeEvaluator]`），禁止在路由里直接 `SafeEvaluator()`。
* CORS 默认 `*` 仅用于开发/演示；生产必须用 `CALC_CORS_ORIGINS` 显式写死前端域名。

### 6.3 新增运算能力必须“白名单 + 测试”同步落地

新增一种运算符/符号时，**同一个提交内**必须完成：

1. 在 `_TRANSLATION_TABLE`（若是全角/别名符号）或 `ALLOWED_CHARACTERS` 中登记该符号；
2. 在 `validate()` 中补上对应的复杂度限制（若该运算可能爆炸式增长）；
3. 在 `tests/test_evaluator.py` 的 `VALID_CASES` 中补正常用例，并在异常分支中补越界用例；
4. 若涉及 API 行为变化，同步更新 `README.md` 的错误码总表/能力说明。

### 6.4 源码自检测试

`tests/test_evaluator.py::test_no_eval_or_exec_in_source` 会扫描仓库根目录下所有 `*.py`，
一旦出现 `eval(` / `exec(` 调用即失败：

```python
def test_no_eval_or_exec_in_source():
    """硬性规则自检：源码里不允许出现 eval( / exec( 调用。"""
    import re
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[1]
    forbidden = re.compile(r"(?<![\w.])(eval|exec)\s*\(")
    offenders = []
    for path in backend_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            offenders.append(path.name)
    assert offenders == [], f"以下文件疑似使用了 eval/exec：{offenders}"
```

* 该测试不得被删除、跳过或改写为恒真；`ruff check .` 会顺带保证源码里没有其它形式的动态执行。
* 其它安全要求：不记录完整用户请求体之外的敏感信息；`requirements.txt` 固定版本（`fastapi==0.115.6`
  等）以避免依赖漂移引入风险；该文件保持 ASCII-only（Windows GBK 环境下 pip 会有解码问题）。

---

## 七、数据访问规范

### 7.1 参数化查询，禁止字符串拼 SQL

* **所有**带外部输入的 SQL 必须使用 `?` 占位符 + 参数元组/列表，绝不把变量格式化进 SQL 字符串：

  ```python
  cursor = connection.execute(
      "INSERT INTO calculation_history (expression, result, created_at) VALUES (?, ?, ?)",
      (expression, result, created_at),
  )
  ```

  ```python
  sql += " WHERE expression LIKE ? OR result LIKE ?"
  pattern = f"%{keyword}%"
  params.extend([pattern, pattern])
  ```

  注意 `%{keyword}%` 作为**参数值**拼接是安全的（LIKE 通配由参数承载），
  但把它插进 SQL 文本就是注入漏洞。
* 允许用 f-string 拼接的只有**常量片段**，且不含任何用户输入：
  `f"SELECT {_SELECT_COLUMNS} FROM calculation_history"`（`_SELECT_COLUMNS` 为模块级常量）。
* 表名/列名一律硬编码，不接受来自请求的标识符。

### 7.2 连接生命周期

* **每次操作新建连接、用完即关**：`sqlite3` 连接不能跨线程复用（FastAPI 同步路由跑在线程池里），
  而 SQLite 建连接开销极小。统一通过 `_connection()` 上下文管理器，保证提交/回滚/关闭：

  ```python
  @contextmanager
  def _connection(self) -> Iterator[sqlite3.Connection]:
      connection = self._connect()
      try:
          yield connection
          connection.commit()
      except sqlite3.Error as exc:
          connection.rollback()
          raise DatabaseError(f"数据库操作失败：{exc}") from exc
      finally:
          connection.close()
  ```

* 连接参数统一在 `_connect()` 内设置，禁止在业务方法里零散配置：

  ```python
  connection = sqlite3.connect(self._db_path, timeout=10.0)
  connection.row_factory = sqlite3.Row          # 支持按列名取值
  connection.execute("PRAGMA journal_mode=WAL")
  connection.execute("PRAGMA synchronous=NORMAL")
  ```

* 开启 **WAL** 提升读写并发；父目录不存在时由 `_connect()` 用
  `self._db_path.parent.mkdir(parents=True, exist_ok=True)` 自动创建。
* 建表语句集中在 `SCHEMA_STATEMENTS`（全部 `IF NOT EXISTS`，幂等），由 `init_schema()` 在
  `lifespan` 启动时执行，不允许在导入期建表。
* 行到字典的转换只走 `_row_to_dict()`，不要在多个方法里重复手写列名映射。
* 数据库错误只抛 `DatabaseError`，不把原始 SQL 或文件路径写进面向用户的 `message`。

### 7.3 表结构变更流程

字段/表结构变更必须在**同一个提交**内完成四件事：

1. 修改 `db.py::SCHEMA_STATEMENTS`（保持 `IF NOT EXISTS` 幂等；如需迁移脚本，另附说明）；
2. 修改 `_SELECT_COLUMNS` 与 `_row_to_dict()`（若有新增列）；
3. 更新 `schemas.py` 中对应的 Pydantic 模型字段与 `Field(description=...)`；
4. 同步更新 **`README.md` 第七节「数据库设计」的表结构说明与错误码/API 文档**，并补充/调整测试
   （`tests/test_api.py` 中涉及该字段的断言）。

当前表结构（`calculation_history`）：

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键，自增 |
| `expression` | TEXT | 用户输入的**原始**表达式（保留 `×` `÷` 等符号，不存归一化结果） |
| `result` | TEXT | 后端计算结果，字符串保存以避免浮点精度丢失与大整数失真 |
| `created_at` | TEXT | ISO 8601（UTC），由 `_now_iso()` 生成，秒级精度带时区 |

---

## 八、测试规范

### 8.1 基本约定

* 框架：**pytest**，配置见 `pytest.ini`：

  ```ini
  [pytest]
  pythonpath = .
  testpaths = tests
  addopts = -q
  filterwarnings =
      ignore::DeprecationWarning
  ```

* 文件名 `test_*.py`，测试函数 `test_*`；`tests/` 下与源码同层，公共夹具写在 `tests/conftest.py`。
* 用例命名遵循 **`test_<行为>_<期望>`**，必要时可加长，读起来像一句话：

  | 用例 | 说明 |
  | --- | --- |
  | `test_calculate_division_by_zero_returns_400_and_writes_nothing` | 除零 → 400 且不写库 |
  | `test_calculate_accepts_chinese_operator_symbols` | 接受 `×` 符号 |
  | `test_history_is_ordered_by_newest_first` | 历史按最新在前 |
  | `test_delete_missing_record_returns_404` | 删除不存在的记录 → 404 |
  | `test_history_survives_repository_restart` | 持久化跨“重启”仍存在 |
  | `test_no_eval_or_exec_in_source` | 源码安全自检 |

* 测试文件与测试函数也必须有 docstring 说明该测试**在证伪什么**，例如
  `test_history_survives_repository_restart` 注明“用两个独立的仓储对象访问同一个文件，模拟后端重启，
  证明历史写在磁盘而不是内存/localStorage”。
* 大量等价输入用 `@pytest.mark.parametrize` 而不是复制粘贴：

  ```python
  @pytest.mark.parametrize(("expression", "expected"), VALID_CASES)
  def test_evaluate_valid_expression(evaluator, expression, expected):
      assert evaluator.evaluate(expression) == expected
  ```

* 测试内 import 局部化：`client` / `db_file` / `evaluator` 这些夹具内部再 `import main`、`from db import ...`，
  以保证环境变量在导入前已设置好。

### 8.2 覆盖三类场景

每个功能点至少覆盖 **正常 / 边界 / 异常** 三类：

| 类别 | 例子 |
| --- | --- |
| 正常 | `("6*7", "42")`、`("3*(2+5)-4/2", "19")`、`test_history_keyword_search`、`test_calculate_success_and_saved_to_history` |
| 边界 | 空库 `test_history_empty_database`、分页 `test_history_pagination`、浮点尾巴 `("0.1+0.2", "0.3")`、`("10/3", "3.33333333333")`、全角符号 `test_normalize_full_width_symbols`、长度上限 `test_expression_too_long` |
| 异常 | `1/0`、`5%0`、`3+`、`*5`、`3..5`、`((1+2)`、`abc`、`__import__('os').system('dir')`、`9**9**9`、`2**100000`、请求体类型错误 → 422、未知路由 → `HTTP_404` |

断言要求：

* API 测试必须同时断言 **HTTP 状态码** 与 **`error.code`**，不要只断言状态码：

  ```python
  response = client.post("/api/calculate", json={"expression": "1/0"})
  assert response.status_code == 400
  body = response.json()
  assert body["success"] is False
  assert body["error"]["code"] == "DIVISION_BY_ZERO"
  ```

* 涉及副作用的用例要断言“没有副作用”（失败不写库、删除后剩余条数正确）。
* 不写依赖执行顺序、依赖网络、依赖真实时钟的用例；测试必须可重复、可并行地独立通过。

### 8.3 夹具与数据库隔离

* **每个用例一套独立数据库**：`client` 依赖 `db_file`，在 `with TestClient(main.app)` 内把
  `app.state.repository` 换成指向该临时文件的仓储并 `init_schema()`，用例之间互不干扰：

  ```python
  @pytest.fixture()
  def client(db_file):
      """每个用例一套"全新数据库"的 TestClient。"""
      from fastapi.testclient import TestClient

      import main
      from db import HistoryRepository

      with TestClient(main.app) as test_client:
          test_client.app.state.repository = HistoryRepository(db_file)
          test_client.app.state.repository.init_schema()
          yield test_client
  ```

* **必须在 `import main` 之前**设置 `CALC_DB_PATH`，否则跑测试会在仓库里生成
  `data/calculator.db`（运行时数据不该由测试产生）：

  ```python
  _BOOT_DB = TESTS_DIR / ".boot-calculator.db"
  os.environ["CALC_DB_PATH"] = str(_BOOT_DB)
  os.environ["CALC_LOG_LEVEL"] = "WARNING"
  ```

* **为什么夹具不用 `tmp_path`，而用 uuid 命名的临时数据库文件**：
  pytest 建临时目录用的是 `mode=0o700`，在部分 Windows 受限安全环境（企业策略 / 沙箱 / 受限令牌）下，
  这样建出来的目录**连创建者自己都无法枚举**，夹具会直接抛 `PermissionError: [WinError 5]`。
  本仓库改为在 `tests/` 目录下用 `uuid` 命名数据库文件，隔离性等价，且在更多环境下都能跑通：

  ```python
  @pytest.fixture()
  def db_file():
      """一个干净的临时 SQLite 文件路径，用例结束后连同 WAL 文件一起删除。"""
      path = TESTS_DIR / f"test-{uuid.uuid4().hex}.db"
      yield path
      _remove_sqlite_files(path)
  ```

* 清理必须覆盖 WAL 伴随文件：`_SQLITE_SUFFIXES = ("", "-wal", "-shm")`；
  另用 `pytest_sessionfinish` 兜底清理引导库与残留的 `test-*.db*`。
* 求值引擎单测直接构造 `SafeEvaluator()`（`evaluator` 夹具），不经过 HTTP，保证领域层可独立测试。

### 8.4 运行

```bash
pip install -r requirements-dev.txt
pytest -v
ruff check .
black --check .
```

当前基线：**38 条用例（含参数化展开共 68 个）全部通过**，其中 `tests/test_evaluator.py` 覆盖求值引擎，
`tests/test_api.py` 覆盖接口与持久化。新增功能必须同时补测试，不允许降低既有覆盖。

---

## 九、日志规范

* 统一使用标准库 `logging`，**禁止 `print`**；格式与级别由 `config.py::configure_logging()` 一处定义：

  ```python
  logging.basicConfig(
      level=getattr(logging, settings.log_level, logging.INFO),
      format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
  )
  ```

  日志级别通过 `CALC_LOG_LEVEL` 环境变量控制（默认 `INFO`，测试环境置为 `WARNING`）。

* 每个模块一个具名日志器，命名按 `calculator.<模块>` 分层：

  ```python
  logger = logging.getLogger("calculator.api")
  logger = logging.getLogger("calculator.evaluator")
  ```

* **级别约定**：

  | 级别 | 使用场景 | 仓库中的例子 |
  | --- | --- | --- |
  | `info` | 正常业务动作，便于演示与排查 | `logger.info("计算成功：%s = %s（%.3f ms，id=%s）", ...)`、`logger.info("删除历史记录 id=%s（%s = %s）", ...)`、`logger.info("清空历史记录，共删除 %s 条", deleted_count)` |
  | `warning` | **业务异常**（客户端可预期错误）与可恢复的降级 | `logger.warning("业务异常 [%s] %s \| 表达式：%s", exc.code, exc.message, exc.expression)`（仅在 `status_code < 500` 时）、`logger.warning("无法清空 asteval 符号表，已退化为仅依赖字符白名单")`、`logger.warning("未分类的求值异常：%s: %s", type(exc).__name__, exc)` |
  | `exception` | **服务端异常**，必须带堆栈 | `logger.exception("服务端异常：%s", exc.message)`、`logger.exception("未捕获异常：%s", exc)` |
  | `debug` | 仅本地排查使用，不进入默认输出 | —— |

* 业务异常与服务端异常的分流写在统一处理器里，判据是状态码而不是异常类型：

  ```python
  if exc.status_code >= 500:
      logger.exception("服务端异常：%s", exc.message)
  else:
      logger.warning("业务异常 [%s] %s | 表达式：%s", exc.code, exc.message, exc.expression)
  ```

* **日志里必须能还原现场**：计算相关日志包含**原始表达式与结果**（外加耗时、记录 id）；删除/清空包含
  被影响的 id 与条数。这样线上排查只需要日志，不需要复现请求。
* 使用 `%s` 惰性格式化参数，**不要**用 f-string 预先拼好字符串（既耗性能，又容易把异常细节吞掉）。
* 不得记录敏感信息（密钥、完整环境变量、数据库文件绝对路径以外的系统信息）；错误响应与日志的措辞分开，
  日志可以详细，返回给前端的必须克制（见第五节）。
* 模块导入期不产生日志；日志初始化放在 `lifespan` 启动阶段调用。

---

## 十、Git 提交规范

采用 **Conventional Commits**：`<type>(<scope>): <中文简述>`。

| type | 用途 |
| --- | --- |
| `feat` | 新功能（新接口、新运算符） |
| `fix` | 缺陷修复（含安全加固） |
| `refactor` | 不改行为的重构 |
| `test` | 新增/调整测试 |
| `docs` | 文档（README、codestyle.md） |
| `chore` | 构建、依赖、配置（requirements、pyproject、Dockerfile） |
| `perf` | 性能优化 |

`scope` 用模块名（`api`、`evaluator`、`db`、`schemas`、`errors`、`config`、`tests`、`docs`）。

```text
feat(evaluator): 支持 ^ 作为乘方并在归一化阶段转换为 **

用户习惯用 ^ 表示乘方，而 Python 的 ^ 是按位异或（2^10 = 8）。
在 normalize 阶段统一替换，避免"结果对不上但不报错"。
同步补充 VALID_CASES 用例。

Refs: README 第八节
```

```text
fix(db): 参数化 LIKE 查询，消除模糊搜索的注入风险
```

```text
test(api): 补除零失败不写库的断言
```

```text
docs(readme): 更新错误码总表
```

```text
chore(deps): 固定 asteval==1.0.5
```

提交纪律：

* 一次提交只做一件事；`feat` 与它的测试放在同一提交（见第六节“白名单 + 测试同步落地”）。
* 摘要行 ≤ 50 个字符、用祈使句、结尾不加句号；正文（可选）说明**为什么**而不是“改了什么”。
* 破坏性变更写 `feat(api)!: ...` 并在正文用 `BREAKING CHANGE:` 说明影响面（错误码改名、接口路径调整）。
* 禁止提交 `data/`、`.venv/`、`__pycache__/`、`tests/*.db*`；禁止提交 `# noqa` 之外的临时调试代码。

---

## 十一、代码审查清单

提交或评审前逐条勾选：

* [ ] `ruff check .`、`ruff format --check .`、`black --check .` 全部通过，`line-length` 未超 110。
* [ ] 没有使用 `eval` / `exec` / `compile` / 动态 `__import__`，`test_no_eval_or_exec_in_source` 通过。
* [ ] 所有 SQL 均参数化（`?` 占位），没有把用户输入格式化进 SQL 文本；SQL 只出现在 `db.py`。
* [ ] 新增/放宽的白名单字符同时补了 `tests/test_evaluator.py` 的正常与越界用例。
* [ ] 新的可预期错误继承 `CalculatorError` 并给出 `code` / `status_code` / 中文 `message`。
* [ ] 没有裸 `except` / 静默 `pass`；捕获后要么翻译成业务异常，要么留 `warning` 日志；`raise ... from exc` 保留因果链。
* [ ] 错误响应不含堆栈、SQL、路径；异常走 `main.py` 的统一处理器，未绕过。
* [ ] 失败的计算不会写库（含“先算后写”顺序与对应断言）。
* [ ] 领域层（`evaluator.py` / `db.py`）没有 import `fastapi` / `starlette`；路由层没有直接操作连接与 SQL。
* [ ] 每个新用例使用独立数据库（`db_file` / `client` 夹具），不写 `data/calculator.db`，跑完无残留 `tests/*.db*`。
* [ ] 新增或调整的行为覆盖正常 / 边界 / 异常三类场景，API 用例同时断言状态码与 `error.code`。
* [ ] 每次数据库操作新建连接并关闭（走 `_connection()`），WAL 与 `PRAGMA` 设置未被绕过。
* [ ] 表结构或接口有变更时，`README.md`（第七节表结构 / 6.5 错误码总表 / 目录结构）与 `schemas.py` 已同步更新。
* [ ] 日志使用 `logging` 且带惰性 `%s` 参数；业务异常 `warning`、服务端异常 `exception`；计算日志含表达式与结果。
* [ ] 新增公开函数有完整类型注解，模块/复杂函数 docstring 说明了“为什么”与边界条件。
* [ ] 提交信息符合 Conventional Commits，且与改动范围一致（`feat`/`fix`/`test`/`docs`/`chore` 不混用）。

---

最后更新：2026-10-02
