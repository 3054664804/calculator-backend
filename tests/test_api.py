"""API 集成测试：用 FastAPI TestClient 直接打接口，覆盖三个必需接口 + 扩展接口。"""

from __future__ import annotations

# ------------------------------------------------------------------ 计算接口
def test_calculate_success_and_saved_to_history(client):
    response = client.post("/api/calculate", json={"expression": "3*(2+5)-4/2"})
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    record = body["data"]
    assert record["expression"] == "3*(2+5)-4/2"
    assert record["result"] == "19"
    assert isinstance(record["id"], int)
    assert record["created_at"]

    # 再查历史，刚才那条必须已经落库（证明是后端持久化，不是前端自己存的）
    history = client.get("/api/history").json()
    assert history["total"] == 1
    assert history["data"][0]["id"] == record["id"]


def test_calculate_accepts_chinese_operator_symbols(client):
    response = client.post("/api/calculate", json={"expression": "3 × 4"})
    assert response.status_code == 200
    assert response.json()["data"]["result"] == "12"
    # 数据库里保存的是"用户原文"，不是归一化之后的字符串
    assert response.json()["data"]["expression"] == "3 × 4"


def test_calculate_division_by_zero_returns_400_and_writes_nothing(client):
    response = client.post("/api/calculate", json={"expression": "1/0"})
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DIVISION_BY_ZERO"
    assert "0" in body["error"]["message"]

    # 失败的计算不能污染历史
    assert client.get("/api/history").json()["total"] == 0


def test_calculate_illegal_expression_returns_400(client):
    response = client.post("/api/calculate", json={"expression": "__import__('os')"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ILLEGAL_CHARACTER"


def test_calculate_empty_expression_returns_400(client):
    response = client.post("/api/calculate", json={"expression": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_EXPRESSION"


def test_calculate_syntax_error_returns_400(client):
    response = client.post("/api/calculate", json={"expression": "3+"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SYNTAX_ERROR"


def test_calculate_with_wrong_payload_type_returns_unified_error(client):
    response = client.post("/api/calculate", json={"expression": 12345})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ------------------------------------------------------------------ 历史接口
def test_history_is_ordered_by_newest_first(client):
    for expression in ["1+1", "2+2", "3+3"]:
        client.post("/api/calculate", json={"expression": expression})

    history = client.get("/api/history").json()
    assert history["total"] == 3
    expressions = [item["expression"] for item in history["data"]]
    assert expressions == ["3+3", "2+2", "1+1"]


def test_history_keyword_search(client):
    client.post("/api/calculate", json={"expression": "100+1"})
    client.post("/api/calculate", json={"expression": "2*3"})

    history = client.get("/api/history", params={"keyword": "100"}).json()
    assert history["total"] == 1
    assert history["data"][0]["expression"] == "100+1"


def test_history_pagination(client):
    for index in range(5):
        client.post("/api/calculate", json={"expression": f"{index}+1"})

    page = client.get("/api/history", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 5
    assert len(page["data"]) == 2


def test_history_empty_database(client):
    history = client.get("/api/history").json()
    assert history == {"success": True, "total": 0, "data": []}


# ------------------------------------------------------------------ 删除接口
def test_delete_single_record(client):
    first = client.post("/api/calculate", json={"expression": "1+1"}).json()["data"]
    second = client.post("/api/calculate", json={"expression": "2+2"}).json()["data"]

    response = client.delete(f"/api/history/{first['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["deleted_id"] == first["id"]

    remaining = client.get("/api/history").json()
    assert remaining["total"] == 1
    assert remaining["data"][0]["id"] == second["id"]


def test_delete_missing_record_returns_404(client):
    response = client.delete("/api/history/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECORD_NOT_FOUND"


def test_clear_history(client):
    for expression in ["1+1", "2+2"]:
        client.post("/api/calculate", json={"expression": expression})

    response = client.delete("/api/history")
    assert response.status_code == 200
    assert response.json()["data"]["deleted_count"] == 2
    assert client.get("/api/history").json()["total"] == 0


# ------------------------------------------------------------------ 系统接口
def test_health_check(client):
    body = client.get("/api/health").json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_unknown_route_returns_unified_404(client):
    response = client.get("/api/not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_404"


# ------------------------------------------------------------------ 持久化验证
def test_history_survives_repository_restart(db_file):
    """用两个独立的仓储对象访问同一个文件，模拟"后端重启"。

    这条用例是为了证明历史记录写在磁盘上，而不是内存 / 前端 localStorage 里。
    """
    from db import HistoryRepository

    first_repo = HistoryRepository(db_file)
    first_repo.init_schema()
    first_repo.create(expression="6*7", result="42")

    second_repo = HistoryRepository(db_file)  # 全新对象，没有共享内存
    records = second_repo.list_all()

    assert len(records) == 1
    assert records[0]["expression"] == "6*7"
    assert records[0]["result"] == "42"
