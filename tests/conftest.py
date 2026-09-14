"""
tests/conftest.py —— pytest 全局夹具（fixture）

职责：
1. 在 import 任何业务代码【之前】把数据库指向"独立测试库"
   （绝不污染开发库 article_db_tutorial 的真实数据）
2. 提供两个全局夹具：
   - client：启动真实 FastAPI 应用（含建表）的测试客户端
   - mock_llm：把大模型调用替换成假实现（测试不花钱、不依赖网络、可重复）

⚠️ 文件顶部三行的顺序是命门：
   os.environ 设置必须在 `from main import app` 之前——
   因为 database.py / main.py 在 import 时就读 DATABASE_URL。
   顺序反了，测试就会连到开发库（污染真实数据）。
"""
import os  # 操作环境变量（先于业务代码）

# ① 指向独立测试库（库不存在没关系，ensure_test_db 夹具会自动创建）
TEST_DB_NAME = "article_db_tutorial_test"
os.environ["DATABASE_URL"] = (
    f"mysql+aiomysql://root:123456@127.0.0.1:3306/{TEST_DB_NAME}?charset=utf8mb4"
)

# ② 现在才允许 import 业务代码（此时 database.py 读到的是测试库地址）
import asyncio  # 同步夹具里跑异步建库逻辑

import pytest  # 测试框架
from sqlalchemy import text  # 原生 SQL 语句
from sqlalchemy.ext.asyncio import create_async_engine  # 异步引擎
from fastapi.testclient import TestClient  # FastAPI 官方测试客户端

from main import app  # 被测应用（DATABASE_URL 已指向测试库）

# ---- 测试专用：调大限流阈值 ----
# 为什么：接口测试聚焦业务正确性，不能被业务限流（30 次/分钟）干扰——
# 全量跑时轮询类测试请求多，会触发 429（响应没有 status 字段 → KeyError）。
# 限流器本身的逻辑已由 tests/test_rate_limiter.py 的 4 个单元测试覆盖，
# 这里旁路它符合"业务限制单独验证、接口测试不被干扰"的测试分层原则。
import main as main_module
main_module.rate_limiter.max_requests = 1_000_000  # 测试环境基本不触发


@pytest.fixture(scope="session", autouse=True)
def ensure_test_db():
    """确保测试库存在（session 级：整个测试过程只建一次）。

    为什么需要：SQLAlchemy 的 create_all 只建【表】不建【库】，
    MySQL 里库不存在会直接连接失败。所以先连"不带库名"的地址，
    执行 CREATE DATABASE IF NOT EXISTS 把库造出来。
    """
    async def _create() -> None:
        # 连到 MySQL 服务器（不指定库），执行建库语句
        engine = create_async_engine(
            "mysql+aiomysql://root:123456@127.0.0.1:3306/",  # 无库名 = 连接服务器
            pool_pre_ping=True,
        )
        async with engine.connect() as conn:
            # IF NOT EXISTS：库已存在就跳过（幂等，重复跑测试不报错）
            await conn.execute(
                text(f"CREATE DATABASE IF NOT EXISTS {TEST_DB_NAME} CHARACTER SET utf8mb4")
            )
        await engine.dispose()  # 用完释放连接池

    asyncio.run(_create())  # 同步夹具里用 asyncio.run 跑异步逻辑


@pytest.fixture(scope="session")
def client(ensure_test_db):
    """返回一个真实可调用的 API 客户端（session 级：整个测试过程共用一个）。

    为什么必须 session 级（这是踩坑后的修正）：
        aiomysql 的连接与"创建它的事件循环"绑定。TestClient 每次
        实例化都会新建一个事件循环——function 级会导致第二个测试
        用新循环去复用旧循环的连接池，直接崩（'NoneType' object has
        no attribute 'send'）。共享一个客户端 = 所有请求在同一循环
        里跑 = 连接池安全复用。

    用 with 包裹：进入时触发 lifespan（自动建表），退出时正常关闭，
    和真实运行 `python main.py` 的启动流程完全一致。
    """
    with TestClient(app) as c:  # with = 触发启动/关闭钩子（lifespan）
        yield c                 # 把客户端交给测试函数使用


@pytest.fixture
def mock_llm(monkeypatch):
    """把大模型调用替换成固定返回的假实现。

    为什么必须 mock：真实调用 = 花钱 + 慢 + 依赖网络 + 结果不可预测，
    测试要求"可重复、可断言"——固定返回的内容才能断言解析结果。

    为什么 patch 两个地方：generate_service 和 refine_service 都
    `from services.llm_service import call_llm`（导入符号），
    patch 源模块没用，必须 patch 到各自模块的引用上。
    """
    async def fake_call_llm(messages: list[dict], max_tokens: int = 2000) -> str:
        """假模型：不联网，固定返回符合格式约定的两段内容。"""
        # 与 generate_service 里的分隔符约定完全一致
        return "===公众号===\n测试公众号内容（来自假模型）\n===小红书===\n测试小红书笔记"

    # patch 到两个 service 模块各自的 call_llm 名字上（monkeypatch 自动还原）
    monkeypatch.setattr("services.generate_service.call_llm", fake_call_llm)
    monkeypatch.setattr("services.refine_service.call_llm", fake_call_llm)
