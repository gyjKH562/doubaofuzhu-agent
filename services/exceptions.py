"""
exceptions.py —— 业务异常集中定义

为什么集中：异常是业务信号，散落在各 service 里会造成
"同一个错误不同表达"（第 8 步就出现两处"文章不存在"）。
集中定义 + 全局处理器 = 错误分类一处定，翻译一处做。
"""
class ArticleNotFoundError(Exception):
    """文章不存在的信号（全局处理器翻译成 404）。"""

class ModelOutputError(Exception):
    """模型输出格式异常的信号（全局处理器翻译成 502）。

    为什么不用裸 ValueError：ValueError 太宽泛——业务代码里任何
    地方都可能抛，全局处理它会把无关错误也误判成"模型问题"。
    专用异常 = 精确信号。
    """

class DBError(Exception):
    """数据库写操作失败的信号（全局处理器翻译成 500）。

    封装 db_helpers.save_row 里的原始异常，让调用方（全局处理器）
    只认识 DBError，原始根因通过 from e 保留在异常链里。
    """