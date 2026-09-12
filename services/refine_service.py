"""
refine_service.py —— 文章改写业务编排

职责：把"改写一篇文章"的完整业务串起来：
    查记录 → 拼改写 prompt（原文 + 指令）→ 调模型 → 解析 → 更新 → 写库

复用了 4 个已有能力（复用地图见第 8 步开篇）：
    call_llm            ← services.llm_service
    parse_generated     ← services.generate_service（输出格式约定一致）
    save_row            ← services.db_helpers（本次新抽）
    ArticleRecord       ← database

分层规则：本文件不 import FastAPI。查不到文章用自定义异常
ArticleNotFoundError 表达，由 router 翻译成 404。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from database import ArticleRecord
from services.db_helpers import save_row
from services.generate_service import SEP_GZH, SEP_XHS, parse_generated
from services.llm_service import LLMError, call_llm
from services.exceptions import ArticleNotFoundError, ModelOutputError
from services.markdown_service import normalize_markdown  # 第 12 步：排版规范化

logger = logging.getLogger(__name__)

# 改写专用系统提示词：角色相同，但任务从"生成"变成"按指令改写"
REFINE_PROMPT = (
    "你是一名资深自媒体文案专家。用户会给出一篇已生成的公众号文章和小红书笔记，"
    "请根据用户的改写指令进行改写，保留原文的核心观点和信息。\n"
    f"输出格式不变：先写【{SEP_GZH}】开头的内容，再写【{SEP_XHS}】开头的内容，"
    "两段之间不要有其他文字。"
)

# 默认改写指令：用户不传 instruction 时用（模板里写清默认行为）
DEFAULT_INSTRUCTION = "在保持原意的前提下优化表达，让内容更吸引读者"



async def refine_article(
    db: AsyncSession,
    article_id: int,
    instruction: str | None = None,
) -> ArticleRecord:
    """改写指定文章，返回改写后的记录。

    参数：
        db: 数据库会话
        article_id: 要改写的文章 id（不存在抛 ArticleNotFoundError）
        instruction: 改写指令，不传用默认"优化表达"
    异常：
        ArticleNotFoundError: 文章不存在
        LLMError: 大模型调用失败
        ValueError: 模型输出格式异常（解析失败）
        其他 Exception: 写库失败
    """
    # ① 查记录（service 层查询：不抛 HTTPException，抛自定义异常）
    row = await db.get(ArticleRecord, article_id)   # 按主键查，不存在返回 None
    if row is None:
        logger.warning("改写失败：文章不存在 id=%d", article_id)
        raise ArticleNotFoundError(f"文章不存在: {article_id}")

    # ② 构造改写 prompt：原文（按分隔符约定拼）+ 用户指令（默认值兜底）
    original = (
        f"{SEP_GZH}\n{row.gzh_article or ''}\n"   # 公众号原文（None 兜底为空串）
        f"{SEP_XHS}\n{row.xhs_note or ''}"        # 小红书原文
    )
    final_instruction = instruction or DEFAULT_INSTRUCTION  # 没传就用默认
    messages = [
        {"role": "system", "content": REFINE_PROMPT},       # 系统：怎么干
        {"role": "user", "content": f"原文如下：\n{original}\n\n改写指令：{final_instruction}"},
    ]
    logger.info("开始改写：id=%d instruction=%s", article_id, final_instruction[:30])

    # ③ 调大模型（复用第 6 步封装：超时/重试/错误分类）
    text = await call_llm(messages, max_tokens=2000)

    # ④ 解析输出（复用生成接口的解析约定，两篇一起改）
    gzh_article, xhs_note = parse_generated(text)

    # 第 12 步：规范化排版（与生成流程一致，改写的输出同样规范化）
    gzh_article = normalize_markdown(gzh_article)
    xhs_note = normalize_markdown(xhs_note)

    # ⑤ 更新 ORM 对象字段 + 统一写库（updated_at 由 onupdate 自动刷新）
    row.gzh_article = gzh_article
    row.xhs_note = xhs_note
    await save_row(db, row)

    logger.info("改写完成：id=%d", row.id)
    return row