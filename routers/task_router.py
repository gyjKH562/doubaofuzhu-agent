"""
task_router.py —— 异步任务域接口（第 13 步）

职责：
    POST /api/tasks       提交生成任务 → 202 + task_id（立即返回，不等待）
    GET  /api/tasks/{id}  查询任务状态 → 200（客户端轮询这个接口）

设计要点：
    1. 提交接口只做两件事：建任务记录 + 启动后台协程——然后立刻返回。
       大模型生成的耗时被移到后台，请求不再被卡住几十秒。
    2. 状态查询接口是"轮询模式"的服务端半边：
       客户端每隔几秒调一次，看到 done 就取结果。
"""
import asyncio  # 后台任务调度（asyncio.create_task）
import logging

from fastapi import APIRouter, Depends, Path  # 路由组织 / 依赖注入 / 路径校验
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db                                # 会话依赖
from schemas.article_schemas import GenerateRequest         # 复用：选题请求体
from schemas.task_schemas import TaskResp                   # 任务响应体
from services.exceptions import ArticleNotFoundError        # 任务不存在 → 404
from services.task_service import (
    create_task_record,   # 建任务记录
    get_task_record,      # 查任务记录
    run_task,             # 后台执行
    task_to_resp,         # ORM → 响应字典
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["异步任务"])  # 文档分组"异步任务"


@router.post("/tasks", response_model=TaskResp, status_code=202, summary="提交生成任务")
async def create_task_api(
    req: GenerateRequest,             # 请求体：{topic}（复用生成的选题模型）
    db: AsyncSession = Depends(get_db),
):
    """提交异步生成任务：立即返回 202 + task_id，生成在后台执行。

    202 Accepted 的语义："已受理，处理中"——不是 201（创建完成），
    也不是 200（同步完成）。客户端拿到 task_id 后轮询查询接口。
    """
    # ① 建任务记录（pending）
    task = await create_task_record(db, req.topic)

    # ② 启动后台协程：不 await，让它自己跑；请求立即返回
    #    asyncio.create_task 把协程挂到事件循环，返回 Task 对象（不阻塞）
    asyncio.create_task(run_task(task.id))
    logger.info("任务已提交后台执行：id=%d", task.id)

    # ③ 立即返回 202 + 任务信息（此时状态大概率还是 pending）
    return task_to_resp(task)


@router.get("/tasks/{task_id}", response_model=TaskResp, summary="查询任务状态")
async def get_task_api(
    *,
    task_id: int = Path(..., gt=0, description="任务 id（必须 >0）"),
    db: AsyncSession = Depends(get_db),
):
    """查询任务状态：pending/running/done/failed；不存在 404。

    客户端轮询模式：每隔 2~3 秒调一次，status=done 时取 result。
    """
    task = await get_task_record(db, task_id)
    if task is None:                          # 任务不存在
        raise ArticleNotFoundError(f"任务不存在: {task_id}")  # 全局处理器翻译 404
    return task_to_resp(task)
