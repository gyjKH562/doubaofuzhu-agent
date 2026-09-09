# fastapi最小骨架 main.py
"""配套env:
"APP_HOST=127.0.0.1
APP_PORT=8000
SERVICE_NAME=ai-chat-backend
SERVICE_VERSION=0.1.0"""
import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI

# 加载本地环境变量，放在最上方
load_dotenv()

# 全局日志配置，整个程序只执行一次
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 读取基础配置
SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-chat-backend")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)

@app.get("/health", summary="健康检查")
async def health_check() -> dict:
    return {"status": "OK"}

@app.get("/", summary="服务信息")
async def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn

    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    logger.info("服务启动: http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port)



"""
database.py —— SQLAlchemy 2.0 异步骨架（通用模板，跨项目复用）

使用步骤：
1. 复制本文件到新项目
2. 把底部"你的模型"替换成新项目的业务模型
3. 在 .env 配置 DATABASE_URL（或改 ASYNC_DB_URL 的默认值）
4. 在 main.py 的 lifespan 里调用 create_tables()
"""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv()

# ── 1. 连接串：环境变量优先，默认值兜底 ──
ASYNC_DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://user:pass@127.0.0.1:3306/your_db?charset=utf8mb4",
)

# ── 2. 异步引擎：连接池总开关 ──
async_engine = create_async_engine(ASYNC_DB_URL)

# ── 3. 会话工厂：开"工作窗口"的工具 ──
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)

# ── 4. FastAPI 公共依赖：每个请求一个会话，自动开关 ──
async def get_db():
    """为每个请求提供数据库会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session

# ── 5. 时间戳工具：Python 3.12+ 兼容的 UTC 时间 ──
def utc_now() -> datetime:
    """当前 UTC 时间（去掉时区标记，兼容 MySQL DATETIME）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ── 6. 所有模型的公共基类 ──
class Base(DeclarativeBase):
    """ORM 模型基类。"""
    pass

# ═══════════════ 替换区：以下换成你的业务模型 ═══════════════
# 示例模型展示三种最常见的列类型：主键 / 字符串 / 时间戳
class YourModel(Base):
    """你的业务表：改表名、改字段，其余不动。"""

    __tablename__ = "your_table"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

# ── 7. 建表：启动时调用，扫描 Base 下所有模型 ──
async def create_tables() -> None:
    """建表函数：表已存在则跳过，不删除已有数据。"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ═══════════════════════════════════════════════════════════
# 模板 C：请求/响应模型（schemas）—— FastAPI 项目必备
# 适用场景：任何"接收数据 + 返回数据"的接口
# 使用步骤：复制本段 → 把 Item 换成你的业务名（Article/User/Order...）→ 改字段
# ═══════════════════════════════════════════════════════════
# 需要补的 import（若文件里没有）：
#   from datetime import datetime
#   from pydantic import BaseModel, ConfigDict, Field

class ItemCreate(BaseModel):
    """创建资源的请求体：客户端提交的 JSON 格式。

    - 请求模型只收"业务字段"，不收 id/时间戳（那是服务器生成的）
    - 必填字段用 ...；可选字段给默认值 None
    - 字段名是前后端契约：客户端必须按这里的名字传
    """
    name: str = Field(..., min_length=1, max_length=50, description="名称（必填）")
    remark: str | None = Field(None, description="备注（可选，不传则为 null）")


class ItemResp(BaseModel):
    """资源响应体：接口返回的统一格式（与请求模型分离，见使用说明）。"""
    # from_attributes=True：允许 ORM 对象直接转成响应模型
    model_config = ConfigDict(from_attributes=True)

    id: int                  # 服务器生成的主键
    name: str
    remark: str | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════
# 模板 D：创建接口（POST + 201 + response_model）—— 所有增改接口的骨架
# 前置依赖：database.py 的 get_db + 你的 ORM 模型 + 模板 C 的 schemas
# 使用步骤：复制本段 → 改路径/函数名/模型名 → 改字段映射
# ═══════════════════════════════════════════════════════════
# 需要补的 import（若文件里没有）：
#   from fastapi import Depends, HTTPException
#   from sqlalchemy.ext.asyncio import AsyncSession
#   from database import YourModel, get_db

@app.post("/api/items", response_model=ItemResp, status_code=201, summary="创建")
async def create_item(req: ItemCreate, db: AsyncSession = Depends(get_db)):
    """创建一条记录并写库，返回带 id 的完整记录。"""
    db_row = YourModel(name=req.name, remark=req.remark)
    db.add(db_row)                    # ① 登记进会话（内存，未落库）
    try:
        await db.commit()             # ② 真正写库，id 在此生成
        await db.refresh(db_row)      # ③ 从库重读，拿到权威值
    except Exception as e:
        await db.rollback()           # 失败：撤销未提交改动
        logger.error("保存失败，错误=%s: %s", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="数据库保存失败，请稍后重试")
    return db_row


# ═══════════════════════════════════════════════════════════
# 模板 E：写库三部曲（独立速查卡，增改接口通用）
# ═══════════════════════════════════════════════════════════
#   db.add(obj)        # 1. 登记（对象进会话，还没写库）
#   await db.commit()  # 2. 落库（INSERT 执行，id 生成）
#   await db.refresh(obj)  # 3. 同步（从库重读权威值）
#   except 时: await db.rollback()  # 4. 失败回滚
# 记忆口诀：先登记，再提交，失败就回滚。
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 F：单条查询（按主键查详情）—— 所有"查详情"接口通用
# 使用：复制 → 改模型/字段/路径 → 改 404 文案
# ═══════════════════════════════════════════════════════════
# 需要补的 import：
#   from fastapi import HTTPException
#   from sqlalchemy import select

@app.get("/api/items/{item_id}", response_model=ItemResp, summary="查询单条")
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """按主键查询单条；查不到返回 404（让调用方明确知道资源不存在）。"""
    stmt = select(YourModel).where(YourModel.id == item_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()  # 0 条 → None；多条 → 报错（数据异常及早暴露）
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return row


# ═══════════════════════════════════════════════════════════
# 模板 G：分页查询（count + offset/limit）—— 所有列表接口通用骨架
# 使用：复制 → 改模型/字段/路径 → 改筛选字段
# ═══════════════════════════════════════════════════════════
# 需要补的 import：
#   from fastapi import Query
#   from sqlalchemy import func, select

@app.get("/api/items", response_model=ItemListResp, summary="列表分页")
async def list_items(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数，上限 100"),
    keyword: str | None = Query(None, max_length=50, description="按名称模糊搜索"),
    db: AsyncSession = Depends(get_db),
):
    """分页查询列表，支持按关键词模糊搜索（参数化查询，防 SQL 注入）。"""
    # ① 动态构造条件：有筛选才加，避免空条件
    conditions = []
    if keyword:
        conditions.append(YourModel.name.contains(keyword))  # LIKE '%kw%' 且自动参数化
    # ② 第一趟查询：总数（供前端算总页数）
    count_stmt = select(func.count()).select_from(YourModel)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()
    # ③ 第二趟查询：当前页数据
    offset = (page - 1) * page_size       # 核心公式：offset = (页码-1) × 每页条数
    list_stmt = (
        select(YourModel)
        .where(*conditions)
        .order_by(YourModel.id.desc())    # 最新在前
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(list_stmt)).scalars().all()
    return ItemListResp(total=total, items=rows)


# ═══════════════════════════════════════════════════════════
# 模板 H：动态条件构造（速查卡）—— 带筛选的查询通用手法
# ═══════════════════════════════════════════════════════════
#   conditions = []                                    # 空列表 = 不过滤
#   if keyword:
#       conditions.append(YourModel.name.contains(kw)) # LIKE '%kw%'（参数化）
#   if start_time:
#       conditions.append(YourModel.created_at >= t)   # 时间范围
#   stmt = select(YourModel).where(*conditions)        # 列表展开为多个条件
# ⚠ where() 至少需要一个条件；conditions 为空时必须跳过 where()（见模板 G）
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 I：APIRouter 组织模板 —— FastAPI 项目标准分层方式
# 适用：接口超过 3 个时，把业务接口从 main.py 抽到 routers/ 下
# 使用：复制 → 改 prefix/tags/路径 → 把接口函数搬进来
# ═══════════════════════════════════════════════════════════
# routers/your_router.py
#   from fastapi import APIRouter, Depends, HTTPException, Query, Response
#   from sqlalchemy import func, select
#   from sqlalchemy.ext.asyncio import AsyncSession
#   from database import YourModel, get_db
#   from schemas.your_schemas import ...
#
#   router = APIRouter(prefix="/api/your", tags=["你的域"])
#
#   @router.post("", response_model=..., status_code=201)
#   async def create(...): ...
#   # ... 更多接口 ...
#
# main.py 里只需两行接入：
#   from routers.your_router import router as your_router
#   app.include_router(your_router)
#
# 关键规则：
#   - prefix 统一路径前缀：@router.post("") 实际是 POST /api/your
#   - 静态路径（如 /list）必须声明在动态路径（如 /{id}）之前
#   - main.py 只做"装配"：创建 app + include_router，不写业务
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 J：部分更新（PUT + exclude_unset + setattr）—— 所有更新接口通用
# 适用：更新时"传什么改什么、没传的不动"，避免误清空字段
# 使用：复制 → 改模型/字段 → 加你的业务校验
# ═══════════════════════════════════════════════════════════
# schemas 里的更新请求模型（全部字段可选）：
#   class ItemUpdate(BaseModel):
#       name: str | None = Field(None, min_length=1, max_length=50)
#       remark: str | None = Field(None)
#
# 接口实现：
#   @router.put("/{item_id}", response_model=ItemResp)
#   async def update_item(item_id: int, req: ItemUpdate,
#                         db: AsyncSession = Depends(get_db)):
#       row = await _get_or_404(db, item_id)          # 先查存在性
#       # 只取"请求里显式写了"的字段（灵魂：exclude_unset）
#       update_data = req.model_dump(exclude_unset=True)
#       # 业务校验：NOT NULL 列不能被置空（类型校验管不了 null）
#       if "name" in update_data and update_data["name"] is None:
#           raise HTTPException(status_code=422, detail="name 不能为空")
#       for field, value in update_data.items():      # 逐字段写回
#           setattr(row, field, value)
#       await db.commit()
#       await db.refresh(row)
#       return row
#
# ⚠ 三个高频坑：忘记 exclude_unset（变全量清空）、
#    NOT NULL 列传 null（500）、删除后 refresh（报错）
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 K：内部复用函数（Rule of Three）—— 查存在性逻辑第 3 次出现时抽
# 适用：多个接口都要"按 id 查 + 不存在抛 404"
# 使用：复制 → 改模型 → 放 router 文件顶部
# ═══════════════════════════════════════════════════════════
#   async def _get_or_404(db: AsyncSession, item_id: int) -> YourModel:
#       """按 id 查记录，查不到直接抛 404。多个接口复用。"""
#       stmt = select(YourModel).where(YourModel.id == item_id)
#       result = await db.execute(stmt)
#       row = result.scalar_one_or_none()  # 0 条→None；多条→报错（数据异常及早暴露）
#       if row is None:
#           raise HTTPException(status_code=404, detail="记录不存在")
#       return row
#
# 命名约定：
#   - 下划线开头 = 模块私有，只在本文件内部使用
#   - 何时抽：同一逻辑出现第 3 次（Rule of Three）——第 1、2 次先忍
# ═══════════════════════════════════════════════════════════
