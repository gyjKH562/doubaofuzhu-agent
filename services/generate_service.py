"""
generate_service.py —— 文章生成业务编排

职责：把"生成一篇自媒体文案"的完整业务串起来：
    查缓存 → 构造 prompt → 调大模型 → 解析输出 → 写库 → 返回记录

分层规则：本文件不 import FastAPI（不出现 HTTPException / Response）。
业务异常向上抛，由 router 层翻译成 HTTP 状态码——service 可被接口、
脚本、测试任意调用。
"""
import logging  # 日志：记录缓存命中/生成过程/失败原因

from sqlalchemy import select          # 构造 SELECT 查询语句
from sqlalchemy.ext.asyncio import AsyncSession  # 异步会话类型（类型注解用）

from database import ArticleRecord                 # ORM 模型：对应 article_record 表
from services.llm_service import LLMError, call_llm  # 第 6 步的封装：调模型 + 错误分类
from services.db_helpers import save_row
from services.exceptions import ModelOutputError
from services.markdown_service import normalize_markdown, normalize_plain  # 第 12 步：排版规范化（公众号 Markdown / 小红书纯文本）

logger = logging.getLogger(__name__)  # 本模块的日志器，__name__ = "services.generate_service"

# 模型输出格式约定：两段内容的分隔标记（第 9 步会换成更稳的 JSON mode）
SEP_GZH = "===公众号==="   # 公众号段的分隔标记
SEP_XHS = "===小红书==="   # 小红书段的分隔标记

# 系统提示词：告诉模型"你是谁、要干什么、按什么格式输出"
SYSTEM_PROMPT = (
    "你是一名资深自媒体文案专家。根据用户给出的选题，生成两篇内容：\n"
    f"1. 公众号文章：标题 + 正文，有观点有案例；\n"
    f"2. 小红书笔记：吸引眼球的标题 + 简洁干货 + 3 个话题标签。\n"
    f"输出格式：先写【{SEP_GZH}】开头的内容，再写【{SEP_XHS}】开头的内容，"
    "两段之间不要有其他文字。"
)


async def find_cached(db: AsyncSession, topic: str) -> ArticleRecord | None:
    """查缓存：同一选题是否已生成过（gzh_article 非空视为已生成）。

    返回最新一条匹配记录，没有则返回 None。
    """
    # 构造查询：选 topic 相同、且 gzh_article 非空的记录
    stmt = (
        select(ArticleRecord)                       # SELECT * FROM article_record
        .where(                                       # WHERE 条件：
            ArticleRecord.topic == topic,             #   ① topic 完全匹配（缓存按选题查）
            ArticleRecord.gzh_article.isnot(None),    #   ② 公众号内容非空 = 已生成过
        )
        .order_by(ArticleRecord.id.desc())          # 按 id 倒序 = 最新生成的排最前
        .limit(1)                                     # 只要 1 条（最新的那次）
    )
    result = await db.execute(stmt)   # 执行查询（异步：不阻塞事件循环）
    return result.scalar_one_or_none()  # 取第一条记录；没有则返回 None


def parse_generated(text: str) -> tuple[str, str]:
    """按分隔符解析模型输出，返回 (公众号内容, 小红书内容)。

    格式约定脆弱（模型偶尔不按格式来），解析失败抛 ValueError，
    由 router 转成 502——宁可明确失败，也不返回残缺内容。
    """
    # ① 用公众号分隔符把文本切成 [分隔符之前, 分隔符之后] 两段
    parts = text.split(SEP_GZH, 1)
    # ② 如果切不出第二段，说明模型根本没按格式输出——直接判失败
    if len(parts) < 2:
        raise ModelOutputError("模型输出缺少公众号分隔符")  # 原来是 ValueError
    # ③ 取分隔符之后的部分（里面装着公众号 + 小红书两段）
    rest = parts[1]
    # ④ 再按小红书分隔符切一次，把公众号和小红书分开
    xhs_parts = rest.split(SEP_XHS, 1)
    # ⑤ 第一段是公众号内容（strip 去掉首尾空白/换行）
    gzh = xhs_parts[0].strip()
    # ⑥ 第二段是小红书内容；没切到就置空字符串（模型漏输出时兜底）
    xhs = xhs_parts[1].strip() if len(xhs_parts) > 1 else ""
    # ⑦ 公众号为空 = 解析结果不可用，宁可报错也不写残缺数据
    if not gzh:
        raise ModelOutputError("公众号内容为空")              # 原来是 ValueError
    logger.info("解析成功：公众号 %d 字，小红书 %d 字", len(gzh), len(xhs))
    return gzh, xhs   # 返回解包后的两段内容


async def generate_article(db: AsyncSession, topic: str) -> tuple[ArticleRecord, bool]:
    """生成文章的主流程（缓存优先）。

    步骤：
        1. 查缓存——命中直接返回（零成本）
        2. 未命中——构造 prompt、调模型、解析、写库
    异常：
        LLMError: 大模型调用失败（由调用方决定如何转 HTTP）
        ValueError: 模型输出格式异常
        其他 Exception: 写库失败
    """
    # ① 查缓存：同一选题生成过就直接返回（省钱省时间的核心）
    cached = await find_cached(db, topic)
    if cached is not None:                      # 命中缓存
        logger.info("缓存命中：topic=%s id=%d", topic, cached.id)
        return cached,True                            # 直接返回，不调模型、不写库

    # ② 缓存未命中：构造消息列表（system 定位角色 + user 给选题）
    logger.info("缓存未命中，开始生成：topic=%s", topic)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},  # 系统消息：告诉模型怎么干活
        {"role": "user", "content": topic},            # 用户消息：这次要生成什么
    ]

    # ③ 调大模型（第 6 步的封装：超时 / 重试 / 错误分类都在这）
    text = await call_llm(messages, max_tokens=2000)   # max_tokens 是成本闸门

    # ④ 解析模型输出为两篇内容
    gzh_article, xhs_note = parse_generated(text)      # 元组解包

    # 第 12 步：规范化排版（去行尾空白/压缩空行/标题前补空行）
    # 只处理新生成的数据；历史数据不动（避免破坏第 7 步的缓存逻辑）
    gzh_article = normalize_markdown(gzh_article)  # 公众号：完整 Markdown 规则
    xhs_note = normalize_plain(xhs_note)          # 小红书：只清洗（# 是话题标签不是标题）

    # ⑤ 写库（写库三部曲——第 3 次出现，第 8 步抽公共函数）
    db_row = ArticleRecord(               # 构造 ORM 对象（内存里，还没进数据库）
        topic=topic,                      # 选题原样存
        gzh_article=gzh_article,          # 生成的公众号文章
        xhs_note=xhs_note,                # 生成的小红书笔记
    )
    await save_row(db, db_row)

    logger.info("生成完成：id=%d topic=%s", db_row.id, topic)
    return db_row,False                         # 返回已落库的记录（含自增 id）
