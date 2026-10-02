"""业务异常定义。

设计要点：
1. 所有**可预期**的错误（除零、非法字符、括号不匹配……）都继承 CalculatorError，
   由 main.py 中的统一异常处理器转换成同一套 JSON 结构：
       {"success": false, "error": {"code": "...", "message": "..."}}
   —— 这样前端只需要处理一种错误结构。
2. code 是给程序看的稳定标识，message 是给用户看的中文提示，两者分离便于前端做 i18n。
3. 每个异常自带 HTTP 状态码：客户端输入问题用 4xx，服务端问题用 5xx。
"""

from __future__ import annotations

from http import HTTPStatus


class CalculatorError(Exception):
    """所有业务异常的基类。"""

    code: str = "CALCULATOR_ERROR"
    status_code: int = HTTPStatus.BAD_REQUEST
    default_message: str = "计算失败，请检查表达式"

    def __init__(self, message: str | None = None, *, expression: str | None = None) -> None:
        self.message = message or self.default_message
        self.expression = expression
        super().__init__(self.message)

    def to_payload(self) -> dict:
        """转换成统一的响应体。"""
        error: dict[str, object] = {"code": self.code, "message": self.message}
        if self.expression is not None:
            error["expression"] = self.expression
        return {"success": False, "error": error}


# --------------------------------------------------------------------------
# 输入校验类异常
# --------------------------------------------------------------------------
class EmptyExpressionError(CalculatorError):
    code = "EMPTY_EXPRESSION"
    default_message = "表达式不能为空"


class ExpressionTooLongError(CalculatorError):
    code = "EXPRESSION_TOO_LONG"
    default_message = "表达式过长，请缩短后再试"


class IllegalCharacterError(CalculatorError):
    code = "ILLEGAL_CHARACTER"
    default_message = "表达式包含非法字符"


class UnbalancedParenthesesError(CalculatorError):
    code = "UNBALANCED_PARENTHESES"
    default_message = "括号不匹配，请检查左右括号数量"


class ExpressionTooComplexError(CalculatorError):
    code = "EXPRESSION_TOO_COMPLEX"
    default_message = "表达式过于复杂，已拒绝计算"


# --------------------------------------------------------------------------
# 求值类异常
# --------------------------------------------------------------------------
class SyntaxErrorInExpression(CalculatorError):
    code = "SYNTAX_ERROR"
    default_message = "表达式语法错误，请检查运算符或数字是否完整"


class DivisionByZeroError(CalculatorError):
    code = "DIVISION_BY_ZERO"
    default_message = "除数不能为 0"


class ResultOverflowError(CalculatorError):
    code = "RESULT_OVERFLOW"
    default_message = "计算结果超出可表示范围"


class UnsupportedOperationError(CalculatorError):
    code = "UNSUPPORTED_OPERATION"
    default_message = "不支持该运算，仅支持实数四则运算"


# --------------------------------------------------------------------------
# 数据访问类异常
# --------------------------------------------------------------------------
class RecordNotFoundError(CalculatorError):
    code = "RECORD_NOT_FOUND"
    status_code = HTTPStatus.NOT_FOUND
    default_message = "历史记录不存在"


class DatabaseError(CalculatorError):
    code = "DATABASE_ERROR"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message = "数据库操作失败，请稍后重试"
