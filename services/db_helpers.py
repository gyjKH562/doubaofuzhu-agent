"""
db_helpers.py —— 数据库操作公共函数

为什么抽出来：写库三部曲（add → commit → refresh，失败回滚）
在 create / update / generate 三处重复出现（Rule of Three），
抽成统一入口 save_row：以后写库只走这一个函数。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession  # 会话类型注解

logger = logging.getLogger(__name__)

async def save_row(db: AsyncSession, row) -> None:
    """写库三部曲封装：add + commit + refresh，失败自动回滚。

    参数：
        db: 数据库会话（FastAPI 依赖注入的那个）
        row: 要保存的 ORM 对象（新建的或已持久化的都可以）
    异常：
        写库失败时抛出原始异常（由调用方 router 转 HTTP 500）

    为什么 add 也放进来：对已持久化的对象（update 场景）重复 add 是
    幂等的（SQLAlchemy 忽略），所以增改场景可以统一走这个函数。
    注意边界：删除场景不要用它——删除后 refresh 会报错。
    """
    db.add(row)                   # ① 登记进会话（新建=INSERT，已存在=UPDATE，幂等）
    try:
        await db.commit()         # ② 落库：真正执行 SQL
        await db.refresh(row)     # ③ 从库重读，拿到 id/时间戳等权威值
    except Exception as e:
        await db.rollback()       # 失败回滚：不留半截数据
        logger.error("写库失败: %s: %s", type(e).__name__, str(e))
        raise                     # 原样抛出，由调用方决定如何转 HTTP