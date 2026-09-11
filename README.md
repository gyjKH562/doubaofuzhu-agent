# 自媒体文案生成工具（后端）

> 个人学习作品集项目 · 从 0 到 1 迭代构建中（当前进度：第 10 步）

基于 FastAPI 的文案生成工具后端：输入选题，生成公众号文章和小红书笔记。
按"增量迭代"方式从零构建：每步只实现最小可用功能，先跑通原型再逐步加固。

**当前已落地**：服务骨架（配置分离 / 日志 / 健康检查）+ 数据库层（异步 ORM / 自动建表）+ 文章 CRUD 闭环（创建 / 查询 / 分页搜索 / 更新 / 删除）+ 路由分层重构 + 大模型调用能力（OpenAI SDK 异步封装：超时 / 重试 / 五级错误分类）+ 生成/改写接口串联（缓存优先）+ 复用之道的实践（save_row）+ 统一异常处理（业务异常集中定义 + 全局处理器 + 参数校验强化）+ **部署前加固**（CORS / 限流 / 全局 500 兜底）。
**规划中**：自动化测试。

## 技术栈

- Python 3.13
- FastAPI 0.141.1 —— 异步 Web 框架（自带 Pydantic 校验 / 自动文档 / 中间件体系）
- uvicorn 0.52.4 —— ASGI Web 服务器
- SQLAlchemy 2.0.52 —— ORM（异步引擎 + 现代 Mapped 写法 + select 查询）
- aiomysql 0.3.2 —— 异步 MySQL 驱动
- cryptography 50.0.1 —— MySQL 8 默认认证方式所需
- openai 3.11.0 —— 官方 SDK 异步客户端（AsyncOpenAI 调用 DeepSeek，兼容 OpenAI 协议）
- python-dotenv 1.2.3 —— 读取 .env 环境变量配置
- MySQL 8.x —— 数据存储
- Git —— 版本管理（每完成一步提交一次）

## 当前进度

- [x] 第 1 步：环境准备 + 最小骨架（虚拟环境 / 依赖锁定 / 配置分离 / logging / /health 健康检查）
- [x] 第 2 步：数据库层（SQLAlchemy 2.0 异步引擎 / 会话依赖 / ORM 模型 / 启动自动建表）
- [x] 第 3 步：写接口（POST 保存文章记录：请求/响应模型分离 + 写库三部曲 + 边界校验）
- [x] 第 4 步：读接口（单条查询 404 / 分页 count+offset+limit / 关键词参数化搜索）
- [x] 第 5 步：更新 + 删除接口（CRUD 闭环）+ 第一次重构（抽 routers/article_router.py）
- [x] 第 6 步：集成大模型（AsyncOpenAI 调用 DeepSeek：超时 / 重试 / 五级错误分类 / 懒加载单例）
- [x] 第 7 步：生成接口串联（缓存命中 + 调模型 + 写库 + 动态状态码）
- [x] 第 8 步：改写接口 + 第二次重构（写库三部曲抽成 save_row，复用之道的实践）
- [x] 第 9 步：统一异常处理 + 参数校验强化（业务异常集中定义 / 全局处理器 / router 瘦身 / Path 校验）
- [x] 第 10 步：部署前加固（CORS 跨域 / IP 限流 / 全局 500 兜底）
- [ ] 后续：pytest 自动化测试

## 快速开始

### 环境要求

- Windows / macOS / Linux
- Python 3.13+
- MySQL 8.x（本机运行，默认端口 3306）
- DeepSeek API key（platform.deepseek.com 申请，新用户有免费额度）

### 1. 创建数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS article_db_tutorial CHARACTER SET utf8mb4"
```

### 2. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows PowerShell 激活虚拟环境
pip install -r requirements.txt
```

### 3. 配置环境变量

```powershell
Copy-Item .env.example .env
# 打开 .env 修改：
#   DATABASE_URL 里的 <your_password> → 你的 MySQL root 密码
#   DEEPSEEK_API_KEY 的 <your_api_key> → 你的 DeepSeek API key
#   ALLOWED_ORIGINS（可选）→ 开发用 *；上线改为前端真实域名
```

### 4. 启动服务

```powershell
python main.py
```

启动日志出现 `数据库初始化完成` 即表示连库成功、表已就绪。

### 5. 验证

- 健康检查：浏览器打开 `http://127.0.0.1:8000/health` → 返回 `{"status":"ok"}`
- 接口文档：浏览器打开 `http://127.0.0.1:8000/docs` → 看到 Swagger 页面（注意：Try it out 会预填示例值，手动改掉再执行）
- 大模型链路：`python scripts/test_llm.py` → 打印"模型回复：..."（需已配置 key）
- 生成链路：`python scripts/test_api.py post /api/generate` → 输入 `{"topic": "你的选题"}` → 第一次 201、同 topic 第二次 200（缓存命中）
- 改写链路：`python scripts/test_api.py post /api/refine` → 输入 `{"article_id": 10, "instruction": "写得更口语化"}` → 200

> 命令行测试用 `scripts/test_api.py`（交互式输入 JSON body，绕开 PowerShell 引号转义与 Swagger 预填坑）。
> 端口提示：本项目用 8000（`.env` 的 APP_PORT 控制）。曾实战遇到 8000 被本机其他程序占用，
> 改 `.env` 的 APP_PORT 即可、无需改代码——这就是配置分离的意义；后续已改回 8000。
> 改代码后必须重启服务（uvicorn 默认无热重载）——"改完不生效"第一排查项是"重启了吗"。
> 限流：每 IP 每分钟 30 次（全局限流）。连续测试超 30 次会遇 429，等窗口重置即可——这是限流在工作。

## API 概览（当前已实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查，探测服务是否存活 |
| GET | / | 服务基本信息 |
| GET | /docs | 自动生成的 Swagger 接口文档 |
| POST | /api/article | 创建文章记录（topic 必填，≤120 字；gzh_article/xhs_note 可选）→ 201 |
| GET | /api/article/list | 列表分页 + 关键词搜索（page / page_size / keyword 参数） |
| GET | /api/article/{article_id} | 按 id 查询单条（不存在 404；id≤0 直接 422，校验前置） |
| PUT | /api/article/{article_id} | 部分更新（只改传入字段；topic 传 null → 422 拦截） |
| DELETE | /api/article/{article_id} | 按 id 删除（成功返回 204 无内容） |
| POST | /api/generate | 按选题生成公众号文章 + 小红书笔记：缓存命中 200 / 新生成 201 / 大模型失败 502 |
| POST | /api/refine | 按指令改写指定文章：成功 200 / 文章不存在 404 / 大模型失败 502 |

> 第 9 步起，404/422/502/500 的错误翻译统一由全局异常处理器负责（router 只抛异常、不翻译）。
> 第 10 步起，任意接口超限流返回 429；未知异常统一 500 JSON（不泄漏内部细节）。

## 工程故事点（面试 / 作品集展示用）

这些是本项目里"能讲出道理"的设计决策，每个都能展开聊 2~3 分钟：

1. **为什么第 5 步才抽路由？——Rule of Three**
   第 3、4 步接口少，抽路由是过度设计；到第 5 步接口满 5 个、`_get_article_or_404` 逻辑第 3 次出现，抽的收益才真正兑现。判断"何时重构"比"怎么重构"更值钱。
2. **PUT 部分更新怎么实现？——exclude_unset 区分"没传"和"传了 null"**
   `model_dump(exclude_unset=True)` 只取请求里显式出现的字段，实现"传什么改什么"；并识别出"传 null 置空 NOT NULL 列"这个坑，用 422 拦截。语义上更接近 PATCH，但实用主义优先。
3. **DELETE 为什么返回 204 而不是 200？**
   204 No Content = "删除成功但无内容可返回"，状态码本身传达语义，前端一行处理。
4. **分页为什么查两次？**
   `COUNT(*)` 拿总数 + `LIMIT/OFFSET` 拿当前页，MySQL 没有一体语法，这是业界标准做法；offset=(page-1)×page_size。
5. **搜索为什么用 contains 而不是拼字符串？**
   参数化查询防 SQL 注入——永远不用 f-string 拼 SQL。
6. **密码 / API key 为什么不进仓库？**
   `.env` 进 .gitignore，`.env.example` 用占位符——真实密钥永不进 git 历史。
7. **git 每步一提交**
   版本历史 = 学习轨迹，随时可回退对比。
8. **大模型调用为什么用官方 SDK 而不是手写 HTTP？**
   手写 aiohttp 的价值是看懂底层（URL/headers/JSON/超时/异常），而 SDK 内置了重试（max_retries）、超时（Timeout）、连接池（单例复用）、异常分类（AuthenticationError/Timeout/ConnectionError/StatusError）。**原理懂了之后，生产用 SDK 是效率选择**——能说出"SDK 替你做了什么"才是真懂。
9. **错误为什么分五类？**
   认证 401 / 超时 / 网络 / 状态码（429、500）/ 兜底——调用方看到错误类别就知道下一步动作（换 key / 重试 / 查网络）。其中 `APITimeoutError` 必须先于 `APIConnectionError` 捕获（子类关系）。
10. **懒加载单例是什么？**
    重对象（连接池客户端）只创建一次、反复复用；懒加载（用到才建）避免 import 副作用（key 未配时不崩）。
11. **生成接口的缓存为什么先查数据库而不是引 Redis？——YAGNI**
    缓存 = article_record 表本身：同选题已生成过就直接返回，零新组件、持久共享、重启不丢。能用查询解决的先不引组件，数据量大了再考虑 Redis。
12. **502 和 500 怎么区分？**
    502 = 上游（大模型）挂了，运维去查大模型服务；500 = 我们自己的代码/数据库出问题，运维来查你。错误归属决定排障方向——所以 service 抛业务异常，router 翻译成准确的状态码。
13. **薄 router、厚 service 的分层原则**
    router 只做"收参 + 翻译异常"，业务编排（缓存/调模型/写库）在 service；service 不 import FastAPI，可被接口、脚本、测试任意调用——依赖方向只能从上往下，不能反过来。
14. **写库三部曲第 3 次出现时抽成 save_row——Rule of Three 兑现**
    create / update / generate 三处重复的 add+commit+refresh+rollback，收敛成一个 `save_row(db, row)`。收益不只是少写代码：**写库逻辑只有一处**，以后加审计日志、换驱动只改一个函数。delete 不纳入（删除后 refresh 会报错）——公共函数要写明适用边界。
15. **分层下"同一事实、两种信号"**
    "文章不存在"——router 层（article_router）用 `HTTPException(404)`，service 层（refine_service）用自定义异常 `ArticleNotFoundError`。为什么不能统一？service 不 import FastAPI，它不知道 HTTP 是什么；后厨（service）喊一声，前台（router）决定怎么跟客人说。
16. **错误翻译从接口收编到全局处理器——第 2 次 Rule of Three**
    第 7、8 步每个接口手动写 4 个 except 分支（同一份翻译写了 3 遍），第 9 步收编：异常类集中定义（exceptions.py），翻译集中注册（main.py 的 exception_handler），router 只剩"收参 + 调 service + 返回"三行。**铁律：router 里不能留 except Exception 兜底**——它会先接住领域异常（LLMError 也是 Exception 子类），全局处理器永远收不到（"502 变 500"的头号原因）。
17. **专用异常 vs 裸 ValueError**
    模型输出解析失败为什么定义 `ModelOutputError` 而不是抛 `ValueError`？ValueError 太宽泛——业务代码里任何地方都可能抛它，全局处理它会把无关错误也误判成"模型问题"。**内建异常表达通用语法错误，业务语义用自定义异常**——精确的信号才能精确地归因。
18. **参数校验前置（fail fast）**
    `Path(..., gt=0)` 让非法 id 在进业务层之前就被 422 拦下——非法输入不该消耗数据库查询。行为变化：以前 `GET /api/article/0` 查库返回 404，现在直接 422。校验越靠前，代码越不容易被脏输入打穿。
19. **为什么大模型项目必须限流？——成本控制**
    generate/refine 每次调用都烧 DeepSeek token，被脚本刷一晚上 = 真金白银。限流（每 IP 每分钟 30 次）是"保护钱包"的工程手段。手写固定窗口（零依赖） vs slowapi（功能全） vs 网关限流（生产首选）——原型阶段手写，够用即止（YAGNI）。限流计时用 `time.monotonic()`（单调时钟）——防用户改系统时间绕过。
20. **CORS：开发期 `*`，生产必须收窄**
    浏览器同源策略是"门卫查学生证"（浏览器拦截跨域响应），不是"查能力"（curl 不受影响）。`*` + `allow_credentials=True` 是浏览器规范禁止的组合，FastAPI 启动即报错。中间件洋葱模型：CORS 必须在外层（先 add），否则预检请求 OPTIONS 会被内层限流误计数。白名单走 `.env` 配置（配置分离第 3 次实践）。
21. **全局 500 兜底：对外不说细节，对内不丢现场**
    未注册异常原来返回 `Internal Server Error` 纯文本（没结构、泄漏信息、无日志）。兜底处理器：响应干净 JSON `{"detail": "服务器内部错误"}`，日志用 `logger.exception` 记录完整 traceback——客户端拿不到内部细节，运维能拿到完整现场。

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| APP_HOST | 127.0.0.1 | 服务监听地址 |
| APP_PORT | 8000 | 服务监听端口 |
| DATABASE_URL | mysql+aiomysql://... | 异步 MySQL 连接串（库名 article_db_tutorial，utf8mb4） |
| DEEPSEEK_API_KEY | （无） | DeepSeek API 密钥（敏感，仅存 .env） |
| DEEPSEEK_BASE_URL | https://api.deepseek.com | DeepSeek 接口地址（/v1 仅为兼容 OpenAI 而设） |
| DEEPSEEK_MODEL | deepseek-chat | 模型名（deepseek-chat / deepseek-reasoner） |
| ALLOWED_ORIGINS | * | CORS 允许的来源，逗号分隔；开发 `*`，上线改前端真实域名 |

## 项目结构

```
doubaofuzhuAgent-tutorial/
├── main.py                # 应用入口（装配）：FastAPI 实例、lifespan 建表、挂载路由、全局异常处理器、CORS/限流中间件
├── database.py            # 数据库层：异步引擎 / 会话依赖 / ORM 模型 / 建表函数
├── routers/
│   ├── __init__.py        # 包标记
│   ├── article_router.py  # 文章域 CRUD 接口（APIRouter 组织，含 Path 参数校验）
│   └── generate_router.py # AI 域接口（POST /api/generate + /api/refine，薄 router 只剩业务调用）
├── services/
│   ├── __init__.py        # 包标记
│   ├── exceptions.py      # 业务异常集中定义（ArticleNotFoundError / ModelOutputError / DBError）
│   ├── rate_limiter.py    # 轻量限流器（固定窗口计数，monotonic 时钟）
│   ├── db_helpers.py      # 数据库操作公共函数（save_row 写库统一入口，失败抛 DBError）
│   ├── llm_service.py     # 大模型调用服务（AsyncOpenAI 单例 + call_llm + 错误分类）
│   ├── generate_service.py # 生成业务编排（缓存优先 + 解析 + 写库）
│   └── refine_service.py  # 改写业务编排（查记录 + 拼改写 prompt + 复用解析/写库）
├── schemas/
│   ├── __init__.py        # 包标记
│   └── article_schemas.py # 请求/响应模型（Create/Resp/ListResp/Update/Generate/Refine）
├── scripts/
│   ├── test_llm.py        # 手动验证脚本：大模型调用链路（非 pytest）
│   └── test_api.py        # 通用 API 测试脚本（交互输入 JSON，绕开 PowerShell 引号坑）
├── requirements.txt       # 运行依赖（版本锁定）
├── .env.example           # 配置模板（提交 git，密码/key 用占位符）
├── .env                   # 本地配置（不提交 git）
└── .gitignore             # git 忽略规则
```

## 开发路线图（Roadmap）

按增量迭代推进，每步最小可用、跑通再加固：

1. ✅ 环境准备 + 最小骨架（配置分离 / 日志 / 健康检查）
2. ✅ 数据库层（异步 ORM + 自动建表）
3. ✅ 写接口：POST 保存文章记录（先不接大模型）
4. ✅ 读接口：单条查询 + 列表分页 + 关键词搜索
5. ✅ 更新 + 删除接口（CRUD 闭环）+ 抽路由重构
6. ✅ 集成大模型：AsyncOpenAI 调用 DeepSeek（超时 / 重试 / 错误分类）
7. ✅ 生成接口串联：缓存命中 + 调模型 + 写库 + 动态状态码
8. ✅ 改写接口：POST /api/refine + 抽 save_row（复用之道的实践）
9. ✅ 统一异常处理：业务异常集中定义 + 全局处理器 + 参数校验强化（router 瘦身）
10. ✅ 部署前加固：CORS 跨域 + IP 限流 + 全局 500 兜底
11. ⬜ pytest 自动化测试
12. ⬜ 可选：Markdown 排版模块（纯后端文本处理）
13. ⬜ 可选：异步任务队列

> 前端页面（HTML/JS）不在当前学习范围：现阶段聚焦后端，后续按需引入。

## 学习记录

- 2026-09-08：第 1 步完成——虚拟环境、依赖版本锁定、.env 配置分离、logging 日志、/health 健康检查接口；实战处理了 8000 端口被占用问题（配置分离的价值验证）。
- 2026-09-08：第 2 步完成——SQLAlchemy 2.0 异步引擎、会话依赖注入、ArticleRecord ORM 模型、启动自动建表；补齐 MySQL 8 认证所需的 cryptography 依赖。
- 2026-09-09：第 3 步完成——POST 写接口、请求/响应模型分离（schemas）、写库三部曲（add/commit/refresh + rollback）、边界校验；实战踩坑：Swagger 的 "Try it out" 会预填示例值，直接执行会把示例数据写进库（定位法：查库看实际存的 topic）。
- 2026-09-09：第 4 步完成——读接口三件套：单条查询（scalar_one_or_none + 404）、分页（count + offset/limit，offset=(page-1)×page_size）、关键词搜索（contains 参数化防注入）；掌握路由声明顺序坑（静态路径必须声明在动态路径之前）与 Query 参数校验（ge/le/max_length）。
- 2026-09-09：第 5 步完成——PUT 部分更新（exclude_unset 区分"没传"和"传了 null"，422 拦截置空）、DELETE 204 语义；第一次重构：抽 routers/article_router.py（Rule of Three）+ _get_article_or_404 复用函数；配齐 git 版本管理（init/add/commit/log，第一次提交 acddee）；安全习惯：.env.example 密码改占位符，真实密码只留在 .env 且不进 git。
- 2026-09-10：第 6 步完成——集成大模型：对比手写 aiohttp 后选用 OpenAI 官方 SDK（AsyncOpenAI）；懒加载单例客户端（连接池复用）、max_retries 内置重试、Timeout 配置、五级异常分类（认证/超时/网络/状态码/兜底）与空内容检查（思考模型边界）；配置分离（API key 仅存 .env）；手动验证脚本 scripts/test_llm.py（无 key / 假 key / 真 key 三态验证）。
- 2026-09-11：第 7 步完成——生成接口串联：业务编排收进 services/generate_service.py（薄 router 厚 service，service 不依赖 web 框架）；缓存优先（同选题已生成直接返回，数据库即缓存）；分隔符解析模型输出；动态状态码（缓存命中 200 / 新生成 201，函数返回 (record, is_cached) 元组）；502 vs 500 错误归属。实战踩坑两次：① Swagger 示例值 'string' 污染缓存（第 3 步的坑第三次踩），脏数据导致生成接口命中假缓存返回假内容——教训："接口有响应 ≠ 功能正确"，判断标准看数据库和日志；② 项目从 E 盘整体迁到 D 盘 + PyCharm 重装，验证 venv/git/.env/数据库四件套迁移无损。
- 2026-09-11：第 8 步完成——改写接口 POST /api/refine：业务编排收进 services/refine_service.py（复用 call_llm / parse_generated / 分隔符 / save_row，只新写"查记录 + 拼 prompt + 更新字段"三小段）；第二次重构：写库三部曲第 3 次出现 → 抽 services/db_helpers.py 的 save_row（create/update/generate/refine 四路写库收敛一处，delete 因不可 refresh 不纳入）；service 层用 ArticleNotFoundError 表达"查不到"，router 翻译 404；改写后缓存联动（同选题再 generate 返回改写后内容）。实战踩坑：Swagger body 编辑器的尾逗号（{"article_id": 10,}）与"删了值没删键"（instruction: ""）都算请求体问题不是代码问题——422 的 detail 是定位第一现场（看 type 区分 json_invalid 语法层 / 字段校验层）；自制 scripts/test_api.py 通用测试脚本（交互式输入 JSON，绕开 PowerShell 引号转义与 Swagger 预填坑，GET/POST/PUT/DELETE 通用）。
- 2026-09-11：第 9 步完成——统一异常处理：新建 services/exceptions.py 集中定义业务异常（ArticleNotFoundError / ModelOutputError / DBError）；main.py 注册全局异常处理器（404/502/502/500 翻译收编一处）；db_helpers.save_row 失败改抛 DBError；generate_service/refine_service 解析失败改抛 ModelOutputError（专用异常替代裸 ValueError）；generate_router 删光全部 try/except（router 只剩业务调用）；article_router 的 _get_article_or_404 改抛领域异常（与 refine 域统一信号）+ 路径参数 Path(gt=0) 校验前置。实战踩坑两次：① 改代码不生效——服务没重启（uvicorn 默认无热重载，运行中的进程还是旧代码；铁证：响应文案还是第 8 步的"记录不存在"）；② list 接口 500 ResponseValidationError（input: None）——加 list() 包装时误删了 return 语句，函数返回 None 无法序列化；排障流程复盘：先看 traceback 最底部（异常类型 + 出错行），再复现代码逻辑，别凭感觉改；教训：复现要覆盖函数整体（签名到 return），不能只测片段。另掌握：假 key 测试验证 LLMError 全局转 502 未被吞成 500（router 删干净的运行证据）。
- 2026-09-11：第 10 步完成——部署前加固三件套：① CORS（CORSMiddleware，白名单走 ALLOWED_ORIGINS 配置，开发 `*`，`allow_credentials=False` 避冲突，必须外层先 add）；② 限流（手写 FixedWindowLimiter 固定窗口：monotonic 时钟 + defaultdict 计数，每 IP 每分钟 30 次，超限 429；为什么必须限流——generate/refine 每次调用烧 token，被刷 = 烧钱）；③ 全局 500 兜底（exception_handler(Exception)：干净 JSON + logger.exception 完整留痕，"对外不说细节、对内不丢现场"）。实战验证：31 次连续请求，第 26 次就 429（因为之前测试已消耗额度）——证明限流是"窗口内累计计数"，不因换脚本重置；CORS 头实测 access-control-allow-origin: *。技术债记录：固定窗口边界突刺 / 单机内存限流多实例失效 / 代理后 client.host 失真（生产解析 X-Forwarded-For）→ 生产换 Redis/网关。
