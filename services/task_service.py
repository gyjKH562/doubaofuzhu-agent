"""
task_service.py —— 异步任务队列的核心逻辑（第 13 步）

职责：把"耗时的大模型生成"改成"提交即返回 + 后台执行 + 轮询状态"。

核心机制（自实现轻量任务队列，零新依赖）：
    1. 提交时：往 task_record 表插一行（status=pending），返回 task_id
    2. 后台：asyncio.create_task 启动协程执行生成（复用 generate_article）
    3. 轮询：客户端反复查 GET /api/tasks/{id} 看状态
    4. 状态机：pending → running → done / failed

为什么自实现而不是 Celery/ARQ（YAGNI）：
    单进程、内存调度对原型足够；生产多实例部署时换 Celery/Redis
    （记入技术债）。核心概念（任务表 + 状态机 + 后台执行）完全一致。

⚠️ 关键坑：后台任务必须自己开数据库会话——
    请求的会话（Depends(get_db)）在响应返回后就被关闭了，
    后台协程再用它 = 用已关闭的会话（会崩）。
"""
import json  # 结果序列化（result 列存 JSON 字符串）
import logging  # 日志

from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话类型

from database import AsyncSessionLocal, TaskRecord  # 会话工厂 + 任务模型
from services.generate_service import generate_article  # 复用生成业务（含缓存）
from services.db_helpers import save_row  # 写库统一入口

logger = logging.getLogger(__name__)

# ---- 任务状态常量（状态机的四个状态）----
# 用常量而不是魔法字符串：写错名字时立刻报错（NameError），拼写错误无处藏身
TASK_PENDING = "pending"    # 已提交，等待执行
TASK_RUNNING = "running"    # 正在执行（大模型调用中）
TASK_DONE = "done"          # 执行成功（result 里有内容）
TASK_FAILED = "failed"      # 执行失败（error 里有原因）


async def create_task_record(db: AsyncSession, topic: str) -> TaskRecord:
    """创建任务记录（status=pending），返回带自增 id 的任务对象。"""
    task = TaskRecord(topic=topic, status=TASK_PENDING)  # 新任务默认排队
    await save_row(db, task)                              # 写库三部曲（复用）
    logger.info("任务已创建：id=%d topic=%s", task.id, topic)
    return task


async def get_task_record(db: AsyncSession, task_id: int) -> TaskRecord | None:
    """按 id 查任务记录；不存在返回 None（由 router 翻译 404）。"""
    return await db.get(TaskRecord, task_id)  # 按主键查，最简查询


def task_to_resp(task: TaskRecord) -> dict:
    """把 ORM 任务对象转成响应字典（TaskResp 的数据源）。

    为什么手动转而不是 from_attributes：result 列存的是 JSON 字符串，
    响应里需要的是 dict——序列化逻辑不同，手动转换最清晰。
    """
    result: dict | None = None
    if task.result:                       # result 非空（任务成功）
        result = json.loads(task.result)  # JSON 字符串 → dict（反序列化）
    return {
        "task_id": task.id,
        "topic": task.topic,
        "status": task.status,
        "result": result,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


async def run_task(task_id: int) -> None:
    """后台执行任务（由 asyncio.create_task 调用，不阻塞请求）。

    流程：标记 running → 调生成业务 → 成功存结果(done) / 失败存原因(failed)。
    为什么 catch Exception：后台协程的异常没人接，一旦抛出任务就
    永远停在 running——必须自己捕获并写进任务状态。
    """
    # ① 自己开会话（不能用请求的会话：响应返回后它已关闭）
    async with AsyncSessionLocal() as db:
        # ② 拉取任务记录，标记 running
        task = await db.get(TaskRecord, task_id)
        if task is None:                    # 任务不存在（极端情况）：记日志退出
            logger.error("后台任务不存在：id=%d", task_id)
            return
        task.status = TASK_RUNNING          # 排队 → 执行中
        await db.commit()                   # 状态先落库（客户端能看到 running）

        # ③ 执行真正的业务（复用第 7 步的生成逻辑：缓存优先）
        try:
            record, is_cached = await generate_article(db, task.topic)
            # ④ 成功：把结果序列化成 JSON 存进 result 列
            task.status = TASK_DONE
            task.result = json.dumps(
                {
                    "article_id": record.id,      # 落库的文章 id
                    "is_cached": is_cached,       # 是否命中缓存
                    "gzh_article": record.gzh_article,  # 公众号文章
                    "xhs_note": record.xhs_note,          # 小红书笔记
                },
                ensure_ascii=False,               # 中文不转 \uXXXX（可读性好）
            )
            task.error = None
            logger.info("任务完成：id=%d topic=%s", task_id, task.topic)
        except Exception as e:                    # 任何异常都接住
            # ⑤ 失败：记录原因（截断防超长），状态置 failed
            task.status = TASK_FAILED
            task.error = str(e)[:500]             # 500 字符足够定位问题
            logger.error("任务失败：id=%d 原因=%s", task_id, e)

        # ⑥ 状态/结果落库（updated_at 由 onupdate 自动刷新）
        await db.commit()
