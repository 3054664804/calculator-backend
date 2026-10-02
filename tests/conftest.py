"""pytest 公共夹具。

两个关键点：

1. 必须在 import main 之前把 CALC_DB_PATH 指到一个临时文件，
   否则跑测试会在仓库里生成 data/calculator.db（那是运行时数据，不该由测试产生）。

2. **刻意不使用 `tmp_path` 夹具，也不创建新目录**：
   pytest 建临时目录用的是 `mode=0o700`，在部分 Windows 受限安全环境
   （企业策略 / 沙箱 / 受限令牌）下，这样建出来的目录连创建者自己都无法枚举，
   夹具会直接抛 `PermissionError: [WinError 5]`。
   这里改成"在 tests/ 目录下用 uuid 命名一个临时数据库文件"，跑完即删：
   隔离性足够、行为等价，而且在更多环境下都能跑通。
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TESTS_DIR = Path(__file__).resolve().parent

# 引导库文件：仅供 import main 时的模块级仓储使用，全局复用同一个文件
_BOOT_DB = TESTS_DIR / ".boot-calculator.db"
os.environ["CALC_DB_PATH"] = str(_BOOT_DB)
os.environ["CALC_LOG_LEVEL"] = "WARNING"

_SQLITE_SUFFIXES = ("", "-wal", "-shm")


def _remove_sqlite_files(base: Path) -> None:
    for suffix in _SQLITE_SUFFIXES:
        Path(f"{base}{suffix}").unlink(missing_ok=True)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """收尾：清理引导库文件与可能残留的临时数据库文件。"""
    _remove_sqlite_files(_BOOT_DB)
    for leftover in TESTS_DIR.glob("test-*.db*"):
        leftover.unlink(missing_ok=True)


@pytest.fixture()
def db_file():
    """一个干净的临时 SQLite 文件路径，用例结束后连同 WAL 文件一起删除。"""
    path = TESTS_DIR / f"test-{uuid.uuid4().hex}.db"
    yield path
    _remove_sqlite_files(path)


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


@pytest.fixture()
def evaluator():
    from evaluator import SafeEvaluator

    return SafeEvaluator()
