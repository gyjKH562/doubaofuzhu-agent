# 自媒体文案生成工具（后端）

> 个人学习作品集项目 · 从 0 到 1 迭代构建中（当前进度：第 4 步）

基于 FastAPI 的文案生成工具后端：输入选题，生成公众号文章和小红书笔记。
按"增量迭代"方式从零构建：每步只实现最小可用功能，先跑通原型再逐步加固。

**当前已落地**：服务骨架（配置分离 / 日志 / 健康检查）+ 数据库层（异步 ORM / 自动建表）+ 文章写读接口（创建 / 单条查询 / 分页列表 / 关键词搜索）。
**规划中**：更新删除（CRUD 闭环）→ 大模型集成（DeepSeek）→ 生成/改写接口 → 限流加固 → 自动化测试。

## 技术栈

- Python 3.13
- FastAPI 0.141.1 —— 异步 Web 框架（自带 Pydantic 校验 / 自动文档）
- uvicorn 0.52.4 —— ASGI Web 服务器
- SQLAlchemy 2.0.52 —— ORM（异步引擎 + 现代 Mapped 写法 + select 查询）
- aiomysql 0.3.2 —— 异步 MySQL 驱动
- cryptography 50.0.1 —— MySQL 8 默认认证方式所需
- python-dotenv 1.2.3 —— 读取 .env 环境变量配置
- MySQL 8.x —— 数据存储

## 当前进度

- [x] 第 1 步：环境准备 + 最小骨架（虚拟环境 / 依赖锁定 / 配置分离 / logging / /health 健康检查）
- [x] 第 2 步：数据库层（SQLAlchemy 2.0 异步引擎 / 会话依赖 / ORM 模型 / 启动自动建表）
- [x] 第 3 步：写接口（POST 保存文章记录：请求/响应模型分离 + 写库三部曲 + 边界校验）
- [x] 第 4 步：读接口（单条查询 404 / 分页 count+offset+limit / 关键词参数化搜索）
- [ ] 后续：CRUD 闭环 → 大模型集成 → 生成/改写接口 → 异常处理 → 限流加固 → 自动化测试

## 快速开始

### 环境要求

- Windows / macOS / Linux
- Python 3.13+
- MySQL 8.x（本机运行，默认端口 3306）

### 1. 创建数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS article_db CHARACTER SET utf8mb4"
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
# 然后用编辑器打开 .env，把 DATABASE_URL 里的密码改成你自己的 MySQL root 密码
```

### 4. 启动服务

```powershell
python main.py
```

启动日志出现 `数据库初始化完成` 即表示连库成功、表已就绪。

### 5. 验证

- 健康检查：浏览器打开 `http://127.0.0.1:8000/health` → 返回 `{"status":"ok"}`
- 接口文档：浏览器打开 `http://127.0.0.1:8000/docs` → 看到 Swagger 页面，可直接点 "Try it out" 调接口
- 建表确认：`mysql -u root -p article_db -e "SHOW TABLES;"` → 看到 `article_record`

> 端口提示：本项目用 8000（`.env` 的 APP_PORT 控制）。曾实战遇到 8000 被本机其他程序占用，
> 改 `.env` 的 APP_PORT 即可、无需改代码——这就是配置分离的意义；后续已改回 8000。

## API 概览（当前已实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查，探测服务是否存活 |
| GET | / | 服务基本信息 |
| GET | /docs | 自动生成的 Swagger 接口文档 |
| POST | /api/article | 创建文章记录（topic 必填，≤120 字；gzh_article/xhs_note 可选） |
| GET | /api/article/list | 列表分页 + 关键词搜索（page / page_size / keyword 参数） |
| GET | /api/article/{article_id} | 按 id 查询单条（不存在返回 404） |

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| APP_HOST | 127.0.0.1 | 服务监听地址 |
| APP_PORT | 8000 | 服务监听端口 |
| DATABASE_URL | mysql+aiomysql://... | 异步 MySQL 连接串（库名 article_db，utf8mb4） |

## 项目结构

```
doubaofuzhuAgent-tutorial/
├── main.py            # 应用入口：FastAPI 实例、lifespan 启动建表、文章写读接口
├── database.py        # 数据库层：异步引擎 / 会话依赖 / ORM 模型 / 建表函数
├── schemas/
│   ├── __init__.py    # 包标记
│   └── article_schemas.py  # 请求/响应模型（ArticleCreate / ArticleResp / ArticleListResp）
├── requirements.txt   # 运行依赖（版本锁定）
├── .env.example       # 配置模板（提交 git）
├── .env               # 本地配置（不提交 git）
└── .gitignore         # git 忽略规则
```

## 开发路线图（Roadmap）

按增量迭代推进，每步最小可用、跑通再加固：

1. ✅ 环境准备 + 最小骨架（配置分离 / 日志 / 健康检查）
2. ✅ 数据库层（异步 ORM + 自动建表）
3. ✅ 写接口：POST 保存文章记录（先不接大模型）
4. ✅ 读接口：单条查询 + 列表分页 + 关键词搜索
5. ⬜ 更新 + 删除接口（CRUD 闭环）
6. ⬜ 集成大模型：aiohttp 调用 DeepSeek（超时 / 日志 / 错误处理）
7. ⬜ 生成接口串联：缓存命中 + 调模型 + 写库
8. ⬜ 文章改写接口（复用之道的实践）
9. ⬜ 统一异常处理 + 参数校验强化
10. ⬜ 限流 + CORS（部署前加固）
11. ⬜ pytest 自动化测试
12. ⬜ 可选：Markdown 排版模块（纯后端文本处理）
13. ⬜ 可选：异步任务队列

> 前端页面（HTML/JS）不在当前学习范围：现阶段聚焦后端，后续按需引入。

## 学习记录

- 2026-09-08：第 1 步完成——虚拟环境、依赖版本锁定、.env 配置分离、logging 日志、/health 健康检查接口；实战处理了 8000 端口被占用问题（配置分离的价值验证）。
- 2026-09-08：第 2 步完成——SQLAlchemy 2.0 异步引擎、会话依赖注入、ArticleRecord ORM 模型、启动自动建表；补齐 MySQL 8 认证所需的 cryptography 依赖。
- 2026-09-09：第 3 步完成——POST 写接口、请求/响应模型分离（schemas）、写库三部曲（add/commit/refresh + rollback）、边界校验；实战踩坑：Swagger 的 "Try it out" 会预填示例值，直接执行会把示例数据写进库（定位法：查库看实际存的 topic）。
- 2026-09-09：第 4 步完成——读接口三件套：单条查询（scalar_one_or_none + 404）、分页（count + offset/limit，offset=(page-1)×page_size）、关键词搜索（contains 参数化防注入）；掌握路由声明顺序坑（静态路径必须声明在动态路径之前）与 Query 参数校验（ge/le/max_length）。
