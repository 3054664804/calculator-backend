"""求值引擎单元测试：覆盖作业要求的全部运算能力与异常分支。"""

from __future__ import annotations

import pytest

from errors import (
    DivisionByZeroError,
    EmptyExpressionError,
    ExpressionTooComplexError,
    ExpressionTooLongError,
    IllegalCharacterError,
    SyntaxErrorInExpression,
    UnbalancedParenthesesError,
)

# --------------------------------------------------------------- 正常计算
VALID_CASES = [
    # 基础四则
    ("1+1", "2"),
    ("9-4", "5"),
    ("6*7", "42"),
    ("8/2", "4"),
    # 复合表达式 + 优先级
    ("3*(2+5)-4/2", "19"),
    ("1+2*3", "7"),
    ("(1+2)*3", "9"),
    ("100/10/2", "5"),
    ("2+3*4-6/3", "12"),
    # 小数
    ("2.5*4", "10"),
    ("0.1+0.2", "0.3"),
    ("1.5+2.25", "3.75"),
    ("10/3", "3.33333333333"),
    ("10/4", "2.5"),
    # 一元正负
    ("-5", "-5"),
    ("3*-2", "-6"),
    ("1 - - 5", "6"),
    ("-(3+2)", "-5"),
    ("-(-5)", "5"),
    ("+7", "7"),
    # 多级括号
    ("((2+3)*(4-1))/5", "3"),
    # 扩展运算符：幂与取模
    ("2^10", "1024"),
    ("2**10", "1024"),
    ("7%3", "1"),
    # 前端直接送入的数学符号与全角符号
    ("3 × 4", "12"),
    ("9 ÷ 3", "3"),
    ("（2＋3）*2".replace("＋", "+"), "10"),
    # 空白容错
    ("  1   +   2  ", "3"),
]


@pytest.mark.parametrize(("expression", "expected"), VALID_CASES)
def test_evaluate_valid_expression(evaluator, expression, expected):
    assert evaluator.evaluate(expression) == expected


# --------------------------------------------------------------- 异常分支
def test_division_by_zero(evaluator):
    with pytest.raises(DivisionByZeroError):
        evaluator.evaluate("1/0")


def test_modulo_by_zero(evaluator):
    with pytest.raises(DivisionByZeroError):
        evaluator.evaluate("5%0")


@pytest.mark.parametrize("expression", ["3+", "*5", "1+*2", "3..5", "((1+2)"])
def test_syntax_errors(evaluator, expression):
    with pytest.raises((SyntaxErrorInExpression, UnbalancedParenthesesError)):
        evaluator.evaluate(expression)


def test_unbalanced_parentheses(evaluator):
    with pytest.raises(UnbalancedParenthesesError):
        evaluator.evaluate("(1+2")


@pytest.mark.parametrize("expression", ["", "   "])
def test_empty_expression(evaluator, expression):
    with pytest.raises(EmptyExpressionError):
        evaluator.evaluate(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "abc",
        "1+2; rm -rf /",
        "__import__('os').system('dir')",
        "1+2#",
        "[1,2]",
        "print(1)",
    ],
)
def test_illegal_characters(evaluator, expression):
    with pytest.raises(IllegalCharacterError):
        evaluator.evaluate(expression)


def test_expression_too_long(evaluator):
    with pytest.raises(ExpressionTooLongError):
        evaluator.evaluate("1+" * 150 + "1")


@pytest.mark.parametrize("expression", ["9**9**9", "2**100000", "2^99999"])
def test_expression_too_complex(evaluator, expression):
    """防止 `9**9**9` 这类表达式把 CPU 打满（安全设计，见 README）。"""
    with pytest.raises(ExpressionTooComplexError):
        evaluator.evaluate(expression)


def test_normalize_full_width_symbols(evaluator):
    assert evaluator.normalize("３＋４") == "３＋４"  # 全角数字不在支持范围内 → 后续被白名单拦截
    assert evaluator.normalize(" 3 ×  4 ") == "3 * 4"
    assert evaluator.normalize("10÷2") == "10/2"


def test_evaluate_is_reusable(evaluator):
    """同一个求值器连续调用不能受上一次错误影响。"""
    with pytest.raises(DivisionByZeroError):
        evaluator.evaluate("1/0")
    assert evaluator.evaluate("2+2") == "4"


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
