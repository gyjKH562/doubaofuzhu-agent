"""
database.py —— 数据库连接与 ORM 模型定义

职责：
1. 创建异步引擎（连接池管理者）和会话工厂
2. 定义"文章记录"表对应的 ORM 模型 ArticleRecord
3. 提供公共依赖 get_db（每个请求自动开关会话）
4. 提供建表函数 create_tables（启动时调用）
"""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
# 列类型：String 定长字符串 / Text 长文本 / DateTime 时间
from sqlalchemy import DateTime, String, Text
# 异步三件套：引擎 / 会话工厂 / 会话类型（用于类型标注）
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
# ORM 现代写法：DeclarativeBase 模型基类 / Mapped 类型标注 / mapped_column 定义列
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 加载 .env（必须在读取环境变量之前）
load_dotenv()

# 连接串从环境变量读，没配则用默认值兜底（本地开发）
ASYNC_DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:<your_password>@127.0.0.1:3306/article_db?charset=utf8mb4",
)

# ---------- 异步引擎：连接池的"总开关" ----------
# 应用启动时创建一次，全程复用；内部自动维护连接池，
# 需要连接时从池里取，用完放回，不反复建立 TCP 连接
async_engine = create_async_engine(ASYNC_DB_URL)

# ---------- 会话工厂：开"工作窗口"的工具 ----------
# expire_on_commit=False：commit 之后对象上的属性依然可读
# （默认行为是 commit 后"过期"，再读属性会触发一次查询，新手常被这个坑到）
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)

# ---------- 公共数据库依赖（FastAPI 依赖注入） ----------
async def get_db():
    """为每个请求提供一个数据库会话，请求结束自动关闭。

    用 yield 而不是 return：async with 保证了无论接口成功还是抛异常，
    会话都会被关闭——这就是"依赖注入管理生命周期"的价值。
    """
    async with AsyncSessionLocal() as session:
        yield session

def utc_now() -> datetime:
    """获取当前 UTC 时间（去掉时区信息，兼容 MySQL 的 DATETIME）。

    说明：datetime.utcnow() 在 Python 3.12+ 已弃用，
    这里用 datetime.now(timezone.utc) 的等价写法避免弃用警告。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ---------- ORM 模型 ----------
# 所有模型类的公共基类：以后新增表都继承它
class Base(DeclarativeBase):
    """ORM 模型基类：SQLAlchemy 通过它扫描并注册所有表定义。"""
    pass

class ArticleRecord(Base):
    """文章记录表：每生成/改写一篇文章，就插入一行。"""

    __tablename__ = "article_record"

    # 主键：自增整数，每插入一行自动 +1
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 选题/标题：可变长字符串，最多 255 字符
    topic: Mapped[str] = mapped_column(String(255))
    # 公众号文章：长文本，允许为空（大模型可能返回空）
    gzh_article: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 小红书笔记：长文本，允许为空
    xhs_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    # 创建时间：插入时自动填当前时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    # 更新时间：插入时填当前时间，每次更新自动刷新
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

class TaskRecord(Base):
    """异步任务记录表：提交一个生成任务就插入一行（第 13 步）。

    为什么需要这张表：异步任务 = 请求先返回 task_id，任务在后台跑，
    客户端靠查这张表得知"做到哪一步了"（状态机）。
    状态流转：pending（排队）→ running（执行中）→ done（成功）/ failed（失败）
    """

    __tablename__ = "task_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255))          # 要生成的选题
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 任务状态（见 task_service 常量）
    result: Mapped[str | None] = mapped_column(Text(), nullable=True)   # 成功结果（JSON 字符串）
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)    # 失败原因
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

async def create_tables() -> None:
    """建表函数：启动时调用，已存在的表自动跳过（不删除、不动已有数据）。"""
    async with async_engine.begin() as conn:
        # run_sync：把同步的建表逻辑放到异步连接上执行
        # create_all：扫描 Base 下所有模型，把缺失的表建出来
        await conn.run_sync(Base.metadata.create_all)



