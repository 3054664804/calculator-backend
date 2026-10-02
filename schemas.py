"""请求 / 响应数据模型（Pydantic v2）。

统一响应约定（前端只认这一套结构）：

成功：
    {"success": true, "total": 12, "data": [...]}
失败：
    {"success": false, "error": {"code": "...", "message": "..."}}

为什么把 result 定义成 str 而不是 float：
  1. `10/3` 这类结果用 float 存会再次引入精度问题，字符串是"最终展示值"；
  2. 大整数（如 2**100）在 JS 里超过 Number.MAX_SAFE_INTEGER 会失真，
     用字符串传输可以原样展示。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------- 请求体
class CalculateRequest(BaseModel):
    """POST /api/calculate 的请求体。"""

    expression: str = Field(
        default="",
        description="待计算的表达式字符串，例如 3*(2+5)-4/2 或 3*-2",
        examples=["3*(2+5)-4/2"],
    )

    model_config = ConfigDict(json_schema_extra={"example": {"expression": "3*(2+5)-4/2"}})


# --------------------------------------------------------------------- 数据体
class HistoryRecord(BaseModel):
    """一条计算历史（对应数据库 calculation_history 表的一行）。"""

    id: int = Field(description="记录 id（数据库自增主键）")
    expression: str = Field(description="用户输入的原始表达式")
    result: str = Field(description="后端计算得到的结果")
    created_at: str = Field(description="创建时间，ISO 8601（UTC）")


class CalculationData(HistoryRecord):
    """计算成功后的返回数据，额外带上后端耗时便于性能观察。"""

    elapsed_ms: float | None = Field(default=None, description="后端计算耗时（毫秒）")


class DeleteData(BaseModel):
    """删除单条历史的结果。"""

    deleted_id: int = Field(description="被删除的记录 id")
    deleted: bool = Field(default=True, description="是否删除成功")
    expression: str | None = Field(default=None, description="被删除记录的表达式（便于前端提示）")
    result: str | None = Field(default=None, description="被删除记录的结果")


class ClearData(BaseModel):
    """清空历史的结果（扩展功能）。"""

    deleted_count: int = Field(description="被清空的记录数量")


# --------------------------------------------------------------------- 响应体
class CalculateResponse(BaseModel):
    success: bool = True
    data: CalculationData


class HistoryListResponse(BaseModel):
    success: bool = True
    total: int = Field(description="符合筛选条件的记录总数")
    data: list[HistoryRecord]


class DeleteResponse(BaseModel):
    success: bool = True
    data: DeleteData


class ClearResponse(BaseModel):
    success: bool = True
    data: ClearData


class HealthResponse(BaseModel):
    success: bool = True
    data: dict


class ErrorDetail(BaseModel):
    code: str = Field(description="稳定的错误码，前端可据此做特殊处理")
    message: str = Field(description="给用户看的中文错误提示")
    expression: str | None = Field(default=None, description="触发错误的表达式")


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
