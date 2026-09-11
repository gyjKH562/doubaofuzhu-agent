"""
main.py —— 项目入口：FastAPI 应用最小骨架

本步骤只做三件事：
1. 加载 .env 配置（主机/端口）
2. 配置全局日志（logging 替代 print）
3. 提供 /health 健康检查接口，验证服务能启动、能响应
"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse  # 构造 JSON 错误响应

from database import create_tables
from routers.article_router import router as article_router
from routers.generate_router import router as generate_router
from services.exceptions import ArticleNotFoundError, DBError, ModelOutputError
from services.llm_service import LLMError

# 先加载 .env，再读环境变量（顺序不能反）
load_dotenv()

# 配置全局日志：时间 + 级别 + 来源模块 + 消息
# 后续所有模块（database、router 等）的 logger 都会继承这套格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# 本模块的日志记录器：__name__ 会显示为 "main"，方便区分日志来源
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服务启动,正在初始化数据库...")
    await create_tables()
    logger.info("数据库初始化完成")
    yield


# 创建 FastAPI 应用实例
# title / version 会显示在 /docs 自动生成的接口文档页面上
app = FastAPI(title="自媒体文案生成工具", version="0.1.0", lifespan=lifespan)


@app.exception_handler(ArticleNotFoundError)
async def article_not_found_handler(request, exc: ArticleNotFoundError):
    """资源不存在 → 404。所有"查不到"的接口统一走这里。"""
    logger.warning("资源不存在: %s", exc)     # 兜底日志：所有 404 都留痕
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(ModelOutputError)
async def model_output_handler(request, exc: ModelOutputError):
    """模型输出格式异常 → 502（上游数据质量问题的信号）。"""
    logger.error("模型输出格式异常: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "模型输出格式异常"})

@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError):
    """大模型调用失败 → 502（上游服务不可用）。"""
    logger.error("大模型调用失败: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})

@app.exception_handler(DBError)
async def db_error_handler(request, exc: DBError):
    """数据库写失败 → 500（我们自己的问题）。"""
    logger.error("数据库操作失败: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "数据库保存失败"})

app.include_router(article_router)
app.include_router(generate_router)

@app.get("/health", summary="健康检查")
async def health_check() -> dict:
    """健康检查接口：部署环境（或你自己）探测服务是否存活。

    约定返回 {"status": "ok"}，200 状态码表示服务正常。
    为什么需要它：生产环境用负载均衡/监控定时请求这个接口，
    服务挂了立刻被发现。第 1 步先建立这个习惯。
    """
    return {"status": "ok"}


@app.get("/", summary="服务信息")
async def root() -> dict:
    """根路径：返回服务基本信息，方便浏览器打开时有个直观回应。"""
    return {"service": "自媒体文案生成工具", "version": "0.1.0", "docs": "/docs"}



# 直接运行本文件时启动服务（python main.py）
# host/port 从 .env 读取，带默认值兜底——这就是"配置分离"
if __name__ == "__main__":
    import uvicorn

    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    logger.info("服务启动: http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port)
