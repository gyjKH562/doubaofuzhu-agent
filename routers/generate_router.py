"""
generate_router.py —— AI 生成域接口

职责：只做"收参 + 调 service + 翻译异常为 HTTP 状态码"。
业务编排在 services/generate_service.py（薄 router、厚 service）。
"""
import logging  # 日志

from fastapi import APIRouter, Depends, HTTPException, Response  # Response：动态改状态码用
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话类型

from database import get_db                                # 会话依赖：每个请求一个 db
from schemas.article_schemas import ArticleResp, GenerateRequest,RefineRequest  # 响应/请求模型
from services.generate_service import generate_article     # 业务编排入口
from services.refine_service import  refine_article

logger = logging.getLogger(__name__)  # 本模块日志器

router = APIRouter(prefix="/api", tags=["AI 生成"])  # 路由前缀 /api，文档分组"AI 生成"

@router.post("/generate", response_model=ArticleResp, status_code=201, summary="生成文章")
async def generate_api(
    req: GenerateRequest,             # FastAPI 自动校验请求体 → GenerateRequest
    db: AsyncSession = Depends(get_db),  # 依赖注入：每个请求新建会话、用完自动关
    response: Response = None,        # 注入响应对象，用于运行时动态改状态码
):
    """按选题生成公众号文章 + 小红书笔记。

    - 新生成：返回 201（创建了新资源）
    - 缓存命中：改成 200（返回已有资源）——调用方靠状态码区分
    - 大模型失败：502（上游服务不可用）；格式异常：502；写库失败：500
    """
    row, is_cached = await generate_article(db, req.topic)   # 异常全部交给全局处理器

    # 【小挑战·留给你】动态状态码：
    #   目标：缓存命中时 response.status_code = 200，新生成保持 201
    #   方案：让 generate_article 返回 (record, is_cached) 元组，这里据此设状态码
    #   当前占位：先统一 201（新生成），你改完这段就算完成挑战
    response.status_code =  200 if is_cached else 201

    return row  # FastAPI 按 response_model=ArticleResp 序列化返回

@router.post("/refine", response_model=ArticleResp, summary="改写文章")
async def refine_api(
    req: RefineRequest,               # 请求体：article_id 必填，instruction 可选
    db: AsyncSession = Depends(get_db),  # 会话依赖
):
    """按指令改写指定文章的公众号内容 + 小红书笔记。

    - 成功：200（改写是更新已有资源，不是新建）
    - 文章不存在：404；大模型失败：502；格式异常：502；写库失败：500
    """
    row = await refine_article(db, req.article_id, req.instruction)   # 就这一行

    return row  # 默认 200：更新已有资源