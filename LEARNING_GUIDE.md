# 自媒体文案生成工具 · 全流程学习手册

> 13 步从零到一构建一个 FastAPI 后端项目 —— 代码 + 知识点 + 踩坑 + 工程决策全记录
>
> 配套项目：`doubaofuzhuAgent-tutorial` ｜ 测试：41 passed ｜ 提交：15 次（全部可追溯）

---

## 📖 阅读指南（先读这一节）

这份手册不是教科书，是**你亲手走过的路的完整复盘**。正确的用法：

1. **按顺序读**：每一步都建立在前一步之上，跳步会断链；
2. **边读边跑**：每步的自测命令亲手执行一遍，代码在编辑器里打开对照；
3. **先想后看**：每步的「思考题」先自己答，再往下看；
4. **读完一章回 README**：README 的「故事点」是这些决策的面试浓缩版，两者互相对照。

**项目全景**（13 步完成后的最终形态）：

```
自媒体文案生成工具（FastAPI 后端）
├── 文章域    POST/GET/PUT/DELETE /api/article（CRUD + 分页 + 搜索）
├── AI 生成域  POST /api/generate（缓存优先）· POST /api/refine（改写）
├── 异步任务域  POST /api/tasks（202 即返）· GET /api/tasks/{id}（轮询）
├── 横切能力   统一异常（404/422/502/500）· 限流（30次/分/IP）· CORS · 日志
└── 质量保障   41 个 pytest 用例（单元 + 接口，独立测试库 + mock 大模型）
```

**13 步路线图**：

| 阶段 | 步骤 | 核心收获 |
|------|------|---------|
| 地基 | 1-2 | 配置分离、日志、异步 ORM、依赖注入 |
| 业务 | 3-5 | 请求/响应模型、写库三部曲、分页搜索、第一次重构（Rule of Three） |
| AI | 6-8 | 大模型 SDK 封装、缓存优先、service 分层、复用之道 |
| 工程化 | 9-10 | 统一异常处理、CORS、限流、500 兜底 |
| 质量 | 11-12 | pytest 自动化测试、纯函数与业务语义 |
| 进阶 | 13 | 异步任务队列（任务表 + 状态机 + 后台执行） |

---

## 第 0 部分：开始之前（环境与心智模型）

### 0.1 环境清单

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.13.12 | 虚拟环境 `.venv`，独立于系统 Python |
| MySQL | 8.x | 数据库，异步驱动 aiomysql |
| Git | 任意 | 版本管理（装到 D 盘，E:\DeveloperTools\Git） |
| IDE | PyCharm | 专业版 |

### 0.2 四个心智模型（第 1 步之前先建立）

**① 配置分离**：代码里不出现任何"环境相关"的值——密码、端口、密钥全部放 `.env`，代码用 `os.getenv` 读取。原因：同一份代码，开发/测试/生产环境不同，配置跟着环境走、不跟着代码走。

**② 日志 vs print**：`print` 是"打印给人看"，日志（`logging`）是"记录给系统看"——带时间、级别、来源模块，可过滤、可分级（INFO/ERROR）。生产环境靠日志排障，靠 print 排障会疯。

**③ 异步**：`async/await` 让一个线程在"等待 IO"时去干别的活（数据库查询、网络请求都是 IO）。FastAPI 天然异步——高并发下线程不被 IO 占死。

**④ 分层**：router（收参/翻译状态码）→ service（业务编排）→ 数据层（ORM/数据库）。各层只管自己的事，方便测试、复用、替换。

### 0.3 三个"永远"的工程习惯

- 永远维护 `requirements.txt`，**锁定版本**（`fastapi==0.141.1` 而不是 `fastapi`）——版本漂移是 bug 之源；
- 永远用虚拟环境（`.venv`）——项目依赖与系统隔离，换机器可复现；
- 永远把密钥留在 `.env`，只提交 `.env.example`（占位符版）。

---

## 第 1 步：项目骨架（配置分离 + 日志 + 健康检查）

### 📌 目标

- 建立项目目录结构、虚拟环境、依赖锁定
- 实现配置分离（.env → 环境变量 → 代码读取）
- 配置全局日志
- 提供 `/health` 健康检查接口

### 🧠 核心知识点

1. **配置分离的实现链路**：`.env` 文件 → `python-dotenv` 的 `load_dotenv()` 读入环境变量 → `os.getenv("APP_PORT", "8000")` 读取（带默认值兜底）。**顺序不能反**：先 `load_dotenv()` 再读。
2. **`logging.basicConfig`**：全局日志格式 `时间 - 模块 - 级别 - 消息`；各模块用 `logging.getLogger(__name__)` 获得自己的 logger（`__name__` 显示模块名，方便定位日志来源）。
3. **健康检查的工程意义**：生产环境用负载均衡/监控定时请求 `/health` 探测服务存活，挂了立刻被发现——第 1 步就建立这个习惯。
4. **`asynccontextmanager` + lifespan**：FastAPI 启动/关闭钩子，启动时初始化数据库（第 2 步用）。

### 💻 代码（本步核心：main.py 骨架）

```python
"""main.py —— 项目入口：FastAPI 应用最小骨架"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# 先加载 .env，再读环境变量（顺序不能反）
load_dotenv()

# 配置全局日志：时间 + 级别 + 来源模块 + 消息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)  # 本模块日志器

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化（第 2 步会在这里建表）。"""
    logger.info("服务启动,正在初始化...")
    yield  # yield 之前是启动逻辑，之后是关闭逻辑

app = FastAPI(title="自媒体文案生成工具", version="0.1.0", lifespan=lifespan)

@app.get("/health", summary="健康检查")
async def health_check() -> dict:
    """健康检查：返回 {"status": "ok"} 表示服务正常。"""
    return {"status": "ok"}

@app.get("/", summary="服务信息")
async def root() -> dict:
    """根路径：浏览器打开时有直观回应。"""
    return {"service": "自媒体文案生成工具", "version": "0.1.0", "docs": "/docs"}

# 直接运行本文件时启动服务（python main.py）
if __name__ == "__main__":
    import uvicorn
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    logger.info("服务启动: http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port)
```

`.env`（真实配置，**不提交 git**）：

```ini
APP_HOST=127.0.0.1
APP_PORT=8000
```

### ⚠️ 踩坑记录

- **8000 端口被占用**：本机其他程序（如 DoubaoChat.exe）占了 8000，服务起不来。解决：`.env` 改 `APP_PORT=8001` 跑通，再改回——**配置分离的价值第一次验证**：改端口不用动代码。
- **`load_dotenv()` 位置**：必须在 `os.getenv` 之前调用，否则读到默认值（服务起在错误的端口上）。

### ✅ 自测验证

```powershell
.\.venv\Scripts\python.exe main.py          # 启动
# 浏览器打开 http://127.0.0.1:8000/health → {"status": "ok"}
# 打开 /docs → Swagger 文档页面出现（title 显示"自媒体文案生成工具"）
```

### 🧰 沉淀

- **配置分离模板**（reuse_snippets 模板 A）：`.env` + `load_dotenv` + `os.getenv(默认值)` —— 任何 Python 项目开局必备。
- **日志配置模板**（模板 B）：`basicConfig` + 模块级 `getLogger(__name__)`。

---

## 第 2 步：数据库层（异步 ORM + 自动建表）

### 📌 目标

- 建立异步数据库引擎与会话工厂（SQLAlchemy 2.0）
- 定义第一个 ORM 模型 `ArticleRecord`
- 提供 `get_db` 依赖（每个请求自动开关会话）
- 启动时自动建表

### 🧠 核心知识点

1. **异步引擎 vs 会话**：
   - `create_async_engine` = 连接池的"总开关"，应用启动创建一次、全程复用；
   - `async_sessionmaker` = 开"工作窗口"的工具，每次请求开一个会话、用完关闭。
2. **`expire_on_commit=False`**：默认行为是 commit 后对象"过期"，再读属性会触发一次查询（新手常被这个坑到）。设 False = commit 后属性依然可读。
3. **依赖注入 `get_db`（yield 版）**：`async with AsyncSessionLocal() as session: yield session`——无论接口成功还是抛异常，会话都会被关闭。FastAPI 自动管理生命周期。
4. **`utc_now` 的写法**：`datetime.utcnow()` 在 Python 3.12+ 已弃用，用 `datetime.now(timezone.utc).replace(tzinfo=None)`——去时区信息兼容 MySQL DATETIME。
5. **`create_all` 只建表不建库**：已存在的表自动跳过（不删数据）；但 MySQL 里**库**不存在会连接失败（第 11 步测试库踩了这个，见后）。

### 💻 代码（database.py 核心）

```python
"""database.py —— 数据库连接与 ORM 模型定义"""
import os
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ASYNC_DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:<your_password>@127.0.0.1:3306/article_db?charset=utf8mb4",
)

# 异步引擎：连接池的"总开关"
async_engine = create_async_engine(ASYNC_DB_URL)
# 会话工厂：开"工作窗口"的工具
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)

async def get_db():
    """每个请求提供一个会话，请求结束自动关闭（yield 保证异常也关闭）。"""
    async with AsyncSessionLocal() as session:
        yield session

def utc_now() -> datetime:
    """当前 UTC 时间（去时区，兼容 MySQL DATETIME）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""
    pass

class ArticleRecord(Base):
    """文章记录表。"""
    __tablename__ = "article_record"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255))
    gzh_article: Mapped[str | None] = mapped_column(Text(), nullable=True)
    xhs_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

async def create_tables() -> None:
    """建表：已存在的表自动跳过。"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### ⚠️ 踩坑记录

- **MySQL 8 认证报错**：MySQL 8 默认认证插件（caching_sha2_password）需要 `cryptography` 库，否则连接报错——这就是 `requirements.txt` 里有 `cryptography==50.0.1` 的原因。
- **`Mapped[str | None]` 语法**：Python 3.10+ 才支持 `|` 联合类型，老版本要用 `Optional[str]`。

### ✅ 自测验证

```powershell
.\.venv\Scripts\python.exe main.py
# 启动日志出现"数据库初始化完成"
# MySQL 里检查：USE article_db_tutorial; SHOW TABLES; → article_record 存在
```

### 🧰 沉淀

- **异步数据库三件套模板**（模板 C）：engine + sessionmaker + get_db，任何 FastAPI+SQLAlchemy 项目开局直接复制。
- **ORM 模型定义模板**（模板 D）：`Mapped` + `mapped_column` + 时间戳双列（created_at/updated_at），所有表的标配。

## 第 3 步：创建接口（请求/响应模型 + 写库三部曲）

### 📌 目标

- 第一个写接口：`POST /api/article`
- 请求/响应模型分离（Pydantic BaseModel）
- 掌握"写库三部曲"：add → commit → refresh

### 🧠 核心知识点

1. **请求模型 vs 响应模型为什么分开**：接口的"收"和"发"契约不同——请求模型只管校验输入（topic 必填、长度限制），响应模型决定返回哪些字段（裁剪出口）。将来加字段互不影响。
2. **Pydantic 自动校验**：`Field(..., min_length=1, max_length=120)` 里 `...` 表示必填。非法输入在**进业务代码之前**就被拦下，返回 **422**——这就是"校验前置"。
3. **写库三部曲**：
   - `db.add(row)`：登记进会话（内存操作，还没进库）
   - `await db.commit()`：真正执行 SQL（INSERT）
   - `await db.refresh(row)`：从库重读，拿到数据库生成的 id/时间戳等权威值
4. **状态码 201**：创建新资源用 201（区别于 200 一般成功）。
5. **`response_model=ArticleResp`**：声明响应格式，FastAPI 自动序列化 + 在 Swagger 生成响应 schema。

### 💻 代码（schemas/article_schemas.py + router 创建接口）

```python
# schemas/article_schemas.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ArticleCreate(BaseModel):
    """创建文章的请求体。"""
    topic: str = Field(..., min_length=1, max_length=120, description="文章选题")
    gzh_article: str | None = Field(None, description="公众号文章（Markdown 格式）")
    xhs_note: str | None = Field(None, description="小红书笔记")

class ArticleResp(BaseModel):
    """文章记录的响应体（所有返回文章的接口统一用它）。"""
    model_config = ConfigDict(from_attributes=True)  # 允许直接从 ORM 对象转换
    id: int
    topic: str
    gzh_article: str | None
    xhs_note: str | None
    created_at: datetime
    updated_at: datetime
```

```python
# routers/article_router.py（创建接口部分）
@router.post("", response_model=ArticleResp, status_code=201, summary="创建文章")
async def create_article(req: ArticleCreate, db: AsyncSession = Depends(get_db)):
    """创建文章记录并写库。"""
    # ① 请求数据装进 ORM 对象（此刻只是内存对象）
    db_row = ArticleRecord(
        topic=req.topic,
        gzh_article=req.gzh_article,
        xhs_note=req.xhs_note,
    )
    # ② 写库三部曲：add 登记、commit 落库、refresh 同步
    db.add(db_row)
    await db.commit()
    await db.refresh(db_row)
    return db_row
```

### ⚠️ 踩坑记录

- **Swagger 预填示例值坑**：Swagger 的 "Try it out" 会预填示例值（`topic: "string"`），直接点执行会把 `"string"` 写进库！定位法：查数据库看实际存的 topic。**这个坑在项目里踩了三次**（第 3、7 步），最后用脚本测试（scripts/test_api.py）绕开。
- **422 的语义**：参数校验失败（类型错/长度错/必填缺失）统一 422；业务层判断的非法值（如 topic 为 null）也转 422——但那是业务校验（第 5 步）。

### ✅ 自测验证

```powershell
# 方式一：Swagger /docs → POST /api/article → 手动改 body 再执行
# 方式二：脚本（绕开 Swagger 坑）
.\.venv\Scripts\python.exe scripts/test_api.py post /api/article '{"topic": "测试选题"}'
# 期望：HTTP 201，响应体含 id 和回显的 topic
# 边界：topic 传空串 → 422；不传 topic → 422
```

### 🧰 沉淀

- **请求/响应模型分离模板**（模板 E）：每个 FastAPI 项目必备——`XxxCreate`（请求）+ `XxxResp`（响应，带 `from_attributes=True`）。
- **写库三部曲模板**（模板 F）：add → commit → refresh（第 8 步升级为 save_row）。

---

## 第 4 步：读接口三件套（单条 + 分页 + 搜索）

### 📌 目标

- `GET /api/article/{id}` 单条查询（404 语义）
- `GET /api/article/list` 分页（page/page_size）
- 关键词搜索（防 SQL 注入）

### 🧠 核心知识点

1. **`scalar_one_or_none()`**：查询结果 0 条 → None；1 条 → 对象；多条 → 报错。配合 `if row is None: raise ...` 实现"查不到 → 404"。
2. **分页核心公式**：`offset = (page - 1) × page_size`。分页查两趟：先 `COUNT(*)` 拿总数（给前端算总页数），再查当前页数据。
3. **参数化防注入**：`ArticleRecord.topic.contains(keyword)` 生成 `LIKE '%keyword%'` 且**自动参数化**——用户输入永远作为"值"而不是"SQL 片段"，这是防 SQL 注入的根本。
4. **`Query(1, ge=1, le=100)`**：查询参数校验（page ≥ 1，page_size ≤ 100），违规 422。
5. **路由顺序坑**：`/list` 是静态路径，`/{article_id}` 是动态路径——**静态路径必须声明在动态路径之前**，否则 `/list` 会被 `/{article_id}` 吃掉（article_id="list" 解析失败）。

### 💻 代码（list 接口核心）

```python
@router.get("/list", response_model=ArticleListResp, summary="文章列表")
async def list_articles(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数，上限 100"),
    keyword: str | None = Query(None, max_length=50, description="按选题模糊搜索"),
    db: AsyncSession = Depends(get_db),
):
    # ① 动态构造查询条件：有 keyword 才加过滤
    conditions = []
    if keyword:
        conditions.append(ArticleRecord.topic.contains(keyword))  # 参数化 LIKE

    # ② 第一趟：总数 COUNT(*)
    count_stmt = select(func.count()).select_from(ArticleRecord)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar_one()

    # ③ 第二趟：当前页数据（offset 公式 + 按 id 倒序）
    offset = (page - 1) * page_size
    list_stmt = (
        select(ArticleRecord)
        .where(*conditions)
        .order_by(ArticleRecord.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = list((await db.execute(list_stmt)).scalars().all())
    return ArticleListResp(total=total, items=rows)
```

### ⚠️ 踩坑记录

- **动态条件不能拼字符串**：`where` 条件用列表动态构造，空列表时**不能**调用 `.where(*[])`（会报错），所以用 `if conditions` 判断。
- **`scalars().all()` 返回类型**：是 `Sequence`，要 `list()` 包一下满足 `items: list[ArticleResp]` 的类型契约。

### ✅ 自测验证

```powershell
python scripts/test_api.py get "/api/article/list?page=1&page_size=5"   # 分页结构 total+items
python scripts/test_api.py get "/api/article/list?keyword=测试"          # 搜索过滤
python scripts/test_api.py get "/api/article/1"                          # 单条
python scripts/test_api.py get "/api/article/999999"                     # 404
python scripts/test_api.py get "/api/article/0"                          # 422（第 9 步起）
```

### 🧰 沉淀

- **分页三件套模板**（模板 G）：count + offset/limit + Query 校验，所有列表接口通用。
- **查询参数校验模板**（模板 H）：`Query(默认值, ge/le/max_length)`。

---

## 第 5 步：更新/删除 + 第一次重构（Rule of Three）

### 📌 目标

- `PUT /api/article/{id}` 部分更新（区分"没传"和"传了 null"）
- `DELETE /api/article/{id}`（204 语义）
- **第一次重构**：抽 `_get_article_or_404`（Rule of Three）

### 🧠 核心知识点

1. **`model_dump(exclude_unset=True)`**——部分更新的灵魂：只取"请求里**明确写了**"的字段。"没传"和"传了 null"是两回事——`exclude_unset` 把两者区分开。
2. **`setattr(row, field, value)` 动态赋值**：for 循环逐字段写回 ORM 对象，不用手写 3 行。
3. **204 No Content**：删除成功的语义——没有响应体。FastAPI 里要 `return Response(status_code=204)` 显式构造（返回 None 会变 200）。
4. **Rule of Three（三次法则）**：代码重复出现 **3 次**才值得抽公共函数——前两次重复先忍（YAGNI），第三次出现时你才真正知道"公共部分"是什么。`_get_article_or_404` 在 get/update/delete 三个接口出现，正是抽取时机。
5. **下划线前缀 `_`**：模块私有函数约定（只在本文件内部使用）。

### 💻 代码（update/delete 接口）

```python
async def _get_article_or_404(db: AsyncSession, article_id: int) -> ArticleRecord:
    """按 id 查文章，查不到直接抛 404（三个接口复用）。"""
    stmt = select(ArticleRecord).where(ArticleRecord.id == article_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"文章不存在: {article_id}")
    return row

@router.put("/{article_id}", response_model=ArticleResp, summary="更新文章")
async def update_article(*, article_id: int = Path(..., gt=0), req: ArticleUpdate, db=Depends(get_db)):
    row = await _get_article_or_404(db, article_id)   # ① 存在性检查
    update_data = req.model_dump(exclude_unset=True)  # ② 只取"明确写了"的字段
    if "topic" in update_data and update_data["topic"] is None:
        raise HTTPException(status_code=422, detail="topic 不能为空")  # ③ 业务校验
    for field, value in update_data.items():          # ④ 逐字段写回
        setattr(row, field, value)
    db.add(row)                                       # ⑤ 写库（add 幂等）
    await db.commit()
    await db.refresh(row)
    return row

@router.delete("/{article_id}", status_code=204, summary="删除文章")
async def delete_article(*, article_id: int = Path(..., gt=0), db=Depends(get_db)):
    row = await _get_article_or_404(db, article_id)   # 不存在先 404
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)                  # 204 显式返回空响应
```

### ⚠️ 踩坑记录

- **topic 传 null 的隐藏坑**：Pydantic 类型校验管不住 `null`（`str | None` 合法），但数据库列是 NOT NULL——必须**业务层**拦下（422）。这就是"类型校验 ≠ 业务校验"。
- **删除后不要 refresh**：行已从库中删除，`refresh` 会报错——所以 delete 不套用"三部曲"。
- **HTTPException 直抛**：第 5 步先用 FastAPI 内置的 `HTTPException`，第 9 步会重构为自定义领域异常（更专业的做法）。

### ✅ 自测验证

```powershell
python scripts/test_api.py put /api/article/1 '{"topic": "新标题"}'   # 200 + topic 更新
python scripts/test_api.py put /api/article/1 '{"topic": null}'       # 422（业务拦截）
python scripts/test_api.py delete /api/article/1                      # 204 无响应体
python scripts/test_api.py get /api/article/1                         # 404（删除生效）
```

### 🧰 沉淀

- **部分更新模板**（模板 I）：`model_dump(exclude_unset=True)` + `setattr` 循环——所有 PUT 接口通用。
- **删除 204 模板**（模板 J）。
- **git 入门**：本步完成配齐 git（init/add/commit/log），第一次提交——版本管理从第 5 步开始。

## 第 6 步：集成大模型（SDK vs 手写 aiohttp + 错误分类）

### 📌 目标

- 集成 DeepSeek 大模型（OpenAI 兼容协议）
- 封装 `call_llm`：超时 / 重试 / 五级错误分类 / 统一 LLMError
- 掌握"**为什么用官方 SDK 而不是手写 HTTP**"

### 🧠 核心知识点

1. **SDK vs 手写 aiohttp 的权衡**（本项目的重要决策）：

| 手写 aiohttp 自己做的 | SDK 帮你做的 |
|----------------------|-------------|
| 拼 URL / headers / payload | `create()` 内部完成 |
| 序列化/解析 JSON | 内部完成（response 对象） |
| 超时 `ClientTimeout` | `timeout` 参数 |
| 重试（手写版没有） | `max_retries` 参数（内置） |
| 错误分类 except | SDK 抛**分类好的异常** |

   结论：**能用官方 SDK 就用**——官方 SDK 是"维护成本最低、错误分类最专业"的选择。自己保留的只有：配置分离、日志、统一 LLMError 包装。

2. **五级错误分类**（`call_llm` 的 except 顺序有讲究）：
   - `AuthenticationError`（401：key 无效）
   - `APITimeoutError`（超时）——**必须先于 APIConnectionError**（它是后者的子类，顺序反了会被先接住）
   - `APIConnectionError`（网络层：DNS/连接被拒）
   - `APIStatusError`（其他非 2xx：429 限流、500 服务端）
   - `APIError`（兜底）
   - 全部包装成 `LLMError` 上抛——**上层接口只认识 LLMError**。

3. **懒加载单例**：`AsyncOpenAI` 内部有连接池，是"重对象"——创建一次反复用。**为什么懒加载**：key 没配置时 import 模块不应报错（test_llm.py 无 key 时靠 call_llm 的开局检查给友好提示）。
4. **`raise ... from None`**：包装异常时不保留原异常链（`from None`）——避免日志里出现 SDK 的内部细节刷屏；需要排查时再改成 `from e`。
5. **`max_tokens` 是成本闸门**：限制生成长度，控制每次调用的费用。

### 💻 代码（llm_service.py 核心）

```python
"""llm_service.py —— 大模型调用服务（DeepSeek，OpenAI 兼容协议，SDK 版）"""
import logging, os
import openai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")   # 密钥（敏感，只在 .env）
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
TIMEOUT_CONNECT = 10
TIMEOUT_TOTAL = 120
MAX_RETRIES = 2

class LLMError(Exception):
    """大模型调用失败的自定义异常（错误分类的第一步）。"""

_client: "openai.AsyncOpenAI | None" = None   # 模块级单例

def get_client() -> openai.AsyncOpenAI:
    """懒加载获取 AsyncOpenAI 单例（第一次调用才创建）。"""
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=openai.Timeout(TIMEOUT_TOTAL, connect=TIMEOUT_CONNECT),
            max_retries=MAX_RETRIES,
        )
    return _client

async def call_llm(messages: list[dict], max_tokens: int = 2000) -> str:
    """调用大模型，返回回复文本。异常统一抛 LLMError。"""
    if not DEEPSEEK_API_KEY:                              # fail fast：没 key 不发请求
        logger.error("未配置 DEEPSEEK_API_KEY")
        raise LLMError("未配置 DEEPSEEK_API_KEY，请在 .env 中填写")
    try:
        resp = await get_client().chat.completions.create(
            model=DEEPSEEK_MODEL, messages=messages, max_tokens=max_tokens,
        )
    except openai.AuthenticationError as e:
        raise LLMError("大模型接口返回 401（API key 无效）") from None
    except openai.APITimeoutError:
        raise LLMError("大模型调用超时，请稍后重试") from None      # 先于连接错误！
    except openai.APIConnectionError as e:
        raise LLMError("网络错误，无法连接大模型服务") from None
    except openai.APIStatusError as e:
        raise LLMError(f"大模型接口返回 {e.status_code}") from None
    except openai.APIError as e:
        raise LLMError("大模型调用失败") from None
    content = resp.choices[0].message.content
    if not content:                                        # 空内容检查
        raise LLMError("大模型返回空内容")
    return content
```

### ⚠️ 踩坑记录

- **except 顺序**：`APITimeoutError` 是 `APIConnectionError` 的子类——顺序写反，超时会被当成网络错误处理。
- **openai 3.x 的 Timeout**：底层是 httpx2，`Timeout` 要么给默认值、要么四个参数全设——写 `Timeout(120)` 会报错，必须 `Timeout(120, connect=10)`。
- **key 不配也 import 不崩**：懒加载设计让 `test_llm.py` 能在无 key 时给出友好提示（"未配置 DEEPSEEK_API_KEY"）而不是 import 阶段崩溃。

### ✅ 自测验证

`scripts/test_llm.py` 三态验证：**无 key**（友好报错）→ **假 key**（401 → LLMError）→ **真 key**（返回真实内容）。这是"手动验证脚本"的样板：验证链路，不靠猜。

### 🧰 沉淀

- **第三方 SDK 封装模板**（模板 K）：懒加载单例 + 超时/重试配置 + 错误分类包装 + 统一异常——所有外部服务（大模型/支付/短信）都这么封装。
- **"能用官方 SDK 就用"决策**：选型时先看官方 SDK，自己手写 HTTP 只在 SDK 缺失时才考虑。

---

## 第 7 步：生成接口（薄 router 厚 service + 缓存优先）

### 📌 目标

- `POST /api/generate`：按选题生成公众号 + 小红书两篇内容
- **缓存优先**：同一选题已生成 → 直接返回（数据库即缓存）
- 分层重构：业务编排收进 service，router 变薄
- 动态状态码：缓存命中 200 / 新生成 201

### 🧠 核心知识点

1. **薄 router 厚 service**：业务编排（查缓存 → 拼 prompt → 调模型 → 解析 → 写库）全部收进 `services/generate_service.py`；router 只剩"收参 + 调 service + 翻译异常"。**service 不 import FastAPI**（不出现 HTTPException/Response）——这样 service 可被接口、脚本、测试任意调用。
2. **缓存优先的实现**：数据库即缓存——`find_cached` 查同 topic + 内容非空的记录，命中直接返回（零成本）。比 Redis 简单，原型阶段够用（生产可换 Redis，见技术债）。
3. **`(record, is_cached)` 元组返回**：让 router 知道是缓存还是新生成，据此动态改状态码（`response.status_code = 200 if is_cached else 201`）。
4. **分隔符解析约定**：模型输出用 `===公众号===` / `===小红书===` 两个标记分两段，`parse_generated` 按标记切分。格式约定脆弱（模型偶尔不按格式来），**解析失败宁可明确报错也不写残缺数据**。
5. **系统提示词（SYSTEM_PROMPT）**：告诉模型角色、任务、输出格式——大模型应用的"说明书"。

### 💻 代码（generate_service.py 核心）

```python
"""generate_service.py —— 文章生成业务编排（薄 router 厚 service）"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import ArticleRecord
from services.llm_service import call_llm
from services.exceptions import ModelOutputError
from services.markdown_service import normalize_markdown, normalize_plain  # 第 12 步接入

SEP_GZH = "===公众号==="   # 公众号段分隔标记
SEP_XHS = "===小红书==="   # 小红书段分隔标记

SYSTEM_PROMPT = (
    "你是一名资深自媒体文案专家。根据用户给出的选题，生成两篇内容：\n"
    "1. 公众号文章：标题 + 正文，有观点有案例；\n"
    "2. 小红书笔记：吸引眼球的标题 + 简洁干货 + 3 个话题标签。\n"
    f"输出格式：先写【{SEP_GZH}】开头的内容，再写【{SEP_XHS}】开头的内容，"
    "两段之间不要有其他文字。"
)

async def find_cached(db: AsyncSession, topic: str) -> ArticleRecord | None:
    """查缓存：同一选题是否已生成过（gzh_article 非空视为已生成）。"""
    stmt = (
        select(ArticleRecord)
        .where(ArticleRecord.topic == topic, ArticleRecord.gzh_article.isnot(None))
        .order_by(ArticleRecord.id.desc())   # 最新的排最前
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

def parse_generated(text: str) -> tuple[str, str]:
    """按分隔符解析模型输出，返回 (公众号内容, 小红书内容)。"""
    parts = text.split(SEP_GZH, 1)
    if len(parts) < 2:
        raise ModelOutputError("模型输出缺少公众号分隔符")
    xhs_parts = parts[1].split(SEP_XHS, 1)
    gzh = xhs_parts[0].strip()
    xhs = xhs_parts[1].strip() if len(xhs_parts) > 1 else ""
    if not gzh:
        raise ModelOutputError("公众号内容为空")   # 宁可报错也不写残缺数据
    return gzh, xhs

async def generate_article(db: AsyncSession, topic: str) -> tuple[ArticleRecord, bool]:
    """生成主流程：查缓存 → 未命中 → 调模型 → 解析 → 规范化 → 写库。"""
    cached = await find_cached(db, topic)
    if cached is not None:                       # 命中缓存：零成本返回
        return cached, True
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": topic},
    ]
    text = await call_llm(messages, max_tokens=2000)
    gzh_article, xhs_note = parse_generated(text)
    # 第 12 步：规范化（公众号 Markdown / 小红书纯文本）
    gzh_article = normalize_markdown(gzh_article)
    xhs_note = normalize_plain(xhs_note)
    db_row = ArticleRecord(topic=topic, gzh_article=gzh_article, xhs_note=xhs_note)
    db.add(db_row)
    await db.commit()
    await db.refresh(db_row)
    return db_row, False
```

```python
# routers/generate_router.py（薄 router）
@router.post("/generate", response_model=ArticleResp, status_code=201, summary="生成文章")
async def generate_api(req: GenerateRequest, db: AsyncSession = Depends(get_db), response: Response = None):
    row, is_cached = await generate_article(db, req.topic)   # 业务全在 service
    response.status_code = 200 if is_cached else 201         # 动态状态码
    return row
```

### ⚠️ 踩坑记录

- **'string' 污染缓存（第 3 步的坑第三次踩）**：Swagger 预填的 `topic: "string"` 被真实生成过 → 之后所有 `topic="string"` 的请求都命中假缓存返回假内容。教训：**"接口有响应 ≠ 功能正确"**，判断标准要看数据库和日志。
- **接口有响应 ≠ 功能正确**：缓存命中返回 200 但内容是脏数据——要用 `SELECT * FROM article_record WHERE topic='string'` 查库验证。
- **解析失败要明确报错**：模型输出格式乱时，宁可 502 也不写残缺数据（写进去的脏数据会污染缓存）。

### ✅ 自测验证

```powershell
python scripts/test_api.py post /api/generate '{"topic": "Python 学习路线"}'
# 第一次 → 201（新生成，等待大模型返回，约 30~120 秒）
# 第二次同一 topic → 200（缓存命中，瞬间返回）
# 边界：topic 空 → 422；key 无效 → 502
# 查库：SELECT * FROM article_record WHERE topic='Python 学习路线'; 确认内容真实
```

### 🧰 沉淀

- **缓存优先模板**（模板 L）：查缓存 → 命中返回 / 未命中重算——所有昂贵操作（AI/计算/IO）通用。
- **薄 router 厚 service 模板**（模板 M）：业务编排收 service，router 只翻译。

---

## 第 8 步：改写接口 + save_row 抽取（复用之道）

### 📌 目标

- `POST /api/refine`：按指令改写指定文章
- **第二次重构**：抽 `save_row`（写库三部曲第 3 次出现 → Rule of Three）
- service 层用领域异常表达"查不到"（为第 9 步铺路）

### 🧠 核心知识点

1. **复用地图**（本步展示"复用之道"）——refine 只新写 3 小段：

| 能力 | 来源 | 复用方式 |
|------|------|---------|
| `call_llm` | llm_service | import（错误分类已封装） |
| `parse_generated` | generate_service | import（输出格式约定一致） |
| `SEP_GZH/SEP_XHS` | generate_service | import（拼原文用同一分隔符） |
| `save_row` | db_helpers（**本步新抽**） | import（写库统一入口） |
| `ArticleRecord` | database | import |

2. **Rule of Three 的实践**：写库三部曲在 create（第 3 步）/ update（第 5 步）/ generate（第 7 步）出现三次 → 第 8 步抽 `save_row`。**为什么第 3 步不抽**：那时还不知道"公共部分"长什么样（YAGNI，过早抽象是浪费）。
3. **`save_row` 的 add 幂等**：对已持久化对象（update 场景）重复 add 是幂等的（SQLAlchemy 忽略），所以增改统一走一个函数。**注意边界**：delete 场景不要用（删除后 refresh 报错）。
4. **默认改写指令**：`instruction or DEFAULT_INSTRUCTION`——用户不传时用默认"优化表达"，接口对调用方友好。
5. **`row.gzh_article or ''`**：None 兜底为空串，避免拼进 prompt 时出现 "None"。

### 💻 代码（db_helpers.py + refine_service.py 核心）

```python
# services/db_helpers.py（第二次重构的产物）
async def save_row(db: AsyncSession, row) -> None:
    """写库三部曲封装：add + commit + refresh，失败自动回滚。

    边界注意：删除场景不要用它——删除后 refresh 会报错。
    """
    db.add(row)                    # ① 登记（新建=INSERT，已存在=UPDATE，幂等）
    try:
        await db.commit()          # ② 落库
        await db.refresh(row)      # ③ 重读权威值（id/时间戳）
    except Exception as e:
        await db.rollback()        # 失败回滚：不留半截数据
        logger.error("写库失败: %s: %s", type(e).__name__, str(e))
        raise DBError("数据库保存失败") from e   # 第 9 步统一用 DBError
```

```python
# services/refine_service.py（只新写三小段）
async def refine_article(db, article_id: int, instruction: str | None = None) -> ArticleRecord:
    """改写指定文章，返回改写后的记录。"""
    row = await db.get(ArticleRecord, article_id)     # ① 查记录
    if row is None:
        raise ArticleNotFoundError(f"文章不存在: {article_id}")   # 领域异常（第 9 步翻译 404）
    original = (
        f"{SEP_GZH}\n{row.gzh_article or ''}\n"
        f"{SEP_XHS}\n{row.xhs_note or ''}"
    )                                                 # ② 拼原文（复用分隔符）
    final_instruction = instruction or DEFAULT_INSTRUCTION
    messages = [
        {"role": "system", "content": REFINE_PROMPT},
        {"role": "user", "content": f"原文如下：\n{original}\n\n改写指令：{final_instruction}"},
    ]
    text = await call_llm(messages, max_tokens=2000)  # ③ 复用：调模型
    gzh_article, xhs_note = parse_generated(text)     # ③ 复用：解析
    gzh_article = normalize_markdown(gzh_article)     # 第 12 步：规范化
    xhs_note = normalize_plain(xhs_note)
    row.gzh_article = gzh_article
    row.xhs_note = xhs_note
    await save_row(db, row)                           # ③ 复用：写库
    return row
```

### ⚠️ 踩坑记录

- **Swagger body 编辑器的尾逗号**：`{"article_id": 10,}`（尾逗号）与 `{"article_id": 10, "instruction": ""}`（删了值没删键）都算请求体问题不是代码问题——**422 的 detail 是定位第一现场**：看 `type` 区分 `json_invalid`（语法层，如尾逗号）和字段校验层（值不合法）。
- **scripts/test_api.py 的诞生**：PowerShell 会把命令行里的双引号剥掉（`'{"a": 1}'` → `{a: 1}`），所以脚本提供**交互式输入**（`input()` 从键盘读），所见即所发——绕开 PowerShell 引号坑和 Swagger 预填坑。

### ✅ 自测验证

```powershell
python scripts/test_api.py post /api/refine   # 交互输入 {"article_id": 10}
# → 200，内容变为"改写结果"（假模型）/ 真实改写（真模型）
# 改写后再 generate 同一 topic → 返回改写后的内容（缓存联动验证）
# 边界：article_id 不存在 → 404；article_id=0 → 422
```

### 🧰 沉淀

- **写库统一入口模板**（模板 N）：save_row 是每个 ORM 项目必备——增改场景全走它。
- **service 层领域异常模板**（模板 O）：查不到 → 抛领域异常（不抛 HTTPException），由 router 翻译。
- **通用 API 测试脚本**（scripts/test_api.py）：urllib 零依赖、交互式输入 JSON，绕开终端引号坑——手动验证接口的通用工具。

## 第 9 步：统一异常处理（领域异常 + 全局处理器）

### 📌 目标

- 集中定义业务异常（`exceptions.py`）
- main.py 注册全局异常处理器（404/502/500 翻译收编一处）
- generate_router 删光 try/except（router 只剩业务调用）
- 路径参数校验前置（`Path(..., gt=0)`）

### 🧠 核心知识点

1. **为什么要集中定义异常**：异常是业务信号。散落在各 service 会造成"同一个错误不同表达"（第 8 步就出现两处"文章不存在"）。**集中定义 + 全局处理器 = 错误分类一处定、翻译一处做**。
2. **专用异常 vs 裸 ValueError**：`ValueError` 太宽泛——业务代码里任何地方都可能抛，全局处理它会把无关错误也误判成"模型问题"。专用异常（`ModelOutputError`） = 精确信号。
3. **异常翻译表**（全局处理器）：
   - `ArticleNotFoundError` → **404**（资源不存在）
   - `ModelOutputError` → **502**（模型输出格式异常——上游数据质量问题）
   - `LLMError` → **502**（大模型调用失败——上游服务不可用）
   - `DBError` → **500**（数据库写失败——我们自己的问题）
   - `Exception`（兜底）→ **500**（第 10 步加）
4. **router 只抛不翻译**：业务层抛领域异常，router 不再 try/except，全局处理器统一翻译——router 只剩"收参 + 调 service + return"。
5. **`Path(..., gt=0)`**：路径参数校验前置——id ≤ 0 在进业务前直接 422，业务代码不需要再判断"id 是否合法"。
6. **`from e` 保留根因链**：`raise DBError("...") from e`——全局处理器只认识 DBError，原始根因通过异常链保留（日志排查用）。

### 💻 代码

```python
# services/exceptions.py —— 业务异常集中定义
class ArticleNotFoundError(Exception):
    """文章不存在的信号（全局处理器翻译成 404）。"""

class ModelOutputError(Exception):
    """模型输出格式异常的信号（全局处理器翻译成 502）。"""

class DBError(Exception):
    """数据库写操作失败的信号（全局处理器翻译成 500）。"""
```

```python
# main.py —— 全局异常处理器（第 9 步新增）
@app.exception_handler(ArticleNotFoundError)
async def article_not_found_handler(request, exc: ArticleNotFoundError):
    logger.warning("资源不存在: %s", exc)              # 兜底日志：所有 404 留痕
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(ModelOutputError)
async def model_output_handler(request, exc: ModelOutputError):
    logger.error("模型输出格式异常: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "模型输出格式异常"})

@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError):
    logger.error("大模型调用失败: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})

@app.exception_handler(DBError)
async def db_error_handler(request, exc: DBError):
    logger.error("数据库操作失败: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "数据库保存失败"})
```

### ⚠️ 踩坑记录

- **"改代码不生效"——服务没重启**：uvicorn 默认**无热重载**，运行中的进程还是旧代码。铁证：响应文案还是第 8 步的"记录不存在"。排障顺序：**改代码 → 重启服务 → 再测**（uvicorn main:app 没有 --reload）。
- **list 接口 500 ResponseValidationError（input: None）**：加 `list()` 包装时**误删了 return 语句**，函数返回 None 无法序列化。**排障流程复盘**：先看 traceback 最底部（异常类型 + 出错行）→ 再复现代码逻辑（签名到 return）→ 别凭感觉改。
- **异常翻译要覆盖全**：删光 router 的 try/except 后，如果某个异常没注册全局处理器，会落到默认 500——用假 key 测试验证 LLMError 真的翻译成 502（不是被吞成 500）。

### ✅ 自测验证

```powershell
python scripts/test_api.py get /api/article/999999     # 404（统一翻译）
python scripts/test_api.py get /api/article/0          # 422（Path 校验前置）
python scripts/test_api.py post /api/refine '{"article_id": 999999}'   # 404
# 假 key（.env 改错）调 generate → 502（LLMError 被翻译，不是裸 500）
```

### 🧰 沉淀

- **统一异常处理模板**（模板 P）：exceptions.py（领域异常） + main.py（全局处理器）——每个 FastAPI 项目必备的"错误分层"。
- **Path 校验前置模板**（模板 Q）：`Path(..., gt=0)`。

---

## 第 10 步：部署前加固（CORS + 限流 + 500 兜底）

### 📌 目标

- CORS（浏览器跨域策略，为前端接入做准备）
- 手写固定窗口限流器（防刷 = 防烧钱）
- 全局 500 兜底（对外不说细节、对内不丢现场）

### 🧠 核心知识点

1. **CORS 是什么**：浏览器**同源策略**——前端域名调本 API 会被浏览器拦截，除非服务器声明允许。`CORSMiddleware` 配置允许的来源列表。
   - 开发期 `*`（允许所有来源）；**生产必须收窄到真实前端域名**（.env 配置 `ALLOWED_ORIGINS`）
   - ⚠️ `"*"` 与 `allow_credentials=True` **冲突**（浏览器规范禁止），用 `*` 时必须 `allow_credentials=False`，否则启动即报错
2. **为什么必须限流**：generate/refine 每次调用**烧大模型 token**，被刷 = 烧钱。限流是"保护钱包"。
3. **固定窗口限流算法**：每个 key 记录 `(窗口起点, 已用次数)`。请求到来：超出窗口则重置，否则计数 +1，超限拒绝。
   - `time.monotonic()`：单调时钟，**不受系统改时间影响**（time.time 会被改系统时间骗过）
   - `defaultdict`：不存在的 key 自动建默认值
4. **全局 500 兜底**：`@app.exception_handler(Exception)`——未注册的异常统一 JSON + `logger.exception` 完整留痕（traceback 进日志）。**"对外不说细节、对内不丢现场"**。
5. **中间件执行顺序**：`add_middleware` 后注册的先执行（洋葱模型）。CORS 必须**最外层**（先 add），否则内层中间件抛错时浏览器收不到 CORS 头。

### 💻 代码（rate_limiter.py + main.py 加固部分）

```python
# services/rate_limiter.py —— 轻量限流器（固定窗口计数）
class FixedWindowLimiter:
    """固定窗口限流器：每个 key 在时间窗口内最多允许 N 次请求。"""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._records: dict[str, list] = defaultdict(lambda: [0.0, 0])  # key -> [起点, 次数]

    def allow(self, key: str) -> bool:
        now = time.monotonic()                 # 单调时钟：不受系统改时间影响
        record = self._records[key]
        if now - record[0] >= self.window_seconds:   # 超出窗口：重置
            record[0] = now
            record[1] = 0
        record[1] += 1                         # 本次计数 +1
        return record[1] <= self.max_requests  # 未超限才放行
```

```python
# main.py —— CORS + 限流中间件 + 500 兜底
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")   # 配置分离
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # 开发 *；生产收窄到前端域名
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,         # 用 * 时必须 False
)

rate_limiter = FixedWindowLimiter(max_requests=30, window_seconds=60)  # 每 IP 每分钟 30 次

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_ip):
        logger.warning("限流触发：IP=%s 路径=%s", client_ip, request.url.path)
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    return await call_next(request)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("未处理异常: %s: %s", type(exc).__name__, str(exc))  # traceback 留痕
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
```

### ⚠️ 踩坑记录

- **限流是"窗口内累计计数"**：实测 31 次连续请求，第 26 次就 429——因为之前测试已消耗额度。**不因换脚本重置**，窗口内全局累计。
- **CORS 启动即报错**：`*` + `allow_credentials=True` 会直接抛错（浏览器规范禁止）——这是"启动期防御"而不是运行期坑。
- **429 响应没有 CORS 头**：如果 CORS 不是最外层，限流中间件返回的 429 会被浏览器拦截（看不到错误详情）。

### ✅ 自测验证

```powershell
# 限流：连续快速请求 31 次，观察第 30 次后出现 429
for ($i=0; $i -lt 35; $i++) { python scripts/test_api.py get /health | Select-String "状态码" }
# 约 60 秒窗口重置后恢复（限流副作用：连续测试后可能 429 约 60 秒，属预期）

# CORS：响应头应含 access-control-allow-origin: *
python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health'); print(r.headers['access-control-allow-origin'])"
```

### 🧰 沉淀

- **限流器模板**（模板 R）：FixedWindowLimiter——单机内存限流，任何原型项目通用。
- **CORS 配置模板**（模板 S）：白名单走环境变量。
- **技术债记录**：固定窗口**边界突刺**（窗口重置瞬间可涌入 2 倍请求）/ 单机内存限流**多实例失效** / 代理后 `client.host` 失真（生产解析 X-Forwarded-For）→ 生产换 Redis/网关限流。

## 第 11 步：自动化测试（pytest 从零到会）

### 📌 目标

- 搭建 pytest 测试体系（conftest + 5 个测试文件，25 用例）
- 掌握三个工程决策：测试库隔离 / session 级 client / mock 大模型
- **里程碑：你独立编写第一条测试**（generate 超长 topic 边界用例）

### 🧠 核心知识点（从零讲起）

1. **测试是什么**：写一段代码"发请求 → 断言结果"，让机器替人检查功能是否正确。跑一次测试 = 自动发几十个请求并核对每个响应。
2. **断言（assert）**：`assert resp.status_code == 201`——如果成立，测试通过；不成立，测试失败（FAILED）。**断言是测试的灵魂**：断言什么，就守护什么。
3. **fixture（夹具）**：测试的"准备工作"。`client` 夹具启动真实应用（含建表），`mock_llm` 夹具把大模型替换成假实现——**测试不花钱、不联网、可重复**。
4. **monkeypatch**：pytest 内置的"打补丁"工具——临时替换函数/属性，测试结束自动还原。
5. **测试设计铁律**：
   - **幂等**：用 `uuid` 随机 topic，跑 100 次结果一致；
   - **断言稳定不变量**：不硬编码 `total` 具体数字（测试库数据会积累），断言"total 是 int、items 是 list"这种结构；
   - **边界全覆盖**：正常路径 + 异常路径（404）+ 边界（422：空/超长/0）。

### 💻 代码（conftest.py —— 测试的"总开关"）

```python
"""tests/conftest.py —— pytest 全局夹具"""
import os  # 操作环境变量（先于业务代码）

# ① 指向独立测试库（绝不污染开发库！）
TEST_DB_NAME = "article_db_tutorial_test"
os.environ["DATABASE_URL"] = (
    f"mysql+aiomysql://root:<your_password>@127.0.0.1:3306/{TEST_DB_NAME}?charset=utf8mb4"
)

# ② 现在才允许 import 业务代码（此时 database.py 读到的是测试库地址）
import asyncio
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi.testclient import TestClient
from main import app

# ③ 测试专用：调大限流阈值（限流逻辑单独单测，接口测试不被干扰）
import main as main_module
main_module.rate_limiter.max_requests = 1_000_000

@pytest.fixture(scope="session", autouse=True)
def ensure_test_db():
    """确保测试库存在（create_all 只建表不建库，库要手动建）。"""
    async def _create() -> None:
        engine = create_async_engine("mysql+aiomysql://root:<your_password>@127.0.0.1:3306/")
        async with engine.connect() as conn:
            await conn.execute(
                text(f"CREATE DATABASE IF NOT EXISTS {TEST_DB_NAME} CHARACTER SET utf8mb4")
            )
        await engine.dispose()
    asyncio.run(_create())

@pytest.fixture(scope="session")
def client(ensure_test_db):
    """真实可调用的 API 客户端（session 级：整个测试共用一个）。"""
    with TestClient(app) as c:   # with = 触发 lifespan（自动建表）
        yield c

@pytest.fixture
def mock_llm(monkeypatch):
    """把大模型调用替换成固定返回的假实现。"""
    async def fake_call_llm(messages: list[dict], max_tokens: int = 2000) -> str:
        return "===公众号===\n测试公众号内容（来自假模型）\n===小红书===\n测试小红书笔记"
    # ⚠ patch 到使用方模块（from x import f 复制了引用，patch 源模块没用）
    monkeypatch.setattr("services.generate_service.call_llm", fake_call_llm)
    monkeypatch.setattr("services.refine_service.call_llm", fake_call_llm)
```

### ⚠️ 踩坑记录（本步实战排障）

- **'NoneType' object has no attribute 'send'（最经典的坑）**：aiomysql 连接与"创建它的事件循环"绑定。TestClient 每实例化新建事件循环——`function` 级 client 会导致第二个测试用新循环去复用旧循环的连接池 → 崩溃。**修正：client 夹具必须 `scope="session"`**（共享一个客户端 = 所有请求在同一循环里跑）。
- **环境变量设置顺序是命门**：`os.environ["DATABASE_URL"]` 必须在 `from main import app` **之前**——database.py 在 import 时就读 DATABASE_URL。顺序反了，测试会连到开发库（污染真实数据）。
- **patch 到使用方模块**：generate_service 里是 `from services.llm_service import call_llm`（复制了引用），所以 `monkeypatch.setattr("services.generate_service.call_llm", ...)`——patch 源模块 `services.llm_service.call_llm` 无效。
- **"弄红测试"的练习**：把限流器 `max_requests` 从 3 改成 2 → 测试 FAILED → 改回 → 全绿。**亲手弄红一次，才知道测试真的在守护代码**。

### ✅ 自测验证

```powershell
.\.venv\Scripts\python.exe -m pytest          # 全量跑
.\.venv\Scripts\python.exe -m pytest tests/test_rate_limiter.py -v   # 单个文件
.\.venv\Scripts\python.exe -m pytest tests/test_generate_api.py::test_生成新文章返回201 -v  # 单个用例
# 期望：25 passed（第 11 步时）；你加的第一条测试后 26 passed
```

### 🧰 沉淀

- **conftest 三件套模板**（模板 S2）：测试库隔离 + session client + mock——任何 FastAPI 项目测试开局直接复制。
- **pytest.ini**：`testpaths = tests` + `pythonpath = .`（让 pytest 认识项目结构）。
- **requirements-dev.txt**：`-r requirements.txt` + pytest + httpx——测试依赖与运行依赖分离。

### 🎓 你独立完成的第一条测试（提交 d8f5652）

```python
def test_生成接口topic超长返回422(mock_llm, client):
    """边界：超长 topic 触发 GenerateRequest 的 max_length=120 校验。"""
    long_topic = "长" * 121                    # 121 个"长"，超过上限 120
    resp = client.post("/api/generate", json={"topic": long_topic})
    assert resp.status_code == 422
```

这条测试的价值：**你从"看不懂测试"到"独立设计边界用例"**——超长输入是 422 校验最典型的边界，这个直觉就是测试思维。

---

## 第 12 步：文本规范化（纯函数 + 业务语义）

### 📌 目标

- 新建 `services/markdown_service.py`（纯函数文本清洗）
- 接入生成/改写流程（只清洗新数据，不动历史数据）
- **设计修正（你评审发现的）**：公众号与小红书规则分开

### 🧠 核心知识点

1. **纯函数三件套**：
   - 无副作用（不碰数据库/网络/文件）——同输入永远同输出
   - 确定性 → **最好测**（输入输出表直接翻译成断言）
   - 可复用 → 任何项目的文本清洗直接拿去用
2. **"排版"为什么做成纯函数而不是新接口**：谁消费这篇文章？——缓存、改写、展示。排版是"数据质量"问题，不是"对外能力"问题——所以做成 service 内部调用（生成/改写后自动规范化），而不是新开一个没人调的接口（YAGNI）。
3. **按业务语义抽象（本步最重要的教训）**：

| 平台 | # 开头的含义 | 规则 |
|------|------------|------|
| 公众号 | Markdown 标题（`# 标题`） | 完整规则：清洗 + 标题前补空行 |
| 小红书 | **话题标签**（`#学习打卡`） | 只清洗：去行尾空白 + 压缩空行 |

   **初版设计缺陷**：把小红书也走了 Markdown 规则，会把话题标签当标题处理（语义错误）——被你评审发现并修正。**教训：抽象要对齐业务语义，不能因为"都是文本清洗"就一刀切。**

4. **只清洗新数据、不动历史数据**：避免破坏第 7 步的缓存逻辑（同一 topic 第二次应命中同一内容——历史数据清洗后内容变了，缓存就不一致）。

### 💻 代码（markdown_service.py）

```python
"""markdown_service.py —— 文本规范化（纯后端文本处理）"""
def _clean_lines(text: str) -> list[str]:
    """内部工具：清洗为"干净的行列表"（公共规则 1 + 2）。"""
    # ① 去掉每行行尾空白（模型输出常见残留空格）
    lines = [line.rstrip() for line in text.split("\n")]
    # ② 压缩连续空行：当前是空行且上一个结果也是空行 → 跳过
    result: list[str] = []
    for line in lines:
        if line == "" and result and result[-1] == "":
            continue
        result.append(line)
    return result

def normalize_markdown(text: str) -> str:
    """公众号用：完整 Markdown 规范化（清洗 + 标题前补空行）。"""
    result = _clean_lines(text)
    # ③ 标题前补空行（# 开头，且前一行不是空行）
    i = 1
    while i < len(result):
        if result[i].startswith("#") and result[i - 1] != "":
            result.insert(i, "")
            i += 1        # 跳过刚插入的空行（列表变长，索引坑！）
        i += 1
    return "\n".join(result).strip()

def normalize_plain(text: str) -> str:
    """小红书用：只清洗（# 是话题标签不是标题，不做标题规则）。"""
    return "\n".join(_clean_lines(text)).strip()
```

### ⚠️ 踩坑记录

- **insert 修改列表长度的索引坑**：`result.insert(i, "")` 后列表变长，必须 `i += 1` 跳过刚插入的空行，否则同一标题会被重复插空行。
- **PowerShell 参数解析坑**：`cmd "a" + $var + "b"` 会把 `+` 当独立参数，导致写坏代码行（曾把 `+` 单独写进代码行）。**文件字符串替换一律用函数封装 + 整段双引号**。
- **幂等性**：规范化函数重复调用结果不变（测试守护）。

### ✅ 自测验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_markdown_service.py -v
# 9 个用例：行尾空白 / 连续空行 / 标题补空行 / 幂等 / 空串 / 话题标签不补空行
```

### 🧰 沉淀

- **纯函数文本清洗模板**（模板 Y）：`_clean_lines` + 两个 public 函数——任何项目的文本清洗直接套用。

---

## 第 13 步：异步任务队列（收官）

### 📌 目标

- `POST /api/tasks`：提交生成任务 → **202 立即返回 task_id**
- `GET /api/tasks/{id}`：轮询任务状态（pending/running/done/failed）
- 自实现"任务表 + asyncio.create_task"（零新依赖）

### 🧠 核心知识点

1. **为什么需要异步任务**：大模型生成要 30~120 秒，同步接口让用户干等 → 连接超时、体验差、线程被占。解法：**提交即返回 + 后台执行 + 轮询状态**——所有 AI 产品的标准架构。
2. **方案权衡**：

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| Celery + Redis | 工业标准、分布式 | 装 Redis + 起 worker + 学习曲线陡 | ❌ 太重（YAGNI） |
| ARQ | 轻量 | 仍需 Redis | ❌ 还是要新组件 |
| **自实现**（任务表 + create_task） | 零新依赖、展示核心机制 | 单进程、重启丢任务 | ✅ 原型最优 |

3. **任务状态机**：`pending（排队）→ running（执行中）→ done（成功）/ failed（失败）`。状态用常量（`TASK_PENDING`）不用魔法字符串——拼写错误立刻 NameError。
4. **`asyncio.create_task`**：把协程"挂"到事件循环上自己跑，调用方**不等它**（类比：下单后外卖自己送，你该干嘛干嘛）。不 `await`——请求立即返回。
5. **202 Accepted 语义**："已受理，处理中"——不是 201（创建完成）、不是 200（同步完成）。
6. **⚠️ 后台任务必须自己开数据库会话**：`Depends(get_db)` 的会话跟着请求走，响应返回后就关闭了——后台协程再用它 = 用已关闭的会话（会崩）。`run_task` 里用 `AsyncSessionLocal()` 自己开。
7. **⚠️ 后台协程的异常没人接**：不 catch 的话任务永远卡在 running——必须 `except Exception` 捕获并写进任务状态（failed + error）。
8. **存储格式 ≠ 传输格式**：result 列存 JSON 字符串（`json.dumps`，含 `ensure_ascii=False` 让中文可读），响应时 `json.loads` 回 dict——手动转换最清晰。

### 💻 代码（task_service.py 核心 + task_router.py）

```python
# services/task_service.py —— 异步任务队列核心
import json, logging
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, TaskRecord
from services.generate_service import generate_article   # 复用生成业务（含缓存）
from services.db_helpers import save_row

TASK_PENDING = "pending"
TASK_RUNNING = "running"
TASK_DONE = "done"
TASK_FAILED = "failed"

async def create_task_record(db: AsyncSession, topic: str) -> TaskRecord:
    """创建任务记录（status=pending）。"""
    task = TaskRecord(topic=topic, status=TASK_PENDING)
    await save_row(db, task)
    return task

async def run_task(task_id: int) -> None:
    """后台执行任务（asyncio.create_task 调用，不阻塞请求）。"""
    async with AsyncSessionLocal() as db:     # ⚠ 自己开会话！
        task = await db.get(TaskRecord, task_id)
        if task is None:
            return
        task.status = TASK_RUNNING            # pending → running
        await db.commit()
        try:
            record, is_cached = await generate_article(db, task.topic)  # 复用！
            task.status = TASK_DONE
            task.result = json.dumps({
                "article_id": record.id, "is_cached": is_cached,
                "gzh_article": record.gzh_article, "xhs_note": record.xhs_note,
            }, ensure_ascii=False)            # 中文不转 \uXXXX
            task.error = None
        except Exception as e:                # ⚠ 后台异常必须捕获！
            task.status = TASK_FAILED
            task.error = str(e)[:500]
        await db.commit()
```

```python
# routers/task_router.py
@router.post("/tasks", response_model=TaskResp, status_code=202, summary="提交生成任务")
async def create_task_api(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    task = await create_task_record(db, req.topic)   # 建任务（pending）
    asyncio.create_task(run_task(task.id))           # 启动后台协程，不 await！
    return task_to_resp(task)                        # 立即返回 202

@router.get("/tasks/{task_id}", response_model=TaskResp, summary="查询任务状态")
async def get_task_api(*, task_id: int = Path(..., gt=0), db=Depends(get_db)):
    task = await get_task_record(db, task_id)
    if task is None:
        raise ArticleNotFoundError(f"任务不存在: {task_id}")   # 复用领域异常 → 404
    return task_to_resp(task)
```

### ⚠️ 踩坑记录（本步实战排障）

- **全量跑失败、单独跑全过（KeyError: 'status'）**：任务轮询测试被**业务限流**打挂——全量跑时前面的测试已消耗限流额度，轮询请求触发 429（响应 `{"detail": ...}` 没有 status 字段）→ KeyError。**修正：conftest 旁路限流（调大阈值）**。原则：**业务限制单独验证（限流器有 4 个单元测试）、接口测试专注业务正确性**。
- **缓存联动验证**：同 topic 提交两次任务 → 第二个任务 `is_cached=True` 且 article_id 一致——证明后台任务完全复用了第 7 步的缓存逻辑（"异步"只是执行方式变了，业务逻辑一行没改）。

### ✅ 自测验证

```powershell
# 真实体验（服务运行时）：提交 → 轮询 → 看到状态流转
python scripts/test_api.py post /api/tasks     # 输入 {"topic": "测试"} → 202 + task_id
python scripts/test_api.py get /api/tasks/1    # pending/running → done
# 边界：task_id=0 → 422；task_id=999999 → 404
.\.venv\Scripts\python.exe -m pytest           # 41 passed
```

### 🧰 沉淀

- **异步任务队列模板**（模板 Z）：任务表 + 状态机 + 后台协程 + 轮询 + 自开会话——任何"耗时操作异步化"项目直接套用（发邮件/批量处理/AI 生成）。
- **技术债诚实记录**：单进程内存调度（重启丢任务、多实例失效）→ 生产换 Celery/ARQ + Redis。核心概念完全一致，换工具只是换执行器。

## 附录 A：最终文件清单与职责

```
doubaofuzhuAgent-tutorial/
├── main.py                  # 入口：装配（FastAPI 实例 / lifespan 建表 / 挂路由 / 全局异常 / CORS / 限流）
├── database.py              # 数据层：异步引擎 / 会话依赖 / ORM 模型（ArticleRecord + TaskRecord）/ 建表
├── routers/
│   ├── article_router.py    # 文章域 CRUD（含 Path 校验、_get_article_or_404 复用）
│   ├── generate_router.py   # AI 域（POST /generate + /refine，薄 router 只剩业务调用）
│   └── task_router.py       # 异步任务域（POST /tasks + GET /tasks/{id}）
├── services/
│   ├── exceptions.py        # 领域异常集中定义（NotFound / ModelOutput / DBError）
│   ├── llm_service.py       # 大模型封装（AsyncOpenAI 单例 + call_llm + 五级错误分类）
│   ├── generate_service.py  # 生成编排（缓存优先 + 解析 + 规范化 + 写库）
│   ├── refine_service.py    # 改写编排（复用 4 个已有能力）
│   ├── markdown_service.py  # 文本规范化（公众号 Markdown / 小红书纯文本）
│   ├── db_helpers.py        # save_row（写库统一入口）
│   ├── rate_limiter.py      # 固定窗口限流器
│   └── task_service.py      # 异步任务核心（状态机 + 后台执行）
├── schemas/
│   ├── article_schemas.py   # 文章域请求/响应模型
│   └── task_schemas.py      # 任务响应模型（TaskResp）
├── scripts/
│   ├── test_api.py          # 通用 API 手动测试脚本（交互输入 JSON）
│   └── test_llm.py          # 大模型链路手动验证（无/假/真 key 三态）
├── tests/                   # pytest（41 用例）
│   ├── conftest.py          # 测试库隔离 + session client + mock_llm
│   ├── test_rate_limiter.py / test_generate_service.py / test_markdown_service.py
│   ├── test_article_api.py / test_generate_api.py / test_task_api.py
├── pytest.ini               # pytest 配置
├── requirements.txt         # 运行依赖（锁定版本）
├── requirements-dev.txt     # 测试依赖（-r requirements.txt + pytest + httpx）
├── .env.example             # 配置模板（占位符，可提交）
├── .gitignore               # 敏感配置 / Python / IDE / 日志
├── LICENSE                  # MIT
└── reuse_snippets.py        # 26 个可复用模板（A~Z）
```

## 附录 B：接口速查表

| 方法 | 路径 | 成功 | 失败 |
|------|------|------|------|
| GET | /health | 200 `{"status":"ok"}` | — |
| GET | / | 200 服务信息 | — |
| POST | /api/article | 201 | 422（topic 空/缺） |
| GET | /api/article/list | 200 total+items | 422（page/page_size 越界） |
| GET | /api/article/{id} | 200 | 404 / 422（id≤0） |
| PUT | /api/article/{id} | 200 | 404 / 422（topic=null） |
| DELETE | /api/article/{id} | 204 | 404 / 422 |
| POST | /api/generate | 201 新生成 / 200 缓存命中 | 422 / 502（模型故障） |
| POST | /api/refine | 200 | 404 / 422 / 502 |
| POST | /api/tasks | 202 + task_id | 422 |
| GET | /api/tasks/{id} | 200 任务状态 | 404 / 422 |

全局：超限流 429；未知异常 500。

## 附录 C：命令速查

```powershell
# ── 服务 ──
.\.venv\Scripts\python.exe main.py                  # 启动（端口从 .env 读）
# ── 测试 ──
.\.venv\Scripts\python.exe -m pytest                # 全量（41 passed）
.\.venv\Scripts\python.exe -m pytest tests/test_rate_limiter.py -v   # 单文件
.\.venv\Scripts\python.exe -m pytest tests/test_task_api.py::test_任务执行完成状态为done -v  # 单用例
# ── 手动测接口（服务运行时）──
.\.venv\Scripts\python.exe scripts/test_api.py get /health
.\.venv\Scripts\python.exe scripts/test_api.py post /api/article '{"topic": "测试"}'
.\.venv\Scripts\python.exe scripts/test_api.py post /api/refine     # 交互输入 JSON
# ── git（装于 E:\DeveloperTools\Git）──
& "E:\DeveloperTools\Git\cmd\git.exe" -C "D:\PyCharm-PROJECT\doubaofuzhuAgent-tutorial" status
& "E:\DeveloperTools\Git\cmd\git.exe" -C "D:\PyCharm-PROJECT\doubaofuzhuAgent-tutorial" add .
& "E:\DeveloperTools\Git\cmd\git.exe" -C "D:\PyCharm-PROJECT\doubaofuzhuAgent-tutorial" commit -m "说明"
& "E:\DeveloperTools\Git\cmd\git.exe" -C "D:\PyCharm-PROJECT\doubaofuzhuAgent-tutorial" push origin main
# ── 查库（mysql 命令不在 PATH 时用临时 python 脚本）──
```

## 附录 D：reuse_snippets.py 模板索引（26 个）

| 编号 | 模板 | 适用场景 |
|------|------|---------|
| A/B | 配置分离 / 日志配置 | 任何 Python 项目开局 |
| C/D | 异步数据库三件套 / ORM 模型 | FastAPI + SQLAlchemy |
| E/F | 请求响应模型分离 / 写库三部曲 | 所有写接口 |
| G/H | 分页三件套 / Query 校验 | 所有列表接口 |
| I/J | 部分更新 / 删除 204 | 所有 PUT/DELETE |
| K | 第三方 SDK 封装 | 大模型/支付/短信 |
| L/M | 缓存优先 / 薄 router 厚 service | 昂贵操作、业务编排 |
| N/O | save_row / 领域异常 | ORM 项目标配 |
| P/Q | 统一异常处理 / Path 校验 | 每个 FastAPI 项目 |
| R/S | 限流器 / CORS | 部署前加固 |
| T~X | 测试相关（conftest 三件套等） | pytest 开局 |
| Y | 纯函数文本清洗 | 任何文本处理 |
| Z | 异步任务队列 | 耗时操作异步化 |

## 附录 E：技术债与未来方向（诚实清单）

| 技术债 | 现状 | 生产解法 |
|--------|------|---------|
| 限流单机内存 | 重启丢计数、多实例失效 | Redis 分布式限流 / 网关限流 |
| 固定窗口边界突刺 | 窗口重置瞬间可涌入 2 倍请求 | 滑动窗口 / 令牌桶 |
| 异步任务内存调度 | 重启丢任务、多实例找不到任务 | Celery/ARQ + Redis |
| 分隔符解析脆弱 | 模型偶尔不按格式输出 | JSON mode / 结构化输出 |
| 缓存用数据库 | 简单够用，高频场景查询重 | 换 Redis + 缓存过期策略 |
| 代理后 IP 失真 | 中间件取 client.host | 解析 X-Forwarded-For |
| 无用户体系 | 任何请求都能调 | 认证鉴权（JWT/OAuth） |
| uvicorn 无热重载 | 改代码要手动重启 | 开发用 --reload |

**未来方向（按优先级）**：
1. 接口对外化：认证（AppKey）+ 配额计费（限流已有基础）
2. 前端页面（后端契约已就绪：Swagger + 异步任务轮询接口）
3. 部署上线：Docker + 云服务器 + HTTPS + 监控（/health 已备）

---

## 🎓 结语

13 步走完，你收获的不只是一个项目，而是一套**可迁移的工程能力**：

- **决策能力**：Rule of Three、YAGNI、SDK vs 手写、自实现 vs Celery——每个选择都有权衡依据
- **排障能力**：traceback 从下往上读、改代码要重启、查库验证"接口有响应 ≠ 功能正确"
- **质量意识**：测试守护、纯函数好测、错误分类一处定
- **工程习惯**：配置分离、日志、锁定依赖、git 每步提交、技术债诚实记录

**这套能力比代码值钱**——因为代码只属于这个项目，而能力属于你的整个工程师生涯。

> 下一步（等你准备好）：前端（后端契约已冻结）→ 部署上线 → 或者开启下一个项目。
> 这份手册 + README 故事点 + reuse_snippets 模板库，就是你面试时最完整的"学习证据链"。
