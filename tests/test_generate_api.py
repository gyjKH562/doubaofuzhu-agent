"""
tests/test_generate_api.py —— AI 生成/改写接口测试（mock 大模型）

覆盖对象：POST /api/generate、POST /api/refine。

设计要点：
1. 所有测试都挂 mock_llm 夹具——大模型调用被替换成假实现，
   generate/refine 走完整业务链路（查缓存→解析→写库），但零成本、零网络。
2. 验证缓存逻辑：同一 topic 第二次请求返回 200（命中缓存）。
3. 验证异常翻译：大模型故障 → 502；文章不存在 → 404；id=0 → 422。
"""
import uuid  # 生成随机选题

from services.llm_service import LLMError  # 模拟大模型故障时要抛的异常


def _new_topic() -> str:
    """造唯一选题（generate 的缓存按 topic 精确匹配，必须不重复）。"""
    return f"pytest-生成-{uuid.uuid4().hex[:8]}"


def test_生成新文章返回201(mock_llm, client):
    """正常路径：新选题 → 调模型 → 写库 → 201 + 两篇内容。"""
    topic = _new_topic()
    resp = client.post("/api/generate", json={"topic": topic})
    assert resp.status_code == 201            # 新资源创建
    data = resp.json()
    assert data["gzh_article"]                 # 公众号内容非空
    assert data["xhs_note"]                    # 小红书内容非空


def test_同一选题第二次请求命中缓存返回200(mock_llm, client):
    """核心缓存逻辑：同 topic 第二次不再调模型，直接返回已有记录（200）。"""
    topic = _new_topic()
    first = client.post("/api/generate", json={"topic": topic})
    assert first.status_code == 201            # 第一次：新生成
    second = client.post("/api/generate", json={"topic": topic})
    assert second.status_code == 200           # 第二次：缓存命中（0 成本）
    # 两条响应应是同一条记录（缓存返回库里的同一条）
    assert second.json()["id"] == first.json()["id"]


def test_生成接口空topic返回422(mock_llm, client):
    """边界：空选题触发 GenerateRequest 的 min_length=1 校验。"""
    resp = client.post("/api/generate", json={"topic": ""})
    assert resp.status_code == 422


def test_大模型故障时返回502(mock_llm, client, monkeypatch):
    """异常路径：模拟大模型挂掉 → 接口必须翻译成 502（不是裸 500）。"""
    async def fake_fail(messages: list[dict], max_tokens: int = 2000) -> str:
        """假故障：永远抛 LLMError（模拟网络/服务异常）。"""
        raise LLMError("模拟：大模型服务不可用")

    # 覆盖 mock_llm 的成功实现，换成故障实现（monkeypatch 后设覆盖先设）
    monkeypatch.setattr("services.generate_service.call_llm", fake_fail)
    resp = client.post("/api/generate", json={"topic": _new_topic()})
    assert resp.status_code == 502            # 全局异常处理器翻译 LLMError → 502


def test_改写文章成功返回200(mock_llm, client):
    """正常路径：建一条文章 → 改写 → 200 + 内容被替换为"改写结果"。"""
    # ① 先建一条有内容的文章（不走 generate，直接 POST article 更快）
    created = client.post(
        "/api/article",
        json={"topic": _new_topic(), "gzh_article": "原文公众号", "xhs_note": "原文小红书"},
    ).json()
    # ② 调用改写接口（mock 的"模型"返回固定内容）
    resp = client.post("/api/refine", json={"article_id": created["id"]})
    assert resp.status_code == 200
    data = resp.json()
    # ③ 断言内容被替换成了假模型返回的文本（证明改写链路真的走通）
    assert "假模型" in data["gzh_article"]


def test_改写不存在的文章返回404(mock_llm, client):
    """异常路径：article_id 不存在 → 404（refine_service 抛领域异常）。"""
    resp = client.post("/api/refine", json={"article_id": 999999999})
    assert resp.status_code == 404


def test_改写id为0返回422(mock_llm, client):
    """边界：article_id=0 违反 RefineRequest 的 gt=0 校验。"""
    resp = client.post("/api/refine", json={"article_id": 0})
    assert resp.status_code == 422


def test_生成接口topic超长返回422(mock_llm, client):
    """边界：超长 topic 触发 GenerateRequest 的 max_length=120 校验。"""
    long_topic = "长" * 121                    # 121 个"长"，超过上限 120
    resp = client.post("/api/generate", json={"topic": long_topic})   # ① 填路径和字段名
    assert resp.status_code == 422         # ② 填期望的状态码