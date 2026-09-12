"""
tests/test_article_api.py —— 文章 CRUD 接口测试（走真实 HTTP 链路）

覆盖对象：POST/GET/PUT/DELETE /api/article（+ /health）。

设计要点：
1. 数据隔离：测试用独立库（conftest 已切换），topic 带 pytest- 前缀 + 随机串，
   每次运行产生全新数据——测试幂等（跑 100 次结果一致）。
2. 断言"稳定的不变量"：不硬编码 total 具体数字（测试库数据会积累），
   只断言结构存在（total 是 int、items 是 list）。
3. 边界全覆盖：422（空 topic / 缺 topic / id=0）、404（不存在的 id）都测。
"""
import uuid  # 生成随机串，保证每次测试的 topic 唯一

# 造唯一选题：pytest- + 8 位随机十六进制（不重复、可辨识）
def _new_topic() -> str:
    return f"pytest-{uuid.uuid4().hex[:8]}"


def test_健康检查(client):
    """正常路径：/health 返回 ok（部署环境存活探测）。"""
    resp = client.get("/health")
    assert resp.status_code == 200          # 200 = 服务活着
    assert resp.json() == {"status": "ok"}  # 响应体按约定


def test_创建文章成功(client):
    """正常路径：POST /api/article → 201 + 数据回显。"""
    topic = _new_topic()
    resp = client.post("/api/article", json={"topic": topic})  # 只传必填
    assert resp.status_code == 201           # 201 = 新资源创建
    data = resp.json()
    assert data["topic"] == topic            # 回显的 topic 与提交一致
    assert data["id"] > 0                    # 数据库自增 id 已生成


def test_创建文章topic为空返回422(client):
    """边界：空串触发 Pydantic min_length=1 校验。"""
    resp = client.post("/api/article", json={"topic": ""})
    assert resp.status_code == 422           # 422 = 参数校验失败


def test_创建文章缺topic返回422(client):
    """边界：请求体里根本没有 topic（必填字段缺失）。"""
    resp = client.post("/api/article", json={})
    assert resp.status_code == 422


def test_文章列表结构正确(client):
    """正常路径：list 接口返回 total + items 结构。"""
    resp = client.get("/api/article/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data                   # 总数字段存在
    assert isinstance(data["total"], int)    # 且是整数
    assert "items" in data                   # 列表字段存在
    assert isinstance(data["items"], list)


def test_查询不存在的文章返回404(client):
    """异常路径：id 超大（测试库不可能有）→ 404。"""
    resp = client.get("/api/article/999999999")
    assert resp.status_code == 404           # 全局异常处理器翻译的 404


def test_查询id为0返回422(client):
    """边界：id=0 违反 Path(..., gt=0) 校验，在进业务前就被拦下。"""
    resp = client.get("/api/article/0")
    assert resp.status_code == 422


def test_更新文章成功(client):
    """正常路径：PUT 部分更新，只改 topic。"""
    created = client.post("/api/article", json={"topic": _new_topic()}).json()  # 先建一条
    new_topic = _new_topic()                                                    # 新选题
    resp = client.put(f"/api/article/{created['id']}", json={"topic": new_topic})
    assert resp.status_code == 200
    assert resp.json()["topic"] == new_topic  # 更新后的值正确


def test_更新文章topic传null返回422(client):
    """边界：topic 列 NOT NULL，传 null 必须被业务层拦下（422）。"""
    created = client.post("/api/article", json={"topic": _new_topic()}).json()
    resp = client.put(f"/api/article/{created['id']}", json={"topic": None})
    assert resp.status_code == 422


def test_删除文章后再次查询404(client):
    """正常路径 + 联动：删除 204 → 再查同一 id 变 404（删除真的生效）。"""
    created = client.post("/api/article", json={"topic": _new_topic()}).json()
    # 删除：204 无响应体（断言状态码即可，不能 .json()）
    resp = client.delete(f"/api/article/{created['id']}")
    assert resp.status_code == 204
    # 联动验证：删过的 id 查不到了
    resp = client.get(f"/api/article/{created['id']}")
    assert resp.status_code == 404
