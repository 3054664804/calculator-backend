"""计算器后端 API 入口（FastAPI）。

职责边界（作业硬性要求）：
  * 所有表达式计算都发生在本文件调用的 evaluator 里 —— 后端是唯一的计算方；
  * 前端只把表达式字符串发过来、把结果字符串显示出去；
  * 关闭本服务后，前端无法得出任何新结果（历史记录仍然可以看，因为那是数据库里的旧数据）。

对外接口：
  POST   /api/calculate        计算表达式 → 写库 → 返回结果
  GET    /api/history          查询全部历史（支持 keyword / limit / offset）
  DELETE /api/history/{id}     删除指定 id 的单条历史
  DELETE /api/history          清空全部历史（扩展功能）
  GET    /api/health           健康检查（前端用来显示"后端连接状态"）
  GET    /docs                 Swagger 交互式文档
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import configure_logging, settings
from db import HistoryRepository
from errors import CalculatorError, RecordNotFoundError
from evaluator import get_evaluator
from schemas import (
    CalculationData,
    CalculateRequest,
    CalculateResponse,
    ClearData,
    ClearResponse,
    DeleteData,
    DeleteResponse,
    ErrorResponse,
    HealthResponse,
    HistoryListResponse,
    HistoryRecord,
)

logger = logging.getLogger("calculator.api")

repository = HistoryRepository(settings.db_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表，关闭时记录日志。"""
    configure_logging()
    repository.init_schema()
    app.state.repository = repository
    logger.info("计算器后端启动完成 | 数据库：%s | CORS：%s", repository.db_path, settings.cors_origins)
    yield
    logger.info("计算器后端已停止")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "前后端分离计算器系统的后端服务。\n\n"
        "* 表达式求值全部在此完成（asteval 安全解析，**不使用 eval/exec**）\n"
        "* 计算历史持久化到 SQLite，刷新页面 / 换浏览器都不丢\n"
        "* 所有错误都返回 `{\"success\": false, \"error\": {\"code\", \"message\"}}`"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 前端与后端不同源，必须开 CORS。
# 生产环境请用环境变量 CALC_CORS_ORIGINS 指定前端域名，例如：
#   CALC_CORS_ORIGINS=https://calculator-frontend-eight.vercel.app
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ===================================================================== 异常处理
@app.exception_handler(CalculatorError)
async def handle_calculator_error(request: Request, exc: CalculatorError) -> JSONResponse:
    """把业务异常统一渲染成约定好的 JSON 结构。"""
    if exc.status_code >= 500:
        logger.exception("服务端异常：%s", exc.message)
    else:
        logger.warning("业务异常 [%s] %s | 表达式：%s", exc.code, exc.message, exc.expression)
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic 参数校验失败（例如 expression 传了数字）也走统一结构，避免前端拿到两种错误格式。"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body") or "body"
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"请求参数不合法：字段 {location} {first.get('msg', '格式错误')}",
            },
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """404 / 405 等框架级错误同样保持结构一致。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)},
        },
    )


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


# ===================================================================== 系统接口
@app.get("/", include_in_schema=False)
def read_root() -> dict:
    """根路径给一个自描述信息，方便助教快速确认服务活着。"""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "status": "ok",
        "docs": "/docs",
        "endpoints": [
            "POST /api/calculate",
            "GET /api/history",
            "DELETE /api/history/{id}",
            "DELETE /api/history",
            "GET /api/health",
        ],
    }


@app.get("/api/health", response_model=HealthResponse, tags=["系统"], summary="健康检查")
def health_check(request: Request) -> HealthResponse:
    """前端用它判断"后端是否在线"；也是部署平台的探活地址。"""
    repo: HistoryRepository = request.app.state.repository
    return HealthResponse(
        data={
            "status": "ok",
            "version": settings.version,
            "database": repo.db_path.name,
            "record_count": repo.count(),
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        }
    )


# ===================================================================== 计算接口
@app.post(
    "/api/calculate",
    response_model=CalculateResponse,
    tags=["计算"],
    summary="计算表达式并保存历史",
    responses={
        400: {"model": ErrorResponse, "description": "表达式非法 / 除零 / 语法错误"},
        500: {"model": ErrorResponse, "description": "服务端异常"},
    },
)
def calculate(payload: CalculateRequest, request: Request) -> CalculateResponse:
    """后端唯一入口：算表达式 → 落库 → 返回带 id 的完整记录。"""
    repo: HistoryRepository = request.app.state.repository
    raw_expression = (payload.expression or "").strip()

    started_at = time.perf_counter()
    result_text = get_evaluator().evaluate(raw_expression)  # 失败会抛 CalculatorError
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)

    record = repo.create(expression=raw_expression, result=result_text)
    logger.info("计算成功：%s = %s（%.3f ms，id=%s）", raw_expression, result_text, elapsed_ms, record["id"])

    return CalculateResponse(data=CalculationData(**record, elapsed_ms=elapsed_ms))


# ===================================================================== 历史接口
@app.get(
    "/api/history",
    response_model=HistoryListResponse,
    tags=["历史"],
    summary="查询历史记录",
)
def list_history(
    request: Request,
    keyword: str | None = Query(default=None, max_length=100, description="按表达式或结果模糊搜索"),
    limit: int | None = Query(default=None, ge=1, le=500, description="返回条数上限，不传表示全部"),
    offset: int = Query(default=0, ge=0, description="偏移量，配合 limit 做分页"),
) -> HistoryListResponse:
    """按 id 倒序返回历史，最新一条在最前面。"""
    repo: HistoryRepository = request.app.state.repository
    normalized_keyword = keyword.strip() if keyword and keyword.strip() else None

    records = repo.list_all(keyword=normalized_keyword, limit=limit, offset=offset)
    total = repo.count(keyword=normalized_keyword)

    return HistoryListResponse(total=total, data=[HistoryRecord(**record) for record in records])


@app.delete(
    "/api/history/{record_id}",
    response_model=DeleteResponse,
    tags=["历史"],
    summary="删除单条历史记录",
    responses={404: {"model": ErrorResponse, "description": "记录不存在"}},
)
def delete_history(
    request: Request,
    record_id: int = Path(ge=1, description="要删除的历史记录 id"),
) -> DeleteResponse:
    """删除指定 id；不存在时返回 404 而不是静默成功，方便前端给出准确提示。"""
    repo: HistoryRepository = request.app.state.repository

    record = repo.get(record_id)
    if record is None:
        raise RecordNotFoundError(f"历史记录 {record_id} 不存在或已被删除")

    repo.delete(record_id)
    logger.info("删除历史记录 id=%s（%s = %s）", record_id, record["expression"], record["result"])

    return DeleteResponse(
        data=DeleteData(
            deleted_id=record_id,
            deleted=True,
            expression=record["expression"],
            result=record["result"],
        )
    )


@app.delete(
    "/api/history",
    response_model=ClearResponse,
    tags=["历史"],
    summary="清空全部历史记录（扩展功能）",
)
def clear_history(request: Request) -> ClearResponse:
    """一键清空历史。前端会先弹确认框，避免误触。"""
    repo: HistoryRepository = request.app.state.repository
    deleted_count = repo.clear()
    logger.info("清空历史记录，共删除 %s 条", deleted_count)
    return ClearResponse(data=ClearData(deleted_count=deleted_count))


if __name__ == "__main__":  # pragma: no cover - 本地调试入口
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("CALC_RELOAD", "0") == "1",
    )
