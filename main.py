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
from fastapi.middleware.cors import CORSMiddleware        # CORS 中间件
from services.rate_limiter import FixedWindowLimiter       # 限流器

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

# 浏览器同源策略：前端域名调本 API 会被浏览器拦截，除非服务器声明允许
# 开发期用 "*"（允许所有来源）；生产必须收窄到真实前端域名（.env 配置）
# ⚠ "*" 与 allow_credentials=True 冲突（浏览器规范禁止），FastAPI 启动即报错
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")  # 配置分离
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # 允许的来源列表（开发期 *）
    allow_methods=["*"],            # 允许所有 HTTP 方法（GET/POST/PUT/DELETE/OPTIONS）
    allow_headers=["*"],            # 允许所有请求头（含 Content-Type）
    allow_credentials=False,        # 用 "*" 时必须 False（见上方 ⚠）
)

# ---- ② 限流：保护自己 + 保护钱包 ----
# generate/refine 每次调用都烧大模型 token，被刷 = 烧钱
rate_limiter = FixedWindowLimiter(max_requests=30, window_seconds=60)  # 每 IP 每分钟 30 次

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """简单 IP 限流：超限返回 429 Too Many Requests。"""
    client_ip = request.client.host if request.client else "unknown"  # 取客户端 IP
    if not rate_limiter.allow(client_ip):      # 超限了
        logger.warning("限流触发：IP=%s 路径=%s", client_ip, request.url.path)  # 留痕
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    return await call_next(request)            # 未超限：放行给内层中间件/路由

# ---- ③ 全局 500 兜底（兑现第 9 步债）----
# 未注册的未知异常：统一 JSON + 日志完整留痕，不向客户端泄漏内部细节
@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("未处理异常: %s: %s", type(exc).__name__, str(exc))  # traceback 进日志
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

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
