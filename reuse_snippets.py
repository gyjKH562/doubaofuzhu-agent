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


# ═══════════════════════════════════════════════════════════
# 模板 L：LLM 调用封装（OpenAI SDK 版）—— 接任何大模型项目的通用骨架
# 适用：DeepSeek / 通义 / 智谱 / OpenAI 等兼容 OpenAI 协议的服务
# 方案权衡（为什么用 SDK 而不是手写 aiohttp）：
#   SDK 内置：重试(max_retries)、超时(Timeout)、连接池(单例)、异常分类
#   手写 aiohttp 的价值：看懂 SDK 替你做了什么（HTTP 底层/异步原理）
#   结论：原理懂了之后，生产代码用 SDK——少写几十行、少踩协议细节的坑
# 使用：复制 → 改环境变量名/模型名 → 改你的业务参数
# ═══════════════════════════════════════════════════════════
# 需要补的 import / 环境变量：
#   import openai
#   from dotenv import load_dotenv
#   .env 里：YOUR_API_KEY / YOUR_BASE_URL / YOUR_MODEL

#   API_KEY = os.getenv("YOUR_API_KEY", "")
#   BASE_URL = os.getenv("YOUR_BASE_URL", "https://api.deepseek.com")
#   MODEL = os.getenv("YOUR_MODEL", "deepseek-chat")
#
#   class LLMError(Exception):
#       """大模型调用失败的自定义异常，上层只认识它。"""
#
#   _client = None
#
#   def get_client() -> openai.AsyncOpenAI:
#       """懒加载单例：AsyncOpenAI 内部有连接池，是"重对象"，只创建一次。"""
#       global _client
#       if _client is None:
#           _client = openai.AsyncOpenAI(
#               api_key=API_KEY,
#               base_url=BASE_URL,
#               timeout=openai.Timeout(120, connect=10),
#               max_retries=2,   # SDK 内置重试
#           )
#       return _client
#
#   async def call_llm(messages: list[dict], max_tokens: int = 2000) -> str:
#       if not API_KEY:
#           raise LLMError("未配置 API_KEY")
#       try:
#           resp = await get_client().chat.completions.create(
#               model=MODEL, messages=messages, max_tokens=max_tokens)
#       except openai.AuthenticationError as e:      # 401 认证失败
#           raise LLMError("API key 无效") from None
#       except openai.APITimeoutError:               # 超时（必须先于连接错误）
#           raise LLMError("调用超时，请稍后重试") from None
#       except openai.APIConnectionError:            # 网络错误
#           raise LLMError("网络错误，无法连接服务") from None
#       except openai.APIStatusError as e:           # 429/500 等
#           raise LLMError(f"接口返回 {e.status_code}") from None
#       except openai.APIError:                      # 兜底
#           raise LLMError("大模型调用失败") from None
#       content = resp.choices[0].message.content
#       if not content:                              # 思考模型可能返回空
#           raise LLMError("大模型返回空内容")
#       return content
#
# ⚠ 两个关键坑：
#   1. APITimeoutError 必须写在 APIConnectionError 之前（超时是连接错误的子类）
#   2. key 未配置时不要 import 阶段就崩——用懒加载 + call_llm 开局检查
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 M：自定义异常分类模式 —— 所有"调用外部服务"的封装通用
# 适用：HTTP 服务 / 第三方 API / 数据库等外部依赖的失败信号
# 思路：对外抛一个干净的领域异常（调用方只认识它），对内打完整日志
# ═══════════════════════════════════════════════════════════
#   class MyServiceError(Exception):
#       """外部服务调用失败。上层 except MyServiceError 统一处理。"""
#
#   try:
#       ...  # 调用外部服务
#   except TimeoutError as e:
#       logger.error("外部服务超时：%s", e)      # 完整原因进日志
#       raise MyServiceError("外部服务超时") from None  # 干净信号给上层
#   except ConnectionError as e:
#       logger.error("外部服务连接失败：%s", e)
#       raise MyServiceError("无法连接外部服务") from None
#
# 要点：
#   - from None：丢弃原始异常链（日志已有原因，异常信息保持干净）
#   - 分类粒度：让调用方知道"超时该重试 / 401 换 key / 网络查环境"
#   - 统一的"未知错误"是排查地狱——错误必须分得出类别
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 N：懒加载单例模式 —— 重对象只创建一次
# 适用：连接池 / HTTP 客户端 / 数据库客户端等"贵"且可复用的对象
# 对比：每次调用新建 = 每次都付全价；全局单例 = 只付一次
# ═══════════════════════════════════════════════════════════
#   _client = None               # 模块级私有：存放单例
#
#   def get_client() -> SomeHeavyClient:
#       """懒加载：第一次调用才真正创建（import 时不创建，避免副作用）。"""
#       global _client
#       if _client is None:
#           _client = SomeHeavyClient(...)   # 真正的创建在这里
#       return _client
#
# 为什么"懒"而不是模块加载时直接建：
#   - 避免 import 阶段的副作用（如 key 未配置时 import 就崩）
#   - 提高启动速度（用到了才创建）
#   - 测试友好（可随时重置 _client = None 重新创建）
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 O：业务编排 service 骨架（缓存优先）—— 所有"先查再干"业务通用
# 适用：AI 生成 / 外部服务调用 / 任何"重复请求不应重复花钱/重复劳动"的业务
# 分层铁律：service 不 import FastAPI（不出现 HTTPException/Response）
#           ——业务异常向上抛，由 router 翻译成 HTTP 状态码
# ═══════════════════════════════════════════════════════════
#   async def find_cached(db, key) -> Model | None:
#       """查缓存：命中条件自己定义（本项目的口径：同 topic 且内容非空）。"""
#       stmt = (select(Model).where(Model.key == key, ...)
#               .order_by(Model.id.desc()).limit(1))
#       return (await db.execute(stmt)).scalar_one_or_none()
#
#   async def do_business(db, key) -> tuple[Model, bool]:
#       """主流程：缓存优先。返回 (结果, 是否命中缓存)。"""
#       cached = await find_cached(db, key)     # ① 查缓存
#       if cached is not None:                  # 命中：直接返回，零成本
#           return cached, True
#       result = await expensive_call(key)      # ② 未命中：做真正的工作
#       db.add(result)                          # ③ 写库（下次就是缓存）
#       await db.commit()
#       return result, False
#
# 缓存哲学：能用查询解决的，先不引组件（Redis 是数据量大之后的选项）
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 P：函数返回值携带"标志位"（元组模式）
# 适用：调用方需要区分"新建 vs 命中 / 成功 vs 降级"等二元结果时
# 对比：改全局变量/再查一次 → 有状态/多一次 IO；返回元组 → 无副作用
# ═══════════════════════════════════════════════════════════
#   async def get_or_create(db, key) -> tuple[Model, bool]:
#       """返回 (记录, 是否已存在)。"""
#       existing = await find(db, key)
#       if existing:
#           return existing, True        # 已存在
#       new = Model(...)
#       db.add(new)
#       await db.commit()
#       return new, False                # 本次新建
#
#   # 调用方解包 + 按标志决定行为：
#   row, is_existing = await get_or_create(db, key)
#   response.status_code = 200 if is_existing else 201
#
# 要点：
#   - 改函数签名后要全局搜调用点（本项目 generate_article 只有一处调用，
#     但项目大了这是必踩的坑）
#   - 元组元素顺序固定，解包时按位置对齐，别把 True/False 搞反
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 Q：router 异常翻译表 —— 所有调外部服务的接口通用
# 适用：AI 接口 / 第三方 API 代理 / 任何"上游可能挂"的接口
# 口诀：上游错 → 502；格式错 → 502；自己错 → 500
# ═══════════════════════════════════════════════════════════
#   try:
#       result = await do_business(db, req.key)
#   except UpstreamError as e:                 # 上游服务（大模型/第三方）挂了
#       logger.error("失败（上游）：%s", e)
#       raise HTTPException(502, detail="上游服务不可用") from None
#   except ValueError as e:                    # 上游返回的数据格式不对
#       logger.error("失败（解析）：%s", e)
#       raise HTTPException(502, detail="上游返回格式异常") from None
#   except Exception as e:                     # 我们自己的问题（写库失败等）
#       logger.error("失败（内部）：%s: %s", type(e).__name__, str(e))
#       raise HTTPException(500, detail="内部错误") from None
#   return result
#
# 为什么 502 vs 500 要分清：
#   运维看到 502 会查上游服务，看到 500 会查你的代码——错误归属影响排障方向
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 R：写库统一入口 save_row —— SQLAlchemy 异步项目通用
# 适用：所有增/改（写库三部曲：add → commit → refresh，失败回滚）
# 边界：删除场景不要用（删除后 refresh 会报错）
# ═══════════════════════════════════════════════════════════
#   import logging
#   from sqlalchemy.ext.asyncio import AsyncSession
#   logger = logging.getLogger(__name__)
#
#   async def save_row(db: AsyncSession, row) -> None:
#       """写库三部曲封装：add + commit + refresh，失败自动回滚。"""
#       db.add(row)                # ① 登记（新建=INSERT；已持久化对象重复 add 幂等）
#       try:
#           await db.commit()      # ② 落库
#           await db.refresh(row)  # ③ 重读权威值（id/时间戳）
#       except Exception as e:
#           await db.rollback()    # 失败回滚，不留半截数据
#           logger.error("写库失败: %s: %s", type(e).__name__, str(e))
#           raise                  # 原样抛出，由 router 层转 500
#
# 调用方（router）：
#   try:
#       await save_row(db, row)
#   except Exception:
#       raise HTTPException(500, "数据库保存失败") from None
#
# 收益：写库逻辑只在一处——以后加审计、加日志、换驱动只改这一个函数
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 S：service 层"查不到"自定义异常 —— 分层项目的通用模式
# 适用：业务编排在 service（不 import FastAPI）时表达"资源不存在"
# ═══════════════════════════════════════════════════════════
#   class XxxNotFoundError(Exception):
#       """业务目标不存在的信号。router 捕获后翻译成 HTTP 404。"""
#
#   # service 层（不 import FastAPI）：
#   async def do_business(db, target_id):
#       row = await db.get(Model, target_id)   # 主键查询：查不到返回 None
#       if row is None:
#           raise XxxNotFoundError(f"目标不存在: {target_id}")
#       ...
#
#   # router 层（翻译成 HTTP）：
#   try:
#       result = await do_business(db, req.target_id)
#   except XxxNotFoundError:
#       raise HTTPException(404, "目标不存在") from None
#
# 为什么 service 不直接抛 HTTPException：
#   分层铁律——service 不知道 HTTP 的存在（可被接口/脚本/测试调用）；
#   "同一事实、两种信号"：router 用 HTTPException，service 用自定义异常
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 T：全局异常处理器配置 —— FastAPI 项目的标准错误处理骨架
# 适用：所有 FastAPI 项目（三件套：异常集中定义 + 全局注册 + router 放手）
# ═══════════════════════════════════════════════════════════
#   # ① 集中定义业务异常（services/exceptions.py）
#   class ArticleNotFoundError(Exception):   # → 404
#       """资源不存在的信号。"""
#   class ModelOutputError(Exception):        # → 502
#       """上游输出格式异常的信号。"""
#   class DBError(Exception):                 # → 500
#       """数据库写操作失败的信号。"""
#
#   # ② 全局注册（main.py，app 实例上）
#   from fastapi.responses import JSONResponse
#   @app.exception_handler(ArticleNotFoundError)
#   async def _not_found(request, exc):
#       logger.warning("资源不存在: %s", exc)
#       return JSONResponse(status_code=404, content={"detail": str(exc)})
#   # ModelOutputError → 502 / DBError → 500 同理
#
#   # ③ router 彻底放手（没有 try/except）
#   @router.post("/xxx")
#   async def xxx(req: Req, db=Depends(get_db)):
#       row = await service_do(db, req.id)   # 异常全交给全局处理器
#       return row
#
# 铁律：router 里不能再留 except Exception——它会先接住领域异常，
# 全局处理器永远收不到（这是最常见的"502 变 500"原因）
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# 模板 U：专用业务异常 vs 裸内建异常 —— 精确错误信号
# 适用：任何"解析/处理失败需要精确归因"的代码
# ═══════════════════════════════════════════════════════════
#   # ❌ 裸内建异常的问题
#   raise ValueError("模型输出缺少分隔符")
#   # → 业务代码里任何地方都可能抛 ValueError（int() 转换、参数检查……），
#   #   全局/上层接住它时无法区分"这是模型问题"还是"无关错误"
#
#   # ✅ 专用异常
#   class ModelOutputError(Exception):
#       """模型输出格式异常（语义 = 只有这一种情况才抛它）"""
#   raise ModelOutputError("模型输出缺少分隔符")
#   # → 上层 except ModelOutputError 时，命中即模型问题，100% 精确
#
# 原则：内建异常表达"语法/通用错误"；业务语义用自定义异常表达。
# 收益：错误分类一处定（异常类）、翻译一处做（处理器），排障方向清晰。
# ═══════════════════════════════════════════════════════════
