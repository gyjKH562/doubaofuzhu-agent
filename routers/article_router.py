"""
article_router.py —— 文章域的全部接口

职责：只放文章相关的业务接口；main.py 只负责"装配"（创建 app、挂载本路由）。
APIRouter 是 FastAPI 的组织单元：prefix 统一路径前缀，tags 决定 /docs 里的分组名。
"""
import logging  # 日志：记录接口调用与错误，替代 print（生产可分级过滤）

from fastapi import APIRouter, Depends, HTTPException, Query, Response
#   - APIRouter：组织一组接口的路由对象
#   - Depends：依赖注入，框架自动提供 db 会话
#   - HTTPException：抛 HTTP 错误（404/422/500）
#   - Query：查询参数的校验与描述
#   - Response：手动构造响应（204 空响应必须用它）
from sqlalchemy import func, select  # func: COUNT 等聚合函数；select: 查询构造
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话的类型注解

from database import ArticleRecord, get_db  # ORM 模型 + 会话依赖（第 2 步产物）
from schemas.article_schemas import (
    ArticleCreate,   # 创建请求体：topic 必填
    ArticleListResp, # 分页响应体：total + items
    ArticleResp,     # 单条响应体：返回字段的裁剪出口
    ArticleUpdate,   # 更新请求体：全部可选（部分更新用）
)
from services.db_helpers import save_row

logger = logging.getLogger(__name__)  # 本模块日志器，格式沿用 main.py 的 basicConfig

# prefix：本路由下所有路径自动带上前缀，@router.post("") 实际就是 POST /api/article
# tags：决定 /docs 页面里的分组名，方便按域查找
router = APIRouter(prefix="/api/article", tags=["文章"])

async def _get_article_or_404(db: AsyncSession, article_id: int) -> ArticleRecord:
    """按 id 查文章，查不到直接抛 404。

    在 get/update/delete 三个接口里复用（Rule of Three：出现 3 次才抽）。
    下划线开头 = 模块私有函数约定：只在本文件内部使用，不对外暴露。
    """
    stmt = select(ArticleRecord).where(ArticleRecord.id == article_id)  # 构造查询
    result = await db.execute(stmt)      # 执行查询（异步必须 await）
    row = result.scalar_one_or_none()    # 0 条→None；1 条→对象；多条→报错
    if row is None:                      # 查不到：抛 404，由 FastAPI 转成 HTTP 响应
        raise HTTPException(status_code=404, detail="记录不存在")
    return row

@router.post("", response_model=ArticleResp, status_code=201, summary="创建文章")
async def create_article(req: ArticleCreate, db: AsyncSession = Depends(get_db)):
    """创建文章记录并写库。

    - req: 已通过 Pydantic 校验的请求体（非法数据到不了这里）
    - db: 依赖注入的会话，请求结束框架自动关闭
    """
    # 第 1 步：把请求数据装进 ORM 对象（此刻只是内存对象，还没进库）
    db_row = ArticleRecord(
        topic=req.topic,            # 必填字段，直接从请求体取
        gzh_article=req.gzh_article,  # 可选字段，没传则为 None
        xhs_note=req.xhs_note,
    )

    # 第 2 步：写库三部曲——add 登记、commit 落库、refresh 同步
    try:
        await save_row(db, db_row)  # 三部曲收敛成一行（add/commit/refresh/rollback 都在里面）
    except Exception as e:
        logger.error("创建失败: %s: %s", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="数据库保存失败，请稍后重试") from None
    return db_row

@router.get("/list", response_model=ArticleListResp, summary="文章列表")
async def list_articles(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数，上限 100"),
    keyword: str | None = Query(None, max_length=50, description="按选题模糊搜索"),
    db: AsyncSession = Depends(get_db),
):
    """分页查询文章列表，支持按选题关键词模糊搜索。

    - 查两趟：先 COUNT 总数（给前端算总页数），再查当前页数据
    - keyword 不传 = 不过滤，返回全部分页
    """
    # ① 动态构造查询条件：有 keyword 才加过滤，避免空条件
    conditions = []
    if keyword:
        # contains() 生成 SQL 的 LIKE '%keyword%'，且自动参数化（防 SQL 注入）
        conditions.append(ArticleRecord.topic.contains(keyword))

    # ② 第一趟查询：总数 COUNT(*)，忽略具体数据只要数量
    count_stmt = select(func.count()).select_from(ArticleRecord)
    if conditions:                    # 有条件才加 where（空列表会报错）
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()  # count 结果就是 int

    # ③ 第二趟查询：当前页数据
    offset = (page - 1) * page_size   # 核心公式：offset = (页码-1) × 每页条数
    list_stmt = (
        select(ArticleRecord)
        .where(*conditions)
        .order_by(ArticleRecord.id.desc())  # 按 id 倒序：最新记录在前
        .offset(offset)                     # 跳过前 offset 条
        .limit(page_size)                   # 只取 page_size 条
    )
    rows = (await db.execute(list_stmt)).scalars().all()  # 取全部结果成列表

    logger.info("查询完成：total=%d 返回 %d 条", total, len(rows))
    return ArticleListResp(total=total, items=rows)  # items 是 ORM 列表，自动转 JSON

@router.get("/{article_id}", response_model=ArticleResp, summary="查询单条")
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """按 id 查询单条文章记录；查不到由 _get_article_or_404 抛 404。"""
    return await _get_article_or_404(db, article_id)  # 复用：存在性检查 + 404

@router.put("/{article_id}", response_model=ArticleResp, summary="更新文章")
async def update_article(
    article_id: int,
    req: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """按 id 更新文章：只更新请求中显式传入的字段，不传的保持不变。

    - model_dump(exclude_unset=True) 区分"没传"和"传了 null"
    - topic 传 null 会置空 NOT NULL 列导致数据库报错，业务层提前拦下
    """
    # ① 先查存在性：不存在直接 404，不用继续
    row = await _get_article_or_404(db, article_id)

    # ② 只取"请求里明确写了"的字段（exclude_unset 是部分更新的灵魂）
    update_data = req.model_dump(exclude_unset=True)
    # ③ 业务校验：topic 列 NOT NULL，传 null 必须拦下（类型校验管不了 null）
    if "topic" in update_data and update_data["topic"] is None:
        raise HTTPException(status_code=422, detail="topic 不能为空")

    # ④ 逐字段写回 ORM 对象：setattr 动态赋值，不用手写 3 行
    for field, value in update_data.items():
        setattr(row, field, value)

    # ⑤ 写库三部曲（同创建接口；第 3 次出现时会抽成公共函数）
    try:
        await save_row(db, row)  # row 已持久化，save_row 里的 add 幂等
    except Exception as e:
        logger.error("更新失败 id=%d: %s: %s", article_id, type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="数据库更新失败，请稍后重试") from None
    return row

@router.delete("/{article_id}", status_code=204, summary="删除文章")
async def delete_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """按 id 删除；成功返回 204（无响应体），查不到返回 404。

    ⚠ 注意：删除后不要 refresh——行已从库中删除，刷新会报错。
    """
    row = await _get_article_or_404(db, article_id)  # 不存在先 404
    await db.delete(row)          # 标记删除（此时还没落库）
    try:
        await db.commit()         # 提交：真正执行 DELETE FROM ... WHERE id=?
    except Exception as e:
        await db.rollback()       # 失败回滚
        logger.error("删除失败 id=%d: %s: %s", article_id, type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="数据库删除失败，请稍后重试")
    return Response(status_code=204)  # 204 显式返回空响应，不带 body