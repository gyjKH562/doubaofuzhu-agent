"""
article_schemas.py —— 文章接口的请求/响应数据模型

职责：声明接口"收什么"（请求体）和"返回什么"（响应体），
Pydantic 依据模型自动完成校验、文档生成、序列化。
"""
from datetime import datetime

# BaseModel：所有 Pydantic 模型的基类
# Field：给字段加约束和描述（会显示在 /docs 里）
# ConfigDict：模型配置（v2 写法，替代旧的 class Config）
from pydantic import BaseModel, ConfigDict, Field

class ArticleCreate(BaseModel):
    """创建文章的请求体：客户端 POST /api/article 时发送的 JSON 格式。"""

    # ... 表示必填；min_length/max_length 由 Pydantic 自动校验，违规返回 422
    topic: str = Field(..., min_length=1, max_length=120, description="文章选题")
    # 可选字段：不传则默认为 None（对应数据库列的 nullable=True）
    gzh_article: str | None = Field(None, description="公众号文章（Markdown 格式）")
    xhs_note: str | None = Field(None, description="小红书笔记")

class ArticleResp(BaseModel):
    """文章记录的响应体：所有返回文章记录的接口统一用它，保证格式一致。"""

    # from_attributes=True：允许直接从 ORM 对象（ArticleRecord）转成这个模型，
    # 省去手动逐字段赋值
    model_config = ConfigDict(from_attributes=True)

    id: int                  # 数据库自增主键
    topic: str               # 选题
    gzh_article: str | None  # 公众号文章（可能为空）
    xhs_note: str | None     # 小红书笔记（可能为空）
    created_at: datetime     # 创建时间
    updated_at: datetime     # 更新时间

class ArticleListResp(BaseModel):
    """文章列表的响应体：所有返回文章列表的接口统一用它，保证格式一致。"""

    total: int                # 总记录数
    items: list[ArticleResp]     # 文章记录列表

class ArticleUpdate(BaseModel):
    """更新文章的请求体：所有字段可选，不传的字段保持原值。

    - 用 model_dump(exclude_unset=True) 区分"没传"和"传了 null"
    - topic 传 null 会被业务层拦下（数据库列 NOT NULL，不能置空）
    """

    topic: str | None = Field(None, min_length=1, max_length=120, description="文章选题")
    gzh_article: str | None = Field(None, description="公众号文章(Markdown 格式)")
    xhs_note: str | None = Field(None, description="小红书笔记")

class GenerateRequest(BaseModel):
    """生成接口的请求体：只需要选题，两篇文章由模型产出。

    为什么不复用 ArticleCreate：接口契约不同——创建接口允许客户端
    自己传文章内容，生成接口的内容必须来自模型，收了反而危险。
    """
    topic: str = Field(..., min_length=1, max_length=120, description="文章选题")

class RefineRequest(BaseModel):
    """改写接口的请求体：指定改哪篇 + 怎么改。

    article_id 必填；instruction 可选（不传用默认"优化表达"指令）。
    """
    article_id: int = Field(..., gt=0, description="要改写的文章 id")
    instruction: str | None = Field(  # 改写要求：可选
        None,
        min_length=1,   # 传了就不能是空串
        max_length=200, # 超长 422
        description="改写指令，如'写得更口语化'；不传则默认优化表达",
    )