"""安全表达式求值引擎（本项目最核心的模块）。

硬性要求：**严禁使用 eval / exec 执行用户输入**。
本模块用第三方安全解析库 asteval 完成求值，并在此基础上做了四层加固：

  第 1 层 · 字符白名单
      只允许 `0-9 + - * / ( ) . % ^` 和空白字符，字母、下划线、引号、方括号
      等一律在进入解析器之前就被拒绝，从根上堵住 `__import__('os')` 这类注入。

  第 2 层 · 符号表清空
      asteval 默认带一份符号表（内置函数等）。这里把它清空，
      即使白名单被绕过，表达式里也没有任何可调用的名字。

  第 3 层 · 复杂度限制
      表达式长度 ≤ 200；幂运算最多一次且指数 ≤ 1000，
      防止 `9**9**9` 这种"一个字符就能打满 CPU"的表达式。

  第 4 层 · 友好归一化
      前端键盘输入的是 `×` `÷` 和全角字符，统一转换成 Python 运算符后再求值，
      用户看到的仍然是自己敲的原文（数据库里存原文）。

求值流程：normalize → validate → asteval.eval → format_result
"""

from __future__ import annotations

import logging
import math
import re
import threading
from decimal import Decimal, InvalidOperation
from typing import Any

from asteval import Interpreter

from errors import (
    CalculatorError,
    DivisionByZeroError,
    EmptyExpressionError,
    ExpressionTooComplexError,
    ExpressionTooLongError,
    IllegalCharacterError,
    ResultOverflowError,
    SyntaxErrorInExpression,
    UnbalancedParenthesesError,
    UnsupportedOperationError,
)

logger = logging.getLogger("calculator.evaluator")

# ---------------------------------------------------------------- 常量
MAX_EXPRESSION_LENGTH = 200
MAX_POWER_EXPONENT = 1000
MAX_POWER_OPERATORS = 1

ALLOWED_CHARACTERS = r"0-9+\-*/().\s%^"
_ALLOWED_PATTERN = re.compile(rf"[{ALLOWED_CHARACTERS}]+")
_ILLEGAL_CHARACTER_PATTERN = re.compile(rf"[^{ALLOWED_CHARACTERS}]")
_POWER_OPERATOR_PATTERN = re.compile(r"\*\*|\^")
_POWER_EXPONENT_PATTERN = re.compile(r"(?:\*\*|\^)\s*(\d+)")

#: 前端 / 中文输入法可能送来的全角与数学符号
_TRANSLATION_TABLE = str.maketrans(
    {
        "×": "*",
        "✕": "*",
        "＊": "*",
        "·": "*",
        "÷": "/",
        "／": "/",
        "−": "-",
        "–": "-",
        "—": "-",
        "－": "-",
        "（": "(",
        "）": ")",
        "．": ".",
        "％": "%",
        "＾": "^",
        "　": " ",
    }
)


class SafeEvaluator:
    """线程内可复用的安全求值器。

    注意：asteval 的 Interpreter 实例**不是线程安全的**（内部有 error 列表等可变状态），
    因此 calculate 路由里每当需要求值时会通过 `get_evaluator()` 取一个线程局部实例。
    """

    def __init__(self) -> None:
        self._interpreter = Interpreter(minimal=True)
        self._harden_symbol_table()
        self._apply_resource_limits()

    # ------------------------------------------------------------ 初始化加固
    def _harden_symbol_table(self) -> None:
        """清空 asteval 符号表：表达式里不允许出现任何函数名 / 变量名。"""
        try:
            self._interpreter.symtable.clear()
        except Exception:  # pragma: no cover - 不同 asteval 版本兼容
            logger.warning("无法清空 asteval 符号表，已退化为仅依赖字符白名单")

    def _apply_resource_limits(self) -> None:
        """尽量使用 asteval 自带的语句长度限制（存在才设置）。"""
        if hasattr(self._interpreter, "max_statement_length"):
            try:
                self._interpreter.max_statement_length = max(
                    MAX_EXPRESSION_LENGTH, int(self._interpreter.max_statement_length or 0)
                )
            except Exception:  # pragma: no cover
                pass

    # ------------------------------------------------------------ 对外接口
    def evaluate(self, raw_expression: str) -> str:
        """把表达式字符串算成结果字符串；任何失败都抛出 CalculatorError 子类。"""
        expression = self.normalize(raw_expression)
        self.validate(expression)
        value = self._run(expression)
        return self.format_result(value, expression)

    # ------------------------------------------------------------ 归一化
    @staticmethod
    def normalize(raw_expression: str) -> str:
        """去掉首尾空白、翻译全角符号、把 ^ 统一成 Python 的幂运算 **。

        为什么要替换 `^`：Python 里 `^` 是**按位异或**，`2^10` 会得到 8 而不是 1024。
        计算器用户习惯用 `^` 表示乘方，所以在归一化阶段统一成 `**`，
        避免出现"结果对不上但代码没报错"的诡异现象。
        """
        if raw_expression is None:
            return ""
        text = str(raw_expression).translate(_TRANSLATION_TABLE).strip()
        text = text.replace("^", "**")
        text = re.sub(r"\s+", " ", text)
        return text

    # ------------------------------------------------------------ 校验
    def validate(self, expression: str) -> None:
        if not expression:
            raise EmptyExpressionError()

        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise ExpressionTooLongError(
                f"表达式长度不能超过 {MAX_EXPRESSION_LENGTH} 个字符（当前 {len(expression)} 个）"
            )

        if _ALLOWED_PATTERN.fullmatch(expression) is None:
            illegal = sorted(set(_ILLEGAL_CHARACTER_PATTERN.findall(expression)))
            shown = " ".join(repr(char) for char in illegal[:5])
            raise IllegalCharacterError(
                f"表达式包含非法字符：{shown}；仅支持数字、小数点、+ - * / ( ) % ^ 和空格",
                expression=expression,
            )

        if expression.count("(") != expression.count(")"):
            raise UnbalancedParenthesesError(
                f"括号不匹配：左括号 {expression.count('(')} 个，右括号 {expression.count(')')} 个",
                expression=expression,
            )

        power_operators = _POWER_OPERATOR_PATTERN.findall(expression)
        if len(power_operators) > MAX_POWER_OPERATORS:
            raise ExpressionTooComplexError(
                "为保证服务稳定，一个表达式最多支持一次幂运算（** 或 ^）", expression=expression
            )
        for match in _POWER_EXPONENT_PATTERN.finditer(expression):
            if int(match.group(1)) > MAX_POWER_EXPONENT:
                raise ExpressionTooComplexError(
                    f"幂运算的指数不能超过 {MAX_POWER_EXPONENT}", expression=expression
                )

    # ------------------------------------------------------------ 求值
    def _run(self, expression: str) -> Any:
        interpreter = self._interpreter
        interpreter.error = []  # 清空上一次求值留下的错误栈
        try:
            value = interpreter.eval(expression, show_errors=False, raise_errors=True)
        except Exception as exc:  # noqa: BLE001 - 统一翻译成业务异常
            raise self._translate_error(exc, expression) from exc

        if value is None:
            last_error = interpreter.error[-1] if interpreter.error else None
            raise self._translate_error(last_error, expression)
        return value

    def _translate_error(self, exc: BaseException | None, expression: str) -> CalculatorError:
        """把 asteval / Python 抛出的异常翻译成带 code 的业务异常。"""
        if exc is None:
            return CalculatorError("无法解析该表达式，请检查输入是否正确", expression=expression)

        if isinstance(exc, ZeroDivisionError):
            return DivisionByZeroError("除数不能为 0", expression=expression)
        if isinstance(exc, (SyntaxError, IndentationError, TabError)):
            return SyntaxErrorInExpression(
                "表达式语法错误，请检查运算符是否连续、数字或括号是否完整", expression=expression
            )
        if isinstance(exc, (NotImplementedError, TypeError, ValueError)):
            # asteval 对 `*5` 这类残缺表达式会抛 NotImplementedError('starred')，
            # 本质仍是"语法不完整"，归到语法错误里对用户更友好。
            return SyntaxErrorInExpression(
                "表达式语法错误，请检查运算符是否连续、数字或括号是否完整", expression=expression
            )
        if isinstance(exc, OverflowError):
            return ResultOverflowError("计算结果超出可表示范围", expression=expression)
        if isinstance(exc, MemoryError):
            return ExpressionTooComplexError("表达式过于复杂，已拒绝计算", expression=expression)
        if isinstance(exc, (NameError, AttributeError, KeyError, IndexError)):
            return UnsupportedOperationError(
                "表达式中包含不支持的函数或变量名，本计算器只支持实数四则运算", expression=expression
            )
        if isinstance(exc, RuntimeError):
            return ExpressionTooComplexError("表达式运算量过大，已拒绝计算", expression=expression)

        logger.warning("未分类的求值异常：%s: %s", type(exc).__name__, exc)
        return CalculatorError("计算失败，请检查表达式是否正确", expression=expression)

    # ------------------------------------------------------------ 结果格式化
    def format_result(self, value: Any, expression: str | None = None) -> str:
        """把 asteval 的返回值转成给用户看的字符串。

        规则：
          * 整数直接输出；
          * 浮点用 12 位有效数字输出，抹掉 `0.1 + 0.2 = 0.30000000000000004` 这类二进制尾巴；
          * 极小/极大的数保留科学计数法；
          * 布尔、复数、字符串、None 一律视为"不支持的运算结果"。
        """
        if isinstance(value, bool) or value is None:
            raise UnsupportedOperationError("该表达式的结果不是有效数字", expression=expression)

        if isinstance(value, int):
            return str(value)

        if isinstance(value, float):
            if math.isnan(value):
                raise UnsupportedOperationError("该表达式的结果不是一个有效数字", expression=expression)
            if math.isinf(value):
                raise ResultOverflowError("计算结果超出可表示范围", expression=expression)
            if value == 0:
                return "0"
            return self._format_float(value)

        if isinstance(value, complex):
            raise UnsupportedOperationError("暂不支持复数运算", expression=expression)

        raise UnsupportedOperationError(
            f"不支持的结果类型：{type(value).__name__}，本计算器只处理实数", expression=expression
        )

    @staticmethod
    def _format_float(value: float) -> str:
        text = f"{value:.12g}"
        if "e" in text or "E" in text:
            try:
                decimal_value = Decimal(text)
            except InvalidOperation:  # pragma: no cover
                return text
            exponent = decimal_value.as_tuple().exponent
            # 1e-12 这种小指数展开成 0.000000000001，更符合计算器的阅读习惯
            if isinstance(exponent, int) and -16 <= exponent < 0:
                return f"{decimal_value:f}"
        return text


_evaluator_lock = threading.Lock()
_evaluator_pool: dict[int, SafeEvaluator] = {}


def get_evaluator() -> SafeEvaluator:
    """按线程返回独立的求值器实例（asteval 实例非线程安全）。"""
    thread_id = threading.get_ident()
    with _evaluator_lock:
        evaluator = _evaluator_pool.get(thread_id)
        if evaluator is None:
            evaluator = SafeEvaluator()
            _evaluator_pool[thread_id] = evaluator
        return evaluator
