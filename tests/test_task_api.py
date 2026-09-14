"""
tests/test_task_api.py —— 异步任务接口测试（第 13 步）

覆盖对象：POST /api/tasks（提交任务）+ GET /api/tasks/{id}（查询状态）。

设计要点：
    1. 提交后任务在后台跑（asyncio.create_task），测试必须"轮询等待"
       任务完成——用 _wait_task_done 帮助函数（最多等 8 秒）。
    2. mock_llm 让后台任务秒完成（假模型不耗时），轮询很快返回。
    3. 缓存联动：同 topic 提交两次任务，第二个任务 is_cached=True
       且 article_id 与第一个一致（复用第 7 步的缓存逻辑）。
"""
import time  # 轮询等待用
import uuid  # 唯一选题

def _new_topic() -> str:
    """造唯一选题（任务内部走缓存逻辑，topic 必须不重复）。"""
    return f"pytest-任务-{uuid.uuid4().hex[:8]}"


def _wait_task_done(client, task_id: int, timeout: float = 8.0) -> dict:
    """轮询帮助函数：反复查任务状态，直到 done/failed 或超时。

    为什么需要轮询：任务在后台执行（异步），发起查询的瞬间
    可能还在 running——测试要模拟真实客户端的轮询行为。
    """
    deadline = time.time() + timeout        # 最晚截止时间
    while time.time() < deadline:
        data = client.get(f"/api/tasks/{task_id}").json()  # 查一次状态
        if data["status"] in ("done", "failed"):           # 终态：返回
            return data
        time.sleep(0.1)                    # 没到终态：等 0.1 秒再查
    raise AssertionError(f"任务 {task_id} 在 {timeout} 秒内未完成")  # 超时 = 测试失败


def test_提交任务立即返回202(mock_llm, client):
    """正常路径：提交任务 → 202 + task_id（不等生成完成）。"""
    resp = client.post("/api/tasks", json={"topic": _new_topic()})
    assert resp.status_code == 202            # 202 = 已受理（非 201/200）
    data = resp.json()
    assert data["task_id"] > 0                # 拿到任务 id（轮询的凭证）
    assert data["status"] in ("pending", "running", "done")  # 刚提交：还没终态


def test_任务执行完成状态为done(mock_llm, client):
    """正常路径：轮询到 done，结果里有生成的文章内容。"""
    task_id = client.post("/api/tasks", json={"topic": _new_topic()}).json()["task_id"]
    data = _wait_task_done(client, task_id)   # 轮询等待后台完成
    assert data["status"] == "done"           # 终态：成功
    assert data["result"]["gzh_article"]      # 公众号内容非空
    assert data["result"]["xhs_note"]         # 小红书内容非空
    assert data["result"]["is_cached"] is False  # 第一次生成：未命中缓存


def test_同选题第二个任务命中缓存(mock_llm, client):
    """缓存联动：同 topic 第二次提交 → is_cached=True 且是同一篇文章。"""
    topic = _new_topic()
    # 第一个任务：真实生成
    t1 = client.post("/api/tasks", json={"topic": topic}).json()["task_id"]
    d1 = _wait_task_done(client, t1)
    # 第二个任务：应命中缓存（第 7 步的 find_cached 在后台任务里同样生效）
    t2 = client.post("/api/tasks", json={"topic": topic}).json()["task_id"]
    d2 = _wait_task_done(client, t2)
    assert d2["result"]["is_cached"] is True          # 命中缓存
    assert d2["result"]["article_id"] == d1["result"]["article_id"]  # 同一篇文章


def test_查询不存在的任务返回404(mock_llm, client):
    """异常路径：task_id 不存在 → 404。"""
    resp = client.get("/api/tasks/999999999")
    assert resp.status_code == 404


def test_查询任务id为0返回422(mock_llm, client):
    """边界：task_id=0 违反 Path(gt=0) 校验 → 422（进业务前被拦）。"""
    resp = client.get("/api/tasks/0")
    assert resp.status_code == 422


def test_大模型故障时任务标记失败(mock_llm, client, monkeypatch):
    """异常路径：后台执行失败 → 任务状态 failed + error 记录原因。

    关键断言：后台协程的异常被捕获写进任务（不会让任务永远卡在 running）。
    """
    from services.llm_service import LLMError
    async def fake_fail(messages: list[dict], max_tokens: int = 2000) -> str:
        raise LLMError("模拟：大模型服务不可用")
    monkeypatch.setattr("services.generate_service.call_llm", fake_fail)

    task_id = client.post("/api/tasks", json={"topic": _new_topic()}).json()["task_id"]
    data = _wait_task_done(client, task_id)
    assert data["status"] == "failed"         # 终态：失败
    assert "模拟" in data["error"]            # 失败原因已记录
