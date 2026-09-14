"""
task_schemas.py —— 异步任务接口的请求/响应数据模型

职责：声明任务接口"收什么"（无请求体，路径参数）和"返回什么"（TaskResp）。
"""
from datetime import datetime

from pydantic import BaseModel  # 所有 Pydantic 模型的基类

class TaskResp(BaseModel):
    """任务查询/创建的响应体：客户端靠它轮询任务状态。"""

    task_id: int               # 任务 id（提交时立即拿到，之后用它查状态）
    topic: str                 # 选题（方便客户端确认是哪个任务）
    status: str                # 任务状态：pending / running / done / failed
    result: dict | None = None # 成功时的结果（含文章内容）；未完成或失败为 None
    error: str | None = None   # 失败原因；成功为 None
    created_at: datetime       # 任务创建时间
    updated_at: datetime       # 最后更新时间（状态每次变化都会刷新）
